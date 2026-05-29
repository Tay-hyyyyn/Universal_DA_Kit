# Claude Code Instructions for Manual Data Analysis

Use this project as a config-driven tabular data analysis workflow.

## Required Context

- `Manual/agent_manifest.json`
- `Manual/README.md`
- `Manual/AGENT_USAGE_GUIDELINES.md`
- Relevant plugin `SKILL.md` under `Manual/plugins/<plugin>/skills/`

## Workflow

1. Create or verify a config copied from `Manual/config/analysis_config.template.json`.
2. Run smoke first with `-TuningTrials 1 -MaxFolds 1 -ExplainModels none`.
3. Read `dataset_review.md` first and list the simulation narrative, manufacturing/process questions, engineering questions, and analyst-background prompts that need user confirmation.
4. Read later stage reports before changing later-stage behavior.
5. Ask the user before full training, package installation, destructive cleanup, or final submission replacement.
6. Keep final reports independent: explain the final model without relying on internal experiment nicknames.

## Guardrails

- No row random split when a meaningful `group_col` exists.
- No direct use of target or direct group identifiers as leakage-prone model features.
- Do not compare raw/log1p as a default modeling rule. Let stage 02 EDA flag whether log1p is a candidate; no log-scale submission values if log models are used.
- Do not skip the Stage 00 domain insight loop. Use analyst background as questions and hypotheses, not as proof.
- No model recommendation without fold scope, metric, target transform, feature count, and output path.
