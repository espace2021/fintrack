"""Atelier 1 — Solutions des exercices.  uv run ateliers/01-sources-api/solutions.py"""
import pandas as pd

from explorer import get


def exercice_1() -> None:
    tx = pd.DataFrame(get("/transactions", limit=1000)["data"])
    debits = tx[(tx.direction == "debit") & (tx.status == "accepted")]
    print(debits.groupby("category")["amount"].agg(["count", "sum"]).sort_values("sum", ascending=False).round(2), "\n")


def exercice_2() -> pd.DataFrame:
    """Pagination par curseur : on avance tant que l'API renvoie des données."""
    since_id, pages, rows = 0, 0, []
    while True:
        page = get("/transactions", since_id=since_id, limit=500)
        if page["count"] == 0:
            break
        rows += page["data"]
        since_id = page["next_since_id"]
        pages += 1
    print(f"{len(rows)} transactions en {pages} appels (dernier id = {since_id})\n")
    return pd.DataFrame(rows)


def exercice_3(tx: pd.DataFrame) -> None:
    accounts = pd.DataFrame(get("/accounts")["data"])
    customers = pd.DataFrame(get("/customers", limit=100)["data"])
    df = tx[tx.direction == "debit"].merge(accounts, on="account_id").merge(customers, on="customer_id")
    top = (df.groupby(["customer_id", "first_name", "last_name", "segment"])["amount"]
             .sum().sort_values(ascending=False).head(5).round(2))
    print(top)


if __name__ == "__main__":
    exercice_1()
    exercice_3(exercice_2())
