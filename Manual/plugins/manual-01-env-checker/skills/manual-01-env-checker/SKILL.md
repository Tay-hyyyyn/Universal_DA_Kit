---
name: manual-01-env-checker
description: Manual 분석 run의 입력 파일, 설정값, Python 실행 환경을 점검합니다.
---

# Manual 01 환경 점검기

## 사용 목적

분석을 시작하기 전에 config의 경로와 필수 패키지, train/test/sample submission 파일을 확인해 뒤 단계 실패를 줄인다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-01-env-checker\scripts\check_env.py --config <config_path> --run-id <run_id>
```

## 주요 산출물

- `Manual/runs/<run_id>/reports/env_check.md`
- `Manual/runs/<run_id>/reports/env_check.json`

## 점검 포인트

- 파일이 없거나 schema가 맞지 않으면 모델 단계까지 진행하지 않는다.
- 패키지 설치가 필요하면 사용자 승인 후 진행한다.
- sample submission이 있는 프로젝트는 제출 컬럼과 ID 정렬 기준을 이 단계에서 확인한다.
