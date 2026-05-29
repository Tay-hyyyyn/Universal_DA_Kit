from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from domain_checkpoint import (  # type: ignore  # noqa: E402
    checkpoint_is_cleared,
    checkpoint_spec,
    clear_pending_checkpoint,
    defer_question_sections,
    answer_statuses,
    answers_fingerprint,
    guidance_markdown_v2,
    open_question_ids_from_answers,
    pending_checkpoint_paths,
    read_json,
    record_cleared_checkpoint,
    record_deferred_checkpoint,
    write_checkpoint_reference_files,
    write_json,
)
from manual_common import append_decision, load_config, run_paths  # type: ignore  # noqa: E402
from manual_domain_expert import ingest_answers_file, write_action_items_files  # type: ignore  # noqa: E402


PAUSE_EXIT_CODE = 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Domain checkpoint gate: pause for user input or defer to defaults.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--stage-before",
        required=True,
        help="Checkpoint key: one of 01,03,05,07 (meaning: right before that stage).",
    )
    parser.add_argument("--auto-proceed", action="store_true", help="If set, defer unanswered questions and continue.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    reports = paths["reports"]
    answers_path = reports / "domain_answers.md"

    spec = checkpoint_spec(str(args.stage_before))
    pend = pending_checkpoint_paths(reports, spec)
    pending = read_json(pend["json"], {})
    pending_same_checkpoint = isinstance(pending, dict) and pending.get("checkpoint_id") == spec.checkpoint_id
    answers_md = answers_path.read_text(encoding="utf-8") if answers_path.exists() else ""
    open_qids = open_question_ids_from_answers(answers_md, spec.question_ids)
    current_fp = answers_fingerprint(answers_md, spec.question_ids)

    if open_qids and args.auto_proceed:
        updated = defer_question_sections(answers_md, open_qids)
        answers_path.write_text(updated, encoding="utf-8")

    # Always ingest to keep domain_context_pack.json synced with current answers.md,
    # and so later stages can use compact_summary even if the user deferred.
    pack = ingest_answers_file(cfg, args.run_id, paths, answers_path)
    if str(spec.stage_before) == "07":
        # Provide a draft action_items.md even if the user defers, so the checkpoint has a concrete core reference.
        try:
            write_action_items_files(cfg, paths)
        except Exception:
            # Non-blocking: checkpoint guidance should still be generated.
            pass

    # Record the checkpoint deferral.
    # - auto_proceed: we deferred open questions right now.
    # - user_deferred_to_default: the agent/user already marked them deferred in domain_answers.md.
    deferred_qids: list[str] = []
    for item in pack.get("cards", []) if isinstance(pack, dict) else []:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("question_id") or "")
        if qid in spec.question_ids and str(item.get("status")) == "deferred":
            deferred_qids.append(qid)
    if deferred_qids:
        reason = "auto_proceed" if (open_qids and args.auto_proceed) else "user_deferred_to_default"
        pack = record_deferred_checkpoint(pack, spec, sorted(set(deferred_qids)), reason=reason)
        write_json(reports / "domain_context_pack.json", pack)
        append_decision(
            cfg,
            args.run_id,
            f"{spec.stage_before}_domain_checkpoint",
            "domain_checkpoint_deferral",
            ", ".join(sorted(set(deferred_qids))),
            "answer, accept, or intentionally defer every required question",
            reason,
            "Deferred questions are kept as no-effect domain context and should be revisited before hard operational conclusions.",
        )

    if args.auto_proceed:
        pack = record_cleared_checkpoint(pack, spec, reason="auto_proceed")
        write_json(reports / "domain_context_pack.json", pack)
        append_decision(
            cfg,
            args.run_id,
            f"{spec.stage_before}_domain_checkpoint",
            "domain_checkpoint_clear",
            "auto_proceed",
            "manual review before advancing",
            f"{spec.checkpoint_id} was cleared by auto-proceed.",
            "The run can continue, but unanswered questions remain deferred-to-default rather than accepted domain rules.",
        )
        clear_pending_checkpoint(reports, spec)
        print(f"[ok] Domain checkpoint auto-cleared: {spec.checkpoint_id} (stage_before={spec.stage_before})")
        return

    # If this checkpoint was already presented and the user has now filled/confirmed it, clear it.
    answers_md2 = answers_path.read_text(encoding="utf-8") if answers_path.exists() else ""
    open_after = open_question_ids_from_answers(answers_md2, spec.question_ids)
    statuses = answer_statuses(answers_md2, spec.question_ids)
    prior_fp = str(pending.get("answers_fingerprint", "")) if isinstance(pending, dict) else ""
    user_confirmed = bool(prior_fp and answers_fingerprint(answers_md2, spec.question_ids) != prior_fp) or any(
        status in {"answered", "accepted", "deferred"} for status in statuses.values()
    )
    if pending_same_checkpoint and not open_after and user_confirmed:
        pack = record_cleared_checkpoint(pack, spec, reason="user_confirmed_after_checkpoint")
        write_json(reports / "domain_context_pack.json", pack)
        status_summary = ", ".join(f"{qid}:{statuses.get(qid, 'open')}" for qid in spec.question_ids)
        append_decision(
            cfg,
            args.run_id,
            f"{spec.stage_before}_domain_checkpoint",
            "domain_checkpoint_review",
            status_summary,
            "all required questions reviewed as answered, accepted, or deferred",
            f"{spec.checkpoint_id} was confirmed after user review.",
            "User checkpoint decisions are now traceable in decision_log.json and available to later reporting.",
        )
        clear_pending_checkpoint(reports, spec)
        print(f"[ok] Domain checkpoint cleared: {spec.checkpoint_id} (stage_before={spec.stage_before})")
        return

    if checkpoint_is_cleared(pack, spec):
        clear_pending_checkpoint(reports, spec)
        print(f"[ok] Domain checkpoint already cleared: {spec.checkpoint_id} (stage_before={spec.stage_before})")
        return

    # First encounter of each checkpoint must pause even if answer fields already contain text.
    # This gives the user a chance to review stage-specific reference materials before accepting.
    reference_paths = write_checkpoint_reference_files(paths["base"], spec, answers_path)
    md = guidance_markdown_v2(paths["base"], spec, answers_path)
    write_json(
        pend["json"],
        {
            "checkpoint_id": spec.checkpoint_id,
            "stage_before": spec.stage_before,
            "title": spec.title,
            "required_question_ids": list(spec.question_ids),
            "open_question_ids": open_after,
            "domain_answers_path": str(answers_path.resolve()),
            "core_refs": list(spec.core_refs),
            "extra_refs": list(spec.extra_refs),
            "reference_report_md": reference_paths.get("md"),
            "reference_report_pdf": reference_paths.get("pdf"),
            "stage_pending_json": str(pend["stage_json"].resolve()),
            "stage_pending_md": str(pend["stage_md"].resolve()),
            "answers_fingerprint": answers_fingerprint(answers_md2, spec.question_ids),
            "created_at": pack.get("created_at"),
        },
    )
    (pend["md"]).write_text(md, encoding="utf-8")
    write_json(pend["stage_json"], read_json(pend["json"], {}))
    (pend["stage_md"]).write_text(md, encoding="utf-8")
    print(md.strip())
    raise SystemExit(PAUSE_EXIT_CODE)


if __name__ == "__main__":
    main()
