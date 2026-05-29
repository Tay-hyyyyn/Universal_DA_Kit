from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PAUSE_EXIT_CODE = 2
OPEN_STATUSES = {"", "open"}
REVIEWED_STATUSES = {"answered", "accepted", "deferred"}


def hypothesis_status_glossary_lines() -> list[str]:
    return [
        "## Status Glossary",
        "",
        "- `open`: 아직 이 가설에 대한 사용자 판단을 적지 않은 상태입니다.",
        "- `answered`: 가설에 대한 생각은 적었지만 이번 run의 핵심 가설로 강하게 채택하지는 않은 상태입니다.",
        "- `accepted`: 이번 run에서 검증하거나 피처로 반영해도 되는 가설입니다.",
        "- `deferred`: 이번 run에서는 기본 추천 또는 보수적 기본값을 따르겠다는 뜻입니다. 반대가 아니라 판단 보류입니다.",
        "- `auto-proceed`: 사용자가 답을 적지 못한 채 파이프라인을 넘겨야 할 때 열린 가설을 자동으로 `deferred` 처리하는 실행 모드입니다. 문서에 직접 적는 값은 아닙니다.",
        "",
        "## Confidence Glossary",
        "",
        "- `낮음`: 아이디어 수준입니다. 후보로만 남기고 강한 결론으로 쓰지 않습니다.",
        "- `보통`: 데이터와 공정 상식이 어느 정도 맞아 떨어집니다. 검증 후보로 적합합니다.",
        "- `높음`: 현장 지식으로 강하게 지지되는 가설입니다. 우선 검증하거나 우선 해석 대상으로 삼습니다.",
        "",
        "## How To Decide",
        "",
        "- `accepted`: 이번 run에서 정말 시험해 보고 싶은 가설",
        "- `answered`: 의견은 있으나 아직 채택은 보류하는 가설",
        "- `deferred`: 지금은 내 판단 대신 기본 추천을 따르겠다는 가설",
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
    p.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def append_decision_log(paths: dict[str, Path], stage: str, decision: str, selected: str, recommended: str, rationale: str, impact: str) -> None:
    path = paths["base"] / "decision_log.json"
    log = read_json(path, [])
    if not isinstance(log, list):
        log = []
    entry = {
        "created_at": now_iso(),
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
    write_json(path, [*log, entry])


def resolve_project_path(cfg: dict[str, Any], value: str | None) -> Path | None:
    if not value:
        return None
    raw = Path(value)
    if raw.is_absolute():
        return raw
    return (Path(cfg.get("_project_root", ".")).resolve() / raw).resolve()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")



def _normalise_hypothesis_template(item: dict[str, Any], index: int) -> dict[str, Any]:
    out = dict(item)
    out.setdefault("hypothesis_id", f"HYP-CUSTOM-{index:02d}")
    out.setdefault("one_sentence", "")
    out.setdefault("mechanism", "")
    out.setdefault("variables", [])
    out["variables"] = _as_list(out.get("variables"))
    out.setdefault("expected_direction", "")
    out.setdefault("lag", "")
    out.setdefault("exception_mode", "")
    out.setdefault("validation_method", "")
    out["feature_plan"] = _as_list(out.get("feature_plan"))
    out.setdefault("leakage_risk", "unknown")
    out.setdefault("confidence", "보통")
    out.setdefault("status", "open")
    out.setdefault("auto_recommended", False)
    return out


def _generic_default_hypotheses(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    target = str(cfg.get("target_col") or "target")
    time_col = str(cfg.get("time_col") or "")
    group_col = str(cfg.get("group_col") or "")
    return [
        {
            "hypothesis_id": "HYP-GENERIC-LEAKAGE-PROXY",
            "one_sentence": "타깃과 매우 가까운 사후 신호나 계산 파생 변수가 예측 성능을 과도하게 높일 수 있다.",
            "mechanism": "현업 데이터에는 결과가 발생한 뒤 기록되는 상태값, 집계값, 보정값이 섞일 수 있어 실제 예측 시점에서 사용할 수 없는 정보가 모델에 들어갈 수 있다.",
            "variables": [target],
            "expected_direction": "상관이 비정상적으로 높은 변수는 성능 향상보다 누수 위험을 먼저 검토한다.",
            "lag": "0s",
            "exception_mode": "예측 시점 이전에 확정되는 원인 변수라면 누수가 아닐 수 있다.",
            "validation_method": "상관 상위 변수의 생성 시점과 업무 의미를 확인하고 포함/제외 ablation을 비교한다.",
            "feature_plan": [],
            "leakage_risk": "high",
            "confidence": "보통",
            "status": "open",
            "auto_recommended": False,
        },
        {
            "hypothesis_id": "HYP-GENERIC-SEGMENT",
            "one_sentence": "운영 구간, 제품군, 설비군, 고객군 같은 segment에 따라 타깃의 패턴이 달라질 수 있다.",
            "mechanism": "서로 다른 조건의 데이터가 한 모델에 섞이면 평균 성능은 좋아 보여도 특정 구간에서 오차가 커질 수 있다.",
            "variables": [group_col, target] if group_col else [target],
            "expected_direction": "segment별 평균, 분산, 오차가 다르게 나타날 수 있다.",
            "lag": "none",
            "exception_mode": "segment별 표본 수가 너무 작으면 별도 모델보다 regularized 통합 모델이 안전하다.",
            "validation_method": "segment별 EDA, group holdout, segment별 metric을 비교한다.",
            "feature_plan": [],
            "leakage_risk": "medium",
            "confidence": "보통",
            "status": "open",
            "auto_recommended": False,
        },
        {
            "hypothesis_id": "HYP-GENERIC-TEMPORAL-DYNAMICS",
            "one_sentence": "시간 순서가 있는 데이터라면 선행 값, 변화량, rolling 상태가 타깃 예측에 도움을 줄 수 있다.",
            "mechanism": "공정, 수요, 설비, 운영 데이터는 직전 상태와 누적 변화가 다음 타깃에 영향을 주는 경우가 많다.",
            "variables": [time_col, target] if time_col else [target],
            "expected_direction": "lag/rolling 피처가 유효할 수 있으나 미래값 사용은 누수다.",
            "lag": "short~medium",
            "exception_mode": "행 순서가 시간 순서를 의미하지 않으면 lag 피처를 만들면 안 된다.",
            "validation_method": "temporal split에서 lag/rolling 포함 모델과 제외 모델을 비교한다.",
            "feature_plan": [],
            "leakage_risk": "medium",
            "confidence": "보통",
            "status": "open",
            "auto_recommended": False,
        },
        {
            "hypothesis_id": "HYP-GENERIC-NONLINEARITY",
            "one_sentence": "주요 입력 변수는 특정 임계값 이후 타깃에 비선형 영향을 줄 수 있다.",
            "mechanism": "용량 한계, 포화, 병목, 제어 개입, 등급 구간 때문에 선형 모델이 놓치는 구간별 효과가 생길 수 있다.",
            "variables": [target],
            "expected_direction": "hinge, bin, interaction 피처가 일부 구간의 오차를 줄일 수 있다.",
            "lag": "none",
            "exception_mode": "표본 수가 적거나 구간 기준이 불안정하면 과적합 위험이 커진다.",
            "validation_method": "hinge/bin/interaction 후보를 같은 fold에서 ablation한다.",
            "feature_plan": [],
            "leakage_risk": "low",
            "confidence": "보통",
            "status": "open",
            "auto_recommended": False,
        },
    ]


def default_hypotheses(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    custom_templates = cfg.get("hypothesis_templates")
    if isinstance(custom_templates, list) and custom_templates:
        return [
            _normalise_hypothesis_template(item, index + 1)
            for index, item in enumerate(custom_templates)
            if isinstance(item, dict)
        ]
    return _generic_default_hypotheses(cfg)


def render_hypothesis_answers(hypotheses: list[dict[str, Any]], cfg: dict[str, Any], run_id: str) -> str:
    lines = [
        "# Hypothesis Answers",
        "",
        f"- run_id: `{run_id}`",
        f"- target_col: `{cfg.get('target_col', '')}`",
        "",
        "아래 가설은 초안입니다. 각 가설마다 `status`를 `answered`, `accepted`, `deferred` 중 하나로 바꾸면 02H 체크포인트가 통과됩니다.",
        "의견을 떠올리기 어렵다면 해당 가설의 `status: deferred`로 두고 진행할 수 있습니다.",
        "",
    ]
    lines += hypothesis_status_glossary_lines() + [""]
    for item in hypotheses:
        lines += [
            f"## {item['hypothesis_id']}",
            f"- one_sentence: {item.get('one_sentence', '')}",
            f"- variables: {', '.join(_as_list(item.get('variables')))}",
            f"- expected_direction: {item.get('expected_direction', '')}",
            f"- lag: {item.get('lag', '')}",
            f"- exception_mode: {item.get('exception_mode', '')}",
            f"- validation_method: {item.get('validation_method', '')}",
            f"- feature_plan: {', '.join(_as_list(item.get('feature_plan')))}",
            f"- leakage_risk: {item.get('leakage_risk', 'unknown')}",
            f"- confidence: {item.get('confidence', '보통')}",
            f"- status: {item.get('status', 'open')}",
            "",
            f"> 공학적 근거: {item.get('mechanism', '')}",
            "",
        ]
    return "\n".join(lines).strip() + "\n"


def parse_hypothesis_answers(markdown: str, starter_hypotheses: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    starter = {str(item["hypothesis_id"]): dict(item) for item in starter_hypotheses}
    starter_ids = set(starter.keys())
    parsed: dict[str, dict[str, Any]] = {}
    current_id = ""
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            candidate = line[3:].strip().split()[0]
            if candidate in starter_ids or candidate.startswith("HYP-"):
                current_id = candidate
                parsed.setdefault(current_id, {})
            else:
                current_id = ""
            continue
        if not current_id or not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        parsed[current_id][key.strip()] = value.strip()

    hypotheses: list[dict[str, Any]] = []
    for hid, base in starter.items():
        item = dict(base)
        item.update(parsed.get(hid, {}))
        item["hypothesis_id"] = hid
        item["variables"] = _as_list(item.get("variables"))
        item["feature_plan"] = _as_list(item.get("feature_plan"))
        item["status"] = str(item.get("status") or "open").strip()
        item["confidence"] = str(item.get("confidence") or "보통").strip()
        item["auto_recommended"] = bool(item.get("auto_recommended")) or item["status"] == "accepted"
        hypotheses.append(item)

    for hid, values in parsed.items():
        if hid in starter:
            continue
        item = dict(values)
        item["hypothesis_id"] = hid
        item["variables"] = _as_list(item.get("variables"))
        item["feature_plan"] = _as_list(item.get("feature_plan"))
        item["status"] = str(item.get("status") or "open").strip()
        item["confidence"] = str(item.get("confidence") or "보통").strip()
        item["auto_recommended"] = item["status"] == "accepted"
        hypotheses.append(item)

    return build_hypothesis_registry(hypotheses, cfg)


def build_hypothesis_registry(hypotheses: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    answer_quality_warnings: list[dict[str, str]] = []
    for item in hypotheses:
        status = str(item.get("status") or "open")
        confidence = str(item.get("confidence") or "보통")
        hid = str(item.get("hypothesis_id") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "accepted" and confidence == "낮음":
            answer_quality_warnings.append(
                {
                    "hypothesis_id": hid,
                    "warning": "accepted_low_confidence",
                    "suggestion": "`accepted`를 유지하려면 검증 근거를 보강하고, 아니면 `answered`로 두는 것이 안전합니다.",
                }
            )
        if status == "accepted" and str(item.get("leakage_risk") or "").lower() in {"high", "높음"}:
            answer_quality_warnings.append(
                {
                    "hypothesis_id": hid,
                    "warning": "accepted_high_leakage_risk",
                    "suggestion": "가설은 검증하되 Stage 03/04에서 미래값·사후변수 누수를 별도 확인해야 합니다.",
                }
            )
    return {
        "schema_version": "manual-hypothesis-registry.v1",
        "created_at": now_iso(),
        "target_col": cfg.get("target_col"),
        "task_type": cfg.get("task_type"),
        "hypotheses": hypotheses,
        "compact_summary": {
            "hypothesis_count": len(hypotheses),
            "status_counts": status_counts,
            "accepted_ids": [item["hypothesis_id"] for item in hypotheses if item.get("status") == "accepted"],
            "open_ids": [item["hypothesis_id"] for item in hypotheses if str(item.get("status") or "open") in OPEN_STATUSES],
            "answer_quality_warnings": answer_quality_warnings,
        },
    }


def build_hypothesis_context_pack(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    reports = paths["reports"]
    budget = cfg.get("context_budget") or {}
    max_chars = int(budget.get("max_chars_per_doc") or 1200)
    top_k = int(budget.get("top_k") or 8)
    evidence_cards = []
    for raw in cfg.get("hypothesis_context_paths") or []:
        path = resolve_project_path(cfg, str(raw))
        if not path or not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        evidence_cards.append(
            {
                "source": str(path),
                "summary": _clip(_compact_text(text), max_chars),
                "usage_stage": "02H_hypothesis_planning",
                "confidence": "source_provided",
            }
        )

    corr = _read_csv(reports / "dataset_review_target_correlations.csv")
    drift = _read_csv(reports / "feature_drift_summary.csv")
    missing = _read_csv(reports / "missing_reason_hypotheses.csv")
    stage00 = read_json(reports / "stage_00_report_payload.json", {})
    stage02 = read_json(reports / "stage_02_report_payload.json", {})
    pack = {
        "schema_version": "manual-hypothesis-context-pack.v1",
        "created_at": now_iso(),
        "target_col": cfg.get("target_col"),
        "task_type": cfg.get("task_type"),
        "evidence_cards": evidence_cards,
        "compact_summary": {
            "target_col": cfg.get("target_col"),
            "evidence_card_count": len(evidence_cards),
            "top_correlations": _records(corr, top_k),
            "top_drift": _records(drift, top_k),
            "top_missing": _records(missing, top_k),
            "stage_00_kpis": stage00.get("kpis", {}) if isinstance(stage00, dict) else {},
            "stage_02_kpis": stage02.get("kpis", {}) if isinstance(stage02, dict) else {},
        },
    }
    return pack


def write_hypothesis_proposal_files(
    cfg: dict[str, Any],
    run_id: str,
    paths: dict[str, Path],
    auto_proceed: bool = False,
) -> dict[str, Any]:
    reports = ensure_dir(paths["reports"])
    default_items = default_hypotheses(cfg)
    answers_path = reports / "hypothesis_answers.md"
    if answers_path.exists():
        registry = parse_hypothesis_answers(answers_path.read_text(encoding="utf-8"), default_items, cfg)
    else:
        answers_path.write_text(render_hypothesis_answers(default_items, cfg, run_id), encoding="utf-8")
        registry = build_hypothesis_registry(default_items, cfg)

    if auto_proceed:
        for item in registry["hypotheses"]:
            if str(item.get("status") or "open") in OPEN_STATUSES:
                item["status"] = "deferred"
                item["confidence"] = "낮음"
                item["user_deferred_to_default"] = True
        registry = build_hypothesis_registry(registry["hypotheses"], cfg)
        answers_path.write_text(render_hypothesis_answers(registry["hypotheses"], cfg, run_id), encoding="utf-8")

    context_pack = build_hypothesis_context_pack(cfg, paths)
    write_json(reports / "hypothesis_context_pack.json", context_pack)
    write_json(reports / "hypothesis_registry.json", registry)
    _write_validation_plan_csv(reports / "hypothesis_validation_plan.csv", registry)
    seed_report = render_seed_report(registry, context_pack)
    (reports / "hypothesis_seed_report.md").write_text(seed_report, encoding="utf-8")
    write_hypothesis_reference_files(reports, seed_report)
    try:
        from manual_report_payloads import write_stage_payload

        write_stage_payload("02H", cfg, paths)
    except Exception:
        pass

    pending = any(str(item.get("status") or "open") in OPEN_STATUSES for item in registry.get("hypotheses", []))
    pending_json = reports / "pending_hypothesis_checkpoint.json"
    pending_md = reports / "pending_hypothesis_checkpoint.md"
    stage_pending_json = reports / "pending_hypothesis_checkpoint_stage_02H.json"
    stage_pending_md = reports / "pending_hypothesis_checkpoint_stage_02H.md"
    if pending and not auto_proceed:
        payload = {
            "checkpoint_id": "CP-02H-HYPOTHESIS",
            "stage_before": "03",
            "title": "02H 가설 수립 체크포인트",
            "hypothesis_answers_path": str(answers_path.resolve()),
            "hypothesis_seed_report_path": str((reports / "hypothesis_seed_report.md").resolve()),
            "hypothesis_context_pack_path": str((reports / "hypothesis_context_pack.json").resolve()),
            "reference_report_pdf": str((reports / "pdf" / "checkpoint_reference_stage_02H.pdf").resolve()),
            "stage_pending_json": str(stage_pending_json.resolve()),
            "stage_pending_md": str(stage_pending_md.resolve()),
            "open_hypothesis_ids": registry.get("compact_summary", {}).get("open_ids", []),
            "created_at": now_iso(),
        }
        write_json(pending_json, payload)
        pending_md.write_text(render_pending_checkpoint_v2(payload), encoding="utf-8")
        write_json(stage_pending_json, payload)
        stage_pending_md.write_text(render_pending_checkpoint_v2(payload), encoding="utf-8")
    else:
        for path in [pending_json, pending_md, stage_pending_json, stage_pending_md]:
            if path.exists():
                path.unlink()
        summary = registry.get("compact_summary", {}) if isinstance(registry, dict) else {}
        append_decision_log(
            paths,
            "02H_hypothesis_checkpoint",
            "hypothesis_status_review",
            f"accepted={','.join(summary.get('accepted_ids', []) or []) or 'none'}; status_counts={json.dumps(summary.get('status_counts', {}), ensure_ascii=False)}",
            "review every hypothesis as accepted, answered, or deferred before Stage 03",
            "02H hypothesis checkpoint is clear or was auto-proceeded.",
            "Stage 03 will only build features for accepted or explicitly auto-recommended hypotheses.",
        )
    return {"pending": pending and not auto_proceed, "registry": registry, "context_pack": context_pack}


def render_seed_report(registry: dict[str, Any], context_pack: dict[str, Any]) -> str:
    lines = [
        "# 가설 수립 시드 리포트",
        "",
        "이 문서는 사용자가 가설을 직접 떠올리기 전에 참고할 기초 정보와 starter hypothesis를 압축해 제공합니다.",
        "",
        "## 읽는 순서",
        "",
        "1. 아래 기초 신호를 보고 데이터에서 강한 관계와 위험 신호를 확인합니다.",
        "2. `hypothesis_answers.md`에서 유지할 가설은 `accepted`, 보류할 가설은 `deferred`로 바꿉니다.",
        "3. Stage 03 피처 엔지니어링은 `accepted` 또는 명시적 자동 추천 가설만 자동 피처 후보로 사용합니다.",
        "",
        "## 기초 데이터 신호",
        "",
    ]
    summary = context_pack.get("compact_summary") or {}
    for key in ["top_correlations", "top_drift", "top_missing"]:
        rows = summary.get(key) or []
        lines += [f"### {key}", ""]
        if rows:
            for row in rows[:8]:
                lines.append("- " + ", ".join(f"{k}={v}" for k, v in row.items() if v is not None))
        else:
            lines.append("- 아직 해당 산출물이 없거나 읽을 수 없습니다.")
        lines.append("")
    lines += ["## Starter Hypotheses", ""]
    for item in registry.get("hypotheses", []):
        lines += [
            f"### {item.get('hypothesis_id')}",
            f"- 한 문장: {item.get('one_sentence', '')}",
            f"- 물리/공학 근거: {item.get('mechanism', '')}",
            f"- 검증 방법: {item.get('validation_method', '')}",
            f"- 권장 피처: {', '.join(_as_list(item.get('feature_plan')))}",
            f"- 누수 위험: {item.get('leakage_risk', '')}",
            "",
        ]
    warnings = (registry.get("compact_summary") or {}).get("answer_quality_warnings") or []
    lines += ["## 답변 품질 경고", ""]
    if warnings:
        for item in warnings:
            lines.append(f"- `{item.get('hypothesis_id')}` {item.get('warning')}: {item.get('suggestion')}")
    else:
        lines.append("- 없음")
    return "\n".join(lines).strip() + "\n"


def write_hypothesis_reference_files(reports: Path, seed_report: str) -> None:
    md_path = reports / "checkpoint_reference_stage_02H.md"
    pdf_path = reports / "pdf" / "checkpoint_reference_stage_02H.pdf"
    ensure_dir(pdf_path.parent)
    md_path.write_text(
        "\n".join(
            [
                "# 02H 가설 체크포인트 참고자료",
                "",
                "현재 Stage 03 피처 엔지니어링 전 단계입니다.",
                "`hypothesis_answers.md`를 수정하기 전에 아래 가설 시드 리포트를 먼저 확인하세요.",
                "",
                seed_report,
            ]
        ),
        encoding="utf-8",
    )
    try:
        import warnings
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        warnings.filterwarnings("ignore", message="Glyph .* missing from font.*")
        for font in ["Malgun Gothic", "Noto Sans CJK KR", "Noto Sans KR", "Arial Unicode MS", "DejaVu Sans"]:
            try:
                matplotlib.font_manager.findfont(font, fallback_to_default=False)
                plt.rcParams["font.family"] = "sans-serif"
                plt.rcParams["font.sans-serif"] = [font]
                break
            except Exception:
                continue
        with PdfPages(pdf_path) as pdf:
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.text(0.06, 0.96, "02H 가설 체크포인트 참고자료", fontsize=16, fontweight="bold", va="top")
            fig.text(0.06, 0.92, seed_report[:3200], fontsize=8.2, va="top", wrap=True)
            fig.text(0.06, 0.03, "Full source: checkpoint_reference_stage_02H.md / hypothesis_seed_report.md", fontsize=7.5)
            pdf.savefig(fig)
            plt.close(fig)
    except Exception:
        # PDF generation is helpful but should not block hypothesis planning in minimal environments.
        pass


def render_pending_checkpoint(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# 02H 가설 수립 체크포인트",
            "",
            "현재 Stage 03 피처 엔지니어링 전 단계입니다.",
            f"사용자의 가설 판단을 `{payload['hypothesis_answers_path']}`에 추가해주세요.",
            f"먼저 참고할 자료: `{payload['hypothesis_seed_report_path']}`",
            f"컨텍스트 압축 자료: `{payload['hypothesis_context_pack_path']}`",
            "의견을 떠올리기 어렵다면 \"그냥 진행해줘\"라고 답변해주세요.",
            "답변 후에는 제가 `hypothesis_registry.json`을 갱신하고 다음 단계로 진행합니다.",
            "",
            "열려 있는 가설:",
            *[f"- `{hid}`" for hid in payload.get("open_hypothesis_ids", [])],
            "",
        ]
    )


def render_pending_checkpoint_v2(payload: dict[str, Any]) -> str:
    lines = [
        "# 02H Hypothesis Checkpoint",
        "",
        "Stage 03 feature generation 전에 사용자 가설 의견을 확인합니다.",
        f"- hypothesis_answers: `{payload['hypothesis_answers_path']}`",
        f"- seed_report: `{payload['hypothesis_seed_report_path']}`",
        f"- context_pack: `{payload['hypothesis_context_pack_path']}`",
        "",
    ]
    lines += hypothesis_status_glossary_lines()
    lines += [
        "",
        "## Action",
        "",
        "- `hypothesis_answers.md`에서 각 가설의 `status`와 `confidence`를 직접 정합니다.",
        "- 판단이 어렵다면 `answered`로 두고 코멘트를 남기거나, 정말 이번 run에서 넘기고 싶으면 `deferred`를 씁니다.",
        "- 이전에 auto-proceed로 deferred 되었던 가설도 이번에는 다시 검토해서 의도를 반영해 주세요.",
        "",
        "Open hypothesis IDs",
    ]
    lines.extend(f"- `{hid}`" for hid in payload.get("open_hypothesis_ids", []))
    lines += [""]
    return "\n".join(lines)


def hypothesis_feature_candidates_from_registry(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in registry.get("hypotheses", []) if isinstance(registry, dict) else []:
        status = str(item.get("status") or "open")
        if status != "accepted" and not bool(item.get("auto_recommended")):
            continue
        plan = _as_list(item.get("feature_plan"))
        formula = ", ".join(plan) if plan else str(item.get("expected_direction") or "")
        rows.append(
            {
                "family": _feature_family(item, formula),
                "feature_name": _safe_feature_name(str(item.get("hypothesis_id") or "hypothesis")),
                "formula": formula,
                "theory_note": item.get("mechanism", ""),
                "required_columns": ",".join(_as_list(item.get("variables"))),
                "recommendation_basis": item.get("one_sentence", ""),
                "domain_knowledge_needed": "Confirm exact columns, time order, and leakage risk before using as a hard rule.",
                "multicollinearity_risk": "medium",
                "leakage_risk": item.get("leakage_risk", "unknown"),
                "auto_recommended": status == "accepted" or bool(item.get("auto_recommended")),
                "hypothesis_id": item.get("hypothesis_id"),
                "validation_method": item.get("validation_method", ""),
                "status": status,
            }
        )
    return rows


def evaluate_hypotheses(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    reports = ensure_dir(paths["reports"])
    registry = read_json(reports / "hypothesis_registry.json", {"hypotheses": []})
    metrics = _read_csv(paths["models"] / "metrics.csv")
    manifest = read_json(paths["processed"] / "feature_manifest.json", {})
    feature_cols = set(str(col) for col in manifest.get("feature_columns", []) or [])
    metric_name = str(cfg.get("metric_primary") or ("rmse" if cfg.get("task_type") == "regression" else "log_loss"))
    lower_is_better = metric_name.lower() not in {"r2", "accuracy", "f1", "roc_auc"}
    results = []
    for item in registry.get("hypotheses", []) if isinstance(registry, dict) else []:
        hid = str(item.get("hypothesis_id") or "")
        variables = [v for v in _as_list(item.get("variables")) if v and v != str(cfg.get("target_col") or "")]
        support_status = "not_testable"
        evidence = "No matching model evidence or feature lineage was found."
        if "O2" in hid and not metrics.empty and "experiment_group" in metrics.columns:
            groups = set(metrics["experiment_group"].astype(str))
            if {"o2_included", "o2_excluded"}.issubset(groups) and metric_name in metrics.columns:
                included = pd.to_numeric(metrics.loc[metrics["experiment_group"].astype(str) == "o2_included", metric_name], errors="coerce").min()
                excluded = pd.to_numeric(metrics.loc[metrics["experiment_group"].astype(str) == "o2_excluded", metric_name], errors="coerce").min()
                better = included < excluded if lower_is_better else included > excluded
                support_status = "supported" if better else "partially_supported"
                evidence = f"{metric_name}: o2_included={included}, o2_excluded={excluded}"
            elif any("o2" in group.lower() for group in groups):
                support_status = "partially_supported"
                evidence = "O2-related experiment groups exist but full include/exclude pair is incomplete."
        elif variables and any(var in feature_cols for var in variables):
            support_status = "partially_supported"
            evidence = "One or more hypothesis variables exist in feature_manifest.json."
        results.append(
            {
                "hypothesis_id": hid,
                "support_status": support_status,
                "evidence": evidence,
                "validation_method": item.get("validation_method", ""),
                "next_action": _next_action(support_status),
            }
        )
    payload = {
        "schema_version": "manual-hypothesis-validation-results.v1",
        "created_at": now_iso(),
        "target_col": cfg.get("target_col"),
        "metric_primary": metric_name,
        "results": results,
    }
    write_json(reports / "hypothesis_validation_results.json", payload)
    (reports / "hypothesis_validation_results.md").write_text(render_validation_results(payload), encoding="utf-8")
    supported = [row["hypothesis_id"] for row in results if row.get("support_status") == "supported"]
    not_testable = [row["hypothesis_id"] for row in results if row.get("support_status") == "not_testable"]
    append_decision_log(
        paths,
        "05H_hypothesis_validation",
        "accepted_hypothesis_evidence",
        f"supported={','.join(supported) or 'none'}; not_testable={','.join(not_testable) or 'none'}",
        "evaluate accepted hypotheses with model evidence, feature lineage, and ablation where available",
        "Hypothesis validation results were summarized after model training.",
        "Unsupported or not-testable hypotheses should remain as follow-up work rather than hard conclusions.",
    )
    try:
        from manual_report_payloads import write_stage_payload

        write_stage_payload("05H", cfg, paths)
    except Exception:
        pass
    return payload


def render_validation_results(payload: dict[str, Any]) -> str:
    lines = [
        "# 가설 검증 결과",
        "",
        f"- target_col: `{payload.get('target_col')}`",
        f"- metric_primary: `{payload.get('metric_primary')}`",
        "",
        "| hypothesis_id | support_status | evidence | next_action |",
        "|---|---|---|---|",
    ]
    for row in payload.get("results", []):
        lines.append(
            f"| {row.get('hypothesis_id')} | {row.get('support_status')} | {str(row.get('evidence', '')).replace('|', '/')} | {row.get('next_action')} |"
        )
    return "\n".join(lines).strip() + "\n"


def _write_validation_plan_csv(path: Path, registry: dict[str, Any]) -> None:
    rows = []
    for item in registry.get("hypotheses", []):
        rows.append(
            {
                "hypothesis_id": item.get("hypothesis_id"),
                "status": item.get("status"),
                "variables": ",".join(_as_list(item.get("variables"))),
                "expected_direction": item.get("expected_direction"),
                "lag": item.get("lag"),
                "validation_method": item.get("validation_method"),
                "feature_plan": ",".join(_as_list(item.get("feature_plan"))),
                "leakage_risk": item.get("leakage_risk"),
            }
        )
    ensure_dir(path.parent)
    pd.DataFrame(rows).to_csv(path, index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _records(df: pd.DataFrame, max_rows: int = 8) -> list[dict[str, Any]]:
    if df.empty:
        return []
    view = df.head(max_rows).where(pd.notna(df.head(max_rows)), None)
    return [_json_safe(item) for item in view.to_dict(orient="records")]


def _clip(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    return text[:limit]


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _feature_family(item: dict[str, Any], formula: str) -> str:
    text = f"{item.get('hypothesis_id', '')} {formula} {item.get('validation_method', '')}".lower()
    if "lag" in text or "지연" in text:
        return "hypothesis_lag"
    if "hinge" in text or "piecewise" in text or "구간" in text:
        return "hypothesis_piecewise"
    if "x_" in text or "×" in text or "interaction" in text:
        return "hypothesis_interaction"
    return "hypothesis_feature"


def _safe_feature_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value.lower()).strip("_") + "_features"


def _next_action(status: str) -> str:
    if status == "supported":
        return "Keep as a validated modeling/reporting hypothesis."
    if status == "partially_supported":
        return "Inspect segment, lag, or ablation diagnostics before turning into a conclusion."
    if status == "not_supported":
        return "Keep in appendix unless domain owner provides new evidence."
    return "Collect required columns or run the planned experiment."


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value
