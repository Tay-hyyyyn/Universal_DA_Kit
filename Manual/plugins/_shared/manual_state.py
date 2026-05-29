from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


STAGE_ORDER = ["00P", "00", "01", "02", "02H", "03", "04", "05", "05H", "06", "07"]
STAGE_LABELS = {
    "00P": "Raw intake",
    "00": "Data review",
    "01": "Environment check",
    "02": "Diagnosis",
    "02H": "Hypothesis planning",
    "03": "Feature build",
    "04": "Validation split",
    "05": "Model training",
    "05H": "Hypothesis evaluation",
    "06": "Submission",
    "07": "Report",
}
STAGE_ARTIFACTS = {
    "00P": ["reports/stage_00P_report_payload.json", "reports/raw_file_profile.json", "reports/table_detection_report.md"],
    "00": ["reports/stage_00_report_payload.json", "reports/dataset_review.md"],
    "01": ["reports/stage_01_report_payload.json", "reports/env_check.md"],
    "02": ["reports/stage_02_report_payload.json", "reports/diagnosis_report.md"],
    "02H": ["reports/stage_02H_report_payload.json", "reports/hypothesis_registry.json", "reports/hypothesis_validation_plan.csv"],
    "03": ["reports/stage_03_report_payload.json", "data/processed/feature_manifest.json", "data/processed/feature_build_report.md"],
    "04": ["reports/stage_04_report_payload.json", "data/folds/sample15_fold_summary.json", "data/folds/sample15_fold_report.md"],
    "05": ["reports/stage_05_report_payload.json", "artifacts/models/model_registry.json", "artifacts/models/metrics.csv"],
    "05H": ["reports/stage_05H_report_payload.json", "reports/hypothesis_validation_results.json"],
    "06": ["reports/stage_06_report_payload.json", "submissions/submission.csv", "submissions/postprocess_choices.json"],
    "07": ["reports/pdf/analysis_report_integrated.pdf"],
}
STAGE_COMMANDS = {
    "00P": "Manual/plugins/manual-00-raw-intake/scripts/raw_intake.py",
    "00": "Manual/plugins/manual-00-data-reviewer/scripts/review_data.py",
    "01": "Manual/plugins/manual-01-env-checker/scripts/check_env.py",
    "02": "Manual/plugins/manual-02-profiler-diagnoser/scripts/diagnose_data.py",
    "02H": "Manual/plugins/manual-hypothesis-planner/scripts/hypothesis_planner.py propose",
    "03": "Manual/plugins/manual-03-feature-builder/scripts/build_features.py",
    "04": "Manual/plugins/manual-04-validation-splitter/scripts/make_folds.py",
    "05": "Manual/plugins/manual-05-model-trainer/scripts/train_model.py",
    "05H": "Manual/plugins/manual-hypothesis-planner/scripts/hypothesis_planner.py evaluate",
    "06": "Manual/plugins/manual-06-submission-maker/scripts/make_submission.py",
    "07": "Manual/plugins/manual-07-report-writer/scripts/write_reports.py",
}


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_project_path(cfg: dict[str, Any], value: str | None) -> Path | None:
    if not value:
        return None
    base = Path(cfg.get("_project_root", ".")).resolve()
    raw = Path(value)
    return raw if raw.is_absolute() else (base / raw).resolve()


def output_root(cfg: dict[str, Any]) -> Path:
    return resolve_project_path(cfg, cfg.get("output_root", "Manual/runs")) or Path(cfg.get("_project_root", ".")).resolve() / "Manual" / "runs"


def analysis_root(cfg: dict[str, Any]) -> Path:
    root = output_root(cfg)
    return root.parent if root.name.lower() == "runs" else root


def run_base(cfg: dict[str, Any], run_id: str) -> Path:
    return ensure_dir(output_root(cfg) / run_id)


def run_state_path(cfg: dict[str, Any], run_id: str) -> Path:
    return run_base(cfg, run_id) / "run_state.json"


def summary_path(cfg: dict[str, Any], run_id: str) -> Path:
    return run_base(cfg, run_id) / "summary.json"


def progress_path(cfg: dict[str, Any], run_id: str) -> Path:
    return run_base(cfg, run_id) / "progress.md"


def run_index_path(cfg: dict[str, Any], run_id: str) -> Path:
    return run_base(cfg, run_id) / "run_index.md"


def artifact_index_path(cfg: dict[str, Any], run_id: str) -> Path:
    return run_base(cfg, run_id) / "artifact_index.json"


def active_run_path(cfg: dict[str, Any]) -> Path:
    return analysis_root(cfg) / "state" / "active_run.json"


