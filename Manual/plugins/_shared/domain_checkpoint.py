from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PENDING_CHECKPOINT_JSON = "pending_checkpoint.json"
PENDING_CHECKPOINT_MD = "pending_checkpoint.md"
DEFERRED_MARKER = "[DEFERRED: User delegated to default]"


def checkpoint_term_lines() -> list[str]:
    return [
        "## Status Glossary",
        "",
        "- `open`: 아직 이번 체크포인트에서 의견을 넣지 않았거나 검토를 끝내지 않은 상태",
        "- `answered`: 의견은 적었지만 강한 운영 규칙으로 확정하지 않은 상태",
        "- `accepted`: 이번 run에서 적극 반영해도 되는 의견",
        "- `deferred`: 이번 run에서는 기본 추천을 따르겠다는 뜻",
        "- `auto-proceed`: 사용자 입력 없이 진행할 때 시스템이 열려 있는 항목을 `deferred` 처리하는 실행 모드",
        "",
        "## Confidence Glossary",
        "",
        "- `낮음`: 참고 의견. 강한 규칙이나 자동 필터링에는 사용하지 않음",
        "- `보통`: 후보 규칙 또는 후보 해석으로 사용할 수 있음",
        "- `높음`: 현장 규칙에 가깝게 강하게 반영 가능",
    ]


@dataclass(frozen=True)
class CheckpointSpec:
    checkpoint_id: str
    stage_before: str
    title: str
    question_ids: tuple[str, ...]
    core_refs: tuple[str, ...]
    extra_refs: tuple[str, ...]


CHECKPOINTS: dict[str, CheckpointSpec] = {
    # Change_plan_1.md
    "01": CheckpointSpec(
        checkpoint_id="CP-01-KPI_TARGET",
        stage_before="01",
        title="KPI와 타깃 도메인 의미 확인",
        question_ids=("D00-KPI-001", "D00-TARGET-001"),
        core_refs=("reports/dataset_review.md",),
        extra_refs=("reports/data_overview.json", "reports/dataset_review_correlation_heatmap.png"),
    ),
    "03": CheckpointSpec(
        checkpoint_id="CP-03-DIAG_FEATURE_IDEA",
        stage_before="03",
        title="물리 범위, 이상치, 피처 아이디어 확인",
        question_ids=("D02-PHYSICAL-RANGE-001", "D02-OPERATING-STATE-001", "D03-FEATURE-001"),
        core_refs=("reports/diagnosis_report.md",),
        extra_refs=("reports/feature_candidate_menu.csv", "reports/missing_reason_hypotheses.csv"),
    ),
    "05": CheckpointSpec(
        checkpoint_id="CP-05-ERROR_COST",
        stage_before="05",
        title="과대/과소 예측 리스크와 오류 비용 확인",
        question_ids=("D05-EVAL-RISK-001",),
        core_refs=("data/folds/sample15_fold_report.md",),
        extra_refs=("data/processed/feature_manifest.json",),
    ),
    "07": CheckpointSpec(
        checkpoint_id="CP-07-ACTION_ITEMS",
        stage_before="07",
        title="결과를 현장 액션으로 전환",
        question_ids=("D07-ACTION-001",),
        core_refs=("reports/action_items.md",),
        extra_refs=("artifacts/models/metrics.csv", "artifacts/models/explainability_report.md"),
    ),
}


def checkpoint_spec(stage_before: str) -> CheckpointSpec:
    if stage_before not in CHECKPOINTS:
        raise ValueError(f"Unknown checkpoint stage_before={stage_before}. Known: {sorted(CHECKPOINTS)}")
    return CHECKPOINTS[stage_before]


def now_ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stage_pending_checkpoint_paths(reports_dir: Path, spec: CheckpointSpec) -> dict[str, Path]:
    return {
        "json": reports_dir / f"pending_checkpoint_stage_{spec.stage_before}.json",
        "md": reports_dir / f"pending_checkpoint_stage_{spec.stage_before}.md",
    }


def pending_checkpoint_paths(reports_dir: Path, spec: CheckpointSpec | None = None) -> dict[str, Path]:
    paths = {
        "json": reports_dir / PENDING_CHECKPOINT_JSON,
        "md": reports_dir / PENDING_CHECKPOINT_MD,
    }
    if spec is not None:
        stage_paths = stage_pending_checkpoint_paths(reports_dir, spec)
        paths["stage_json"] = stage_paths["json"]
        paths["stage_md"] = stage_paths["md"]
    return paths


def clear_pending_checkpoint(reports_dir: Path, spec: CheckpointSpec | None = None) -> None:
    paths = pending_checkpoint_paths(reports_dir, spec)
    for p in paths.values():
        if p.exists():
            p.unlink()


