#!/usr/bin/env python3
"""
v05 종목추천 — FastAPI 서버.
정적 파일 서빙 + API (유튜브 자막 요약 등).

실행:
  python3.12 server.py
  → http://localhost:3001
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import fastapi
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

# ── 환경 로드 ─────────────────────────────────────────────
ROOT = Path(__file__).parent
ENV_PATH = ROOT / "config" / "api_keys.env"

# .env 로드 (dotenv 없이 직접)
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ── Gemini 클라이언트 싱글턴 ─────────────────────────────────
_gemini_client = None


def _get_gemini_client():
    """Gemini Client를 1회만 생성하여 재사용 (메모리 누수 방지)."""
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client

# ── 로깅 ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("server")

# ── FastAPI ───────────────────────────────────────────────
app = FastAPI(title="v05 종목추천", docs_url="/api/docs")


# ── 매크로 응답 캐시 (짧은 TTL, 동일 요청 반복 방지) ────────
import time as _time

_macro_cache: dict | None = None
_macro_cache_ts: float = 0
_MACRO_CACHE_TTL = 30  # 30초 캐시


# ── YouTube 자막 요약 API ─────────────────────────────────

class SummaryRequest(BaseModel):
    video_id: str
    title: str = ""


class SummaryResponse(BaseModel):
    video_id: str
    title: str
    summary: str
    key_points: list[str]
    mentioned_tickers: list[str]
    error: str = ""


def extract_transcript(video_id: str) -> str:
    """유튜브 자막 추출 (무료, API키 불필요)."""
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        # 한국어 우선, 없으면 영어, 없으면 자동생성
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(
            video_id,
            languages=["ko", "en"],
        )
        text = " ".join(snippet.text for snippet in transcript.snippets)
        return text
    except Exception as e:
        logger.warning(f"Transcript fetch failed for {video_id}: {e}")
        # 자동생성 자막 시도
        try:
            transcript = ytt_api.fetch(video_id)
            text = " ".join(snippet.text for snippet in transcript.snippets)
            return text
        except Exception as e2:
            raise RuntimeError(f"자막을 가져올 수 없습니다: {e2}")


def summarize_with_gemini(text: str, title: str) -> dict:
    """Gemini Flash Lite 무료 모델로 요약 (use_search=False → 무료)."""
    client = _get_gemini_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY not set")

    from google.genai import types

    # 자막이 너무 길면 자르기 (무료 모델 컨텍스트 제한)
    if len(text) > 15000:
        text = text[:15000] + "\n...(이하 생략)"

    prompt = f"""아래는 경제/투자 유튜브 영상 '{title}'의 자막입니다.
이 영상의 내용을 투자자 관점에서 요약해주세요.
영어 자막이면 반드시 한국어로 번역하여 요약해주세요.

=== 자막 ===
{text}

