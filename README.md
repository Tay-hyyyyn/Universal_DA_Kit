# Universal DA Kit

Universal DA Kit is a reusable, configuration-driven workflow for tabular regression and classification. It helps a project move from raw-data intake to a validated model, submission or holdout output, and a final report without changing the original dataset.

The kit is designed for practical data-analysis work: routine EDA remains lightweight, while multi-stage modeling keeps its decisions, validation scope, and generated artifacts traceable.

## What it does

- Handles optional raw CSV/Excel normalization before analysis.
- Reviews schema, target, missingness, outliers, feature drift, and domain questions.
- Builds reusable features, including time-aware features only when a valid time column is configured.
- Selects validation folds using automatic, temporal, grouped, or standard strategies as appropriate.
- Trains tuned tabular models for regression or classification and records out-of-fold metrics.
- Creates submission or holdout outputs and an integrated report.
- Protects raw data, test-set boundaries, runtime artifacts, and model files from accidental publication.

## Workflow

| Stage | Purpose |
| --- | --- |
| 00P | Optional raw CSV/Excel intake and normalization |
| 00 | Dataset review and column dictionary |
| 00D / 02H | Domain and hypothesis checkpoints |
| 01–02 | Environment checks, profiling, and diagnosis |
| 03–04 | Feature building and validation split |
| 05 | Model training and evaluation |
| 05H–07 | Hypothesis evaluation, output creation, and final reporting |

The pipeline pauses at domain or hypothesis checkpoints unless `-AutoProceed` is supplied. This keeps important modeling decisions visible without imposing a heavy process on simple work.

## Repository layout

```text
Universal_DA_Kit/
├── Manual/
│   ├── config/                 # Dataset configuration templates
│   ├── plugins/                # Stage-specific analysis tools
│   ├── run_manual_pipeline.ps1 # Pipeline entry point
│   └── runs/<run_id>/          # Local runtime outputs (ignored by Git)
├── docs/                       # Lightweight agent and workflow guidance
├── examples/                   # Synthetic example data
├── sample/                     # Sample input helpers
└── tests/                      # Package and data-validation tests
```

## Quick start

### 1. Install dependencies

Use Python 3.10 or later. Create a virtual environment, activate it, and install the project dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

### 2. Create a dataset configuration

Copy `Manual/config/new_dataset_config.example.json` to a project-specific file, then set at minimum:

- `train_path`
- `target_col`
- `task_type` (`regression` or `classification`)

Set `id_col`, `group_col`, `time_col`, `test_path`, and `sample_submission_path` when they apply. Keep `test_usage_mode` at its conservative default until final evaluation.

### 3. Run a small smoke workflow

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\<project_config>.json `
  -RunId smoke `
  -AutoProceed `
  -TuningTrials 1 `
  -MaxFolds 1 `
  -ExplainModels none `
  -NoPdfReport
```

Review the generated files in `Manual/runs/smoke/` before running a larger job.

### 4. Run the checkpoint-guided workflow

Omit `-AutoProceed` when you want to review domain and hypothesis checkpoints. After responding to a checkpoint, resume the same run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Manual\run_manual_pipeline.ps1 `
  -Config Manual\config\<project_config>.json `
  -RunId <run_id> `
  -Resume
```

Use `-FullTrain` only after the smoke output and validation design are confirmed.

## Outputs

Each run stores its artifacts under `Manual/runs/<run_id>/`:

- `reports/`: dataset review, diagnostics, checkpoints, and final reports
- `data/processed/`: normalized and feature-engineered data
- `data/folds/`: validation folds and split summaries
- `artifacts/models/`: metrics, tuning results, predictions, and model registry
- `submissions/`: submission or holdout prediction files

These files, along with raw datasets and trained model binaries, are deliberately excluded from Git.

## Lightweight agent guidance

`AGENTS.md` and `CLAUDE.md` provide short maps to the relevant area guidance. Small EDA changes do not require a formal plan; multi-file modeling work uses a short plan and focused verification, while high-risk raw-data or external-system changes require approval.

See `Manual/README.md` and `Manual/PROJECT_START_GUIDE.md` for the full project-start and checkpoint workflow.

## Validation

Run the package checks with:

```powershell
python -m unittest discover -s tests -v
```

Run `pytest tests/` when pytest is available in the environment.
