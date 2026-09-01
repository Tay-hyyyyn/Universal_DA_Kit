# Workflow Recipes

## Explore

Use when the user asks how something works or where to change it.

1. Run targeted file search.
2. Read root map and relevant area guide.
3. Trace entry points and data flow.
4. Return a concise map with file references.

## Implement

Use when the user asks for a change.

1. Read the root map and the relevant area guide.
2. For L2/L3 work, state a short plan and the verification to run; L0/L1 work can proceed directly.
3. Edit the smallest coherent set of files.
4. Run the closest verification.
5. Report verification evidence when the change affects behavior or data.

## Review

Use when asked for review or before commit.

1. Inspect diff.
2. Compare against requirements and area guides.
3. Report correctness, security, regression, and missing-test findings first.
4. Avoid style-only feedback unless it hides behavior risk.

## Learn

Use when a lesson should persist.

1. Confirm the lesson is repeatable.
2. Record it in `docs/agent/learned-notes.md` only after it recurs or when the user requests it.
3. Update an area guide only when the lesson changes normal operating behavior, then sync AGENTS and CLAUDE pairs.