아래 JSON으로만 반환 (설명 없이 JSON만):
{{
  "summary": "영상 핵심 내용 3~5줄 요약 (반드시 한글로)",
  "key_points": [
    "핵심 포인트 1 (한글)",
    "핵심 포인트 2 (한글)",
    "핵심 포인트 3 (한글)"
  ],
  "mentioned_tickers": ["영상에서 언급된 종목 티커/이름 (없으면 빈 배열)"],
  "market_sentiment": "bullish/bearish/neutral",
  "trading_implication": "매매 시사점 한 줄 (한글)"
}}"""

    config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=2048,
        response_mime_type="application/json",
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
        config=config,
    )

    result_text = response.text.strip()

    # JSON 추출 — Gemini가 ```json 블록이나 여분 텍스트를 붙일 수 있음
    start = result_text.find("{")
    end = result_text.rfind("}") + 1
    if start >= 0 and end > start:
        result_text = result_text[start:end]

    return json.loads(result_text)


# ── 요약 캐시 (파일 기반) ─────────────────────────────────
CACHE_DIR = ROOT / "data" / "youtube_cache"


def get_cached_summary(video_id: str) -> dict | None:
    path = CACHE_DIR / f"{video_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_cached_summary(video_id: str, data: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{video_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── API 엔드포인트 ────────────────────────────────────────

@app.post("/api/youtube/summary", response_model=SummaryResponse)
async def youtube_summary(req: SummaryRequest):
    """유튜브 영상 자막 추출 + Gemini 무료 요약."""
    video_id = req.video_id.strip()
    if not video_id:
        raise HTTPException(400, "video_id is required")

    # 캐시 확인
    cached = get_cached_summary(video_id)
    if cached:
        logger.info(f"Cache hit: {video_id}")
        return SummaryResponse(
            video_id=video_id,
            title=cached.get("title", req.title),
            summary=cached.get("summary", ""),
            key_points=cached.get("key_points", []),
            mentioned_tickers=cached.get("mentioned_tickers", []),
        )

    # 자막 추출
    try:
        transcript = extract_transcript(video_id)
    except Exception as e:
        return SummaryResponse(
            video_id=video_id,
            title=req.title,
            summary="",
            key_points=[],
            mentioned_tickers=[],
            error=f"자막 추출 실패: {str(e)}",
        )

    # Gemini 요약
    try:
        result = summarize_with_gemini(transcript, req.title)
    except Exception as e:
        return SummaryResponse(
            video_id=video_id,
            title=req.title,
            summary="",
            key_points=[],
            mentioned_tickers=[],
            error=f"요약 실패: {str(e)}",
        )

    # 캐시 저장
    cache_data = {
        "video_id": video_id,
        "title": req.title,
        **result,
    }
    save_cached_summary(video_id, cache_data)

    return SummaryResponse(
        video_id=video_id,
        title=req.title,
        summary=result.get("summary", ""),
        key_points=result.get("key_points", []),
        mentioned_tickers=result.get("mentioned_tickers", []),
    )


@app.get("/api/youtube/rss/{channel_id}")
async def youtube_rss(channel_id: str):
    """YouTube RSS 프록시 (CORS 우회)."""
    import httpx
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if resp.status_code != 200:
                raise HTTPException(resp.status_code, f"YouTube RSS unavailable (HTTP {resp.status_code})")
            return fastapi.responses.Response(
                content=resp.text,
                media_type="application/xml",
            )
    except httpx.TimeoutException:
        raise HTTPException(504, "YouTube RSS timeout")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/macro")
async def macro_realtime():
    """실시간 매크로 지표 (yfinance, 무료, Gemini/Claude 소모 없음)."""
    global _macro_cache, _macro_cache_ts

    # 30초 TTL 캐시: 같은 데이터를 반복 fetch 방지
    if _macro_cache and (_time.time() - _macro_cache_ts) < _MACRO_CACHE_TTL:
        return _macro_cache

    import asyncio
    import gc
    import yfinance as yf

    TICKERS = {
        "vix": "^VIX",
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "kospi": "^KS11",
        "kosdaq": "^KQ11",
        "usdkrw": "KRW=X",
        "gold": "GC=F",
        "oil_wti": "CL=F",
        "bitcoin": "BTC-USD",
        "dollar_index": "DX-Y.NYB",
        "us10y_yield": "^TNX",
    }

    def _fetch():
        data = {}
        for name, ticker in TICKERS.items():
            try:
                t = yf.Ticker(ticker)
                price = t.fast_info.last_price
                prev = t.fast_info.previous_close
                if price and prev:
                    data[name] = {
                        "price": round(price, 4),
                        "prev_close": round(prev, 4),
                        "change_pct": round((price - prev) / prev * 100, 2),
                    }
            except Exception:
                pass

        # VIX zone
        vix = data.get("vix", {}).get("price", 0)
        data["vix_zone"] = (
            "극공포" if vix >= 40 else
            "공포" if vix >= 30 else
            "긴장" if vix >= 20 else
            "평시"
        )

        # yfinance Singleton 내부 세션 쿠키 정리 (메모리 누수 방지)
        try:
            from yfinance.data import YfData
            yfdata = YfData()
            if yfdata._session:
                yfdata._session.cookies.clear()
        except Exception:
            pass
        gc.collect()

        return data

    result = await asyncio.to_thread(_fetch)
    _macro_cache = result
    _macro_cache_ts = _time.time()
    return result


# ── 실시간 뉴스 피드 (RSS, 저장 없이 바로 응답) ──────────────

import asyncio as _asyncio
import re as _re
import xml.etree.ElementTree as _ET
from datetime import datetime as _dt, timezone as _tz
from email.utils import parsedate_to_datetime as _parse_rfc2822
from hashlib import md5 as _md5

_news_cache: list[dict] | None = None
_news_cache_ts: float = 0
_NEWS_CACHE_TTL = 120  # 2분 캐시 (RSS 서버 부하 방지)

# 1군: 경제/시장 전용 피드 (잡기사 거의 없음)
_NEWS_FEEDS = {
    "CNBC":       "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",    # Economy
    "CNBC":       "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",    # Economy
    "Reuters":    "https://news.google.com/rss/search?q=source:reuters+breaking+OR+urgent+OR+exclusive&hl=en-US&gl=US&ceid=US:en",
    "Bloomberg":  "https://news.google.com/rss/search?q=source:bloomberg+breaking+OR+exclusive+OR+urgent&hl=en-US&gl=US&ceid=US:en",
    "WSJ":        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "Fed":        "https://www.federalreserve.gov/feeds/press_all.xml",
}
# 2군: 보조 피드
_NEWS_FEEDS_AUX = {
    "Investing":  "https://www.investing.com/rss/news_14.rss",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/marketpulse",
}
# 합치기
_NEWS_FEEDS_ALL = {**_NEWS_FEEDS, **_NEWS_FEEDS_AUX}

# CNBC Economy/Finance 두 개 다 쓰기 위해 리스트로 관리
_NEWS_FEED_LIST = [
    ("CNBC",       "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),   # Economy
    ("CNBC",       "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"),   # Finance
    ("Reuters",    "https://news.google.com/rss/search?q=source:reuters+economy+OR+markets+OR+oil+OR+iran+OR+fed+OR+trade&hl=en-US&gl=US&ceid=US:en"),
    ("Bloomberg",  "https://news.google.com/rss/search?q=source:bloomberg+economy+OR+markets+OR+oil+OR+iran+OR+fed+OR+trade&hl=en-US&gl=US&ceid=US:en"),
    ("WSJ",        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("Fed",        "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("Investing",  "https://www.investing.com/rss/news_14.rss"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/marketpulse"),
]

# 잡기사 드롭만 유지 (전용 피드라 PASS 키워드 불필요)
_DROP_KEYWORDS = _re.compile(
    r"(?i)\b("
    r"my\s+husband|my\s+wife|my\s+daughter|my\s+son|"
    r"recipe|cooking|diet|weight\s?loss|fitness|"
    r"celebrity|kardashian|wedding|divorce|"
    r"horoscope|astrology|zodiac|"
    r"game\s+of|movie\s+review|tv\s+show|netflix|"
    r"lifestyle|travel\s+guide|vacation|"
    r"crossword|puzzle|quiz"
    r")\b"
)


def _parse_feed_items(xml_bytes: bytes, source: str) -> list[dict]:
    """RSS XML → [{title, summary, link, source, published, ts}]"""
    items = []
    try:
        root = _ET.fromstring(xml_bytes)
    except _ET.ParseError:
        return items

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        # Google News RSS wraps real title: "Actual Title - Source"
        # 소스 태그 제거
        clean_title = _re.sub(r"\s*-\s*(Reuters|Bloomberg|AP|CNBC|MarketWatch)\s*$", "", title)

        summary = (item.findtext("description") or "").strip()
        # HTML 태그 제거
        summary = _re.sub(r"<[^>]+>", "", summary).strip()[:200]

        link = (item.findtext("link") or "").strip()

        pub = item.findtext("pubDate") or ""
        ts = 0.0
        published = ""
        if pub:
            try:
                from datetime import timedelta as _td, datetime as _datetime
                try:
                    dt = _parse_rfc2822(pub)
                except Exception:
                    # Investing.com 등 비표준 포맷: "2026-04-14 03:31:06"
                    dt = _datetime.strptime(pub.strip(), "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=_tz.utc
                    )
                ts = dt.timestamp()
                dt_kst = dt + _td(hours=9)
                published = dt.strftime("%m/%d %H:%M UTC") + " · " + dt_kst.strftime("%H:%M KST")
            except Exception:
                pass

        # 잡기사 드롭 (전용 피드라 PASS 필터 불필요)
        text = f"{clean_title} {summary}"
        if _DROP_KEYWORDS.search(text):
            continue

        # 중복 방지용 ID
        uid = _md5(clean_title.lower().encode()).hexdigest()[:12]

        items.append({
            "id": uid,
            "title": clean_title,
            "summary": summary,
            "link": link,
            "source": source,
            "published": published,
            "ts": ts,
        })
    return items


async def _fetch_one_feed(source: str, url: str) -> list[dict]:
    """단일 RSS 피드 비동기 fetch."""
    import urllib.request
    def _do():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=8)
            return _parse_feed_items(resp.read(), source)
        except Exception:
            return []
    return await _asyncio.to_thread(_do)


def _dedup_by_title(items: list[dict]) -> list[dict]:
    """같은 뉴스 여러 소스에서 올 수 있으니 제목 ID로 중복 제거."""
    seen: set[str] = set()
    out = []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            out.append(it)
    return out


@app.get("/api/news/live")
async def news_live():
    """
    실시간 미국 경제 속보 피드.
    경제/시장 전용 RSS 8개 → 잡기사 드롭 → 중복 제거 → 시간순 최신 50건.
    저장 없이 메모리 캐시(2분)만 사용.
    """
    global _news_cache, _news_cache_ts

    if _news_cache is not None and (_time.time() - _news_cache_ts) < _NEWS_CACHE_TTL:
        return {"items": _news_cache, "cached": True}

    tasks = [_fetch_one_feed(src, url) for src, url in _NEWS_FEED_LIST]
    results = await _asyncio.gather(*tasks)

    all_items: list[dict] = []
    for batch in results:
        all_items.extend(batch)

    # 시간순 정렬 (최신 우선) → 중복 제거 → 50건 제한
    all_items.sort(key=lambda x: x["ts"], reverse=True)
    all_items = _dedup_by_title(all_items)[:50]

    _news_cache = all_items
    _news_cache_ts = _time.time()
    return {"items": all_items, "cached": False}


# ── 뉴스 한국어 번역 (googletrans, 무료, 캐시) ───────────────

_translate_cache: dict[str, str] = {}  # id → 한국어 제목


@app.get("/api/news/translate")
async def news_translate():
    """
    현재 캐시된 뉴스 제목을 한국어로 번역.
    googletrans (Google Translate 무료) 사용, API key 불필요.
    이미 번역된 건은 캐시에서 즉시 반환 → 재호출 없음.
    """
    if _news_cache is None:
        return {"translations": {}}

    to_translate = [item for item in _news_cache if item["id"] not in _translate_cache]

    if to_translate:
        from deep_translator import GoogleTranslator

        def _do_translate():
            tr = GoogleTranslator(source="en", target="ko")
            for item in to_translate:
                try:
                    result = tr.translate(item["title"])
                    _translate_cache[item["id"]] = result or item["title"]
                except Exception as e:
                    logger.warning(f"Translate failed [{item['id']}]: {e}")
                    _translate_cache[item["id"]] = item["title"]

        await _asyncio.to_thread(_do_translate)

    return {"translations": _translate_cache}


# ── AI 종목 집중 분석 (비동기 폴링 + 파일 저장) ────────────

import threading
import uuid

ANALYZE_DIR = ROOT / "data" / "stock_analyze"
ANALYZE_DIR.mkdir(parents=True, exist_ok=True)

_analyze_tasks: dict[str, dict] = {}  # task_id → {status, result, query}


def _build_analyze_prompt(query: str) -> str:
    return f"""당신은 월스트리트 출신 시니어 주식 애널리스트입니다.
