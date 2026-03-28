from __future__ import annotations
"""
Step 5-2: Claude CLI로 최종 리포트 생성.
종합 분석 → 투자자 친화적 마크다운 리포트.
"""

import json
import logging
from pathlib import Path

from src.utils.claude_cli import ask_claude
from src.utils.config import DATA_DIR, now_kst
from src.utils.gemini_client import generate_json

logger = logging.getLogger(__name__)


# ── 일정 검색 (Gemini Search) ─────────────────────────────────────────────────

def fetch_upcoming_events(stocks: list[dict], batch_size: int = 5) -> dict:
    """
    추천 종목들의 향후 일정 (실적발표, 배당, 컨퍼런스 등) 검색.
    5종목씩 배치로 Gemini Search 호출하여 쿼리 절약.

    Returns:
        {ticker: {"earnings": ..., "events": [...], "summary": ...}, ...}
    """
    today = now_kst().strftime("%Y년 %m월 %d일")
    result = {}

    for i in range(0, len(stocks), batch_size):
        batch = stocks[i:i + batch_size]
        stock_list = ", ".join(
            f"{s.get('name','')}({s.get('ticker','')})" for s in batch
        )
        tickers = [s.get("ticker", "") for s in batch]

        prompt = f"""오늘({today}) 기준 아래 종목들의 향후 1개월 주요 일정을 검색해서 JSON으로 반환해줘.
실적발표, 배당락일, IR/컨퍼런스, FDA 승인, 주주총회, 지수편입/편출, 분할 등 주가에 영향 주는 이벤트만.

종목: {stock_list}

{{
  "events": [
    {{
      "ticker": "티커",
      "upcoming": [
        {{"date": "YYYY-MM-DD 또는 예정", "event": "이벤트명", "impact": "호재/악재/중립", "detail": "상세 설명"}}
      ]
    }}
  ]
}}

규칙:
- 확인된 일정만 포함 (추측 금지)
- 날짜 모르면 "미정" 또는 "Q2 예정" 등으로
- 일정 없으면 upcoming을 빈 배열 []"""

        for attempt in range(2):  # 1회 재시도
            try:
                data = generate_json(
                    prompt,
                    temperature=0.1,
                    use_search=True,
                    search_context=f"step5_events_batch{i // batch_size + 1}",
                )
                for item in data.get("events", []):
                    ticker = item.get("ticker", "")
                    if ticker:
                        result[ticker] = item.get("upcoming", [])
                break  # 성공 시 재시도 안 함
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"Event search retry (batch {i // batch_size + 1}): {e}")
                else:
                    logger.warning(f"Event search failed (batch {i // batch_size + 1}): {e}")
                    for t in tickers:
                        result.setdefault(t, [])

    logger.info(f"Upcoming events fetched for {len(result)} stocks")
    return result

REPORT_PROMPT = """당신은 주식시장 분석 전문가입니다.
아래 분석 데이터를 바탕으로 오늘의 종목 추천 리포트를 작성해주세요.

=== 오늘의 시장 환경 ===
{market_summary}

=== 유효 테마 ===
{themes_summary}

=== 최종 추천 종목 ({market_label}) ===
{stocks_summary}

=== 향후 주요 일정 ===
{events_summary}

아래 JSON 형식으로 반환하세요:
{{
  "report_title": "오늘의 추천 종목 - 날짜",
  "executive_summary": "오늘 시장 핵심 3줄 요약",
  "market_view": "전체 시장 방향성 (bullish/bearish/neutral) + 근거",
  "top_theme": "오늘 최강 테마 이름 + 한 줄 이유",
  "recommendations": [
    {{
      "rank": 1,
      "ticker": "티커",
      "name": "종목명",
      "theme": "테마",
      "why": "왜 지금 이 종목인지 2~3줄",
      "entry": "진입 전략",
      "stop_loss": "손절 기준",
      "target": "목표가/목표 등락률",
      "risk": "주요 리스크",
      "trading_type": "단타/스윙",
      "upcoming_events": "향후 주요 일정 (실적발표·배당 등) 1~2줄 요약. 없으면 '예정된 일정 없음'"
    }}
  ],
  "avoid_stocks": ["주의할 종목 티커/이름"],
  "one_line_strategy": "오늘 전체 매매 전략 한 줄"
}}"""


