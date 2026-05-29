---
name: manual-02-profiler-diagnoser
description: 결측, 이상치, train/test 차이, 타깃 분포 형태, 도메인 질문을 진단하고 처리 가설을 남깁니다.
---

# Manual 02 프로파일러·진단기

## 사용 목적

결측과 이상치를 단순 삭제 대상으로 보지 않고 원인 가설, 처리 방식, 모델링 영향으로 나눠 정리한다. 회귀 타깃의 형태를 함께 진단해 `log1p`가 모델 단계 후보인지 여부를 이 단계에서 flag한다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-02-profiler-diagnoser\scripts\diagnose_data.py --config <config_path> --run-id <run_id>
```

## 주요 산출물

- `Manual/runs/<run_id>/reports/diagnosis_report.md`
- `Manual/runs/<run_id>/reports/missing_reason_hypotheses.csv`
- `Manual/runs/<run_id>/reports/feature_drift_summary.csv`
- `Manual/runs/<run_id>/reports/target_outlier_summary.json`
- `Manual/runs/<run_id>/reports/domain_insight_questions.md`

## 점검 포인트

- 결측률, 결측 indicator와 타깃 shift를 함께 본다. train/test shift 점검 시 표면적인 분포 외에도 **Kolmogorov-Smirnov (K-S) Test**를 통해 두 분포 간 수학적 동질성을 검증하고, 그룹별 타깃 차이는 **ANOVA** 등 통계적 유의성 검정을 실시한다.
- 이상치는 제거 전에 자연 발생 가능성과 비즈니스 의미를 먼저 기록한다.
- 상수열/저분산 컬럼과 train/test 분포 드리프트 후보를 따로 요약해, 해석이 불안정한 컬럼을 조기에 분리한다.
- target 변환은 모델 단계 기본값이 아니다. 타깃이 0 이상이고 왜도 또는 p99/median 비율이 클 때만 `log1p`를 후보로 추천한다.
- `target_outlier_summary.json`의 `target_transform_screening.recommend_log1p_candidate`가 모델 단계의 raw/log 비교 여부를 결정한다.
- 사용자의 도메인 판단이 필요한 항목은 질문 목록으로 분리한다.