종목 "{query}"에 대해 아래 항목을 **반드시 모두** 분석해주세요.
웹 검색을 활용하여 최신 데이터 기반으로 작성하세요.

## 1. 주요 정보 (7항목)

| 분석 요소 | 분석 결과 |
|---|---|
| **밸류에이션** | 현재 주가가 실적 대비 저평가/고평가인가? (P/E, P/S, Forward P/E, Fair Value 추정) |
| **경쟁사 비교** | 섹터 내 대장주인가? 경쟁사 대비 매출/영업이익 성장률 비교 (구체적 수치) |
| **재무 건전성** | 최근 분기 매출 증가량, 영업이익률, 보유 현금, 부채비율 (구체적 수치) |
| **자본 리스크** | 유상증자 가능성, 보호예수 해제(오버행) 물량, 희석 리스크 |
| **애널리스트 평가** | 최근 1~2개월 내 주요 투자기관 애널리스트 의견 요약 (컨센서스, 평균 목표주가) |
| **핵심 호재/악재** | 신기술, 대형 수주, 지수 편입/편출, 규제, 소송 등 최근 이벤트 |
| **레버리지 티커** | 이 종목의 2배 레버리지(Bull 2X) ETF 티커가 존재하면 표기 |

## 2. 애널리스트 상세 (최근 1~2개월)