def checkpoint_is_cleared(pack: dict[str, Any], spec: CheckpointSpec) -> bool:
    if not isinstance(pack, dict):
        return False
    cleared = pack.get("cleared_checkpoints")
    if not isinstance(cleared, list):
        return False
    return any(isinstance(item, dict) and item.get("checkpoint_id") == spec.checkpoint_id for item in cleared)


def guidance_markdown(run_base: Path, spec: CheckpointSpec, answers_path: Path) -> str:
    core = [str((run_base / rel).resolve()) for rel in spec.core_refs if (run_base / rel).exists()]
    extra = [str((run_base / rel).resolve()) for rel in spec.extra_refs if (run_base / rel).exists()]
    # Even if some references are missing, we still print the intended paths.
    if not core:
        core = [str((run_base / spec.core_refs[0]).resolve())]
    if not extra:
        extra = [str((run_base / rel).resolve()) for rel in spec.extra_refs]
    refs = checkpoint_reference_paths(run_base, spec)
    qids = ", ".join(spec.question_ids)
    return "\n".join(
        [
            "# Domain Checkpoint (Pending)",
            "",
            f"- checkpoint_id: `{spec.checkpoint_id}`",
            f"- stage_before: `{spec.stage_before}`",
            f"- title: {spec.title}",
            f"- required_question_ids: `{qids}`",
            f"- domain_answers: `{str(answers_path.resolve())}`",
            f"- reference_report_md: `{str(refs['md'].resolve())}`",
            f"- reference_report_pdf: `{str(refs['pdf'].resolve())}`",
            "",
            f"현재 Stage `{spec.stage_before}` 직전 체크포인트입니다.",
            f"사용자의 도메인 인사이트가 있으면 `{str(answers_path.resolve())}`에서 해당 질문 카드에 추가해주세요.",
            "",
            "참고 자료:",
            "",
            f"- [핵심 자료] `{core[0]}`",
            *[f"- [부가 자료] `{p}`" for p in extra],
            "",
            "의견을 떠올리기 어렵다면 \"그냥 진행해줘\"라고 답변해주세요.",
            "답변 후에는 제가 domain_context_pack.json을 갱신하고 다음 단계로 진행합니다.",
            "",
        ]
    ).strip() + "\n"


def guidance_markdown_v2(run_base: Path, spec: CheckpointSpec, answers_path: Path) -> str:
    core = [str((run_base / rel).resolve()) for rel in spec.core_refs if (run_base / rel).exists()]
    extra = [str((run_base / rel).resolve()) for rel in spec.extra_refs if (run_base / rel).exists()]
    if not core:
        core = [str((run_base / spec.core_refs[0]).resolve())]
    if not extra:
        extra = [str((run_base / rel).resolve()) for rel in spec.extra_refs]
    refs = checkpoint_reference_paths(run_base, spec)
    qids = ", ".join(spec.question_ids)
    lines = [
        "# Domain Checkpoint (Pending)",
        "",
        f"- checkpoint_id: `{spec.checkpoint_id}`",
        f"- stage_before: `{spec.stage_before}`",
        f"- title: {spec.title}",
        f"- required_question_ids: `{qids}`",
        f"- domain_answers: `{str(answers_path.resolve())}`",
        f"- reference_report_md: `{str(refs['md'].resolve())}`",
        f"- reference_report_pdf: `{str(refs['pdf'].resolve())}`",
        "",
    ]
    lines += checkpoint_term_lines()
    lines += [
        "",
        f"현재 Stage `{spec.stage_before}` 직전 체크포인트입니다.",
        f"사용자 의견은 `{str(answers_path.resolve())}`에서 해당 질문 카드에 적어 주세요.",
        "",
        "참고 자료:",
        "",
        f"- [핵심 자료] `{core[0]}`",
    ]
    lines.extend(f"- [추가 자료] `{p}`" for p in extra)
    lines += [
        "",
        "판단이 아직 어려우면 `answered`로 두고 설명을 적거나, 이번 run에서 제 기본 추천을 따르려면 `deferred`를 쓰면 됩니다.",
        "",
    ]
    return "\n".join(lines)


def checkpoint_reference_paths(run_base: Path, spec: CheckpointSpec) -> dict[str, Path]:
    return {
        "md": run_base / "reports" / f"checkpoint_reference_stage_{spec.stage_before}.md",
        "pdf": run_base / "reports" / "pdf" / f"checkpoint_reference_stage_{spec.stage_before}.pdf",
    }


