from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


METADATA_KEYS = {
    "description": "description",
    "descriptions": "description",
    "desc": "description",
    "unit": "units",
    "units": "units",
    "plot min": "plot_min",
    "plot max": "plot_max",
    "min": "plot_min",
    "max": "plot_max",
}


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_project_path(cfg: dict[str, Any], value: str | None) -> Path | None:
    if not value:
        return None
    raw = Path(value)
    if raw.is_absolute():
        return raw
    return (Path(cfg.get("_project_root", ".")).resolve() / raw).resolve()


def run_raw_intake(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    raw_cfg = cfg.get("raw_intake") or {}
    raw_paths = [resolve_project_path(cfg, str(item)) for item in raw_cfg.get("raw_paths", [])]
    raw_paths = [path for path in raw_paths if path and path.exists()]
    if not raw_paths:
        raise FileNotFoundError("raw_intake.raw_paths is enabled, but no readable raw files were found.")

    reports = ensure_dir(paths["reports"])
    processed = ensure_dir(paths["processed"])
    merge_strategy = str(raw_cfg.get("merge_strategy") or "single_table").lower()
    if merge_strategy == "vertical_concat" or len(raw_paths) > 1:
        table = detect_and_concat_tables(raw_paths, cfg)
    else:
        table = detect_table(raw_paths[0])
    normalized = table["data"]
    metadata = table["metadata"]
    semantics = semantic_candidates(metadata, cfg)

    normalized_path = processed / "normalized_train.csv"
    normalized.to_csv(normalized_path, index=False)
    try:
        normalized.to_parquet(processed / "normalized_train.parquet", index=False)
    except Exception:
        # Parquet engines are optional in lightweight environments.
        pass
    pd.DataFrame(metadata).to_csv(reports / "column_metadata.csv", index=False)
    pd.DataFrame(semantics).to_csv(reports / "column_semantics_candidates.csv", index=False)

    profile = {
        "schema_version": "manual-raw-file-profile.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "raw_path": str(raw_paths[0]),
        "raw_paths": [str(path) for path in raw_paths],
        "shape": list(normalized.shape),
        "selected_table": {
            "header_row": table["header_row"],
            "data_start_row": table["data_start_row"],
            "confidence": table["confidence"],
        },
        "metadata_rows": table["metadata_rows"],
        "continuity": table.get("continuity", {}),
        "duplicate_timestamp_count": int(table.get("duplicate_timestamp_count", 0)),
        "dropped_duplicate_timestamp_count": int(table.get("dropped_duplicate_timestamp_count", 0)),
        "columns": normalized.columns.tolist(),
    }
    write_json(reports / "raw_file_profile.json", profile)
    write_nan_profile(normalized, reports / "nan_profile.csv")
    update_config_train_path(cfg, normalized_path)
    write_domain_evidence_cards(cfg, reports)
    (reports / "table_detection_report.md").write_text(render_table_detection_report(profile, metadata), encoding="utf-8")
    (reports / "cleaning_plan.md").write_text(render_cleaning_plan(profile, metadata, semantics), encoding="utf-8")
    try:
        from manual_report_payloads import write_stage_payload

        write_stage_payload("00P", cfg, paths)
    except Exception:
        pass
    try:
        from log_writer import append_manual_log

        append_manual_log(
            cfg,
            "00P raw intake",
            "메타행을 분리하고 raw CSV를 분석용 테이블로 정규화했습니다.",
            [str(path) for path in raw_paths],
            [str(normalized_path), str(reports / "raw_file_profile.json"), str(reports / "nan_profile.csv")],
            checkpoint="cleaning_plan.md 확인",
            next_step="Stage 00 data review",
        )
    except Exception:
        pass
    return profile


def detect_and_concat_tables(paths: list[Path], cfg: dict[str, Any]) -> dict[str, Any]:
    raw_cfg = cfg.get("raw_intake") or {}
    meta_rows = int(raw_cfg.get("meta_rows") or 5)
    timestamp_col = str(raw_cfg.get("timestamp_col") or "TagName")
    rename_timestamp = str(raw_cfg.get("rename_timestamp") or "timestamp")
    reference_meta = read_meta_block(paths[0], meta_rows)
    frames = []
    for path in paths:
        meta = read_meta_block(path, meta_rows)
        if meta != reference_meta:
            raise ValueError(f"Raw metadata rows do not match: {path}")
        headers = list(reference_meta[0])
        frame = pd.read_csv(path, skiprows=meta_rows, header=None, names=headers, low_memory=False)
        if timestamp_col in frame.columns:
            frame = frame.rename(columns={timestamp_col: rename_timestamp})
        frames.append(frame)
    normalized = pd.concat(frames, ignore_index=True)
    normalized = normalized.dropna(how="all")
    normalized = convert_numeric_columns(normalized)
    if rename_timestamp in normalized.columns:
        normalized[rename_timestamp] = pd.to_datetime(normalized[rename_timestamp], errors="coerce")
        duplicate_count = int(normalized[rename_timestamp].duplicated().sum())
        normalized = normalized.sort_values(rename_timestamp).drop_duplicates(subset=[rename_timestamp], keep="first").reset_index(drop=True)
        continuity = timestamp_continuity(normalized[rename_timestamp])
    else:
        duplicate_count = 0
        continuity = {}
    headers = [rename_timestamp if col == timestamp_col else col for col in reference_meta[0]]
    metadata = build_column_metadata_from_meta(reference_meta, headers)
    metadata_rows = [{"row_index": idx, "type": str(row[0]), "raw_key": str(row[0])} for idx, row in enumerate(reference_meta)]
    return {
        "header_row": 0,
        "data_start_row": meta_rows,
        "metadata_rows": metadata_rows,
        "metadata": metadata,
        "data": normalized,
        "confidence": "high",
        "continuity": continuity,
        "duplicate_timestamp_count": duplicate_count,
        "dropped_duplicate_timestamp_count": duplicate_count,
    }


def read_meta_block(path: Path, row_count: int) -> list[list[str]]:
    rows = pd.read_csv(path, header=None, nrows=row_count, dtype=str, keep_default_na=False).fillna("")
    return [[str(value).strip() for value in row.tolist()] for _, row in rows.iterrows()]


def build_column_metadata_from_meta(rows: list[list[str]], headers: list[str]) -> list[dict[str, Any]]:
    metadata = []
    descriptions = rows[1] if len(rows) > 1 else []
    units = rows[2] if len(rows) > 2 else []
    plot_min = rows[3] if len(rows) > 3 else []
    plot_max = rows[4] if len(rows) > 4 else []
    for idx, header in enumerate(headers):
        metadata.append(
            {
                "column": header,
                "description": descriptions[idx] if idx < len(descriptions) else "",
                "units": units[idx] if idx < len(units) else "",
                "plot_min": plot_min[idx] if idx < len(plot_min) else "",
                "plot_max": plot_max[idx] if idx < len(plot_max) else "",
            }
        )
    return metadata


def timestamp_continuity(values: pd.Series) -> dict[str, Any]:
    timestamps = pd.to_datetime(values, errors="coerce")
    diffs = timestamps.diff().dropna().dt.total_seconds()
    gap_mask = diffs != 1.0
    first_gap_after = None
    if gap_mask.any():
        idx = gap_mask[gap_mask].index[0]
        prev_idx = idx - 1
        if prev_idx in timestamps.index and pd.notna(timestamps.loc[prev_idx]):
            first_gap_after = timestamps.loc[prev_idx].isoformat()
    return {
        "row_count": int(len(timestamps)),
        "valid_timestamp_count": int(timestamps.notna().sum()),
        "invalid_timestamp_count": int(timestamps.isna().sum()),
        "gap_count": int(gap_mask.sum()) if not diffs.empty else 0,
        "first_gap_after": first_gap_after,
        "min_gap_seconds": float(diffs.min()) if not diffs.empty else None,
        "max_gap_seconds": float(diffs.max()) if not diffs.empty else None,
    }


def write_nan_profile(df: pd.DataFrame, path: Path) -> None:
    rows = []
    total = max(1, len(df))
    for col in df.columns:
        missing = int(df[col].isna().sum())
        rows.append({"column": col, "missing_count": missing, "missing_rate_pct": missing / total * 100.0})
    pd.DataFrame(rows).to_csv(path, index=False)


def update_config_train_path(cfg: dict[str, Any], normalized_path: Path) -> None:
    config_path = cfg.get("_config_path")
    if not config_path:
        return
    path = Path(str(config_path))
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["train_path"] = str(normalized_path.resolve())
    payload.setdefault("raw_intake", {})["last_normalized_train_path"] = str(normalized_path.resolve())
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_table(path: Path) -> dict[str, Any]:
    raw = read_raw_table(path)
    metadata_rows: list[dict[str, Any]] = []
    header_row = 0
    for idx, row in raw.iterrows():
        first = str(row.iloc[0]).strip().lower()
        if first in METADATA_KEYS:
            metadata_rows.append({"row_index": int(idx), "type": METADATA_KEYS[first], "raw_key": str(row.iloc[0])})
            continue
        non_empty = sum(1 for value in row.tolist() if str(value).strip())
        if non_empty >= 2:
            header_row = int(idx)
            break
    headers = [str(value).strip() or f"unnamed_{i}" for i, value in enumerate(raw.iloc[header_row].tolist())]
    data = raw.iloc[header_row + 1 :].copy()
    data.columns = headers
    data = data.dropna(how="all")
    data = data.loc[:, [col for col in data.columns if not str(col).startswith("unnamed_")]]
    data = convert_numeric_columns(data.reset_index(drop=True))
    metadata = build_column_metadata(raw, header_row, headers)
    return {
        "header_row": header_row,
        "data_start_row": header_row + 1,
        "metadata_rows": metadata_rows,
        "metadata": metadata,
        "data": data,
        "confidence": "high" if metadata_rows else "medium",
    }


def read_raw_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, header=None, dtype=str).fillna("")
    return pd.read_csv(path, header=None, dtype=str, keep_default_na=False).fillna("")