웹 검색으로 이 종목에 대한 최근 1~2개월 내 애널리스트 리포트를 **최소 6개 이상** 찾아주세요.
각 리포트의 발표 날짜, 투자 기관명, 목표 주가, 투자의견, 코멘트(한국어)를 포함하세요.
날짜 내림차순(최신순)으로 정렬하세요.

## 3. 단타 정보 (5항목)

| 분석 요소 | 분석 결과 |
|---|---|
| **상대 거래량 (RVOL)** | 최근 거래량이 평소 대비 몇 배인가? 돈이 쏠리고 있는가? |
| **옵션 활동** | 비정상적인 콜옵션 대량 매수(Unusual Options Activity) 포착 여부 |
| **공매도 & 숏커버링** | Short Float %, Short Ratio(Days to Cover), 숏 스퀴즈 가능성 |
| **시간 외 거래** | 프리마켓/애프터마켓 갭(Gap) 발생 여부, 방향 |
| **SMC 패턴 (15분봉)** | Order Block 지지, CHoCH(추세 전환), FVG(갭 메우기) 패턴 존재 여부 |

## 3. 수급 검증 (Verify)

RVOL 급증 + 콜옵션 유입이 동시에 나타나는지 종합 판단하여, '진짜 돈'이 들어왔는지 한 줄 결론.

