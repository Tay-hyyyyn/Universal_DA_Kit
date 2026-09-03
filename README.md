# Universal DA Kit

**Universal DA Kit**은 정형 데이터의 회귀(Regression) 및 분류(Classification) 문제를 위한 재사용 가능하고 설정 기반(Config-driven)의 데이터 분석 워크플로우 패키지입니다. 원본 데이터셋을 훼손하지 않으면서, 원시 데이터 수집부터 탐색적 데이터 분석(EDA), 가설 검증, 모델 학습 및 튜닝, 제출/홀드아웃 파일 생성, 최종 통합 보고서 작성까지 전 과정을 체계적으로 수행할 수 있도록 지원합니다.

실무 데이터 분석 작업에 최적화되어 있습니다. 일상적인 EDA는 가볍고 신속하게 진행할 수 있으며, 다단계 모델링 과정에서는 분석가의 의사결정, 검증 범위, 생성된 아티팩트의 추적 가능성을 명확하게 유지합니다.

---

## 주요 기능

- **원본 데이터 보호 및 전처리**: 분석 전 원시 CSV/Excel 파일의 정규화(선택적)를 지원하며, 원본 데이터셋 불변 원칙을 철저히 준수합니다.
- **종합적인 데이터 진단**: 스키마, 타깃 분포, 결측치, 이상치, 피처 드리프트(Feature Drift) 및 도메인 질문을 체계적으로 검토합니다.
- **재사용 가능한 피처 엔지니어링**: 유효한 시간 열(Time column)이 설정된 경우에만 시간 인식 피처를 생성하는 등 데이터 누수(Data Leakage)를 방지하는 안전한 피처를 구성합니다.
- **견고한 교차 검증 전략**: 데이터 특성에 맞춰 자동(Auto), 시계열(Temporal), 그룹(Grouped), 표준 K-Fold 교차 검증 분할을 적용합니다.
- **모델 튜닝 및 학습**: 회귀 및 분류 작업을 위한 정형 데이터 모델을 최적화하고 OOF(Out-of-Fold) 평가 지표를 기록합니다.
- **제출 파일 및 통합 보고서 생성**: 테스트셋에 맞춘 제출 파일과 마크다운 및 PDF 형태의 단계별·최종 통합 분석 보고서를 생성합니다.
- **보안 및 자산 관리**: 원본 데이터, 테스트셋 레이블, 런타임 결과물, 학습된 모델 바이너리가 Git에 실수로 커밋되지 않도록 안전하게 보호합니다.

---

## 파이프라인 워크플로우

| 단계 (Stage) | 역할 및 목적 |
| --- | --- |
| **00P** | (선택 사항) 원시 CSV/Excel 데이터 수집 및 표준화 |
| **00** | 데이터셋 구조 검토 및 컬럼 정의서(Column Dictionary) 생성 |
| **00D / 02H** | 도메인 지식 질문 및 분석 가설 설정 체크포인트 |
| **01–02** | 실행 환경 점검, 프로파일링 및 데이터 진단(결측치/이상치 분석) |
| **03–04** | 피처 엔지니어링 및 교차 검증 분할(Validation Split) |
| **05** | 모델 학습, 하이퍼파라미터 튜닝 및 OOF 평가 |
| **05H–07** | 가설 검증, 최종 제출물(Submission) 생성 및 종합 보고서 작성 |

파이프라인 실행 시 `-AutoProceed` 플래그를 전달하지 않으면 도메인 및 가설 체크포인트에서 자동으로 일시 정지합니다. 이를 통해 단순 분석 작업에는 부담을 주지 않으면서도, 모델링의 핵심 의사결정을 분석가가 직접 확인하고 제어할 수 있습니다.

---

## 저장소 구조

```text
Universal_DA_Kit/
├── Manual/
│   ├── config/                 # 데이터셋 설정 템플릿
│   ├── plugins/                # 단계별(Stage 00~07) 분석 도구
│   ├── run_manual_pipeline.ps1 # 파이프라인 통합 실행 스크립트
│   └── runs/<run_id>/          # 로컬 실행 결과물 (Git 추적 제외)
├── docs/                       # 워크플로우 및 에이전트 가이드 문서
├── examples/                   # 예제용 합성(Synthetic) 데이터셋
├── sample/                     # 샘플 입력 보조 도구
└── tests/                      # 패키지 및 데이터 검증 테스트 코드
```

