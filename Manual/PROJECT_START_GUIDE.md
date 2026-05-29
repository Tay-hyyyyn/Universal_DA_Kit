# Manual 새 데이터셋 시작 가이드

이 문서는 `Manual/` 프로세스를 새 데이터셋에 적용할 때의 표준 시작 절차를 정리한다.

## 현재 Manual 폴더 판정

현재 `Manual/`은 단순 문서 폴더가 아니다. 아래 요소가 함께 들어 있는 실행 가능한 데이터분석 프로세스 폴더다.

- 실행 구조: `run_manual_pipeline.ps1`, `agent_manifest.json`
- 단계별 코드: `plugins/manual-*`, `plugins/_shared`
- 설정 예시: `config/*.json`
- 사용자/agent 가이드: `README.md`, `CODE_AGENT_ONBOARDING.md`, `AGENT_USAGE_GUIDELINES.md`
- 테스트: `tests/`
- 과거 실행 산출물: `runs/`, `state/`, `log.md`, `__pycache__/`, `tests/_tmp*`

따라서 팀 공유나 새 프로젝트 시작용으로는 산출물이 제거된 clean template copy를 사용하는 것이 좋다.

## 새 프로젝트 권장 폴더 구조

새 데이터셋을 시작할 때는 프로젝트 루트 아래에 `Manual/`을 두고, 데이터와 실행 산출물을 분리한다.

```text
<project_root>/
├── Manual/
│   ├── config/
│   │   ├── analysis_config.template.json
│   │   └── <project>_config.json
│   ├── plugins/
│   ├── tests/
│   ├── run_manual_pipeline.ps1
│   ├── README.md
│   ├── PROJECT_START_GUIDE.md
│   ├── log.md
│   └── runs/
│       └── <run_id>/
├── data/
│   ├── raw/
│   │   ├── train.csv
│   │   ├── test.csv
│   │   └── sample_submission.csv
│   └── metadata/
└── docs/
```

대용량 원천 데이터는 Git에 올리지 않는 것을 기본으로 한다. Git에는 `Manual/`, config 예시, 분석 코드, README, 최종 요약 문서를 올리고, 원천 데이터는 팀 공유 스토리지나 별도 데이터 저장소 위치만 문서화한다.

## 시작 절차

1. Clean template copy를 새 프로젝트 루트에 `Manual/` 이름으로 복사한다.
2. 원천 데이터를 `<project_root>/data/raw/`에 둔다.
3. `Manual/config/new_dataset_config.example.json`을 복사해 `Manual/config/<project>_config.json`을 만든다.
4. config에서 `train_path`, `target_col`, `task_type`을 먼저 채운다.
5. 가능한 경우 `test_path`, `sample_submission_path`, `id_col`, `group_col`, `time_col`도 채운다. 단, `test_path`는 기본 정책상 최종 평가 전까지 학습·튜닝·모델선택에 쓰지 않는다.
6. 메타행이 있는 CSV, 다중 CSV 병합, 단위행 제거가 필요하면 `raw_intake.enabled=true`로 두고 `raw_paths`, `meta_rows`, `timestamp_col`을 지정한다.
7. `domain_context`와 `domain_expertise_notes`에 업무/공정 맥락을 짧게 적는다.
8. 먼저 smoke run을 수행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\<project>_config.json `
  -RunId <project>_smoke `
  -AutoProceed `
  -TuningTrials 1 `
  -MaxFolds 1 `
  -ExplainModels none `
  -NoPdfReport
```

9. smoke run이 통과하면 `-AutoProceed`를 빼고 체크포인트 기반으로 정식 run을 시작한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\<project>_config.json `
  -RunId <project>_001 `
  -TuningTrials 8 `
  -MaxFolds 0