def build_checkpoint_reference_markdown(run_base: Path, spec: CheckpointSpec, answers_path: Path) -> str:
    lines = [
        f"# Stage {spec.stage_before} 체크포인트 참고 보고서",
        "",
        f"- 체크포인트: `{spec.checkpoint_id}`",
        f"- 목적: {spec.title}",
        f"- 답변 파일: `{answers_path.resolve()}`",
        f"- 답변할 질문: {', '.join(f'`{qid}`' for qid in spec.question_ids)}",
        "",
        "## 확인 순서",
        "",
        "1. 핵심 자료를 먼저 읽고 현재 Stage에서 새로 알게 된 내용을 확인합니다.",
        "2. `domain_answers.md`의 해당 체크포인트 섹션만 보완합니다.",
        "3. 확신이 낮으면 `확신도: 낮음`으로 둡니다. 이 경우 자동 필터링이나 강한 결론으로 쓰지 않습니다.",
        "",
        "## 핵심 자료",
        "",
    ]
    for rel in spec.core_refs:
        p = run_base / rel
        lines.append(f"- `{p.resolve()}`")
    lines += ["", "## 추가 자료", ""]
    for rel in spec.extra_refs:
        p = run_base / rel
        lines.append(f"- `{p.resolve()}`")
    lines += ["", "## 예상 답변 가이드", ""]
    if spec.stage_before == "01":
        lines += [
            "- KPI: 품질 손실 감소, 처리시간 단축, 비용 절감, 리스크 감소.",
            "- 타깃 의미: 실제 의사결정에 쓰이는 결과 지표, 규칙 위반 리스크, 운영 효율 간접 지표.",
        ]
    elif spec.stage_before == "03":
        lines += [
            "- 이상치: 실제 기동/정지/부하 급변인지, 센서 오류인지, 운전 모드 전환인지 구분합니다.",
            "- 운전 상태: 정상 운전, 예열/기동, 정지 잔여 운전, 부하 상승/하강, 센서 교정 구간.",
            "- 피처: 부하 대비 자원 사용량, 비율, 온도차, 상태 변화, 제어/운영 조건의 상호작용.",
        ]
    elif spec.stage_before == "05":
        lines += [
            "- 더 위험한 오류: 실제 위험 상태를 낮게 예측하는 것, 불필요한 조치를 과하게 유도하는 것.",
            "- 평가 관점: RMSE/MAE뿐 아니라 위험 구간 recall, 상위 타깃 구간 오차를 확인합니다.",
        ]
    elif spec.stage_before == "07":
        lines += [
            "- 액션: 센서 캘리브레이션, 밸브 상태, SCR 온도, 암모니아 투입, 발전 출력/효율 동시 확인.",
            "- 보고서 구분: 도메인 가정, 확인된 규칙, 추가 확인 필요를 분리합니다.",
        ]
    return "\n".join(lines).strip() + "\n"
def write_checkpoint_reference_files(run_base: Path, spec: CheckpointSpec, answers_path: Path) -> dict[str, str]:
    paths = checkpoint_reference_paths(run_base, spec)
    paths["md"].parent.mkdir(parents=True, exist_ok=True)
    paths["pdf"].parent.mkdir(parents=True, exist_ok=True)
    md = build_checkpoint_reference_markdown(run_base, spec, answers_path)
    paths["md"].write_text(md, encoding="utf-8")
    try:
        import textwrap
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        for font in ["Malgun Gothic", "Noto Sans CJK KR", "Noto Sans KR", "DejaVu Sans"]:
            try:
                matplotlib.font_manager.findfont(font, fallback_to_default=False)
                plt.rcParams["font.family"] = font
                break
            except Exception:
                continue
        plt.rcParams["axes.unicode_minus"] = False
        with PdfPages(paths["pdf"]) as pdf:
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.text(0.06, 0.96, f"Stage {spec.stage_before} 체크포인트 참고 보고서", fontsize=16, fontweight="bold", va="top")
            y = 0.91
            for line in md.splitlines()[2:40]:
                wrapped = textwrap.wrap(line, width=72) or [""]
                for part in wrapped:
                    fig.text(0.06, y, part, fontsize=8.5, va="top")
                    y -= 0.022
                    if y < 0.08:
                        break
                if y < 0.08:
                    break
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            heatmap = run_base / "reports" / "dataset_review_correlation_heatmap.png"
            if spec.stage_before == "01" and heatmap.exists():
                img = plt.imread(heatmap)
                fig, ax = plt.subplots(figsize=(11.69, 8.27))
                ax.imshow(img)
                ax.axis("off")
                ax.set_title("타깃과 주요 변수의 관계(한글 의미명)", fontsize=14)
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
    except Exception:
        pass
    return {key: str(value) for key, value in paths.items()}


