from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


STAGE_TITLES = {
    "00P": "Raw 데이터 인입",
    "00": "데이터 전체 리뷰",
    "01": "환경 및 입력 점검",
    "02": "결측 및 이상치 진단",
    "02H": "가설 수립",
    "03": "피처 생성 및 전처리",
    "04": "검증 분할",
    "05": "모델 학습",
    "05H": "가설 검증",
    "06": "제출 및 후처리",
}

STAGE_MARKDOWN_FILES = {
    "00P": "table_detection_report.md",
    "00": "dataset_review.md",
    "01": "env_check.md",
    "02": "diagnosis_report.md",
    "02H": "hypothesis_seed_report.md",
    "03": "feature_build_report.md",
    "04": "sample15_fold_report.md",
    "05": "explainability_report.md",
    "05H": "hypothesis_validation_results.md",
    "06": "submission_report.md",
}

def _label_map_from_col_dict(col_dict: pd.DataFrame) -> dict[str, str]:
    if col_dict is None or col_dict.empty:
        return {}
    if "column" not in col_dict.columns:
        return {}
    # Prefer human-friendly Korean display names when available.
    if "display_name_ko" in col_dict.columns:
        m = col_dict.set_index("column")["display_name_ko"].astype(str).to_dict()
        return {k: v for k, v in m.items() if v and v != "nan"}
    return {}


def _with_feature_labels(df: pd.DataFrame, label_map: dict[str, str]) -> pd.DataFrame:
    if df is None or df.empty or not label_map:
        return df
    if "feature" not in df.columns:
        return df
    out = df.copy()
    # Always include a Korean-first label column for display/reporting.
    out["feature_name_ko"] = out["feature"].map(lambda x: label_map.get(str(x), str(x)))
    if "feature_name_ko" in out.columns:
        cols = list(out.columns)
        cols = ["feature_name_ko"] + [c for c in cols if c != "feature_name_ko"]
        out = out[cols]
    return out


def read_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def stage_payload_path(paths: dict[str, Path], stage: str) -> Path:
    return paths["reports"] / f"stage_{stage}_report_payload.json"


def stage_markdown_path(paths: dict[str, Path], stage: str) -> Path:
    return paths["reports"] / STAGE_MARKDOWN_FILES[stage]


