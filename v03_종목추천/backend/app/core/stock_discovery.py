"""
Step 2: Stock Discovery — Claude API로 테마별 중소주를 발굴하고 랭킹.

종목 랭킹 기준 (가중치 적용 = 100점 만점):
  1. 테마 순수도 (25%) — 매출 중 해당 테마 비중, Pure-play일수록 높음
  2. 매출 성장률 (20%) — 최근 분기 YoY 매출 성장률
  3. 거래량 급증 (20%) — 최근 거래량 vs 평균 (시장 관심도)
  4. 가격 위치 (15%) — 52주 고점 대비 위치 (이미 과열된 종목은 감점)
  5. 촉매 유무 (10%) — 계약/실적/규제 등 구체적 이벤트
  6. 재무 건전성 (10%) — 현금보유, 부채비율
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from app.config import settings
from app.models.schemas import DiscoveredStock, TrendTheme

logger = logging.getLogger(__name__)

STOCK_DISCOVERY_PROMPT = """You are a stock research analyst specializing in small/mid-cap stocks.

THEME: "{theme}"
THEME CONTEXT: {description}

Find {count} US-listed small/mid-cap stocks that benefit from this theme.

Requirements:
- Market cap: $100M to $10B (STRICT — do NOT include mega/large caps like AAPL, MSFT, NVDA, etc.)
- US-listed on NYSE, NASDAQ, or NYSE American
- Actively traded (not OTC/pink sheets)
- Real, currently existing companies with valid tickers

Score each stock on these criteria:
1. purity_score (0-25): What % of revenue/business comes directly from this theme. Pure-play=20-25, significant exposure=12-18, tangential=5-10.
2. growth_score (0-20): Recent quarter YoY revenue growth. 50%+=18-20, 20-50%=12-17, 0-20%=5-11, negative=0-4.
3. volume_score (0-20): Recent trading volume surge vs 20-day average. 3x+=18-20, 2x=12-17, normal=5-10.
4. position_score (0-15): Position in 52-week range. Near lows (potential upside)=12-15, middle=7-11, near highs (already ran)=0-6.
5. catalyst_score (0-10): Specific upcoming catalysts (contracts, earnings, FDA, regulation). Strong catalyst=8-10, moderate=4-7, none=0-3.
6. financial_score (0-10): Cash position, debt ratio, burn rate. Strong balance sheet=8-10, adequate=4-7, concerning=0-3.

IMPORTANT: Return ONLY a valid JSON array. Example:
[
  {{
    "ticker": "RCAT",
    "name": "Red Cat Holdings",
    "stock_rank": 1,
    "purity_score": 24,
    "growth_score": 18,
    "volume_score": 19,
    "position_score": 13,
    "catalyst_score": 9,
    "financial_score": 8,
    "total_score": 91,
    "reasoning": "Pure-play military drone company. 120% YoY revenue growth. Recent DoD contract win.",
    "market_cap_estimate": "$820M"
  }}
]

Return exactly {count} stocks ranked by total_score descending.
Only include REAL companies with VALID tickers. Do NOT make up companies."""


def _parse_json_response(text: str) -> list[dict]:
    """AI 응답에서 JSON 배열을 추출."""
    text = text.strip()

    if "```" in text:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            text = text[start:end]

    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            text = text[start:end]

    return json.loads(text)


def _discover_for_theme(
    client: anthropic.Anthropic,
    theme: TrendTheme,
    count: int,
) -> list[DiscoveredStock]:
    """단일 테마에 대해 종목을 발굴."""
    prompt = STOCK_DISCOVERY_PROMPT.format(
        theme=theme.theme,
        description=f"{theme.description}. {theme.reasoning}",
        count=count,
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        raw_stocks = _parse_json_response(content)

        stocks = []
        for item in raw_stocks:
            # total_score 재계산
            calculated_total = (
                item.get("purity_score", 0)
                + item.get("growth_score", 0)
                + item.get("volume_score", 0)
                + item.get("position_score", 0)
                + item.get("catalyst_score", 0)
                + item.get("financial_score", 0)
            )
            item["total_score"] = calculated_total
            item["theme"] = theme.theme
            item["theme_rank"] = theme.rank

            stocks.append(DiscoveredStock(**item))

        stocks.sort(key=lambda s: s.total_score, reverse=True)
        for i, stock in enumerate(stocks):
            stock.stock_rank = i + 1

        logger.info(
            f"  Theme '{theme.theme}': discovered {len(stocks)} stocks "
            f"({[s.ticker for s in stocks]})"
        )
        return stocks

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse Claude response for theme '{theme.theme}': {e}")
        return []
    except Exception as e:
        logger.error(f"Stock discovery failed for theme '{theme.theme}': {e}")
        return []


def discover_stocks(
    themes: list[TrendTheme],
    stocks_per_theme: int | None = None,
) -> list[DiscoveredStock]:
    """
    각 테마별로 Claude API를 호출해 중소주를 발굴.
    테마별 병렬 처리.

    Returns:
        전체 발굴 종목 리스트
    """
    stocks_per_theme = stocks_per_theme or settings.STOCKS_PER_THEME

    if not settings.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not configured")
        return []

    if not themes:
        logger.warning("No themes provided for stock discovery")
        return []

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    all_stocks: list[DiscoveredStock] = []

    logger.info(f"Starting stock discovery for {len(themes)} themes")

    # 테마별 병렬 호출 (최대 5개)
    with ThreadPoolExecutor(max_workers=min(len(themes), 5)) as executor:
        futures = {
            executor.submit(_discover_for_theme, client, theme, stocks_per_theme): theme
            for theme in themes
        }

        for future in as_completed(futures):
            theme = futures[future]
            try:
                stocks = future.result()
                all_stocks.extend(stocks)
            except Exception as e:
                logger.error(f"Exception discovering stocks for '{theme.theme}': {e}")

    # 티커 중복 제거 (여러 테마에서 같은 종목이 나올 수 있음 → 더 높은 점수 유지)
    seen: dict[str, DiscoveredStock] = {}
    for stock in all_stocks:
        if stock.ticker not in seen or stock.total_score > seen[stock.ticker].total_score:
            seen[stock.ticker] = stock

    deduped = sorted(seen.values(), key=lambda s: s.total_score, reverse=True)

    logger.info(
        f"Stock discovery complete: {len(all_stocks)} found, "
        f"{len(deduped)} unique after dedup"
    )
    return deduped
