# manual-hypothesis-planner

Use this plugin when the Manual run needs to create, ingest, or evaluate explicit data-analysis hypotheses.

## Commands

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-hypothesis-planner\scripts\hypothesis_planner.py propose --config <config_path> --run-id <run_id>
.\.venv\Scripts\python.exe Manual\plugins\manual-hypothesis-planner\scripts\hypothesis_planner.py ingest --config <config_path> --run-id <run_id>
.\.venv\Scripts\python.exe Manual\plugins\manual-hypothesis-planner\scripts\hypothesis_planner.py evaluate --config <config_path> --run-id <run_id>
```

## Outputs

- `reports/hypothesis_seed_report.md`
- `reports/hypothesis_answers.md`
- `reports/hypothesis_context_pack.json`
- `reports/hypothesis_registry.json`
- `reports/hypothesis_validation_plan.csv`
- `reports/hypothesis_validation_results.md`
- `reports/hypothesis_validation_results.json`

The `propose` command pauses with exit code `2` when hypotheses are still `open`.
