from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from domain_checkpoint import (  # type: ignore  # noqa: E402
    answers_fingerprint,
    checkpoint_spec,
    guidance_markdown_v2,
    open_question_ids_from_answers,
    pending_checkpoint_paths,
    write_checkpoint_reference_files,
    write_json,
)
from manual_common import load_config, run_paths  # type: ignore  # noqa: E402
from manual_domain_expert import ingest_answers_file, write_action_items_files, write_questionnaire_files  # type: ignore  # noqa: E402
from manual_hypothesis import read_json as read_hypothesis_json  # type: ignore  # noqa: E402
from manual_hypothesis import write_hypothesis_proposal_files  # type: ignore  # noqa: E402


DOMAIN_STAGES = ("01", "03", "05", "07")


def materialize_domain_checkpoint(cfg: dict, run_id: str, paths: dict[str, Path], stage_before: str) -> dict:
    reports = paths["reports"]
    answers_path = reports / "domain_answers.md"
    spec = checkpoint_spec(stage_before)
    if str(spec.stage_before) == "07":
        try:
            write_action_items_files(cfg, paths)
        except Exception:
            pass
    reference_paths = write_checkpoint_reference_files(paths["base"], spec, answers_path)
    answers_md = answers_path.read_text(encoding="utf-8") if answers_path.exists() else ""
    open_qids = open_question_ids_from_answers(answers_md, spec.question_ids)
    pend = pending_checkpoint_paths(reports, spec)
    payload = {
        "checkpoint_id": spec.checkpoint_id,
        "stage_before": spec.stage_before,
        "title": spec.title,
        "required_question_ids": list(spec.question_ids),
        "open_question_ids": open_qids,
        "domain_answers_path": str(answers_path.resolve()),
        "core_refs": list(spec.core_refs),
        "extra_refs": list(spec.extra_refs),
        "reference_report_md": reference_paths.get("md"),
        "reference_report_pdf": reference_paths.get("pdf"),
        "stage_pending_json": str(pend["stage_json"].resolve()),
        "stage_pending_md": str(pend["stage_md"].resolve()),
        "answers_fingerprint": answers_fingerprint(answers_md, spec.question_ids),
        "materialized_for_review": True,
    }
    md = guidance_markdown_v2(paths["base"], spec, answers_path)
    write_json(pend["stage_json"], payload)
    pend["stage_md"].write_text(md, encoding="utf-8")
    return {
        "stage_before": stage_before,
        "checkpoint_id": spec.checkpoint_id,
        "pending_md": str(pend["stage_md"].resolve()),
        "answers_path": str(answers_path.resolve()),
        "open_question_ids": open_qids,
    }


