# Cursor / IDE Agent Rules for Manual Data Analysis

Paste these rules into the workspace rules for Cursor, Copilot Workspace, or similar IDE agents.

- Treat `Manual/` as the reusable tabular ML pipeline and keep project-specific examples outside shared plugin code.
- Read `Manual/agent_manifest.json` before editing pipeline files.
- Keep all project-specific settings in config JSON files.
- Prefer small, explicit edits to plugin scripts; update README/skill/report docs when behavior changes.
- Run smoke commands before full runs.
- Read Stage 00 `dataset_review.md` before feature/model changes; preserve the data-based simulation narrative, manufacturing/process questions, engineering questions, analyst-background prompts, and initial hypothesis-to-feature candidates.
- Never report a model score without metric name, fold scope, validation rows, target transform, and feature count.
- Target transformation is decided by EDA/profiling; compare raw and `log1p` only when stage 02 flags it, and restore log predictions before submission.
- If adding a feature, document hypothesis, formula, leakage risk, validation result, and decision.
- If creating a final report, write it as an independent reader-facing document rather than a transcript of internal experiments.
