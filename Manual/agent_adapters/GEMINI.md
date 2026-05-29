# Gemini CLI Instructions for Manual Data Analysis

This workspace uses `Manual/` as a reusable tabular supervised learning pipeline.

## Start Here

Read:

1. `Manual/agent_manifest.json`
2. `Manual/README.md`
3. `Manual/AGENT_USAGE_GUIDELINES.md`

Then inspect the config and the relevant plugin skill file.

## Execution Pattern

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 -Config Manual\config\<project_config>.json -RunId smoke -TuningTrials 1 -MaxFolds 1 -ExplainModels none
```

Use full train only after confirming smoke outputs and user intent.

After Stage 00, read `dataset_review.md` and explicitly surface:

- the data-based simulation narrative,
- manufacturing/process questions,
- engineering questions,
- analyst-background prompts,
- initial hypothesis-to-feature candidates.

Use these prompts to collect domain insight before changing feature or model behavior.

## Reporting Rules

- Always state whether the metric is sample, full OOF, holdout, or submission-only.
- Always state the EDA target-transform recommendation, the actual target mode used, and whether predictions were restored to raw units.
- Include feature lineage and overfitting controls in final summaries.
- Keep project-specific insights out of Manual plugin code unless generalized through config.
