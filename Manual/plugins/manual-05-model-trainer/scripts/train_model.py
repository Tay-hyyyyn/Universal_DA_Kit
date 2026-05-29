from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import run_model_trainer


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Manual tabular models.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--full-train", action="store_true")
    parser.add_argument("--explain-models", default="ridge,surrogate")
    parser.add_argument("--target-mode", default="auto", choices=["auto", "both", "raw", "log1p"])
    parser.add_argument("--tuning-trials", type=int, default=8)
    parser.add_argument("--max-folds", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=1)
    args = parser.parse_args()
    run_model_trainer(
        args.config,
        args.run_id,
        full_train=args.full_train,
        explain_models=args.explain_models,
        target_mode=args.target_mode,
        tuning_trials=args.tuning_trials,
        max_folds=args.max_folds,
        seed=args.seed,
        n_jobs=args.n_jobs,
    )


if __name__ == "__main__":
    main()
