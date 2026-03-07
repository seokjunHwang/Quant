"""
Step 3: Stock Validator — yfinance + AI로 발굴 종목을 검증.

검증 항목:
  Pass/Fail (하나라도 Fail이면 제거):
    1. 티커 실존 — yfinance에서 데이터 반환되는지
    2. 시총 범위 — $100M ≤ 시총 ≤ $10B
    3. 유동성 — 일평균 거래대금 ≥ $500K
    4. 거래 가능 — 최근 5거래일 내 거래 존재

  경고 플래그 (제거는 안하지만 감점):
    5. 유상증자/희석 — 최근 90일 이내 ATM, PIPE, 워런트 행사
    6. 공매도 비율 — Short Interest > 30%
    7. 내부자 매도 — 최근 30일 대규모 내부자 매도
    8. SEC 조사/소송 — SEC investigation, class action
    9. 실적 악화 — 3분기 연속 매출 감소

  경고 처리:
    0개 → 그대로 통과
    1개 → 통과 + ⚠️ 표시
    2개 → 통과 + ⚠️⚠️ + 종합점수 -10점
    3개+ → 자동 제거
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import yfinance as yf

from app.config import settings
from app.models.schemas import DiscoveredStock, ValidatedStock, ValidationWarning

logger = logging.getLogger(__name__)

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

NEGATIVE_CATALYST_PROMPT = """For the following US-listed stocks, check for any NEGATIVE catalysts or red flags in the past 90 days.

Stocks to check: {tickers}

For EACH stock, check these specific items:
1. DILUTION: Any secondary offering, ATM offering, PIPE deal, shelf registration (S-3), warrant exercise, or stock dilution events
2. INSIDER_SELLING: Large insider sales (CEO/CFO/Directors selling significant shares)
3. SEC_ISSUE: SEC investigation, enforcement action, class action lawsuit, accounting irregularities
4. REVENUE_DECLINE: 3+ consecutive quarters of revenue decline

IMPORTANT: Return ONLY a valid JSON object. If a stock has NO issues, include it with an empty array.
Example:
{{
  "RCAT": [],
  "UMAC": [
    {{"type": "dilution", "description": "ATM offering of $50M announced on 2026-02-15"}},
    {{"type": "insider_selling", "description": "CEO sold 500K shares on 2026-01-20"}}
  ],
  "JOBY": [
    {{"type": "revenue_decline", "description": "Revenue declined for 3 consecutive quarters"}}
  ]
}}

