"""CLI 진입점.

사용 예:
    python -m runners.cli debate --ticker NVDA
    python -m runners.cli debate --ticker BTC --asset-class crypto
    python -m runners.cli list --ticker NVDA
    python -m runners.cli show <run_id>
    python -m runners.cli debate --ticker NVDA --mock   # 빠른 mock 테스트
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import yaml

from runners.orchestrator import run_debate
from storage import Repository

log = logging.getLogger(__name__)


def load_config(path: str = "config.yml", mock: bool = False) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if mock:
        cfg.setdefault("runner", {})["type"] = "mock"
    return cfg


async def _cmd_debate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config, mock=args.mock)
    if args.rounds:
        cfg.setdefault("debate", {})["max_rounds"] = args.rounds

    asset_class = args.asset_class
    if asset_class == "auto":
        asset_class = "crypto" if args.ticker.upper() in {"BTC", "ETH", "SOL"} else "stock"

    result = await run_debate(
        config=cfg, ticker=args.ticker.upper(),
        asset_class=asset_class, event_type=args.event,
    )
    print(f"\n✔ 저장: {result.saved_path}")
    print(f"  run_id: {result.run_id}")
    print(f"  turns:  {len(result.transcript['turns'])}")
    print(f"  cost:   ${result.transcript['total_cost_usd']:.4f}")
    print(f"  stop:   {result.transcript['final_report']['stop_reason']}")
    print(f"\n--- 최종 요약 ---\n{result.transcript['final_report']['summary']}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    repo = Repository.from_config(cfg)
    rows = repo.list_runs(ticker=args.ticker, since=args.since)
    if not rows:
        print("(no runs)")
        return 0
    for r in rows:
        print(f"{r['started_at']}  {r['ticker']:<6}  "
              f"{(r.get('stop_reason') or '-'):<12}  ${r.get('total_cost_usd', 0):.4f}  {r['run_id']}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    repo = Repository.from_config(cfg)
    data = repo.load(args.run_id)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="debate", description="멀티 AI 토론 트레이딩 쇼케이스")
    p.add_argument("--config", default="config.yml")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("debate", help="1회 토론 실행")
    d.add_argument("--ticker", required=True)
    d.add_argument("--asset-class", default="auto", choices=["auto", "stock", "crypto"])
    d.add_argument("--rounds", type=int, default=None, help="config 의 max_rounds 를 덮어씀")
    d.add_argument("--event", default="manual")
    d.add_argument("--mock", action="store_true", help="LLM 호출을 mock 으로 (claude 미호출)")
    d.set_defaults(handler=lambda a: asyncio.run(_cmd_debate(a)))

    ls = sub.add_parser("list", help="저장된 토론 목록")
    ls.add_argument("--ticker", default=None)
    ls.add_argument("--since", default=None)
    ls.set_defaults(handler=_cmd_list)

    sh = sub.add_parser("show", help="특정 run_id 의 트랜스크립트 출력")
    sh.add_argument("run_id")
    sh.set_defaults(handler=_cmd_show)

    args = p.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
