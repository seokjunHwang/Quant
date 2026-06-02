"""24/7 스케줄러 — config.yml 의 trigger 들에 따라 토론 자동 실행.

Phase 6 에서 본격 가동. 현재는 골격만 제공 — 매수자가 cron/launchd/systemd
와 결합해 운영하는 것이 권장 방식.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import yaml

from runners.orchestrator import run_debate

log = logging.getLogger(__name__)


async def _run_once_for_each_ticker(config: dict) -> None:
    basic = config.get("basic", {})
    for ticker in basic.get("tickers_stock", []):
        try:
            await run_debate(config=config, ticker=ticker, asset_class="stock")
        except Exception as e:
            log.exception("토론 실패 %s: %s", ticker, e)
    for ticker in basic.get("tickers_crypto", []):
        try:
            await run_debate(config=config, ticker=ticker, asset_class="crypto")
        except Exception as e:
            log.exception("토론 실패 %s: %s", ticker, e)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = yaml.safe_load(Path("config.yml").read_text(encoding="utf-8"))
    log.info("스케줄러 시작 (간이 모드 — 트리거 1회 실행)")
    asyncio.run(_run_once_for_each_ticker(cfg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
