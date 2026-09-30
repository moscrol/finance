# GitHub Primary Backup Implementation Plan

> For agentic workers: execute inline in this session using the approved design; preserve all unrelated work.

**Goal:** GitHub is the finance development remote; local Gitea and standalone bundles preserve recovery data.

**Architecture:** An installed Python runner pins source refs, bundles code, copies refs to Gitea with normal atomic pushes, and exports API metadata. GitHub writes are disabled in the runner. Development configuration and agent entry points select origin/main.

**Tech Stack:** Python standard library, Git, gh, Keychain, macOS launchd.

- [x] Add `scripts/github_local_backup.py`; install copies into a stable runtime directory, independent of this worktree.
- [x] Verify real local Git flows with `tests/test_github_local_backup.py`: fast-forward, deleted source branch retention, divergent source archival, destination rejection, standalone recovery.
- [x] Update `AGENTS.md`, `docs/workflows/agent-foundation.md`, `scripts/workspace.py`, `scripts/worktree_board.py`, and the shared preferences to select GitHub.
- [x] Add competing-remote regression checks to `tests/test_workspace.py` and `tests/test_worktree_board.py`.
- [x] Save original Git configuration; switch finance push defaults and former Gitea branch tracking entries to origin without changing commit pointers.
- [x] Configure GitHub main with required `workbench-check` and `registry-check`, administrator enforcement, and force/deletion protection; read back settings.
- [x] Install the hourly local runner; wait for its actual successful backup and verify source branches, retained destination branches and recoverable bundle.
- [x] Publish the setup branch as a GitHub PR; attach it to this chat. Keep main merge behind the existing user-confirmation rule.
- [x] Record actual installation, validation scope and recovery instructions in a shareable handoff and local output.

Execution evidence: `docs/handoffs/2026-09-30-github-primary-local-backup.md`.
Remaining integration gate: PR #5 requires successful full CI; the user explicitly authorized merging after all checks pass, and GitHub auto-merge is enabled. Environment installation is already active.
