import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "127.0.0.1")
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# Strict Discount Definitions
DISCOUNT_TIERS = {
    0: {"code": None, "rate": 0.0, "label": "Standard Pricing (0%)"},
    1: {"code": "SAVE10", "rate": 0.10, "label": "10% Courtesy Discount"},
    2: {"code": "CLOSENOW15", "rate": 0.15, "label": "15% Maximum Closing Discount"},
}
MAX_DISCOUNT_TIER = 2
MAX_DISCOUNT_RATE = 0.15
ALLOWED_PROMO_CODES = {None, "SAVE10", "CLOSENOW15"}
