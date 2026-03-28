from __future__ import annotations
"""
Step 5-2: Claude CLI로 최종 리포트 생성.
종합 분석 → 투자자 친화적 마크다운 리포트.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.utils.claude_cli import ask_claude
from src.utils.config import DATA_DIR

logger = logging.getLogger(__name__)

REPORT_PROMPT = """당신은 주식시장 분석 전문가입니다.
아래 분석 데이터를 바탕으로 오늘의 종목 추천 리포트를 작성해주세요.

=== 오늘의 시장 환경 ===
{market_summary}

=== 유효 테마 ===
{themes_summary}

=== 최종 추천 종목 ({market_label}) ===
{stocks_summary}

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
      "trading_type": "단타/스윙"
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

    # 종목 요약
    stock_lines = []
    for s in ranked_stocks[:15]:
        chart_timing = s.get("chart_result", {}).get("timing", "-")
        score = s.get("final_score", 0)
        stock_lines.append(
            f"[{s.get('rank','')}위] {s.get('name','')}({s.get('ticker','')}) "
            f"점수:{score} 테마:{s.get('theme','')} 타이밍:{chart_timing}\n"
            f"  차트: {s.get('chart_result', {}).get('chart_summary', '')[:80]}\n"
            f"  뉴스: {s.get('research', {}).get('news_summary', '')[:80]}"
        )
    stocks_summary = "\n".join(stock_lines)

    prompt = REPORT_PROMPT.format(
        market_label=market_label,
        market_summary=market_summary_text,
        themes_summary=themes_summary,
        stocks_summary=stocks_summary,
    )

    logger.info("Generating final report via Claude CLI...")
    result = ask_claude(prompt, expect_json=True, context="step5_report")
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
    today = datetime.now().strftime("%Y%m%d")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = DATA_DIR / today / market
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    full_data = {
        "generated_at": datetime.now().isoformat(),
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
    today = datetime.now().strftime("%Y년 %m월 %d일")
    market_label = "국장" if market == "kr" else "미장" if market == "us" else "국장+미장"

    lines = [
        f"# 종목 추천 리포트 — {today} ({market_label})",
        f"> 생성: {datetime.now().strftime('%H:%M')} KST",
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
