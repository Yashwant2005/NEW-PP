import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "src" / "data"

BOT_TOKEN = os.getenv("BOT_TOKEN", "123456789:TEST_BOT_TOKEN_NOT_REAL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "pokeplay_webhook_secret_key")
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "pokeplay_game.sqlite"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

DEFAULT_COINS = 1000
DEFAULT_SAFARI_PASSES = 1
DEFAULT_BALLS = {
    "regular": 15,
    "great": 5,
    "ultra": 2,
    "master": 0,
    "safari": 0
}
