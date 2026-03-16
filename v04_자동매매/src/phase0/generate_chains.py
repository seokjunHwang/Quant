"""
Phase 0: Gemini API로 로직체인 생성.

카테고리별 50개씩, 총 300개+ 초기 체인 생성.
"""

import json
import logging
from pathlib import Path

from src.phase0.schema import LogicChain
from src.utils.config import DATA_DIR
from src.utils.gemini_client import generate_json

logger = logging.getLogger(__name__)

CHAINS_DIR = DATA_DIR / "logic_chains"

CATEGORIES = [
    ("금리_통화정책", "금리/통화정책 (Fed 금리 결정, 양적긴축/완화, 국채 수익률, 인플레이션)"),
    ("지정학_전쟁", "지정학/전쟁 (중동 분쟁, 러시아-우크라이나, 대만 해협, 북한 도발, NATO)"),
    ("무역_관세", "무역/관세 (미중 무역전쟁, 트럼프 관세, EU 규제, 반도체 수출규제, 리쇼어링)"),
    ("원자재_에너지", "원자재/에너지 (유가, 천연가스, 금, 구리, 리튬, OPEC, 신재생에너지)"),
    ("기술_규제", "기술/규제 (AI 규제, 빅테크 독점, 데이터 프라이버시, FDA 승인, 특허 분쟁)"),
    ("실적_어닝시즌", "실적/어닝시즌 (어닝 서프라이즈, 가이던스 상향/하향, 섹터 로테이션, IPO)"),
]

SYSTEM_INSTRUCTION = """당신은 미국 주식시장 매크로 분석 전문가입니다.
로직체인을 JSON 배열로 생성합니다.
각 체인은 매크로 이벤트와 수혜/피해 섹터 간의 인과관계를 나타냅니다.
단타 매매(1~5일)에 활용할 것이므로 즉각반응 체인을 우선 생성하세요."""

PROMPT_TEMPLATE = """카테고리: {category_desc}

아래 JSON 스키마에 맞게 로직체인을 {count}개 생성하세요.

JSON 스키마:
{{
  "chain_id": "LC-XXX",
  "category": "{category_name}",
  "event": "트리거 이벤트명",
  "causal_path": "이벤트 → 1차효과 → 2차효과 → 최종 영향",
  "beneficiary_sectors": ["수혜 섹터 1", "수혜 섹터 2"],
  "victim_sectors": ["피해 섹터 1"],
  "intensity": "high | medium | low",
  "time_horizon": "즉각 | 1~3일 | 1주일+",
  "reaction_speed": "즉각반응 | 1~3일 | 1주일+",
  "pre_signals": [
    "선행 징후 1 (이 이벤트가 터지기 전에 나타나는 시장 신호)",
    "선행 징후 2",
    "선행 징후 3"
  ]
}}

규칙:
- 미국 주식시장 기준
- 각 체인에 반드시 pre_signals 3~5개를 포함
- reaction_speed는 "즉각반응" 체인을 60% 이상 포함
- 섹터명은 영문으로 (예: "Semiconductors", "Oil & Gas", "Defense", "Gold Miners")
- beneficiary_sectors와 victim_sectors는 구체적으로 (예: "Banks" 말고 "Regional Banks" 또는 "Large Cap Banks")
- chain_id는 "{id_prefix}-001" 부터 순서대로

{count}개를 JSON 배열로 반환하세요."""


def generate_category_chains(
    category_name: str,
    category_desc: str,
    count: int = 50,
    id_prefix: str = "LC",
) -> list[LogicChain]:
    """단일 카테고리에 대해 로직체인을 생성."""
    prompt = PROMPT_TEMPLATE.format(
        category_name=category_name,
        category_desc=category_desc,
        count=count,
        id_prefix=id_prefix,
    )

    try:
        raw = generate_json(
            prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.4,
            max_tokens=16384,
        )

        chains = []
        for item in raw:
            item["category"] = category_name
            item["source"] = "gemini_generated"
            chains.append(LogicChain.from_dict(item))

        logger.info(f"[{category_name}] Generated {len(chains)} chains")
        return chains

    except Exception as e:
        logger.error(f"[{category_name}] Generation failed: {e}")
        return []


def generate_all_chains(count_per_category: int = 50) -> list[LogicChain]:
    """
    모든 카테고리에 대해 로직체인 생성.
    결과를 JSON 파일로 저장.
    """
    CHAINS_DIR.mkdir(parents=True, exist_ok=True)

    all_chains: list[LogicChain] = []
    chain_counter = 1

    for cat_name, cat_desc in CATEGORIES:
        id_prefix = f"LC-{cat_name[:2].upper()}"
        chains = generate_category_chains(
            category_name=cat_name,
            category_desc=cat_desc,
            count=count_per_category,
            id_prefix=id_prefix,
        )

        # Re-assign sequential IDs
        for chain in chains:
            chain.chain_id = f"LC-{chain_counter:04d}"
            chain_counter += 1

        all_chains.extend(chains)

        # Save per-category file
        cat_path = CHAINS_DIR / f"{cat_name}.json"
        with open(cat_path, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in chains], f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(chains)} chains to {cat_path}")

    # Save combined file
    all_path = CHAINS_DIR / "all_chains.json"
    with open(all_path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in all_chains], f, ensure_ascii=False, indent=2)

    logger.info(f"Total: {len(all_chains)} chains generated and saved")
    return all_chains


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_all_chains(count_per_category=50)
