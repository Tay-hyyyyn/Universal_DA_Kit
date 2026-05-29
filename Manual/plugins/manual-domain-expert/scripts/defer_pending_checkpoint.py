from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from domain_checkpoint import (  # type: ignore  # noqa: E402
    CHECKPOINTS,
    clear_pending_checkpoint,
    defer_question_sections,
    pending_checkpoint_paths,
    read_json,
    record_deferred_checkpoint,
    write_json,
)
from manual_common import load_config, run_paths  # type: ignore  # noqa: E402
from manual_domain_expert import ingest_answers_file, write_action_items_files  # type: ignore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark the current pending checkpoint as deferred-to-default and continue.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    reports = paths["reports"]
    pending = read_json(reports / "pending_checkpoint.json", {})
    if not isinstance(pending, dict) or not pending.get("stage_before"):
        print("[skip] No pending checkpoint found.")
        return

    stage_before = str(pending.get("stage_before"))
    spec = CHECKPOINTS.get(stage_before)
    if not spec:
        raise ValueError(f"Unknown pending checkpoint stage_before={stage_before}")

    open_qids = pending.get("open_question_ids") or pending.get("required_question_ids") or []
    open_qids = [str(x) for x in open_qids if str(x)]
    answers_path = reports / "domain_answers.md"
    answers_md = answers_path.read_text(encoding="utf-8") if answers_path.exists() else ""
    answers_path.write_text(defer_question_sections(answers_md, open_qids), encoding="utf-8")

    pack = ingest_answers_file(cfg, args.run_id, paths, answers_path)
    pack = record_deferred_checkpoint(pack, spec, sorted(set(open_qids)), reason="user_deferred_to_default")
    write_json(reports / "domain_context_pack.json", pack)

    if stage_before == "07":
        try:
            write_action_items_files(cfg, paths)
        except Exception:
            pass

    clear_pending_checkpoint(reports)
    print(f"[ok] Deferred pending checkpoint and updated pack: {spec.checkpoint_id}")


if __name__ == "__main__":
    main()

