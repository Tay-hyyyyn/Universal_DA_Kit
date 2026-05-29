from __future__ import annotations

import importlib.util
import json
import math
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_PACKAGES = [
    "pandas",
    "numpy",
    "sklearn",
    "xgboost",
    "matplotlib",
    "seaborn",
    "pyarrow",
    "joblib",
]

SEMANTIC_KEYWORDS: dict[str, list[str]] = {
    "identifier": ["id", "key", "code"],
    "target_like": ["target", "label", "delay", "y"],
    "time_order": ["time", "date", "hour", "day", "week", "month", "shift", "step", "seq", "phase", "period"],
    "group_segment": ["group", "scenario", "layout", "site", "line", "cell", "zone", "area", "plant"],
    "demand_load": ["order", "demand", "inflow", "volume", "qty", "quantity", "count", "sku", "items", "load", "traffic", "pick", "pack", "ship"],
    "capacity_resource": ["capacity", "staff", "worker", "robot", "machine", "charger", "dock", "station", "resource", "active", "idle", "hvac", "motor", "pump", "battery", "power", "energy", "compressor"],
    "utilization_pressure": ["util", "ratio", "pct", "rate", "density", "queue", "wait", "pressure", "congestion", "path", "route", "distance", "travel"],
    "error_quality": ["error", "fault", "fail", "defect", "quality", "collision", "blocked", "latency", "response", "risk", "safety", "maintenance", "wear"],
    "environment": ["temp", "temperature", "humidity", "wind", "rain", "precip", "noise", "vibration", "air", "co2", "light", "cold", "cool", "heat", "thermal"],
    "location_layout": ["layout", "aisle", "floor", "height", "width", "intersection", "exit", "entry", "door", "building", "racking", "rack"],
    "finance_cost": ["cost", "price", "sales", "revenue", "margin", "profit", "fee"],
}

DEFAULT_ANALYST_BACKGROUND = [
    "기계공학 전공",
    "제조업/공정 경험",
    "냉동·냉장 물류/창고 구축 경험",
    "여행 및 동선 관심",
]


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


def load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).resolve()
    cfg = read_json(path, {})
    if not cfg:
        raise ValueError(f"Config not found or empty: {path}")
    for key in ["train_path", "target_col", "task_type"]:
        if not cfg.get(key):
            raise ValueError(f"Manual config requires `{key}`.")
    task = str(cfg["task_type"]).lower()
    if task not in {"regression", "classification"}:
        raise ValueError("task_type must be regression or classification.")
    project_root = Path(cfg.get("project_root", "."))
    if not project_root.is_absolute():
        project_root = (path.parent / project_root).resolve()
    cfg["_config_path"] = str(path)
    cfg["_project_root"] = str(project_root)
    cfg["task_type"] = task
    return cfg


def project_root(cfg: dict[str, Any]) -> Path:
    return Path(cfg["_project_root"]).resolve()


def resolve_project_path(cfg: dict[str, Any], value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else (project_root(cfg) / p).resolve()


def run_dir(cfg: dict[str, Any], run_id: str) -> Path:
    output_root = resolve_project_path(cfg, cfg.get("output_root", "Manual/runs"))
    return ensure_dir(output_root / run_id)


def run_paths(cfg: dict[str, Any], run_id: str) -> dict[str, Path]:
    base = run_dir(cfg, run_id)
    return {
        "base": base,
        "reports": ensure_dir(base / "reports"),
        "pdf": ensure_dir(base / "reports" / "pdf"),
        "processed": ensure_dir(base / "data" / "processed"),
        "folds": ensure_dir(base / "data" / "folds"),
        "models": ensure_dir(base / "artifacts" / "models"),
        "submissions": ensure_dir(base / "submissions"),
    }


def append_decision(cfg: dict[str, Any], run_id: str, stage: str, decision: str, selected: str, recommended: str, rationale: str, impact: str) -> None:
    path = run_dir(cfg, run_id) / "decision_log.json"
    log = read_json(path, [])
    if not isinstance(log, list):
        log = []
    entry = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "decision": decision,
        "selected": selected,
        "recommended": recommended,
        "rationale": rationale,
        "impact": impact,
        "mutable": True,
    }
    signature_keys = ["stage", "decision", "selected", "recommended", "rationale", "impact"]
    if any(isinstance(item, dict) and all(item.get(key) == entry[key] for key in signature_keys) for item in log):
        return
    log.append(entry)
    write_json(path, log)


def append_stage_log(cfg: dict[str, Any], stage: str, purpose: str, inputs: list[str], outputs: list[str], checkpoint: str = "없음", next_step: str = "") -> None:
    try:
        from log_writer import append_manual_log

        append_manual_log(cfg, stage, purpose, inputs, outputs, checkpoint=checkpoint, next_step=next_step)
    except Exception:
        pass


def save_dataframe(df: pd.DataFrame, path: str | Path) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    if p.suffix.lower() == ".parquet":
        df.to_parquet(p, index=False)
    elif p.suffix.lower() == ".csv":
        df.to_csv(p, index=False)
    else:
        raise ValueError(f"Unsupported output extension: {p.suffix}")


def ensure_unique_keys(df: pd.DataFrame, keys: str | list[str], frame_name: str) -> None:
    key_cols = [keys] if isinstance(keys, str) else list(keys)
    missing = [column for column in key_cols if column not in df.columns]
    if missing:
        raise ValueError(f"{frame_name} is missing required key columns: {missing}")
    duplicate_mask = df.duplicated(subset=key_cols, keep=False)
    if duplicate_mask.any():
        sample = df.loc[duplicate_mask, key_cols].head(5).to_dict(orient="records")
        raise ValueError(f"{frame_name} contains duplicated keys for {key_cols}. Examples: {sample}")


def merge_one_to_one(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str | list[str],
    left_name: str,
    right_name: str,
    how: str = "inner",
    require_all_left: bool = True,
) -> pd.DataFrame:
    key_cols = [on] if isinstance(on, str) else list(on)
    ensure_unique_keys(left, key_cols, left_name)
    ensure_unique_keys(right, key_cols, right_name)
    merged = left.merge(right, on=key_cols, how=how, validate="1:1")
    if require_all_left and len(merged) != len(left):
        raise ValueError(
            f"{left_name} -> {right_name} merge on {key_cols} changed row count "
            f"from {len(left)} to {len(merged)}."
        )
    return merged


def align_by_id(
    reference: pd.DataFrame,
    values: pd.DataFrame,
    id_col: str,
    value_columns: list[str],
    reference_name: str,
    values_name: str,
    exact_keys: bool = True,
) -> pd.DataFrame:
    ref = reference[[id_col]].copy()
    cols = [id_col] + [column for column in value_columns if column != id_col]
    pred = values[cols].copy()
    ensure_unique_keys(ref, id_col, reference_name)
    ensure_unique_keys(pred, id_col, values_name)
    if exact_keys:
        ref_ids = set(ref[id_col])
        pred_ids = set(pred[id_col])
        if ref_ids != pred_ids:
            missing = sorted(ref_ids - pred_ids)[:5]
            extra = sorted(pred_ids - ref_ids)[:5]
            raise ValueError(
                f"{values_name} IDs do not exactly match {reference_name}. "
                f"Missing examples: {missing}, extra examples: {extra}"
            )
    aligned = ref.merge(pred, on=id_col, how="left", validate="1:1")
    missing_cols = [column for column in value_columns if column not in aligned.columns]
    if missing_cols:
        raise ValueError(f"{values_name} is missing value columns after ID align: {missing_cols}")
    if aligned[value_columns].isna().any().any():
        raise ValueError(f"{values_name} contains missing values after aligning to {reference_name}.")
    if len(aligned) != len(ref) or not aligned[id_col].equals(ref[id_col]):
        raise ValueError(f"{values_name} failed to preserve {reference_name} ID order.")
    return aligned


def ensure_feature_schema_match(train_frame: pd.DataFrame, test_frame: pd.DataFrame, context: str) -> None:
    train_cols = list(train_frame.columns)
    test_cols = list(test_frame.columns)
    if train_cols == test_cols:
        return
    train_set = set(train_cols)
    test_set = set(test_cols)
    missing_in_test = [column for column in train_cols if column not in test_set][:10]
    extra_in_test = [column for column in test_cols if column not in train_set][:10]
    raise ValueError(
        f"{context} feature schema mismatch. "
        f"Missing in test: {missing_in_test}, extra in test: {extra_in_test}."
    )


def ensure_prediction_export_scale(
    registry: dict | None,
    context: str,
    expected: str = "raw",
    allow_missing: bool = True,
) -> str | None:
    if registry is None:
        if allow_missing:
            return None
        raise ValueError(f"{context} has no model registry payload.")
    if not isinstance(registry, dict):
        raise ValueError(f"{context} registry must be a dict, got {type(registry).__name__}.")
    export_scale = registry.get("prediction_export_scale")
    if export_scale is None:
        if allow_missing:
            return None
        raise ValueError(f"{context} registry is missing `prediction_export_scale`.")
    if export_scale != expected:
        raise ValueError(
            f"{context} registry says prediction export scale is `{export_scale}`, expected `{expected}`."
        )
    return export_scale


def read_processed(paths: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame]:
    train = pd.read_parquet(paths["processed"] / "train_features.parquet")
    test_path = paths["processed"] / "test_features.parquet"
    test = pd.read_parquet(test_path) if test_path.exists() else None
    y = pd.read_parquet(paths["processed"] / "y.parquet")
    manifest = read_json(paths["processed"] / "feature_manifest.json", {})
    id_col = manifest.get("id_col") or "_manual_row_id"
    ensure_unique_keys(train, id_col, "processed train")
    if test is not None:
        ensure_unique_keys(test, id_col, "processed test")
    ensure_unique_keys(y, id_col, "processed target")
    return train, test, y


def safe_div(num: Any, den: Any, fill: float = 0.0) -> Any:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.divide(num, den)
    if isinstance(out, np.ndarray):
        return np.where(np.isfinite(out), out, fill)
    if isinstance(out, pd.Series):
        return out.replace([np.inf, -np.inf], np.nan).fillna(fill)
    return out if np.isfinite(out) else fill


def infer_semantic_group(column: str, description: str = "") -> str:
    name = f"{column} {description}".lower()
    for group, keywords in SEMANTIC_KEYWORDS.items():
        if any(keyword in name for keyword in keywords):
            return group
    return "numeric_other"


def semantic_group_ko(semantic_group: str) -> str:
    return {
        "identifier": "식별자",
        "target_like": "타깃/결과 후보",
        "time_order": "시간/순서",
        "group_segment": "그룹/세그먼트",
        "demand_load": "부하/수요",
        "capacity_resource": "설비/자원/용량",
        "utilization_pressure": "가동률/압력/병목",
        "error_quality": "품질/장애/리스크",
        "environment": "환경/온도/열",
        "location_layout": "위치/구역/공간",
        "finance_cost": "비용/금액",
        "numeric_other": "일반 수치",
    }.get(semantic_group, semantic_group)


