---
name: manual-00-data-reviewer
description: 범용 표 형식 데이터분석의 시작 단계에서 데이터 구조, 타깃, 컬럼 의미, 도메인 인사이트 질문, 초기 EDA 질문을 정리합니다.
---

# Manual 00 데이터 리뷰어

## 사용 목적

새 데이터셋을 받았을 때 “무엇을 예측하는 데이터인지, 어떤 컬럼군이 있고, 어떤 업무/공정 상황일 수 있으며, 사용자의 경험을 어떤 질문과 가설로 끌어내야 하는지”를 먼저 정리한다.

이 단계의 보고서는 단순 EDA 요약이 아니라 1차 기본 보고서다. 데이터 기반 가상 시뮬레이션, 제조업·공정 질문, 기계공학 질문, 사용자 경험 활용 질문, 초기 가설과 피처 후보를 함께 제공한다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-00-data-reviewer\scripts\review_data.py --config Manual\config\analysis_config.template.json --run-id <run_id>
```

## 주요 산출물

- `Manual/runs/<run_id>/reports/dataset_review.md`
- `Manual/runs/<run_id>/reports/column_dictionary.csv`
- `Manual/runs/<run_id>/reports/data_overview.json`

## 점검 포인트

- `target_col`, `task_type`, `id_col`, `group_col`, `time_col` 후보를 확인한다.
- 컬럼명 기반 도메인 추정은 가설로만 기록하고, 사용자의 도메인 입력이 필요한 질문을 남긴다.
- 데이터 기반 가상 시뮬레이션은 실제 사실로 단정하지 않고, 컬럼명과 타깃을 근거로 한 “가설적 해석”임을 명시한다.
- 제조업/공정 관점에서는 병목, 처리량, WIP, capacity, 품질, 설비 제약 질문을 남긴다.
- 기계공학 관점에서는 열전달, 냉각부하, 마찰/마모, 진동, 모터·배터리 부하, 유동/압력, 제어응답 질문을 남긴다.
- 사용자의 전공, 실무 경험, 관심사를 EDA와 피처 후보로 연결한다.
- 다음 단계가 바로 결측·이상치 진단으로 이어지도록 컬럼군과 데이터 범위를 명확히 적는다.
