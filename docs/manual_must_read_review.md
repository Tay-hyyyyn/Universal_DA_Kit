# Lightweight Must Read It Review

## Adopted

- Root and area `AGENTS.md`/`CLAUDE.md` maps route agents to only the relevant workflow.
- L0/L1 work stays direct; L2 work uses a short plan and relevant verification; L3 work requires approval and rollback planning.
- Manual run state and compact stage payloads are preferred over long historical reports.
- Raw data, test data, runtime outputs, and model artifacts remain separate from reusable code.
- Learned notes and measurement logs are optional records for recurring issues, larger work, or recovery after a failed check.

## Intentionally Excluded

- OpenSpec, delta specifications, and mandatory implementation-plan files.
- `ultracode`, automatic subagents, profile pickers, and plugin installation as default workflow steps.
- Stop gates, forced evidence JSON, retry budgets, and hooks that block ordinary analysis tasks.
- External absolute-path dependencies on the `Must Read It` workspace.

## Interpretation

This package uses the useful routing and safety principles of Must Read It without turning routine EDA or small preprocessing changes into a mandatory harness. Stronger orchestration can be added later as an opt-in profile for a genuinely large engineering task.
