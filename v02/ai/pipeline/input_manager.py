"""Stage 1: Input Manager — Pine Script file detection and metadata management.

Scans the pine/ directory for .pine files, registers new ones in the DB,
and tracks conversion status.
"""

from pathlib import Path

from ai.pipeline.converter import file_hash, PINE_DIR, CONVERTED_DIR
from ai.pipeline.utils.db import PipelineDB
from ai.pipeline.utils.logger import get_logger

logger = get_logger("input_manager")


def _extract_title_from_source(source: str, filename: str) -> str:
    """Try to extract a title from Pine Script comments or use filename."""
    for line in source.split("\n")[:10]:
        line = line.strip()
        # // Title: ... or // @title ...
        if line.startswith("//") and any(kw in line.lower() for kw in ["title", "name"]):
            return line.lstrip("/").strip().split(":", 1)[-1].strip()
        # indicator("Title", ...) or strategy("Title", ...)
        if line.startswith(("indicator(", "strategy(")):
            import re
            match = re.search(r'["\'](.*?)["\']', line)
            if match:
                return match.group(1)
    return filename.replace("_", " ").replace("-", " ").title()


def scan_pine_directory(db: PipelineDB | None = None) -> dict:
    """Scan pine/ directory and register new or modified .pine files.

    Returns:
        Dict with counts: {"new": N, "modified": N, "unchanged": N}
    """
    db = db or PipelineDB()
    PINE_DIR.mkdir(parents=True, exist_ok=True)

    pine_files = list(PINE_DIR.glob("*.pine"))
    stats = {"new": 0, "modified": 0, "unchanged": 0}

    if not pine_files:
        logger.info("No .pine files found in pine/ directory")
        return stats

    for pine_path in pine_files:
        indicator_id = pine_path.stem
        current_hash = file_hash(pine_path)
        source = pine_path.read_text(encoding="utf-8", errors="replace")
        title = _extract_title_from_source(source, indicator_id)

        existing = db.get_indicator(indicator_id)

        if existing is None:
            # New file
            db.upsert_indicator({
                "id": indicator_id,
                "title": title,
                "source_file": str(pine_path.relative_to(PINE_DIR.parent.parent)),
                "source_code_hash": current_hash,
                "conversion_status": "pending",
            })
            stats["new"] += 1
            logger.info(f"New indicator: {indicator_id} ({title})")

        elif existing["source_code_hash"] != current_hash:
            # Modified file — reset to pending
            db.upsert_indicator({
                "id": indicator_id,
                "title": title,
                "source_file": str(pine_path.relative_to(PINE_DIR.parent.parent)),
                "source_code_hash": current_hash,
                "conversion_status": "pending",
            })
            stats["modified"] += 1
            logger.info(f"Modified indicator: {indicator_id} (hash changed → pending)")

        else:
            stats["unchanged"] += 1

    logger.info(
        f"Scan complete: {stats['new']} new, {stats['modified']} modified, "
        f"{stats['unchanged']} unchanged (total: {len(pine_files)} files)"
    )
    return stats


def get_status_report(db: PipelineDB | None = None) -> str:
    """Generate a status report of all indicators in the pipeline."""
    db = db or PipelineDB()
    indicators = db.get_all_indicators()

    if not indicators:
        return "No indicators registered. Place .pine files in indicators/pine/"

    # Count by status
    status_counts = {}
    for ind in indicators:
        s = ind["conversion_status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    lines = ["Pipeline Status Report", "=" * 50]
    lines.append(f"Total indicators: {len(indicators)}")
    for status, count in sorted(status_counts.items()):
        lines.append(f"  {status}: {count}")
    lines.append("")

    # Detail table
    lines.append(f"{'ID':<25} {'Title':<30} {'Status':<12} {'Added'}")
    lines.append("-" * 80)
    for ind in indicators:
        added = (ind.get("added_at") or "")[:10]
        lines.append(
            f"{ind['id']:<25} {ind['title'][:29]:<30} {ind['conversion_status']:<12} {added}"
        )

    return "\n".join(lines)
