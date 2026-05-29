from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


def _as_path(value: str | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)


def resolve_log_path(cfg: dict[str, Any]) -> Path | None:
    raw = cfg.get("log_path")
    if raw:
        path = Path(str(raw))
        if path.is_absolute():
            return path
        return (Path(cfg.get("_project_root", ".")).resolve() / path).resolve()
    output_root = cfg.get("output_root")
    if output_root:
        out = Path(str(output_root))
        if not out.is_absolute():
            out = (Path(cfg.get("_project_root", ".")).resolve() / out).resolve()
        return (out.parent if out.name.lower() == "runs" else out) / "log.md"
    return None


def append_log(
    log_path: str | Path,
    stage: str,
    purpose: str,
    inputs: list[str] | tuple[str, ...],
    outputs: list[str] | tuple[str, ...],
    checkpoint: str = "없음",
    next_step: str = "",
    now: datetime | None = None,
) -> None:
    path = _as_path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = now or datetime.now()
    date_str = current.strftime("%Y-%m-%d")
    time_str = current.strftime("%H:%M:%S")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    lines: list[str] = []
    if not existing.strip():
        lines.append("# 작업 로그")
        lines.append("")
    if f"## {date_str}" not in existing:
        if existing and not existing.endswith("\n"):
            lines.append("")
        lines.append(f"## {date_str}")
        lines.append("")
    lines.append(f"### {time_str} - {stage}")
    lines.append(f"- **목적:** {purpose}")
    lines.append("- **입력:** " + _format_path_list(inputs))
    lines.append("- **산출물:** " + _format_path_list(outputs))
    lines.append(f"- **체크포인트:** {checkpoint}")
    if next_step:
        lines.append(f"- **다음 권장:** {next_step}")
    lines.append("")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))
        if not lines[-1].endswith("\n"):
            handle.write("\n")


def append_manual_log(
    cfg: dict[str, Any],
    stage: str,
    purpose: str,
    inputs: list[str] | tuple[str, ...],
    outputs: list[str] | tuple[str, ...],
    checkpoint: str = "없음",
    next_step: str = "",
) -> None:
    path = resolve_log_path(cfg)
    if not path:
        return
    append_log(path, stage, purpose, [str(item) for item in inputs], [str(item) for item in outputs], checkpoint, next_step)


def parse_log_entries(log_path: str | Path) -> list[dict[str, str]]:
    path = _as_path(log_path)
    if not path.exists():
        return []
    entries: list[dict[str, str]] = []
    current_date = ""
    current: dict[str, str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        date_match = re.match(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", line)
        if date_match:
            current_date = date_match.group(1)
            continue
        entry_match = re.match(r"^###\s+(\d{2}:\d{2}:\d{2})\s+-\s+(.+?)\s*$", line)
        if entry_match:
            current = {"date": current_date, "time": entry_match.group(1), "stage": entry_match.group(2)}
            entries.append(current)
            continue
        if current is None:
            continue
        field_match = re.match(r"^-\s+\*\*(.+?)\:\*\*\s*(.*)$", line)
        if field_match:
            key = field_match.group(1).strip()
            current[key] = field_match.group(2).strip()
    return entries


def _format_path_list(items: list[str] | tuple[str, ...]) -> str:
    values = [str(item) for item in items if str(item)]
    if not values:
        return "`없음`"
    return ", ".join(f"`{value}`" for value in values)