---

## 빠른 시작 (Quick Start)

### 1. 가상환경 구성 및 의존성 설치

Python 3.10 이상을 권장합니다. 가상환경을 생성 및 활성화한 후 패키지 의존성을 설치합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

### 2. 데이터셋 설정(Config) 파일 생성

`Manual/config/new_dataset_config.example.json`을 복사하여 프로젝트 설정 파일을 생성하고, 최소한 아래 필수 항목들을 지정합니다:

- `train_path`: 학습 데이터 파일 경로
- `target_col`: 예측 대상 타깃 컬럼명
- `task_type`: 작업 유형 (`regression` 또는 `classification`)

필요한 경우 `id_col`(식별자), `group_col`(그룹 검증용), `time_col`(시계열 분할용), `test_path`, `sample_submission_path`를 추가로 설정합니다. `test_usage_mode`는 최종 평가 전까지 보수적인 기본값을 유지하는 것을 권장합니다.

### 3. 스모크(Smoke) 테스트 실행

파이프라인이 정상 동작하는지 작은 규모로 빠르게 확인합니다:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\<project_config>.json `
  -RunId smoke `
  -AutoProceed `
  -TuningTrials 1 `
  -MaxFolds 1 `
  -ExplainModels none `
  -NoPdfReport
```

대규모 학습을 실행하기 전에 `Manual/runs/smoke/`에 생성된 결과 파일을 확인하세요.

### 4. 체크포인트 기반 워크플로우 실행

도메인 지식 및 분석 가설을 점검하며 신중하게 진행하려면 `-AutoProceed` 옵션을 제외하고 실행합니다. 체크포인트 안내에 따라 응답을 작성한 후 동일한 실행 ID로 재개할 수 있습니다:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\<project_config>.json `
  -RunId <run_id> `
  -Resume
```

전체 폴드 및 데이터에 대한 정밀 학습(`-FullTrain`)은 스모크 테스트와 검증 설계가 확정된 이후에 사용하는 것을 권장합니다.

---

## 실행 산출물 (Outputs)

모든 파이프라인 실행 결과물은 `Manual/runs/<run_id>/` 경로에 체계적으로 저장됩니다:

- `reports/`: 데이터 검토서, 데이터 진단서, 가설/체크포인트 문서, 최종 통합 보고서
- `data/processed/`: 정규화 및 피처 엔지니어링이 완료된 데이터셋
- `data/folds/`: 검증 폴드 분할 인덱스 및 분할 요약 보고서
- `artifacts/models/`: 평가 지표(Metrics), 튜닝 결과, 예측치(OOF/Test), 모델 레지스트리
- `submissions/`: 최종 제출용(또는 홀드아웃 검증용) 예측 결과 파일

> 원본 데이터셋, 생성된 런타임 파일, 학습된 모델 바이너리는 보안 및 저장소 경량화를 위해 Git 커밋 대상에서 자동으로 제외됩니다.

---

## AI 에이전트 작업 가이드

`AGENTS.md` 및 `CLAUDE.md`는 작업 유형별 참조 문서를 신속하게 파악할 수 있도록 돕는 라우팅 맵을 제공합니다:

- **L0 / L1 (단순 EDA 및 차트 수정)**: 별도의 장황한 작업 계획 없이 즉시 가볍게 실행하고 결과를 확인합니다.
- **L2 (다중 파일 모델링 및 구조 개편)**: 간결한 작업 계획 수립과 검증 절차를 선행합니다.
- **L3 (고위험 작업 - 원본 데이터/DB 변경)**: 사용자 승인 및 롤백 방안을 사전에 확보합니다.

자세한 프로젝트 시작 및 체크포인트 가이드는 `Manual/README.md` 및 `Manual/PROJECT_START_GUIDE.md`를 참조하세요.

---

## 유효성 검증 (Validation)

프로젝트 테스트 스위트를 실행하여 정상 동작 여부를 검증합니다:

```powershell
python -m unittest discover -s tests -v
```

환경에 `pytest`가 설치되어 있는 경우 아래 명령어로도 실행할 수 있습니다:

```powershell
pytest tests/
```
