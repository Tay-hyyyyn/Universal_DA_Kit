from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import run_profiler_diagnoser


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose missing values and outliers from a Manual config.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_profiler_diagnoser(args.config, args.run_id)


if __name__ == "__main__":
    main()
