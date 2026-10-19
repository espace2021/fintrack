"""Atelier 2 — Producteur : API FinTrack -> topic Kafka fin.transactions

uv run ateliers/02-streaming-kafka/producer.py            # reprend là où il s'était arrêté
uv run ateliers/02-streaming-kafka/producer.py --reset    # repart du début de l'API
"""
import json
import sys
import time
from pathlib import Path

import httpx
from confluent_kafka import Producer

API = "http://localhost:8000"
HEADERS = {"X-API-Key": "atelier"}
TOPIC = "fin.transactions"
STATE = Path(__file__).parent / ".producer_state.json"   # mémorise le curseur since_id

producer = Producer({
    "bootstrap.servers": "localhost:29092",
    "client.id": "fin-producer",
    "acks": "all",               # le message est confirmé quand Kafka l'a bien écrit
    "enable.idempotence": True,  # pas de doublon en cas de nouvel essai réseau
})

def on_delivery(err, msg) -> None:
    if err:
        print(f"ÉCHEC : {err}")
    else:
        tx = json.loads(msg.value())
        montant = tx.get("amount")
        # un montant peut arriver en texte ("41,06") : on l'affiche tel quel
        montant = f"{montant:>8.2f}" if isinstance(montant, (int, float)) else f"{montant!s:>8}"
        print(f"-> partition {msg.partition()} | offset {msg.offset():>5} | "
              f"{msg.key().decode()} | {montant} € | {tx.get('category')}")

def main() -> None:
    since_id = 0 if "--reset" in sys.argv or not STATE.exists() else json.loads(STATE.read_text())["since_id"]
    print(f"Départ à since_id={since_id}. Ctrl+C pour arrêter.\n")
    try:
        while True:
            page = httpx.get(f"{API}/transactions", headers=HEADERS,
                             params={"since_id": since_id, "limit": 200}, timeout=10).json()
            for tx in page["data"]:
                # La CLÉ = le compte : toutes les opérations d'un compte vont dans la même partition
                producer.produce(TOPIC, key=tx["account_id"], value=json.dumps(tx), on_delivery=on_delivery)
                producer.poll(0)
            producer.flush()
            if page["count"]:
                since_id = page["next_since_id"]
                STATE.write_text(json.dumps({"since_id": since_id}))
            time.sleep(2)
    except KeyboardInterrupt:
        producer.flush()
        print(f"\nArrêt. Curseur sauvegardé : since_id={since_id}")

if __name__ == "__main__":
    main()
