from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import run_validation_splitter


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Manual validation folds.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sample-frac", type=float, default=0.15)
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--full-train", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    run_validation_splitter(
        args.config,
        args.run_id,
        sample_frac=args.sample_frac,
        n_splits=args.n_splits,
        seed=args.seed,
        full_train=args.full_train,
        interactive=args.interactive,
    )


if __name__ == "__main__":
    main()
