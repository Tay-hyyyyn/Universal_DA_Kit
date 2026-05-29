---
name: manual-06-submission-maker
description: sample submission 정렬을 보존하고 앙상블·후처리 선택을 기록하며 제출 파일을 생성합니다.
---

# Manual 06 제출 생성기

## 사용 목적

모델 예측을 sample submission 형식에 맞춰 정렬하고, ensemble/clip/postprocess 선택을 재현 가능하게 남긴다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-06-submission-maker\scripts\make_submission.py --config <config_path> --run-id <run_id> --ensemble-method best
```

## 주요 산출물

- `Manual/runs/<run_id>/submissions/submission.csv`
- `Manual/runs/<run_id>/reports/submission_report.md`
- `Manual/runs/<run_id>/submissions/postprocess_choices.json`

## 점검 포인트

- 예측 단위가 raw인지 log 복원값인지 반드시 확인한다.
- ID 순서와 제출 컬럼명이 sample submission과 일치하는지 점검한다.
- 제출 후보가 여러 개면 모델, 피처셋, fold, 점수, 후처리 설정을 인덱스로 남긴다.
