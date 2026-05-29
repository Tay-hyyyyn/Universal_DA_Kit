from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from log_writer import append_manual_log  # type: ignore  # noqa: E402
from manual_common import load_config, run_paths  # type: ignore  # noqa: E402
from manual_hypothesis import (  # type: ignore  # noqa: E402
    PAUSE_EXIT_CODE,
    default_hypotheses,
    evaluate_hypotheses,
    parse_hypothesis_answers,
    write_hypothesis_proposal_files,
    write_json,
)
from manual_state import refresh_run_state  # type: ignore  # noqa: E402


def propose(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    result = write_hypothesis_proposal_files(cfg, args.run_id, paths, auto_proceed=args.auto_proceed)
    append_manual_log(
        cfg,
        "02H hypothesis planning",
        "Create hypothesis registry and validation plan",
        [args.config],
        [str(paths["reports"] / "hypothesis_registry.json"), str(paths["reports"] / "hypothesis_validation_plan.csv")],
        checkpoint="Hypothesis approval before Stage 03",
        next_step="Build accepted hypothesis features in Stage 03.",
    )
    refresh_run_state(cfg, args.run_id)
    if result["pending"]:
        pending_md = paths["reports"] / "pending_hypothesis_checkpoint.md"
        print(pending_md.read_text(encoding="utf-8").strip())
        raise SystemExit(PAUSE_EXIT_CODE)
    print(f"[ok] Hypothesis planning files are ready: {paths['reports'] / 'hypothesis_registry.json'}")


def ingest(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    answers_path = paths["reports"] / "hypothesis_answers.md"
    if not answers_path.exists():
        raise FileNotFoundError(f"hypothesis_answers.md not found: {answers_path}")
    registry = parse_hypothesis_answers(answers_path.read_text(encoding="utf-8"), default_hypotheses(cfg), cfg)
    write_json(paths["reports"] / "hypothesis_registry.json", registry)
    for path in [
        paths["reports"] / "pending_hypothesis_checkpoint.json",
        paths["reports"] / "pending_hypothesis_checkpoint.md",
        paths["reports"] / "pending_hypothesis_checkpoint_stage_02H.json",
        paths["reports"] / "pending_hypothesis_checkpoint_stage_02H.md",
    ]:
        if path.exists() and not registry.get("compact_summary", {}).get("open_ids"):
            path.unlink()
    append_manual_log(
        cfg,
        "02H hypothesis ingest",
        "Ingest edited hypothesis answers into registry",
        [str(answers_path)],
        [str(paths["reports"] / "hypothesis_registry.json")],
        checkpoint="Stage 03 feature approval",
        next_step="Run feature builder.",
    )
    refresh_run_state(cfg, args.run_id)
    print(f"[ok] Hypothesis answers ingested: {paths['reports'] / 'hypothesis_registry.json'}")


def evaluate(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    result = evaluate_hypotheses(cfg, paths)
    append_manual_log(
        cfg,
        "05H hypothesis evaluation",
        "Evaluate accepted hypotheses after model training",
        [str(paths["reports"] / "hypothesis_registry.json"), str(paths["models"] / "metrics.csv")],
        [str(paths["reports"] / "hypothesis_validation_results.json"), str(paths["reports"] / "hypothesis_validation_results.md")],
        checkpoint="Stage 06/07 residual-to-action review",
        next_step="Review supported hypotheses and field actions.",
    )
    refresh_run_state(cfg, args.run_id)
    print(f"[ok] Hypothesis evaluation completed: {len(result.get('results', []))} hypotheses")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual hypothesis planner/evaluator.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("propose", help="Create hypothesis seed report, answers template, registry, and validation plan.")
    p.add_argument("--config", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--auto-proceed", action="store_true")
    p.set_defaults(func=propose)

    p = sub.add_parser("ingest", help="Parse edited hypothesis_answers.md into hypothesis_registry.json.")
    p.add_argument("--config", required=True)
    p.add_argument("--run-id", required=True)
    p.set_defaults(func=ingest)

    p = sub.add_parser("evaluate", help="Summarize hypothesis validation evidence after model training.")
    p.add_argument("--config", required=True)
    p.add_argument("--run-id", required=True)
    p.set_defaults(func=evaluate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
