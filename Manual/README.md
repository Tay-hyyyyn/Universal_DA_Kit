# Manual Universal Tabular Analysis Workflow

`Manual/` is a reusable staged workflow for tabular regression and classification projects. It is driven by config files and keeps runtime outputs under `Manual/runs/<run_id>/`.

## Quick Start

Copy and edit:

```text
Manual/config/new_dataset_config.example.json
```

Required fields:

- `train_path`
- `target_col`
- `task_type`

Run a small smoke workflow:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\new_dataset_config.example.json `
  -RunId smoke `
  -TuningTrials 1 `
  -MaxFolds 1 `
  -ExplainModels none
```

## Stage Flow

| Stage | Purpose |
|---|---|
| 00P | Optional raw CSV/Excel intake and normalization |
| 00 | Dataset review and column dictionary |
| 00D | Domain questionnaire and compact context pack |
| 01 | Environment and input validation |
| 02 | Profiling, missingness, outliers, target diagnosis |
| 02H | Hypothesis proposal checkpoint |
| 03 | Feature building |
| 04 | Validation split |
| 05 | Model training |
| 05H | Hypothesis evaluation |
| 06 | Submission or holdout output |
| 07 | Final report writing |

## Agent Guidance

Start with `Manual/AGENTS.md`. Use compact JSON context packs and stage payloads before opening long generated reports.

## Runtime Policy

Do not commit `Manual/runs/`, `Manual/state/`, raw datasets, model artifacts, or private config files.
