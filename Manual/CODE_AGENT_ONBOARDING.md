# Code Agent Onboarding

`Manual/` is a reusable 0-7 stage workflow for tabular supervised-learning projects. It is config-driven and should stay independent from any single dataset, domain, contest, or client project.

## Start

1. Read `Manual/AGENTS.md`.
2. Read `Manual/config/new_dataset_config.example.json`.
3. Check `Manual/CONTEXT_MINIMIZATION_GUIDE.md` before opening long generated reports.
4. Use `Manual/runs/<run_id>/run_state.json` and compact context packs for resume work.

## Guardrails

- Keep project-specific columns in config or run artifacts, not in reusable plugin code.
- Do not use held-out test data for model selection unless the user explicitly allows it.
- Do not commit runtime outputs, raw data, model artifacts, or local state.
- Keep `AGENTS.md` and `CLAUDE.md` aligned.
