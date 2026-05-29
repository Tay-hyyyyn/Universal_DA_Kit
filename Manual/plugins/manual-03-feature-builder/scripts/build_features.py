from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import run_feature_builder


def main() -> None:
    parser = argparse.ArgumentParser(description="Build processed features from a Manual config.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--feature-families", default="auto")
    parser.add_argument("--time-features", default="auto", choices=["auto", "none", "order"])
    parser.add_argument("--apply-correlation-pruning", action="store_true")
    args = parser.parse_args()
    run_feature_builder(
        args.config,
        args.run_id,
        interactive=args.interactive,
        feature_families=args.feature_families,
        time_features=args.time_features,
        apply_correlation_pruning=args.apply_correlation_pruning,
    )


if __name__ == "__main__":
    main()
