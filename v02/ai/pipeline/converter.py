"""Stage 2: Pine Script → Python converter using Claude API.

Semantic conversion: Claude understands the Pine Script logic and generates
equivalent Python code using pandas-ta, rather than mechanical parsing.
"""

import hashlib
import importlib.util
import re
import types
from datetime import datetime
from pathlib import Path

from ai.pipeline.utils.logger import get_logger

logger = get_logger("converter")

BASE_DIR = Path(__file__).resolve().parent.parent
PINE_DIR = BASE_DIR / "indicators" / "pine"
CONVERTED_DIR = BASE_DIR / "indicators" / "converted"

CONVERSION_PROMPT = """다음 Pine Script 지표를 분석하고 Python으로 변환하라.

[요구사항]
1. pandas-ta 라이브러리를 사용하여 동일한 지표를 계산하라.
2. 매수/매도 시그널을 생성하는 함수를 구현하라.
3. 함수 시그니처를 정확히 따르라:
   def generate_signals(df: pd.DataFrame, **params) -> pd.DataFrame
   - 입력: OHLCV DataFrame (columns: open, high, low, close, volume, DatetimeIndex)
   - 출력: 원본 DataFrame에 'signal' 컬럼 추가 (1=매수, -1=매도, 0=홀드)
4. Pine Script의 input() 파라미터는 함수의 keyword argument로 변환하라.
5. 핵심 매매 로직만 변환하고, 시각화(plot, bgcolor, barcolor) 관련 코드는 무시하라.
6. alertcondition이나 strategy.entry/exit가 있으면 그것을 기반으로 시그널을 생성하라.
7. NaN 처리를 신경써라 — 지표 계산 초기 구간의 NaN은 signal=0으로 처리.

[출력 형식]
반드시 아래 형식의 Python 코드만 출력하라. 설명이나 마크다운 없이 순수 코드만:

```python
import pandas as pd
import pandas_ta as ta
import numpy as np

METADATA = {
    "name": "지표 이름",
    "category": "momentum|trend|volatility|volume|pattern|composite",
    "default_params": {"param1": value1, "param2": value2},
    "description": "지표 핵심 로직 한 줄 설명"
}

def generate_signals(df: pd.DataFrame, param1=value1, param2=value2) -> pd.DataFrame:
    result = df.copy()
    # 지표 계산 로직
    # 시그널 생성 로직
    result['signal'] = 0  # 기본값
    # 매수/매도 조건 설정
    return result
```

[Pine Script]
{source_code}
"""


def file_hash(filepath: Path) -> str:
    """Calculate MD5 hash of file contents."""
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def extract_python_code(response_text: str) -> str:
    """Extract Python code from Claude's response."""
    # Try to find code block
    pattern = r"```python\s*\n(.*?)```"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # If no code block, check if the response itself is valid Python
    if "def generate_signals" in response_text:
        # Remove any markdown artifacts
        lines = response_text.split("\n")
        code_lines = [l for l in lines if not l.startswith("```")]
        return "\n".join(code_lines).strip()

    raise ValueError("Could not extract Python code from Claude response")


def validate_converted_code(code: str) -> list[str]:
    """Validate that converted code has required structure. Returns list of issues."""
    issues = []

    if "def generate_signals" not in code:
        issues.append("Missing generate_signals() function")

    if "METADATA" not in code:
        issues.append("Missing METADATA dict")

    if "import pandas" not in code:
        issues.append("Missing pandas import")

    if "'signal'" not in code and '"signal"' not in code:
        issues.append("No 'signal' column assignment found")

    # Try to compile
    try:
        compile(code, "<converted>", "exec")
    except SyntaxError as e:
        issues.append(f"Syntax error: {e}")

    return issues


def convert_pine_script(
    pine_path: Path,
    model: str = "claude-sonnet-4-20250514",
    force: bool = False,
) -> Path | None:
    """Convert a Pine Script file to Python using Claude API.

    Args:
        pine_path: Path to .pine file.
        model: Claude model to use.
        force: Force reconversion even if cache exists.

    Returns:
        Path to converted .py file, or None if conversion failed.
    """
    import anthropic

    pine_path = Path(pine_path)
    if not pine_path.exists():
        logger.error(f"Pine Script not found: {pine_path}")
        return None

    # Determine output path
    stem = pine_path.stem
    out_path = CONVERTED_DIR / f"{stem}.py"

    # Check cache: skip if hash matches and not forced
    if not force and out_path.exists():
        # Read existing file header for hash
        existing_code = out_path.read_text(encoding="utf-8")
        if f"source_hash: {file_hash(pine_path)}" in existing_code:
            logger.info(f"Cache hit (hash match): {stem}.py — skipping conversion")
            return out_path

    # Read Pine Script
    source_code = pine_path.read_text(encoding="utf-8")
    logger.info(f"Converting: {pine_path.name} ({len(source_code)} chars)")

    # Call Claude API
    prompt = CONVERSION_PROMPT.replace("{source_code}", source_code)

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text

    # Extract and validate code
    try:
        code = extract_python_code(response_text)
    except ValueError as e:
        logger.error(f"Failed to extract code for {stem}: {e}")
        return None

    issues = validate_converted_code(code)
    if issues:
        logger.warning(f"Validation issues for {stem}: {issues}")
        # Still save if it compiles, just warn
        if any("Syntax error" in i for i in issues):
            logger.error(f"Conversion failed for {stem} — syntax error")
            return None

    # Add header with metadata
    header = f'''"""
Auto-converted from Pine Script: {pine_path.name}
Converted at: {datetime.now().isoformat()}
Model: {model}
source_hash: {file_hash(pine_path)}
Verification status: pending
"""
'''
    final_code = header + code

    # Save
    CONVERTED_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(final_code, encoding="utf-8")
    logger.info(f"Saved: {out_path.name}")

    return out_path


def load_converted_module(indicator_id: str) -> types.ModuleType | None:
    """Dynamically load a converted Python module.

    Args:
        indicator_id: The indicator name (filename without extension).

    Returns:
        Module with generate_signals() and METADATA, or None.
    """
    py_path = CONVERTED_DIR / f"{indicator_id}.py"
    if not py_path.exists():
        logger.error(f"Converted module not found: {py_path}")
        return None

    spec = importlib.util.spec_from_file_location(
        f"converted.{indicator_id}", str(py_path)
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.error(f"Failed to load {indicator_id}: {e}")
        return None

    # Validate
    if not hasattr(module, "generate_signals"):
        logger.error(f"Module {indicator_id} missing generate_signals()")
        return None

    return module


def convert_all(model: str = "claude-sonnet-4-20250514", force: bool = False) -> dict:
    """Convert all unconverted .pine files in the pine directory.

    Returns:
        Dict with counts: {"converted": N, "skipped": N, "failed": N}
    """
    PINE_DIR.mkdir(parents=True, exist_ok=True)
    pine_files = list(PINE_DIR.glob("*.pine"))

    if not pine_files:
        logger.info("No .pine files found in pine/ directory")
        return {"converted": 0, "skipped": 0, "failed": 0}

    stats = {"converted": 0, "skipped": 0, "failed": 0}

    for pine_path in pine_files:
        result = convert_pine_script(pine_path, model=model, force=force)
        if result:
            stats["converted"] += 1
        else:
            stats["failed"] += 1

    logger.info(f"Conversion complete: {stats}")
    return stats
