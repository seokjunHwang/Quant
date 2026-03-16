"""Global configuration loader."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"

# Load .env if exists
_env_path = CONFIG_DIR / "api_keys.env"
if _env_path.exists():
    load_dotenv(_env_path)

# Load settings.yaml
_settings_path = CONFIG_DIR / "settings.yaml"
with open(_settings_path, "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)


# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# --- AI Models ---
GEMINI_PRIMARY_MODEL = "gemini-3.1-pro-preview"
GEMINI_FALLBACK_MODEL = "gemini-3.1-flash-lite-preview"

# --- Scoring Weights ---
SCORING_WEIGHTS = SETTINGS.get("scoring", {}).get("weights", {})
VIX_BONUS_RANGES = SETTINGS.get("vix_bonus", {}).get("ranges", [])
FILTERS = SETTINGS.get("filters", {})
RISK = SETTINGS.get("risk", {})
SYSTEM_MODE = SETTINGS.get("system", {}).get("mode", "paper")
MAX_POSITIONS = SETTINGS.get("system", {}).get("max_positions", 5)
MIN_SCORE = SETTINGS.get("system", {}).get("min_score_to_enter", 60)