def open_question_ids_from_answers(answers_md: str, required_qids: tuple[str, ...]) -> list[str]:
    open_qids: list[str] = []
    for qid in required_qids:
        # Look for the section and parse "- 상태:" line. This keeps the dependency light.
        m = re.search(rf"^#{{2,3}}\s+{re.escape(qid)}\b.*?$([\s\S]*?)(?=^#{{2,3}}\s+D\d{{2}}-|\Z)", answers_md, re.MULTILINE)
        if not m:
            open_qids.append(qid)
            continue
        section = m.group(1)
        sm = re.search(r"^\s*-\s*상태\s*:\s*(.*)$", section, re.MULTILINE)
        status = (sm.group(1).strip() if sm else "open").lower()
        # If the user filled any content, do not block even if they forgot to update the status field.
        selected = ""
        refinement = ""
        msel = re.search(r"^\s*-\s*선택한 예시 답변\s*:\s*(.*)$", section, re.MULTILINE)
        if msel:
            selected = (msel.group(1) or "").strip()
        mref = re.search(r"^\s*-\s*내 상황 보완\s*:\s*(.*)$", section, re.MULTILINE)
        if mref:
            refinement = (mref.group(1) or "").strip()
        filled = bool(selected.strip()) or bool(refinement.strip())
        # Accept "open" as pending only when not filled.
        if status == "open" and not filled:
            open_qids.append(qid)
    return open_qids


def answer_section_text(answers_md: str, qid: str) -> str:
    m = re.search(rf"^#{{2,3}}\s+{re.escape(qid)}\b.*?$([\s\S]*?)(?=^#{{2,3}}\s+D\d{{2}}-|\Z)", answers_md, re.MULTILINE)
    return m.group(0) if m else ""


def answers_fingerprint(answers_md: str, qids: tuple[str, ...]) -> str:
    text = "\n".join(answer_section_text(answers_md, qid) for qid in qids)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def answer_statuses(answers_md: str, qids: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for qid in qids:
        section = answer_section_text(answers_md, qid)
        sm = re.search(r"^\s*-\s*상태\s*:\s*(.*)$", section, re.MULTILINE)
        out[qid] = (sm.group(1).strip() if sm else "open").lower()
    return out


def defer_question_sections(answers_md: str, qids: list[str], marker: str = DEFERRED_MARKER) -> str:
    out = answers_md
    for qid in qids:
        pattern = re.compile(rf"(^#{{2,3}}\s+{re.escape(qid)}\b.*?$)([\s\S]*?)(?=^#{{2,3}}\s+D\d{{2}}-|\Z)", re.MULTILINE)
        m = pattern.search(out)
        if not m:
            continue
        header, body = m.group(1), m.group(2)
        # Write marker into "내 상황 보완" only if empty.
        body = re.sub(
            r"(^\s*-\s*내 상황 보완\s*:\s*)(.*)$",
            lambda mm: mm.group(1) + (marker if not mm.group(2).strip() else mm.group(2).strip()),
            body,
            flags=re.MULTILINE,
        )
        # Force deferred status.
        body = re.sub(r"(^\s*-\s*상태\s*:\s*).*$", r"\1deferred", body, flags=re.MULTILINE)
        # Keep confidence low by default if user didn't fill.
        body = re.sub(r"(^\s*-\s*확신도\s*:\s*).*$", r"\1낮음", body, flags=re.MULTILINE)
        out = out[: m.start()] + header + body + out[m.end() :]
    return out


def record_deferred_checkpoint(pack: dict[str, Any], spec: CheckpointSpec, deferred_qids: list[str], reason: str) -> dict[str, Any]:
    if not isinstance(pack, dict):
        return pack
    entry = {
        "checkpoint_id": spec.checkpoint_id,
        "stage_before": spec.stage_before,
        "question_ids": deferred_qids,
        "reason": reason,
        "recorded_at": now_ts(),
    }
    arr = pack.get("deferred_checkpoints")
    if not isinstance(arr, list):
        arr = []
    # De-dupe by checkpoint_id + recorded question set (keep first).
    sig = (entry["checkpoint_id"], tuple(sorted(entry["question_ids"])))
    existing = set()
    for item in arr:
        if isinstance(item, dict):
            existing.add((item.get("checkpoint_id"), tuple(sorted(item.get("question_ids") or []))))
    if sig not in existing:
        arr.append(entry)
    pack["deferred_checkpoints"] = arr
    return pack


def record_cleared_checkpoint(pack: dict[str, Any], spec: CheckpointSpec, reason: str) -> dict[str, Any]:
    if not isinstance(pack, dict):
        return pack
    entry = {
        "checkpoint_id": spec.checkpoint_id,
        "stage_before": spec.stage_before,
        "question_ids": list(spec.question_ids),
        "reason": reason,
        "recorded_at": now_ts(),
    }
    arr = pack.get("cleared_checkpoints")
    if not isinstance(arr, list):
        arr = []
    if not any(isinstance(item, dict) and item.get("checkpoint_id") == spec.checkpoint_id for item in arr):
        arr.append(entry)
    pack["cleared_checkpoints"] = arr
    return pack
