# Manual Agent Map

`Manual/`은 범용 표 형식 데이터 분석 파이프라인을 실행하는 영역입니다. 실제 데이터와 실행 산출물은 `Manual/runs/<run_id>/`에만 두며, 기본 작업에서는 긴 과거 보고서를 읽지 않습니다.

## 단계 라우팅

| 작업 | 먼저 읽을 위치 |
| --- | --- |
| 원본 CSV/Excel 정규화 | `plugins/manual-00-raw-intake/` |
| 데이터 검토·환경 확인·진단 | `plugins/manual-00-data-reviewer/`, `manual-01-env-checker/`, `manual-02-profiler-diagnoser/` |
| 도메인·가설 확인 | `plugins/manual-domain-expert/`, `manual-hypothesis-planner/` |
| 피처·검증·모델·제출·보고서 | `manual-03-feature-builder/`부터 `manual-07-report-writer/` |

## 실행 및 재개

1. 새 작업은 `README.md`, `config/new_dataset_config.example.json`, 필요한 플러그인 `SKILL.md`만 읽습니다.
2. 기존 run은 `state/active_run.json`, `runs/<run_id>/run_state.json`, 현재 단계의 report payload 순서로 확인합니다.
3. `run_manual_pipeline.ps1`로 실행하며, smoke run 이후에만 full train을 고려합니다.

## 보호 규칙

- raw와 test 데이터는 설정된 용도 밖의 피처·모델 선택에 사용하지 않습니다.
- 원본 데이터, run 산출물, 모델 파일은 커밋하지 않습니다.
- explorer/reviewer/verifier는 독립적인 탐색·리뷰가 필요한 L2/L3 작업에서만 선택적으로 사용합니다.
