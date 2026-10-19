"""Consommateur Kafka : fin.transactions"""

import json
from confluent_kafka import Consumer

consumer = Consumer({
    "bootstrap.servers": "localhost:29092",
    "group.id": "dashboard",
    "auto.offset.reset": "earliest",
})

consumer.subscribe(["fin.transactions"])

try:
    while True:
        # poll() : interroge Kafka pour récupérer un message.
        #1.0 : le délai d'attente maximal, exprimé en secondes.
        
        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():
            print("Erreur :", msg.error())
            continue

        tx = json.loads(msg.value())

        suspect = tx["amount"] > 800 and tx["country"] != "FR"

        print(
            f"{tx['account_id']} | "
            f"{tx['amount']:.2f} € | "
            f"{tx['category']} | "
            f"{tx['country']}"
            f"{' <-- SUSPECT' if suspect else ''}"
        )

except KeyboardInterrupt:
    print("\nArrêt du consommateur.")

finally:
    consumer.close()