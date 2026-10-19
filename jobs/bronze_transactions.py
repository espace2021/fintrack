"""Atelier 3 - Kafka (fin.transactions) -> table Iceberg lake.bronze.transactions."""
from pyspark.sql import SparkSession, functions as F
 
spark = SparkSession.builder.appName("bronze-transactions").getOrCreate()
spark.sparkContext.setLogLevel("WARN")
spark.sql("CREATE NAMESPACE IF NOT EXISTS lake.bronze")
 
# Structure d'une transaction : tout en TEXTE (STRING).
# En bronze, on ne type pas et on ne corrige pas : rien ne doit être perdu.
SCHEMA = ("id STRING, transaction_id STRING, account_id STRING, timestamp STRING, "
          "amount STRING, direction STRING, currency STRING, category STRING, "
          "merchant STRING, channel STRING, country STRING, status STRING")
 
# 1. Lire Kafka en continu
kafka = (spark.readStream.format("kafka")
         .option("kafka.bootstrap.servers", "kafka:9092")
         .option("subscribe", "fin.transactions")
         .option("startingOffsets", "earliest")      # depuis le début du topic
         .load())
 
# 2. Garder le message d'origine, puis en extraire les champs
transactions = (kafka
    .select(F.col("value").cast("string").alias("raw_value"),   # le message tel quel
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"))
    .withColumn("t", F.from_json("raw_value", SCHEMA))
    .select("t.*", "raw_value", "kafka_partition", "kafka_offset")
    .withColumn("ingested_at", F.current_timestamp()))
 
# 3. Écrire en continu dans une table Iceberg
requete = (transactions.writeStream
    .format("iceberg")
    .outputMode("append")                # on ajoute, on ne remplace pas
    .trigger(processingTime="10 seconds") # un micro-lot toutes les 10 s
    .option("checkpointLocation", "/opt/jobs/_checkpoints/bronze_transactions")
    .toTable("lake.bronze.transactions"))
 
print("Streaming démarré : Ctrl+C pour arrêter.")
requete.awaitTermination()
