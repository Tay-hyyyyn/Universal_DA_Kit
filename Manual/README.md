# 수동 범용 정형 데이터 분석 워크플로우 (Manual Tabular Workflow)

`Manual/`은 정형 데이터 회귀(Regression) 및 분류(Classification) 프로젝트를 위한 재사용 가능한 단계별 워크플로우입니다. JSON 설정 파일 기반으로 동작하며, 실행 산출물은 `Manual/runs/<run_id>/` 하위에 체계적으로 저장됩니다.

## 빠른 시작 (Quick Start)

설정 템플릿을 복사하여 프로젝트에 맞게 수정합니다:

```text
Manual/config/new_dataset_config.example.json
```

필수 설정 항목:

- `train_path`: 학습 데이터 파일 경로
- `target_col`: 타깃 컬럼명
- `task_type`: 작업 유형 (`regression` 또는 `classification`)

스모크(Smoke) 테스트 파이프라인 실행:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\new_dataset_config.example.json `
  -RunId smoke `
  -TuningTrials 1 `
  -MaxFolds 1 `
  -ExplainModels none
```

## 단계별 흐름 (Stage Flow)

| 단계 | 역할 및 목적 |
|---|---|
| 00P | (선택) 원시 CSV/Excel 데이터 수집 및 정규화 |
| 00 | 데이터셋 구조 검토 및 컬럼 정의서 생성 |
| 00D | 도메인 질문지 및 축약형 컨텍스트 팩 생성 |
| 01 | 실행 환경 및 입력 파일 유효성 검증 |
| 02 | 프로파일링, 결측치, 이상치 및 타깃 분포 진단 |
| 02H | 가설 제안 체크포인트 |
| 03 | 피처 엔지니어링 및 가공 피처 생성 |
| 04 | 교차 검증(Validation) 분할 |
| 05 | 모델 학습 및 하이퍼파라미터 튜닝 |
| 05H | 가설 평가 및 검증 |
| 06 | 제출(Submission) 또는 홀드아웃 예측 파일 생성 |
| 07 | 최종 보고서(PDF/Markdown) 작성 |

## 에이전트 작업 지침

`Manual/AGENTS.md`를 먼저 확인하세요. 긴 생성 보고서를 열람하기 전에 축약형 JSON 컨텍스트 팩과 단계별 페이로드를 우선적으로 확인합니다.

## 런타임 정책

`Manual/runs/`, `Manual/state/`, 원본 데이터셋, 모델 아티팩트 및 개인 설정 파일은 Git에 커밋하지 않습니다.
