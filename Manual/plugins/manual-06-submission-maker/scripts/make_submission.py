from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import run_submission_maker


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Manual prediction/submission output.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ensemble-method", default="weighted", choices=["weighted", "simple", "best", "manual"])
    parser.add_argument("--manual-weights", default="")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--clip-negative", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--upper-clip", default="auto")
    args = parser.parse_args()
    run_submission_maker(
        args.config,
        args.run_id,
        ensemble_method=args.ensemble_method,
        manual_weights=args.manual_weights,
        interactive=args.interactive,
        clip_negative=args.clip_negative,
        upper_clip=args.upper_clip,
    )


if __name__ == "__main__":
    main()