def load_stage_payload(stage: str, cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    payload_path = stage_payload_path(paths, stage)
    payload = read_json(payload_path, {})
    if payload:
        return payload
    return write_stage_payload(stage, cfg, paths)


def write_stage_payload(stage: str, cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    payload = build_stage_payload(stage, cfg, paths)
    write_json(stage_payload_path(paths, stage), payload)
    return payload


def write_stage_markdown(stage: str, payload: dict[str, Any], paths: dict[str, Path]) -> Path:
    out_path = stage_markdown_path(paths, stage)
    out_path.write_text(render_stage_markdown(payload), encoding="utf-8")
    return out_path


def build_stage_payload(stage: str, cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    if stage == "00P":
        return _build_stage_00p_payload(cfg, paths)
    if stage == "00":
        return _build_stage_00_payload(cfg, paths)
    if stage == "01":
        return _build_stage_01_payload(cfg, paths)
    if stage == "02":
        return _build_stage_02_payload(cfg, paths)
    if stage == "02H":
        return _build_stage_02h_payload(cfg, paths)
    if stage == "03":
        return _build_stage_03_payload(cfg, paths)
    if stage == "04":
        return _build_stage_04_payload(cfg, paths)
    if stage == "05":
        return _build_stage_05_payload(cfg, paths)
    if stage == "05H":
        return _build_stage_05h_payload(cfg, paths)
    if stage == "06":
        return _build_stage_06_payload(cfg, paths)
    raise ValueError(f"Unsupported payload stage: {stage}")


def render_stage_markdown(payload: dict[str, Any]) -> str:
    stage = str(payload.get("stage", ""))
    if stage in {"00P", "02H", "03", "04", "05", "05H", "06"}:
        return _render_generic_stage_markdown(payload)
    if stage == "00":
        return _render_stage_00_markdown(payload)
    if stage == "01":
        return _render_stage_01_markdown(payload)
    if stage == "02":
        return _render_stage_02_markdown(payload)
    raise ValueError(f"Unsupported payload stage: {stage}")


def _build_stage_00p_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    reports = paths["reports"]
    profile = read_json(reports / "raw_file_profile.json", {})
    metadata = _load_df(reports / "column_metadata.csv")
    semantics = _load_df(reports / "column_semantics_candidates.csv")
    return _base_payload(
        "00P",
        paths,
        [
            "raw_file_profile.json",
            "table_detection_report.md",
            "cleaning_plan.md",
            "column_metadata.csv",
            "column_semantics_candidates.csv",
            "domain_evidence_cards.json",
        ],
        {
            "raw_path": profile.get("raw_path"),
            "shape": profile.get("shape"),
            "header_row": (profile.get("selected_table") or {}).get("header_row"),
            "data_start_row": (profile.get("selected_table") or {}).get("data_start_row"),
            "confidence": (profile.get("selected_table") or {}).get("confidence"),
            "metadata_columns": int(len(metadata)) if not metadata.empty else 0,
        },
        {
            "column_metadata": _records(metadata, ["column", "description", "units", "plot_min", "plot_max"], max_rows=20),
            "semantic_candidates": _records(semantics, ["column", "description", "units", "semantic_group", "confidence"], max_rows=20),
        },
        {"table_detection_report": _read_text(reports / "table_detection_report.md"), "cleaning_plan": _read_text(reports / "cleaning_plan.md")},
    )


def _build_stage_00_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    reports = paths["reports"]
    overview = read_json(reports / "data_overview.json", {})
    domain_pack = read_json(reports / "domain_context_pack.json", {})
    col_dict = _load_df(reports / "column_dictionary.csv")
    label_map = _label_map_from_col_dict(col_dict)
    corr = _load_df(reports / "dataset_review_target_correlations.csv")
    dataset_review = _read_text(reports / "dataset_review.md")
    target = str(overview.get("target_col") or cfg.get("target_col") or "")
    target_row = col_dict[col_dict["column"] == target].head(1)
    target_summary = target_row.iloc[0].to_dict() if not target_row.empty else {}
    group_counts = pd.DataFrame(
        [{"semantic_group": key, "columns": value} for key, value in (overview.get("semantic_group_counts") or {}).items()]
    )
    if group_counts.empty and not col_dict.empty and "semantic_group" in col_dict.columns:
        group_counts = col_dict["semantic_group"].value_counts().reset_index()
        group_counts.columns = ["semantic_group", "columns"]
    return {
        "schema_version": "manual-stage-report-payload.v1",
        "stage": "00",
        "title": STAGE_TITLES["00"],
        "source_artifacts": _existing_artifacts(
            reports,
            [
                "data_overview.json",
                "column_dictionary.csv",
                "dataset_review_target_correlations.csv",
                "dataset_review_correlation_heatmap.png",
                "dataset_review.md",
                "domain_questionnaire.json",
                "domain_questionnaire.md",
                "domain_answers.md",
                "domain_context_pack.json",
            ],
        ),
        "kpis": {
            "task_type": overview.get("task_type") or cfg.get("task_type"),
            "target_col": target,
            "target_col_label": label_map.get(target, target),
            "train_shape": overview.get("train_shape"),
            "test_shape": overview.get("test_shape"),
            "id_col": overview.get("id_col"),
            "group_col": overview.get("group_col") or cfg.get("group_col") or "미설정",
            "time_col": overview.get("time_col") or cfg.get("time_col") or "미설정",
            "inferred_context": overview.get("inferred_context", ""),
            "heatmap_file": "dataset_review_correlation_heatmap.png" if (reports / "dataset_review_correlation_heatmap.png").exists() else None,
            "domain_answered_count": (domain_pack.get("compact_summary") or {}).get("answered_count", 0) if isinstance(domain_pack, dict) else 0,
            "domain_low_confidence_count": (domain_pack.get("compact_summary") or {}).get("low_confidence_count", 0) if isinstance(domain_pack, dict) else 0,
        },
        "target_summary": _json_safe(target_summary),
        "tables": {
            "top_correlations": _records(corr, ["feature_name_ko", "feature", "description", "corr_with_target", "abs_corr"], max_rows=12),
            "semantic_groups": _records(group_counts, ["semantic_group", "columns"], max_rows=20),
            "column_preview": _records(
                col_dict,
                ["column", "role", "semantic_group", "dtype_train", "missing_rate_train", "mean", "std", "skewness", "interpretation"],
                max_rows=12,
            ),
        },
        "decision_highlights": _decision_highlights(paths["base"], "00"),
        "sections": {
            "context_estimate": overview.get("inferred_context", ""),
            "simulation_story": _extract_heading_block(dataset_review, "## 데이터 기반 가상 시뮬레이션"),
            "process_questions": _extract_heading_block(dataset_review, "## 제조업·공정 관점 질문"),
            "engineering_questions": _extract_heading_block(dataset_review, "## 기계공학 관점 질문"),
            "user_background_questions": _extract_heading_block(dataset_review, "## 사용자 경험 활용 질문"),
            "initial_hypotheses": _extract_heading_block(dataset_review, "## 초기 가설 → EDA/피처 후보"),
            "domain_context_summary": domain_pack.get("compact_summary") if isinstance(domain_pack, dict) else {},
        },
    }


def _build_stage_01_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    env = read_json(paths["reports"] / "env_check.json", {})
    file_status = env.get("file_status") or {}
    packages = env.get("packages") or {}
    files_df = pd.DataFrame([{"name": key, **value} for key, value in file_status.items()])
    packages_df = pd.DataFrame([{"package": key, "version": value or "missing"} for key, value in packages.items()])
    return {
        "schema_version": "manual-stage-report-payload.v1",
        "stage": "01",
        "title": STAGE_TITLES["01"],
        "source_artifacts": _existing_artifacts(paths["reports"], ["env_check.json", "env_check.md"]),
        "kpis": {
            "python_version": env.get("python_version"),
            "python_executable": env.get("python_executable"),
            "platform": env.get("platform"),
            "ready": bool(env.get("ready")),
            "missing_package_count": len(env.get("missing_packages") or []),
            "configured_target": cfg.get("target_col"),
        },
        "tables": {
            "files": _records(files_df, ["name", "exists", "path"], max_rows=20),
            "packages": _records(packages_df, ["package", "version"], max_rows=20),
        },
        "decision_highlights": _decision_highlights(paths["base"], "01"),
        "sections": {
            "missing_packages": env.get("missing_packages") or [],
        },
    }


def _build_stage_02_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    reports = paths["reports"]
    outlier = read_json(reports / "target_outlier_summary.json", {})
    domain_pack = read_json(reports / "domain_context_pack.json", {})
    col_dict = _load_df(reports / "column_dictionary.csv")
    label_map = _label_map_from_col_dict(col_dict)
    missing = _load_df(reports / "missing_reason_hypotheses.csv")
    drift = _load_df(reports / "feature_drift_summary.csv")
    evidence = _load_df(reports / "target_outlier_evidence.csv")
    treatments = _load_df(reports / "treatment_recommendations.csv")
    stat_probe = read_json(reports / "stat_probe_report.json", {})
    corr_matrix = _load_df(reports / "correlation_matrix.csv")
    lag_analysis = _load_df(reports / "lag_analysis.csv")
    missing = _with_feature_labels(missing, label_map)
    drift = _with_feature_labels(drift, label_map)
    evidence = _with_feature_labels(evidence, label_map)
    treatments = _with_feature_labels(treatments, label_map)
    return {
        "schema_version": "manual-stage-report-payload.v1",
        "stage": "02",
        "title": STAGE_TITLES["02"],
        "source_artifacts": _existing_artifacts(
            reports,
            [
                "target_outlier_summary.json",
                "missing_reason_hypotheses.csv",
                "feature_drift_summary.csv",
                "target_outlier_evidence.csv",
                "target_outlier_hypotheses.csv",
                "treatment_recommendations.csv",
                "domain_insight_questions.md",
                "domain_context_pack.json",
                "domain_context_pack.md",
                "diagnosis_report.md",
                "stat_probe_report.json",
                "stat_probe_report.md",
                "correlation_matrix.csv",
                "bootstrap_effects.csv",
                "lag_analysis.csv",
            ],
        ),
        "kpis": {
            "target_col": cfg.get("target_col"),
            "target_col_label": label_map.get(str(cfg.get("target_col") or ""), str(cfg.get("target_col") or "")),
            "judgment": outlier.get("judgment"),
            "recommended_target_handling": outlier.get("recommended_target_handling"),
            "log_target_recommendation": outlier.get("log_target_recommendation"),
            "skewness": outlier.get("skewness"),
            "p99_median_ratio": outlier.get("p99_median_ratio"),
            "robust_z_max": outlier.get("robust_z_max"),
            "natural_outlier_score": outlier.get("natural_outlier_score"),
            "drift_candidate_count": int((drift.get("status") == "drift_candidate").sum()) if not drift.empty and "status" in drift.columns else 0,
            "domain_answered_count": (domain_pack.get("compact_summary") or {}).get("answered_count", 0) if isinstance(domain_pack, dict) else 0,
            "domain_low_confidence_count": (domain_pack.get("compact_summary") or {}).get("low_confidence_count", 0) if isinstance(domain_pack, dict) else 0,
            "stat_probe_status": "error" if isinstance(stat_probe, dict) and stat_probe.get("error") else ("ok" if stat_probe else "missing"),
            "stat_probe_top_correlation_count": len(stat_probe.get("top_correlations") or []) if isinstance(stat_probe, dict) else 0,
            "stat_probe_lag_count": int(len(lag_analysis)) if not lag_analysis.empty else 0,
        },
        "tables": {
            "top_missing": _records(
                missing,
                [
                    "feature_name_ko",
                    "feature",
                    "semantic_group",
                    "missing_rate_train",
                    "missing_rate_test",
                    "hypothesis",
                    "recommended_handling",
                    "confidence",
                ],
                max_rows=20,
            ),
            "top_drift": _records(
                drift,
                ["feature_name_ko", "feature", "semantic_group", "approx_ks_gap", "median_gap_std", "mean_gap_std", "status", "note"],
                max_rows=15,
            ),
            "outlier_evidence": _records(
                evidence,
                ["feature_name_ko", "feature", "semantic_group", "corr_with_target", "top_1pct_mean", "rest_mean", "top_vs_rest_diff"],
                max_rows=12,
            ),
            "treatments": _records(treatments, ["kind", "feature_name_ko", "feature", "recommendation", "reason"], max_rows=20),
            "correlation_matrix": _records(corr_matrix, max_rows=12),
            "lag_analysis": _records(lag_analysis, max_rows=20),
        },
        "decision_highlights": _decision_highlights(paths["base"], "02"),
        "sections": {
            "domain_questions": _read_text(reports / "domain_insight_questions.md"),
            "domain_context_summary": domain_pack.get("compact_summary") if isinstance(domain_pack, dict) else {},
        },
    }


def _build_stage_02h_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    reports = paths["reports"]
    registry = read_json(reports / "hypothesis_registry.json", {})
    context_pack = read_json(reports / "hypothesis_context_pack.json", {})
    plan = _load_df(reports / "hypothesis_validation_plan.csv")
    hypotheses = registry.get("hypotheses", []) if isinstance(registry, dict) else []
    summary = registry.get("compact_summary", {}) if isinstance(registry, dict) else {}
    return _base_payload(
        "02H",
        paths,
        [
            "hypothesis_seed_report.md",
            "hypothesis_answers.md",
            "hypothesis_context_pack.json",
            "hypothesis_registry.json",
            "hypothesis_validation_plan.csv",
            "checkpoint_reference_stage_02H.md",
        ],
        {
            "hypothesis_count": summary.get("hypothesis_count", len(hypotheses)),
            "accepted_count": len(summary.get("accepted_ids", []) or []),
            "open_count": len(summary.get("open_ids", []) or []),
            "evidence_card_count": len(context_pack.get("evidence_cards", []) or []) if isinstance(context_pack, dict) else 0,
        },
        {
            "hypotheses": _records(pd.DataFrame(hypotheses), ["hypothesis_id", "status", "confidence", "one_sentence", "validation_method", "leakage_risk"], max_rows=12),
            "validation_plan": _records(plan, ["hypothesis_id", "status", "variables", "validation_method", "feature_plan", "leakage_risk"], max_rows=12),
        },
        {
            "seed_report": _read_text(reports / "hypothesis_seed_report.md"),
            "compact_context": context_pack.get("compact_summary", {}) if isinstance(context_pack, dict) else {},
        },
    )


def _build_stage_03_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    reports = paths["reports"]
    processed = paths["processed"]
    manifest = read_json(processed / "feature_manifest.json", {})
    menu = _load_df(reports / "feature_candidate_menu.csv")
    return _base_payload(
        "03",
        paths,
        [
            "feature_candidate_menu.csv",
            "../data/processed/feature_manifest.json",
            "../data/processed/feature_build_report.md",
        ],
        {
            "feature_families": manifest.get("feature_families", []),
            "generated_feature_count": len(manifest.get("generated_features", []) or []),
            "feature_column_count": len(manifest.get("feature_columns", []) or []),
            "hypothesis_candidate_count": int(menu["hypothesis_id"].notna().sum()) if not menu.empty and "hypothesis_id" in menu.columns else 0,
            "correlation_pruning_applied": manifest.get("correlation_pruning_applied"),
        },
        {
            "feature_candidates": _records(menu, ["family", "feature_name", "hypothesis_id", "formula", "recommendation_basis", "leakage_risk", "auto_recommended"], max_rows=20),
        },
        {"feature_build_report": _read_text(processed / "feature_build_report.md"), "manifest_summary": manifest},
    )


def _build_stage_04_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    folds = paths["folds"]
    summary = read_json(folds / "sample15_fold_summary.json", {})
    fold_counts = summary.get("fold_counts") or {}
    counts_df = pd.DataFrame([{"fold": key, "rows": value} for key, value in fold_counts.items()])
    return _base_payload(
        "04",
        paths,
        ["../data/folds/sample15_fold_summary.json", "../data/folds/sample15_fold_report.md", "../data/folds/sample15_folds.csv", "../data/folds/full_folds.csv"],
        {
            "split_type": summary.get("split_type"),
            "rows": summary.get("rows"),
            "folds": summary.get("folds"),
            "group_leakage_count": summary.get("group_leakage_count"),
            "full_fold_exists": (folds / "full_folds.csv").exists(),
        },
        {"fold_counts": _records(counts_df, ["fold", "rows"], max_rows=20)},
        {"fold_report": _read_text(folds / "sample15_fold_report.md"), "summary": summary},
    )


def _allow_test_usage(cfg: dict[str, Any], stage: str) -> bool:
    mode = str(cfg.get("test_usage_mode", "forbidden")).strip().lower()
    if mode in {"allow", "allowed", "enabled"}:
        return True
    if mode in {"explicit_only", "manual_only"}:
        allowed = {
            str(item).strip().lower()
            for item in (cfg.get("test_usage_allowed_stages") or [])
            if str(item).strip()
        }
        return stage.strip().lower() in allowed
    return False


def _build_stage_05_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    models = paths["models"]
    metrics = _load_df(models / "metrics.csv")
    tuning = _load_df(models / "tuning_results.csv")
    registry = read_json(models / "model_registry.json", {})
    metric = cfg.get("metric_primary") or ("rmse" if cfg.get("task_type") == "regression" else "log_loss")
    best_row = metrics.head(1).to_dict(orient="records")[0] if not metrics.empty else {}
    test_usage_mode = str(cfg.get("test_usage_mode", "forbidden")).strip().lower() or "forbidden"
    test_path_configured = bool(cfg.get("test_path"))
    test_usage_allowed = _allow_test_usage(cfg, "05_model_trainer")
    test_policy_note = (
        "Test set was not used for Stage 05 training, tuning, or model selection."
        if test_path_configured and not test_usage_allowed
        else "No test set was configured for Stage 05."
        if not test_path_configured
        else "Test set usage was explicitly allowed by config for this stage."
    )
    return _base_payload(
        "05",
        paths,
        ["../artifacts/models/metrics.csv", "../artifacts/models/tuning_results.csv", "../artifacts/models/oof_predictions.csv", "../artifacts/models/model_registry.json", "../artifacts/models/explainability_report.md", "../artifacts/models/ablation_groups_plan.csv"],
        {
            "metric_primary": metric,
            "best_model": best_row.get("model"),
            "best_metric": best_row.get(metric),
            "model_count": len(registry.get("models", {}) or {}) if isinstance(registry, dict) else 0,
            "tuning_rows": int(len(tuning)) if not tuning.empty else 0,
            "test_path_configured": test_path_configured,
            "test_usage_mode": test_usage_mode,
            "test_usage_allowed": test_usage_allowed,
            "test_set_policy": "excluded_from_training_tuning_selection" if test_path_configured and not test_usage_allowed else "not_configured" if not test_path_configured else "explicitly_allowed",
        },
        {
            "metrics": _records(metrics, max_rows=12),
            "tuning_preview": _records(tuning, max_rows=12),
        },
        {
            "explainability_report": _read_text(models / "explainability_report.md"),
            "model_registry": registry,
            "test_set_guardrail": {
                "test_path_configured": test_path_configured,
                "test_usage_mode": test_usage_mode,
                "test_usage_allowed_for_stage_05": test_usage_allowed,
                "note": test_policy_note,
            },
        },
    )


def _build_stage_05h_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    reports = paths["reports"]
    results = read_json(reports / "hypothesis_validation_results.json", {})
    rows = pd.DataFrame(results.get("results", []) if isinstance(results, dict) else [])
    return _base_payload(
        "05H",
        paths,
        ["hypothesis_validation_results.json", "hypothesis_validation_results.md"],
        {
            "hypothesis_count": int(len(rows)) if not rows.empty else 0,
            "supported_count": int((rows.get("support_status") == "supported").sum()) if not rows.empty and "support_status" in rows.columns else 0,
            "not_testable_count": int((rows.get("support_status") == "not_testable").sum()) if not rows.empty and "support_status" in rows.columns else 0,
        },
        {"validation_results": _records(rows, ["hypothesis_id", "support_status", "evidence", "next_action"], max_rows=20)},
        {"validation_report": _read_text(reports / "hypothesis_validation_results.md")},
    )


def _build_stage_06_payload(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    submissions = paths["submissions"]
    reports = paths["reports"]
    mode = str(cfg.get("submission_mode", "submission")).lower()
    prediction_file = submissions / ("holdout_predictions.csv" if mode == "holdout_analysis" else "submission.csv")
    submission = _load_df(prediction_file)
    weights = _load_df(submissions / "ensemble_weights.csv")
    choices = read_json(submissions / "postprocess_choices.json", {})
    residual_summary = read_json(reports / "holdout_residual_summary.json", {}) if mode == "holdout_analysis" else {}
    hourly = _load_df(reports / "holdout_error_by_hour.csv")
    target_cols = [c for c in submission.columns if c != (cfg.get("id_col") or "_manual_row_id")] if not submission.empty else []
    target_summary = {}
    if target_cols:
        preferred_col = "prediction" if "prediction" in submission.columns else target_cols[-1]
        vals = pd.to_numeric(submission[preferred_col], errors="coerce")
        target_summary = {"mean": vals.mean(), "std": vals.std(), "min": vals.min(), "max": vals.max()}
    artifact_names = [
        "../submissions/holdout_predictions.csv",
        "holdout_residual_analysis.md",
        "holdout_error_by_hour.csv",
        "holdout_residual_summary.json",
        "../submissions/postprocess_choices.json",
    ] if mode == "holdout_analysis" else [
        "../submissions/submission.csv",
        "../submissions/submission_report.md",
        "../submissions/ensemble_weights.csv",
        "../submissions/postprocess_choices.json",
    ]
    return _base_payload(
        "06",
        paths,
        artifact_names,
        {
            "mode": mode,
            "submission_rows": int(len(submission)) if not submission.empty else 0,
            "holdout_rows": residual_summary.get("holdout_rows") if isinstance(residual_summary, dict) else None,
            "prediction_column": "prediction" if "prediction" in submission.columns else (target_cols[-1] if target_cols else None),
            "ensemble_method": choices.get("ensemble_method"),
            "upper_clip": choices.get("upper_clip"),
            "rmse": residual_summary.get("rmse") if isinstance(residual_summary, dict) else None,
            "mae": residual_summary.get("mae") if isinstance(residual_summary, dict) else None,
            "bias": residual_summary.get("bias") if isinstance(residual_summary, dict) else None,
            "target_summary": _json_safe(target_summary),
        },
        {
            "ensemble_weights": _records(weights, max_rows=20),
            "submission_preview": _records(submission, max_rows=8),
            "holdout_error_by_hour": _records(hourly, max_rows=24),
        },
        {
            "submission_report": _read_text(reports / "holdout_residual_analysis.md" if mode == "holdout_analysis" else submissions / "submission_report.md"),
            "postprocess_choices": choices,
            "holdout_residual_summary": residual_summary,
        },
    )


def _render_stage_00_markdown(payload: dict[str, Any]) -> str:
    kpis = payload.get("kpis", {})
    target_summary = payload.get("target_summary", {})
    tables = payload.get("tables", {})
    sections = payload.get("sections", {})
    target_label = kpis.get("target_col_label") or kpis.get("target_col")
    lines = [
        "# 데이터셋 리뷰",
        "",
        f"- 작업 유형: `{kpis.get('task_type')}`",
        f"- 타깃 컬럼: `{target_label}` ({kpis.get('target_col')})",
        f"- Train 크기: `{kpis.get('train_shape')}`",
        f"- Test 크기: `{kpis.get('test_shape') if kpis.get('test_shape') is not None else '미제공'}`",
        f"- ID 컬럼: `{kpis.get('id_col') or '_manual_row_id'}`",
        f"- 그룹 컬럼: `{kpis.get('group_col')}`",
        f"- 시간 컬럼: `{kpis.get('time_col')}`",
        f"- 도메인 답변 수: `{kpis.get('domain_answered_count', 0)}`",
        f"- 낮은 확신도 질문 수: `{kpis.get('domain_low_confidence_count', 0)}`",
        "",
        "## 데이터/상황 추정",
        "",
        str(sections.get("context_estimate") or "데이터/상황 추정을 위한 구조화 정보가 아직 충분하지 않습니다."),
        "",
        "이 문서는 구조화 산출물(JSON/CSV)을 기준으로 다시 작성된 사용자-facing 보고서다.",
        "",
        "## 타깃 요약",
        "",
    ]
    for key in ["dtype_train", "missing_rate_train", "mean", "std", "min", "median", "p99", "max", "skewness"]:
        value = target_summary.get(key)
        if value is not None:
            lines.append(f"- {key}: `{value}`")
    top_corr = pd.DataFrame(tables.get("top_correlations", []))
    if not top_corr.empty:
        lines += [
            "",
            "## 타깃과의 주요 관계",
            "",
        ]
        if kpis.get("heatmap_file"):
            lines.append(f"- Heatmap: `{kpis['heatmap_file']}`")
            lines.append("")
        lines.append("- 아래 표는 원문 컬럼명보다 한국어 의미명(`feature_name_ko`)을 우선 표시합니다.")
        lines.append("")
        lines.append(_markdown_table(top_corr))
    semantic = pd.DataFrame(tables.get("semantic_groups", []))
    if not semantic.empty:
        lines += ["", "## 컬럼 그룹", "", _markdown_table(semantic)]
    column_preview = pd.DataFrame(tables.get("column_preview", []))
    if not column_preview.empty:
        lines += ["", "## 컬럼 사전 미리보기", "", _markdown_table(column_preview, max_rows=12)]
    lines += _domain_summary_markdown(sections.get("domain_context_summary") or {})
    lines += _decision_markdown(payload.get("decision_highlights", []))
    for key in ["simulation_story", "process_questions", "engineering_questions", "user_background_questions", "initial_hypotheses"]:
        section_text = str(sections.get(key) or "").strip()
        if section_text:
            lines += ["", section_text]
    return "\n".join(lines).strip() + "\n"


def _render_stage_01_markdown(payload: dict[str, Any]) -> str:
    kpis = payload.get("kpis", {})
    tables = payload.get("tables", {})
    lines = [
        "# 환경 점검",
        "",
        f"- Python: `{kpis.get('python_version')}`",
        f"- 실행 파일: `{kpis.get('python_executable')}`",
        f"- 플랫폼: `{kpis.get('platform')}`",
        f"- 준비 상태: `{kpis.get('ready')}`",
        "",
        "## 파일",
        "",
        _markdown_table(pd.DataFrame(tables.get("files", []))),
        "",
        "## 패키지",
        "",
        _markdown_table(pd.DataFrame(tables.get("packages", []))),
    ]
    missing_packages = payload.get("sections", {}).get("missing_packages") or []
    if missing_packages:
        lines += ["", "## 누락 패키지", ""]
        lines.extend(f"- `{name}`" for name in missing_packages)
    lines += _decision_markdown(payload.get("decision_highlights", []))
    return "\n".join(lines).strip() + "\n"


def _render_stage_02_markdown(payload: dict[str, Any]) -> str:
    kpis = payload.get("kpis", {})
    tables = payload.get("tables", {})
    lines = [
        "# 결측/이상치 진단",
        "",
        "## 타깃 이상치 요약",
        "",
        f"- 판단: {kpis.get('judgment', 'unknown')}",
        f"- 타깃 처리 권장: {kpis.get('recommended_target_handling', 'unknown')}",
        f"- 타깃 변환 EDA 판단: {kpis.get('log_target_recommendation', 'unknown')}",
        f"- 왜도(skewness): {kpis.get('skewness', 'n/a')}",
        f"- p99/median 비율: {kpis.get('p99_median_ratio', 'n/a')}",
        f"- robust z-score 최대: {kpis.get('robust_z_max', 'n/a')}",
        f"- drift 후보 컬럼 수: {kpis.get('drift_candidate_count', 0)}",
        f"- 도메인 답변 수: {kpis.get('domain_answered_count', 0)}",
        f"- 낮은 확신도 질문 수: {kpis.get('domain_low_confidence_count', 0)}",
        "",
        "## 결측 가설 상위",
        "",
        _markdown_table(pd.DataFrame(tables.get("top_missing", []))),
    ]
    top_drift = pd.DataFrame(tables.get("top_drift", []))
    if not top_drift.empty:
        lines += ["", "## train/test 드리프트 상위", "", _markdown_table(top_drift, max_rows=15)]
    outlier_evidence = pd.DataFrame(tables.get("outlier_evidence", []))
    if not outlier_evidence.empty:
        lines += ["", "## 이상치 설명 후보 피처", "", _markdown_table(outlier_evidence, max_rows=12)]
    treatments = pd.DataFrame(tables.get("treatments", []))
    if not treatments.empty:
        lines += ["", "## 처리 추천", "", _markdown_table(treatments, max_rows=20)]
    lines += _domain_summary_markdown(payload.get("sections", {}).get("domain_context_summary") or {})
    lines += _decision_markdown(payload.get("decision_highlights", []))
    domain_questions = str(payload.get("sections", {}).get("domain_questions") or "").strip()
    if domain_questions:
        lines += ["", domain_questions]
    return "\n".join(lines).strip() + "\n"


def _decision_highlights(base_path: Path, stage_prefix: str) -> list[dict[str, Any]]:
    decisions = read_json(base_path / "decision_log.json", [])
    if not isinstance(decisions, list):
        return []
    return [item for item in decisions if str(item.get("stage", "")).startswith(stage_prefix)]


def _domain_summary_markdown(summary: dict[str, Any]) -> list[str]:
    if not summary:
        return []
    lines = ["", "## 도메인 답변 요약", ""]
    hypotheses = summary.get("domain_hypotheses") or []
    confirmed = summary.get("confirmed_domain_rules") or []
    open_or_low = summary.get("open_or_low_confidence_questions") or []
    if hypotheses:
        lines += ["### 도메인 가설", ""]
        lines.extend(f"- {item}" for item in hypotheses)
    if confirmed:
        lines += ["", "### 확인된 도메인 규칙", ""]
        lines.extend(f"- {item}" for item in confirmed)
    if open_or_low:
        lines += ["", "### 추가 확인 필요", ""]
        lines.extend(f"- `{item}`" for item in open_or_low)
    return lines


def _decision_markdown(decisions: list[dict[str, Any]]) -> list[str]:
    if not decisions:
        return []
    lines = ["", "## 결정 강조", ""]
    for item in decisions[:5]:
        lines.append(
            f"- `{item.get('decision')}`: 선택=`{item.get('selected')}` | 권장=`{item.get('recommended')}` | 영향={item.get('impact')}"
        )
    return lines


def _base_payload(
    stage: str,
    paths: dict[str, Path],
    artifact_names: list[str],
    kpis: dict[str, Any],
    tables: dict[str, list[dict[str, Any]]],
    sections: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "manual-stage-report-payload.v1",
        "stage": stage,
        "title": STAGE_TITLES[stage],
        "source_artifacts": _existing_artifacts_multi(paths, artifact_names),
        "kpis": _json_safe(kpis),
        "tables": _json_safe(tables),
        "decision_highlights": _decision_highlights(paths["base"], stage),
        "sections": _json_safe(sections),
    }


def _existing_artifacts_multi(paths: dict[str, Path], names: list[str]) -> list[str]:
    roots = [paths["reports"], paths["base"]]
    out: list[str] = []
    for name in names:
        raw = Path(name)
        candidates = []
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.extend(root / raw for root in roots)
        if any(path.exists() for path in candidates):
            out.append(name)
    return out


def _render_generic_stage_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload.get('title')}",
        "",
        f"- stage: `{payload.get('stage')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        "",
        "## KPI",
        "",
    ]
    kpis = payload.get("kpis") or {}
    if kpis:
        lines.extend(f"- {key}: `{value}`" for key, value in kpis.items())
    else:
        lines.append("- No KPI available.")
    for name, rows in (payload.get("tables") or {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        lines += ["", f"## {name}", "", _markdown_table(df, max_rows=20)]
    sections = payload.get("sections") or {}
    for key, value in sections.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        text = str(text).strip()
        if not text:
            continue
        lines += ["", f"## {key}", "", text[:2500]]
    lines += _decision_markdown(payload.get("decision_highlights", []))
    return "\n".join(lines).strip() + "\n"


def _existing_artifacts(root: Path, names: list[str]) -> list[str]:
    return [name for name in names if (root / name).exists()]


def _extract_heading_block(text: str, heading: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.DataFrame()


def _records(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> list[dict[str, Any]]:
    if df.empty:
        return []
    view = df.copy()
    if columns:
        keep = [column for column in columns if column in view.columns]
        if keep:
            view = view[keep]
    view = view.head(max_rows)
    view = view.where(pd.notna(view), None)
    return [_json_safe(record) for record in view.to_dict(orient="records")]


def _markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.head(max_rows).fillna("").astype(str)
    headers = list(view.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in view.iterrows():
        values = [str(row[column]).replace("|", "/")[:120] for column in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.DataFrame):
        return _records(value)
    if isinstance(value, pd.Series):
        return _json_safe(value.to_dict())
    if value is None:
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value
