# Git Conventions

Read this only when the task involves Git, commits, branches, PRs, or conflict handling.

## Rules

- Check current branch and status before staging.
- Stage explicit paths. Do not use `git add .`.
- Do not overwrite user changes.
- Do not run destructive commands unless the user explicitly asks and approval policy allows it.
- Commit messages should describe the behavior or artifact changed.

## Suggested Checks

```bash
git status --short
git diff --stat
git diff --check
```
