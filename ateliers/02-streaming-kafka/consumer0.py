"""Producteur Kafka : API FinTrack -> fin.transactions"""

import json
import time

import httpx
from confluent_kafka import Producer

API = "http://localhost:8000/transactions"
TOPIC = "fin.transactions"

producer = Producer({
    "bootstrap.servers": "localhost:29092",
    "enable.idempotence": True,
})

since_id = 0

try:
    while True:
        response = httpx.get(
            API,
            headers={"X-API-Key": "atelier"},
            params={"since_id": since_id, "limit": 200},
            timeout=10,
        )
        response.raise_for_status()
        page = response.json()

        for tx in page["data"]:
            producer.produce(
                TOPIC,
                key=str(tx["account_id"]),
                value=json.dumps(tx),
            )

        producer.poll(0)
        producer.flush()

        if page["count"]:
            since_id = page["next_since_id"]
            print(f"Curseur : {since_id}")

        time.sleep(2)

except KeyboardInterrupt:
    print("Arrêt du producteur.")

finally:
    producer.flush()