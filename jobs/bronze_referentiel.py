"""Atelier 3 - Charge le référentiel FinTrack dans la couche bronze (batch)."""
import json
import urllib.request
 
from pyspark.sql import SparkSession, functions as F
 
API = "https://fintrack-api-83hn.onrender.com"         # adresse de l'API dans le réseau Docker
HEADERS = {"X-API-Key": "atelier"}
 
 
def get(path):
    """Appelle l'API et renvoie la réponse JSON."""
    req = urllib.request.Request(API + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as reponse:
        return json.loads(reponse.read())
 
 
def toutes_les_pages(path):
    """Suit le curseur since_id jusqu'à la fin (vu à l'atelier 1)."""
    lignes, since_id = [], 0
    while True:
        page = get(f"{path}?since_id={since_id}&limit=1000")
        if page["count"] == 0:
            return lignes
        lignes += page["data"]
        since_id = page["next_since_id"]
 
 
spark = SparkSession.builder.appName("bronze-referentiel").getOrCreate()
spark.sparkContext.setLogLevel("WARN")
spark.sql("CREATE NAMESPACE IF NOT EXISTS lake.bronze")
 
sources = {
    "customers": get("/customers?limit=100")["data"],
    "accounts": get("/accounts")["data"],
    "fraud_reports": toutes_les_pages("/fraud-reports"),
}
 
for nom, lignes in sources.items():
    df = spark.createDataFrame(lignes)
    df = df.withColumn("ingested_at", F.current_timestamp())
    # crée la table, ou la remplace si elle existe déjà
    df.writeTo(f"lake.bronze.{nom}").createOrReplace()
    print(f"lake.bronze.{nom} : {df.count()} lignes")
 
spark.stop()
