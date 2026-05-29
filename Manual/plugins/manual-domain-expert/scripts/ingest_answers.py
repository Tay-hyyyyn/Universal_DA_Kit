from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import load_config, run_paths  # type: ignore  # noqa: E402
from manual_domain_expert import ingest_answers_file  # type: ignore  # noqa: E402
from manual_state import refresh_run_state  # type: ignore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert domain_answers.md into domain_context_pack.json.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--answers", default="", help="Optional path to an answers markdown file. Defaults to reports/domain_answers.md.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = run_paths(cfg, args.run_id)
    pack = ingest_answers_file(cfg, args.run_id, paths, args.answers or None)
    refresh_run_state(cfg, args.run_id)
    summary = pack.get("compact_summary", {})
    print(f"Wrote domain context pack to {paths['reports'] / 'domain_context_pack.json'}")
    print(f"Answered cards: {summary.get('answered_count', 0)}")
    print(f"Low-confidence questions: {summary.get('low_confidence_count', 0)}")


if __name__ == "__main__":
    main()
