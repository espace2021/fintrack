"""Atelier 1 — Interroger une API source.

Lancer depuis la racine du projet :  uv run ateliers/01-sources-api/explorer.py
"""
import json
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

API = "http://localhost:8000"
HEADERS = {"X-API-Key": "atelier"}
DATA_DIR = Path(__file__).parent / "data"


def get(path: str, **params) -> dict:
    """Appelle l'API et renvoie le JSON. Lève une erreur si le code HTTP n'est pas 2xx."""
    r = httpx.get(f"{API}{path}", headers=HEADERS, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def main() -> None:
    # 1. Le référentiel : qui sont les clients ? quels comptes ont-ils ?
    customers = pd.DataFrame(get("/customers", limit=100)["data"])
    accounts = pd.DataFrame(get("/accounts")["data"])
    print(f"{len(customers)} clients, {len(accounts)} comptes")
    print(customers[["customer_id", "first_name", "last_name", "segment", "city"]].head(), "\n")

    # 2. Le flux : les transactions (on en récupère une page de 100)
    page = get("/transactions", since_id=0, limit=100)
    tx = pd.DataFrame(page["data"])
    print(f"{page['count']} transactions reçues, prochain curseur : since_id={page['next_since_id']}")
    print(tx[["transaction_id", "timestamp", "account_id", "amount", "category", "merchant", "country"]].head(), "\n")

    # 3. Dépôt brut : on sauvegarde la réponse telle quelle (c'est la « landing zone »)
    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"transactions_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(page["data"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Réponse brute sauvegardée dans {out}")

    # ---------------------------------------------------------------- À VOUS
    # Exercice 1 : total dépensé par catégorie (débits acceptés uniquement)
    # Exercice 2 : récupérer TOUTES les transactions en suivant le curseur since_id
    # Exercice 3 : joindre transactions -> comptes -> clients : qui dépense le plus ?


if __name__ == "__main__":
    main()
