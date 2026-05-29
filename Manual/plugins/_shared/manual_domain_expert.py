from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


QUESTIONNAIRE_SCHEMA_VERSION = "manual-domain-questionnaire.v1"
CONTEXT_PACK_SCHEMA_VERSION = "manual-domain-context-pack.v1"
ACTION_ITEMS_SCHEMA_VERSION = "manual-domain-action-items.v1"

VALID_CONFIDENCE = {"낮음", "보통", "높음"}
VALID_STATUS = {"open", "answered", "accepted", "deferred"}


DEFERRED_MARKER_PREFIX = "[DEFERRED"


def status_glossary_lines() -> list[str]:
    return [
        "## Status Glossary",
        "",
        "- `open`: 아직 의견을 넣지 않았거나, 이번 체크포인트에서 검토를 끝내지 않은 상태입니다.",
        "- `answered`: 답변은 적었지만 아직 강한 운영 규칙으로 확정하지 않은 상태입니다. 설명을 남기고 다음 해석에 참고시키고 싶을 때 씁니다.",
        "- `accepted`: 지금 분석 run에서 적극 반영해도 되는 의견 또는 규칙입니다. 피처, 해석, 액션 제안에 직접 반영해도 좋다는 뜻입니다.",
        "- `deferred`: 이번 run에서는 기본 추천이나 모델 기본 동작을 따르겠다는 뜻입니다. 반대 의견이 아니라, 이번 체크포인트에서 판단을 보류한다는 의미입니다.",
        "- `auto-proceed`: 파이프라인이 사용자 입력 없이 넘어가야 할 때 쓰는 실행 모드입니다. 열려 있는 항목을 자동으로 `deferred` 처리합니다. 사용자가 직접 문서를 검토할 때는 이 값을 적을 필요가 없습니다.",
        "",
        "## Confidence Glossary",
        "",
        "- `낮음`: 느낌이나 경험 수준의 의견입니다. 모델 해석 참고용으로는 쓰되 강한 규칙으로 취급하지 않습니다.",
        "- `보통`: 현재 데이터와 현장 상식을 함께 보면 타당해 보이는 의견입니다. 후보 규칙이나 후보 피처로 반영할 수 있습니다.",
        "- `높음`: 현장 규칙 또는 공정 지식으로 거의 확실한 의견입니다. 분석에서 명시적 제약이나 우선 규칙으로 반영할 수 있습니다.",
        "",
        "## How To Fill",
        "",
        "- `선택한 예시 답변`: 가장 가까운 starter answer를 고르거나 짧게 직접 적습니다.",
        "- `내 상황 보완`: 예외 조건, 실제 현장 맥락, 수치 범위, 주의할 점을 적습니다.",
        "- 가장 보수적으로 적고 싶으면 `answered + 낮음`으로 두면 됩니다.",
        "- 이번 run에서 제 의견을 그대로 따르려면 `deferred`로 두면 됩니다.",
    ]