def build_column_metadata(raw: pd.DataFrame, header_row: int, headers: list[str]) -> list[dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {header: {"column": header} for header in headers if header and not header.startswith("unnamed_")}
    for idx in range(header_row):
        row = raw.iloc[idx]
        key = METADATA_KEYS.get(str(row.iloc[0]).strip().lower())
        if not key:
            continue
        for col_index, header in enumerate(headers):
            if col_index == 0 or header.startswith("unnamed_"):
                continue
            value = str(row.iloc[col_index]).strip()
            if value:
                metadata.setdefault(header, {"column": header})[key] = value
    for header, item in metadata.items():
        item.setdefault("description", "")
        item.setdefault("units", "")
        item.setdefault("plot_min", "")
        item.setdefault("plot_max", "")
    return list(metadata.values())


def convert_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        converted = pd.to_numeric(out[col], errors="coerce")
        if converted.notna().sum() >= max(1, int(len(out) * 0.6)):
            out[col] = converted
    return out


def semantic_candidates(metadata: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    target = str(cfg.get("target_col") or "")
    rows = []
    for item in metadata:
        column = str(item.get("column") or "")
        desc = str(item.get("description") or "")
        text = f"{column} {desc}".lower()
        group = "unknown"
        confidence = "low"
        if column == target or "emission" in text:
            group, confidence = "target_or_emission", "high"
        elif any(token in text for token in ["temp", "ttxm", "temperature", "온도"]):
            group, confidence = "thermal_or_temperature", "high"
        elif any(token in text for token in ["time", "date", "timestamp", "시간"]):
            group, confidence = "time_order", "high"
        elif any(token in text for token in ["pressure", "press", "cpd", "npr", "압력"]):
            group, confidence = "pressure", "medium"
        elif any(token in text for token in ["flow", "fq", "mass", "유량"]):
            group, confidence = "flow_or_mass", "medium"
        rows.append(
            {
                "column": column,
                "description": desc,
                "units": item.get("units", ""),
                "semantic_group": group,
                "confidence": confidence,
                "usage_stage": "00P_raw_intake",
            }
        )
    return rows


def write_domain_evidence_cards(cfg: dict[str, Any], reports: Path) -> None:
    raw_cfg = cfg.get("raw_intake") or {}
    budget = cfg.get("context_budget") or {}
    max_chars = int(budget.get("max_chars_per_doc") or 1200)
    cards = []
    for value in raw_cfg.get("metadata_doc_paths", []) or []:
        path = resolve_project_path(cfg, str(value))
        if not path or not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        cards.append(
            {
                "source": str(path),
                "summary": re.sub(r"\s+", " ", text).strip()[:max_chars],
                "column_candidates": [],
                "confidence": "source_provided",
                "usage_stage": "00P_raw_intake",
            }
        )
    write_json(reports / "domain_evidence_cards.json", {"schema_version": "manual-domain-evidence-cards.v1", "cards": cards})


def render_table_detection_report(profile: dict[str, Any], metadata: list[dict[str, Any]]) -> str:
    lines = [
        "# Raw Table Detection Report",
        "",
        f"- raw_path: `{profile.get('raw_path')}`",
        f"- header_row: `{profile.get('selected_table', {}).get('header_row')}`",
        f"- data_start_row: `{profile.get('selected_table', {}).get('data_start_row')}`",
        f"- shape: `{profile.get('shape')}`",
        f"- confidence: `{profile.get('selected_table', {}).get('confidence')}`",
        "",
        "## Column Metadata",
        "",
        "| column | description | units |",
        "|---|---|---|",
    ]
    for item in metadata:
        lines.append(f"| {item.get('column')} | {item.get('description', '')} | {item.get('units', '')} |")
    return "\n".join(lines).strip() + "\n"


def render_cleaning_plan(profile: dict[str, Any], metadata: list[dict[str, Any]], semantics: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "# Cleaning Plan",
            "",
            "## 자동 수행",
            "",
            "- Description/Units/Plot Min/Plot Max 같은 메타행은 데이터행에서 분리합니다.",
            "- 감지된 헤더행 이후의 행만 모델 입력 후보로 저장합니다.",
            "- 60% 이상 숫자로 변환 가능한 컬럼은 numeric으로 변환합니다.",
            "",
            "## 사용자 확인 필요",
            "",
            "- 헤더행 감지 confidence가 medium 이하이면 원본 파일의 표 범위를 확인합니다.",
            "- semantic_group이 unknown인 컬럼은 Stage 00/02에서 의미를 보강합니다.",
            "- 문서 기반 의미 추정은 `domain_evidence_cards.json`의 짧은 evidence card만 기본 컨텍스트로 사용합니다.",
            "",
            f"- normalized_train.csv rows/cols: `{profile.get('shape')}`",
            f"- metadata columns: `{len(metadata)}`",
            f"- semantic candidates: `{len(semantics)}`",
            "",
        ]
    )
