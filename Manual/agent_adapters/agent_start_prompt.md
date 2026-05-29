# Start Prompt for Another Code Agent

You are working in a repository that contains `Manual/`, a reusable config-driven tabular data analysis workflow.

Before changing files:

1. Read `Manual/agent_manifest.json`.
2. If this is a continuing run, read `state/active_run.json`, `runs/<run_id>/summary.json`, and `runs/<run_id>/progress.md` first.
3. Read only the stage payload or stage artifact you actually need.
4. Read `Manual/CONTEXT_MINIMIZATION_GUIDE.md`.
5. Read `Manual/README.md` only when the project is new or the run structure is unclear.
6. Inspect the project config copied from `Manual/config/analysis_config.template.json`.

Your job is to run or improve the Manual data analysis workflow safely.

Rules:

- Keep Manual generic; do not hardcode project-specific column names into Manual plugins.
- Minimize context: prefer `summary.json`, `run_state.json`, and `stage_*_report_payload.json` over full markdown reports when possible.
- Use smoke runs before full train runs.
- Read Stage 00 `dataset_review.md` before changing feature/model behavior. Summarize the data-based simulation narrative, manufacturing/process questions, engineering questions, analyst-background prompts, and initial hypothesis-to-feature candidates that need user confirmation.
- If `group_col` exists, prefer group-aware validation.
- Treat target transformation as an EDA/profiler decision. Compare raw and `log1p` only when stage 02 flags it or I explicitly ask for it; restore log predictions with `expm1` before submission.
- Record feature lineage: hypothesis, formula, leakage risk, validation result, decision.
- Record model tuning: trial count, fold count, best parameters, metric, train-valid gap.
- Validate submissions: ID order, required columns, null predictions, negative values, output units.
- Final reports must be understandable to someone who does not know the internal experiment history.

When summarizing work, include:

- Files changed.
- Commands run and results.
- Key metrics with fold scope.
- Remaining risks or decisions for the user.
