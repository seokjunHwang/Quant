from __future__ import annotations
"""
Step 3-1 (CLI 버전): Gemini CLI 구독으로 개별 종목 리서치.

설계:
* 모델: gemini-3.1-pro-preview (OAuth 구독, API key 불필요)
* 검색: CLI 내장 WebSearch/WebFetch 자동 사용
* 호출 단위: 5종목씩 묶음 배치 (호출 수 ↓, 부팅 오버헤드 ↓)
* 동시 실행: asyncio + subprocess (기본 2 동시, 설정 가능)
* 재시도: 배치 실패 → 같은 5종목을 1건씩 fallback → 그래도 실패 시 빈 결과
* 부분 응답: 배치 응답에서 누락된 ticker 만 골라 1건씩 보충 호출
* 캐시: data/cache/step3/{date}/{market}_{ticker}.json (같은 날만 유효)
* Quota 가드: today_remaining < threshold 면 기존 API key Flash로 자동 fallback
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Sequence

from src.utils.config import DATA_DIR, now_kst
from src.utils.gemini_cli import (
    _extract_json,
    _log_usage,
    _strip_noise,
    get_gemini_cli_usage,
)

logger = logging.getLogger(__name__)

MODEL = "gemini-3.1-pro-preview"
BATCH_SIZE = 5
CONCURRENCY = 2                 # 동시 실행 배치 수
TIMEOUT_BATCH_SEC = 900         # 배치 1회당 timeout (15분, CLI 느림 대비 충분)
TIMEOUT_SINGLE_SEC = 900        # 단건 fallback timeout (15분)
QUOTA_GUARD_THRESHOLD = 30      # 잔여 호출 < 이 값 → API key fallback
CACHE_DIR = DATA_DIR / "cache" / "step3"

DEFAULT_RECORD = {
    "catalysts": [],
    "risks": [],
    "news_summary": "",
    "momentum": "neutral",
    "analyst_view": None,
    "score_hint": 50,
}


# ── 캐시 ──────────────────────────────────────────────────────────────────────
def _cache_path(market: str, ticker: str) -> Path:
    date = now_kst().strftime("%Y%m%d")
    return CACHE_DIR / date / f"{market}_{ticker}.json"


def _cache_load(market: str, ticker: str) -> dict | None:
    p = _cache_path(market, ticker)
    if not p.exists():
        return None
    try:
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_save(market: str, ticker: str, record: dict) -> None:
    p = _cache_path(market, ticker)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with p.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"  cache save failed [{ticker}]: {e}")


# ── 보정 ──────────────────────────────────────────────────────────────────────
def _ensure_record(stock: dict, partial: dict | None = None) -> dict:
    """부족한 필드를 기본값으로 채워서 일관된 dict 반환."""
    rec = {
        "ticker": stock.get("ticker", ""),
        "name": stock.get("name", stock.get("ticker", "")),
        "theme": stock.get("theme", ""),
    }
    rec.update(DEFAULT_RECORD)
    if partial:
        for k, v in partial.items():
            if v is not None and v != "":
                rec[k] = v
    return rec


# ── 프롬프트 ──────────────────────────────────────────────────────────────────
def _build_batch_prompt(batch: Sequence[dict], market: str) -> str:
    now = now_kst()
    today = now.strftime("%Y년 %m월 %d일")
    current_time = now.strftime("%H시 %M분")
    market_name = "한국" if market == "kr" else "미국"
    exchange = "KOSPI/KOSDAQ" if market == "kr" else "NYSE/NASDAQ"

    items = "\n".join(
        f"{i+1}. {s.get('name','')}({s.get('ticker','')}) — 테마: {s.get('theme','')}"
        for i, s in enumerate(batch)
    )

    schema = """{
    "ticker": "<티커>",
    "name": "<종목명>",
    "theme": "<연관 테마>",
    "catalysts": [
      {"type": "호재/악재/중립", "content": "구체적 내용 (출처)", "date": "날짜", "impact": "high/medium/low"}
    ],
    "risks": [
      {"type": "리스크 유형", "description": "설명", "severity": "high/medium/low"}
    ],
    "news_summary": "최근 1주일 핵심 뉴스 2~3줄 요약",
    "momentum": "bullish/bearish/neutral",
    "analyst_view": "애널리스트 의견 또는 목표주가 (없으면 null)",
    "score_hint": 0-100
  }"""

    return f"""현재 시각: {today} {current_time} (한국시간 KST)
{market_name} {exchange} 종목 {len(batch)}개를 각각 웹 검색해서 리서치한다.

