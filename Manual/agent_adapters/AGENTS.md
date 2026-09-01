# Agent Instructions for Manual Data Analysis

Scope: this file applies to the project where it is copied. It is designed for Codex/OpenAI-style code agents.

## Read First

1. Read `Manual/agent_manifest.json`.
2. Read `Manual/README.md`.
3. Read `Manual/CODE_AGENT_ONBOARDING.md` and `Manual/CONTEXT_MINIMIZATION_GUIDE.md` when the task spans multiple stages or resumes a run.
4. If working on a specific stage, read that plugin's `skills/<plugin>/SKILL.md`.

## Operating Rules

- Keep `Manual/` generic; do not hardcode project-specific column names into Manual plugins.
- Use config files for project-specific paths, target, ID, group, time, and metadata choices.
- Run a smoke pipeline before full training.
- Do not treat smoke/sample metrics as final performance.
- If `group_col` exists, use group-aware validation.
- Target transformation is an EDA decision. Compare raw and `log1p` only when stage 02 flags it or the user explicitly requests it; restore log predictions with `expm1` before submission.
- Stage 00 `dataset_review.md` must include a data-based simulation narrative, manufacturing/process questions, engineering questions, analyst-background prompts, and initial hypothesis-to-feature candidates.
- After Stage 00, summarize what the user should confirm from their domain experience before changing feature/model behavior.
- Record feature lineage and user decisions in reports and run artifacts.

## Standard Smoke Command

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 -Config Manual\config\<project_config>.json -RunId smoke -TuningTrials 1 -MaxFolds 1 -ExplainModels none
```

## Completion Checklist

- Config fields verified.
- Stage outputs exist.
- Metrics and tuning results are from the intended fold scope.
- Submission, if created, has correct ID order and no null predictions.
- Final report explains data, features, validation, model tuning, overfitting controls, and output units.
