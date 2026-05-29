# Manual Context Minimization Guide

Manual을 이어서 작업할 때는 전체 문서를 매번 읽지 말고, 아래 순서로 최소 컨텍스트만 확인한다.

## 1. 현재 run 찾기

- `state/active_run.json`
- `runs/<run_id>/summary.json`
- `runs/<run_id>/progress.md`
- `runs/<run_id>/reports/domain_context_pack.json`

## 2. 필요한 stage만 읽기

- 데이터 구조 확인: `reports/stage_00_report_payload.json`
- 환경/입력 확인: `reports/stage_01_report_payload.json`
- 진단 확인: `reports/stage_02_report_payload.json`
- 도메인 답변 확인: `reports/domain_context_pack.json`의 `compact_summary`
- 현장 액션 확인: `reports/action_items.json`
- 피처/검증/모델/제출은 해당 stage 산출물과 manifest만 읽기

## 3. 문서 읽기 축소 규칙

- 새 프로젝트 온보딩이 아니면 `README.md` 전체를 다시 읽지 않는다.
- stage 하나만 수정할 때는 관련 `SKILL.md`, stage payload, 직접 산출물만 읽는다.
- 보고서 재생성 시에는 MD 원본보다 `stage_*_report_payload.json`을 우선 source of truth로 본다.
- 도메인 답변 원문 `domain_answers.md`는 사용자가 직접 수정할 때만 열고, agent 작업에는 `domain_context_pack.json`을 우선 사용한다.

## 4. 프롬프트 축소 규칙

- 현재 단계, 다음 단계, 필요한 입력 파일, 기대 산출물만 적는다.
- 이미 저장된 결정은 `decision_log.json`을 붙여 넣지 말고 핵심 한 줄만 요약한다.
- 긴 JSON 전체를 붙여 넣지 말고 필요한 KPI와 상위 5~15행만 가져온다.
- `starter_answer_only` 또는 `confidence=낮음` 도메인 답변은 확정 규칙처럼 쓰지 말고 “가설/추가 확인”으로 요약한다.

## 5. 도메인 답변 안전 규칙

- Stage 02의 `domain_rule_candidate`는 자동 필터링으로 적용하지 않는다.
- Stage 03의 `domain_feature_hypothesis`는 자동 생성 피처가 아니라 후보로만 기록한다.
- Stage 05의 도메인 리스크 답변은 metric과 threshold 해석을 돕되, config를 자동 변경하지 않는다.
- Stage 07은 `action_items.json`과 `action_items.md`를 읽어 현장 점검 항목을 요약한다.

## 6. 권장 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-next-guide\scripts\next_guide.py --project-root <analysis_root>
```

## 7. 02H/05H 가설 단계 컨텍스트 규칙

- 가설을 세울 때 긴 공학 보고서 원문을 매번 붙이지 않는다.
- 먼저 `runs/<run_id>/run_index.md`와 `runs/<run_id>/artifact_index.json`을 읽는다.
- 가설 수립에는 `reports/hypothesis_context_pack.json`의 `compact_summary`와 `evidence_cards`만 기본 입력으로 사용한다.
- 사용자가 직접 수정하는 파일은 `reports/hypothesis_answers.md`이고, agent 기본 입력은 `reports/hypothesis_registry.json`이다.
- Stage 03 피처 후보 검토에는 `reports/feature_candidate_menu.csv`에서 `hypothesis_id`, `formula`, `leakage_risk`, `validation_method`, `status` 컬럼만 우선 확인한다.
- Stage 05 이후에는 긴 모델 보고서보다 `artifacts/models/metrics.csv`, `artifacts/models/ablation_groups_plan.csv`, `reports/hypothesis_validation_results.json`을 먼저 읽는다.
- 원문 보고서가 필요하면 `artifact_index.json`에서 크기를 확인한 뒤 관련 섹션만 열고, 다음 prompt에는 top-k 요약만 남긴다.

## 8. Report Payload 우선 규칙

- 모든 PDF 대상 stage는 `reports/stage_<stage>_report_payload.json`을 먼저 만든다.
- PDF writer는 이 payload를 우선 읽고, 원본 MD/CSV/JSON은 payload가 부족할 때만 보조로 읽는다.
- 현재 표준 payload 적용 stage는 `00P`, `00`, `01`, `02`, `02H`, `03`, `04`, `05`, `05H`, `06`이다.
- 긴 보고서 재생성이나 리뷰 요청 시 원본 markdown 전체보다 해당 stage payload의 `kpis`, `tables`, `sections`만 우선 전달한다.