def materialize_hypothesis_checkpoint(cfg: dict, run_id: str, paths: dict[str, Path]) -> dict:
    reports = paths["reports"]
    write_hypothesis_proposal_files(cfg, run_id, paths, auto_proceed=False)
    registry = read_hypothesis_json(reports / "hypothesis_registry.json", {"hypotheses": []})
    answers_path = reports / "hypothesis_answers.md"
    seed_report_path = reports / "hypothesis_seed_report.md"
    context_pack_path = reports / "hypothesis_context_pack.json"
    stage_pending_json = reports / "pending_hypothesis_checkpoint_stage_02H.json"
    stage_pending_md = reports / "pending_hypothesis_checkpoint_stage_02H.md"
    generic_json = reports / "pending_hypothesis_checkpoint.json"
    generic_md = reports / "pending_hypothesis_checkpoint.md"
    hypotheses = registry.get("hypotheses", []) if isinstance(registry, dict) else []
    status_counts: dict[str, int] = {}
    open_ids: list[str] = []
    for item in hypotheses:
        status = str(item.get("status") or "open")
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "open":
            open_ids.append(str(item.get("hypothesis_id") or ""))
    payload = {
        "checkpoint_id": "CP-02H-HYPOTHESIS",
        "stage_before": "03",
        "title": "02H hypothesis review",
        "hypothesis_answers_path": str(answers_path.resolve()),
        "hypothesis_seed_report_path": str(seed_report_path.resolve()),
        "hypothesis_context_pack_path": str(context_pack_path.resolve()),
        "reference_report_pdf": str((reports / "pdf" / "checkpoint_reference_stage_02H.pdf").resolve()),
        "stage_pending_json": str(stage_pending_json.resolve()),
        "stage_pending_md": str(stage_pending_md.resolve()),
        "open_hypothesis_ids": open_ids,
        "status_counts": status_counts,
        "materialized_for_review": True,
    }
    lines = [
        "# 02H Hypothesis Checkpoint",
        "",
        f"- hypothesis_answers: `{answers_path.resolve()}`",
        f"- seed_report: `{seed_report_path.resolve()}`",
        f"- context_pack: `{context_pack_path.resolve()}`",
        f"- open_hypothesis_ids: `{', '.join(open_ids) if open_ids else 'none'}`",
        f"- status_counts: `{json.dumps(status_counts, ensure_ascii=False)}`",
        "",
        "## Status Glossary",
        "",
        "- `open`: 아직 판단하지 않음",
        "- `answered`: 의견은 적었지만 채택 보류",
        "- `accepted`: 이번 run에서 반영/검증",
        "- `deferred`: 이번 run에서는 기본 추천을 따름",
        "- `auto-proceed`: 시스템이 열린 가설을 자동으로 `deferred` 처리하는 실행 모드",
        "",
        "`hypothesis_answers.md`에서 각 가설의 `status`를 `answered`, `accepted`, `deferred` 중 하나로 바꾸세요.",
        "이전에 auto-proceed로 자동 deferred 된 항목도 이번에는 다시 읽고 의도적으로 상태를 확정하세요.",
        "",
    ]
    write_json(generic_json, payload)
    generic_md.write_text("\n".join(lines), encoding="utf-8")
    write_json(stage_pending_json, payload)
    stage_pending_md.write_text("\n".join(lines), encoding="utf-8")
    return {
        "stage_before": "02H",
        "checkpoint_id": "CP-02H-HYPOTHESIS",
        "pending_md": str(stage_pending_md.resolve()),
        "answers_path": str(answers_path.resolve()),
        "open_question_ids": open_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize all checkpoint markdown files for an existing Manual run.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    write_questionnaire_files(cfg, args.run_id, paths, overwrite_answers_template=False)
    ingest_answers_file(cfg, args.run_id, paths, paths["reports"] / "domain_answers.md")

    results: list[dict] = []
    for stage_before in DOMAIN_STAGES:
        results.append(materialize_domain_checkpoint(cfg, args.run_id, paths, stage_before))
    results.insert(1, materialize_hypothesis_checkpoint(cfg, args.run_id, paths))

    queue_json = paths["reports"] / "checkpoint_queue.json"
    queue_md = paths["reports"] / "checkpoint_queue.md"
    first_open_seen = False
    enriched_results: list[dict] = []
    for item in results:
        open_ids = item.get("open_question_ids") or []
        review_state = "done"
        if open_ids:
            review_state = "current" if not first_open_seen else "blocked"
            first_open_seen = True
        enriched = dict(item)
        enriched["review_state"] = review_state
        enriched_results.append(enriched)
    write_json(queue_json, {"run_id": args.run_id, "checkpoints": enriched_results})
    queue_lines = [
        "# 체크포인트 큐",
        "",
        "이 파일을 먼저 열고 위에서부터 처리하면 됩니다. `current`인 항목이 지금 사용자가 확인할 체크포인트입니다.",
        "",
        "## Queue State Glossary",
        "",
        "- `current`: 지금 확인해야 하는 체크포인트",
        "- `done`: 필수 질문이 모두 답변/채택/보류되어 통과 가능한 체크포인트",
        "- `blocked`: 앞선 체크포인트가 끝난 뒤 확인할 예정인 체크포인트",
        "",
        "## Status Glossary",
        "",
        "- `open`: 아직 판단하지 않음",
        "- `answered`: 의견은 적었지만 이번 run의 강한 규칙으로 쓰지는 않음",
        "- `accepted`: 이번 run에서 반영하거나 검증",
        "- `deferred`: 이번 run에서는 기본 추천을 따름",
        "- `auto-proceed`: 시스템이 열린 항목을 자동으로 `deferred` 처리하는 실행 모드",
        "",
    ]
    for item in enriched_results:
        queue_lines += [
            f"## {item['stage_before']} | {item['checkpoint_id']}",
            f"- review_state: `{item['review_state']}`",
            f"- pending_md: `{item['pending_md']}`",
            f"- answers_path: `{item['answers_path']}`",
            f"- open_ids: `{', '.join(item.get('open_question_ids') or []) if item.get('open_question_ids') else 'none'}`",
            "",
        ]
    queue_md.write_text("\n".join(queue_lines), encoding="utf-8")
    print(f"[ok] Materialized checkpoint files: {queue_md}")


if __name__ == "__main__":
    main()
