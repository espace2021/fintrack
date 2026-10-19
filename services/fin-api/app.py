"""FinTrack API — fausse API d'une néobanque, pour les ateliers.

Génère en continu des transactions bancaires réalistes (dont ~2 % de fraudes),
un référentiel clients/comptes et des cours de bourse fictifs.
Environ 5 % des transactions sont volontairement « abîmées » (montant en texte,
casse, date, doublon…) pour simuler un système source imparfait.
Documentation interactive : http://localhost:8000/docs
"""
import os
import random
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from faker import Faker
from fastapi import Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from fastapi_offline import FastAPIOffline as FastAPI  # Swagger servi en local, sans CDN

SEED = int(os.getenv("SEED", "42"))
API_KEY = os.getenv("API_KEY", "atelier")
TX_PER_SECOND = float(os.getenv("TX_PER_SECOND", "2"))
FRAUD_RATE = float(os.getenv("FRAUD_RATE", "0.02"))
FRAUD_REPORT_DELAY_S = int(os.getenv("FRAUD_REPORT_DELAY_S", "60"))
TAUX_DEFAUTS = 0.05   # 5 % des transactions abîmées (données « sales »)

fake = Faker("fr_FR")
Faker.seed(SEED)
rnd = random.Random(SEED)
rnd_defauts = random.Random(SEED + 1)   # hasard séparé : les données propres restent identiques
lock = threading.Lock()


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# --------------------------------------------------------------- Référentiel
CATEGORIES = {
    "alimentation": ((5, 120), ["Carrefour", "Monoprix", "Lidl", "Biocoop", "Franprix"]),
    "restaurant": ((10, 90), ["Le Petit Zinc", "Sushi Shop", "Big Mamma", "Boulangerie Paul"]),
    "transport": ((2, 80), ["SNCF", "RATP", "Uber", "TotalEnergies", "Vélib"]),
    "shopping": ((15, 300), ["Fnac", "Zara", "Decathlon", "Amazon", "IKEA"]),
    "loisirs": ((8, 150), ["Netflix", "Spotify", "UGC", "Steam", "Ticketmaster"]),
    "sante": ((10, 200), ["Pharmacie Centrale", "Doctolib", "Optic 2000"]),
    "voyage": ((50, 1500), ["Air France", "Booking.com", "Airbnb", "Accor"]),
}
CATEGORY_WEIGHTS = [30, 15, 20, 12, 10, 5, 3]
FOREIGN_COUNTRIES = ["US", "BR", "NG", "CN", "RU", "TH"]

CUSTOMERS, ACCOUNTS = [], []
for i in range(1, 51):
    cid = f"C{i:04d}"
    CUSTOMERS.append({
        "customer_id": cid,
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.unique.email(),
        "city": fake.city(),
        "birth_date": fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
        "segment": rnd.choices(["standard", "premium", "pro"], [70, 20, 10])[0],
        "created_at": fake.date_between("-5y", "-30d").isoformat(),
    })
    for acc_type in ["courant"] + (["epargne"] if rnd.random() < 0.5 else []):
        ACCOUNTS.append({
            "account_id": f"A{len(ACCOUNTS) + 1:05d}",
            "customer_id": cid,
            "type": acc_type,
            "iban": fake.iban(),
            "currency": "EUR",
            "opened_at": CUSTOMERS[-1]["created_at"],
        })
CURRENT_ACCOUNTS = [a["account_id"] for a in ACCOUNTS if a["type"] == "courant"]

# --------------------------------------------------------------- Transactions
TRANSACTIONS: deque = deque(maxlen=50_000)
FRAUD_REPORTS: deque = deque(maxlen=10_000)
_pending_frauds: list = []   # (date de signalement, transaction)
_next_tx = 1
_next_report = 1


def abimer(tx: dict) -> dict:
    """Simule un système source imparfait : abîme une transaction au hasard."""
    defaut = rnd_defauts.choice(["montant", "casse", "pays", "commercant", "date", "negatif", "compte"])
    if defaut == "montant":
        tx["amount"] = str(tx["amount"]).replace(".", ",")          # "12,5" (texte)
    elif defaut == "casse":
        tx["category"] = tx["category"].upper() + " "               # "ALIMENTATION "
    elif defaut == "pays":
        tx["country"] = tx["country"].lower()                        # "fr"
    elif defaut == "commercant":
        tx["merchant"] = None                                        # valeur manquante
    elif defaut == "date":
        d = datetime.fromisoformat(tx["timestamp"])
        tx["timestamp"] = d.strftime("%d/%m/%Y %H:%M")               # "11/10/2026 14:05"
    elif defaut == "negatif":
        tx["amount"] = -tx["amount"]                                 # montant impossible
    elif defaut == "compte":
        tx["account_id"] = "A99999"                                  # compte inconnu
    return tx


def ajouter(tx: dict) -> None:
    """Ajoute une transaction ; parfois, la source l'envoie deux fois (doublon)."""
    global _next_tx
    TRANSACTIONS.append(tx)
    if rnd_defauts.random() < TAUX_DEFAUTS / 5:
        TRANSACTIONS.append({**tx, "id": _next_tx})   # même transaction_id, nouvel id
        _next_tx += 1


