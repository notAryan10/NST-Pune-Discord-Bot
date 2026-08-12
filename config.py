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

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
