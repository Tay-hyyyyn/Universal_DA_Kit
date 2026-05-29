# manual-00-raw-intake

Use this optional plugin before Stage 00 when the dataset is not already clean tabular data.

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-00-raw-intake\scripts\raw_intake.py --config <config_path> --run-id <run_id>
```

## Outputs

- `reports/raw_file_profile.json`
- `reports/table_detection_report.md`
- `reports/cleaning_plan.md`
- `reports/column_metadata.csv`
- `reports/column_semantics_candidates.csv`
- `reports/domain_evidence_cards.json`
- `data/processed/normalized_train.csv`

The normalized file is an intake artifact. Update the run config `train_path` only after the detected table and cleaning plan are reviewed.
