# Manual 도메인/가설 체크포인트 사용가이드

이 가이드는 Manual을 처음 쓰는 사용자도 도메인 지식과 가설 수립 과정을 안전하게 분석 사이클에 반영하도록 돕기 위한 문서입니다. 사용자가 깊은 전문가는 아니어도 “상식적 의심”, “검색해서 알게 된 배경지식”, “팀원에게 확인할 질문” 수준의 얕은 전문성을 남기는 것을 목표로 합니다.

## 전체 흐름

1. config에 `train_path`, `target_col`, `task_type`을 채웁니다.
2. Stage 00이 데이터 구조와 도메인 질문지를 만듭니다.
3. Stage 01/03/05/07 직전에는 `domain_answers.md` 체크포인트가 열립니다.
4. Stage 02 이후에는 `02H` 가설 체크포인트가 열리고 `hypothesis_answers.md`를 수정합니다.
5. Stage 05 이후에는 `05H`가 가설 검증 결과를 정리합니다.
6. 최종 보고서는 도메인 가설, 확정 규칙, 가설 검증 결과, 추가 확인 필요 항목을 구분해 표시합니다.

## 도메인 질문 파일

- 파일 위치: `Manual/runs/<run_id>/reports/domain_answers.md`
- 목적: KPI, 타깃 의미, 물리 범위, 운전 상태, 피처 아이디어, 평가 위험, 현장 액션을 질문합니다.
- 답변이 어렵다면 예상 답변 중 가까운 것을 고르고 `확신도: 낮음`으로 둡니다.
- 예시 답변만 선택한 항목은 확정 규칙이 아니라 `domain_hypothesis`로 저장됩니다.
- 낮은 확신도 답변은 자동 필터링이나 원본 데이터 삭제에 쓰지 않고, EDA 관찰 포인트와 보고서 질문으로만 사용합니다.

## 가설 질문 파일

- 파일 위치: `Manual/runs/<run_id>/reports/hypothesis_answers.md`
- 참고 자료: `Manual/runs/<run_id>/reports/hypothesis_seed_report.md`
- 목적: 예측모델이 검증해야 할 공학/통계 가설을 정리합니다.
- 각 가설은 `A가 어떠하면 B가 이러할 것이기에 타깃에 어떤 영향을 끼칠 것이다` 형식의 한 문장, 변수, 기대 방향, 지연, 예외 모드, 검증 방법, 피처 계획을 포함합니다.

## Status 의미

- `open`: 아직 사용자가 이 질문이나 가설을 검토하지 않았습니다. 이 상태가 남아 있으면 해당 체크포인트는 멈춥니다.
- `answered`: 의견은 남겼지만 자동 피처 생성이나 강한 규칙 적용까지 확정하지 않았습니다.
- `accepted`: 이번 분석에서 검증하고 피처 후보에도 반영할 항목입니다.
- `deferred`: 지금은 모르겠으므로 기본 추천 기준으로 넘어갑니다.

의견을 떠올리기 어렵다면 “그냥 진행해줘”라고 답하면 됩니다. 이 경우 현재 체크포인트의 열려 있는 항목은 `deferred`로 남고, 최종 보고서에는 기본 추천 기준으로 진행했다는 흔적이 남습니다.

## 도메인 지식 활용 위치

- Stage 00/01 전: 분석 목표, 타깃의 현장 의미, 데이터 row의 의미를 확인합니다.
- Stage 02 이후: 물리적으로 말이 안 되는 값, 결측/이상치의 도메인 원인, 운전 상태 구분을 보완합니다.
- Stage 02H: 공학적 메커니즘, 기대 방향, 지연시간, 예외 모드, 검증 방법을 가설로 확정합니다.
- Stage 03 전: Manual은 확정된 가설을 lag, rolling, hinge, interaction, piecewise 피처 후보로 바꿉니다.
- Stage 05 이후: Manual은 모델/ablation/feature lineage를 바탕으로 각 가설을 지지/부분지지/검증불가로 정리합니다.
- Stage 07 전: 검증된 가설을 현장 액션, 추가 계측 확인, 리포트 메시지로 바꿉니다.

## 컨텍스트 효율 규칙

- agent는 `domain_answers.md`와 긴 공학 보고서 원문을 매번 읽지 않습니다.
- 기본 입력은 `domain_context_pack.json`, `hypothesis_context_pack.json`, `hypothesis_registry.json`, `run_index.md`, `artifact_index.json`입니다.
- 긴 보고서는 필요한 경우에만 열고, 다음 작업에는 top-k 요약과 compact summary만 넘깁니다.
