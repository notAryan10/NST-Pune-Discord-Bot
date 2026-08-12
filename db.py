"""MongoDB handles. MongoClient is lazy, so importing this does not open a connection."""
from pymongo import MongoClient

import config

client = MongoClient(config.MONGO_URI)
db = client["nst_bot"]

verifications = db["verifications"]
batches = db["batches"]