조사 대상:
{items}

각 종목에 대해 다음 검색을 수행해라:
- "{{종목명}} {{티커}} 뉴스 {today}" — 최근 뉴스/공시
- "{{종목명}} {{티커}} 실적 애널리스트 목표주가" — 실적 전망
- "{{종목명}} {{티커}} 수급 외국인 기관" — 수급 동향

결과는 정확히 다음 형식의 JSON 배열로만 반환해라 (앞뒤 설명 금지).
배열 길이는 정확히 {len(batch)}개여야 하고, 입력 순서를 유지해라.

```json
[
  {schema}
]
```

규칙:
- catalysts 는 실제 검색된 뉴스/공시 기반, 날짜 명시
- 오늘 또는 최근 1주일 정보 우선
- score_hint: 단타/스윙 매매 매력도 (100이 최고)
- 정보 없으면 catalysts/risks 빈 배열, momentum=neutral, score_hint=50
- 모든 필드 누락 없이 채워라
"""


# ── CLI 호출 (async) ─────────────────────────────────────────────────────────
async def _run_cli(prompt: str, *, timeout: int, context: str) -> str:
    """asyncio.create_subprocess_exec로 CLI 호출. stdout 텍스트 반환."""
    t0 = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            "gemini", "-p", prompt, "-m", MODEL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            _log_usage(MODEL, context, success=False,
                       latency=time.time() - t0, error="timeout")
            raise RuntimeError(f"Gemini CLI timeout ({timeout}s)")

        latency = round(time.time() - t0, 2)
        if proc.returncode != 0:
            err = (stderr.decode("utf-8", errors="replace"))[:300]
            _log_usage(MODEL, context, success=False, latency=latency, error=err)
            raise RuntimeError(f"Gemini CLI failed: {err}")

        text = _strip_noise(stdout.decode("utf-8", errors="replace")).strip()
        _log_usage(MODEL, context, success=True, latency=latency)
        return text
    except FileNotFoundError:
        _log_usage(MODEL, context, success=False, latency=time.time() - t0,
                   error="gemini binary not found")
        raise RuntimeError("gemini CLI not installed")


# ── 배치 호출 ────────────────────────────────────────────────────────────────
async def _research_batch(batch: list[dict], market: str) -> list[dict]:
    """5종목 배치를 한 번의 CLI 호출로 처리. 누락 ticker는 단건 보충."""
    prompt = _build_batch_prompt(batch, market)
    ctx = f"step3_{market}_batch{len(batch)}"

    try:
        text = await _run_cli(prompt, timeout=TIMEOUT_BATCH_SEC, context=ctx)
        parsed = _extract_json(text)
    except Exception as e:
        logger.warning(f"  배치 실패 ({len(batch)}종목): {e} → 단건 fallback")
        return await _fallback_singles(batch, market)

    # parsed가 list여야 함. dict면 {"results": [...]} 같은 래퍼일 수 있음
    items: list[dict] = []
    if isinstance(parsed, list):
        items = [x for x in parsed if isinstance(x, dict)]
    elif isinstance(parsed, dict):
        for key in ("results", "stocks", "data", "items"):
            if key in parsed and isinstance(parsed[key], list):
                items = [x for x in parsed[key] if isinstance(x, dict)]
                break
        if not items and len(parsed) > 0:
            # 단일 종목 dict 한 개만 온 경우
            items = [parsed]

    # ticker 매칭 (응답이 입력 순서를 깨뜨려도 ticker로 다시 정렬)
    by_ticker: dict[str, dict] = {}
    for it in items:
        t = str(it.get("ticker", "")).strip()
        if t:
            by_ticker[t] = it

    results: list[dict] = []
    missing: list[dict] = []
    for stock in batch:
        ticker = str(stock.get("ticker", "")).strip()
        if ticker in by_ticker:
            results.append(_ensure_record(stock, by_ticker[ticker]))
        else:
            missing.append(stock)

    # 부분 누락 처리: 누락된 종목만 단건 보충
    if missing:
        logger.info(f"  배치 부분 누락 {len(missing)}/{len(batch)}건 → 단건 보충")
        filled = await _fallback_singles(missing, market)
        results.extend(filled)

    # 입력 순서 복원
    order = {str(s.get("ticker", "")): i for i, s in enumerate(batch)}
    results.sort(key=lambda r: order.get(str(r.get("ticker", "")), 1e9))
    return results


async def _fallback_singles(batch: list[dict], market: str) -> list[dict]:
    """배치 실패/누락 시 1건씩 재호출."""
    out: list[dict] = []
    for stock in batch:
        single_prompt = _build_batch_prompt([stock], market)
        ctx = f"step3_{market}_single_{stock.get('ticker','')}"
        try:
            text = await _run_cli(single_prompt, timeout=TIMEOUT_SINGLE_SEC, context=ctx)
            parsed = _extract_json(text)
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                out.append(_ensure_record(stock, parsed[0]))
            elif isinstance(parsed, dict):
                out.append(_ensure_record(stock, parsed))
            else:
                rec = _ensure_record(stock)
                rec["error"] = "unparsable response"
                out.append(rec)
        except Exception as e:
            logger.warning(f"  단건 실패 [{stock.get('ticker')}]: {e}")
            rec = _ensure_record(stock)
            rec["error"] = str(e)[:200]
            out.append(rec)
    return out


# ── Quota 가드 + Flash fallback ──────────────────────────────────────────────
def _quota_ok(needed_calls: int) -> bool:
    usage = get_gemini_cli_usage()
    remaining = usage.get("today_remaining", 0)
    return remaining - needed_calls >= QUOTA_GUARD_THRESHOLD


def _research_via_api_key_fallback(stocks: list[dict], market: str) -> list[dict]:
    """Quota 부족 시 기존 API key Flash 모듈로 위임."""
    logger.warning("  Gemini CLI quota 부족 → API key Flash로 fallback")
    from src.step3_research.stock_gemini import research_stocks_batch as legacy_batch
    return legacy_batch(stocks, market, max_stocks=len(stocks))


# ── 메인 진입점 ──────────────────────────────────────────────────────────────
async def _research_async(
    candidates: list[dict],
    market: str,
    max_stocks: int,
) -> list[dict]:
    targets = candidates[:max_stocks]
    if not targets:
        return []

    # 1) 캐시 조회
    cached_results: dict[str, dict] = {}
    pending: list[dict] = []
    for s in targets:
        ticker = str(s.get("ticker", "")).strip()
        cached = _cache_load(market, ticker)
        if cached:
            cached_results[ticker] = cached
        else:
            pending.append(s)

    if cached_results:
        logger.info(f"  [{market}] 캐시 적중 {len(cached_results)}/{len(targets)}건")

    # 2) Quota 가드 — 필요 호출 수 ~= ceil(pending / BATCH_SIZE)
    needed_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    if pending and not _quota_ok(needed_batches):
        legacy = _research_via_api_key_fallback(pending, market)
        for r in legacy:
            cached_results[r.get("ticker", "")] = r
            _cache_save(market, r.get("ticker", ""), r)
    else:
        # 3) 5종목 배치 분할
        batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
        logger.info(
            f"  [{market}] CLI 배치 {len(batches)}개 (각 ≤{BATCH_SIZE}종목, "
            f"동시 {CONCURRENCY})"
        )

        sem = asyncio.Semaphore(CONCURRENCY)

        async def run(b: list[dict], idx: int) -> list[dict]:
            async with sem:
                logger.info(f"  [{market}] batch {idx+1}/{len(batches)} 시작 ({len(b)}종목)")
                t0 = time.time()
                res = await _research_batch(b, market)
                logger.info(
                    f"  [{market}] batch {idx+1}/{len(batches)} 완료 "
                    f"({len(res)}건, {round(time.time()-t0,1)}s)"
                )
                return res

        gathered = await asyncio.gather(*[run(b, i) for i, b in enumerate(batches)])
        for batch_results in gathered:
            for r in batch_results:
                ticker = r.get("ticker", "")
                if ticker:
                    cached_results[ticker] = r
                    _cache_save(market, ticker, r)

    # 4) 입력 순서대로 정렬해 반환
    out: list[dict] = []
    for s in targets:
        ticker = str(s.get("ticker", "")).strip()
        if ticker in cached_results:
            out.append(cached_results[ticker])
        else:
            rec = _ensure_record(s)
            rec["error"] = "missing"
            out.append(rec)
    return out


def research_stocks_batch(
    candidates: list[dict],
    market: str,
    max_stocks: int = 30,
) -> list[dict]:
    """
    main.py에서 부르는 진입점. 기존 stock_gemini.research_stocks_batch와
    시그니처 동일하므로 import 한 줄만 바꾸면 교체 가능.
    """
    return asyncio.run(_research_async(candidates, market, max_stocks))
