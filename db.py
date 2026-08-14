"""MongoDB handles. MongoClient is lazy, so importing this does not open a connection."""
from pymongo import MongoClient

import config

client = MongoClient(config.MONGO_URI)
db = client["nst_bot"]

verifications = db["verifications"]
batches = db["batches"]
roster = db["roster"]  # official name/URN list, populated by scripts/import_roster.py
verify_attempts = db["verify_attempts"]  # failed-attempt counters and lockouts