def normalize_description(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def translate_description_to_korean(description: str, column: str = "") -> str:
    desc = normalize_description(description)
    low = desc.lower()
    col_low = column.lower()
    patterns = [
        ("reactor inlet metric", "반응기 입구 지표"),
        ("reactor inlet oxygen", "반응기 입구 산소 농도"),
        ("reactor inlet temperature", "반응기 입구 온도"),
        ("dgan suc pr", "DGAN 흡입 압력 제어값"),
        ("dgan to compression pres control", "DGAN 압축 압력 제어밸브 위치"),
        ("syngas supply pressure", "합성가스 공급 압력"),
        ("syngas supply temperature", "합성가스 공급 온도"),
        ("clamped sg fuel flow", "합성가스 연료 유량(보정)"),
        ("lhv wet", "합성가스 습식 저위발열량"),
        ("syngas srv", "합성가스 정지/비율 밸브 개도"),
        ("syngas gcv", "합성가스 제어밸브 개도"),
        ("interstage syngas press", "합성가스 중간단 압력"),
        ("secondary manifold pressure", "2차 매니폴드 압력"),
        ("gt generated watts", "가스터빈 발전 출력"),
        ("turbine inlet diff pressure", "터빈 입구 차압"),
        ("compressor inlet temperature", "압축기 입구 온도"),
        ("ambient pressure", "대기압"),
        ("igv feedback", "입구 가이드베인 개도"),
        ("compressor discharge pressure", "압축기 토출 압력"),
        ("compressor discharge temperature", "압축기 토출 온도"),
        ("inlet heating control valve", "입구 가열 제어밸브 위치"),
        ("voted speed signal", "터빈 회전속도"),
        ("inlet duct temperature", "입구 덕트 온도"),
        ("exhaust mass flow", "배기가스 질량유량"),
        ("exhaust temp", "배기가스 온도"),
        ("primary manifold diff", "1차 매니폴드 차압"),
        ("secondary manifold diff", "2차 매니폴드 차압"),
        ("nozzle pressure ratio in secondary", "2차 매니폴드 노즐 압력비"),
        ("nozzle pressure ratio in primary", "1차 매니폴드 노즐 압력비"),
        ("n2 injection supply pressure", "질소 주입 공급 압력"),
        ("n2 injection temperature", "질소 주입 온도"),
        ("n2 injection flow", "질소 주입 유량"),
        ("nitrogen diluent o2", "질소 희석가스 산소 농도"),
        ("n2 injection control valve", "질소 주입 제어밸브 개도"),
        ("n2 diluent intercavity temperature", "질소 희석 인터캐비티 온도"),
        ("n2 injection intercavity pressure", "질소 주입 인터캐비티 압력"),
        ("n2 injection tfire", "질소 주입 기준 연소온도"),
        ("inlet dew point", "입구 노점 온도"),
        ("sg perfoemance heater syngas inlet temperature", "합성가스 성능히터 입구 온도"),
    ]
    for key, label in patterns:
        if key in low:
            return label
    if "emission" in col_low:
        return "배출 지표"
    if "temperature" in low or "temp" in low or "tt" in col_low:
        return "온도 계측값"
    if "pressure" in low or "press" in low or "pr" in col_low:
        return "압력 계측값"
    if "flow" in low:
        return "유량 계측값"
    if "valve" in low or "position" in low or "feedback" in low:
        return "밸브/제어 위치"
    if "ratio" in low:
        return "압력/운전 비율"
    if "power" in low or "watt" in low:
        return "발전 출력"
    if desc:
        return desc
    token = column.split(".")[-1] if column else "feature"
    return token


def practical_interpretation(column: str, semantic_group: str, description: str = "") -> str:
    label = translate_description_to_korean(description, column)
    group = semantic_group_ko(semantic_group)
    if description:
        return f"{label}: {group} 성격의 계측값으로, 타깃과의 관계를 분포/상관/시차 관점에서 확인한다."
    return f"{label}: 원문 태그에서 추정한 {group} 성격의 변수다. 실제 센서 의미는 도메인 확인이 필요하다."


def load_column_metadata(cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    candidates: list[Path] = []
    direct = cfg.get("column_metadata_path") or cfg.get("column_dictionary_path")
    if direct:
        path = resolve_project_path(cfg, str(direct))
        if path:
            candidates.append(path)
    for item in cfg.get("metadata_paths", []) or []:
        if isinstance(item, dict) and str(item.get("kind", "")).lower() in {"column_metadata", "column_dictionary", "column_descriptions"}:
            path = resolve_project_path(cfg, item.get("path"))
            if path:
                candidates.append(path)
    out: dict[str, dict[str, str]] = {}
    for path in candidates:
        if not path.exists():
            continue
        meta = pd.read_csv(path)
        cols_lower = {c.lower(): c for c in meta.columns}
        col_col = cols_lower.get("column") or cols_lower.get("tagname") or cols_lower.get("feature")
        if not col_col:
            continue
        desc_col = cols_lower.get("description") or cols_lower.get("desc") or cols_lower.get("meaning")
        unit_col = cols_lower.get("unit") or cols_lower.get("units")
        display_col = cols_lower.get("display_name_ko") or cols_lower.get("name_ko") or cols_lower.get("korean_name")
        for _, row in meta.iterrows():
            col = str(row.get(col_col, "")).strip()
            if not col:
                continue
            desc = normalize_description(row.get(desc_col, "")) if desc_col else ""
            unit = normalize_description(row.get(unit_col, "")) if unit_col else ""
            display = normalize_description(row.get(display_col, "")) if display_col else ""
            out[col] = {
                "description": desc,
                "unit": unit,
                "display_name_ko": display or translate_description_to_korean(desc, col),
            }
    return out


def display_name_map(col_dict: pd.DataFrame) -> dict[str, str]:
    if "display_name_ko" not in col_dict.columns:
        return {}
    return {
        str(row["column"]): str(row.get("display_name_ko") or row["column"])
        for _, row in col_dict.iterrows()
    }


def unique_label_map(col_dict: pd.DataFrame, max_len: int = 28) -> dict[str, str]:
    base = display_name_map(col_dict)
    seen: dict[str, int] = {}
    out: dict[str, str] = {}
    for col in col_dict["column"].astype(str).tolist():
        label = base.get(col, col)
        label = label[:max_len]
        seen[label] = seen.get(label, 0) + 1
        out[col] = label if seen[label] == 1 else f"{label}({seen[label]})"
    return out


def interpretation_for(column: str, semantic_group: str) -> str:
    name = column.lower()
    if semantic_group == "identifier":
        return "Identifier or key used for joins, grouping, or submission ordering."
    if semantic_group == "time_order":
        return "Time, order, calendar, or sequence signal that can encode seasonality or process phase."
    if semantic_group == "demand_load":
        return "Demand or workload signal; higher values can increase pressure on resources."
    if semantic_group == "capacity_resource":
        return "Capacity or resource availability signal; ratios against demand are often useful."
    if semantic_group == "utilization_pressure":
        return "Utilization, queue, wait, or density signal that can reveal bottlenecks."
    if semantic_group == "error_quality":
        return "Error, reliability, quality, or risk signal that can explain disruptions and outliers."
    if semantic_group == "environment":
        return "External or environmental condition signal."
    if semantic_group == "location_layout":
        return "Physical layout, site, area, or spatial configuration signal."
    if semantic_group == "finance_cost":
        return "Cost, price, or financial magnitude signal."
    if "delay" in name:
        return "Delay-related signal; check leakage risk if it describes the future."
    return "General feature; inspect distribution and relationship with the target."


def load_raw_data(cfg: dict[str, Any], nrows: int | None = None) -> dict[str, Any]:
    train_path = resolve_project_path(cfg, cfg["train_path"])
    test_path = resolve_project_path(cfg, cfg.get("test_path"))
    sample_path = resolve_project_path(cfg, cfg.get("sample_submission_path"))
    if not train_path or not train_path.exists():
        raise FileNotFoundError(f"train_path not found: {train_path}")
    train = pd.read_csv(train_path, nrows=nrows)
    test = pd.read_csv(test_path, nrows=nrows) if test_path and test_path.exists() else None
    sample = pd.read_csv(sample_path, nrows=nrows) if sample_path and sample_path.exists() else None
    metadata = []
    for item in cfg.get("metadata_paths", []) or []:
        meta_path = resolve_project_path(cfg, item.get("path"))
        if meta_path and meta_path.exists():
            metadata.append({**item, "path_resolved": str(meta_path), "frame": pd.read_csv(meta_path)})
    return {"train": train, "test": test, "sample_submission": sample, "metadata": metadata}


def merge_metadata(df: pd.DataFrame | None, metadata: list[dict[str, Any]]) -> pd.DataFrame | None:
    if df is None:
        return None
    out = df.copy()
    for item in metadata:
        meta = item["frame"]
        join_key = item.get("join_key")
        left_on = item.get("left_on", join_key)
        right_on = item.get("right_on", join_key)
        if left_on and right_on and left_on in out.columns and right_on in meta.columns:
            out = out.merge(meta, left_on=left_on, right_on=right_on, how="left", suffixes=("", "_meta"))
    return out


def load_modeling_data(cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    raw = load_raw_data(cfg)
    train = merge_metadata(raw["train"], raw["metadata"])
    test = merge_metadata(raw["test"], raw["metadata"])
    return train, test, raw["sample_submission"]


def allow_test_usage(cfg: dict[str, Any], stage: str) -> bool:
    """
    Guardrail for test-set usage.
    Default is blocked unless the config explicitly opts in.
    """
    mode = str(cfg.get("test_usage_mode", "forbidden")).strip().lower()
    if mode in {"allow", "allowed", "enabled"}:
        return True
    if mode in {"explicit_only", "manual_only"}:
        allowed_stages = {
            str(item).strip().lower()
            for item in (cfg.get("test_usage_allowed_stages") or [])
            if str(item).strip()
        }
        return stage.strip().lower() in allowed_stages
    return False


def choose_id_col(cfg: dict[str, Any], train: pd.DataFrame, test: pd.DataFrame | None = None) -> str:
    configured = cfg.get("id_col")
    if configured and configured in train.columns:
        return configured
    candidates = [c for c in train.columns if c.lower() in {"id", "row_id", "index"} or c.lower().endswith("_id")]
    if candidates:
        return candidates[0]
    return "_manual_row_id"


def ensure_id_column(df: pd.DataFrame, id_col: str) -> pd.DataFrame:
    out = df.copy()
    if id_col not in out.columns:
        out.insert(0, id_col, np.arange(len(out)))
    return out


def numeric_columns(df: pd.DataFrame, exclude: set[str] | None = None) -> list[str]:
    excluded = exclude or set()
    return [c for c in df.columns if c not in excluded and pd.api.types.is_numeric_dtype(df[c])]


def compact_examples(series: pd.Series, max_items: int = 4) -> str:
    values = series.dropna().astype(str).unique()[:max_items]
    return " | ".join(values)


def markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.head(max_rows).fillna("").astype(str)
    headers = list(view.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in view.iterrows():
        values = [str(row[col]).replace("|", "/")[:120] for col in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def column_stats(train: pd.DataFrame, test: pd.DataFrame | None, cfg: dict[str, Any]) -> pd.DataFrame:
    target_col = cfg["target_col"]
    id_col = choose_id_col(cfg, train, test)
    group_col = cfg.get("group_col")
    time_col = cfg.get("time_col")
    metadata = load_column_metadata(cfg)
    all_cols = list(dict.fromkeys(list(train.columns) + (list(test.columns) if test is not None else [])))
    rows = []
    for col in all_cols:
        role = "feature"
        if col == target_col:
            role = "target"
        elif col == id_col:
            role = "id"
        elif group_col and col == group_col:
            role = "group"
        elif time_col and col == time_col:
            role = "time"
        train_s = train[col] if col in train.columns else pd.Series(dtype="float64")
        test_s = test[col] if test is not None and col in test.columns else pd.Series(dtype="float64")
        is_num = pd.api.types.is_numeric_dtype(train_s) if len(train_s) else pd.api.types.is_numeric_dtype(test_s)
        numeric = pd.to_numeric(train_s, errors="coerce") if is_num else pd.Series(dtype="float64")
        meta = metadata.get(col, {})
        description = normalize_description(meta.get("description", ""))
        unit = normalize_description(meta.get("unit", ""))
        display_name = normalize_description(meta.get("display_name_ko", "")) or translate_description_to_korean(description, col)
        semantic = infer_semantic_group(col, description)
        rows.append(
            {
                "column": col,
                "display_name_ko": display_name,
                "description": description,
                "unit": unit,
                "role": role,
                "semantic_group": semantic,
                "semantic_group_ko": semantic_group_ko(semantic),
                "dtype_train": str(train_s.dtype) if col in train.columns else "",
                "dtype_test": str(test_s.dtype) if test is not None and col in test.columns else "",
                "missing_rate_train": round(float(train_s.isna().mean()) * 100, 4) if col in train.columns else np.nan,
                "missing_rate_test": round(float(test_s.isna().mean()) * 100, 4) if test is not None and col in test.columns else np.nan,
                "unique_train": int(train_s.nunique(dropna=True)) if col in train.columns else 0,
                "unique_test": int(test_s.nunique(dropna=True)) if test is not None and col in test.columns else 0,
                "mean": round(float(numeric.mean()), 6) if len(numeric) and numeric.notna().any() else np.nan,
                "std": round(float(numeric.std()), 6) if len(numeric) and numeric.notna().any() else np.nan,
                "min": round(float(numeric.min()), 6) if len(numeric) and numeric.notna().any() else np.nan,
                "p01": round(float(numeric.quantile(0.01)), 6) if len(numeric) and numeric.notna().any() else np.nan,
                "median": round(float(numeric.median()), 6) if len(numeric) and numeric.notna().any() else np.nan,
                "p99": round(float(numeric.quantile(0.99)), 6) if len(numeric) and numeric.notna().any() else np.nan,
                "max": round(float(numeric.max()), 6) if len(numeric) and numeric.notna().any() else np.nan,
                "skewness": round(float(numeric.skew()), 6) if len(numeric) and numeric.notna().sum() > 2 else np.nan,
                "example_values": compact_examples(train_s if col in train.columns else test_s),
                "interpretation": practical_interpretation(col, semantic, description),
            }
        )
    return pd.DataFrame(rows)


def infer_dataset_context(col_dict: pd.DataFrame, cfg: dict[str, Any]) -> str:
    if cfg.get("domain_context"):
        return str(cfg["domain_context"])
    names = " ".join(col_dict["column"].astype(str).str.lower().tolist())
    logistics_hits = sum(k in names for k in ["order", "sku", "robot", "dock", "warehouse", "wms", "charger", "conveyor"])
    manufacturing_hits = sum(k in names for k in ["machine", "line", "defect", "quality", "process", "temperature", "pressure"])
    finance_hits = sum(k in names for k in ["sales", "price", "revenue", "cost", "customer", "transaction"])
    if logistics_hits >= 4:
        return "이 데이터셋은 물류/operations 운영을 설명하는 것으로 보이며, 수요(유입), 자원(인력/로봇/설비), 공정 혼잡, IT 신호, 레이아웃 조건 등이 타깃에 영향을 주는 구조로 해석된다."
    if manufacturing_hits >= 4:
        return "이 데이터셋은 제조/공정 제어 환경으로 보이며, 설비, 품질, 환경, 처리량(throughput) 신호가 포함된 것으로 해석된다."
    if finance_hits >= 4:
        return "이 데이터셋은 상거래/금융 거래로 보이며, 고객, 가격, 수요, 비용 신호가 포함된 것으로 해석된다."
    return "이 데이터셋은 일반적인 표 형식 지도학습 문제로 보이며, 실제 도메인 맥락은 프로젝트 담당자와 확인이 필요하다."


def as_text_list(value: Any, default: list[str] | None = None) -> list[str]:
    if value is None or value == "":
        return list(default or [])
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace(";", ",").split(",")]
        return [part for part in parts if part]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def columns_for(
    col_dict: pd.DataFrame,
    semantic_groups: set[str] | None = None,
    keywords: list[str] | None = None,
    limit: int = 6,
) -> list[str]:
    semantic_groups = semantic_groups or set()
    keywords = [keyword.lower() for keyword in (keywords or [])]
    selected: list[str] = []
    for _, row in col_dict.iterrows():
        column = str(row["column"])
        semantic_group = str(row.get("semantic_group", ""))
        column_lower = column.lower()
        if semantic_group in semantic_groups or any(keyword in column_lower for keyword in keywords):
            selected.append(column)
        if len(selected) >= limit:
            break
    return selected


def format_columns(columns: list[str], label_map: dict[str, str] | None = None) -> str:
    if not columns:
        return "자동 후보 없음"
    label_map = label_map or {}
    values = []
    for column in columns:
        label = label_map.get(column, column)
        values.append(f"`{label}`({column})" if label != column else f"`{column}`")
    return ", ".join(values)


def detect_domain_signals(col_dict: pd.DataFrame, cfg: dict[str, Any], context: str) -> dict[str, bool]:
    names = " ".join(col_dict["column"].astype(str).str.lower().tolist())
    text = f"{names} {context} {cfg.get('domain_context', '')}".lower()
    return {
        "logistics": any(k in text for k in ["order", "sku", "warehouse", "wms", "dock", "picking", "packing", "shipment"]),
        "manufacturing": any(k in text for k in ["machine", "line", "process", "plant", "factory", "defect", "quality", "throughput"]),
        "robotics_motion": any(k in text for k in ["robot", "route", "path", "travel", "distance", "battery", "charger", "collision"]),
        "thermal_cooling": any(k in text for k in ["temp", "temperature", "cold", "cool", "heat", "thermal", "hvac", "freezer", "refriger"]),
        "layout_spatial": any(k in text for k in ["layout", "aisle", "rack", "racking", "zone", "exit", "entry", "door", "floor"]),
        "maintenance_quality": any(k in text for k in ["fault", "fail", "defect", "quality", "maintenance", "wear", "vibration", "risk"]),
        "time_flow": any(k in text for k in ["time", "date", "hour", "shift", "step", "seq", "phase", "period"]),
        "finance": any(k in text for k in ["sales", "price", "revenue", "cost", "customer", "transaction"]),
    }


def analyst_background(cfg: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "background": as_text_list(cfg.get("analyst_background"), DEFAULT_ANALYST_BACKGROUND),
        "domain_notes": as_text_list(cfg.get("domain_expertise_notes")),
        "experience_keywords": as_text_list(cfg.get("experience_keywords")),
        "interest_keywords": as_text_list(cfg.get("interest_keywords")),
        "first_report_focus": as_text_list(cfg.get("first_report_focus")),
    }


def build_simulation_story(
    cfg: dict[str, Any],
    train: pd.DataFrame,
    test: pd.DataFrame | None,
    col_dict: pd.DataFrame,
    context: str,
) -> list[str]:
    target = cfg["target_col"]
    signals = detect_domain_signals(col_dict, cfg, context)
    labels = display_name_map(col_dict)
    demand_cols = columns_for(col_dict, {"demand_load"}, limit=4)
    resource_cols = columns_for(col_dict, {"capacity_resource"}, limit=4)
    pressure_cols = columns_for(col_dict, {"utilization_pressure"}, limit=4)
    environment_cols = columns_for(col_dict, {"environment"}, limit=4)
    layout_cols = columns_for(col_dict, {"location_layout", "group_segment"}, ["layout", "zone", "aisle", "rack"], limit=4)
    quality_cols = columns_for(col_dict, {"error_quality"}, limit=4)
    group_col = cfg.get("group_col") or "그룹 미설정"
    time_col = cfg.get("time_col") or "명시적 시간 컬럼 미설정"
    row_scope = f"train {train.shape[0]:,}행"
    if test is not None:
        row_scope += f", test {test.shape[0]:,}행"

    if signals["logistics"] or signals["robotics_motion"] or signals["layout_spatial"]:
        scene = (
            "이 데이터는 주문이 들어오고, 로봇·작업자·충전기·도크·포장 구역이 함께 움직이는 "
            "물류센터 또는 자동화 창고의 운영 흐름을 관찰한 기록으로 볼 수 있다."
        )
    elif signals["manufacturing"]:
        scene = (
            "이 데이터는 설비와 라인이 제품을 처리하면서 품질, 환경 조건, 처리량, 대기 상태가 변하는 "
            "제조 공정 운영 기록으로 볼 수 있다."
        )
    elif signals["finance"]:
        scene = "이 데이터는 고객, 가격, 거래, 비용 신호가 결과값에 영향을 주는 상거래/금융 의사결정 기록으로 볼 수 있다."
    else:
        scene = "이 데이터는 여러 설명 변수로 타깃을 예측하는 표 형식 지도학습 기록이며, 실제 업무 장면은 사용자 확인이 필요하다."

    story = [
        "## 데이터 기반 가상 시뮬레이션",
        "",
        "> 아래 이야기는 컬럼명, 타깃, 그룹/시간 구조를 근거로 만든 **가설적 시뮬레이션**이다. 실제 업무 사실은 사용자 도메인 지식으로 확인해야 한다.",
        "",
        f"- 데이터 규모는 `{row_scope}`이고, 예측 대상은 `{labels.get(target, target)}`({target})이다.",
        f"- {scene}",
        f"- `{group_col}` 단위는 같은 공장/창고/시나리오/설비 흐름이 반복 측정된 묶음일 수 있으므로 검증 누수와 구조 일반화 확인에 중요하다.",
        f"- `{time_col}` 정보가 있거나 행 순서가 공정 순서라면 초반부/후반부, 피크 시간, 누적 병목, 설비 피로도 같은 흐름을 따로 보아야 한다.",
        f"- 수요·물량 신호 후보: {format_columns(demand_cols, labels)}",
        f"- 자원·설비·처리능력 후보: {format_columns(resource_cols, labels)}",
        f"- 혼잡·대기·동선 압력 후보: {format_columns(pressure_cols, labels)}",
        f"- 환경·온도·냉각 조건 후보: {format_columns(environment_cols, labels)}",
        f"- 레이아웃·구역·공간 구조 후보: {format_columns(layout_cols, labels)}",
        f"- 오류·품질·장애 후보: {format_columns(quality_cols, labels)}",
        "- `자동 후보 없음`은 현재 컬럼명/설명만으로 그 범주의 후보를 찾지 못했다는 뜻이다. 실제 도메인상 후보가 없다는 결론은 아니다.",
    ]
    return story


def build_process_questions(cfg: dict[str, Any], col_dict: pd.DataFrame, context: str) -> list[str]:
    labels = display_name_map(col_dict)
    demand_cols = columns_for(col_dict, {"demand_load"}, limit=5)
    resource_cols = columns_for(col_dict, {"capacity_resource"}, limit=5)
    pressure_cols = columns_for(col_dict, {"utilization_pressure"}, limit=5)
    quality_cols = columns_for(col_dict, {"error_quality"}, limit=5)
    layout_cols = columns_for(col_dict, {"location_layout", "group_segment"}, ["layout", "zone", "aisle", "rack"], limit=5)
    return [
        "## 제조업·공정 관점 질문",
        "",
        "- 질문: 이 데이터는 어떤 유형의 문제에 가장 가까운가? 예: 물류 운영, 예지보전, 공정품질최적화, 배출/에너지 예측, 일반 수요 예측.",
        "- 예상 답변: `공정품질최적화`, `예지보전`, `배출량 예측`, `운전 조건별 효율 예측`, `처리시간 예측` 중 가까운 것을 고르고 이유를 적는다.",
        f"- 질문: 부하/수요 후보({format_columns(demand_cols, labels)})가 커질 때 설비/자원 후보({format_columns(resource_cols, labels)})가 충분한가?",
        "- 예상 답변: `부하가 커질수록 타깃이 증가할 수 있음`, `제어/운영 여유를 봐야 함`, `자동 후보 없음이면 관련 컬럼을 직접 지정해야 함`.",
        f"- 질문: 병목/압력 후보({format_columns(pressure_cols, labels)})는 문제가 이미 발생한 결과인가, 문제를 미리 알려주는 선행 신호인가?",
        "- 예상 답변: `압력/병목 상승은 조건 변화의 선행 신호`, `결과 계측값은 사후 신호에 가까움`, `제어 위치는 행동 신호이므로 시점 확인 필요`.",
        f"- 질문: 품질/장애 후보({format_columns(quality_cols, labels)})는 실제 장애, 센서 누락, 제어 이벤트, 운전 상태 변화 중 무엇에 가까운가?",
        "- 예상 답변: `센서 교정 이슈`, `운전 전환 구간`, `정상 제어 반응`, `실제 설비 이상 가능성`.",
        f"- 질문: 그룹/구역 후보({format_columns(layout_cols, labels)})는 서로 다른 운전 모드나 설비 구간을 나누는 기준인가?",
        "- 예상 답변: `운전 모드별로 분리 필요`, `같은 설비의 연속 시간 데이터`, `구역/라인 구분 없음`.",
        "- EDA 제안: 부하 대비 용량 비율, 운전 모드별 타깃 평균, 시간 순서별 타깃 변화, 결측률이 높은 구간의 타깃 shift를 먼저 확인한다.",
    ]


def build_engineering_questions(cfg: dict[str, Any], col_dict: pd.DataFrame, context: str) -> list[str]:
    signals = detect_domain_signals(col_dict, cfg, context)
    labels = display_name_map(col_dict)
    environment_cols = columns_for(col_dict, {"environment"}, ["temp", "cold", "cool", "hvac", "heat"], limit=5)
    resource_cols = columns_for(col_dict, {"capacity_resource"}, ["motor", "power", "energy", "battery", "charger"], limit=5)
    motion_cols = columns_for(col_dict, {"utilization_pressure"}, ["route", "path", "distance", "travel", "queue"], limit=5)
    quality_cols = columns_for(col_dict, {"error_quality"}, ["fault", "wear", "vibration", "maintenance"], limit=5)
    basics = []
    if signals["thermal_cooling"]:
        basics.append("열전달/냉각부하: 온도 gap, 외기 유입, 문 개폐, 냉각 회복시간, HVAC 전력은 지연과 상호작용할 수 있다.")
    if signals["robotics_motion"]:
        basics.append("동역학/동선: 이동거리, 회전/교차로, 충전 대기, 배터리 부하는 로봇 처리 capacity를 줄일 수 있다.")
    if signals["manufacturing"] or signals["logistics"]:
        basics.append("공정공학: takt time, cycle time, WIP, throughput, utilization은 병목 위치를 찾는 기본 개념이다.")
    if signals["maintenance_quality"]:
        basics.append("신뢰성/정비: fault, vibration, wear 신호는 단기 이상치보다 설비 상태 변화의 누적 신호일 수 있다.")
    if not basics:
        basics.append("공학 지식이 필요한지 판단하려면 타깃 단위, 측정 장치, 물리적으로 불가능한 값, row 순서의 의미를 먼저 확인한다.")
    return [
        "## 기계공학 관점 질문",
        "",
        f"- 질문: 열·환경 후보({format_columns(environment_cols, labels)})는 타깃에 직접 영향을 주는 조건인가, 다른 작업량의 결과인가?",
        "- 예상 답변: `온도/환경 조건이 타깃에 직접 영향`, `냉각/희석 조건의 결과 신호`, `센서 위치 때문에 지연 반응 가능`.",
        f"- 질문: 출력/설비/자원 후보({format_columns(resource_cols, labels)})는 설비 부하 또는 제어 여유의 proxy로 쓸 수 있는가?",
        "- 예상 답변: `발전 출력은 부하 proxy`, `밸브 개도는 제어량`, `압축기 토출 압력은 운전 상태 proxy`.",
        f"- 질문: 비율·압력·대기 후보({format_columns(motion_cols, labels)})는 운전 제약이나 병목을 반영하는가?",
        "- 예상 답변: `노즐 압력비는 연소/분사 조건`, `매니폴드 차압은 공급 안정성`, `자동 후보 없음이면 직접 후보 지정`.",
        f"- 질문: 정비·품질 후보({format_columns(quality_cols, labels)})는 설비 피로, 센서 교정, 제어응답 문제와 연결되는가?",
        "- 예상 답변: `센서 캘리브레이션 확인`, `밸브 노후화 가능성`, `정상 운전 전환 구간으로 분리`.",
        "",
        "### 관련 기초 개념",
        "",
        *[f"- {item}" for item in basics],
    ]


def build_user_background_questions(cfg: dict[str, Any]) -> list[str]:
    profile = analyst_background(cfg)
    background = profile["background"]
    notes = profile["domain_notes"]
    experience = profile["experience_keywords"]
    interests = profile["interest_keywords"]
    focus = profile["first_report_focus"]
    return [
        "## 사용자 경험 활용 질문",
        "",
        f"- 분석가 배경: {', '.join(background) if background else 'config에 analyst_background를 입력하면 맞춤 질문을 강화할 수 있음'}",
        f"- 도메인 메모: {', '.join(notes) if notes else '아직 없음'}",
        f"- 경험 키워드: {', '.join(experience) if experience else '아직 없음'}",
        f"- 관심 키워드: {', '.join(interests) if interests else '아직 없음'}",
        f"- 1차 보고서 집중점: {', '.join(focus) if focus else '데이터 구조, 공정 상황, 공학적 피처 후보'}",
        "- 질문: 기계공학 전공 관점에서 부하-용량, 에너지, 열전달, 마찰/마모, 제어응답으로 설명 가능한 컬럼이 있는가?",
        "- 예상 답변: `발전 출력-연료 유량-배기가스 온도`, `압축기 토출 압력-토출 온도`, `밸브 개도-압력비`처럼 연결해 적는다.",
        "- 질문: 제조업/공정 경험 관점에서 실제 병목, 대기 지점, 설비 제약, 작업자 개입 지점은 어디인가?",
        "- 예상 답변: `기동/정지 전환`, `부하 급변`, `센서 교체/보정`, `밸브 제어 한계`, `촉매/반응기 온도 조건`.",
        "- 질문: 온도/냉각/환경 경험 관점에서 타깃에 영향을 줄 수 있는 열적 조건은 무엇인가?",
        "- 예상 답변: `입구 온도`, `배기가스 온도`, `SCR 반응기 온도`, `노점`, `냉각/희석 조건`.",
        "- 질문: 흐름/동선 관점에서 시간 순서, 피크 구간, 전환 구간, 병목 구간을 어떻게 나눌 수 있는가?",
        "- 예상 답변: `정상 운전`, `기동`, `정지`, `부하 상승`, `부하 하강`, `센서 결측 집중 구간`.",
    ]


def build_initial_hypotheses(cfg: dict[str, Any], col_dict: pd.DataFrame, context: str) -> list[str]:
    target = cfg["target_col"]
    labels = display_name_map(col_dict)
    load_cols = columns_for(col_dict, {"demand_load"}, limit=3)
    resource_cols = columns_for(col_dict, {"capacity_resource"}, limit=3)
    pressure_cols = columns_for(col_dict, {"utilization_pressure"}, limit=3)
    environment_cols = columns_for(col_dict, {"environment"}, ["temp", "cold", "cool", "hvac"], limit=3)
    layout_cols = columns_for(col_dict, {"location_layout", "group_segment"}, ["layout", "zone", "aisle", "rack"], limit=3)
    time_cols = columns_for(col_dict, keywords=["hour", "shift", "step", "seq", "phase", "date", "day", "period"], limit=3)
    rows = [
        {
            "가설": "수요가 capacity를 넘으면 타깃이 악화된다",
            "근거 컬럼": format_columns(load_cols + resource_cols, labels),
            "확인 EDA": "부하/용량 분위수별 타깃 평균, scatter/boxplot",
            "피처 후보": "load_capacity_ratio, utilization_gap",
            "주의점": "분모 0, 같은 의미 피처 중복",
        },
        {
            "가설": "대기·혼잡 신호는 병목의 선행 또는 결과 신호다",
            "근거 컬럼": format_columns(pressure_cols, labels),
            "확인 EDA": "혼잡 후보 상위 분위수의 타깃 shift",
            "피처 후보": "queue_pressure, wait_x_load",
            "주의점": "미래 지연을 직접 포함한 누수 여부 확인",
        },
        {
            "가설": "환경·냉각 조건이 처리 안정성을 바꾼다",
            "근거 컬럼": format_columns(environment_cols, labels),
            "확인 EDA": "온도/환경 bin별 타깃, 부하와의 interaction",
            "피처 후보": "temp_gap, cooling_load_proxy",
            "주의점": "비율만 있고 실제 물량이 없으면 규모 보완 필요",
        },
        {
            "가설": "레이아웃/구역별 공정 성격이 다르다",
            "근거 컬럼": format_columns(layout_cols, labels),
            "확인 EDA": "그룹/레이아웃별 타깃, train/test 분포 차이",
            "피처 후보": "layout_cluster, density_proxy, exit_access_proxy",
            "주의점": "ID 암기형 피처와 구조 일반화 구분",
        },
        {
            "가설": "시간 흐름 후반부에 누적 병목이 커진다",
            "근거 컬럼": format_columns(time_cols, labels),
            "확인 EDA": "row 순서/시간대별 타깃, 결측률, 잔차 변화",
            "피처 후보": "phase, lag, rolling, expanding, late_flag",
            "주의점": "그룹 밖 정보를 섞지 않도록 fold 내부 생성",
        },
    ]
    return [
        "## 초기 가설 → EDA/피처 후보",
        "",
        f"- 목표: `{labels.get(target, target)}`({target})를 설명할 수 있는 도메인 가설을 EDA와 피처 후보로 바로 연결한다.",
        "- 가설 문장은 보고서에서 길게 늘이지 않고, `무엇이 변하면 타깃이 어떻게 변할 것인가` 형태의 짧은 문장으로 유지한다.",
        "",
        markdown_table(pd.DataFrame(rows), max_rows=10),
    ]


def save_first_report_heatmap(matrix: pd.DataFrame, path: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    try:
        import seaborn as sns  # type: ignore
    except Exception:
        sns = None

    ensure_dir(path.parent)
    font_path = Path(__file__).resolve().parents[3] / "NanumGothic.ttf"
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9, 7))
    if sns is not None:
        sns.heatmap(matrix, cmap="RdBu_r", center=0.0, annot=True, fmt=".2f", ax=ax)
    else:
        image = ax.imshow(matrix.values, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
        ax.figure.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        ax.set_xticks(np.arange(len(matrix.columns)))
        ax.set_yticks(np.arange(len(matrix.index)))
        ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
        ax.set_yticklabels(matrix.index)
    ax.set_title("타깃과 주요 운전 변수의 상관관계")
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def first_report_correlation_bundle(train: pd.DataFrame, cfg: dict[str, Any], reports: Path, col_dict: pd.DataFrame | None = None) -> tuple[pd.DataFrame, Path]:
    target = cfg["target_col"]
    out_csv = reports / "dataset_review_target_correlations.csv"
    heatmap_path = reports / "dataset_review_correlation_heatmap.png"
    label_map = unique_label_map(col_dict) if col_dict is not None else {}
    desc_map = {}
    if col_dict is not None and "description" in col_dict.columns:
        desc_map = col_dict.set_index("column")["description"].to_dict()
    if target not in train.columns:
        empty = pd.DataFrame(columns=["feature_name_ko", "feature", "description", "corr_with_target", "abs_corr"])
        empty.to_csv(out_csv, index=False)
        return empty, heatmap_path

    numeric = train.select_dtypes(include=[np.number]).copy()
    if target not in numeric.columns:
        empty = pd.DataFrame(columns=["feature_name_ko", "feature", "description", "corr_with_target", "abs_corr"])
        empty.to_csv(out_csv, index=False)
        return empty, heatmap_path
    numeric = numeric.loc[:, numeric.nunique(dropna=True) > 1]
    if target not in numeric.columns:
        empty = pd.DataFrame(columns=["feature_name_ko", "feature", "description", "corr_with_target", "abs_corr"])
        empty.to_csv(out_csv, index=False)
        return empty, heatmap_path

    if len(numeric) > 50000:
        numeric = numeric.sample(50000, random_state=42)

    corr = numeric.corr(numeric_only=True)
    if target not in corr.columns:
        empty = pd.DataFrame(columns=["feature_name_ko", "feature", "description", "corr_with_target", "abs_corr"])
        empty.to_csv(out_csv, index=False)
        return empty, heatmap_path

    target_corr = corr[target].drop(labels=[target], errors="ignore").dropna()
    top_features = target_corr.abs().sort_values(ascending=False).head(12).index.tolist()
    summary = pd.DataFrame(
        {
            "feature_name_ko": [label_map.get(feature, feature) for feature in top_features],
            "feature": top_features,
            "description": [desc_map.get(feature, "") for feature in top_features],
            "corr_with_target": [float(target_corr.loc[feature]) for feature in top_features],
        }
    )
    summary["abs_corr"] = summary["corr_with_target"].abs()
    summary.to_csv(out_csv, index=False)

    if top_features:
        matrix_cols = [target] + top_features
        matrix = corr.loc[matrix_cols, matrix_cols].round(4)
        matrix = matrix.rename(index=label_map, columns=label_map)
        save_first_report_heatmap(matrix, heatmap_path)
    return summary, heatmap_path


def write_dataset_review(
    path: Path,
    cfg: dict[str, Any],
    train: pd.DataFrame,
    test: pd.DataFrame | None,
    col_dict: pd.DataFrame,
    context: str,
    corr_summary: pd.DataFrame,
    heatmap_path: Path,
) -> None:
    target = cfg["target_col"]
    labels = display_name_map(col_dict)
    target_row = col_dict[col_dict["column"] == target]
    group_counts = col_dict["semantic_group"].value_counts().reset_index()
    group_counts.columns = ["semantic_group", "columns"]
    lines = [
        "# 데이터셋 리뷰",
        "",
        f"- 작업 유형: `{cfg['task_type']}`",
        f"- 타깃 컬럼: `{labels.get(target, target)}`({target})",
        f"- Train 크기: `{train.shape}`",
        f"- Test 크기: `{test.shape if test is not None else '미제공'}`",
        f"- ID 컬럼: `{choose_id_col(cfg, train, test)}`",
        f"- 그룹 컬럼: `{cfg.get('group_col') or '미설정'}`",
        f"- 시간 컬럼: `{cfg.get('time_col') or '미설정'}`",
        "",
        "## 데이터/상황 추정",
        "",
        context,
        "",
        "이 추정은 컬럼명, 컬럼 설명, config 기반 초안이다. 사용자의 제조업·공정·공학 경험을 반영해 실제 업무 맥락을 보정한 뒤 EDA와 피처 설계로 이어간다.",
        "",
        "## 타깃 요약",
        "",
    ]
    if not target_row.empty:
        row = target_row.iloc[0].to_dict()
        for key in ["dtype_train", "missing_rate_train", "mean", "std", "min", "median", "p99", "max", "skewness"]:
            lines.append(f"- {key}: `{row.get(key)}`")
    if not corr_summary.empty:
        corr_cols = [c for c in ["feature_name_ko", "feature", "description", "corr_with_target", "abs_corr"] if c in corr_summary.columns]
        lines += [
            "",
            "## 타깃과의 주요 관계",
            "",
            f"- Heatmap: `{heatmap_path.name}`",
            "- 아래 표와 시각화는 원문 태그명보다 사용자가 의미를 바로 이해할 수 있는 한국어 의미명을 우선 표시한다.",
            "",
            markdown_table(corr_summary[corr_cols], max_rows=12),
        ]
    lines += [
        "",
        "## 컬럼 그룹",
        "",
        markdown_table(group_counts),
        "",
        "## 실무적 해석",
        "",
        "- 수요/유입 컬럼은 공정에 들어오는 압력을 설명한다.",
        "- 자원/용량 컬럼은 공정이 흡수할 수 있는 처리 능력을 설명한다.",
        "- 가동률/대기열/오류/품질 컬럼은 병목, 결측, 이상치의 원인을 설명하는 경우가 많다.",
        "- ID/그룹/시간(순서) 컬럼은 검증 누수를 피하기 위해 특히 주의해서 다룬다.",
        "- `자동 후보 없음`은 현재 자동 분류기가 해당 범주의 후보를 찾지 못했다는 뜻이다. 도메인 지식상 후보가 있다면 `domain_answers.md`에 직접 적는다.",
        "",
        *build_simulation_story(cfg, train, test, col_dict, context),
        "",
        *build_process_questions(cfg, col_dict, context),
        "",
        *build_engineering_questions(cfg, col_dict, context),
        "",
        *build_user_background_questions(cfg),
        "",
        *build_initial_hypotheses(cfg, col_dict, context),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_data_review(config_path: str | Path, run_id: str) -> None:
    from manual_domain_expert import write_questionnaire_files
    from manual_report_payloads import write_stage_markdown, write_stage_payload
    from manual_state import refresh_run_state

    cfg = load_config(config_path)
    paths = run_paths(cfg, run_id)
    train, test, sample = load_modeling_data(cfg)
    if cfg["target_col"] not in train.columns:
        raise ValueError(f"Target `{cfg['target_col']}` is not in train data.")
    id_col = choose_id_col(cfg, train, test)
    train = ensure_id_column(train, id_col)
    test = ensure_id_column(test, id_col) if test is not None else None
    col_dict = column_stats(train, test, cfg)
    context = infer_dataset_context(col_dict, cfg)
    reports = paths["reports"]
    col_dict.to_csv(reports / "column_dictionary.csv", index=False)
    overview = {
        "task_type": cfg["task_type"],
        "target_col": cfg["target_col"],
        "id_col": id_col,
        "group_col": cfg.get("group_col"),
        "time_col": cfg.get("time_col"),
        "train_shape": list(train.shape),
        "test_shape": list(test.shape) if test is not None else None,
        "sample_submission_shape": list(sample.shape) if sample is not None else None,
        "semantic_group_counts": col_dict["semantic_group"].value_counts().to_dict(),
        "inferred_context": context,
        "domain_signal_flags": detect_domain_signals(col_dict, cfg, context),
        "analyst_background": analyst_background(cfg),
        "train_not_test": sorted(set(train.columns) - set(test.columns)) if test is not None else [],
        "test_not_train": sorted(set(test.columns) - set(train.columns)) if test is not None else [],
    }
    write_json(reports / "data_overview.json", overview)
    corr_summary, heatmap_path = first_report_correlation_bundle(train, cfg, reports, col_dict)
    write_dataset_review(reports / "dataset_review.md", cfg, train, test, col_dict, context, corr_summary, heatmap_path)
    write_questionnaire_files(cfg, run_id, paths)
    append_decision(
        cfg,
        run_id,
        "00_data_review",
        "target_and_task",
        f"{cfg['target_col']} / {cfg['task_type']}",
        "config required",
        "The Manual workflow treats target and task type as explicit config values to prevent silent target mistakes.",
        "All downstream diagnostics, validation, models, metrics, and submission columns use this choice.",
    )
    payload = write_stage_payload("00", cfg, paths)
    write_stage_markdown("00", payload, paths)
    append_stage_log(
        cfg,
        "00 data review",
        "Review dataset schema, target, context, and initial correlations",
        [str(config_path), str(resolve_project_path(cfg, cfg.get("train_path")))],
        [str(reports / "dataset_review.md"), str(reports / "data_overview.json"), str(reports / "column_dictionary.csv")],
        checkpoint="Stage 01 KPI/purpose confirmation",
        next_step="Confirm the target KPI and prediction purpose before environment check.",
    )
    refresh_run_state(cfg, run_id)
    print(f"Wrote data review outputs to {reports}")


def installed_version(module_name: str) -> str | None:
    if importlib.util.find_spec(module_name) is None:
        return None
    try:
        module = __import__(module_name)
        return str(getattr(module, "__version__", "installed"))
    except Exception:
        return "installed"


def run_env_check(config_path: str | Path, run_id: str) -> None:
    from manual_report_payloads import write_stage_markdown, write_stage_payload
    from manual_state import refresh_run_state

    cfg = load_config(config_path)
    paths = run_paths(cfg, run_id)
    files = {
        "train_path": resolve_project_path(cfg, cfg.get("train_path")),
        "test_path": resolve_project_path(cfg, cfg.get("test_path")),
        "sample_submission_path": resolve_project_path(cfg, cfg.get("sample_submission_path")),
    }
    for meta in cfg.get("metadata_paths", []) or []:
        files[f"metadata:{meta.get('name') or meta.get('path')}"] = resolve_project_path(cfg, meta.get("path"))
    file_status = {k: {"path": str(v) if v else "", "exists": bool(v and v.exists())} for k, v in files.items()}
    packages = {pkg: installed_version(pkg) for pkg in DEFAULT_PACKAGES}
    status = {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "file_status": file_status,
        "packages": packages,
        "missing_packages": [pkg for pkg, version in packages.items() if version is None],
        "ready": bool(file_status["train_path"]["exists"]) and all(v is not None for v in packages.values()),
    }
    write_json(paths["reports"] / "env_check.json", status)
    lines = ["# 환경 점검", "", f"- Python: `{status['python_version']}`", f"- 실행 파일: `{status['python_executable']}`", ""]
    lines.append("## 파일")
    for name, item in file_status.items():
        lines.append(f"- `{name}`: {item['exists']} ({item['path']})")
    lines += ["", "## 패키지"]
    for pkg, version in packages.items():
        lines.append(f"- `{pkg}`: {version or 'missing'}")
    (paths["reports"] / "env_check.md").write_text("\n".join(lines), encoding="utf-8")
    payload = write_stage_payload("01", cfg, paths)
    write_stage_markdown("01", payload, paths)
    append_stage_log(
        cfg,
        "01 env check",
        "Check input files and required Python packages",
        [str(config_path)],
        [str(paths["reports"] / "env_check.md"), str(paths["reports"] / "env_check.json")],
        checkpoint="Stage 02 diagnostics",
        next_step="Run missing/outlier diagnostics and statistical probe.",
    )
    refresh_run_state(cfg, run_id)
    print(f"환경 점검 산출물 생성 완료: {paths['reports']}")


def concentration_ratio(df: pd.DataFrame, mask: pd.Series, group_col: str | None) -> float:
    if not group_col or group_col not in df.columns or not mask.any():
        return 1.0
    base = float(mask.mean())
    if base <= 0:
        return 1.0
    grouped = mask.groupby(df[group_col], sort=False).mean()
    return float(grouped.max() / base) if len(grouped) else 1.0


def top_related_numeric(df: pd.DataFrame, indicator: pd.Series, exclude: set[str], n: int = 5) -> str:
    if indicator.nunique(dropna=False) <= 1:
        return ""
    num_cols = numeric_columns(df, exclude)
    sample_idx = df.sample(60000, random_state=42).index if len(df) > 60000 else df.index
    ind = indicator.loc[sample_idx].astype(float)
    values = {}
    for col in num_cols:
        s = pd.to_numeric(df.loc[sample_idx, col], errors="coerce")
        if s.notna().sum() < 3 or s.nunique(dropna=True) <= 1:
            continue
        corr = safe_corr(ind, s)
        if pd.notna(corr):
            values[col] = abs(float(corr))
    return ";".join(f"{k}:{v:.3f}" for k, v in sorted(values.items(), key=lambda item: item[1], reverse=True)[:n])


def target_shift_label(shift: float, base: float) -> str:
    if pd.isna(shift):
        return "target_unavailable"
    if abs(shift) <= max(abs(base), 1.0) * 0.03:
        return "weak"
    return "target_higher_when_missing" if shift > 0 else "target_lower_when_missing"


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    paired = pd.concat(
        [
            pd.to_numeric(left, errors="coerce").rename("left"),
            pd.to_numeric(right, errors="coerce").rename("right"),
        ],
        axis=1,
    ).dropna()
    if len(paired) < 3:
        return float("nan")
    if paired["left"].nunique(dropna=True) <= 1 or paired["right"].nunique(dropna=True) <= 1:
        return float("nan")
    return float(paired["left"].corr(paired["right"]))


def empirical_cdf_gap(train_s: pd.Series, test_s: pd.Series) -> float:
    train_arr = np.sort(pd.to_numeric(train_s, errors="coerce").dropna().to_numpy(dtype=float))
    test_arr = np.sort(pd.to_numeric(test_s, errors="coerce").dropna().to_numpy(dtype=float))
    if len(train_arr) < 3 or len(test_arr) < 3:
        return float("nan")
    merged = np.sort(np.unique(np.concatenate([train_arr, test_arr])))
    if len(merged) == 0:
        return float("nan")
    train_cdf = np.searchsorted(train_arr, merged, side="right") / len(train_arr)
    test_cdf = np.searchsorted(test_arr, merged, side="right") / len(test_arr)
    return float(np.max(np.abs(train_cdf - test_cdf)))


def distribution_shift_summary(train: pd.DataFrame, test: pd.DataFrame | None, cfg: dict[str, Any], col_dict: pd.DataFrame) -> pd.DataFrame:
    if test is None or test.empty:
        return pd.DataFrame(
            columns=[
                "feature",
                "semantic_group",
                "train_non_null",
                "test_non_null",
                "approx_ks_gap",
                "median_gap_std",
                "mean_gap_std",
                "status",
                "note",
            ]
        )
    semantic_map = col_dict.set_index("column")["semantic_group"].to_dict() if not col_dict.empty and "column" in col_dict.columns else {}
    excluded = {cfg.get("target_col"), cfg.get("id_col"), cfg.get("group_col"), cfg.get("time_col"), None}
    rows = []
    for col in numeric_columns(train, excluded):
        if col not in test.columns:
            continue
        train_s = pd.to_numeric(train[col], errors="coerce")
        test_s = pd.to_numeric(test[col], errors="coerce")
        train_non_null = int(train_s.notna().sum())
        test_non_null = int(test_s.notna().sum())
        if train_non_null < 3 or test_non_null < 3:
            continue
        train_std = float(train_s.std(skipna=True)) if train_non_null else 0.0
        test_std = float(test_s.std(skipna=True)) if test_non_null else 0.0
        constant = train_s.nunique(dropna=True) <= 1 or test_s.nunique(dropna=True) <= 1 or max(train_std, test_std) < 1e-9
        ks_gap = empirical_cdf_gap(train_s, test_s)
        scale = max(train_std, test_std, 1e-9)
        median_gap_std = abs(float(train_s.median(skipna=True)) - float(test_s.median(skipna=True))) / scale
        mean_gap_std = abs(float(train_s.mean(skipna=True)) - float(test_s.mean(skipna=True))) / scale
        if constant:
            status = "constant_or_low_variance"
            note = "한쪽 또는 양쪽 데이터에서 분산이 거의 없어 상관/검정 해석이 제한됩니다."
        elif (pd.notna(ks_gap) and ks_gap >= 0.3) or median_gap_std >= 1.0 or mean_gap_std >= 1.0:
            status = "drift_candidate"
            note = "train/test 분포 차이가 커서 검증 또는 피처 해석 시 주의가 필요합니다."
        else:
            status = "stable_or_mild"
            note = "큰 분포 차이는 아직 감지되지 않았습니다."
        rows.append(
            {
                "feature": col,
                "semantic_group": semantic_map.get(col, infer_semantic_group(col)),
                "train_non_null": train_non_null,
                "test_non_null": test_non_null,
                "approx_ks_gap": round(float(ks_gap), 6) if pd.notna(ks_gap) else np.nan,
                "median_gap_std": round(float(median_gap_std), 6),
                "mean_gap_std": round(float(mean_gap_std), 6),
                "status": status,
                "note": note,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["status", "approx_ks_gap", "median_gap_std", "mean_gap_std"], ascending=[True, False, False, False])


def missing_hypotheses(train: pd.DataFrame, test: pd.DataFrame | None, cfg: dict[str, Any], col_dict: pd.DataFrame) -> pd.DataFrame:
    target = cfg["target_col"]
    task = cfg["task_type"]
    group_col = cfg.get("group_col")
    y = train[target]
    base_target = float(pd.to_numeric(y, errors="coerce").mean()) if task == "regression" else float(y.astype("category").cat.codes.mean())
    semantic_map = col_dict.set_index("column")["semantic_group"].to_dict()
    rows = []
    for col in [c for c in train.columns if c != target]:
        mask = train[col].isna()
        test_rate = float(test[col].isna().mean()) if test is not None and col in test.columns else np.nan
        train_rate = float(mask.mean())
        if train_rate == 0 and (pd.isna(test_rate) or test_rate == 0):
            continue
        semantic = semantic_map.get(col, infer_semantic_group(col))
        if task == "regression" and mask.any():
            target_shift = float(pd.to_numeric(train.loc[mask, target], errors="coerce").mean() - base_target)
        elif mask.any():
            target_shift = float(train.loc[mask, target].astype("category").cat.codes.mean() - base_target)
        else:
            target_shift = 0.0
        related = top_related_numeric(train, mask, {col, target})
        group_ratio = concentration_ratio(train, mask, group_col)
        drift_gap = abs((test_rate if not pd.isna(test_rate) else train_rate) - train_rate)
        zero_hint = False
        lower = col.lower()
        if any(k in lower for k in ["avg", "mean", "wait", "recovery", "duration", "time"]):
            related_cols = [c for c in train.columns if c != col and any(k in c.lower() for k in ["count", "queue", "flag", "event", "fault", "error"])]
            for rcol in related_cols[:20]:
                values = pd.to_numeric(train.loc[mask, rcol], errors="coerce")
                if len(values) and values.notna().any() and float((values.fillna(0) == 0).mean()) >= 0.75:
                    zero_hint = True
                    break
        if zero_hint:
            hypothesis = "조건부 결측: 관련 이벤트가 없을 때 측정값이 정의되지 않을 수 있다."
            handling = "zero_plus_missing_indicator"
            confidence = 0.82
            data_evidence = "결측 행에서 관련 이벤트/카운트 후보가 0에 집중된다."
            domain_evidence = "이벤트가 발생할 때만 기록되는 센서·작업·품질 변수일 수 있다."
        elif drift_gap >= 0.03:
            hypothesis = "수집 구간 차이 결측: train/test 결측률이 다르다."
            handling = "median_plus_missing_indicator_and_drift_check"
            confidence = min(0.9, 0.55 + drift_gap * 5)
            data_evidence = f"train/test 결측률 차이가 {drift_gap * 100:.3f}%p로 관찰된다."
            domain_evidence = "운전 기간, 센서 교체, 수집 시스템 변경 가능성을 확인해야 한다."
        elif group_ratio >= 3.0:
            hypothesis = "세그먼트 집중 결측: 특정 그룹/운전 구간에 결측이 몰린다."
            handling = "group_median_plus_missing_indicator"
            confidence = min(0.9, 0.55 + group_ratio / 10)
            data_evidence = f"결측 집중 비율이 {group_ratio:.3f}로 높다."
            domain_evidence = "특정 운전 모드, 설비 상태, 시간대에서만 값이 빠지는지 확인해야 한다."
        elif semantic in {"environment", "error_quality"}:
            hypothesis = "센서/품질 기록 결측: 계측 또는 이벤트 기록 변수로 보인다."
            handling = "median_plus_missing_indicator"
            confidence = 0.66
            data_evidence = f"semantic_group={semantic} 변수에서 결측이 관찰된다."
            domain_evidence = "센서 통신, 보정, 운전 전환, 품질 이벤트 기록 누락 가능성이 있다."
        elif target_shift_label(target_shift, base_target) != "weak":
            hypothesis = "타깃 연동 결측: 결측 여부 자체가 결과와 관련될 수 있다."
            handling = "median_plus_missing_indicator"
            confidence = 0.7
            data_evidence = f"결측 시 타깃 평균 변화가 {target_shift:.6f}로 관찰된다."
            domain_evidence = "값이 빠지는 운전 상태가 결과 악화/개선과 연결되는지 확인해야 한다."
        else:
            hypothesis = "무작위 결측 후보: 강한 조건부/세그먼트/타깃 연동 신호가 약하다."
            handling = "median_impute_indicator_optional"
            confidence = 0.52
            data_evidence = "결측률 차이, 세그먼트 집중, 타깃 변화 신호가 강하지 않다."
            domain_evidence = "특별한 계측/운전 이유가 없다면 중앙값 대체부터 비교한다."
        rows.append(
            {
                "feature": col,
                "semantic_group": semantic,
                "missing_rate_train": round(train_rate * 100, 4),
                "missing_rate_test": round(test_rate * 100, 4) if not pd.isna(test_rate) else np.nan,
                "train_test_missing_gap": round(drift_gap * 100, 4) if not pd.isna(drift_gap) else np.nan,
                "segment_concentration_ratio": round(group_ratio, 5),
                "target_shift_when_missing": round(target_shift, 6),
                "target_shift_label": target_shift_label(target_shift, base_target),
                "top_related_features": related,
                "hypothesis": hypothesis,
                "data_evidence": data_evidence,
                "domain_evidence": domain_evidence,
                "recommended_handling": handling,
                "confidence": round(float(confidence), 4),
            }
        )
    cols = [
        "feature",
        "semantic_group",
        "missing_rate_train",
        "missing_rate_test",
        "train_test_missing_gap",
        "segment_concentration_ratio",
        "target_shift_when_missing",
        "target_shift_label",
        "top_related_features",
        "hypothesis",
        "data_evidence",
        "domain_evidence",
        "recommended_handling",
        "confidence",
    ]
    return pd.DataFrame(rows, columns=cols).sort_values(["missing_rate_train", "missing_rate_test"], ascending=False)


def target_outlier_summary(train: pd.DataFrame, cfg: dict[str, Any], col_dict: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    target = cfg["target_col"]
    task = cfg["task_type"]
    if task == "classification":
        counts = train[target].value_counts(dropna=False)
        summary = {
            "task_type": task,
            "class_counts": {str(k): int(v) for k, v in counts.items()},
            "minority_class_rate": round(float(counts.min() / counts.sum()), 6) if counts.sum() else np.nan,
            "judgment": "Classification target: inspect class imbalance rather than numeric outliers.",
            "recommended_target_handling": "Use stratified validation if no group column exists; consider class weights for severe imbalance.",
        }
        return summary, pd.DataFrame(), pd.DataFrame()
    y = pd.to_numeric(train[target], errors="coerce").dropna()
    q = {
        "min": float(y.min()),
        "p01": float(y.quantile(0.01)),
        "p05": float(y.quantile(0.05)),
        "p25": float(y.quantile(0.25)),
        "median": float(y.quantile(0.5)),
        "p75": float(y.quantile(0.75)),
        "p95": float(y.quantile(0.95)),
        "p99": float(y.quantile(0.99)),
        "p995": float(y.quantile(0.995)),
        "p999": float(y.quantile(0.999)),
        "max": float(y.max()),
        "mean": float(y.mean()),
    }
    iqr = q["p75"] - q["p25"]
    iqr_upper = q["p75"] + 1.5 * iqr
    mad = float(np.median(np.abs(y - q["median"])))
    robust_z = 0.6745 * (y - q["median"]) / max(mad, 1e-9)
    skewness = float(y.skew())
    top_mask = train[target] >= q["p99"]
    id_cols = {cfg.get("id_col"), cfg.get("group_col"), cfg.get("time_col"), target, None}
    candidates = [c for c in numeric_columns(train, id_cols) if c in col_dict["column"].values]
    sample = train.sample(80000, random_state=42) if len(train) > 80000 else train
    evidence_rows = []
    y_sample = pd.to_numeric(sample[target], errors="coerce")
    semantic_map = col_dict.set_index("column")["semantic_group"].to_dict()
    for col in candidates:
        s = pd.to_numeric(sample[col], errors="coerce")
        if s.notna().sum() < 10 or s.nunique(dropna=True) <= 1:
            continue
        corr = safe_corr(s, y_sample)
        top_mean = float(pd.to_numeric(train.loc[top_mask, col], errors="coerce").mean()) if top_mask.any() else np.nan
        rest_mean = float(pd.to_numeric(train.loc[~top_mask, col], errors="coerce").mean()) if (~top_mask).any() else np.nan
        evidence_rows.append(
            {
                "feature": col,
                "semantic_group": semantic_map.get(col, infer_semantic_group(col)),
                "corr_with_target": round(float(corr), 6) if pd.notna(corr) else np.nan,
                "top_1pct_mean": round(top_mean, 6) if pd.notna(top_mean) else np.nan,
                "rest_mean": round(rest_mean, 6) if pd.notna(rest_mean) else np.nan,
                "top_vs_rest_diff": round(top_mean - rest_mean, 6) if pd.notna(top_mean) and pd.notna(rest_mean) else np.nan,
            }
        )
    evidence = pd.DataFrame(evidence_rows)
    if not evidence.empty:
        evidence["abs_corr"] = evidence["corr_with_target"].abs()
        evidence = evidence.sort_values(["abs_corr", "top_vs_rest_diff"], ascending=False).drop(columns=["abs_corr"])
    signal_groups = {"demand_load", "capacity_resource", "utilization_pressure", "error_quality"}
    support = evidence.head(15)
    signal_support = float(support["semantic_group"].isin(signal_groups).mean()) if not support.empty else 0.0
    group_conc = concentration_ratio(train, top_mask, cfg.get("group_col"))
    p99_median_ratio = q["p99"] / max(q["median"], 1e-9)
    target_is_non_negative = bool(q["min"] >= 0)
    positive_target = bool(cfg.get("positive_target") or target_is_non_negative)
    transform_policy = str(cfg.get("target_transform_policy", "eda_auto")).lower()
    recommend_log_candidate = bool(positive_target and (skewness > 1.5 or p99_median_ratio > 5))
    if transform_policy in {"raw_only", "raw"}:
        recommend_log_candidate = False
    elif transform_policy in {"force_compare", "both"}:
        recommend_log_candidate = bool(positive_target)
    natural_score = min(1.0, 0.45 * signal_support + 0.25 * min(abs(skewness) / 5, 1) + 0.2 * min(group_conc / 4, 1) + 0.1 * min(p99_median_ratio / 8, 1))
    if natural_score >= 0.6:
        judgment = "실제 희귀 운전/병목 이상치 가능성이 높다."
        target_handling = "검증 성능을 확인하며 robust 학습 또는 보수적 clipping을 비교한다."
    elif natural_score >= 0.35:
        judgment = "실제 운전 변화와 측정 노이즈가 섞인 이상치 가능성이 있다."
        target_handling = "raw/log target, 이상치 flag, p99.5-p99.9 clipping을 검증에서 비교한다."
    else:
        judgment = "입력/단위/조인/측정 노이즈 이상치 가능성이 있다."
        target_handling = "도메인 확인 후 winsorization 또는 상한 clipping을 검증한다."
        
    try:
        from sklearn.ensemble import IsolationForest
        if_cols = [c for c in numeric_columns(train, id_cols) if pd.api.types.is_numeric_dtype(train[c])]
        if if_cols:
            clf = IsolationForest(contamination=0.01, random_state=42)
            sample_if = train[if_cols].fillna(0).sample(min(len(train), 10000), random_state=42)
            preds = clf.fit_predict(sample_if)
            outlier_ratio = float((preds == -1).mean())
            judgment += f" [IsolationForest Anomaly Ratio: {outlier_ratio:.3f}]"
    except Exception:
        pass

    outlier_hypotheses = pd.DataFrame(
        [
            {
                "target_col": target,
                "hypothesis": "희귀 운전/병목 이벤트",
                "data_evidence": "상위 타깃 값이 부하, 가동률, 자원, 오류 후보와 함께 움직이는지 확인한다.",
                "domain_evidence": "기동/정지, 부하 급변, 제어 한계, 설비 이상 같은 실제 운전 이벤트일 수 있다.",
                "support_score": round(natural_score, 4),
                "recommended_handling": target_handling,
            },
            {
                "target_col": target,
                "hypothesis": "측정/단위/조인/라벨 노이즈",
                "data_evidence": "robust z-score가 크지만 설명 변수 신호가 약하면 의심한다.",
                "domain_evidence": "센서 보정, 단위 변환, 수집/결합 오류 가능성을 확인한다.",
                "support_score": round(1 - natural_score, 4),
                "recommended_handling": "샘플 행을 확인하고 clipping/winsorization을 검증에서 비교한다.",
            },
            {
                "target_col": target,
                "hypothesis": "특정 운전 모드",
                "data_evidence": f"상위 이상치의 그룹 집중 비율은 {group_conc:.3f}이다.",
                "domain_evidence": "특정 운전 모드, 설비 상태, 시간대에서만 발생하는지 확인한다.",
                "support_score": round(min(group_conc / 4, 1), 4),
                "recommended_handling": "그룹/세그먼트 검증과 운전 모드 interaction 피처를 검토한다.",
            },
        ]
    )
    summary = {
        "task_type": task,
        "quantiles": {k: round(v, 6) for k, v in q.items()},
        "iqr_upper": round(float(iqr_upper), 6),
        "robust_z_max": round(float(np.nanmax(np.abs(robust_z))), 6),
        "skewness": round(skewness, 6),
        "p99_median_ratio": round(float(p99_median_ratio), 6),
        "target_is_non_negative": target_is_non_negative,
        "top_1pct_threshold": round(q["p99"], 6),
        "group_concentration_ratio": round(group_conc, 6),
        "natural_outlier_score": round(natural_score, 6),
        "judgment": judgment,
        "recommended_target_handling": target_handling,
        "clip_recommendation": "Compare p99.5-p99.9 clipping if validation improves.",
        "target_transform_screening": {
            "stage": "EDA/profiler",
            "policy": transform_policy,
            "default_model_target": "raw",
            "recommend_log1p_candidate": recommend_log_candidate,
            "reason": "Positive/non-negative target with high skewness or p99/median ratio." if recommend_log_candidate else "Target shape does not require log1p as a default modeling branch.",
            "model_stage_action": "Compare raw and log1p only because EDA flagged the target shape." if recommend_log_candidate else "Use raw target unless the user explicitly requests transform comparison.",
        },
        "log_target_recommendation": "EDA flagged log1p as a candidate transform; compare in model stage only if this recommendation is accepted." if recommend_log_candidate else "EDA did not flag log1p as a default candidate; raw target is the default.",
    }
    return summary, outlier_hypotheses, evidence


def write_domain_questions(path: Path, cfg: dict[str, Any], missing_df: pd.DataFrame, outlier_summary: dict[str, Any]) -> None:
    lines = [
        "# 도메인 인사이트 질문",
        "",
        "전처리/피처 엔지니어링 결정을 고정하기 전에 아래 질문을 확인한다.",
        "",
        "`자동 후보 없음`은 자동 분류기가 후보를 찾지 못했다는 뜻이다. 실제 도메인 후보가 있다면 사용자가 직접 적어도 된다.",
        "",
        "## 타깃/이상치",
        "",
        f"- `{cfg['target_col']}`의 상위 꼬리(극단값)가 운영상 자연스럽게 발생할 수 있는가?",
        "  예상 답변: `부하 급변이면 가능`, `센서 오류 가능`, `기동/정지 구간이면 따로 봐야 함`, `환경 기준 초과라면 놓치면 안 됨`.",
        "- 타깃이 0 또는 음수가 물리적으로 가능한가?",
        "  예상 답변: `타깃은 음수 불가`, `센서 보정 전 값은 0 근처 가능`, `결측/오류는 별도 표시 필요`.",
        "- 타깃이 양수/0 이상이고 긴 꼬리라면 `log1p` 변환이 의미 있는 단위인가?",
        "  예상 답변: `비율 오차 해석이면 의미 있음`, `절대 ppm 오차가 중요하면 raw 유지`, `둘 다 검증 비교`.",
        "- 평가 지표가 MAE/RMSE 중 무엇이며, log 변환이 그 지표에 어떤 trade-off를 만들 수 있는가?",
        "  예상 답변: `초과 배출을 크게 벌점 주려면 RMSE`, `일반적인 평균 오차는 MAE`, `기준치 초과 recall도 별도 확인`.",
        "- 극단값은 실제 희귀 이벤트/병목, 지연 보고, 단위 오류, 조인 오류, 합성 노이즈 중 무엇일 가능성이 큰가?",
        "  예상 답변: `실제 부하 급변`, `센서 스파이크`, `정지/기동 전환`, `단위 변환 오류`.",
        "- 진짜 극단 지연이라면 사전에 함께 상승해야 할 부하/용량/오류/운영 지표는 무엇인가?",
        "  예상 답변: `발전 출력`, `연료 유량`, `SCR 온도`, `밸브 개도`, `압축기 토출 조건`.",
        "",
        "## 결측값",
        "",
        "- 이벤트가 있을 때만 관측되는 조건부 변수는 무엇인가?",
        "  예상 답변: `정지/기동 이벤트`, `밸브 동작 시점`, `센서가 활성화되는 운전 모드`.",
        "- 빈칸이 '0'을 의미해야 하는 변수는 무엇인가?",
        "  예상 답변: `유량 없음`, `장비 미동작`, `이벤트 없음`은 0일 수 있지만 센서 미수집과 구분 필요.",
        "- 센서/IT/수기 입력 시스템이 site/shift/line/scenario별로 실패하는 패턴이 있는가?",
        "  예상 답변: `특정 시간대 결측`, `센서 교체일`, `운전 모드 전환 직후`, `데이터 수집 시스템 중단`.",
        "- train/test 결측 패턴 차이는 공정 변화인가, 수집 아티팩트인가?",
        "  예상 답변: `운전 기간 차이`, `정비 이후 센서 정상화`, `수집 정책 변경`, `단순 파일 병합 문제`.",
        "",
        "## 피처 엔지니어링",
        "",
        "- 핵심 병목은 무엇인가: 수요 과부하, 용량 부족, 설비/자원 상태, 품질 이벤트, IT/센서 지연, 레이아웃/사이트, 인력?",
        "  예상 답변: `출력 대비 연료/질소 주입`, `온도 조건`, `압력비`, `밸브 개도`, `센서 결측/보정 상태`.",
        "- row 순서는 실제 시간인가, 시뮬레이션/정렬 인덱스인가?",
        "  예상 답변: `TagName이 실제 1초 간격 시간`, `정렬된 로그`, `구간별 연속성 확인 필요`.",
        "- 안전한 그룹 변수와 누수 가능성이 큰 식별자는 무엇인가?",
        "  예상 답변: `시간은 순서 피처로 가능하지만 미래 rolling 주의`, `타깃 이후 측정값은 누수`, `단순 ID는 모델 입력 제외`.",
    ]
    if not missing_df.empty:
        lines += ["", "## 우선순위 높은 결측 컬럼", ""]
        for _, row in missing_df.head(10).iterrows():
            lines.append(f"- `{row['feature']}`: {row['hypothesis']} | 권장: `{row['recommended_handling']}`")
    lines += ["", "## 현재 이상치 판단", "", f"- {outlier_summary.get('judgment', 'unknown')}"]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_profiler_diagnoser(config_path: str | Path, run_id: str) -> None:
    from manual_domain_expert import domain_treatment_candidates_from_pack, load_domain_context_pack
    from manual_report_payloads import write_stage_markdown, write_stage_payload
    from manual_state import refresh_run_state

    cfg = load_config(config_path)
    paths = run_paths(cfg, run_id)
    train, test, _ = load_modeling_data(cfg)
    id_col = choose_id_col(cfg, train, test)
    train = ensure_id_column(train, id_col)
    test = ensure_id_column(test, id_col) if test is not None else None
    col_path = paths["reports"] / "column_dictionary.csv"
    col_dict = pd.read_csv(col_path) if col_path.exists() else column_stats(train, test, cfg)
    missing_df = missing_hypotheses(train, test, cfg, col_dict)
    missing_df.to_csv(paths["reports"] / "missing_reason_hypotheses.csv", index=False)
    drift_df = distribution_shift_summary(train, test, cfg, col_dict)
    drift_df.to_csv(paths["reports"] / "feature_drift_summary.csv", index=False)
    outlier_summary, outlier_h, evidence = target_outlier_summary(train, cfg, col_dict)
    write_json(paths["reports"] / "target_outlier_summary.json", outlier_summary)
    outlier_h.to_csv(paths["reports"] / "target_outlier_hypotheses.csv", index=False)
    evidence.to_csv(paths["reports"] / "target_outlier_evidence.csv", index=False)
    treatments = [{"kind": "missing", "feature": row["feature"], "recommendation": row["recommended_handling"], "reason": row["hypothesis"]} for _, row in missing_df.iterrows()]
    treatments.append({"kind": "target_outlier", "feature": cfg["target_col"], "recommendation": outlier_summary.get("recommended_target_handling", ""), "reason": outlier_summary.get("judgment", "")})
    transform_screening = outlier_summary.get("target_transform_screening", {})
    treatments.append({"kind": "target_transform_screening", "feature": cfg["target_col"], "recommendation": transform_screening.get("model_stage_action", ""), "reason": transform_screening.get("reason", "")})
    domain_pack = load_domain_context_pack(paths)
    if domain_pack:
        treatments.extend(domain_treatment_candidates_from_pack(domain_pack))
    pd.DataFrame(treatments).to_csv(paths["reports"] / "treatment_recommendations.csv", index=False)
    write_domain_questions(paths["reports"] / "domain_insight_questions.md", cfg, missing_df, outlier_summary)
    try:
        from stat_probe_helpers import run_stat_probe

        stat_probe = run_stat_probe(train, cfg, paths["reports"])
    except Exception as exc:
        stat_probe = {"error": str(exc)}
        write_json(paths["reports"] / "stat_probe_report.json", stat_probe)
    report = [
        "# 결측/이상치 진단",
        "",
        "## 타깃 이상치 요약",
        "",
        f"- 판단: {outlier_summary.get('judgment', 'unknown')}",
        f"- 타깃 처리 권장: {outlier_summary.get('recommended_target_handling', 'unknown')}",
        f"- 타깃 변환 EDA 판단: {outlier_summary.get('log_target_recommendation', 'unknown')}",
        f"- 왜도(skewness): {outlier_summary.get('skewness', 'n/a')}",
        f"- p99/median 비율: {outlier_summary.get('p99_median_ratio', 'n/a')}",
        f"- robust z-score 최대: {outlier_summary.get('robust_z_max', 'n/a')}",
        "",
        "## 결측 가설 상위",
        "",
        markdown_table(missing_df.head(20)) if not missing_df.empty else "_No missing values detected._",
    ]
    if not drift_df.empty:
        report += [
            "",
            "## train/test 분포 드리프트 상위",
            "",
            markdown_table(drift_df.head(15)),
        ]
    if isinstance(stat_probe, dict):
        report += [
            "",
            "## 02S Statistical Probe",
            "",
            f"- status: `{'error' if stat_probe.get('error') else 'ok'}`",
            f"- top correlation rows: `{len(stat_probe.get('top_correlations') or [])}`",
            f"- lag rows: `{len(stat_probe.get('lag_analysis') or [])}`",
        ]
        if stat_probe.get("error"):
            report.append(f"- error: `{stat_probe.get('error')}`")
    (paths["reports"] / "diagnosis_report.md").write_text("\n".join(report), encoding="utf-8")
    append_decision(
        cfg,
        run_id,
        "02_profiler_diagnoser",
        "missing_and_outlier_policy",
        "recommendation files generated",
        "data-driven hypotheses",
        "결측/이상치 처리는 하드코딩하지 않고, 피처 생성 단계에서 추천 파일을 읽어 적용한다.",
        "이후 대체, indicator, 타깃 변환, 클리핑, 도메인 질문이 이 진단 결과에 근거하게 된다.",
    )
    payload = write_stage_payload("02", cfg, paths)
    write_stage_markdown("02", payload, paths)
    append_stage_log(
        cfg,
        "02 profiler diagnoser",
        "Missing/outlier diagnosis and 02S statistical probe",
        [str(config_path)],
        [
            str(paths["reports"] / "diagnosis_report.md"),
            str(paths["reports"] / "stat_probe_report.json"),
            str(paths["reports"] / "correlation_matrix.csv"),
            str(paths["reports"] / "lag_analysis.csv"),
        ],
        checkpoint="02H hypothesis approval",
        next_step="Review pending_hypothesis_checkpoint.md before feature building.",
    )
    refresh_run_state(cfg, run_id)
    print(f"진단 산출물 생성 완료: {paths['reports']}")


def parse_family_selection(raw: str, default: list[str]) -> list[str]:
    value = (raw or "auto").strip().lower()
    if value in {"auto", ""}:
        return default
    if value in {"none", "no"}:
        return []
    if value in {"all", "*"}:
        return ["missing_indicator", "missing_profile", "ratio", "pressure", "skew_transform", "time_order"]
    allowed = {"missing_indicator", "missing_profile", "ratio", "pressure", "skew_transform", "time_order"}
    return [part.strip() for part in value.split(",") if part.strip() in allowed]


def build_feature_candidate_menu(train: pd.DataFrame, cfg: dict[str, Any], col_dict: pd.DataFrame, missing_df: pd.DataFrame) -> pd.DataFrame:
    semantic = col_dict.set_index("column")["semantic_group"].to_dict()
    rows = []
    if not missing_df.empty:
        rows.append(
            {
                "family": "missing_profile",
                "feature_name": "row_missing_count,row_missing_fraction",
                "formula": "count/fraction of missing values per row",
                "theory_note": "결측 패턴은 운전 모드나 수집 품질의 latent state를 나타낼 수 있다.",
                "required_columns": ",".join([c for c in train.columns if c != cfg["target_col"]]),
                "recommendation_basis": "Row-level missingness can capture sparse records, logging degradation, or latent operating states.",
                "domain_knowledge_needed": "Confirm whether sparse rows indicate real operating regimes or ingestion artifacts.",
                "multicollinearity_risk": "low",
                "leakage_risk": "low unless missingness is created after the prediction point",
                "auto_recommended": True,
            }
        )
    for _, row in missing_df.iterrows():
        rows.append(
            {
                "family": "missing_indicator",
                "feature_name": f"{row['feature']}__is_missing",
                "formula": f"isna({row['feature']})",
                "theory_note": "결측 indicator는 값 자체보다 '값이 빠졌다는 사건'이 타깃과 연결될 때 유용하다.",
                "required_columns": row["feature"],
                "recommendation_basis": row["hypothesis"],
                "domain_knowledge_needed": "Confirm whether blank means zero, not observed, or unknown.",
                "multicollinearity_risk": "low",
                "leakage_risk": "low unless missingness is created after target window",
                "auto_recommended": "indicator" in str(row["recommended_handling"]),
            }
        )
    load_cols = [c for c, g in semantic.items() if g in {"demand_load", "utilization_pressure"} and c in train.columns and pd.api.types.is_numeric_dtype(train[c])]
    cap_cols = [c for c, g in semantic.items() if g == "capacity_resource" and c in train.columns and pd.api.types.is_numeric_dtype(train[c])]
    for lcol in load_cols[:8]:
        for ccol in cap_cols[:5]:
            if lcol == ccol:
                continue
            rows.append(
                {
                    "family": "ratio",
                    "feature_name": f"{lcol}__per__{ccol}",
                    "formula": f"{lcol} / ({ccol} + 1)",
                    "theory_note": "부하/용량 비율은 utilization 개념으로, 병목은 절대값보다 상대적 여유 부족에서 나타나는 경우가 많다.",
                    "required_columns": f"{lcol},{ccol}",
                    "recommendation_basis": "Demand-to-capacity ratios often expose bottlenecks better than raw load or raw capacity alone.",
                    "domain_knowledge_needed": "Confirm numerator is process load and denominator is usable capacity/resource.",
                    "multicollinearity_risk": "medium",
                    "leakage_risk": "low if both columns are known before prediction time",
                    "auto_recommended": True,
                }
            )
    error_cols = [c for c, g in semantic.items() if g == "error_quality" and c in train.columns and pd.api.types.is_numeric_dtype(train[c])]
    if len(error_cols) >= 2:
        rows.append(
            {
                "family": "pressure",
                "feature_name": "error_quality_pressure_score",
                "formula": "mean z-score of error/quality/risk columns",
                "theory_note": "여러 센서/품질 신호를 표준화 평균하면 공통 이상 상태를 하나의 압력 지표로 요약할 수 있다.",
                "required_columns": ",".join(error_cols[:12]),
                "recommendation_basis": "Multiple reliability signals can represent a shared process disruption state.",
                "domain_knowledge_needed": "Confirm higher values consistently mean worse operating condition.",
                "multicollinearity_risk": "medium",
                "leakage_risk": "medium if error columns are measured after target window",
                "auto_recommended": True,
            }
        )
    excluded = {cfg["target_col"], cfg.get("id_col"), cfg.get("group_col"), cfg.get("time_col"), None}
    for col in numeric_columns(train, excluded)[:200]:
        s = pd.to_numeric(train[col], errors="coerce")
        if s.notna().sum() > 20 and s.min() >= 0 and abs(float(s.skew())) >= 2:
            rows.append(
                {
                    "family": "skew_transform",
                    "feature_name": f"{col}__log1p",
                    "formula": f"log1p({col})",
                    "theory_note": "log1p 변환은 긴 꼬리 분포를 압축해 큰 값 몇 개가 모델을 지배하는 현상을 줄인다.",
                    "required_columns": col,
                    "recommendation_basis": f"Skewness is {float(s.skew()):.3f}; log transform can stabilize heavy-tailed numeric features.",
                    "domain_knowledge_needed": "Confirm zero and positive scale make log1p meaningful.",
                    "multicollinearity_risk": "high with original feature",
                    "leakage_risk": "low if source feature is known before prediction time",
                    "auto_recommended": True,
                }
            )
    if cfg.get("group_col") and cfg["group_col"] in train.columns:
        rows.append(
            {
                "family": "time_order",
                "feature_name": "group_step/group_phase",
                "formula": "cumcount within group and sin/cos phase",
                "theory_note": "순서/phase 피처는 운전 주기, 기동/정지, 누적 피로처럼 시간에 따라 변하는 상태를 표현한다.",
                "required_columns": cfg["group_col"],
                "recommendation_basis": "Rows inside a group may encode process phase or sequence position.",
                "domain_knowledge_needed": "Confirm row order is meaningful and not arbitrary.",
                "multicollinearity_risk": "low",
                "leakage_risk": "medium if row order is sorted using future target information",
                "auto_recommended": str((cfg.get("feature_defaults") or {}).get("time_features", "none")) == "order",
            }
        )
    return pd.DataFrame(rows)


def decide_missing_imputation(row: pd.Series) -> tuple[str, bool]:
    handling = str(row.get("recommended_handling", "median_impute_indicator_optional"))
    keep_indicator = "indicator" in handling and not handling.endswith("optional")
    if str(row.get("target_shift_label", "")) not in {"weak", "target_unavailable"}:
        keep_indicator = True
    if handling.startswith("zero"):
        return "zero", keep_indicator
    if handling.startswith("group"):
        return "group_median", keep_indicator
    return "median", keep_indicator


def apply_imputation(train: pd.DataFrame, test: pd.DataFrame | None, cfg: dict[str, Any], missing_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str], dict[str, Any]]:
    train = train.copy()
    test = test.copy() if test is not None else None
    target = cfg["target_col"]
    decisions = {}
    indicator_cols = []
    missing_map = {row["feature"]: row for _, row in missing_df.iterrows()} if not missing_df.empty else {}
    for col in train.columns:
        if col == target:
            continue
        train_missing = train[col].isna()
        test_missing = test[col].isna() if test is not None and col in test.columns else pd.Series(False, index=[])
        if not train_missing.any() and not (len(test_missing) and test_missing.any()):
            continue
        row = missing_map.get(col, pd.Series({"recommended_handling": "median_impute_indicator_optional", "target_shift_label": "weak", "hypothesis": ""}))
        strategy, keep_indicator = decide_missing_imputation(row)
        if keep_indicator:
            ind = f"{col}__is_missing"
            train[ind] = train_missing.astype("int8")
            if test is not None and col in test.columns:
                test[ind] = test_missing.astype("int8")
            indicator_cols.append(ind)
        if pd.api.types.is_numeric_dtype(train[col]):
            if strategy == "zero":
                train[col] = train[col].fillna(0)
                if test is not None and col in test.columns:
                    test[col] = test[col].fillna(0)
            elif strategy == "group_median" and cfg.get("group_col") in train.columns:
                group_col = cfg["group_col"]
                fallback = float(train[col].median())
                if not np.isfinite(fallback):
                    fallback = 0.0
                mapping = train.groupby(group_col, dropna=False)[col].median()
                train[col] = train[col].fillna(train[group_col].map(mapping)).fillna(fallback)
                if test is not None and col in test.columns and group_col in test.columns:
                    test[col] = test[col].fillna(test[group_col].map(mapping)).fillna(fallback)
            else:
                fill_value = float(train[col].median())
                if not np.isfinite(fill_value):
                    fill_value = 0.0
                train[col] = train[col].fillna(fill_value)
                if test is not None and col in test.columns:
                    test[col] = test[col].fillna(fill_value)
        else:
            train[col] = train[col].fillna("__missing__")
            if test is not None and col in test.columns:
                test[col] = test[col].fillna("__missing__")
        decisions[col] = {"strategy": strategy, "keep_indicator": keep_indicator, "reason": str(row.get("hypothesis", ""))}
    return train, test, indicator_cols, decisions


def add_ratio_features(train: pd.DataFrame, test: pd.DataFrame | None, menu: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str]]:
    generated = []
    for _, row in menu[menu["family"] == "ratio"].head(30).iterrows():
        cols = [c.strip() for c in str(row["required_columns"]).split(",") if c.strip()]
        if len(cols) != 2 or cols[0] not in train.columns or cols[1] not in train.columns:
            continue
        name = str(row["feature_name"])
        train[name] = safe_div(train[cols[0]], train[cols[1]] + 1)
        if test is not None and cols[0] in test.columns and cols[1] in test.columns:
            test[name] = safe_div(test[cols[0]], test[cols[1]] + 1)
        generated.append(name)
    return train, test, generated


def add_pressure_features(train: pd.DataFrame, test: pd.DataFrame | None, menu: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str]]:
    generated = []
    for _, row in menu[menu["family"] == "pressure"].iterrows():
        cols = [c for c in str(row["required_columns"]).split(",") if c in train.columns and pd.api.types.is_numeric_dtype(train[c])]
        if len(cols) < 2:
            continue
        name = str(row["feature_name"])
        means = train[cols].mean()
        stds = train[cols].std().replace(0, 1)
        train[name] = ((train[cols] - means) / stds).mean(axis=1)
        if test is not None:
            shared = [c for c in cols if c in test.columns]
            if shared:
                test[name] = ((test[shared] - means[shared]) / stds[shared]).mean(axis=1)
        generated.append(name)
    return train, test, generated


def add_skew_features(train: pd.DataFrame, test: pd.DataFrame | None, menu: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str]]:
    generated = []
    for _, row in menu[menu["family"] == "skew_transform"].head(30).iterrows():
        col = str(row["required_columns"])
        if col not in train.columns:
            continue
        name = str(row["feature_name"])
        train[name] = np.log1p(np.maximum(pd.to_numeric(train[col], errors="coerce").fillna(0), 0))
        if test is not None and col in test.columns:
            test[name] = np.log1p(np.maximum(pd.to_numeric(test[col], errors="coerce").fillna(0), 0))
        generated.append(name)
    return train, test, generated


def add_missing_profile_features(train: pd.DataFrame, test: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str]]:
    out_train = train.copy()
    out_test = test.copy() if test is not None else None
    train_missing = out_train.isna()
    out_train["row_missing_count"] = train_missing.sum(axis=1).astype("int16")
    out_train["row_missing_fraction"] = train_missing.mean(axis=1).astype("float32")
    if out_test is not None:
        test_missing = out_test.isna()
        out_test["row_missing_count"] = test_missing.sum(axis=1).astype("int16")
        out_test["row_missing_fraction"] = test_missing.mean(axis=1).astype("float32")
    return out_train, out_test, ["row_missing_count", "row_missing_fraction"]


def add_order_features(df: pd.DataFrame, group_col: str) -> tuple[pd.DataFrame, list[str]]:
    out = df.copy()
    out["group_step"] = out.groupby(group_col, sort=False).cumcount()
    max_step = out.groupby(group_col)["group_step"].transform("max").replace(0, 1)
    phase = out["group_step"] / max_step
    out["group_phase_sin"] = np.sin(2 * np.pi * phase)
    out["group_phase_cos"] = np.cos(2 * np.pi * phase)
    out["is_group_start"] = (out["group_step"] == 0).astype("int8")
    out["is_group_end"] = (out["group_step"] == max_step).astype("int8")
    return out, ["group_step", "group_phase_sin", "group_phase_cos", "is_group_start", "is_group_end"]


def add_hypothesis_features(
    train: pd.DataFrame,
    test: pd.DataFrame | None,
    registry: dict[str, Any],
    cfg: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str]]:
    train = train.copy()
    test = test.copy() if test is not None else None
    generated: list[str] = []
    accepted = [
        item
        for item in registry.get("hypotheses", []) if isinstance(registry, dict)
        if str(item.get("status") or "open") == "accepted" or bool(item.get("auto_recommended"))
    ]
    lag_seconds = [_parse_lag_seconds(item) for item in ((cfg.get("hypothesis_defaults") or {}).get("lag_grid") or ["30s", "60s", "120s", "300s"])]
    lag_seconds = [value for value in lag_seconds if value > 0]
    for item in accepted:
        hid = str(item.get("hypothesis_id") or "").upper()
        plan_items = _as_list_local(item.get("feature_plan"))
        generated.extend(_add_generic_hypothesis_feature_plan(train, test, plan_items, lag_seconds))
        plan_text = " ".join(str(part) for part in plan_items).upper()
    return train, test, list(dict.fromkeys(generated))


def _add_generic_hypothesis_feature_plan(
    train: pd.DataFrame,
    test: pd.DataFrame | None,
    plan_items: list[str],
    lag_seconds: list[int],
) -> list[str]:
    generated: list[str] = []
    for raw_item in plan_items:
        parts = [part.strip() for part in str(raw_item).split(":") if part.strip()]
        if len(parts) < 2:
            continue
        op = parts[0].lower().replace("-", "_")
        if op in {"lag", "lags"}:
            generated.extend(_add_lags_for_column(train, test, parts[1], lag_seconds or [1]))
        elif op in {"diff", "delta"}:
            window = _parse_lag_seconds(parts[2]) if len(parts) > 2 else (lag_seconds[0] if lag_seconds else 1)
            generated.extend(_add_diff_for_column(train, test, parts[1], [window]))
        elif op in {"rolling", "rolling_mean", "roll_mean"}:
            window = _parse_lag_seconds(parts[2]) if len(parts) > 2 else (lag_seconds[0] if lag_seconds else 3)
            generated.extend(_add_rolling_mean_for_column(train, test, parts[1], [window]))
        elif op in {"hinge", "piecewise"}:
            q_spec = parts[2] if len(parts) > 2 else "q75"
            generated.extend(_add_hinge_for_column(train, test, parts[1], q_spec))
        elif op in {"interaction", "x", "multiply"} and len(parts) >= 3:
            generated.extend(_add_interaction_feature(train, test, parts[1], parts[2]))
        elif op in {"ratio", "divide", "div"} and len(parts) >= 3:
            generated.extend(_add_ratio_feature(train, test, parts[1], parts[2]))
    return generated


def _parse_lag_seconds(value: Any) -> int:
    text = str(value).strip().lower()
    if text.endswith("s"):
        return max(0, int(float(text[:-1])))
    if text.endswith("m"):
        return max(0, int(float(text[:-1]) * 60))
    return max(0, int(float(text)))


def _as_list_local(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _add_lags_for_column(train: pd.DataFrame, test: pd.DataFrame | None, column: str, lags: list[int]) -> list[str]:
    if column not in train.columns:
        return []
    generated = []
    for seconds in lags:
        name = f"{column}__lag_{seconds}s"
        train[name] = pd.to_numeric(train[column], errors="coerce").shift(seconds)
        if test is not None and column in test.columns:
            test[name] = pd.to_numeric(test[column], errors="coerce").shift(seconds)
        generated.append(name)
    return generated


def _add_diff_and_rolling(train: pd.DataFrame, test: pd.DataFrame | None, column: str, windows: list[int]) -> list[str]:
    if column not in train.columns:
        return []
    generated = []
    source = pd.to_numeric(train[column], errors="coerce")
    for window in windows:
        diff_name = f"{column}__diff_{window}s"
        roll_name = f"{column}__roll_mean_{window}s"
        train[diff_name] = source - source.shift(window)
        train[roll_name] = source.shift(1).rolling(window=window, min_periods=1).mean()
        if test is not None and column in test.columns:
            test_source = pd.to_numeric(test[column], errors="coerce")
            test[diff_name] = test_source - test_source.shift(window)
            test[roll_name] = test_source.shift(1).rolling(window=window, min_periods=1).mean()
        generated.extend([diff_name, roll_name])
    return generated


def _add_diff_for_column(train: pd.DataFrame, test: pd.DataFrame | None, column: str, windows: list[int]) -> list[str]:
    if column not in train.columns:
        return []
    generated = []
    source = pd.to_numeric(train[column], errors="coerce")
    for window in windows:
        if window <= 0:
            continue
        name = f"{column}__diff_{window}s"
        train[name] = source - source.shift(window)
        if test is not None and column in test.columns:
            test_source = pd.to_numeric(test[column], errors="coerce")
            test[name] = test_source - test_source.shift(window)
        generated.append(name)
    return generated


def _add_rolling_mean_for_column(train: pd.DataFrame, test: pd.DataFrame | None, column: str, windows: list[int]) -> list[str]:
    if column not in train.columns:
        return []
    generated = []
    source = pd.to_numeric(train[column], errors="coerce")
    for window in windows:
        if window <= 0:
            continue
        name = f"{column}__roll_mean_{window}s"
        train[name] = source.shift(1).rolling(window=window, min_periods=1).mean()
        if test is not None and column in test.columns:
            test_source = pd.to_numeric(test[column], errors="coerce")
            test[name] = test_source.shift(1).rolling(window=window, min_periods=1).mean()
        generated.append(name)
    return generated


def _add_hinge_for_column(train: pd.DataFrame, test: pd.DataFrame | None, column: str, quantile_spec: str) -> list[str]:
    if column not in train.columns:
        return []
    values = pd.to_numeric(train[column], errors="coerce")
    quantile, label = _parse_quantile_spec(quantile_spec)
    threshold = float(values.quantile(quantile))
    name = f"{column}__hinge_{label}"
    train[name] = np.maximum(values - threshold, 0)
    if test is not None and column in test.columns:
        test_values = pd.to_numeric(test[column], errors="coerce")
        test[name] = np.maximum(test_values - threshold, 0)
    return [name]


def _parse_quantile_spec(value: Any) -> tuple[float, str]:
    text = str(value or "q75").strip().lower()
    if text.startswith("q"):
        pct = float(text[1:])
        quantile = pct / 100.0 if pct > 1 else pct
        return min(max(quantile, 0.0), 1.0), f"q{int(round(quantile * 100))}"
    quantile = float(text)
    quantile = quantile / 100.0 if quantile > 1 else quantile
    return min(max(quantile, 0.0), 1.0), f"q{int(round(quantile * 100))}"


def _add_interaction_feature(train: pd.DataFrame, test: pd.DataFrame | None, left: str, right: str) -> list[str]:
    if left not in train.columns or right not in train.columns:
        return []
    name = f"{left}__x__{right}"
    train[name] = pd.to_numeric(train[left], errors="coerce") * pd.to_numeric(train[right], errors="coerce")
    if test is not None and left in test.columns and right in test.columns:
        test[name] = pd.to_numeric(test[left], errors="coerce") * pd.to_numeric(test[right], errors="coerce")
    return [name]


def _add_ratio_feature(train: pd.DataFrame, test: pd.DataFrame | None, numerator: str, denominator: str) -> list[str]:
    if numerator not in train.columns or denominator not in train.columns:
        return []
    name = f"{numerator}__div__{denominator}"
    den = pd.to_numeric(train[denominator], errors="coerce").replace(0, np.nan)
    train[name] = pd.to_numeric(train[numerator], errors="coerce") / den
    if test is not None and numerator in test.columns and denominator in test.columns:
        test_den = pd.to_numeric(test[denominator], errors="coerce").replace(0, np.nan)
        test[name] = pd.to_numeric(test[numerator], errors="coerce") / test_den
    return [name]


def correlation_prune(train: pd.DataFrame, test: pd.DataFrame | None, generated_cols: list[str], threshold: float) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str]]:
    numeric = [c for c in generated_cols if c in train.columns and pd.api.types.is_numeric_dtype(train[c])]
    if len(numeric) < 2:
        return train, test, []
    sample = train[numeric].sample(60000, random_state=42) if len(train) > 60000 else train[numeric]
    corr = sample.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    drops = [col for col in upper.columns if any(upper[col] > threshold)]
    if drops:
        train = train.drop(columns=drops, errors="ignore")
        if test is not None:
            test = test.drop(columns=drops, errors="ignore")
    return train, test, drops


