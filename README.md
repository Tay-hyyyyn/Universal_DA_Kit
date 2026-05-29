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
