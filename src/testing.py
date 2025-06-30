#pip install pokemontcgsdk
#dbutils.library.restartPython()

import os
import json
from pokemontcgsdk import Card, RestClient
from pyspark.sql import SparkSession
from pyspark.sql.types import *

# --- Configuration ---
api_key = dbutils.secrets.get(scope="my_scope", key="POKEMON_API_KEY")
if not api_key:
    raise ValueError("API key not found. Set the POKEMON_API_KEY environment variable.")
RestClient.configure(api_key)

# --- Helpers ---
def obj_to_dict(obj):
    if isinstance(obj, list):
        return [obj_to_dict(item) for item in obj]
    elif hasattr(obj, "__dict__"):
        return {key: obj_to_dict(value) for key, value in obj.__dict__.items()}
    else:
        return obj

# --- Fetch data ---
cards = list(Card.where(page=1, pageSize=1))  # Or use Card.all() cautiously for large datasets
cards_list = [obj_to_dict(c) for c in cards]

# --- Create Spark Session ---
spark = SparkSession.builder.getOrCreate()

# --- Create Spark DataFrame ---
# Normalize complex fields by converting them to JSON strings
for card in cards_list:
    for key, value in card.items():
        if isinstance(value, (list, dict)):
            card[key] = json.dumps(value)

# Now safely create the DataFrame
# --- Fetch data ---
cards = list(Card.where(page=1, pageSize=1))  # Or use Card.all() cautiously for large datasets
cards_list = [obj_to_dict(c) for c in cards]

df = spark.createDataFrame(cards_list)

spark = SparkSession.builder.getOrCreate()
df.display()

# --- Save to Delta Lake ---
#df.write.format("delta").mode("overwrite").saveAsTable("pokemon_tcg_collection.bronze.tcg_all_cards_simplified")