def effective_stage_order(cfg: dict[str, Any]) -> list[str]:
    order = list(STAGE_ORDER)
    raw_cfg = cfg.get("raw_intake") or {}
    if not bool(raw_cfg.get("enabled")):
        order = [stage for stage in order if stage != "00P"]
    return order


def infer_completed_stages(base: Path, cfg: dict[str, Any]) -> list[str]:
    completed: list[str] = []
    for stage in effective_stage_order(cfg):
        required = STAGE_ARTIFACTS[stage]
        if all((base / rel).exists() for rel in required):
            completed.append(stage)
        else:
            break
    return completed


def detect_artifact_index(base: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for stage, rel_paths in STAGE_ARTIFACTS.items():
        existing = [rel for rel in rel_paths if (base / rel).exists()]
        if existing:
            found[stage] = existing
    return found


def detect_artifact_records(base: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        for rel in STAGE_ARTIFACTS[stage]:
            path = base / rel
            if not path.exists():
                continue
            stat = path.stat()
            records.append(
                {
                    "stage": stage,
                    "path": rel,
                    "size_bytes": int(stat.st_size),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "read_priority": "high" if stage in {"00", "02", "02H", "05H", "07"} else "medium",
                }
            )
    return records


def next_stage_from_completed(completed: list[str], cfg: dict[str, Any]) -> str | None:
    for stage in effective_stage_order(cfg):
        if stage not in completed:
            return stage
    return None


def recommended_next_command(cfg: dict[str, Any], run_id: str, stage: str | None) -> str:
    if not stage:
        return "No next command. The run looks complete."
    config_path = f"\"{str(cfg.get('_config_path', '<config_path>'))}\""
    script = STAGE_COMMANDS[stage]
    if stage == "04":
        return f".\\.venv\\Scripts\\python.exe {script} --config {config_path} --run-id {run_id} --seed 42"
    if stage == "05":
        return f".\\.venv\\Scripts\\python.exe {script} --config {config_path} --run-id {run_id} --target-mode auto --explain-models ridge,surrogate --tuning-trials 8 --seed 42 --n-jobs 1"
    if stage == "06":
        return f".\\.venv\\Scripts\\python.exe {script} --config {config_path} --run-id {run_id} --ensemble-method weighted --upper-clip auto"
    if stage == "07":
        return f".\\.venv\\Scripts\\python.exe {script} --config {config_path} --run-id {run_id} --stage integrated"
    return f".\\.venv\\Scripts\\python.exe {script} --config {config_path} --run-id {run_id}"


def concise_metrics(base: Path) -> dict[str, Any]:
    metrics_path = base / "artifacts" / "models" / "metrics.csv"
    if not metrics_path.exists():
        return {}
    metrics = pd.read_csv(metrics_path)
    if metrics.empty:
        return {}
    metric_cols = [col for col in ["rmse", "mae", "r2", "accuracy", "f1", "roc_auc", "log_loss"] if col in metrics.columns]
    row = metrics.iloc[0].to_dict()
    out = {"best_model": row.get("model")}
    for col in metric_cols[:3]:
        out[col] = row.get(col)
    return out


def build_summary(cfg: dict[str, Any], run_id: str, state: dict[str, Any]) -> dict[str, Any]:
    base = run_base(cfg, run_id)
    return {
        "run_id": run_id,
        "status": state["status"],
        "completed_stage_count": len(state["stages_completed"]),
        "stages_completed": state["stages_completed"],
        "recommended_next_stage": state["recommended_next_stage"],
        "recommended_next_command": state["recommended_next_command"],
        "decision_count": state["decision_count"],
        "best_metrics": concise_metrics(base),
        "has_submission": (base / "submissions" / "submission.csv").exists(),
        "has_integrated_pdf": (base / "reports" / "pdf" / "analysis_report_integrated.pdf").exists(),
        "artifact_index_path": str(artifact_index_path(cfg, run_id)),
        "run_index_path": str(run_index_path(cfg, run_id)),
        "last_updated": state["last_updated"],
    }


def render_progress_markdown(state: dict[str, Any], summary: dict[str, Any]) -> str:
    completed = ", ".join(state["stages_completed"]) if state["stages_completed"] else "none"
    best_metrics = summary.get("best_metrics") or {}
    metric_lines = [f"- {key}: `{value}`" for key, value in best_metrics.items()] or ["- No model summary yet."]
    lines = [
        "# Run Progress",
        "",
        f"- Run ID: `{state['run_id']}`",
        f"- Status: `{state['status']}`",
        f"- Completed stages: `{completed}`",
        f"- Recommended next stage: `{state['recommended_next_stage'] or 'none'}`",
        "",
        "## Next Command",
        "",
        f"`{state['recommended_next_command']}`",
        "",
        "## Key Artifacts",
        "",
    ]
    for stage in state.get("stage_order", STAGE_ORDER):
        artifacts = state["artifacts"].get(stage) or []
        if artifacts:
            lines.append(f"- {stage} {STAGE_LABELS[stage]}: " + ", ".join(f"`{item}`" for item in artifacts))
    lines += [
        "",
        "## Decision/Model Summary",
        "",
        f"- decision_log items: `{state['decision_count']}`",
        *metric_lines,
        "",
        f"- Last updated: `{state['last_updated']}`",
        "",
    ]
    return "\n".join(lines)


def render_run_index_markdown(state: dict[str, Any], summary: dict[str, Any]) -> str:
    pending = state.get("pending_checkpoint") or {}
    artifacts = state.get("artifact_index_records") or []
    lines = [
        "# Run Index",
        "",
        f"- run_id: `{state['run_id']}`",
        f"- status: `{state['status']}`",
        f"- completed: `{', '.join(state['stages_completed']) or 'none'}`",
        f"- next_stage: `{state['recommended_next_stage'] or 'none'}`",
        f"- next_command: `{state['recommended_next_command']}`",
        "",
    ]
    if pending:
        lines += [
            "## Pending Checkpoint",
            "",
            f"- checkpoint_id: `{pending.get('checkpoint_id')}`",
            f"- title: `{pending.get('title')}`",
            "",
        ]
    lines += ["## Read First Artifacts", ""]
    if artifacts:
        for item in artifacts[:8]:
            lines.append(f"- `{item['stage']}` `{item['path']}` ({item['size_bytes']} bytes)")
    else:
        lines.append("- No artifacts yet.")
    return "\n".join(lines).strip() + "\n"


def refresh_run_state(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    base = run_base(cfg, run_id)
    completed = infer_completed_stages(base, cfg)
    next_stage = next_stage_from_completed(completed, cfg)
    now = datetime.now().isoformat(timespec="seconds")
    decision_log = read_json(base / "decision_log.json", [])
    pending_domain = read_json(base / "reports" / "pending_checkpoint.json", {})
    pending_hypothesis = read_json(base / "reports" / "pending_hypothesis_checkpoint.json", {})
    has_domain_pending = isinstance(pending_domain, dict) and bool(pending_domain.get("checkpoint_id"))
    has_hypothesis_pending = isinstance(pending_hypothesis, dict) and bool(pending_hypothesis.get("checkpoint_id"))
    has_pending_checkpoint = has_domain_pending or has_hypothesis_pending
    active_pending = pending_domain if has_domain_pending else pending_hypothesis
    artifact_records = detect_artifact_records(base)
    state = {
        "run_id": run_id,
        "config_path": str(cfg.get("_config_path", "")),
        "status": (
            "blocked"
            if has_pending_checkpoint
            else ("completed" if next_stage is None else ("ready" if completed else "initialized"))
        ),
        "current_stage": completed[-1] if completed else None,
        "recommended_next_stage": next_stage,
        "recommended_next_command": recommended_next_command(cfg, run_id, next_stage),
        "stages_completed": completed,
        "stage_order": effective_stage_order(cfg),
        "artifacts": detect_artifact_index(base),
        "artifact_index_records": artifact_records,
        "last_updated": now,
        "decision_count": len(decision_log) if isinstance(decision_log, list) else 0,
        "pending_checkpoint": active_pending if has_pending_checkpoint else None,
    }
    summary = build_summary(cfg, run_id, state)
    write_json(run_state_path(cfg, run_id), state)
    write_json(summary_path(cfg, run_id), summary)
    write_json(artifact_index_path(cfg, run_id), artifact_records)
    progress_path(cfg, run_id).write_text(render_progress_markdown(state, summary), encoding="utf-8")
    run_index_path(cfg, run_id).write_text(render_run_index_markdown(state, summary), encoding="utf-8")
    write_json(
        active_run_path(cfg),
        {
            "active_run_id": run_id,
            "config_path": str(cfg.get("_config_path", "")),
            "run_state_path": str(run_state_path(cfg, run_id)),
            "summary_path": str(summary_path(cfg, run_id)),
            "run_index_path": str(run_index_path(cfg, run_id)),
            "artifact_index_path": str(artifact_index_path(cfg, run_id)),
            "last_updated": now,
        },
    )
    return state