BASE_QUESTION_CARDS: list[dict[str, Any]] = [
    {
        "question_id": "D00-KPI-001",
        "stage": "00",
        "topic": "문제정의",
        "question": "이 분석으로 줄이고 싶은 손실이나 개선하고 싶은 성과는 무엇인가요?",
        "why_it_matters": "분석 목표가 KPI와 연결되어야 모델 성능이 실제 의사결정 가치로 이어집니다.",
        "starter_answers": [
            "불량률 감소",
            "에너지 비용 절감",
            "장비 정지시간 감소",
            "생산량 증가",
            "검사 시간 단축",
        ],
        "upgrade_prompt": "가능하면 금액, 시간, 비율, 월 단위 손실처럼 측정 가능한 표현으로 발전시켜 적습니다.",
        "answer_format": "선택한 예시 답변, 내 상황 보완, 확신도, 상태를 작성합니다.",
        "decision_effect": "목표 정의, 보고서 첫 페이지, 모델 평가 해석에 반영됩니다.",
    },
    {
        "question_id": "D00-TARGET-001",
        "stage": "00",
        "topic": "목표변수",
        "question": "지금 예측하려는 `{target_col}`가 실제 현장에서 의미 있는 결과인가요?",
        "why_it_matters": "목표변수가 사후 결과이거나 의사결정 시점 이후에만 알 수 있으면 누수와 실행 불가능성이 생깁니다.",
        "starter_answers": [
            "최종 불량 여부",
            "배출량 또는 품질 지표",
            "다음 고장까지 남은 시간",
            "생산 수율",
            "작업 완료시간",
        ],
        "upgrade_prompt": "목표값을 언제 알 수 있는지, 예측 결과를 누가 어떤 의사결정에 쓰는지 함께 적습니다.",
        "answer_format": "목표변수 의미, 알 수 있는 시점, 의사결정 사용처를 짧게 작성합니다.",
        "decision_effect": "타깃 검증, 누수 점검, 평가 지표 선택에 반영됩니다.",
    },
    {
        "question_id": "D02-PHYSICAL-RANGE-001",
        "stage": "02",
        "topic": "데이터 진단",
        "question": "물리적으로 말이 안 되는 값의 범위가 있나요?",
        "why_it_matters": "현장 상식으로 걸러지는 값은 통계적 이상치보다 먼저 검토해야 하는 데이터 품질 후보입니다.",
        "starter_answers": [
            "온도가 음수면 이상",
            "압력이 0이면 센서 오류",
            "유량이 0인데 생산량이 있으면 이상",
            "전력이 음수면 오류",
            "습도가 100%를 넘으면 확인 필요",
        ],
        "upgrade_prompt": "정확한 기준을 모르면 상식적 의심 범위와 확인 필요라고 함께 적습니다.",
        "answer_format": "컬럼명 또는 센서명, 의심 범위, 왜 이상하다고 보는지 작성합니다.",
        "decision_effect": "이상치 후보, rule filter 후보, 보고서의 추가 확인 질문에 반영됩니다.",
    },
    {
        "question_id": "D02-OPERATING-STATE-001",
        "stage": "02",
        "topic": "운전 상태",
        "question": "분석에서 제외하거나 따로 봐야 할 운전 구간이 있나요?",
        "why_it_matters": "예열, 정지, 청소, 유지보수 구간은 정상 운전과 다른 분포를 만들어 모델을 흔들 수 있습니다.",
        "starter_answers": [
            "장비 예열",
            "정지 상태",
            "청소/CIP",
            "교대 직후",
            "유지보수 직후",
            "센서 교체일",
        ],
        "upgrade_prompt": "해당 구간을 알 수 있는 컬럼, 시간대, 값 패턴을 같이 적습니다.",
        "answer_format": "구간 이름, 식별 가능한 조건, 제외/분리/관찰 중 하나를 작성합니다.",
        "decision_effect": "세그먼트 분석, 필터링 후보, 검증 분할 주의사항에 반영됩니다.",
    },
    {
        "question_id": "D03-FEATURE-001",
        "stage": "03",
        "topic": "피처 설계",
        "question": "원시 컬럼끼리 조합하면 더 의미 있는 변수가 있나요?",
        "why_it_matters": "도메인 파생변수는 모델이 물리 관계를 더 쉽게 배우도록 돕지만, 공식과 시점을 확인해야 합니다.",
        "starter_answers": [
            "온도차",
            "압력비",
            "유량 대비 전력",
            "생산량 대비 에너지",
            "rolling 평균",
            "진동 RMS",
        ],
        "upgrade_prompt": "공식이 완벽하지 않아도 A/B가 효율처럼 보인다는 수준으로 적습니다.",
        "answer_format": "변수 아이디어, 가능한 공식, 필요한 컬럼, 누수 의심 여부를 작성합니다.",
        "decision_effect": "feature_candidate_menu.csv의 도메인 피처 후보로 반영됩니다.",
    },
    {
        "question_id": "D05-EVAL-RISK-001",
        "stage": "05",
        "topic": "평가 기준",
        "question": "어떤 예측 실수가 더 위험한가요?",
        "why_it_matters": "현장 리스크가 비대칭이면 단순 평균 오차보다 threshold, 재현율, 보수적 예측이 더 중요할 수 있습니다.",
        "starter_answers": [
            "고장인데 정상으로 예측하는 것",
            "정상인데 고장으로 오탐하는 것",
            "배출량 초과를 놓치는 것",
            "불량을 정상으로 넘기는 것",
            "불필요한 정비 알람이 너무 많은 것",
        ],
        "upgrade_prompt": "비용, 안전, 규제, 현장 신뢰도 관점에서 더 위험한 실수를 적습니다.",
        "answer_format": "더 위험한 오류, 이유, 가능하면 비용 또는 운영 영향도를 작성합니다.",
        "decision_effect": "metric 선택, threshold 해석, 모델 비교 보고서에 반영됩니다.",
    },
    {
        "question_id": "D07-ACTION-001",
        "stage": "07",
        "topic": "결과 해석",
        "question": "중요한 변수 상위 결과를 현장 액션으로 바꾸면 무엇을 확인해야 하나요?",
        "why_it_matters": "모델 해석은 현장 점검, 추가 실험, 운영 개선으로 번역될 때 분석 결과로서 가치가 생깁니다.",
        "starter_answers": [
            "센서 캘리브레이션 확인",
            "밸브 상태 점검",
            "냉각수 라인 확인",
            "작업 조건 재점검",
            "유지보수 이력 확인",
        ],
        "upgrade_prompt": "누가, 언제, 어떤 순서로 확인할지까지 적으면 액션 아이템으로 바로 전환됩니다.",
        "answer_format": "확인 대상, 점검 순서, 담당자 또는 확인 자료를 작성합니다.",
        "decision_effect": "action_items.md/json과 최종 보고서의 다음 행동에 반영됩니다.",
    },
]