---
분석 결과를 아래 JSON으로만 반환하세요 (설명 없이 JSON만):
{{
  "ticker": "분석한 티커 (예: LRCX)",
  "name": "종목 전체명",
  "market": "us 또는 kr",
  "current_price": "현재가 (문자열)",
  "summary": "이 종목에 대한 한줄 종합 판단 (한국어)",
  "main_analysis": [
    {{"category": "밸류에이션", "result": "분석 결과 (한국어, 구체적 수치 포함)"}},
    {{"category": "경쟁사 비교", "result": "..."}},
    {{"category": "재무 건전성", "result": "..."}},
    {{"category": "자본 리스크", "result": "..."}},
    {{"category": "애널리스트 평가", "result": "..."}},
    {{"category": "핵심 호재/악재", "result": "..."}},
    {{"category": "레버리지 티커", "result": "..."}}
  ],
  "analyst_ratings": [
    {{"date": "2026-04-15", "firm": "Deutsche Bank", "target": "$300", "rating": "Buy", "comment": "코멘트 (한국어)"}},
    {{"date": "2026-04-14", "firm": "Morgan Stanley", "target": "$295", "rating": "Overweight", "comment": "코멘트"}},
    {{"date": "...", "firm": "...", "target": "...", "rating": "...", "comment": "..."}}
  ],
  "swing_analysis": [
    {{"category": "상대 거래량 (RVOL)", "result": "..."}},
    {{"category": "옵션 활동", "result": "..."}},
    {{"category": "공매도 & 숏커버링", "result": "..."}},
    {{"category": "시간 외 거래", "result": "..."}},
    {{"category": "SMC 패턴 (15분봉)", "result": "..."}}
  ],
  "verify": "수급 검증 한줄 결론 (한국어)"
}}"""


def _run_analyze_bg(task_id: str, query: str):
    """백그라운드 스레드에서 Claude CLI 실행 + 결과 파일 저장."""
    import subprocess
    prompt = _build_analyze_prompt(query)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "claude-opus-4-6",
             "--output-format", "json", "--allowedTools", "WebSearch"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            _analyze_tasks[task_id] = {"status": "error", "error": f"Claude CLI 오류: {(result.stderr or '')[:200]}"}
            return

        raw = result.stdout.strip()
        try:
            wrapper = json.loads(raw)
            if isinstance(wrapper, dict) and "result" in wrapper:
                raw = wrapper["result"]
        except Exception:
            pass

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]

        data = json.loads(raw)
        data["_query"] = query
        data["_analyzed_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        data["_task_id"] = task_id

        # 파일 저장 (날짜별)
        today = _time.strftime("%Y%m%d")
        day_dir = ANALYZE_DIR / today
        day_dir.mkdir(parents=True, exist_ok=True)
        ticker = data.get("ticker", query).replace("/", "_")
        ts = _time.strftime("%H%M%S")
        filepath = day_dir / f"{ticker}_{ts}.json"
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Analysis saved: {filepath}")

        _analyze_tasks[task_id] = {"status": "done", "result": data}

    except subprocess.TimeoutExpired:
        _analyze_tasks[task_id] = {"status": "error", "error": "분석 시간 초과 (5분). 다시 시도해주세요."}
    except json.JSONDecodeError as e:
        _analyze_tasks[task_id] = {"status": "error", "error": f"응답 파싱 실패: {str(e)[:100]}"}
    except FileNotFoundError:
        _analyze_tasks[task_id] = {"status": "error", "error": "Claude CLI가 설치되어 있지 않습니다."}
    except Exception as e:
        _analyze_tasks[task_id] = {"status": "error", "error": f"분석 실패: {str(e)[:200]}"}


class StockAnalyzeRequest(BaseModel):
    query: str


@app.post("/api/stock/analyze")
async def stock_analyze(req: StockAnalyzeRequest):
    """분석 요청 → task_id 즉시 반환 (5초 이내). 백그라운드에서 Claude CLI 실행."""
    query = req.query.strip()
    if not query:
        raise HTTPException(400, "종목명 또는 티커를 입력하세요")

    task_id = str(uuid.uuid4())[:8]
    _analyze_tasks[task_id] = {"status": "running", "query": query}
    t = threading.Thread(target=_run_analyze_bg, args=(task_id, query), daemon=True)
    t.start()

    return {"task_id": task_id, "status": "running"}


@app.get("/api/stock/analyze/{task_id}")
async def stock_analyze_poll(task_id: str):
    """폴링: 분석 진행 상태 확인."""
    task = _analyze_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "해당 분석 작업을 찾을 수 없습니다")
    return task


@app.get("/api/stock/history")
async def stock_analyze_history():
    """저장된 분석 기록 목록 (날짜별)."""
    if not ANALYZE_DIR.exists():
        return {"dates": []}
    dates = []
    for d in sorted(ANALYZE_DIR.iterdir(), reverse=True):
        if not d.is_dir() or not d.name.isdigit():
            continue
        files = sorted(d.glob("*.json"), reverse=True)
        items = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                items.append({
                    "filename": f.name,
                    "ticker": data.get("ticker", ""),
                    "name": data.get("name", ""),
                    "summary": data.get("summary", "")[:60],
                    "analyzed_at": data.get("_analyzed_at", ""),
                })
            except Exception:
                pass
        if items:
            dates.append({"date": d.name, "items": items})
    return {"dates": dates}


@app.get("/api/stock/history/{date}/{filename}")
async def stock_analyze_detail(date: str, filename: str):
    """특정 분석 기록 상세 조회."""
    filepath = ANALYZE_DIR / date / filename
    if not filepath.exists():
        raise HTTPException(404, "분석 기록을 찾을 수 없습니다")
    return json.loads(filepath.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "gemini_key_set": bool(GEMINI_API_KEY)}


# ── 정적 파일 (web/) ─────────────────────────────────────
WEB_DIR = ROOT / "web"


# 모든 응답에 캐시 무효화 헤더 강제 (개발 중 변경 즉시 반영)
@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# SPA fallback: index.html
@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


# Mount static files (css, js, data)
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")


# ── 서버 실행 ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3001
    logger.info(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
