"""4-step 하네스 엔지니어링 라운드 컨트롤러.

   파이프라인: Architect → Builder → Gatekeeper → Memory
   라운드: Gatekeeper가 fail 내면 룰 갱신 후 다음 라운드로."""
import argparse
import json
import uuid
from pathlib import Path

import yaml

from core import make_backend
from agents import Architect, Builder, Gatekeeper, Memory
from sandbox.docker_runner import DockerSandbox


def load_config(path="config/settings.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text())


def run_round(task: str, cfg: dict, task_id: str, round_no: int):
    backend = make_backend(cfg["backend"], cfg["model"])
    sandbox = DockerSandbox(**cfg["sandbox"])

    architect = Architect(backend)
    builder = Builder(backend)
    gatekeeper = Gatekeeper(backend, sandbox=sandbox)
    memory = Memory(backend, rule_path=cfg["paths"]["rules"])

    rules = Path(cfg["paths"]["rules"]).read_text()
    task_dir = Path(cfg["paths"]["tasks"]) / task_id / f"round_{round_no:02d}"
    task_dir.mkdir(parents=True, exist_ok=True)

    # Step 1
    blueprint = architect.run(task=task, rules=rules)
    (task_dir / "01_blueprint.json").write_text(json.dumps(blueprint, indent=2, ensure_ascii=False))

    # Step 2
    artifact = builder.run(blueprint)
    (task_dir / "02_artifact.txt").write_text(artifact)

    # Step 3
    review = gatekeeper.run(blueprint, artifact)
    (task_dir / "03_review.json").write_text(json.dumps(review, indent=2, ensure_ascii=False))

    # Step 4
    lesson = memory.run(review, failure_log=[])
    (task_dir / "04_lesson.md").write_text(lesson)

    return review


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True)
    p.add_argument("--backend", choices=["cli", "api"], default=None)
    p.add_argument("--rounds", type=int, default=None)
    args = p.parse_args()

    cfg = load_config()
    if args.backend:
        cfg["backend"] = args.backend
    if args.rounds:
        cfg["max_rounds"] = args.rounds

    task_id = uuid.uuid4().hex[:8]
    print(f"[task_id] {task_id}  backend={cfg['backend']}  rounds={cfg['max_rounds']}")

    for r in range(1, cfg["max_rounds"] + 1):
        print(f"\n=== Round {r} ===")
        review = run_round(args.task, cfg, task_id, r)
        # TODO: review.passed True면 종료
        # TODO: False면 룰 반영 후 다음 라운드로


if __name__ == "__main__":
    main()
