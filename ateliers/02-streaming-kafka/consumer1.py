"""Atelier 2 — Consommateur : lit fin.transactions et calcule des totaux en direct

uv run ateliers/02-streaming-kafka/consumer.py                    # groupe "dashboard"
uv run ateliers/02-streaming-kafka/consumer.py --group fraude     # un autre groupe
uv run ateliers/02-streaming-kafka/consumer.py --alertes          # n'affiche que les transactions suspectes
"""
import argparse
import json
from collections import defaultdict

from confluent_kafka import Consumer

TOPIC = "fin.transactions"

parser = argparse.ArgumentParser()
parser.add_argument("--group", default="dashboard", help="consumer group")
parser.add_argument("--alertes", action="store_true", help="n'afficher que les montants > 800 € hors de France")
args = parser.parse_args()

consumer = Consumer({
    "bootstrap.servers": "localhost:29092",
    "group.id": args.group,
    "auto.offset.reset": "earliest",   # nouveau groupe : on lit depuis le début du topic
})

def on_assign(c, partitions):
    print(f"[{args.group}] partitions attribuées : {[p.partition for p in partitions]}")

consumer.subscribe([TOPIC], on_assign=on_assign)
totals, n = defaultdict(float), 0

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(msg.error())
            continue
        tx = json.loads(msg.value())
        n += 1
        if tx["direction"] == "debit" and tx["status"] == "accepted":
            totals[tx["category"]] += tx["amount"]

        suspect = tx["amount"] > 800 and tx["country"] != "FR"
        if suspect or not args.alertes:
            flag = "  <-- SUSPECT" if suspect else ""
            print(f"[p{msg.partition()} o{msg.offset():>5}] {tx['account_id']} "
                  f"{tx['amount']:>8.2f} € {tx['category']:<12} {tx['country']}{flag}")

        if n % 50 == 0 and not args.alertes:
            print("\n--- Dépenses cumulées ---")
            for cat, total in sorted(totals.items(), key=lambda x: -x[1]):
                print(f"{cat:<14}{total:>12.2f} €")
            print()
except KeyboardInterrupt:
    pass
finally:
    consumer.close()   # quitte proprement le groupe -> rééquilibrage immédiat