def make_transaction(ts: datetime) -> dict:
    global _next_tx
    is_fraud = rnd.random() < FRAUD_RATE
    if is_fraud:
        category = rnd.choice(["shopping", "voyage"])
        amount = round(rnd.uniform(800, 4000), 2)
        country = rnd.choice(FOREIGN_COUNTRIES)
        channel = "carte_en_ligne"
    elif rnd.random() < 0.04:  # salaire ou virement entrant
        category, amount, country, channel = "revenu", round(rnd.uniform(1500, 4500), 2), "FR", "virement"
    else:
        category = rnd.choices(list(CATEGORIES), CATEGORY_WEIGHTS)[0]
        lo, hi = CATEGORIES[category][0]
        amount = round(rnd.uniform(lo, hi), 2)
        country = "FR" if rnd.random() < 0.95 else rnd.choice(["ES", "IT", "DE", "BE"])
        channel = rnd.choice(["carte", "carte", "carte_en_ligne", "prelevement"])

    merchant = "Employeur" if category == "revenu" else rnd.choice(CATEGORIES[category][1])
    tx = {
        "id": _next_tx,                                 # curseur pour la pagination
        "transaction_id": f"T{_next_tx:08d}",
        "account_id": rnd.choice(CURRENT_ACCOUNTS),
        "timestamp": ts.isoformat(),
        "amount": amount,
        "direction": "credit" if category == "revenu" else "debit",
        "currency": "EUR",
        "category": category,
        "merchant": merchant,
        "channel": channel,
        "country": country,
        "status": "declined" if rnd.random() < 0.02 else "accepted",
    }
    _next_tx += 1
    if is_fraud:
        _pending_frauds.append((ts + timedelta(seconds=FRAUD_REPORT_DELAY_S), tx))
    elif rnd_defauts.random() < TAUX_DEFAUTS:   # on n'abîme jamais une fraude
        tx = abimer(tx)
    return tx


def release_fraud_reports(at: datetime) -> None:
    """Les fraudes ne sont connues qu'après coup (signalement du client)."""
    global _next_report
    ready = [p for p in _pending_frauds if p[0] <= at]
    for p in ready:
        _pending_frauds.remove(p)
        FRAUD_REPORTS.append({
            "id": _next_report,
            "transaction_id": p[1]["transaction_id"],
            "reported_at": p[0].isoformat(),
            "reason": rnd.choice(["carte_volee", "achat_non_reconnu", "phishing"]),
        })
        _next_report += 1


# Historique : 24 h de transactions déjà présentes au démarrage
_start = now() - timedelta(hours=24)
for k in range(1500):
    ajouter(make_transaction(_start + timedelta(seconds=k * 57)))
release_fraud_reports(now())

# --------------------------------------------------------------- Cours de bourse
TICKERS = {"FINX": 42.0, "NOVA": 118.5, "AQUA": 23.4, "LUMN": 310.0, "TERRA": 77.7}
QUOTES = {t: {"ticker": t, "price": p, "timestamp": now().isoformat()} for t, p in TICKERS.items()}


def generator() -> None:
    last_quote = time.monotonic()
    while True:
        time.sleep(rnd.expovariate(TX_PER_SECOND))
        with lock:
            ts = now()
            ajouter(make_transaction(ts))
            release_fraud_reports(ts)
            if time.monotonic() - last_quote >= 1:
                for q in QUOTES.values():
                    q["price"] = round(max(1.0, q["price"] * (1 + rnd.gauss(0, 0.002))), 2)
                    q["timestamp"] = ts.isoformat()
                last_quote = time.monotonic()


threading.Thread(target=generator, daemon=True).start()

# --------------------------------------------------------------- API
app = FastAPI(
    title="FinTrack API",
    description="Fausse API d'une néobanque pour les ateliers lakehouse. "
                "Toutes les routes (sauf /health) exigent l'en-tête `X-API-Key: atelier` : cliquez sur **Authorize** et saisissez `atelier`.",
    version="1.0",
)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False,
                              description="Clé d'accès des ateliers : atelier")


def check_key(x_api_key: str | None = Security(api_key_header)) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="En-tête X-API-Key manquant ou invalide")


@app.get("/health", tags=["technique"])
def health():
    return {"status": "ok", "transactions_en_memoire": len(TRANSACTIONS)}


@app.get("/customers", tags=["référentiel"], dependencies=[Depends(check_key)])
def list_customers(limit: int = Query(20, le=100), offset: int = 0):
    return {"total": len(CUSTOMERS), "limit": limit, "offset": offset,
            "data": CUSTOMERS[offset: offset + limit]}


@app.get("/customers/{customer_id}", tags=["référentiel"], dependencies=[Depends(check_key)])
def get_customer(customer_id: str):
    for c in CUSTOMERS:
        if c["customer_id"] == customer_id:
            return {**c, "accounts": [a for a in ACCOUNTS if a["customer_id"] == customer_id]}
    raise HTTPException(status_code=404, detail="Client inconnu")


@app.get("/accounts", tags=["référentiel"], dependencies=[Depends(check_key)])
def list_accounts(customer_id: str | None = None):
    data = [a for a in ACCOUNTS if customer_id in (None, a["customer_id"])]
    return {"total": len(data), "data": data}


@app.get("/transactions", tags=["flux"], dependencies=[Depends(check_key)])
def list_transactions(since_id: int = Query(0, description="Renvoie les transactions dont id > since_id"),
                      limit: int = Query(100, le=1000)):
    with lock:
        data = [t for t in TRANSACTIONS if t["id"] > since_id][:limit]
    next_id = data[-1]["id"] if data else since_id
    return {"count": len(data), "next_since_id": next_id, "data": data}


@app.get("/fraud-reports", tags=["flux"], dependencies=[Depends(check_key)])
def list_fraud_reports(since_id: int = 0, limit: int = Query(100, le=1000)):
    with lock:
        data = [r for r in FRAUD_REPORTS if r["id"] > since_id][:limit]
    return {"count": len(data), "next_since_id": data[-1]["id"] if data else since_id, "data": data}


@app.get("/quotes", tags=["marché"], dependencies=[Depends(check_key)])
def list_quotes():
    with lock:
        return {"data": [dict(q) for q in QUOTES.values()]}