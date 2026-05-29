from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import load_config, run_paths  # type: ignore  # noqa: E402
from manual_domain_expert import write_questionnaire_files  # type: ignore  # noqa: E402
from manual_state import refresh_run_state  # type: ignore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Manual domain expert learning question cards.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--overwrite-answers-template", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    write_questionnaire_files(
        cfg,
        args.run_id,
        paths,
        overwrite_answers_template=args.overwrite_answers_template,
    )
    refresh_run_state(cfg, args.run_id)
    print(f"Wrote domain questionnaire to {paths['reports']}")


if __name__ == "__main__":
    main()
