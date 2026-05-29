from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import load_config, run_paths  # type: ignore  # noqa: E402
from manual_raw_intake import run_raw_intake  # type: ignore  # noqa: E402
from manual_state import refresh_run_state  # type: ignore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual optional raw CSV/Excel intake stage.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    profile = run_raw_intake(cfg, paths)
    refresh_run_state(cfg, args.run_id)
    print(f"[ok] Raw intake completed: header_row={profile['selected_table']['header_row']} -> {paths['processed'] / 'normalized_train.csv'}")


if __name__ == "__main__":
    main()