def default_question_cards(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or {}
    target_col = str(cfg.get("target_col") or "target")
    cards = copy.deepcopy(BASE_QUESTION_CARDS)
    for card in cards:
        for key in ["question", "why_it_matters", "upgrade_prompt", "answer_format", "decision_effect"]:
            card[key] = str(card[key]).format(target_col=target_col)
        card["confidence"] = "낮음"
        card["status"] = "open"
    return cards


def render_questionnaire_markdown(cards: list[dict[str, Any]], cfg: dict[str, Any], run_id: str) -> str:
    lines = [
        "# 도메인 전문가 학습형 질문지",
        "",
        f"- run_id: `{run_id}`",
        f"- target_col: `{cfg.get('target_col', 'target')}`",
        "",
        "이 질문지는 전문가만 답하라는 문서가 아닙니다. 답이 바로 떠오르지 않으면 예상 답변 중 가까운 것을 고르고, 확신도는 `낮음`으로 둔 뒤 나중에 보완합니다.",
        "",
        "## 답변 규칙",
        "",
        "- `선택한 예시 답변`에는 아래 예상 답변 중 가까운 표현을 적습니다.",
        "- `내 상황 보완`에는 현재 데이터, 현장 맥락, 검색해서 알게 된 배경지식, 팀원에게 확인할 내용을 적습니다.",
        "- 확신도는 `낮음`, `보통`, `높음` 중 하나를 사용합니다.",
        "- 상태는 `open`, `answered`, `accepted`, `deferred` 중 하나를 사용합니다.",
    ]
    lines += [""] + status_glossary_lines()
    for card in cards:
        lines += [
            "",
            f"## {card['question_id']} | Stage {card['stage']} | {card['topic']}",
            "",
            f"**질문:** {card['question']}",
            "",
            f"**왜 중요한가:** {card['why_it_matters']}",
            "",
            f"**Manual 반영:** {card['decision_effect']}",
            "",
            f"**답변 발전 방향:** {card['upgrade_prompt']}",
            "",
            "### 예상 답변",
            "",
        ]
        lines.extend(f"- {answer}" for answer in card.get("starter_answers", []))
        lines += [
            "",
            "### 답변 작성",
            "",
            "- 선택한 예시 답변: ",
            "- 내 상황 보완: ",
            "- 확신도: 낮음",
            "- 상태: open",
        ]
    return "\n".join(lines).strip() + "\n"


def render_answers_template(cards: list[dict[str, Any]], cfg: dict[str, Any], run_id: str) -> str:
    checkpoint_groups = [
        (
            "Stage 01 직전 체크포인트",
            "KPI와 타깃 의미를 확인합니다. Stage 00의 dataset_review.md를 본 뒤 답합니다.",
            {"D00-KPI-001", "D00-TARGET-001"},
        ),
        (
            "Stage 03 직전 체크포인트",
            "진단 결과를 보고 물리 범위, 운전 상태, 피처 아이디어를 보완합니다.",
            {"D02-PHYSICAL-RANGE-001", "D02-OPERATING-STATE-001", "D03-FEATURE-001"},
        ),
        (
            "Stage 05 직전 체크포인트",
            "피처와 검증 분할 결과를 본 뒤 어떤 예측 실수가 더 위험한지 정합니다.",
            {"D05-EVAL-RISK-001"},
        ),
        (
            "Stage 07 직전 체크포인트",
            "모델 결과를 현장 액션으로 바꿀 때 무엇을 확인할지 정리합니다.",
            {"D07-ACTION-001"},
        ),
    ]
    card_by_id = {str(card["question_id"]): card for card in cards}
    lines = [
        "# domain_answers.md",
        "",
        f"- run_id: `{run_id}`",
        f"- target_col: `{cfg.get('target_col', 'target')}`",
        "",
        "이 파일은 체크포인트별로 나누어 답합니다. Stage 01에서 모든 질문을 미리 채우는 것이 아니라, 각 Stage에서 생성된 참고자료를 본 뒤 해당 섹션만 보완합니다.",
        "",
        "## 상태값 의미",
        "",
        "- `open`: 아직 해당 체크포인트에서 사용자가 확인/확정하지 않은 상태입니다. 내용이 조금 있어도 Stage별 참고자료를 보고 다시 보완할 수 있습니다.",
        "- `answered`: 사용자가 답변을 작성했지만 아직 강한 규칙으로 확정하지 않은 상태입니다.",
        "- `accepted`: 사용자가 확신도 높음으로 확인한 도메인 규칙 후보입니다.",
        "- `deferred`: 사용자가 이번 체크포인트를 기본 추천으로 넘긴 상태입니다.",
        "",
        "## 답변 원칙",
        "",
        "- 예상 답변 중 가까운 것을 골라도 됩니다.",
        "- 확신이 낮으면 `확신도: 낮음`으로 두고, 보고서에는 도메인 가설로만 남깁니다.",
        "- `자동 후보 없음`은 자동 분류기가 후보를 못 찾았다는 뜻이며, 실제 후보가 없다는 결론은 아닙니다.",
        "",
    ]
    lines += status_glossary_lines()
    for title, guide, qids in checkpoint_groups:
        lines += ["", f"## {title}", "", guide]
        for qid in qids:
            card = card_by_id.get(qid)
            if not card:
                continue
            lines += [
                "",
                f"### {card['question_id']} | Stage {card['stage']} | {card['topic']}",
                f"- 질문: {card['question']}",
                f"- 왜 중요한가: {card['why_it_matters']}",
                f"- 예상 답변 참고: {', '.join(card.get('starter_answers', [])[:5])}",
                f"- 답변 발전 방향: {card['upgrade_prompt']}",
                "- 선택한 예시 답변: ",
                "- 내 상황 보완: ",
                "- 확신도: 낮음",
                "- 상태: open",
            ]
    return "\n".join(lines).strip() + "\n"


def parse_answers_markdown(markdown: str, cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    card_by_id = {str(card["question_id"]): card for card in cards}
    sections = _split_answer_sections(markdown)
    parsed: dict[str, dict[str, Any]] = {}
    for question_id, body in sections.items():
        if question_id not in card_by_id:
            continue
        selected = _clean_answer(_field_value(body, "선택한 예시 답변"))
        refinement = _clean_answer(_field_value(body, "내 상황 보완"))
        confidence = _normalize_confidence(_field_value(body, "확신도"))
        answer_text = " | ".join(part for part in [selected, refinement] if part)
        status = _normalize_status(_field_value(body, "상태"), bool(answer_text))
        starter_answers = {str(item).strip() for item in card_by_id[question_id].get("starter_answers", [])}
        starter_only = bool(selected) and selected in starter_answers and not refinement
        deferred_only = _is_deferred_only(selected, refinement)
        if deferred_only:
            # Treat "[DEFERRED ...]" as a workflow control marker, not as a domain answer.
            answer_source = "deferred_to_default"
            conclusion_level = "unanswered"
            safety_level = "no_effect"
            status = "deferred"
            answer_text = ""
            selected = ""
            refinement = refinement or f"{DEFERRED_MARKER_PREFIX}: User delegated to default]"
        elif not answer_text or answer_text == "모름":
            answer_source = "unanswered"
            conclusion_level = "unanswered"
            safety_level = "no_effect"
            status = "open" if status == "answered" else status
        elif starter_only:
            answer_source = "starter_answer_only"
            conclusion_level = "domain_hypothesis"
            safety_level = "observation_only"
        else:
            answer_source = "user_refined"
            conclusion_level = "confirmed_domain_rule" if confidence == "높음" and status == "accepted" else "domain_hypothesis"
            safety_level = "review_candidate" if conclusion_level == "confirmed_domain_rule" else "observation_only"
        parsed[question_id] = {
            "question_id": question_id,
            "selected_starter_answer": selected,
            "refinement": refinement,
            "raw_answer": answer_text,
            "confidence": confidence,
            "status": status,
            "answer_source": answer_source,
            "conclusion_level": conclusion_level,
            "safety_level": safety_level,
        }
    return parsed


def _is_deferred_only(selected: str, refinement: str) -> bool:
    # If the user (or agent) wrote a deferred marker, we treat it as "no domain answer provided".
    # This keeps the context pack clean and ensures deferred answers never become "domain hypotheses".
    s = (selected or "").strip()
    r = (refinement or "").strip()
    marker = DEFERRED_MARKER_PREFIX

    has_marker = s.startswith(marker) or r.startswith(marker)
    if not has_marker:
        return False

    # Only treat as deferred when the section contains nothing except deferred markers.
    def strip_markers(text: str) -> str:
        return re.sub(r"\[DEFERRED[^\]]*\]", "", text or "").strip()

    return strip_markers(s) == "" and strip_markers(r) == ""


def build_context_pack(
    cards: list[dict[str, Any]],
    answers: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    merged_cards: list[dict[str, Any]] = []
    stage_notes: dict[str, list[str]] = {}
    hypotheses: list[str] = []
    confirmed_rules: list[str] = []
    open_or_low: list[str] = []
    answer_quality_warnings: list[dict[str, str]] = []
    for card in cards:
        question_id = str(card["question_id"])
        answer = answers.get(question_id, {})
        item = {
            **card,
            "selected_starter_answer": answer.get("selected_starter_answer", ""),
            "refinement": answer.get("refinement", ""),
            "raw_answer": answer.get("raw_answer", ""),
            "confidence": answer.get("confidence", card.get("confidence", "낮음")),
            "status": answer.get("status", card.get("status", "open")),
            "answer_source": answer.get("answer_source", "unanswered"),
            "conclusion_level": answer.get("conclusion_level", "unanswered"),
            "safety_level": answer.get("safety_level", "no_effect"),
        }
        if item["raw_answer"]:
            note = f"{question_id}: {_compact_domain_note(str(item['raw_answer']))}"
            stage_notes.setdefault(str(item["stage"]), []).append(note)
            if item["conclusion_level"] == "confirmed_domain_rule":
                confirmed_rules.append(note)
            elif item["conclusion_level"] == "domain_hypothesis":
                hypotheses.append(note)
        if item["status"] in {"open", "deferred"} or item["confidence"] == "낮음":
            open_or_low.append(question_id)
        if item["status"] == "accepted" and item["confidence"] == "낮음":
            answer_quality_warnings.append(
                {
                    "question_id": question_id,
                    "warning": "accepted_low_confidence",
                    "suggestion": "`accepted`를 유지하려면 확신도를 `보통` 이상으로 올릴 근거를 적고, 아니면 `answered`로 낮추는 것이 안전합니다.",
                }
            )
        if item["status"] == "accepted" and item["answer_source"] == "starter_answer_only":
            answer_quality_warnings.append(
                {
                    "question_id": question_id,
                    "warning": "accepted_starter_only",
                    "suggestion": "예시 답변만 선택한 상태라면 `내 상황 보완`에 실제 현장 조건이나 예외를 한 줄 이상 적어 주세요.",
                }
            )
        if question_id.startswith("D07-") and item["status"] == "accepted" and item["confidence"] != "높음":
            answer_quality_warnings.append(
                {
                    "question_id": question_id,
                    "warning": "action_item_without_high_confidence",
                    "suggestion": "현장 액션으로 바로 바꿀 답변은 가능하면 `확신도: 높음` 근거를 적고, 어렵다면 `answered`로 남기는 편이 안전합니다.",
                }
            )
        merged_cards.append(item)
    compact_summary = {
        "target_col": cfg.get("target_col"),
        "task_type": cfg.get("task_type"),
        "answered_count": sum(1 for item in merged_cards if item["raw_answer"]),
        "accepted_count": sum(1 for item in merged_cards if item["status"] == "accepted"),
        "low_confidence_count": sum(1 for item in merged_cards if item["confidence"] == "낮음"),
        "domain_hypotheses": hypotheses[:20],
        "confirmed_domain_rules": confirmed_rules[:20],
        "open_or_low_confidence_questions": open_or_low,
        "answer_quality_warnings": answer_quality_warnings,
        "stage_notes": stage_notes,
    }
    return {
        "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target_col": cfg.get("target_col"),
        "task_type": cfg.get("task_type"),
        "cards": merged_cards,
        "compact_summary": compact_summary,
        "safety_policy": {
            "starter_answers_are_hypotheses": True,
            "low_confidence_answers_never_auto_filter": True,
            "domain_rules_default_status": "candidate",
            "automatic_source_data_deletion": False,
        },
    }


def domain_treatment_candidates_from_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in pack.get("cards", []):
        if str(item.get("stage")) != "02" or not item.get("raw_answer"):
            continue
        rows.append(
            {
                "kind": "domain_rule_candidate",
                "feature": "domain_context",
                "recommendation": f"candidate only; review before filtering: {_compact_domain_note(str(item['raw_answer']), max_sentences=3)}",
                "reason": (
                    f"{item.get('question_id')} confidence={item.get('confidence')} "
                    f"status={item.get('status')} level={item.get('conclusion_level')}"
                ),
            }
        )
    return rows


def domain_feature_candidates_from_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in pack.get("cards", []):
        if item.get("question_id") != "D03-FEATURE-001" or not item.get("raw_answer"):
            continue
        rows.append(
            {
                "family": "domain_feature_hypothesis",
                "feature_name": "domain_feature_hypothesis_1",
                "formula": "user-proposed; confirm columns and formula before implementation",
                "required_columns": "manual_review_required",
                "recommendation_basis": str(item["raw_answer"]),
                "domain_knowledge_needed": "Convert the hypothesis into exact columns, units, formula, and leakage check before auto-generation.",
                "multicollinearity_risk": "unknown",
                "leakage_risk": "review_required",
                "auto_recommended": False,
                "confidence": item.get("confidence"),
                "status": item.get("status"),
            }
        )
    return rows


def build_model_guidance_from_pack(pack: dict[str, Any]) -> dict[str, Any]:
    notes = []
    for item in pack.get("cards", []):
        if item.get("question_id") == "D05-EVAL-RISK-001" and item.get("raw_answer"):
            notes.append(
                {
                    "question_id": item.get("question_id"),
                    "risk_note": item.get("raw_answer"),
                    "confidence": item.get("confidence"),
                    "status": item.get("status"),
                    "usage": "Use as metric/threshold interpretation guidance; do not override configured metric automatically.",
                }
            )
    return {
        "schema_version": "manual-domain-model-guidance.v1",
        "items": notes,
        "safety_note": "Domain risk answers guide interpretation only unless the user explicitly changes metric_primary or thresholds.",
    }


def build_action_items_from_pack(pack: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for item in pack.get("cards", []):
        if item.get("question_id") != "D07-ACTION-001" or not item.get("raw_answer"):
            continue
        items.append(
            {
                "action_id": f"ACT-{item['question_id']}",
                "question_id": item["question_id"],
                "recommended_action": item["raw_answer"],
                "evidence_level": item.get("conclusion_level", "domain_hypothesis"),
                "confidence": item.get("confidence"),
                "status": item.get("status"),
                "source": "domain_context_pack",
                "next_check": "Connect this action to top feature importance, SHAP, residual, or data-quality evidence in the final report.",
            }
        )
    return {
        "schema_version": ACTION_ITEMS_SCHEMA_VERSION,
        "items": items,
        "open_or_low_confidence_questions": (pack.get("compact_summary") or {}).get("open_or_low_confidence_questions", []),
    }


def render_context_pack_markdown(pack: dict[str, Any]) -> str:
    summary = pack.get("compact_summary") or {}
    lines = [
        "# 도메인 컨텍스트 팩",
        "",
        f"- run_id: `{pack.get('run_id')}`",
        f"- target_col: `{pack.get('target_col')}`",
        f"- answered_count: `{summary.get('answered_count', 0)}`",
        f"- accepted_count: `{summary.get('accepted_count', 0)}`",
        f"- low_confidence_count: `{summary.get('low_confidence_count', 0)}`",
        "",
        "## 도메인 가설",
        "",
    ]
    hypotheses = summary.get("domain_hypotheses") or []
    lines.extend(f"- {item}" for item in hypotheses) if hypotheses else lines.append("- 없음")
    lines += ["", "## 확인된 도메인 규칙", ""]
    confirmed = summary.get("confirmed_domain_rules") or []
    lines.extend(f"- {item}" for item in confirmed) if confirmed else lines.append("- 없음")
    lines += ["", "## 추가 확인 필요", ""]
    open_or_low = summary.get("open_or_low_confidence_questions") or []
    lines.extend(f"- {item}" for item in open_or_low) if open_or_low else lines.append("- 없음")
    lines += ["", "## 답변 품질 경고", ""]
    warnings = summary.get("answer_quality_warnings") or []
    if warnings:
        for item in warnings:
            lines.append(f"- `{item.get('question_id')}` {item.get('warning')}: {item.get('suggestion')}")
    else:
        lines.append("- 없음")
    return "\n".join(lines).strip() + "\n"


def render_action_items_markdown(payload: dict[str, Any]) -> str:
    lines = ["# 도메인 기반 액션 아이템", ""]
    items = payload.get("items") or []
    if not items:
        lines.append("- 아직 accepted 상태의 결과 해석 답변이 없습니다. `domain_answers.md`의 D07 질문을 보완하세요.")
    for item in items:
        lines += [
            f"## {item['action_id']}",
            "",
            f"- 권장 액션: {item['recommended_action']}",
            f"- 근거 수준: `{item['evidence_level']}`",
            f"- 확신도: `{item['confidence']}`",
            f"- 상태: `{item['status']}`",
            f"- 다음 확인: {item['next_check']}",
            "",
        ]
    open_or_low = payload.get("open_or_low_confidence_questions") or []
    if open_or_low:
        lines += ["## 추가 확인 질문", ""]
        lines.extend(f"- {qid}" for qid in open_or_low)
    return "\n".join(lines).strip() + "\n"


def write_questionnaire_files(
    cfg: dict[str, Any],
    run_id: str,
    paths: dict[str, Path],
    overwrite_answers_template: bool = False,
) -> dict[str, Any]:
    cards = default_question_cards(cfg)
    reports = paths["reports"]
    payload = {
        "schema_version": QUESTIONNAIRE_SCHEMA_VERSION,
        "run_id": run_id,
        "target_col": cfg.get("target_col"),
        "cards": cards,
        "answer_file": "domain_answers.md",
    }
    _write_json(reports / "domain_questionnaire.json", payload)
    (reports / "domain_questionnaire.md").write_text(render_questionnaire_markdown(cards, cfg, run_id), encoding="utf-8")
    answers_path = reports / "domain_answers.md"
    if overwrite_answers_template or not answers_path.exists():
        answers_path.write_text(render_answers_template(cards, cfg, run_id), encoding="utf-8")
    return payload


def ingest_answers_file(
    cfg: dict[str, Any],
    run_id: str,
    paths: dict[str, Path],
    answers_path: str | Path | None = None,
) -> dict[str, Any]:
    cards = default_question_cards(cfg)
    path = Path(answers_path) if answers_path else paths["reports"] / "domain_answers.md"
    if not path.is_absolute():
        path = (paths["reports"] / path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Domain answers file not found: {path}")
    # Preserve run-level checkpoint history even if users re-ingest answers multiple times.
    previous_pack = _read_json(paths["reports"] / "domain_context_pack.json", {})
    answers = parse_answers_markdown(path.read_text(encoding="utf-8"), cards)
    pack = build_context_pack(cards, answers, cfg, run_id)
    if isinstance(previous_pack, dict):
        for key in ["deferred_checkpoints", "cleared_checkpoints"]:
            prior = previous_pack.get(key)
            if isinstance(prior, list):
                pack[key] = prior
    _write_json(paths["reports"] / "domain_context_pack.json", pack)
    (paths["reports"] / "domain_context_pack.md").write_text(render_context_pack_markdown(pack), encoding="utf-8")
    return pack


def load_domain_context_pack(paths: dict[str, Path]) -> dict[str, Any]:
    return _read_json(paths["reports"] / "domain_context_pack.json", {})


def write_model_guidance_files(paths: dict[str, Path]) -> dict[str, Any] | None:
    pack = load_domain_context_pack(paths)
    if not pack:
        return None
    payload = build_model_guidance_from_pack(pack)
    _write_json(paths["reports"] / "modeling_domain_guidance.json", payload)
    return payload


def write_action_items_files(cfg: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any] | None:
    pack = load_domain_context_pack(paths)
    if not pack:
        return None
    payload = build_action_items_from_pack(pack)
    _write_json(paths["reports"] / "action_items.json", payload)
    (paths["reports"] / "action_items.md").write_text(render_action_items_markdown(payload), encoding="utf-8")
    return payload


def _split_answer_sections(markdown: str) -> dict[str, str]:
    pattern = re.compile(r"^#{2,3}\s+(D\d{2}-[A-Z0-9-]+)\b.*$", re.MULTILINE)
    matches = list(pattern.finditer(markdown))
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        sections[match.group(1)] = markdown[start:end]
    return sections


def _field_value(section: str, field: str) -> str:
    current = ""
    capture = False
    for line in section.splitlines():
        match = re.match(rf"^\s*-\s*{re.escape(field)}\s*:\s*(.*)$", line)
        if match:
            current = match.group(1).strip()
            capture = True
            continue
        if capture and line.startswith("  "):
            current = f"{current}\n{line.strip()}".strip()
            continue
        if capture and re.match(r"^\s*-\s*[^:]+:", line):
            break
    return current.strip()


def _normalize_confidence(value: str) -> str:
    clean = _clean_answer(value)
    return clean if clean in VALID_CONFIDENCE else "낮음"


def _normalize_status(value: str, has_answer: bool) -> str:
    clean = _clean_answer(value)
    if clean in VALID_STATUS:
        return clean
    return "answered" if has_answer else "open"


def _clean_answer(value: Any) -> str:
    text = str(value or "").strip()
    placeholders = {"", "-", "여기에 작성", "(여기에 작성)", "선택", "없음"}
    return "" if text in placeholders else text


def _shorten(text: str, max_chars: int) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def _compact_domain_note(text: str, max_sentences: int = 2) -> str:
    compact = " ".join(str(text).split())
    parts = re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+|(?<=함\.)\s+|(?<=음\.)\s+", compact)
    parts = [part.strip(" ,") for part in parts if part.strip(" ,")]
    if not parts:
        return compact
    return " / ".join(parts[:max_sentences])


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
