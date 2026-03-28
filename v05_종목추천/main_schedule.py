from __future__ import annotations
"""
v05 스케줄 실행기.
매일 06:30 KST (평일) 에 main.py 파이프라인을 자동 실행.

실행:
  python main_schedule.py
  python main_schedule.py --market kr
  python main_schedule.py --market us --from step3 --dry-run
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta

import pytz

KST = pytz.timezone("Asia/Seoul")
RUN_HOUR = 6
RUN_MINUTE = 30


def next_run_time() -> datetime:
    """다음 실행 시각 계산 (평일 06:30 KST)."""
    now = datetime.now(KST)
    target = now.replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)

    # 오늘 시각이 이미 지났으면 다음날로
    if now >= target:
        target += timedelta(days=1)

    # 주말이면 월요일로
    while target.weekday() >= 5:  # 5=토, 6=일
        target += timedelta(days=1)

    return target


def run_pipeline(args) -> None:
    """main.py 호출 (main.py 옵션 그대로 전달)."""
    cmd = [sys.executable, "main.py", "--market", args.market]
    if args.from_step != "step1":
        cmd += ["--from", args.from_step]
    if args.dry_run:
        cmd += ["--dry-run"]
    print(f"\n[{datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} KST] 파이프라인 시작 → {' '.join(cmd)}")
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(description="v05 스케줄 실행기")
    parser.add_argument("--market", choices=["kr", "us", "all"], default="all")
    parser.add_argument("--from", dest="from_step", default="step1",
                        choices=["step1", "step2", "step3", "step4", "step5"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 50)
    print("  v05 스케줄러 시작")
    print(f"  실행 시각: 매일 {RUN_HOUR:02d}:{RUN_MINUTE:02d} KST (평일)")
    print(f"  옵션: market={args.market} / from={args.from_step}"
          + (" / dry-run" if args.dry_run else ""))
    print("  종료: Ctrl+C")
    print("=" * 50)

    while True:
        target = next_run_time()
        now = datetime.now(KST)
        wait_sec = (target - now).total_seconds()

        print(f"\n  다음 실행: {target.strftime('%Y-%m-%d %H:%M')} KST "
              f"({wait_sec/3600:.1f}시간 후)")

        try:
            time.sleep(wait_sec)
        except KeyboardInterrupt:
            print("\n  스케줄러 종료.")
            break

        run_pipeline(args)


if __name__ == "__main__":
    main()
