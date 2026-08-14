"""Environment values and server constants. No side effects beyond reading .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

COMMAND_PREFIX = "!"

UNVERIFIED_ROLE = "Unverified"
CONFIRMED_ROLE = "Confirmed Student"
VERIFICATION_CHANNEL = "verification-queue"

YEAR_MAP = {1: "Freshers", 2: "2nd Year", 3: "3rd Year", 4: "4th Year"}
YEAR_ROLES = frozenset(YEAR_MAP.values())

BAD_WORDS = ["shit", "fuck"]
ALLOWED_EXTENSIONS = ("pdf", "png")

# --- Roster verification ---
# Flip to False to run the matcher in suggest-only mode: every submission still lands
# in the queue for a human, but pre-scored. Useful for watching the thresholds before
# letting the bot assign roles on its own.
ROSTER_AUTO_APPROVE = True

NAME_MATCH_AUTO = 90  # >= this, the name is trusted outright
NAME_MATCH_REVIEW = 75  # >= this goes to the admin queue; below it is rejected

# A URN embeds a date of birth, so it is partly guessable. These caps are what stop
# someone working through candidate URNs for a classmate.
VERIFY_MAX_ATTEMPTS = 3
VERIFY_LOCKOUT_MINUTES = 60
VERIFY_REPLY_TIMEOUT = 180.0

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
