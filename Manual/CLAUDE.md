# Manual Agent Map

## Purpose

`Manual` is the reusable staged tabular data-analysis workflow. It owns workflow plugins, configs, tests, and run outputs. Actual project outputs belong under `runs/<run_id>` and should not become default context.

## Stage Routing

| Work | First map or script |
|---|---|
| Raw CSV/Excel intake | `plugins/manual-00-raw-intake/` |
| Dataset review | `plugins/manual-00-data-reviewer/` |
| Environment/input check | `plugins/manual-01-env-checker/` |
| Profiling and diagnosis | `plugins/manual-02-profiler-diagnoser/` |
| Domain checkpoint | `plugins/manual-domain-expert/` |
| Hypothesis planning | `plugins/manual-hypothesis-planner/` |
| Feature building | `plugins/manual-03-feature-builder/` |
| Validation split | `plugins/manual-04-validation-splitter/` |
| Model training | `plugins/manual-05-model-trainer/` |
| Submission/holdout output | `plugins/manual-06-submission-maker/` |
| Final reporting | `plugins/manual-07-report-writer/` |

## Resume Order

1. `state/active_run.json`
2. `runs/<run_id>/run_state.json`
3. `runs/<run_id>/artifact_index.json`
4. `runs/<run_id>/reports/stage_<stage>_report_payload.json`
5. `runs/<run_id>/reports/domain_context_pack.json`
6. `runs/<run_id>/reports/hypothesis_context_pack.json`

## Status Rules

- Domain and hypothesis statuses are `open`, `answered`, `accepted`, or `deferred`.
- Do not introduce `closed`.
- Filled but still-open answers can be normalized with `tools/update_manual_status.ps1`.
- Low-confidence or starter-only answers are hypotheses, not hard filtering rules.

## Do Not Do

- Do not read every archived report before routine work.
- Do not use test-set outcomes for feature selection or model selection.
- Do not publish `runs/`, generated data, or model artifacts.
- Do not edit only one of `AGENTS.md` and `CLAUDE.md`.