def run_feature_builder(
    config_path: str | Path,
    run_id: str,
    interactive: bool = False,
    feature_families: str = "auto",
    time_features: str = "auto",
    apply_correlation_pruning: bool = False,
) -> None:
    import warnings
    from pandas.errors import PerformanceWarning
    from manual_domain_expert import domain_feature_candidates_from_pack, load_domain_context_pack
    from manual_hypothesis import hypothesis_feature_candidates_from_registry
    from manual_report_payloads import write_stage_payload
    from manual_state import refresh_run_state

    warnings.filterwarnings("ignore", category=PerformanceWarning)
    cfg = load_config(config_path)
    paths = run_paths(cfg, run_id)
    train, test, _ = load_modeling_data(cfg)
    id_col = choose_id_col(cfg, train, test)
    cfg["id_col"] = id_col
    train = ensure_id_column(train, id_col)
    test = ensure_id_column(test, id_col) if test is not None else None
    target = cfg["target_col"]
    y = train[[id_col, target]].copy()
    if cfg.get("positive_target") and cfg["task_type"] == "regression":
        y[f"{target}__log1p"] = np.log1p(np.maximum(pd.to_numeric(y[target], errors="coerce"), 0))
    train = train.drop(columns=[target])
    if test is not None and target in test.columns:
        # Some datasets ship a labeled "test" segment. Ensure the target is not treated as a feature.
        test = test.drop(columns=[target])
    col_path = paths["reports"] / "column_dictionary.csv"
    col_dict = pd.read_csv(col_path) if col_path.exists() else column_stats(pd.concat([train, y[[target]]], axis=1), test, cfg)
    missing_path = paths["reports"] / "missing_reason_hypotheses.csv"
    missing_df = pd.read_csv(missing_path) if missing_path.exists() else pd.DataFrame(columns=["feature", "recommended_handling", "target_shift_label", "hypothesis"])
    menu = build_feature_candidate_menu(pd.concat([train, y[[target]]], axis=1), cfg, col_dict, missing_df)
    domain_pack = load_domain_context_pack(paths)
    domain_feature_rows = domain_feature_candidates_from_pack(domain_pack) if domain_pack else []
    if domain_feature_rows:
        menu = pd.concat([menu, pd.DataFrame(domain_feature_rows)], ignore_index=True)
    hypothesis_registry = read_json(paths["reports"] / "hypothesis_registry.json", {})
    hypothesis_feature_rows = hypothesis_feature_candidates_from_registry(hypothesis_registry) if hypothesis_registry else []
    if hypothesis_feature_rows:
        menu = pd.concat([menu, pd.DataFrame(hypothesis_feature_rows)], ignore_index=True)
    menu.to_csv(paths["reports"] / "feature_candidate_menu.csv", index=False)
    default_families = sorted(menu.loc[menu["auto_recommended"].astype(bool), "family"].dropna().unique().tolist()) if not menu.empty else []
    families = parse_family_selection(feature_families, default_families)
    default_time = (cfg.get("feature_defaults") or {}).get("time_features", "none")
    time_choice = default_time if time_features == "auto" else time_features
    if interactive:
        print("\nFeature families: missing_indicator, missing_profile, ratio, pressure, skew_transform, time_order, all, none")
        raw = input(f"Choose feature families [default: {','.join(families) or 'none'}]: ").strip()
        if raw:
            families = parse_family_selection(raw, families)
        raw_time = input(f"Time/order features? none/order [default: {time_choice}]: ").strip().lower()
        if raw_time in {"none", "order"}:
            time_choice = raw_time
        raw_prune = input("Apply correlation pruning? y/N: ").strip().lower()
        apply_correlation_pruning = raw_prune in {"y", "yes"}
    train, test, indicator_cols, missing_decisions = apply_imputation(train, test, cfg, missing_df)
    generated = []
    if "missing_profile" in families:
        train, test, cols = add_missing_profile_features(train, test)
        generated.extend(cols)
    if "ratio" in families:
        train, test, cols = add_ratio_features(train, test, menu)
        generated.extend(cols)
    if "pressure" in families:
        train, test, cols = add_pressure_features(train, test, menu)
        generated.extend(cols)
    if "skew_transform" in families:
        train, test, cols = add_skew_features(train, test, menu)
        generated.extend(cols)
    if time_choice == "order" and cfg.get("group_col") and cfg["group_col"] in train.columns:
        train, cols = add_order_features(train, cfg["group_col"])
        if test is not None and cfg["group_col"] in test.columns:
            test, _ = add_order_features(test, cfg["group_col"])
        generated.extend(cols)
    train, test, hypothesis_generated = add_hypothesis_features(train, test, hypothesis_registry, cfg)
    generated.extend(hypothesis_generated)
    threshold = float((cfg.get("feature_defaults") or {}).get("correlation_threshold", 0.95))
    pruned = []
    if apply_correlation_pruning:
        train, test, pruned = correlation_prune(train, test, generated, threshold)
    save_dataframe(train, paths["processed"] / "train_features.parquet")
    if test is not None:
        save_dataframe(test, paths["processed"] / "test_features.parquet")
    save_dataframe(y, paths["processed"] / "y.parquet")
    manifest = {
        "task_type": cfg["task_type"],
        "target_col": target,
        "id_col": id_col,
        "group_col": cfg.get("group_col"),
        "time_col": cfg.get("time_col"),
        "feature_families": families,
        "time_features": time_choice,
        "missing_indicator_columns": indicator_cols,
        "missing_decisions": missing_decisions,
        "generated_features": generated,
        "hypothesis_generated_features": hypothesis_generated,
        "hypothesis_feature_candidates": hypothesis_feature_rows,
        "hypothesis_registry_path": str(paths["reports"] / "hypothesis_registry.json") if hypothesis_registry else "",
        "correlation_pruning_applied": bool(apply_correlation_pruning),
        "correlation_threshold": threshold,
        "pruned_features": pruned,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)) if test is not None else 0,
        "feature_columns": [c for c in train.columns if c != id_col],
    }
    write_json(paths["processed"] / "feature_manifest.json", manifest)
    report = [
        "# 피처 생성 보고서",
        "",
        f"- Feature families: `{','.join(families) or 'none'}`",
        f"- Time/order features: `{time_choice}`",
        f"- Generated features: `{len(generated)}`",
        f"- Missing indicators: `{len(indicator_cols)}`",
        f"- Correlation pruning: `{apply_correlation_pruning}`",
        f"- Pruned features: `{len(pruned)}`",
        "",
        "## 의사결정 영향",
        "",
        "- 비율/압력(pressure) 피처는 도메인 형태의 병목 신호를 추가한다.",
        "- skew 변환은 선형 모델에 도움이 될 수 있으나 원본 변수와 중복될 수 있다.",
        "- 시간/순서 피처는 그룹 내부 row 순서가 의미 있을 때만 안전하다.",
    ]
    (paths["processed"] / "feature_build_report.md").write_text("\n".join(report), encoding="utf-8")
    append_decision(
        cfg,
        run_id,
        "03_feature_builder",
        "feature_families",
        ",".join(families) or "none",
        ",".join(default_families) or "none",
        "피처 패밀리는 semantic 그룹, 결측, 왜도, 공정 압력 휴리스틱 기반 후보 중에서 선택되었다.",
        "선택 결과는 모델 입력 컬럼과 이후 해석 가능성에 직접 영향을 준다.",
    )
    append_decision(
        cfg,
        run_id,
        "03_feature_builder",
        "time_features",
        time_choice,
        default_time,
        "시간/순서 피처는 row 순서가 공정 단계 신호일 수도, 반대로 누수 위험일 수도 있어 선택 사항이다.",
        "그룹 기반 공정 문제에서는 도움이 될 수 있으나, row 순서가 임의라면 제거해야 한다.",
    )
    write_stage_payload("03", cfg, paths)
    append_stage_log(
        cfg,
        "03 feature builder",
        "Build selected feature families and accepted hypothesis features",
        [str(config_path), str(paths["reports"] / "hypothesis_registry.json")],
        [str(paths["processed"] / "train_features.parquet"), str(paths["processed"] / "feature_manifest.json")],
        checkpoint="Stage 03 physics/range review",
        next_step="Run temporal validation split after reviewing generated features.",
    )
    refresh_run_state(cfg, run_id)
    print(f"전처리(피처) 산출물 생성 완료: {paths['processed']}")