def generate_report(
    themes_data: dict,
    ranked_stocks: list[dict],
    macro_data: dict,
    market: str,
) -> dict:
    """
    Claude CLI → 최종 투자 리포트.

    Args:
        themes_data: step2 테마 분석 결과
        ranked_stocks: step5 최종 순위 종목 리스트
        macro_data: step1 매크로 데이터
        market: "kr" | "us" | "all"
    """
    market_label = "국장" if market == "kr" else "미장" if market == "us" else "국장+미장"

    # 시장 요약
    market_summary = themes_data.get("market_summary", "")
    overall_strategy = themes_data.get("overall_strategy", "")
    market_summary_text = f"{market_summary}\n전략: {overall_strategy}"

    # 테마 요약
    theme_lines = []
    for t in themes_data.get("themes", [])[:5]:
        theme_lines.append(
            f"- [{t.get('strength','?')}] {t.get('theme_name','')} "
            f"({t.get('trading_type','')} / {t.get('duration','')}): {t.get('reason','')[:80]}"
        )
    themes_summary = "\n".join(theme_lines)

    # 향후 일정 검색 (Gemini Search)
    top15 = ranked_stocks  # main.py에서 이미 국장/미장별 상위 N개로 잘라서 전달
    logger.info(f"Fetching upcoming events for {len(top15)} stocks...")
    events_map = fetch_upcoming_events(top15)

    # 종목 요약 (일정 포함)
    stock_lines = []
    for s in top15:
        ticker = s.get("ticker", "")
        chart_timing = s.get("chart_result", {}).get("timing", "-")
        score = s.get("final_score", 0)

        events = events_map.get(ticker, [])
        events_text = ""
        if events:
            events_text = "  일정: " + " / ".join(
                f"{e.get('date','?')} {e.get('event','')}" for e in events[:3]
            )

        stock_lines.append(
            f"[{s.get('rank','')}위] {s.get('name','')}({ticker}) "
            f"점수:{score} 테마:{s.get('theme','')} 타이밍:{chart_timing}\n"
            f"  차트: {s.get('chart_result', {}).get('chart_summary', '')[:80]}\n"
            f"  뉴스: {s.get('research', {}).get('news_summary', '')[:80]}"
            + (f"\n{events_text}" if events_text else "")
        )
    stocks_summary = "\n".join(stock_lines)

    # 일정 요약 (별도 섹션)
    event_lines = []
    for s in top15:
        ticker = s.get("ticker", "")
        name = s.get("name", "")
        events = events_map.get(ticker, [])
        if events:
            for e in events[:3]:
                impact = e.get("impact", "중립")
                event_lines.append(
                    f"- {name}({ticker}): {e.get('date','?')} {e.get('event','')} [{impact}]"
                )
    events_summary = "\n".join(event_lines) if event_lines else "확인된 향후 일정 없음"

    prompt = REPORT_PROMPT.format(
        market_label=market_label,
        market_summary=market_summary_text,
        themes_summary=themes_summary,
        stocks_summary=stocks_summary,
        events_summary=events_summary,
    )

    logger.info("Generating final report via Claude CLI...")
    result = ask_claude(prompt, expect_json=True, context="step5_report")

    # events_map도 result에 첨부
    if isinstance(result, dict):
        result["_events_map"] = events_map

    return result if isinstance(result, dict) else {}


def save_report(
    report: dict,
    ranked_stocks: list[dict],
    themes_data: dict,
    macro_data: dict,
    market: str,
) -> Path:
    """
    최종 리포트 JSON + MD 저장.
    """
    today = now_kst().strftime("%Y%m%d")
    timestamp = now_kst().strftime("%Y%m%d_%H%M")
    out_dir = DATA_DIR / today / market / "step5_리포트"
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    full_data = {
        "generated_at": now_kst().isoformat(),
        "market": market,
        "report": report,
        "ranked_stocks": ranked_stocks,
        "themes": themes_data,
        "macro_snapshot": {
            k: v for k, v in macro_data.items()
            if isinstance(v, dict) and "price" in v
        },
    }
    json_path = out_dir / f"final_report_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)

    # MD
    md_path = out_dir / f"final_report_{timestamp}.md"
    _write_md_report(report, ranked_stocks, themes_data, macro_data, market, md_path)

    logger.info(f"Final report saved → {md_path}")
    return md_path