Only report issues you are confident about. Do not speculate."""


def _validate_with_yfinance(stock: DiscoveredStock) -> dict:
    """yfinance로 티커 실존, 시총, 유동성, 거래 가능 여부 확인."""
    result = {
        "ticker": stock.ticker,
        "exists": False,
        "market_cap": 0.0,
        "avg_daily_value": 0.0,
        "recently_traded": False,
        "short_percent": 0.0,
        "revenue_declining": False,
    }

    try:
        t = yf.Ticker(stock.ticker)
        info = t.info

        if not info or not info.get("marketCap"):
            return result

        result["exists"] = True
        result["market_cap"] = float(info.get("marketCap", 0))

        # 유동성: 평균 거래량 × 현재가
        avg_volume = info.get("averageVolume", 0) or 0
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0) or 0
        result["avg_daily_value"] = avg_volume * current_price

        # 최근 거래 확인
        hist = t.history(period="5d")
        if hist is not None and not hist.empty and len(hist) > 0:
            result["recently_traded"] = True

        # 공매도 비율
        result["short_percent"] = float(info.get("shortPercentOfFloat", 0) or 0) * 100

        # 매출 감소 추세 확인 (분기 실적)
        try:
            financials = t.quarterly_income_stmt
            if financials is not None and not financials.empty:
                if "Total Revenue" in financials.index:
                    revenues = financials.loc["Total Revenue"].dropna().head(4)
                    if len(revenues) >= 3:
                        rev_list = revenues.tolist()
                        declining = all(
                            rev_list[i] < rev_list[i + 1]
                            for i in range(min(3, len(rev_list) - 1))
                        )
                        result["revenue_declining"] = declining
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"[{stock.ticker}] yfinance validation error: {e}")

    return result


def _search_negative_catalysts(tickers: list[str]) -> dict[str, list[dict]]:
    """Perplexity API로 악재 뉴스를 일괄 검색."""
    if not settings.PERPLEXITY_API_KEY or not tickers:
        return {t: [] for t in tickers}

    prompt = NEGATIVE_CATALYST_PROMPT.format(tickers=", ".join(tickers))

    try:
        response = httpx.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar-pro",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=60.0,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]

        # JSON 추출
        text = content.strip()
        if "```" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                text = text[start:end]
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                text = text[start:end]

        result = json.loads(text)

        # 누락된 티커 빈 배열로 채우기
        for t in tickers:
            if t not in result:
                result[t] = []

        return result

    except Exception as e:
        logger.error(f"Negative catalyst search failed: {e}")
        return {t: [] for t in tickers}


def validate_stocks(stocks: list[DiscoveredStock]) -> list[ValidatedStock]:
    """
    발굴된 종목을 검증.
    1. yfinance로 기본 데이터 검증 (병렬)
    2. Perplexity로 악재 뉴스 검색 (배치)
    3. 결과 종합하여 Pass/Fail 판정 + 경고 플래그

    Returns:
        검증된 종목 리스트 (Fail 제거됨)
    """
    if not stocks:
        return []

    logger.info(f"Validating {len(stocks)} stocks...")

    # 1. yfinance 병렬 검증
    yf_results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
        futures = {
            executor.submit(_validate_with_yfinance, stock): stock
            for stock in stocks
        }
        for future in as_completed(futures):
            stock = futures[future]
            try:
                yf_results[stock.ticker] = future.result()
            except Exception as e:
                logger.error(f"[{stock.ticker}] Validation exception: {e}")
                yf_results[stock.ticker] = {"exists": False}

    # 2. Perplexity로 악재 검색 (실존하는 종목만, 10개씩 배치)
    existing_tickers = [t for t, r in yf_results.items() if r.get("exists")]
    all_negatives: dict[str, list[dict]] = {}

    batch_size = 10
    for i in range(0, len(existing_tickers), batch_size):
        batch = existing_tickers[i:i + batch_size]
        batch_result = _search_negative_catalysts(batch)
        all_negatives.update(batch_result)

    # 3. 결과 종합
    validated: list[ValidatedStock] = []

    for stock in stocks:
        yf_data = yf_results.get(stock.ticker, {})
        negatives = all_negatives.get(stock.ticker, [])

        # Pass/Fail 체크
        fail_reason = None

        if not yf_data.get("exists"):
            fail_reason = "Ticker does not exist"
        elif yf_data["market_cap"] < settings.MIN_MARKET_CAP:
            fail_reason = f"Market cap ${yf_data['market_cap']/1e6:.0f}M below $100M minimum"
        elif yf_data["market_cap"] > settings.MAX_MARKET_CAP:
            fail_reason = f"Market cap ${yf_data['market_cap']/1e9:.1f}B above $10B maximum"
        elif yf_data["avg_daily_value"] < settings.MIN_AVG_DAILY_VALUE:
            fail_reason = f"Daily value ${yf_data['avg_daily_value']/1e3:.0f}K below $500K minimum"
        elif not yf_data.get("recently_traded"):
            fail_reason = "No trading activity in last 5 days"

        # 경고 플래그 수집
        warnings: list[ValidationWarning] = []

        if yf_data.get("short_percent", 0) > settings.HIGH_SHORT_INTEREST:
            warnings.append(ValidationWarning(
                warning_type="short_interest",
                description=f"Short interest {yf_data['short_percent']:.1f}% (>{settings.HIGH_SHORT_INTEREST}%)",
            ))

        if yf_data.get("revenue_declining"):
            warnings.append(ValidationWarning(
                warning_type="revenue_decline",
                description="Revenue declined for 3+ consecutive quarters",
            ))

        for neg in negatives:
            neg_type = neg.get("type", "unknown")
            neg_desc = neg.get("description", "")
            if neg_type in ("dilution", "insider_selling", "sec_issue"):
                warnings.append(ValidationWarning(
                    warning_type=neg_type,
                    description=neg_desc,
                ))

        # 경고 3개 이상이면 Fail
        if fail_reason is None and len(warnings) > settings.MAX_WARNING_COUNT:
            fail_reason = f"Too many warnings ({len(warnings)})"

        passed = fail_reason is None

        v = ValidatedStock(
            ticker=stock.ticker,
            name=stock.name,
            theme=stock.theme,
            theme_rank=stock.theme_rank,
            stock_rank=stock.stock_rank,
            discovery_score=stock.total_score,
            market_cap=yf_data.get("market_cap", 0),
            avg_daily_value=yf_data.get("avg_daily_value", 0),
            warnings=warnings,
            warning_count=len(warnings),
            passed=passed,
            fail_reason=fail_reason,
        )

        if passed:
            validated.append(v)
            log_suffix = f" ⚠️×{len(warnings)}" if warnings else ""
            logger.info(f"  ✅ {stock.ticker} — mcap ${yf_data.get('market_cap', 0)/1e6:.0f}M{log_suffix}")
        else:
            logger.info(f"  ❌ {stock.ticker} — {fail_reason}")

    logger.info(f"Validation complete: {len(validated)}/{len(stocks)} passed")
    return validated