```

## 체크포인트에서 사용자가 할 일

Manual은 사용자 의견이 필요한 지점에서 `reports/pending_checkpoint.md` 또는 `reports/pending_hypothesis_checkpoint.md`를 만든 뒤 멈춘다. `reports/checkpoint_queue.md`가 있으면 이 파일을 먼저 열고 `review_state: current` 항목부터 처리한다.

| 시점 | 사용자가 읽을 파일 | 사용자가 수정할 파일 | 목적 |
|---|---|---|---|
| Stage 01 전 | `reports/pending_checkpoint.md` | `reports/domain_answers.md` | 타깃 KPI, 예측 목적, 위험한 오류 유형 확인 |
| Stage 02H | `reports/hypothesis_seed_report.md`, `reports/pending_hypothesis_checkpoint.md` | `reports/hypothesis_answers.md` | 검증할 가설을 `accepted`, 보류할 가설을 `deferred`로 결정 |
| Stage 03 전 | `reports/pending_checkpoint.md` | `reports/domain_answers.md` | 피처 사용 가능성, 물리/업무 범위, 누수 위험 확인 |
| Stage 05 전 | `reports/pending_checkpoint.md` | `reports/domain_answers.md` | 모델 선정 전 허용 모델, 위험 오차, 해석 우선순위 확인 |
| Stage 07 전 | `reports/pending_checkpoint.md` | `reports/domain_answers.md` | 최종 결과를 액션 아이템과 공유 문서로 변환 |

수정 후에는 같은 명령에 `-Resume`을 붙여 이어서 실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\<project>_config.json `
  -RunId <project>_001 `
  -Resume
```

## status 작성 규칙

`domain_answers.md`와 `hypothesis_answers.md`에서 사용하는 status는 아래 의미로 통일한다.

| status | 의미 | 언제 쓰나 |
|---|---|---|
| `open` | 아직 사용자가 판단하지 않은 상태 | 자동 생성 직후 |
| `answered` | 의견은 적었지만 이번 run의 강한 결정으로 쓰지는 않음 | 참고 의견, 낮은 확신 |
| `accepted` | 이번 run에 반영하거나 검증할 항목 | 피처 생성, ablation, 보고서 핵심 가설 |
| `deferred` | 이번 run에서는 보류 | 정보 부족, 추후 검토 |
| `auto-proceed` | 사용자가 직접 쓴 status가 아니라 실행 옵션 | 미답변 항목을 보수적으로 `deferred` 처리하고 진행 |

## Train / Validation / Test 구분

| 구분 | 쓰임 | Manual 기본 정책 |
|---|---|---|
| train | 모델 학습, 피처 생성, 교차검증 | 사용 |
| validation/holdout | 모델 선택, 튜닝, 오류 분석 | 사용 |
| test | 마지막 최종 확인 | 사용자가 명시하기 전까지 미사용 |

새 프로젝트 config는 기본적으로 `test_usage_mode: "forbidden"`을 둔다. 따라서 `test_path`를 적어도 Stage 05 모델 학습/튜닝/선택에는 test set이 들어가지 않는다. test set 사용은 사용자가 마지막 시점에 별도로 허용할 때만 진행한다.

## 가설 기반 범용 피처 문법

새 데이터셋에서는 `hypothesis_answers.md` 또는 config의 `hypothesis_templates`에서 `feature_plan`에 아래처럼 명시할 수 있다.

| 문법 | 생성 피처 |
|---|---|
| `lag:column_name` | `column_name__lag_<n>s` |
| `diff:column_name:3s` | `column_name__diff_3s` |
| `rolling_mean:column_name:5s` | `column_name__roll_mean_5s` |
| `hinge:column_name:q75` | `column_name__hinge_q75` |
| `interaction:col_a:col_b` | `col_a__x__col_b` |
| `ratio:col_a:col_b` | `col_a__div__col_b` |

시간 의미가 없는 데이터에는 `lag`, `diff`, `rolling_mean`을 쓰지 않는다. 시간 순서가 있다면 반드시 `time_col`을 지정하고 Stage 04에서 시간 누수를 확인한다.

## 결과물 위치

- 실행 로그: `Manual/log.md`
- 현재 run 상태: `Manual/runs/<run_id>/run_state.json`
- 진행 요약: `Manual/runs/<run_id>/progress.md`
- 체크포인트 파일: `Manual/runs/<run_id>/reports/pending_*.md`
- 피처 산출물: `Manual/runs/<run_id>/data/processed/`
- fold 산출물: `Manual/runs/<run_id>/data/folds/`
- 모델 산출물: `Manual/runs/<run_id>/artifacts/models/`
- 최종 보고서: `Manual/runs/<run_id>/reports/pdf/analysis_report_integrated.pdf`

## Git 공유 기준

Git에는 아래만 올린다.

- `Manual/run_manual_pipeline.ps1`
- `Manual/plugins/`
- `Manual/config/*.example.json` 또는 민감정보가 제거된 config
- `Manual/*.md`
- `Manual/tests/`

Git에는 아래를 올리지 않는다.

- `Manual/runs/`
- `Manual/state/`
- `Manual/log.md`
- `data/raw/` 원천 데이터
- `__pycache__/`, `*.pyc`, 테스트 임시폴더

