# 유니버설 DA 키트

유니버설 DA 키트는 범용 설정 기반 테이블 형식 데이터 분석 워크플로 패키지입니다. `Manual` 워크플로를 기반으로 구축되었으며, 단일 프로젝트 데이터셋이 아닌 재사용 가능한 회귀/분류 프로젝트를 위해 설계되었습니다.

## 이 패키지가 제공하는 기능

- 데이터 수집부터 최종 보고서 작성까지 단계별 데이터 분석
- 설정 기반 대상, 작업 유형, ID, 그룹 및 시간 열 선택
- 데이터 검토, 프로파일링, 진단, 특징 구축, 검증 분할, 모델 학습, 제출/출력 및 보고서 작성 단계
- 토큰 효율적인 작업을 위한 에이전트 맵(`AGENTS.md` 및 `CLAUDE.md`)
- 사용자의 결정을 간결하고 추적 가능하게 유지하는 도메인 및 가설 체크포인트 파일

## 저장소 구조

```text
Universal_DA_Kit/
+-- Manual/
| +-- AGENTS.md
| +-- CLAUDE.md
| +-- config/
| +-- plugins/
| +-- run_manual_pipeline.ps1
+-- docs/
| +-- agent/
+-- examples/
+-- tests/
```

## 빠른 시작

1. `Manual/config/new_dataset_config.example.json` 파일을 복사합니다.

2. `train_path`, `target_col`, `task_type`을 설정합니다.

3. 파이프라인 실행:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
-Config Manual\config\new_dataset_config.example.json `
-RunId demo_run `
-TuningTrials 1 `
-MaxFolds 1 `

-ExplainModels none
```

런타임 출력은 `Manual/runs/<run_id>/` 폴더에 저장되며 Git에서는 무시됩니다.

## 에이전트 워크플로

이 저장소에는 핵심적인 "먼저 읽어보세요" 패턴이 포함되어 있습니다.

- `AGENTS.md` 및 `CLAUDE.md`를 통한 간략한 루트/영역 맵,

- `.agents/plugins/marketplace.json`,
- 간결한 컨텍스트 및 스테이지 페이로드 지침,
- 명확한 아카이브/런타임 제외 정책.

공개 패키지는 의도적으로 과거 프로젝트 검토 문서 및 실행 출력을 제외합니다.



# Universal DA Kit

Universal DA Kit is a generic, config-driven tabular data-analysis workflow package. It is built from the `Manual` workflow and is intended for reusable regression/classification projects, not for a single project dataset.

## What This Package Provides

- staged data analysis from intake to final report,
- config-based target, task type, ID, group, and time column selection,
- data review, profiling, diagnosis, feature building, validation split, model training, submission/output, and report writing stages,
- agent maps (`AGENTS.md` and `CLAUDE.md`) for token-efficient work,
- domain and hypothesis checkpoint files that keep user decisions compact and traceable.

## Repository Layout

```text
Universal_DA_Kit/
+-- Manual/
|   +-- AGENTS.md
|   +-- CLAUDE.md
|   +-- config/
|   +-- plugins/
|   +-- run_manual_pipeline.ps1
+-- docs/
|   +-- agent/
+-- examples/
+-- tests/
```

## Quick Start

1. Copy `Manual/config/new_dataset_config.example.json`.
2. Set `train_path`, `target_col`, and `task_type`.
3. Run the pipeline:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\new_dataset_config.example.json `
  -RunId demo_run `
  -TuningTrials 1 `
  -MaxFolds 1 `
  -ExplainModels none
```

Runtime outputs go under `Manual/runs/<run_id>/` and are ignored by Git.

## Agent Workflow

This repo includes the core Must Read It First pattern:

- short root/area maps through `AGENTS.md` and `CLAUDE.md`,
- `.agents/plugins/marketplace.json`,
- compact context and stage payload guidance,
- a clear archive/runtime exclusion policy.

The public package intentionally excludes historical project review documents and run outputs.