def make_temporal_holdout_folds(df: pd.DataFrame, cfg: dict[str, Any], sample_frac: float, n_splits: int, seed: int, full: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    id_col = cfg.get("id_col") or "_manual_row_id"
    group_col = cfg.get("group_col")
    time_col = cfg.get("time_col")
    if not time_col or time_col not in df.columns:
        raise ValueError("temporal_holdout validation requires a configured time_col in the data.")

    validation = cfg.get("validation") or {}
    holdout_days = float(validation.get("holdout_days", 3))
    holdout_gap_seconds = int(validation.get("holdout_gap_seconds", 300))
    fold_count = int(validation.get("cv_folds_in_train", n_splits or 5))

    work = df.copy()
    work[time_col] = pd.to_datetime(work[time_col], errors="coerce")
    work = work.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)
    ensure_unique_keys(work, id_col, "temporal holdout source")
    if work.empty:
        raise ValueError("temporal_holdout source has no timestamped rows.")

    diffs = work[time_col].drop_duplicates().sort_values().diff().dropna()
    positive_diffs = diffs[diffs > pd.Timedelta(0)]
    step = positive_diffs.median() if not positive_diffs.empty else pd.Timedelta(seconds=1)
    if pd.isna(step) or step <= pd.Timedelta(0):
        step = pd.Timedelta(seconds=1)

    max_ts = work[time_col].max()
    holdout_start = max_ts - pd.Timedelta(days=holdout_days) + step
    gap_start = holdout_start - pd.Timedelta(seconds=holdout_gap_seconds)

    split = np.where(work[time_col] >= holdout_start, "holdout", np.where(work[time_col] >= gap_start, "gap", "train"))
    out_cols = [id_col]
    if group_col and group_col in work.columns:
        out_cols.append(group_col)
    out_cols.append(time_col)
    out = work[out_cols].copy()
    out["split"] = split

    if int((out["split"] == "holdout").sum()) == 0:
        holdout_rows = max(1, int(round(len(out) * 0.2)))
        out.loc[:, "split"] = "train"
        out.loc[out.index[-holdout_rows:], "split"] = "holdout"
        gap_rows = min(max(1, int(round(holdout_gap_seconds / max(step.total_seconds(), 1)))), max(0, len(out) - holdout_rows))
        if gap_rows:
            out.loc[out.index[-holdout_rows - gap_rows : -holdout_rows], "split"] = "gap"

    if not full and sample_frac < 1.0:
        rng = np.random.default_rng(seed)
        train_idx = out.index[out["split"] == "train"].to_numpy()
        sample_size = max(1, int(round(len(train_idx) * sample_frac))) if len(train_idx) else 0
        keep_train = set(rng.choice(train_idx, size=sample_size, replace=False).tolist()) if sample_size else set()
        out = out[(out["split"] != "train") | out.index.isin(keep_train)].copy()

    out["fold"] = -1
    train_idx = out.index[out["split"] == "train"].to_numpy()
    fold_count = min(max(2, fold_count), max(2, len(train_idx))) if len(train_idx) >= 2 else 1
    if len(train_idx):
        for fold, idx_chunk in enumerate(np.array_split(train_idx, fold_count)):
            if len(idx_chunk):
                out.loc[idx_chunk, "fold"] = fold
    out.loc[out["split"] == "gap", "fold"] = -1
    out.loc[out["split"] == "holdout", "fold"] = 99
    out = out.reset_index(drop=True)

    split_counts = {str(k): int(v) for k, v in out["split"].value_counts().sort_index().items()}
    fold_counts = {str(k): int(v) for k, v in out["fold"].value_counts().sort_index().items()}
    leakage_count = 0
    if group_col and group_col in out.columns:
        leakage_count = int((out.groupby(group_col)["split"].nunique() > 1).sum())
    summary = {
        "full": full,
        "sample_frac": sample_frac,
        "split_type": "TemporalHoldout",
        "rows": int(len(out)),
        "folds": int(len([f for f in out["fold"].unique() if f >= 0 and f != 99])),
        "fold_counts": fold_counts,
        "split_counts": split_counts,
        "group_col": group_col,
        "group_leakage_count": leakage_count,
        "time_col": time_col,
        "holdout_days": holdout_days,
        "holdout_gap_seconds": holdout_gap_seconds,
        "holdout_start": str(holdout_start),
        "gap_start": str(gap_start),
    }
    ensure_unique_keys(out, id_col, "generated temporal holdout assignments")
    return out, summary