def _write_md_report(
    report: dict,
    ranked_stocks: list[dict],
    themes_data: dict,
    macro_data: dict,
    market: str,
    path: Path,
) -> None:
    today = now_kst().strftime("%Y년 %m월 %d일")
    market_label = "국장" if market == "kr" else "미장" if market == "us" else "국장+미장"

    lines = [
        f"# 종목 추천 리포트 — {today} ({market_label})",
        f"> 생성: {now_kst().strftime('%H:%M')} KST",
        "",
        "---",
        "",
        "## 핵심 요약",
        "",
        report.get("executive_summary", ""),
        "",
        f"**시장 방향:** {report.get('market_view', '')}",
        f"**오늘의 핵심 테마:** {report.get('top_theme', '')}",
        f"**매매 전략:** {report.get('one_line_strategy', '')}",
        "",
        "---",
        "",
        "## 매크로 현황",
        "",
    ]

    for k, v in macro_data.items():
        if isinstance(v, dict) and "price" in v:
            chg = v.get("change_pct", 0)
            sign = "+" if chg >= 0 else ""
            lines.append(f"- **{k}**: {v['price']} ({sign}{chg:.1f}%)")

    lines += [
        "",
        "---",
        "",
        "## 오늘의 테마",
        "",
    ]

    for t in themes_data.get("themes", []):
        lines += [
            f"### [{t.get('strength','?')}] {t.get('theme_name','')}",
            f"- **유형**: {t.get('trading_type','')} / {t.get('duration','')}",
            f"- **근거**: {t.get('reason','')}",
            f"- **리스크**: {t.get('risk','')}",
            "",
        ]

    lines += [
        "---",
        "",
        f"## 최종 추천 종목 ({len(ranked_stocks)}개)",
        "",
    ]

    for rec in report.get("recommendations", []):
        rank = rec.get("rank", "?")
        ticker = rec.get("ticker", "")
        name = rec.get("name", "")
        theme = rec.get("theme", "")
        why = rec.get("why", "")
        entry = rec.get("entry", "-")
        stop = rec.get("stop_loss", "-")
        target = rec.get("target", "-")
        risk = rec.get("risk", "-")
        ttype = rec.get("trading_type", "-")

        # 점수 찾기
        score = next(
            (s.get("final_score", "-") for s in ranked_stocks if s.get("ticker") == ticker),
            "-"
        )
        score_detail = next(
            (s.get("score_detail", {}) for s in ranked_stocks if s.get("ticker") == ticker),
            {}
        )

        upcoming = rec.get("upcoming_events", "")

        lines += [
            f"### {rank}위 — {name} ({ticker})",
            f"**테마:** {theme} | **유형:** {ttype} | **종합점수:** {score}",
            "",
            f"> {why}",
            "",
            f"| 항목 | 내용 |",
            f"|------|------|",
            f"| 진입 | {entry} |",
            f"| 손절 | {stop} |",
            f"| 목표 | {target} |",
            f"| 리스크 | {risk} |",
            f"| 향후 일정 | {upcoming or '예정된 일정 없음'} |",
        ]

        if score_detail:
            lines.append(
                f"| 점수 구성 | 테마:{score_detail.get('theme','-')} "
                f"차트:{score_detail.get('chart','-')} "
                f"수급:{score_detail.get('supply_demand','-')} "
                f"재무:{score_detail.get('financial','-')} |"
            )
        lines.append("")

    # 피해야 할 종목
    avoid = report.get("avoid_stocks", [])
    if avoid:
        lines += [
            "---",
            "",
            "## 주의 종목",
            "",
            ", ".join(avoid),
            "",
        ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
