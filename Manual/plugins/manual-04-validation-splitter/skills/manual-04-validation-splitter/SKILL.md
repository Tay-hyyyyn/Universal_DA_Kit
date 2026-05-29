---
name: manual-04-validation-splitter
description: sample fold와 full fold를 만들고 group/time 누수 위험을 관리합니다.
---

# Manual 04 검증 분할기

## 사용 목적

빠른 실험용 sample fold와 최종 판단용 full fold를 분리해, 점수 해석에서 샘플/전체 혼동을 막는다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-04-validation-splitter\scripts\make_folds.py --config <config_path> --run-id <run_id>
```

## 주요 산출물

- `Manual/runs/<run_id>/data/folds/sample15_group_kfold.csv`
- `Manual/runs/<run_id>/data/folds/full_group_kfold.csv`
- `Manual/runs/<run_id>/reports/sample15_fold_report.md`

## 점검 포인트

- group 컬럼이 있으면 row split보다 group split을 우선한다.
- time/order 컬럼이 있으면 미래 정보 누수 가능성을 별도 점검한다.
- 모델 점수를 말할 때 fold 파일명, 행 수, seed를 함께 남긴다.
