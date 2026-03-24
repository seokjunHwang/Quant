"""
Step 2-2: AI 역추론 — 이상 신호의 원인을 추론하고 로직체인과 매칭.

흐름:
1. 이상 신호 텍스트 → Gemini에게 원인 추론 요청
2. 추론 결과 → ChromaDB에서 pre_signals 벡터 유사도 매칭
3. 매칭된 로직체인에서 수혜/피해 섹터 도출
4. 매칭 실패 시 → Gemini가 신규 체인 생성 → DB 추가
"""

import json
import logging
from datetime import date, datetime

from src.phase0.embed_chains import add_new_chain, search_chains
from src.phase0.schema import LogicChain
from src.step2_inference.anomaly_detector import (
    aggregate_anomalies,
    build_anomaly_summary,
    build_search_query,
)
from src.utils.gemini_client import generate, generate_json

logger = logging.getLogger(__name__)

REVERSE_INFERENCE_SYSTEM = """당신은 미국 주식시장 매크로 분석 전문가입니다.
주어진 시장 이상 신호를 분석하여, 이 신호들이 발생한 근본 원인을 역추론하세요.
단순한 설명이 아니라 "왜 이런 움직임이 동시에 나왔는가?"에 초점을 맞추세요."""

REVERSE_INFERENCE_PROMPT = """다음 이상 신호들이 동시에 감지되었습니다:

{anomaly_summary}

아래 형식의 JSON 배열로 가능한 시나리오 3개를 반환하세요:
[
  {{
    "scenario": "시나리오명",
    "probability": 0.7,
    "reasoning": "이 신호 조합이 왜 이 시나리오를 가리키는지 상세 설명",
    "expected_event": "예상되는 이벤트/뉴스",
    "time_horizon": "즉각 | 1~3일 | 1주일+",
    "beneficiary_sectors": ["수혜 섹터1", "수혜 섹터2"],
    "victim_sectors": ["피해 섹터1"],
    "key_signals_used": ["사용한 신호1", "사용한 신호2"]
  }}
]

규칙:
- probability는 0.0~1.0 (합이 1.0이 될 필요 없음)
- 섹터명은 영문 (예: "Semiconductors", "Defense", "Gold Miners")
- 가장 가능성 높은 시나리오를 첫 번째로"""

NEW_CHAIN_PROMPT = """아래 시나리오를 로직체인 형식으로 변환하세요:

시나리오: {scenario}
추론: {reasoning}
예상 이벤트: {expected_event}
수혜: {beneficiary}
피해: {victim}

JSON 형식:
{{
  "event": "트리거 이벤트명",
  "causal_path": "이벤트 → 1차효과 → 2차효과 → 최종 영향",
  "beneficiary_sectors": ["섹터1", "섹터2"],
  "victim_sectors": ["섹터1"],
  "intensity": "high | medium | low",
  "time_horizon": "즉각 | 1~3일 | 1주일+",
  "reaction_speed": "즉각반응 | 1~3일 | 1주일+",
  "pre_signals": ["선행 징후 1", "선행 징후 2", "선행 징후 3"],
  "category": "금리_통화정책 | 지정학_전쟁 | 무역_관세 | 원자재_에너지 | 기술_규제 | 실적_어닝시즌"
}}"""

# Minimum similarity threshold for chain matching
MIN_SIMILARITY = 0.35


def run_reverse_inference(
    macro_result: dict,
    smart_money_result: dict,
) -> dict:
    """
    역추론 전체 파이프라인.

    Args:
        macro_result: Step 1 매크로 수집 결과
        smart_money_result: Step 1 스마트머니 수집 결과

    Returns:
        {
            "scenarios": [...],       # AI 추론 시나리오
            "matched_chains": [...],  # 매칭된 로직체인
            "new_chains_added": int,  # 신규 추가된 체인 수
            "beneficiary_sectors": [...],  # 최종 수혜 섹터
            "victim_sectors": [...],       # 최종 피해 섹터
        }
    """
    # 1. Aggregate anomalies (레벨 기반 컨텍스트 포함이라 항상 1개 이상)
    anomalies = aggregate_anomalies(macro_result, smart_money_result)

    summary = build_anomaly_summary(anomalies)

    logger.info(f"Detected {len(anomalies)} anomalies, running inference...")

    # 2. AI reverse inference
    scenarios = _infer_scenarios(summary)

    # 3. Vector search — 시나리오 텍스트로 검색 (원시 신호보다 의미 매칭 훨씬 좋음)
    matched_chains = _search_matching_chains_from_scenarios(scenarios, anomalies)

    # 4. Generate new chains if no good match
    new_count = 0
    if not matched_chains and scenarios:
        new_count = _generate_new_chains(scenarios)

    # 5. Compile final sectors
    all_beneficiary = set()
    all_victim = set()

    for s in scenarios:
        all_beneficiary.update(s.get("beneficiary_sectors", []))
        all_victim.update(s.get("victim_sectors", []))

    for c in matched_chains:
        all_beneficiary.update(c.get("beneficiary_sectors", []))
        all_victim.update(c.get("victim_sectors", []))

    return {
        "scenarios": scenarios,
        "matched_chains": matched_chains,
        "new_chains_added": new_count,
        "beneficiary_sectors": sorted(all_beneficiary),
        "victim_sectors": sorted(all_victim),
        "anomaly_count": len(anomalies),
        "timestamp": datetime.now().isoformat(),
    }


