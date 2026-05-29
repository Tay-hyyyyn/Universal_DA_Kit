---
name: manual-domain-expert
description: Generate learning-oriented domain expert question cards and ingest user answers into Manual domain context packs.
---

# Manual Domain Expert

## Purpose

Use this plugin when a Manual run needs domain input but the user is not a deep domain expert. The plugin gives each question starter answers, explains why the answer matters, and stores low-confidence answers as hypotheses instead of hard rules.

## Commands

Generate the questionnaire after Stage 00:

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-domain-expert\scripts\generate_questionnaire.py --config Manual\config\<project_config>.json --run-id <run_id>
```

Ingest user answers after editing `Manual\runs\<run_id>\reports\domain_answers.md`:

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-domain-expert\scripts\ingest_answers.py --config Manual\config\<project_config>.json --run-id <run_id>
```

Run a domain checkpoint gate (pause if required cards are still open):

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-domain-expert\scripts\domain_checkpoint.py --config Manual\config\<project_config>.json --run-id <run_id> --stage-before <01|03|05|07>
```

If the user says "그냥 진행해줘", defer the current pending checkpoint using the pending file:

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-domain-expert\scripts\defer_pending_checkpoint.py --config Manual\config\<project_config>.json --run-id <run_id>
```

## Outputs

- `domain_questionnaire.md`: learning question cards with starter answers.
- `domain_answers.md`: user-editable answer template.
- `domain_context_pack.json`: compact machine-readable domain context.
- `domain_context_pack.md`: human-readable summary.

## Safety Rules

- Starter-answer-only responses are domain hypotheses, not confirmed facts.
- Low-confidence answers must not trigger source data deletion or automatic filtering.
- Domain rules start as candidates and require user confirmation before becoming accepted rules.
