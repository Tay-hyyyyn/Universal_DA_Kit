from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_SITE_PACKAGES = Path(__file__).resolve().parents[4] / ".venv" / "Lib" / "site-packages"
if PROJECT_SITE_PACKAGES.exists():
    sys.path.insert(0, str(PROJECT_SITE_PACKAGES))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from log_writer import append_manual_log, parse_log_entries, resolve_log_path
from manual_common import load_config, load_modeling_data, read_json, resolve_project_path, run_paths
from manual_domain_expert import write_action_items_files
from manual_report_payloads import load_stage_payload
from manual_state import refresh_run_state


STAGE_NAMES = {
    "00P": "stage_00p_raw_intake.pdf",
    "00": "stage_00_data_review.pdf",
    "01": "stage_01_env_check.pdf",
    "02": "stage_02_diagnosis.pdf",
    "02H": "stage_02h_hypothesis_planning.pdf",
    "03": "stage_03_feature_build.pdf",
    "04": "stage_04_validation.pdf",
    "05": "stage_05_model.pdf",
    "05H": "stage_05h_hypothesis_evaluation.pdf",
    "06": "stage_06_submission.pdf",
}


def set_theme() -> str:
    sns.set_theme(style="whitegrid")
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["axes.unicode_minus"] = False
    for font in ["Malgun Gothic", "Noto Sans CJK KR", "Noto Sans KR", "Arial Unicode MS", "DejaVu Sans"]:
        try:
            matplotlib.font_manager.findfont(font, fallback_to_default=False)
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = [font]
            return font
        except Exception:
            continue
    return "default"


def fig_a4() -> plt.Figure:
    return plt.figure(figsize=(8.27, 11.69))


def header(fig: plt.Figure, title: str, subtitle: str, footer: str) -> None:
    fig.text(0.06, 0.965, title, fontsize=17, fontweight="bold", va="top")
    fig.text(0.06, 0.938, subtitle, fontsize=9.5, color="#374151", va="top")
    fig.lines.append(plt.Line2D([0.06, 0.94], [0.925, 0.925], transform=fig.transFigure, color="#111827", lw=1))
    fig.text(0.06, 0.025, footer, fontsize=7.5, color="#6B7280", va="bottom")


def kpi_box(ax: plt.Axes, title: str, items: list[tuple[str, str]], face: str = "#F3F4F6") -> None:
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, color=face, ec="#D1D5DB", lw=0.8))
    ax.text(0.04, 0.92, title, fontsize=11, fontweight="bold", va="top")
    y = 0.78
    for key, value in items:
        ax.text(0.04, y, key, fontsize=8.5, fontweight="bold", color="#111827", va="top")
        ax.text(0.40, y, str(value)[:70], fontsize=8.5, color="#374151", va="top")
        y -= 0.14
        if y < 0.08:
            break


def decision_box(ax: plt.Axes, decisions: list[dict], stage: str) -> None:
    relevant = [d for d in decisions if str(d.get("stage", "")).startswith(stage)]
    if not relevant:
        kpi_box(ax, "결정 강조", [("상태", "아직 기록된 사용자/설정 결정이 없습니다.")], face="#FFF7ED")
        return
    items = []
    for d in relevant[:5]:
        items.append((str(d.get("decision", "")), f"선택={d.get('selected')} | 영향={d.get('impact')}"))
    kpi_box(ax, "결정 강조(수정 가능)", items, face="#FFF7ED")


def draw_table(ax: plt.Axes, df: pd.DataFrame, title: str, max_rows: int = 12) -> None:
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    if df.empty:
        ax.text(0.02, 0.5, "No data available yet.", fontsize=10)
        return
    view = df.head(max_rows).copy()
    for col in view.columns:
        view[col] = view[col].astype(str).str.slice(0, 42)
    table = ax.table(cellText=view.values, colLabels=view.columns, cellLoc="left", colLoc="left", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1.0, 1.18)


