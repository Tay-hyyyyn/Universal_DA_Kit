from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from manual_common import load_config, run_paths  # type: ignore  # noqa: E402
from manual_state import read_json, refresh_run_state  # type: ignore  # noqa: E402


def active_pointer(project_root: str) -> dict:
    return read_json(Path(project_root).resolve() / "state" / "active_run.json", {})


def resolve_inputs(config: str | None, run_id: str | None, project_root: str | None) -> tuple[str, str]:
    if config and run_id:
        return config, run_id
    if project_root:
        pointer = active_pointer(project_root)
        if pointer.get("config_path") and pointer.get("active_run_id"):
            return str(pointer["config_path"]), str(pointer["active_run_id"])
    raise ValueError("Use --config and --run-id, or pass --project-root to reuse state/active_run.json.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual run 상태를 갱신하고 다음 명령 1개를 추천합니다.")
    parser.add_argument("--config", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--project-root", default="")
    args = parser.parse_args()

    config_path, run_id = resolve_inputs(args.config or None, args.run_id or None, args.project_root or None)
    cfg = load_config(config_path)
    paths = run_paths(cfg, run_id)

    # If a domain checkpoint is pending, guide the user first (before suggesting the next command).
    pending_md = paths["reports"] / "pending_checkpoint.md"
    if pending_md.exists():
        print(pending_md.read_text(encoding="utf-8").strip())
        return
    pending_hypothesis_md = paths["reports"] / "pending_hypothesis_checkpoint.md"
    if pending_hypothesis_md.exists():
        print(pending_hypothesis_md.read_text(encoding="utf-8").strip())
        return

    state = refresh_run_state(cfg, run_id)
    print(f"현재 run: {run_id}")
    print(f"완료 단계: {', '.join(state['stages_completed']) or '없음'}")
    print(f"다음 추천 단계: {state['recommended_next_stage'] or '없음'}")
    print(f"다음 추천 명령: {state['recommended_next_command']}")


if __name__ == "__main__":
    main()
