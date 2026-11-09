---
name: commit_and_push_lsstcheck
description: Commit and push changes in the lsstcheck repo as small focused commits with humanized messages. Use when asked to commit, push, open a PR, or prepare changes for GitHub in this project.
---

# Commit and push for lsstcheck

## Commit style

- One logical change per commit. Keep code, tests, docs, and config
  in separate commits when they are separate concerns. Do not bundle
  unrelated edits into one commit.
- Check `git status` and `git diff` first. Stage only the files that
  belong to the change and leave unrelated work uncommitted.
- Match the existing history: imperative subject line, a short body
  explaining why the change was made, then the Devin trailer.

## Message text

- Apply the humanizer skill to every commit message and PR body
  before writing it. Keep the text plain: state what changed and why,
  with no AI tells, no inflated claims, and no filler.
- ASCII only, no emoji, no em dashes.

## Push

- Remote is `origin` -> github.com/Astro-Sean/lsstcheck, branch `main`.
- Push only when the user asked for it. Never force-push; if the
  remote moved, fetch and rebase or merge first.
