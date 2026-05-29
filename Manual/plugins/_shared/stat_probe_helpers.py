from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_CORE_PATTERNS = ["NOX", "O2", "DWATT", "EXHMASS", "TTXM", "CSGV", "CPD", "NQJ", "VNPR"]


def run_stat_probe(frame: pd.DataFrame, cfg: dict[str, Any], reports_dir: str | Path) -> dict[str, Any]:
    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)
    target = str(cfg.get("target_col") or "")
    time_col = str(cfg.get("time_col") or "")
    if target not in frame.columns:
        raise ValueError(f"target_col not found for stat probe: {target}")

    work = frame.copy()
    if time_col and time_col in work.columns:
        work[time_col] = pd.to_datetime(work[time_col], errors="coerce")
        work = work.sort_values(time_col).reset_index(drop=True)

    numeric_cols = [
        col
        for col in work.columns
        if col != time_col and pd.api.types.is_numeric_dtype(pd.to_numeric(work[col], errors="coerce"))
    ]
    if target not in numeric_cols:
        numeric_cols.insert(0, target)
    corr_matrix = work[numeric_cols].apply(pd.to_numeric, errors="coerce").corr()
    corr_matrix.to_csv(reports / "correlation_matrix.csv")

    top_corr = _top_target_correlations(corr_matrix, target)
    bootstrap = _bootstrap_effects(work, target, [row["feature"] for row in top_corr[:12]])
    bootstrap.to_csv(reports / "bootstrap_effects.csv", index=False)
    lag = _lag_analysis(work, cfg, target, time_col, [row["feature"] for row in top_corr[:12]])
    lag.to_csv(reports / "lag_analysis.csv", index=False)

    payload = {
        "schema_version": "manual-stat-probe.v1",
        "target_col": target,
        "time_col": time_col,
        "correlation_count": len(top_corr),
        "top_correlations": top_corr[:20],
        "bootstrap_rows": int(len(bootstrap)),
        "lag_rows": int(len(lag)),
        "outputs": {
            "correlation_matrix": str((reports / "correlation_matrix.csv").resolve()),
            "bootstrap_effects": str((reports / "bootstrap_effects.csv").resolve()),
            "lag_analysis": str((reports / "lag_analysis.csv").resolve()),
        },
    }
    (reports / "stat_probe_report.json").write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(reports / "stat_probe_report.md", payload, bootstrap, lag)
    return payload


def _top_target_correlations(corr_matrix: pd.DataFrame, target: str) -> list[dict[str, Any]]:
    if target not in corr_matrix.columns:
        return []
    rows = []
    for feature, corr in corr_matrix[target].drop(labels=[target], errors="ignore").items():
        if pd.isna(corr):
            continue
        rows.append({"feature": str(feature), "corr_with_target": float(corr), "abs_corr": float(abs(corr))})
    rows.sort(key=lambda row: row["abs_corr"], reverse=True)
    return rows


def _bootstrap_effects(frame: pd.DataFrame, target: str, features: list[str]) -> pd.DataFrame:
    rows = []
    y = pd.to_numeric(frame[target], errors="coerce")
    for feature in features:
        if feature not in frame.columns:
            continue
        x = pd.to_numeric(frame[feature], errors="coerce")
        subset = pd.DataFrame({"x": x, "y": y}).dropna()
        if len(subset) < 8:
            continue
        q1 = subset["x"].quantile(0.25)
        q3 = subset["x"].quantile(0.75)
        low = subset.loc[subset["x"] <= q1, "y"]
        high = subset.loc[subset["x"] >= q3, "y"]
        if len(low) == 0 or len(high) == 0:
            continue
        diff = float(high.mean() - low.mean())
        pooled = float(np.sqrt((high.var(ddof=1) + low.var(ddof=1)) / 2.0)) if len(low) > 1 and len(high) > 1 else 0.0
        rows.append(
            {
                "feature": feature,
                "low_count": int(len(low)),
                "high_count": int(len(high)),
                "low_mean_target": float(low.mean()),
                "high_mean_target": float(high.mean()),
                "mean_diff_high_minus_low": diff,
                "effect_size": diff / pooled if pooled else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _lag_analysis(frame: pd.DataFrame, cfg: dict[str, Any], target: str, time_col: str, features: list[str]) -> pd.DataFrame:
    lag_grid = ((cfg.get("hypothesis_defaults") or {}).get("lag_grid") or ["0s", "30s", "60s", "120s", "300s"])
    rows = []
    y = pd.to_numeric(frame[target], errors="coerce")
    for feature in _core_first(features):
        if feature not in frame.columns:
            continue
        x = pd.to_numeric(frame[feature], errors="coerce")
        for label in lag_grid:
            seconds = _parse_seconds(label)
            shifted = x.shift(seconds) if seconds > 0 else x
            corr = shifted.corr(y)
            if pd.isna(corr):
                continue
            rows.append(
                {
                    "feature": feature,
                    "lag_label": str(label),
                    "lag_seconds": int(seconds),
                    "corr_with_target": float(corr),
                    "abs_corr": float(abs(corr)),
                    "time_col": time_col,
                }
            )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["feature", "abs_corr"], ascending=[True, False])
    return out


def _core_first(features: list[str]) -> list[str]:
    def rank(name: str) -> tuple[int, str]:
        upper = name.upper()
        return (0 if any(token in upper for token in DEFAULT_CORE_PATTERNS) else 1, name)

    return sorted(dict.fromkeys(features), key=rank)[:20]


def _parse_seconds(value: Any) -> int:
    text = str(value).strip().lower()
    if text.endswith("ms"):
        return max(0, int(float(text[:-2]) / 1000))
    if text.endswith("s"):
        return max(0, int(float(text[:-1])))
    if text.endswith("m"):
        return max(0, int(float(text[:-1]) * 60))
    return max(0, int(float(text)))


def _write_markdown(path: Path, payload: dict[str, Any], bootstrap: pd.DataFrame, lag: pd.DataFrame) -> None:
    lines = [
        "# Statistical Probe Report",
        "",
        f"- target_col: `{payload.get('target_col')}`",
        f"- correlation_count: `{payload.get('correlation_count')}`",
        f"- bootstrap_rows: `{payload.get('bootstrap_rows')}`",
        f"- lag_rows: `{payload.get('lag_rows')}`",
        "",
        "## Top Correlations",
        "",
    ]
    for row in payload.get("top_correlations", [])[:10]:
        lines.append(f"- `{row['feature']}`: corr={row['corr_with_target']:.6f}")
    if not bootstrap.empty:
        lines += ["", "## Bootstrap Effects", "", _markdown_table(bootstrap.head(10))]
    if not lag.empty:
        lines += ["", "## Lag Candidates", "", _markdown_table(lag.head(15))]
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    view = frame.copy()
    for col in view.columns:
        view[col] = view[col].map(lambda value: "" if pd.isna(value) else str(value)[:80])
    lines = [
        "| " + " | ".join(view.columns) + " |",
        "| " + " | ".join(["---"] * len(view.columns)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]).replace("|", "/") for col in view.columns) + " |")
    return "\n".join(lines)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if pd.isna(value) if not isinstance(value, (dict, list, tuple, str)) else False:
        return None
    return value