def make_folds_for_index(df: pd.DataFrame, cfg: dict[str, Any], sample_frac: float, n_splits: int, seed: int, full: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    validation = cfg.get("validation") or {}
    if str(validation.get("strategy", "")).lower() == "temporal_holdout":
        return make_temporal_holdout_folds(df, cfg, sample_frac, n_splits, seed, full)

    from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold, TimeSeriesSplit

    id_col = cfg.get("id_col") or "_manual_row_id"
    group_col = cfg.get("group_col")
    time_col = cfg.get("time_col")
    target = cfg["target_col"]
    task = cfg["task_type"]
    work = df.copy()
    if not full:
        if group_col and group_col in work.columns:
            groups = pd.Series(work[group_col].dropna().unique())
            n_groups = max(1, int(round(len(groups) * sample_frac)))
            chosen = set(groups.sample(n=n_groups, random_state=seed).tolist())
            work = work[work[group_col].isin(chosen)].copy()
        else:
            work = work.sample(frac=sample_frac, random_state=seed).copy()
    ensure_unique_keys(work, id_col, "fold splitter source")
    if group_col and group_col in work.columns:
        max_splits = int(work[group_col].nunique())
    else:
        max_splits = len(work)
    fold_count = min(n_splits, max(2, max_splits))
    out_cols = [id_col]
    if group_col and group_col in work.columns:
        out_cols.append(group_col)
    out = work[out_cols].copy()
    out["fold"] = -1
    
    if time_col and time_col in work.columns:
        work = work.sort_values(time_col).reset_index(drop=True)
        splitter = TimeSeriesSplit(n_splits=fold_count)
        iterator = splitter.split(work)
        split_type = "TimeSeriesSplit"
    elif group_col and group_col in work.columns and work[group_col].nunique() >= fold_count:
        splitter = GroupKFold(n_splits=fold_count)
        iterator = splitter.split(work, groups=work[group_col].to_numpy())
        split_type = "GroupKFold"
    elif task == "classification" and target in work.columns and work[target].nunique() >= 2:
        splitter = StratifiedKFold(n_splits=fold_count, shuffle=True, random_state=seed)
        iterator = splitter.split(work, work[target])
        split_type = "StratifiedKFold"
    else:
        splitter = KFold(n_splits=fold_count, shuffle=True, random_state=seed)
        iterator = splitter.split(work)
        split_type = "KFold"
    for fold, (_, valid_idx) in enumerate(iterator):
        out.iloc[valid_idx, out.columns.get_loc("fold")] = fold
    leakage_count = 0
    if group_col and group_col in out.columns:
        leakage_count = int((out.groupby(group_col)["fold"].nunique() > 1).sum())
    summary = {
        "full": full,
        "sample_frac": sample_frac,
        "split_type": split_type,
        "rows": int(len(out)),
        "folds": int(out["fold"].nunique()),
        "fold_counts": {str(k): int(v) for k, v in out["fold"].value_counts().sort_index().items()},
        "group_col": group_col,
        "group_leakage_count": leakage_count,
    }
    ensure_unique_keys(out, id_col, "generated fold assignments")
    return out, summary


def run_validation_splitter(config_path: str | Path, run_id: str, sample_frac: float, n_splits: int, seed: int, full_train: bool, interactive: bool = False) -> None:
    from manual_report_payloads import write_stage_payload
    from manual_state import refresh_run_state

    cfg = load_config(config_path)
    paths = run_paths(cfg, run_id)
    train, _, y = read_processed(paths)
    manifest = read_json(paths["processed"] / "feature_manifest.json", {})
    id_col = manifest.get("id_col") or cfg.get("id_col") or "_manual_row_id"
    cfg["id_col"] = id_col
    ensure_unique_keys(train, id_col, "validation splitter train frame")
    work = merge_one_to_one(train, y, id_col, "validation splitter train frame", "validation splitter target frame", how="left")
    if interactive:
        raw = input("전체 학습 폴드를 만들려면 run-full 입력. 15% 샘플만이면 Enter: ").strip().lower()
        full_train = raw == "run-full" or full_train
    sample_folds, sample_summary = make_folds_for_index(work, cfg, sample_frac, n_splits, seed, full=False)
    sample_folds.to_csv(paths["folds"] / "sample15_folds.csv", index=False)
    write_json(paths["folds"] / "sample15_fold_summary.json", sample_summary)
    full_created = False
    if full_train:
        full_folds, full_summary = make_folds_for_index(work, cfg, sample_frac, n_splits, seed, full=True)
        full_folds.to_csv(paths["folds"] / "full_folds.csv", index=False)
        write_json(paths["folds"] / "full_fold_summary.json", full_summary)
        full_created = True
    write_json(
        paths["folds"] / "fold_run_summary.json",
        {"sample_frac": sample_frac, "sample_fold_file": str(paths["folds"] / "sample15_folds.csv"), "full_train_requested": bool(full_train), "full_train_created": full_created},
    )
    lines = [
        "# 검증 폴드 보고서",
        "",
        f"- 샘플 행 수: {sample_summary['rows']}",
        f"- 분할 유형: {sample_summary['split_type']}",
        f"- 그룹 누수 카운트: {sample_summary['group_leakage_count']}",
        f"- 전체 학습 폴드 생성 여부: {full_created}",
        "",
    ]
    for fold, count in sample_summary["fold_counts"].items():
        lines.append(f"- Fold {fold}: {count}")
    (paths["folds"] / "sample15_fold_report.md").write_text("\n".join(lines), encoding="utf-8")
    append_decision(
        cfg,
        run_id,
        "04_validation_splitter",
        "training_scope",
        "full_train" if full_train else "sample15",
        "sample15",
        "기본 검증 범위는 빠른 반복을 위해 그룹 또는 row의 15%만 사용하며, 전체 학습은 사용자의 명시적 의도로만 허용된다.",
        "전체 학습을 요청하기 전까지 모델 점수와 학습 시간은 이 범위 기준으로 산출된다.",
    )
    write_stage_payload("04", cfg, paths)
    append_stage_log(
        cfg,
        "04 validation splitter",
        "Create validation folds with temporal holdout/gap when configured",
        [str(paths["processed"] / "train_features.parquet"), str(paths["processed"] / "y.parquet")],
        [str(paths["folds"] / "sample15_folds.csv"), str(paths["folds"] / "sample15_fold_summary.json")],
        checkpoint="Stage 05 error-risk review",
        next_step="Train models after confirming holdout design and O2 policy.",
    )
    refresh_run_state(cfg, run_id)
    print(f"폴드 산출물 생성 완료: {paths['folds']}")


def metric_score(task: str, y_true: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    if task == "regression":
        rmse = float(np.sqrt(np.mean((y_true - pred) ** 2)))
        mae = float(np.mean(np.abs(y_true - pred)))
        denom = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = float(1 - np.sum((y_true - pred) ** 2) / denom) if denom > 0 else 0.0
        return {"rmse": rmse, "mae": mae, "r2": r2}
    from sklearn.metrics import accuracy_score, f1_score, log_loss, roc_auc_score

    labels = np.unique(y_true)
    if pred.ndim == 1:
        proba = pred
        y_hat = (proba >= 0.5).astype(int) if len(labels) <= 2 else np.rint(proba).astype(int)
    else:
        proba = pred
        y_hat = np.argmax(proba, axis=1)
    out = {"accuracy": float(accuracy_score(y_true, y_hat)), "f1": float(f1_score(y_true, y_hat, average="weighted"))}
    try:
        if len(labels) <= 2:
            out["roc_auc"] = float(roc_auc_score(y_true, proba if np.ndim(proba) == 1 else proba[:, 1]))
        out["log_loss"] = float(log_loss(y_true, proba))
    except Exception:
        pass
    return out


def primary_metric(cfg: dict[str, Any]) -> str:
    if cfg.get("metric_primary"):
        return str(cfg["metric_primary"])
    return "rmse" if cfg["task_type"] == "regression" else "log_loss"


def metric_is_lower_better(metric: str) -> bool:
    return metric not in {"accuracy", "f1", "roc_auc", "r2"}


def build_preprocessor(X: pd.DataFrame, scale_numeric: bool = False):
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    categorical = [
        c
        for c in X.columns
        if pd.api.types.is_object_dtype(X[c])
        or pd.api.types.is_string_dtype(X[c])
        or isinstance(X[c].dtype, pd.CategoricalDtype)
    ]
    numeric = [c for c in X.columns if c not in categorical]
    try:
        onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    except TypeError:
        onehot = OneHotEncoder(handle_unknown="ignore", sparse=True)
    num_step = StandardScaler(with_mean=False) if scale_numeric else "passthrough"
    return ColumnTransformer([("num", num_step, numeric), ("cat", onehot, categorical)], sparse_threshold=1.0, verbose_feature_names_out=False)


def parse_explain_models(raw: str) -> list[str]:
    value = (raw or "").lower().strip()
    if value in {"none", "xgboost-only", "xgb-only"}:
        return []
    if value in {"all", "*"}:
        return ["ridge", "elasticnet", "surrogate"]
    allowed = ["ridge", "elasticnet", "surrogate"]
    return [name for name in allowed if name in [p.strip() for p in value.split(",")]]


def aligned_training_ids(train: pd.DataFrame, y: pd.DataFrame, folds: pd.DataFrame, id_col: str) -> pd.DataFrame:
    use_ids = folds[[id_col]].copy()
    aligned = merge_one_to_one(train[[id_col]], use_ids, id_col, "processed train IDs", "fold assignments", how="inner", require_all_left=False)
    aligned = merge_one_to_one(aligned[[id_col]], y[[id_col]], id_col, "aligned train IDs", "target IDs", how="inner")
    return aligned[[id_col]]


def model_specs(task: str, explain_models: list[str], seed: int, n_jobs: int) -> dict[str, Any]:
    from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    from xgboost import XGBClassifier, XGBRegressor

    if task == "regression":
        specs = {
            "xgboost": {
                "estimator": XGBRegressor(objective="reg:squarederror", eval_metric="rmse", tree_method="hist", random_state=seed, n_jobs=n_jobs, verbosity=0),
                "scale": False,
                "params": {
                    "model__max_depth": [3, 5, 7],
                    "model__learning_rate": [0.03, 0.06, 0.1],
                    "model__n_estimators": [250, 500],
                    "model__subsample": [0.8, 1.0],
                    "model__colsample_bytree": [0.8, 1.0],
                    "model__reg_lambda": [1.0, 3.0],
                },
            }
        }
        if "ridge" in explain_models:
            specs["ridge"] = {"estimator": Ridge(random_state=seed), "scale": True, "params": {"model__alpha": [0.3, 1.0, 3.0, 10.0]}}
        if "elasticnet" in explain_models:
            specs["elasticnet"] = {"estimator": ElasticNet(max_iter=5000, random_state=seed), "scale": True, "params": {"model__alpha": [0.001, 0.01, 0.1], "model__l1_ratio": [0.1, 0.5, 0.9]}}
        if "surrogate" in explain_models:
            specs["surrogate_tree"] = {"estimator": DecisionTreeRegressor(random_state=seed), "scale": False, "params": {"model__max_depth": [3, 4, 5], "model__min_samples_leaf": [50, 200, 500]}}
        return specs
    specs = {
        "xgboost": {
            "estimator": XGBClassifier(eval_metric="logloss", tree_method="hist", random_state=seed, n_jobs=n_jobs, verbosity=0),
            "scale": False,
            "params": {
                "model__max_depth": [3, 5, 7],
                "model__learning_rate": [0.03, 0.06, 0.1],
                "model__n_estimators": [150, 300],
                "model__subsample": [0.8, 1.0],
                "model__colsample_bytree": [0.8, 1.0],
            },
        }
    }
    if "ridge" in explain_models:
        specs["logistic_ridge"] = {"estimator": LogisticRegression(max_iter=2000, penalty="l2", solver="lbfgs", n_jobs=n_jobs), "scale": True, "params": {"model__C": [0.1, 1.0, 3.0, 10.0]}}
    if "elasticnet" in explain_models:
        specs["logistic_elasticnet"] = {"estimator": LogisticRegression(max_iter=2000, penalty="elasticnet", solver="saga", l1_ratio=0.5, n_jobs=n_jobs), "scale": True, "params": {"model__C": [0.1, 1.0, 3.0], "model__l1_ratio": [0.1, 0.5, 0.9]}}
    if "surrogate" in explain_models:
        specs["surrogate_tree"] = {"estimator": DecisionTreeClassifier(random_state=seed), "scale": False, "params": {"model__max_depth": [3, 4, 5], "model__min_samples_leaf": [50, 200, 500]}}
    return specs


def candidate_params(param_grid: dict[str, list[Any]], trials: int, seed: int) -> list[dict[str, Any]]:
    from sklearn.model_selection import ParameterSampler

    if not param_grid:
        return [{}]
    if trials <= 1:
        return [{key: values[0] for key, values in param_grid.items()}]
    max_grid = int(np.prod([len(v) for v in param_grid.values()]))
    return list(ParameterSampler(param_grid, n_iter=min(trials, max(1, max_grid)), random_state=seed))


def model_prediction(estimator: Any, X: pd.DataFrame, task: str) -> np.ndarray:
    if task == "classification":
        if hasattr(estimator, "predict_proba"):
            proba = estimator.predict_proba(X)
            if proba.shape[1] == 2:
                return proba[:, 1]
            return np.argmax(proba, axis=1)
        return estimator.predict(X)
    return np.asarray(estimator.predict(X), dtype=float)


def transform_target(y: pd.Series, mode: str) -> pd.Series:
    if mode == "log1p":
        return np.log1p(np.maximum(pd.to_numeric(y, errors="coerce"), 0))
    return y


def inverse_target(pred: np.ndarray, mode: str) -> np.ndarray:
    if mode == "log1p":
        return np.expm1(pred)
    return pred


def feature_names_from_pipeline(pipeline: Any) -> list[str]:
    try:
        return list(pipeline.named_steps["preprocess"].get_feature_names_out())
    except Exception:
        return []


def write_explainability(path: Path, models: dict[str, Any], metrics: pd.DataFrame) -> None:
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, export_text

    lines = ["# 해석 리포트", ""]
    for name, pipe in models.items():
        model = pipe.named_steps["model"]
        names = feature_names_from_pipeline(pipe)
        lines += [f"## {name}", ""]
        if hasattr(model, "feature_importances_") and names:
            top = sorted(zip(names, model.feature_importances_), key=lambda item: abs(float(item[1])), reverse=True)[:25]
            lines.extend(f"- `{feature}`: {float(value):.6f}" for feature, value in top)
        elif hasattr(model, "coef_") and names:
            coef = np.asarray(model.coef_).ravel()
            top = sorted(zip(names, coef), key=lambda item: abs(float(item[1])), reverse=True)[:25]
            lines.extend(f"- `{feature}`: {float(value):.6f}" for feature, value in top)
        elif isinstance(model, (DecisionTreeRegressor, DecisionTreeClassifier)):
            lines += ["```text", export_text(model, feature_names=names[: model.n_features_in_] if names else None, max_depth=4)[:6000], "```"]
        else:
            lines.append("내장 해석 정보를 생성할 수 없습니다.")
        lines.append("")
    if not metrics.empty:
        lines += ["## 성능 지표", "", metrics.to_string(index=False)]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_model_trainer(
    config_path: str | Path,
    run_id: str,
    full_train: bool,
    explain_models: str,
    target_mode: str,
    tuning_trials: int,
    max_folds: int | None,
    seed: int,
    n_jobs: int,
) -> None:
    from manual_domain_expert import write_model_guidance_files
    from manual_report_payloads import write_stage_payload
    from manual_state import refresh_run_state

    import joblib
    from sklearn.base import clone
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import LabelEncoder

    cfg = load_config(config_path)
    paths = run_paths(cfg, run_id)
    write_model_guidance_files(paths)
    manifest = read_json(paths["processed"] / "feature_manifest.json", {})
    id_col = manifest.get("id_col") or cfg.get("id_col") or "_manual_row_id"
    target = cfg["target_col"]
    task = cfg["task_type"]
    train, test, y_df = read_processed(paths)
    folds_path = paths["folds"] / ("full_folds.csv" if full_train else "sample15_folds.csv")
    if not folds_path.exists():
        raise FileNotFoundError(f"Fold file not found: {folds_path}")
    folds = pd.read_csv(folds_path)
    fold_cols = [id_col, "fold"] + (["split"] if "split" in folds.columns else [])
    work = merge_one_to_one(train, folds[fold_cols], id_col, "manual processed train", "manual fold assignments", how="inner", require_all_left=False)
    work = merge_one_to_one(work, y_df[[id_col, target]], id_col, "manual train+fold frame", "manual target frame", how="inner")
    if "split" in work.columns and (work["split"] == "holdout").any():
        fit_work = work[work["split"].fillna("train") == "train"].copy()
        holdout_work = work[work["split"] == "holdout"].copy()
        if fit_work.empty:
            raise ValueError("Temporal holdout produced no training rows.")
    else:
        fit_work = work
        holdout_work = pd.DataFrame()
    drop_cols = [id_col, target, "fold", "split", cfg.get("group_col"), cfg.get("time_col")]
    X = fit_work.drop(columns=[c for c in drop_cols if c and c in fit_work.columns])
    if not holdout_work.empty:
        X_test = holdout_work.drop(columns=[c for c in drop_cols if c and c in holdout_work.columns])
        test_id_frame = holdout_work[[id_col]].copy()
    else:
        test_allowed = allow_test_usage(cfg, "05_model_trainer")
        if test is not None and test_allowed:
            X_test = test.drop(columns=[c for c in [id_col, cfg.get("group_col"), cfg.get("time_col")] if c and c in test.columns])
            test_id_frame = test[[id_col]].copy()
        else:
            X_test = pd.DataFrame()
            test_id_frame = pd.DataFrame()
    if not X_test.empty:
        ensure_feature_schema_match(X, X_test, "manual-model-trainer")
    train_id_frame = fit_work[[id_col]].copy()
    y = fit_work[target]
    if task == "classification":
        label_encoder = LabelEncoder()
        y_fit_base = pd.Series(label_encoder.fit_transform(y), index=y.index)
        target_modes = ["raw"]
    else:
        y_fit_base = pd.to_numeric(y, errors="coerce")
        if target_mode == "auto":
            outlier_summary = read_json(paths["reports"] / "target_outlier_summary.json", {})
            screening = outlier_summary.get("target_transform_screening", {})
            transform_policy = str(cfg.get("target_transform_policy", "eda_auto")).lower()
            use_log_candidate = bool(screening.get("recommend_log1p_candidate")) and bool(cfg.get("positive_target") or outlier_summary.get("target_is_non_negative"))
            if transform_policy in {"raw_only", "raw"}:
                use_log_candidate = False
            elif transform_policy in {"force_compare", "both"}:
                use_log_candidate = bool(cfg.get("positive_target") or outlier_summary.get("target_is_non_negative"))
            target_modes = ["raw", "log1p"] if use_log_candidate else ["raw"]
        elif target_mode == "both":
            target_modes = ["raw", "log1p"] if cfg.get("positive_target") else ["raw"]
        else:
            target_modes = [target_mode]
    chosen_explain = parse_explain_models(explain_models)
    specs = model_specs(task, chosen_explain, seed, n_jobs)
    metric_name = primary_metric(cfg)
    lower_better = metric_is_lower_better(metric_name)
    tuning_rows: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    oof = pd.DataFrame({id_col: train_id_frame[id_col].to_numpy(), target: y_fit_base.to_numpy() if task == "classification" else y.to_numpy()})
    test_predictions = pd.DataFrame({id_col: test_id_frame[id_col].to_numpy()}) if not test_id_frame.empty else pd.DataFrame()
    registry = {"task_type": task, "target_col": target, "id_col": id_col, "models": {}, "fold_file": str(folds_path), "prediction_export_scale": "raw"}
    final_models = {}
    fold_values = fit_work["fold"].to_numpy()
    selected_folds = sorted(pd.unique(fold_values))
    if max_folds:
        selected_folds = selected_folds[:max_folds]
    for model_key, spec in specs.items():
        pipe = Pipeline([("preprocess", build_preprocessor(X, bool(spec["scale"]))), ("model", spec["estimator"])])
        candidates = candidate_params(spec["params"], tuning_trials, seed)
        for mode in target_modes:
            best_score = None
            best_params = None
            for params in candidates:
                preds = np.zeros(len(X), dtype=float)
                for fold in selected_folds:
                    tr_idx = np.where(fold_values != fold)[0]
                    va_idx = np.where(fold_values == fold)[0]
                    est = clone(pipe)
                    est.set_params(**params)
                    fit_y = transform_target(y_fit_base, mode) if task == "regression" else y_fit_base
                    est.fit(X.iloc[tr_idx], fit_y.iloc[tr_idx])
                    fold_pred = model_prediction(est, X.iloc[va_idx], task)
                    if task == "regression":
                        fold_pred = inverse_target(fold_pred, mode)
                    preds[va_idx] = fold_pred
                valid_idx = np.isin(fold_values, selected_folds)
                truth = y_fit_base.to_numpy()[valid_idx] if task == "classification" else y.to_numpy()[valid_idx]
                score = metric_score(task, truth, preds[valid_idx])
                row = {"model": model_key, "target_mode": mode, "params": json.dumps(params, sort_keys=True), **score}
                tuning_rows.append(row)
                current = score.get(metric_name, next(iter(score.values())))
                if best_score is None or (current < best_score if lower_better else current > best_score):
                    best_score = current
                    best_params = params
            full_name = f"{model_key}_{mode}"
            final = clone(pipe)
            final.set_params(**(best_params or {}))
            fit_y_all = transform_target(y_fit_base, mode) if task == "regression" else y_fit_base
            final.fit(X, fit_y_all)
            preds = np.zeros(len(X), dtype=float)
            for fold in selected_folds:
                tr_idx = np.where(fold_values != fold)[0]
                va_idx = np.where(fold_values == fold)[0]
                est = clone(pipe)
                est.set_params(**(best_params or {}))
                est.fit(X.iloc[tr_idx], fit_y_all.iloc[tr_idx])
                fold_pred = model_prediction(est, X.iloc[va_idx], task)
                if task == "regression":
                    fold_pred = inverse_target(fold_pred, mode)
                preds[va_idx] = fold_pred
            test_pred = model_prediction(final, X_test, task) if not X_test.empty else np.array([])
            if task == "regression":
                test_pred = inverse_target(test_pred, mode)
                if cfg.get("positive_target"):
                    preds = np.maximum(preds, 0)
                    test_pred = np.maximum(test_pred, 0)
            oof[full_name] = preds
            if len(test_pred):
                test_predictions[full_name] = test_pred
            model_path = paths["models"] / f"{full_name}.joblib"
            joblib.dump(final, model_path)
            score = metric_score(task, y_fit_base.to_numpy() if task == "classification" else y.to_numpy(), preds)
            metrics_rows.append({"model": full_name, "base_model": model_key, "target_mode": mode, **score, "rows": len(X), "tuning_trials": len(candidates), "model_path": str(model_path)})
            registry["models"][full_name] = {
                "model_path": str(model_path),
                "target_mode": mode,
                "best_params": best_params or {},
                "prediction_export_scale": "raw",
            }
            final_models[full_name] = final
            print(f"Trained {full_name}: {metric_name}={score.get(metric_name, math.nan):.6f}")
    tuning = pd.DataFrame(tuning_rows)
    metrics = pd.DataFrame(metrics_rows)
    if metric_name in metrics.columns:
        metrics = metrics.sort_values(metric_name, ascending=lower_better)
    if not metrics.empty and "experiment_group" not in metrics.columns:
        metrics["experiment_group"] = "baseline"
    ablation_groups = (cfg.get("hypothesis_defaults") or {}).get("ablation_groups", [])
    if ablation_groups:
        pd.DataFrame(
            [
                {
                    "experiment_group": group,
                    "status": "planned",
                    "note": "Configured for hypothesis evaluation. Full retraining per group can be executed in a follow-up run.",
                }
                for group in ablation_groups
            ]
        ).to_csv(paths["models"] / "ablation_groups_plan.csv", index=False)
    tuning.to_csv(paths["models"] / "tuning_results.csv", index=False)
    metrics.to_csv(paths["models"] / "metrics.csv", index=False)
    oof.to_csv(paths["models"] / "oof_predictions.csv", index=False)
    if not test_predictions.empty:
        test_predictions.to_csv(paths["models"] / "test_predictions.csv", index=False)
    write_json(paths["models"] / "model_registry.json", registry)
    write_explainability(paths["models"] / "explainability_report.md", final_models, metrics)
    append_decision(
        cfg,
        run_id,
        "05_model_trainer",
        "model_set",
        "xgboost+" + (",".join(chosen_explain) if chosen_explain else "none"),
        "xgboost+ridge,surrogate",
        "XGBoost is always included; interpretable models are optional baselines for coefficient/tree explanations.",
        "The model set affects runtime, ensemble diversity, and interpretability.",
    )
    write_stage_payload("05", cfg, paths)
    append_stage_log(
        cfg,
        "05 model trainer",
        "Train models and export out-of-fold/holdout predictions",
        [str(folds_path), str(paths["processed"] / "train_features.parquet")],
        [str(paths["models"] / "metrics.csv"), str(paths["models"] / "oof_predictions.csv"), str(paths["models"] / "test_predictions.csv")],
        checkpoint="Stage 06 output mode",
        next_step="Run holdout_analysis or submission maker according to config.",
    )
    if test is not None and holdout_work.empty and not allow_test_usage(cfg, "05_model_trainer"):
        print("Manual guardrail: test set exists but was excluded from model tuning/training by default policy.")
    refresh_run_state(cfg, run_id)
    print(f"Wrote model artifacts to {paths['models']}")


def normalized_weights(metrics: pd.DataFrame, metric: str) -> dict[str, float]:
    if metrics.empty or metric not in metrics.columns:
        return {}
    best = metrics.sort_values(metric, ascending=metric_is_lower_better(metric)).drop_duplicates("model")
    values = best[metric].to_numpy(dtype=float)
    if metric_is_lower_better(metric):
        raw = 1.0 / np.maximum(values, 1e-9)
    else:
        raw = np.maximum(values, 1e-9)
    raw = raw / raw.sum()
    return dict(zip(best["model"], raw))


def parse_manual_weights(raw: str, cols: list[str]) -> dict[str, float]:
    values = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        name, weight = item.split("=", 1)
        name = name.strip()
        if name not in cols:
            raise ValueError(f"Unknown model in manual weights: {name}")
        values[name] = float(weight)
    total = sum(values.values())
    if total <= 0:
        raise ValueError("Manual weights must sum to a positive value.")
    return {k: v / total for k, v in values.items()}


def write_holdout_analysis_outputs(
    preds: pd.DataFrame,
    truth: pd.DataFrame,
    folds: pd.DataFrame,
    features: pd.DataFrame,
    cfg: dict[str, Any],
    paths: dict[str, Path],
) -> dict[str, Any]:
    id_col = cfg.get("id_col") or "_manual_row_id"
    target = cfg["target_col"]
    submissions = ensure_dir(paths["submissions"])
    reports = ensure_dir(paths["reports"])
    ensure_unique_keys(preds, id_col, "holdout predictions")
    ensure_unique_keys(truth, id_col, "holdout truth")

    pred_cols = [c for c in preds.columns if c != id_col]
    if not pred_cols:
        raise ValueError("holdout_analysis requires at least one prediction column.")
    pred_col = pred_cols[0]
    if cfg.get("metric_primary"):
        metrics_path = paths.get("models", Path("")) / "metrics.csv" if "models" in paths else None
        if metrics_path and metrics_path.exists():
            metrics = pd.read_csv(metrics_path)
            metric = primary_metric(cfg)
            if metric in metrics.columns and "model" in metrics.columns:
                best = metrics.sort_values(metric, ascending=metric_is_lower_better(metric)).iloc[0]["model"]
                if best in pred_cols:
                    pred_col = str(best)

    merged = preds[[id_col, pred_col]].merge(truth[[id_col, target]], on=id_col, how="inner", validate="1:1")
    if not folds.empty and id_col in folds.columns:
        keep_cols = [id_col] + [c for c in ["split", "fold"] if c in folds.columns]
        merged = merged.merge(folds[keep_cols], on=id_col, how="left", validate="1:1")
        if "split" in merged.columns and (merged["split"] == "holdout").any():
            merged = merged[merged["split"] == "holdout"].copy()
    if not features.empty and id_col in features.columns:
        feature_cols = [id_col] + [c for c in [cfg.get("time_col"), "timestamp"] if c and c in features.columns]
        feature_cols = list(dict.fromkeys(feature_cols))
        merged = merged.merge(features[feature_cols], on=id_col, how="left", validate="1:1")

    merged = merged.rename(columns={pred_col: "prediction"})
    merged["residual"] = pd.to_numeric(merged[target], errors="coerce") - pd.to_numeric(merged["prediction"], errors="coerce")
    merged["abs_error"] = merged["residual"].abs()
    merged["squared_error"] = merged["residual"] ** 2
    rmse = float(np.sqrt(merged["squared_error"].mean())) if len(merged) else math.nan
    mae = float(merged["abs_error"].mean()) if len(merged) else math.nan
    bias = float(merged["residual"].mean()) if len(merged) else math.nan

    time_col = cfg.get("time_col") if cfg.get("time_col") in merged.columns else ("timestamp" if "timestamp" in merged.columns else None)
    if time_col:
        merged[time_col] = pd.to_datetime(merged[time_col], errors="coerce")
        by_hour = (
            merged.assign(hour=merged[time_col].dt.hour)
            .dropna(subset=["hour"])
            .groupby("hour", as_index=False)
            .agg(rows=(id_col, "count"), rmse=("squared_error", lambda s: float(np.sqrt(np.mean(s)))), mae=("abs_error", "mean"), bias=("residual", "mean"))
        )
    else:
        by_hour = pd.DataFrame(columns=["hour", "rows", "rmse", "mae", "bias"])

    holdout_path = submissions / "holdout_predictions.csv"
    merged.to_csv(holdout_path, index=False)
    by_hour.to_csv(reports / "holdout_error_by_hour.csv", index=False)
    summary = {
        "mode": "holdout_analysis",
        "prediction_column": pred_col,
        "holdout_rows": int(len(merged)),
        "rmse": rmse,
        "mae": mae,
        "bias": bias,
    }
    write_json(reports / "holdout_residual_summary.json", summary)
    report = [
        "# Holdout Residual Analysis",
        "",
        f"- Rows: `{len(merged)}`",
        f"- Prediction column: `{pred_col}`",
        f"- RMSE: `{rmse:.6f}`" if not math.isnan(rmse) else "- RMSE: `nan`",
        f"- MAE: `{mae:.6f}`" if not math.isnan(mae) else "- MAE: `nan`",
        f"- Bias(target - prediction): `{bias:.6f}`" if not math.isnan(bias) else "- Bias(target - prediction): `nan`",
        "",
        "## Files",
        "",
        f"- `{holdout_path}`",
        f"- `{reports / 'holdout_error_by_hour.csv'}`",
    ]
    (reports / "holdout_residual_analysis.md").write_text("\n".join(report), encoding="utf-8")
    merged[[id_col, "prediction"]].to_csv(submissions / "submission.csv", index=False)
    write_json(submissions / "postprocess_choices.json", summary)
    pd.DataFrame([{"model": pred_col, "weight": 1.0}]).to_csv(submissions / "ensemble_weights.csv", index=False)
    (submissions / "submission_report.md").write_text("\n".join(report), encoding="utf-8")
    return summary


def run_submission_maker(
    config_path: str | Path,
    run_id: str,
    ensemble_method: str,
    manual_weights: str,
    interactive: bool,
    clip_negative: bool,
    upper_clip: str,
) -> None:
    from manual_report_payloads import write_stage_payload
    from manual_state import refresh_run_state

    cfg = load_config(config_path)
    paths = run_paths(cfg, run_id)
    target = cfg["target_col"]
    id_col = read_json(paths["processed"] / "feature_manifest.json", {}).get("id_col") or cfg.get("id_col") or "_manual_row_id"
    pred_path = paths["models"] / "test_predictions.csv"
    if not pred_path.exists():
        raise FileNotFoundError(f"test_predictions.csv not found: {pred_path}")
    preds = pd.read_csv(pred_path)
    ensure_unique_keys(preds, id_col, "manual test predictions")
    metrics = pd.read_csv(paths["models"] / "metrics.csv") if (paths["models"] / "metrics.csv").exists() else pd.DataFrame()
    registry = read_json(paths["models"] / "model_registry.json", {})
    if isinstance(registry, dict):
        ensure_prediction_export_scale(registry, "manual submission maker model registry")
    if str(cfg.get("submission_mode", "")).lower() == "holdout_analysis":
        train_features, _, y_df = read_processed(paths)
        folds_path = paths["folds"] / "full_folds.csv"
        if not folds_path.exists():
            folds_path = paths["folds"] / "sample15_folds.csv"
        folds = pd.read_csv(folds_path) if folds_path.exists() else pd.DataFrame()
        summary = write_holdout_analysis_outputs(preds, y_df, folds, train_features, cfg | {"id_col": id_col}, paths)
        append_decision(
            cfg,
            run_id,
            "06_submission_maker",
            "submission_mode",
            "holdout_analysis",
            "submission",
            "Configured workflow uses the last temporal holdout period for residual analysis instead of a competition submission.",
            "Outputs residual diagnostics, hourly error, and holdout predictions for process review.",
        )
        write_stage_payload("06", cfg, paths)
        append_stage_log(
            cfg,
            "06 holdout analysis",
            "Create holdout predictions and residual diagnostics",
            [str(pred_path), str(folds_path)],
            [
                str(paths["submissions"] / "holdout_predictions.csv"),
                str(paths["reports"] / "holdout_residual_analysis.md"),
                str(paths["reports"] / "holdout_error_by_hour.csv"),
            ],
            checkpoint="Stage 07 action conversion",
            next_step="Review residual patterns and convert them into field-check actions.",
        )
        refresh_run_state(cfg, run_id)
        print(f"Holdout analysis artifacts written: {paths['reports']}")
        return
    cols = [c for c in preds.columns if c != id_col]
    if interactive:
        raw = input("앙상블 선택: weighted/simple/best/manual [기본 weighted]: ").strip().lower()
        if raw in {"weighted", "simple", "best", "manual"}:
            ensemble_method = raw
    if ensemble_method == "simple":
        weights = {c: 1.0 / len(cols) for c in cols}
    elif ensemble_method == "best":
        metric = primary_metric(cfg)
        if not metrics.empty and metric in metrics.columns:
            best = metrics.sort_values(metric, ascending=metric_is_lower_better(metric)).iloc[0]["model"]
            if best not in cols:
                best = cols[0]
        else:
            best = cols[0]
        weights = {c: 1.0 if c == best else 0.0 for c in cols}
    elif ensemble_method == "manual":
        weights = parse_manual_weights(manual_weights, cols)
    else:
        weights = normalized_weights(metrics[metrics["model"].isin(cols)], primary_metric(cfg))
        if not weights:
            weights = {c: 1.0 / len(cols) for c in cols}
    pred = np.zeros(len(preds), dtype=float)
    for col, weight in weights.items():
        pred += preds[col].to_numpy(dtype=float) * float(weight)
    notes = []
    upper_clip_value = None
    if cfg["task_type"] == "regression":
        outlier_summary = read_json(paths["reports"] / "target_outlier_summary.json", {})
        if upper_clip.lower() == "auto" and outlier_summary:
            q = outlier_summary.get("quantiles", {})
            if "Possible" in str(outlier_summary.get("judgment", "")):
                upper_clip_value = q.get("p995") or q.get("p99")
            elif "Mixed" in str(outlier_summary.get("judgment", "")):
                upper_clip_value = q.get("p999") or q.get("p995")
            notes.append(f"상한 클리핑(auto)은 이상치 판단({outlier_summary.get('judgment', 'unknown')})을 사용했습니다.")
        elif upper_clip.lower() not in {"none", "no"}:
            upper_clip_value = float(upper_clip)
        if upper_clip_value is not None:
            pred = np.minimum(pred, float(upper_clip_value))
            notes.append(f"상한 클리핑 적용: {upper_clip_value}.")
        if clip_negative and cfg.get("positive_target"):
            pred = np.maximum(pred, 0)
            notes.append("타깃이 양수로 가정되어 음수 예측을 0 이상으로 클리핑했습니다.")
    sample_path = resolve_project_path(cfg, cfg.get("sample_submission_path"))
    if sample_path and sample_path.exists():
        sample = pd.read_csv(sample_path)
        target_out = target if target in sample.columns else [c for c in sample.columns if c != id_col][-1]
        submission = align_by_id(
            sample[[id_col]],
            pd.DataFrame({id_col: preds[id_col], target_out: pred}),
            id_col,
            [target_out],
            "manual sample submission IDs",
            "manual submission predictions",
        )[[id_col, target_out]]
    else:
        target_out = target
        submission = pd.DataFrame({id_col: preds[id_col], target_out: pred})
    out_path = paths["submissions"] / "submission.csv"
    submission.to_csv(out_path, index=False)
    weights_df = pd.DataFrame([{"model": k, "weight": v} for k, v in weights.items()])
    weights_df.to_csv(paths["submissions"] / "ensemble_weights.csv", index=False)
    choices = {"ensemble_method": ensemble_method, "weights": weights, "clip_negative": clip_negative, "upper_clip": upper_clip, "upper_clip_value": upper_clip_value, "postprocess_notes": notes}
    write_json(paths["submissions"] / "postprocess_choices.json", choices)
    report = [
        "# 제출(예측) 보고서",
        "",
        f"- 출력: `{out_path}`",
        f"- 행 수: {len(submission)}",
        f"- 앙상블: `{ensemble_method}`",
        f"- 예측 min/mean/max: {float(np.min(pred)):.6f} / {float(np.mean(pred)):.6f} / {float(np.max(pred)):.6f}",
        "",
        "## 가중치",
        "",
        markdown_table(weights_df),
        "",
        "## 후처리",
        "",
    ]
    report.extend(f"- {note}" for note in notes)
    (paths["submissions"] / "submission_report.md").write_text("\n".join(report), encoding="utf-8")
    append_decision(
        cfg,
        run_id,
        "06_submission_maker",
        "ensemble_and_postprocess",
        ensemble_method,
        "weighted",
        "선택한 앙상블 규칙으로 모델 예측을 결합하고, 설정된 후처리만 적용합니다.",
        "샘플 제출 순서를 보존하면서 최종 예측 파일이 바뀝니다.",
    )
    write_stage_payload("06", cfg, paths)
    append_stage_log(
        cfg,
        "06 submission maker",
        "Create submission or prediction output with postprocessing choices",
        [str(pred_path)],
        [str(paths["submissions"] / "submission.csv"), str(paths["submissions"] / "submission_report.md")],
        checkpoint="Stage 07 report review",
        next_step="Generate integrated reports.",
    )
    refresh_run_state(cfg, run_id)
    print(f"제출 파일 생성 완료: {out_path}")
