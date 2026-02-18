"""Stage 4: Analyzer — Role classification for verified indicators.

Uses Claude API to classify each indicator's role in a composite strategy:
primary_signal, confirmation, market_filter, exit_signal.
"""

import json
from pathlib import Path

from ai.pipeline.converter import load_converted_module, PINE_DIR, CONVERTED_DIR
from ai.pipeline.utils.db import PipelineDB
from ai.pipeline.utils.logger import get_logger

logger = get_logger("analyzer")

CLASSIFICATION_PROMPT = """다음 지표의 Python 코드와 원본 Pine Script를 분석하여 역할을 분류하라.

반드시 아래 JSON 형식으로만 응답하라. 설명 없이 JSON만 출력:

{{
  "roles": ["primary_signal | confirmation | market_filter | exit_signal 중 해당하는 것들"],
  "indicator_type": "추세추종 | 모멘텀 | 변동성 | 거래량 | 패턴인식 | 복합",
  "market_condition": "추세장 | 횡보장 | 전체",
  "timeframe_fit": "스캘핑 | 데이트레이딩 | 스윙 | 포지션",
  "recommended_partners": ["이 지표와 보완적인 역할/유형 설명"],
  "description": "핵심 로직 한 줄 요약"
}}

역할 분류 기준:
- primary_signal: 명확한 매수/매도 진입 시그널을 생성 (예: crossover, threshold cross)
- confirmation: 단독보다 보조 확인 용도로 적합 (예: RSI로 과매수/과매도 확인)
- market_filter: 시장 상태를 판단하여 매매 허용/금지 (예: ADX로 추세 유무 판단)
- exit_signal: 청산 타이밍 결정에 특화 (예: trailing stop, SAR)

하나의 지표가 여러 역할을 가질 수 있다.

[원본 Pine Script]
{pine_source}

[변환된 Python]
{python_source}
"""


def analyze_indicator(
    indicator_id: str,
    model: str = "claude-sonnet-4-20250514",
    db: PipelineDB | None = None,
) -> dict | None:
    """Analyze a verified indicator and classify its role.

    Args:
        indicator_id: Indicator name (filename stem).
        model: Claude model to use.
        db: Pipeline database instance.

    Returns:
        Analysis result dict, or None on failure.
    """
    import anthropic

    db = db or PipelineDB()

    # Check status
    ind = db.get_indicator(indicator_id)
    if ind is None:
        logger.error(f"Indicator not found: {indicator_id}")
        return None
    if ind["conversion_status"] != "verified":
        logger.warning(f"{indicator_id} is not verified (status={ind['conversion_status']})")

    # Read source files
    pine_path = PINE_DIR / f"{indicator_id}.pine"
    py_path = CONVERTED_DIR / f"{indicator_id}.py"

    pine_source = ""
    if pine_path.exists():
        pine_source = pine_path.read_text(encoding="utf-8", errors="replace")

    if not py_path.exists():
        logger.error(f"Converted file not found: {py_path}")
        return None
    python_source = py_path.read_text(encoding="utf-8")

    # Call Claude API
    prompt = CLASSIFICATION_PROMPT.replace("{pine_source}", pine_source).replace(
        "{python_source}", python_source
    )

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Parse JSON response
    try:
        # Handle potential markdown wrapping
        if response_text.startswith("```"):
            response_text = response_text.strip("`").strip()
            if response_text.startswith("json"):
                response_text = response_text[4:].strip()
        result = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse analysis JSON for {indicator_id}: {response_text[:200]}")
        return None

    # Get default params from module
    module = load_converted_module(indicator_id)
    default_params = {}
    if module and hasattr(module, "METADATA"):
        default_params = module.METADATA.get("default_params", {})

    # Save to DB
    analysis_data = {
        "indicator_id": indicator_id,
        "roles": json.dumps(result.get("roles", []), ensure_ascii=False),
        "indicator_type": result.get("indicator_type", ""),
        "market_condition": result.get("market_condition", ""),
        "timeframe_fit": result.get("timeframe_fit", ""),
        "recommended_partners": json.dumps(
            result.get("recommended_partners", []), ensure_ascii=False
        ),
        "default_params": json.dumps(default_params),
        "description": result.get("description", ""),
    }
    db.upsert_analysis(analysis_data)

    logger.info(f"Analyzed {indicator_id}: roles={result.get('roles')}, type={result.get('indicator_type')}")
    return result


def analyze_all(
    model: str = "claude-sonnet-4-20250514",
    db: PipelineDB | None = None,
) -> dict:
    """Analyze all verified indicators that haven't been analyzed yet.

    Returns:
        Dict with counts: {"analyzed": N, "skipped": N, "failed": N}
    """
    db = db or PipelineDB()
    verified = db.get_indicators_by_status("verified")

    stats = {"analyzed": 0, "skipped": 0, "failed": 0}

    for ind in verified:
        indicator_id = ind["id"]

        # Skip if already analyzed
        existing = db.get_analysis(indicator_id)
        if existing:
            stats["skipped"] += 1
            continue

        result = analyze_indicator(indicator_id, model=model, db=db)
        if result:
            stats["analyzed"] += 1
        else:
            stats["failed"] += 1

    logger.info(f"Analysis complete: {stats}")
    return stats


def get_indicators_by_role(db: PipelineDB | None = None) -> dict[str, list[dict]]:
    """Get all analyzed indicators grouped by role.

    Returns:
        Dict mapping role name to list of indicator info.
    """
    db = db or PipelineDB()
    indicators = db.get_analyzed_indicators()

    by_role: dict[str, list[dict]] = {
        "primary_signal": [],
        "confirmation": [],
        "market_filter": [],
        "exit_signal": [],
    }

    for ind in indicators:
        roles_str = ind.get("roles", "[]")
        try:
            roles = json.loads(roles_str)
        except json.JSONDecodeError:
            roles = []

        for role in roles:
            if role in by_role:
                by_role[role].append(ind)

    return by_role