def draw_text_block(ax: plt.Axes, title: str, text: str, max_chars: int = 2800) -> None:
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    clean = str(text or "No content available yet.").strip()
    if len(clean) > max_chars:
        clean = clean[:max_chars] + "\n\n[truncated in PDF; see the md/json artifact for full content]"
    ax.text(0.01, 0.98, clean, fontsize=8.3, va="top", ha="left", wrap=True)


def load_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.DataFrame()


def parse_project_log(log_path: str | Path) -> list[dict]:
    return parse_log_entries(log_path)


def payload_df(payload: dict, name: str) -> pd.DataFrame:
    return pd.DataFrame((payload.get("tables") or {}).get(name, []))


def section_00P(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("00P", cfg, paths)
    kpis = payload.get("kpis", {})
    metadata = payload_df(payload, "column_metadata")
    semantics = payload_df(payload, "semantic_candidates")
    fig = fig_a4()
    header(fig, "00P. Raw 데이터 인입", "메타행, 헤더, 단위, 의미 후보를 분리한 정제 전 점검", footer)
    gs = fig.add_gridspec(3, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.35, wspace=0.25)
    kpi_box(
        fig.add_subplot(gs[0, 0]),
        "Raw table detection",
        [
            ("raw_path", kpis.get("raw_path")),
            ("shape", kpis.get("shape")),
            ("header_row", kpis.get("header_row")),
            ("data_start", kpis.get("data_start_row")),
            ("confidence", kpis.get("confidence")),
        ],
    )
    decision_box(fig.add_subplot(gs[0, 1]), payload.get("decision_highlights", []), "00P")
    draw_table(fig.add_subplot(gs[1, :]), metadata, "Column metadata", 12)
    draw_table(fig.add_subplot(gs[2, :]), semantics, "Semantic candidates", 12)
    pdf.savefig(fig)
    plt.close(fig)


def section_00(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("00", cfg, paths)
    kpis = payload.get("kpis", {})
    target_summary = payload.get("target_summary", {})
    col_dict = payload_df(payload, "column_preview")
    corr_df = payload_df(payload, "top_correlations")
    train, _, _ = load_modeling_data(cfg)
    target = cfg["target_col"]
    target_label = kpis.get("target_col_label") or target
    fig = fig_a4()
    header(fig, "00. 데이터 전체 리뷰", "컬럼, 타깃, 행 구조, 분포, 데이터 상황 해석", footer)
    gs = fig.add_gridspec(3, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.34, wspace=0.25)
    kpi_box(
        fig.add_subplot(gs[0, 0]),
        "데이터 요약",
        [
            ("작업", kpis.get("task_type", cfg["task_type"])),
            ("타깃", target_label),
            ("train", kpis.get("train_shape")),
            ("test", kpis.get("test_shape")),
            ("맥락", kpis.get("inferred_context", "")),
        ],
    )
    decision_box(fig.add_subplot(gs[0, 1]), payload.get("decision_highlights", []), "00")
    ax = fig.add_subplot(gs[1, 0])
    if target in train.columns and pd.api.types.is_numeric_dtype(train[target]):
        vals = pd.to_numeric(train[target], errors="coerce").dropna()
        ax.hist(vals, bins=70, color="#2563EB", alpha=0.85)
        ax.set_title("타깃 분포", loc="left")
        ax.set_xlabel(target_label)
    else:
        draw_table(ax, train[[target]].head(10) if target in train else pd.DataFrame(), "타깃 예시")
    ax = fig.add_subplot(gs[1, 1])
    semantic_df = payload_df(payload, "semantic_groups")
    if not semantic_df.empty:
        groups = semantic_df.set_index("semantic_group")["columns"].head(12)
        ax.barh(groups.index[::-1], groups.values[::-1], color="#10B981")
        ax.set_title("컬럼 그룹(semantic)", loc="left")
        ax.set_xlabel("컬럼 수")
    else:
        ax.axis("off")
    table_cols = ["column", "role", "semantic_group", "dtype_train", "missing_rate_train", "mean", "std", "skewness", "interpretation"]
    preview_df = col_dict if not col_dict.empty else pd.DataFrame([target_summary]) if target_summary else pd.DataFrame()
    if not corr_df.empty and "column" not in preview_df.columns:
        preview_df = preview_df
    draw_table(fig.add_subplot(gs[2, :]), preview_df[[c for c in table_cols if c in preview_df.columns]].head(12), "컬럼 사전 미리보기", 12)
    pdf.savefig(fig)
    plt.close(fig)


def section_01(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("01", cfg, paths)
    kpis = payload.get("kpis", {})
    fig = fig_a4()
    header(fig, "01. 환경 및 입력 점검", "Python, 패키지, 설정된 입력 파일 확인", footer)
    gs = fig.add_gridspec(2, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.32, wspace=0.25)
    kpi_box(fig.add_subplot(gs[0, 0]), "실행 환경", [("python", kpis.get("python_version")), ("실행 파일", kpis.get("python_executable")), ("준비 상태", kpis.get("ready"))])
    decision_box(fig.add_subplot(gs[0, 1]), payload.get("decision_highlights", []), "01")
    packages = payload_df(payload, "packages")
    files = payload_df(payload, "files")
    draw_table(fig.add_subplot(gs[1, 0]), packages, "패키지", 12)
    draw_table(fig.add_subplot(gs[1, 1]), files, "입력 파일", 10)
    pdf.savefig(fig)
    plt.close(fig)


def section_02(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("02", cfg, paths)
    kpis = payload.get("kpis", {})
    missing = payload_df(payload, "top_missing")
    evidence = payload_df(payload, "outlier_evidence")
    fig = fig_a4()
    header(fig, "02. 결측 및 이상치 진단", "결측 원인 가설, 이상치 가설, 처리 추천 근거", footer)
    gs = fig.add_gridspec(3, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.35, wspace=0.25)
    kpi_box(
        fig.add_subplot(gs[0, 0]),
        "이상치 근거",
        [
            ("판단", kpis.get("judgment")),
            ("왜도", kpis.get("skewness")),
            ("robust z 최대", kpis.get("robust_z_max")),
            ("p99/median", kpis.get("p99_median_ratio")),
            ("drift 후보", kpis.get("drift_candidate_count")),
        ],
    )
    decision_box(fig.add_subplot(gs[0, 1]), payload.get("decision_highlights", []), "02")
    ax = fig.add_subplot(gs[1, :])
    if not missing.empty:
        top = missing.sort_values("missing_rate_train", ascending=False).head(15)
        ypos = np.arange(len(top))
        ax.barh(ypos, top["missing_rate_train"], color="#2563EB", label="train 결측률")
        if "missing_rate_test" in top:
            ax.scatter(top["missing_rate_test"], ypos, color="#F59E0B", label="test 결측률")
        ax.set_yticks(ypos)
        label_col = "feature_name_ko" if "feature_name_ko" in top.columns else "feature"
        ax.set_yticklabels(top[label_col].astype(str), fontsize=8)
        ax.invert_yaxis()
        ax.set_title("결측률 상위 피처", loc="left")
        ax.legend(fontsize=8)
    else:
        ax.axis("off")
        ax.text(0.02, 0.5, "결측 가설 파일을 찾지 못했습니다.")
    ax = fig.add_subplot(gs[2, 0])
    if not missing.empty and "target_shift_when_missing" in missing:
        x = pd.to_numeric(missing["missing_rate_train"], errors="coerce")
        y = pd.to_numeric(missing["target_shift_when_missing"], errors="coerce")
        ax.scatter(x, y, s=28, color="#10B981", alpha=0.75)
        ax.axhline(0, color="#374151", lw=1)
        ax.set_title("결측률과 타깃 변화", loc="left")
        ax.set_xlabel("결측률(%)")
        ax.set_ylabel("타깃 변화")
    else:
        ax.axis("off")
    table_cols = ["feature_name_ko", "feature", "semantic_group", "corr_with_target", "top_vs_rest_diff"]
    draw_table(fig.add_subplot(gs[2, 1]), evidence[[c for c in table_cols if c in evidence.columns]].head(10), "이상치 설명 후보 피처", 10)
    pdf.savefig(fig)
    plt.close(fig)


def section_03(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("03", cfg, paths)
    menu = payload_df(payload, "feature_candidates")
    kpis = payload.get("kpis", {})
    fig = fig_a4()
    header(fig, "03. 피처 생성 및 전처리", "데이터 특성 기반 후보, 사용자 선택, 다중공선성 위험", footer)
    gs = fig.add_gridspec(3, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.35, wspace=0.25)
    kpi_box(
        fig.add_subplot(gs[0, 0]),
        "피처 생성 설정",
        [
            ("피처군", ",".join(kpis.get("feature_families", []) or [])),
            ("생성 개수", kpis.get("generated_feature_count")),
            ("전체 피처", kpis.get("feature_column_count")),
            ("가설 후보", kpis.get("hypothesis_candidate_count")),
            ("상관 pruning", kpis.get("correlation_pruning_applied")),
        ],
    )
    decision_box(fig.add_subplot(gs[0, 1]), read_json(paths["base"] / "decision_log.json", []), "03")
    ax = fig.add_subplot(gs[1, 0])
    if not menu.empty:
        counts = menu["family"].value_counts()
        ax.barh(counts.index[::-1], counts.values[::-1], color="#2563EB")
        ax.set_title("피처 후보군", loc="left")
        ax.set_xlabel("후보 수")
    else:
        ax.axis("off")
    ax = fig.add_subplot(gs[1, 1])
    generated = pd.Series((payload.get("sections", {}).get("manifest_summary") or {}).get("generated_features", []) or [])
    if len(generated):
        fam = generated.str.extract(r"(__per__|log1p|pressure|group_)")[0].fillna("other").value_counts()
        ax.barh(fam.index[::-1], fam.values[::-1], color="#10B981")
        ax.set_title("생성된 피처 유형", loc="left")
    else:
        ax.axis("off")
    table_cols = ["family", "feature_name", "recommendation_basis", "multicollinearity_risk", "leakage_risk"]
    draw_table(fig.add_subplot(gs[2, :]), menu[[c for c in table_cols if c in menu.columns]].head(12), "피처 후보 메뉴", 12)
    pdf.savefig(fig)
    plt.close(fig)


def section_02H(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("02H", cfg, paths)
    plan = payload_df(payload, "validation_plan")
    seed_report = str((payload.get("sections") or {}).get("seed_report") or "")
    fig = fig_a4()
    header(fig, "02H. Hypothesis Planning", "Starter hypotheses, domain/evidence context, and validation plan", footer)
    gs = fig.add_gridspec(3, 1, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.35)
    kpis = payload.get("kpis", {})
    kpi_box(
        fig.add_subplot(gs[0, 0]),
        "Hypothesis checkpoint",
        [
            ("hypotheses", kpis.get("hypothesis_count")),
            ("accepted", kpis.get("accepted_count")),
            ("open", kpis.get("open_count")),
            ("evidence cards", kpis.get("evidence_card_count")),
            ("registry", "hypothesis_registry.json"),
        ],
    )
    draw_table(fig.add_subplot(gs[1, 0]), plan.head(8), "Validation plan", 8)
    draw_text_block(fig.add_subplot(gs[2, 0]), "Seed report excerpt", seed_report, 1500)
    pdf.savefig(fig)
    plt.close(fig)


def section_04(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("04", cfg, paths)
    summary = payload.get("sections", {}).get("summary") or {}
    fig = fig_a4()
    header(fig, "04. 검증 분할", "15% 샘플 검증, group 누수 방지, full-train 게이트", footer)
    gs = fig.add_gridspec(2, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.32, wspace=0.25)
    kpi_box(fig.add_subplot(gs[0, 0]), "폴드 요약", [("분할", summary.get("split_type")), ("행 수", summary.get("rows")), ("폴드", summary.get("folds")), ("그룹 누수", summary.get("group_leakage_count"))])
    decision_box(fig.add_subplot(gs[0, 1]), read_json(paths["base"] / "decision_log.json", []), "04")
    ax = fig.add_subplot(gs[1, :])
    counts = summary.get("fold_counts") or {}
    if counts:
        ax.bar(list(counts.keys()), list(counts.values()), color="#2563EB")
        ax.set_title("폴드별 행 수", loc="left")
        ax.set_xlabel("폴드")
        ax.set_ylabel("행 수")
    else:
        ax.axis("off")
    pdf.savefig(fig)
    plt.close(fig)


def section_05(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("05", cfg, paths)
    metrics = payload_df(payload, "metrics")
    tuning = payload_df(payload, "tuning_preview")
    oof = load_df(paths["models"] / "oof_predictions.csv")
    metric = (payload.get("kpis") or {}).get("metric_primary") or cfg.get("metric_primary") or ("rmse" if cfg["task_type"] == "regression" else "log_loss")
    fig = fig_a4()
    header(fig, "05. 모델 학습", "XGBoost 필수, 해석 모델 선택, 튜닝과 OOF 진단", footer)
    gs = fig.add_gridspec(3, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.35, wspace=0.25)
    draw_table(fig.add_subplot(gs[0, 0]), metrics.head(8), "모델 성능 지표", 8)
    decision_box(fig.add_subplot(gs[0, 1]), read_json(paths["base"] / "decision_log.json", []), "05")
    ax = fig.add_subplot(gs[1, :])
    if not tuning.empty and metric in tuning.columns:
        vals = pd.to_numeric(tuning[metric], errors="coerce").dropna()
        ax.scatter(np.arange(len(vals)), vals, s=18, alpha=0.65, color="#2563EB")
        ax.set_title(f"튜닝 시행({metric})", loc="left")
        ax.set_xlabel("시행")
        ax.set_ylabel(metric)
    else:
        ax.axis("off")
    ax = fig.add_subplot(gs[2, :])
    if cfg["task_type"] == "regression" and not metrics.empty and not oof.empty:
        best = str(metrics.iloc[0]["model"])
        target = cfg["target_col"]
        if best in oof.columns and target in oof.columns:
            y_true = pd.to_numeric(oof[target], errors="coerce")
            y_pred = pd.to_numeric(oof[best], errors="coerce")
            mask = y_true.notna() & y_pred.notna()
            res = y_true[mask] - y_pred[mask]
            idx = np.random.default_rng(42).choice(len(res), size=min(15000, len(res)), replace=False)
            ax.scatter(y_true[mask].to_numpy()[idx], res.to_numpy()[idx], s=8, alpha=0.25, color="#F59E0B")
            ax.axhline(0, color="#374151", lw=1)
            ax.set_title(f"OOF 잔차(best={best})", loc="left")
            ax.set_xlabel("실제값")
            ax.set_ylabel("실제값 - 예측값")
        else:
            ax.axis("off")
    else:
        ax.axis("off")
    pdf.savefig(fig)
    plt.close(fig)


def section_05H(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("05H", cfg, paths)
    result_rows = payload_df(payload, "validation_results")
    result_md = str((payload.get("sections") or {}).get("validation_report") or "")
    fig = fig_a4()
    header(fig, "05H. Hypothesis Evaluation", "Supported, partially supported, and not-testable hypotheses after modeling", footer)
    gs = fig.add_gridspec(2, 1, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.35)
    draw_table(fig.add_subplot(gs[0, 0]), result_rows[["hypothesis_id", "support_status", "evidence", "next_action"]] if not result_rows.empty else result_rows, "Hypothesis validation results", 10)
    draw_text_block(fig.add_subplot(gs[1, 0]), "Result notes", result_md, 2200)
    pdf.savefig(fig)
    plt.close(fig)


def section_06(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("06", cfg, paths)
    submission = payload_df(payload, "submission_preview")
    weights = payload_df(payload, "ensemble_weights")
    choices = (payload.get("sections") or {}).get("postprocess_choices") or {}
    fig = fig_a4()
    header(fig, "06. 제출 및 후처리", "앙상블, clip, sample 순서 보존, 최종 예측 분포", footer)
    gs = fig.add_gridspec(3, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.35, wspace=0.25)
    kpi_box(
        fig.add_subplot(gs[0, 0]),
        "제출 설정",
        [
            ("앙상블", choices.get("ensemble_method")),
            ("상한 클립", choices.get("upper_clip")),
            ("클립 값", choices.get("upper_clip_value")),
            ("음수 클립", choices.get("clip_negative")),
        ],
    )
    decision_box(fig.add_subplot(gs[0, 1]), read_json(paths["base"] / "decision_log.json", []), "06")
    ax = fig.add_subplot(gs[1, :])
    target_cols = [c for c in submission.columns if c != (cfg.get("id_col") or "ID")]
    if target_cols:
        vals = pd.to_numeric(submission[target_cols[-1]], errors="coerce").dropna()
        ax.hist(vals, bins=70, color="#2563EB", alpha=0.85)
        ax.set_title("제출 예측 분포", loc="left")
        ax.set_xlabel(target_cols[-1])
    else:
        ax.axis("off")
    draw_table(fig.add_subplot(gs[2, :]), weights, "앙상블 가중치", 12)
    pdf.savefig(fig)
    plt.close(fig)


def section_log_history(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    entries = parse_project_log(resolve_log_path(cfg))
    rows = []
    for entry in entries[-30:]:
        rows.append(
            {
                "date": entry.get("date"),
                "time": entry.get("time"),
                "stage": entry.get("stage"),
                "purpose": entry.get("purpose"),
                "checkpoint": entry.get("checkpoint"),
            }
        )
    fig = fig_a4()
    header(fig, "Project Log", "Chronological log.md entries recorded during this dataset analysis", footer)
    gs = fig.add_gridspec(1, 1, left=0.06, right=0.94, bottom=0.07, top=0.90)
    draw_table(fig.add_subplot(gs[0, 0]), pd.DataFrame(rows), "Recent work history", 30)
    pdf.savefig(fig)
    plt.close(fig)


def section_06(pdf: PdfPages, cfg: dict, paths: dict[str, Path], footer: str) -> None:
    payload = load_stage_payload("06", cfg, paths)
    kpis = payload.get("kpis", {})
    submission = payload_df(payload, "submission_preview")
    weights = payload_df(payload, "ensemble_weights")
    hourly = payload_df(payload, "holdout_error_by_hour")
    choices = (payload.get("sections") or {}).get("postprocess_choices") or {}
    mode = str(kpis.get("mode") or cfg.get("submission_mode") or "submission")
    fig = fig_a4()
    header(fig, "06. Prediction Output", "Holdout residual analysis or submission postprocessing", footer)
    gs = fig.add_gridspec(3, 2, left=0.06, right=0.94, bottom=0.07, top=0.90, hspace=0.35, wspace=0.25)
    kpi_box(
        fig.add_subplot(gs[0, 0]),
        "Output settings",
        [
            ("mode", mode),
            ("ensemble", choices.get("ensemble_method")),
            ("upper_clip", choices.get("upper_clip")),
            ("rmse", kpis.get("rmse")),
            ("mae", kpis.get("mae")),
        ],
    )
    decision_box(fig.add_subplot(gs[0, 1]), read_json(paths["base"] / "decision_log.json", []), "06")
    ax = fig.add_subplot(gs[1, :])
    value_col = "residual" if "residual" in submission.columns else ("prediction" if "prediction" in submission.columns else None)
    if value_col:
        vals = pd.to_numeric(submission[value_col], errors="coerce").dropna()
        ax.hist(vals, bins=70, color="#2563EB", alpha=0.85)
        ax.set_title(f"{value_col} distribution", loc="left")
        ax.set_xlabel(value_col)
    else:
        target_cols = [c for c in submission.columns if c != (cfg.get("id_col") or "ID")]
        if target_cols:
            vals = pd.to_numeric(submission[target_cols[-1]], errors="coerce").dropna()
            ax.hist(vals, bins=70, color="#2563EB", alpha=0.85)
            ax.set_title("Prediction distribution", loc="left")
            ax.set_xlabel(target_cols[-1])
        else:
            ax.axis("off")
    if mode.lower() == "holdout_analysis":
        draw_table(fig.add_subplot(gs[2, :]), hourly, "Holdout error by hour", 24)
    else:
        draw_table(fig.add_subplot(gs[2, :]), weights, "Ensemble weights", 12)
    pdf.savefig(fig)
    plt.close(fig)


SECTION_FUNCS = {
    "00P": section_00P,
    "00": section_00,
    "01": section_01,
    "02": section_02,
    "02H": section_02H,
    "03": section_03,
    "04": section_04,
    "05": section_05,
    "05H": section_05H,
    "06": section_06,
}


def write_pdf_for_stages(cfg: dict, run_id: str, stages: list[str], out_path: Path, footer: str) -> None:
    paths = run_paths(cfg, run_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(out_path) as pdf:
        for stage in stages:
            SECTION_FUNCS[stage](pdf, cfg, paths, footer)
        if len(stages) > 1:
            section_log_history(pdf, cfg, paths, footer)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual 단계별 PDF 또는 통합 PDF를 생성합니다.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", default="all", choices=["all", "integrated", *STAGE_NAMES.keys()])
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    write_action_items_files(cfg, paths)
    font = set_theme()
    footer = f"생성 시각 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 폰트 {font} | Run {args.run_id}"
    if args.stage == "all":
        for stage, filename in STAGE_NAMES.items():
            write_pdf_for_stages(cfg, args.run_id, [stage], paths["pdf"] / filename, footer)
        write_pdf_for_stages(cfg, args.run_id, list(STAGE_NAMES.keys()), paths["pdf"] / "analysis_report_integrated.pdf", footer)
        append_manual_log(
            cfg,
            "07 report writer",
            "Generate stage PDFs and integrated report with project log history",
            [args.config],
            [str(paths["pdf"] / "analysis_report_integrated.pdf")],
            checkpoint="Final field-action review",
        )
        refresh_run_state(cfg, args.run_id)
        print(f"단계별 PDF 및 통합 PDF 생성 완료: {paths['pdf']}")
        return
    if args.stage == "integrated":
        out = Path(args.out) if args.out else paths["pdf"] / "analysis_report_integrated.pdf"
        write_pdf_for_stages(cfg, args.run_id, list(STAGE_NAMES.keys()), out, footer)
        append_manual_log(
            cfg,
            "07 report writer",
            "Generate integrated report with project log history",
            [args.config],
            [str(out)],
            checkpoint="Final field-action review",
        )
        refresh_run_state(cfg, args.run_id)
        print(f"통합 PDF 생성 완료: {out}")
        return
    out = Path(args.out) if args.out else paths["pdf"] / STAGE_NAMES[args.stage]
    write_pdf_for_stages(cfg, args.run_id, [args.stage], out, footer)
    append_manual_log(
        cfg,
        "07 report writer",
        f"Generate stage report {args.stage}",
        [args.config],
        [str(out)],
        checkpoint="Report review",
    )
    refresh_run_state(cfg, args.run_id)
    print(f"단계 PDF 생성 완료: {out}")


if __name__ == "__main__":
    main()
