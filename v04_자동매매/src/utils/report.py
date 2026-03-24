"""
실행 결과를 Markdown 리포트로 저장.
JSON과 동일한 파일명으로 .md 파일 생성.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def generate_report(result: dict, filepath: Path) -> None:
    """result dict → .md 파일로 저장."""
    lines = []

    ts = result.get("timestamp", "")[:16].replace("T", " ")
    vix = result.get("vix", {})
    anomalies = result.get("anomalies", [])
    scenarios = result.get("scenarios", [])
    chains = result.get("matched_chains", [])
    sectors = result.get("beneficiary_sectors", [])
    rankings = result.get("rankings", [])
    duration = result.get("duration_sec", 0)

    # ── 헤더 ──────────────────────────────────────────────────
    lines += [
        f"# 미장 단타 분석 리포트",
        f"",
        f"> 실행시각: {ts}  |  소요: {duration:.0f}초",
        f"",
        f"---",
        f"",
    ]

    # ── 매크로 현황 ────────────────────────────────────────────
    lines += [
        f"## 1. 매크로 현황",
        f"",
        f"| 지표 | 값 | 상태 |",
        f"|------|-----|------|",
        f"| VIX | {vix.get('vix','?')} | {vix.get('zone','?')} (보너스 +{vix.get('bonus',0)}) |",
    ]
    for a in anomalies:
        src = a.get("source", a.get("indicator", "?"))
        desc = a.get("description", "")
        chg = a.get("change_pct", 0)
        lines.append(f"| {src} | {chg:+.1f}% | {desc} |")
    lines.append("")

    # ── 시나리오 ──────────────────────────────────────────────
    lines += [
        f"## 2. AI 역추론 시나리오",
        f"",
        f"**수혜 섹터**: {', '.join(sectors) if sectors else '없음'}",
        f"",
    ]
    for i, sc in enumerate(scenarios, 1):
        name = sc.get("scenario", sc.get("name", "?"))
        prob = sc.get("probability", 0)
        reasoning = sc.get("reasoning", "")
        expected = sc.get("expected_event", "")
        horizon = sc.get("time_horizon", "?")
        beneficiary = sc.get("beneficiary_sectors", [])

        lines += [
            f"### 시나리오 {i} — {name}",
            f"",
            f"- **확률**: {prob*100:.0f}%  |  **시간축**: {horizon}",
            f"- **예상 이벤트**: {expected}" if expected else "",
            f"- **수혜 섹터**: {', '.join(beneficiary)}" if beneficiary else "",
            f"",
            f"> {reasoning[:300]}{'...' if len(reasoning) > 300 else ''}",
            f"",
        ]

    # ── 매칭 로직체인 ──────────────────────────────────────────
    if chains:
        lines += [
            f"## 3. 매칭된 로직체인",
            f"",
        ]
        for c in chains[:5]:
            event = c.get("event", "?")
            path = c.get("causal_path", "")
            beneficiary_c = c.get("beneficiary_sectors", [])
            sim = c.get("similarity", 0)
            lines += [
                f"**{event}** (유사도 {sim:.3f})",
                f"",
                f"> {path}",
                f"",
                f"수혜: {', '.join(beneficiary_c)}",
                f"",
            ]

    # ── 종목 랭킹 ─────────────────────────────────────────────
    lines += [
        f"## 4. 종목 랭킹 (Top {min(len(rankings), 20)})",
        f"",
        f"| 순위 | 티커 | 종목명 | 점수 | LC | SM | V | C | VIX | 섹터 | 신뢰도 |",
        f"|------|------|--------|------|----|----|---|---|-----|------|--------|",
    ]
    for s in rankings:
        bd = s.get("breakdown", {})
        lines.append(
            f"| #{s['rank']} | **{s['ticker']}** | {s.get('name','')} "
            f"| {s['total_score']:.1f} "
            f"| {bd.get('logic_chain_score',0):.0f} "
            f"| {bd.get('smart_money_score',0):.0f} "
            f"| {bd.get('volume_score',0):.0f} "
            f"| {bd.get('chart_score',0):.0f} "
            f"| +{bd.get('vix_bonus',0):.0f} "
            f"| {s.get('sector','-')} "
            f"| {s.get('confidence','-')} |"
        )
    lines.append("")

    # ── AI 최종 판단 (있을 경우) ──────────────────────────────
    buy_recs = [s for s in rankings if s.get("judgment", {}).get("action") == "buy"]
    if buy_recs:
        lines += [
            f"## 5. AI 매수 추천",
            f"",
        ]
        for s in buy_recs:
            j = s["judgment"]
            lines += [
                f"### ✅ {s['ticker']} — {s.get('name','')}",
                f"",
                f"- **목표가**: ${j.get('target_price',0):.2f}  |  "
                f"**손절가**: ${j.get('stop_loss',0):.2f}  |  "
                f"**보유기간**: {j.get('hold_days','?')}일",
                f"",
                f"> {j.get('reasoning','')}",
                f"",
            ]

    # ── 저장 ─────────────────────────────────────────────────
    md_path = filepath.with_suffix(".md")
    md_path.write_text("\n".join(l for l in lines if l is not None), encoding="utf-8")
