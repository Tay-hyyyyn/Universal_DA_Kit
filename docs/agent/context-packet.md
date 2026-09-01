# Optional Context Packet

Use this only for L2/L3 work, a resumed run, or recovery after a failed verification. L0/L1 work should use the relevant area guide and the closest check without creating a packet.

```yaml
version: "1.0.0"
task_type: ""
goal: ""
user_output: ""
inputs: []
must_read: []
avoid_unless_needed: []
constraints: []
assumptions: []
definition_of_done: []
verification_evidence: []
measurement:
  estimated_context_files: 0
  tool_calls: 0
  rework: false
  verification_result: ""
learned_note_triggers: []
```

## Rules

- Read `AGENTS.md` first, then one workflow file from its routing table.
- Read a matching learned-notes section only when the issue has occurred before.
- Define the closest practical verification before editing; report the evidence when the task needs verification.
- Keep the packet in the conversation or task note. Do not create it as a required repository artifact.
