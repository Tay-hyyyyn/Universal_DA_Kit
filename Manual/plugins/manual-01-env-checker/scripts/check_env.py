from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import run_env_check


def main() -> None:
    parser = argparse.ArgumentParser(description="Check configured files and Python packages.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_env_check(args.config, args.run_id)


if __name__ == "__main__":
    main()
