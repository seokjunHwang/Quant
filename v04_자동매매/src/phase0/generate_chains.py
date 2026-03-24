"""
Phase 0: Gemini API로 로직체인 생성.

카테고리 20개 × 25개씩 = 총 500개 초기 체인 생성.
"""

import json
import logging
import time
from pathlib import Path

from src.phase0.schema import LogicChain
from src.utils.config import DATA_DIR
from src.utils.gemini_client import generate_json

logger = logging.getLogger(__name__)

CHAINS_DIR = DATA_DIR / "logic_chains"

CATEGORIES = [
    # ── 통화/금융 ──
    ("금리_통화정책", "금리/통화정책 (Fed 금리 결정, 양적긴축/완화, 국채 수익률, 인플레이션, FOMC 회의)"),
    ("금융위기_신용경색", "금융위기/신용경색 (은행 파산(SVB, 리먼), 서브프라임, 신용스프레드 급등, 뱅크런, 유동성 위기, 채권시장 폭락)"),
    ("인플레이션_디플레이션", "인플레이션/디플레이션 (CPI 급등, PCE 서프라이즈, 스태그플레이션, 임금-물가 스파이럴, 디플레 공포)"),

    # ── 지정학/정치 ──
    ("지정학_전쟁", "지정학/전쟁 (중동 분쟁(이란-이스라엘), 러시아-우크라이나, 대만 해협 위기, NATO 확대, 핵위협)"),
    ("미국_선거_정치", "미국 선거/정치 (대통령 선거, 중간선거, 정권교체 효과, 의회 교착, 정부 셧다운, 부채한도 위기, 탄핵)"),
    ("테러_자연재해", "테러/자연재해 (9/11 같은 대형 테러, 허리케인(카트리나/하비), 대지진, 쓰나미, 산불, 인프라 파괴)"),

    # ── 무역/글로벌 ──
    ("무역_관세", "무역/관세 (미중 무역전쟁, 트럼프 관세(60%), EU 보복관세, 반도체 수출규제, 리쇼어링, WTO 분쟁)"),
    ("공급망_물류", "공급망/물류 (수에즈 운하 봉쇄, 반도체 부족, 항만 파업, 해운비 급등, 중국 봉쇄(제로코로나), 희토류 수출금지)"),
    ("신흥국_위기", "신흥국 위기 (통화위기(터키/아르헨티나), 국가 디폴트, 자본유출, IMF 구제금융, 중국 부동산 버블 붕괴(에버그란데))"),

    # ── 원자재 ──
    ("원자재_에너지", "원자재/에너지 (유가 급등/폭락, OPEC 감산/증산, 천연가스 위기, LNG 수요, 신재생에너지 전환, 에너지 안보)"),
    ("금_안전자산", "금/안전자산 (금값 급등, 중앙은행 금 매입, 달러 약세→금 강세, 비트코인 vs 금, 안전자산 선호(risk-off))"),

    # ── 산업/기술 ──
    ("기술_규제", "기술/규제 (AI 규제, 빅테크 독점 소송, 데이터 프라이버시(GDPR), FDA 승인/거부, 특허 분쟁, 반독점)"),
    ("AI_기술혁신", "AI/기술혁신 (ChatGPT/AI 붐, 신형 GPU 발표, AI 규제법안, 자율주행 승인, 양자컴퓨팅 돌파, 로봇/자동화)"),
    ("암호화폐_디지털자산", "암호화폐/디지털자산 (비트코인 반감기, ETF 승인, 거래소 파산(FTX), 규제 강화/완화, 스테이블코인 위기, CBDC)"),

    # ── 보건/사회 ──
    ("팬데믹_전염병", "팬데믹/전염병 (COVID-19, SARS, 조류독감(H5N1), 원숭이두창, WHO 비상선언, 백신 개발, 봉쇄/락다운, 의료주 수혜)"),
    ("노동시장_고용", "노동시장/고용 (비농업 고용(NFP) 서프라이즈, 실업률 급등, 대규모 파업(UAW/UPS), 해고 물결(빅테크 레이오프), 임금 상승)"),

    # ── 기업/시장 ──
    ("실적_어닝시즌", "실적/어닝시즌 (어닝 서프라이즈/쇼크, 가이던스 상향/하향, 매그니피센트7 실적, 섹터 로테이션, IPO 붐/한파)"),
    ("MA_기업이벤트", "M&A/기업 이벤트 (메가딜 발표, 적대적 인수, 기업 분사(스핀오프), 대형 파산(Chapter 11), 자사주 매입, 배당 컷)"),

    # ── 환경/정책 ──
    ("ESG_기후변화", "ESG/기후변화 (탄소규제 강화, 그린뉴딜/IRA 보조금, 탄소세 도입, 전기차 보조금 변경, 석탄 퇴출, 탄소배출권 가격)"),
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

        # Rate limit 방지: 카테고리 간 3초 쿨다운
        time.sleep(3)

    # Save combined file
    all_path = CHAINS_DIR / "all_chains.json"
    with open(all_path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in all_chains], f, ensure_ascii=False, indent=2)

    logger.info(f"Total: {len(all_chains)} chains generated and saved")
    return all_chains


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_all_chains(count_per_category=25)
