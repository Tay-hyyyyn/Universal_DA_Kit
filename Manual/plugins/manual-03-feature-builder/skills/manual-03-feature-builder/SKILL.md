---
name: manual-03-feature-builder
description: 결측·이상치 진단과 사용자 선택을 바탕으로 범용 표 형식 피처셋과 feature manifest를 생성합니다.
---

# Manual 03 피처 생성기

## 사용 목적

진단 결과를 받아 결측 처리, 인코딩, 기본 파생 피처, 도메인 후보 피처를 만들고 재현 가능한 manifest를 남긴다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-03-feature-builder\scripts\build_features.py --config <config_path> --run-id <run_id>
```

## 주요 산출물

- `Manual/runs/<run_id>/data/processed/train_features.parquet`
- `Manual/runs/<run_id>/data/processed/test_features.parquet`
- `Manual/runs/<run_id>/data/processed/feature_manifest.json`
- `Manual/runs/<run_id>/reports/feature_build_report.md`

## 점검 포인트

- 새 피처는 `가설 → 공식 → 누수 위험 → 검증 방법`을 함께 기록한다.
- 도메인 피처는 프로젝트 컬럼명에 종속되지 않게 config 기반으로 일반화한다.
- 피처 추가 후에는 baseline 대비 점수, 중요도, train/test shift, fold 안정성을 확인한다.
- 컬럼 단위 결측 indicator 외에 행 단위 결측 프로파일(`row_missing_count`, `row_missing_fraction`)도 우선 후보로 점검한다.

## Generic Feature Design Patterns

다른 표 형식 프로젝트에서도 다음 메커니즘을 우선 검토한다.

- 그룹 내부 순서가 있으면 lag/rolling/expanding/onset/phase 피처를 만든다.
- 구조 컬럼이 있으면 density, capacity, distance, access proxy로 변환한다.
- 비율 컬럼은 실제 물량 또는 처리 capacity와 결합해 규모 정보를 보완한다.
- 결측은 단순 대체값뿐 아니라 `is_missing`, row 결측률, 후반부/세그먼트 결측 interaction으로 기록한다.
- feature manifest에는 가능하면 `hypothesis_source`, `mechanism`, `formula`, `validation_status`를 남긴다.

피처가 특정 대회에서 좋아 보여도, Manual에서는 컬럼명을 직접 하드코딩하지 말고 config의 `domain_context`, `group_col`, `time_col`, metadata 설정을 통해 일반화한다.
