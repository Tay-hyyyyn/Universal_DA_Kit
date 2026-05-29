---
name: manual-next-guide
description: 현재 run의 산출물과 상태 파일을 읽어 다음 명령 1개를 추천합니다.
---

# Manual Next Guide

## 사용 목적

`run_state.json`, `summary.json`, `progress.md`를 갱신하고, 현재 run에서 다음에 실행할 명령 1개를 짧게 추천한다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-next-guide\scripts\next_guide.py --config <config_path> --run-id <run_id>
```

활성 run 포인터를 재사용할 때:

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-next-guide\scripts\next_guide.py --project-root <analysis_root>
```

## 최소 컨텍스트 규칙

- 전체 README를 매번 다시 읽기보다, 먼저 `state/active_run.json`과 `runs/<run_id>/summary.json`을 확인한다.
- 다음 작업이 특정 stage 하나라면 그 stage의 payload와 산출물만 읽는다.
- 추천은 항상 명령 1개만 제시한다.

## 주요 산출물

- `state/active_run.json`
- `runs/<run_id>/run_state.json`
- `runs/<run_id>/summary.json`
- `runs/<run_id>/progress.md`
