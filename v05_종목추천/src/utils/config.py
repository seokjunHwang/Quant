from __future__ import annotations
"""글로벌 설정 로더."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"

load_dotenv(CONFIG_DIR / "api_keys.env")

with open(CONFIG_DIR / "settings.yaml", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")

# Models
GEMINI_PRIMARY_MODEL = SETTINGS["gemini"]["primary_model"]
GEMINI_FALLBACK_MODEL = SETTINGS["gemini"]["fallback_model"]

# Settings shortcuts
FILTERING = SETTINGS["filtering"]
SCORING = SETTINGS["scoring"]
UNIVERSE = SETTINGS["universe"]
MAX_CANDIDATES = FILTERING["max_candidates"]
LARGE_CAP_COUNT = FILTERING["large_cap_count"]
SMALL_MID_CAP_COUNT = FILTERING["small_mid_cap_count"]