def _infer_scenarios(anomaly_summary: str) -> list[dict]:
    """Gemini에게 역추론 요청."""
    prompt = REVERSE_INFERENCE_PROMPT.format(anomaly_summary=anomaly_summary)

    try:
        scenarios = generate_json(
            prompt,
            system_instruction=REVERSE_INFERENCE_SYSTEM,
            temperature=0.3,
        )

        if isinstance(scenarios, list):
            logger.info(f"Inferred {len(scenarios)} scenarios")
            return scenarios

        return []

    except Exception as e:
        logger.error(f"Reverse inference failed: {e}")
        return []


def _search_matching_chains_from_scenarios(
    scenarios: list[dict],
    anomalies: list[dict],
) -> list[dict]:
    """
    시나리오 + 이상신호 텍스트로 ChromaDB 다중 검색 후 머지.

    - 시나리오별로 "이벤트 설명 + 수혜섹터" 쿼리를 만들어 검색
    - 원시 이상신호 쿼리도 보조로 검색
    - 중복 제거 후 유사도 기준 정렬
    """
    seen_ids: set[str] = set()
    all_results: list[dict] = []

    queries = []

    # 시나리오 기반 쿼리 (의미 매칭에 훨씬 효과적)
    for sc in scenarios[:3]:
        scenario_name = sc.get("scenario", "")
        expected = sc.get("expected_event", "")
        beneficiary = ", ".join(sc.get("beneficiary_sectors", []))
        reasoning_snippet = sc.get("reasoning", "")[:200]
        q = f"{scenario_name}. {expected}. 수혜: {beneficiary}. {reasoning_snippet}"
        queries.append(q.strip())

    # 보조: 원시 이상신호 쿼리
    raw_terms = [a.get("description", "") for a in anomalies if a.get("description")]
    if raw_terms:
        queries.append(", ".join(raw_terms[:5]))

    try:
        for query in queries:
            if not query:
                continue
            results = search_chains(query, n_results=5, reaction_speed=None)
            for r in results:
                cid = r.get("chain_id", "")
                if cid not in seen_ids and r["similarity"] >= MIN_SIMILARITY:
                    seen_ids.add(cid)
                    all_results.append(r)

        # 유사도 기준 내림차순 정렬
        all_results.sort(key=lambda x: x["similarity"], reverse=True)
        good = all_results[:10]  # 상위 10개

        if good:
            logger.info(
                f"Found {len(good)} matching chains "
                f"(best: {good[0]['similarity']:.3f})"
            )
        else:
            logger.info(f"No chains above similarity threshold ({MIN_SIMILARITY})")

        return good

    except Exception as e:
        logger.warning(f"Chain search failed: {e}")
        return []


def _generate_new_chains(scenarios: list[dict]) -> int:
    """매칭 실패 시 시나리오를 새 로직체인으로 변환하여 DB에 추가."""
    added = 0

    for scenario in scenarios[:2]:  # Top 2 scenarios only
        try:
            prompt = NEW_CHAIN_PROMPT.format(
                scenario=scenario.get("scenario", ""),
                reasoning=scenario.get("reasoning", ""),
                expected_event=scenario.get("expected_event", ""),
                beneficiary=", ".join(scenario.get("beneficiary_sectors", [])),
                victim=", ".join(scenario.get("victim_sectors", [])),
            )

            chain_data = generate_json(prompt, temperature=0.2)
            if isinstance(chain_data, list):
                chain_data = chain_data[0]

            # Create LogicChain
            chain_id = f"LC-AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}-{added}"
            chain_data["chain_id"] = chain_id
            chain_data["source"] = "auto_generated"

            chain = LogicChain.from_dict(chain_data)
            add_new_chain(chain)
            added += 1

            logger.info(f"Auto-generated chain: {chain_id} - {chain.event}")

        except Exception as e:
            logger.warning(f"Failed to generate new chain: {e}")

    return added
