# Agent Context Packet

Read this packet before opening long reports or generated artifacts.

## Start Here

1. Read `AGENTS.md` or `CLAUDE.md` in the smallest relevant folder.
2. For workflow work, start with `Manual/AGENTS.md`.
3. Prefer JSON payloads and compact context packs over full markdown reports.
4. Treat `Manual/runs/` and `Manual/state/` as local runtime outputs.

## Public Package Boundaries

- Keep this repository generic.
- Do not add project-specific raw data, run outputs, model binaries, or private paths.
- Add dataset-specific examples only under `examples/` and keep them synthetic.
