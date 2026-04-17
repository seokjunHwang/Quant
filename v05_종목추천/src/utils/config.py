from __future__ import annotations
"""글로벌 설정 로더."""

import os
from datetime import datetime
from pathlib import Path

import pytz
import yaml
from dotenv import load_dotenv

KST = pytz.timezone("Asia/Seoul")


def now_kst() -> datetime:
    """한국 시간 기준 현재 시각."""
    return datetime.now(KST)

ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
DAILY_DIR = DATA_DIR / "daily"  # 날짜별 파이프라인 결과

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

# 시장별 리포트 종목 수
MAX_REPORT_KR = FILTERING["kr"]["max_report"]
MAX_REPORT_US = FILTERING["us"]["max_report"]
LARGE_CAP_KR = FILTERING["kr"]["large_cap_count"]
SMALL_MID_KR = FILTERING["kr"]["small_mid_cap_count"]
LARGE_CAP_US = FILTERING["us"]["large_cap_count"]
SMALL_MID_US = FILTERING["us"]["small_mid_cap_count"]
MAX_CHART = FILTERING["max_chart_analysis"]
MAX_RESEARCH_KR = FILTERING["kr"]["max_research"]
MAX_RESEARCH_US = FILTERING["us"]["max_research"]
