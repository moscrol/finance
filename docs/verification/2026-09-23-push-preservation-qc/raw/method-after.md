---
name: push-unpushed-branches-classify-and-preview-commit
description: "Bulk-pushing ~1000 local branches to gitea: classify tips with one rev-list --not, skip tips already contained in remote refs, never force; and verify commit-only checkers (check_evidence_archive.py) on an unreferenced preview commit built from a temp index before the real commit"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 197bae32-870b-475a-b32c-ca583412e425
  modified: 2026-09-23
---

2026-09-22 (S1 / user task #63): user asked to push every unpushed branch and finish the market-cutoff tree, "不改任何历史". 1,011 local branches vs 290 gitea heads.

**Classify once, not per branch:** `git rev-list <all local tips> --not <all gitea head SHAs>` gives the local-only commit set; a branch is unpushed iff its tip is in that set. Buckets: synced / new_unpushed / ff_push / diverged / remote_ahead / contained (tip reachable from gitea/main or another gitea ref, e.g. a merged-and-deleted branch or a PR head). Push only new + ff (188 that day); contained (572) must NOT be re-pushed — it resurrects branches the merge flow deleted. Diverged (10) are reported, never forced or merged. Take a fresh `ls-remote` for the final local==remote table. In the historical #63 batch, 188 targets = 173 new heads + 11 fast-forwards + 4 already pushed identically by concurrent sessions (including `fix/eastmoney-snapshot-direct-ip-0922`, omitted from the first narrative). The 1,011/290 inventory and its buckets are the initial snapshot, not a live count; report the final enumeration separately, with its timestamp. Local/remote reads are not an atomic cross-repository snapshot.

**Hook-safe bulk push:** `~/.claude/hooks/block-dangerous-git.sh` blocks `push … [ /:]main( |$)` and `-f/--force`; names like `qc/overnight-onto-main` or `wip/mainline-…` pass because `main` is not delimited. Pre-check the refspec list with the same regex, then pass the refs explicitly on the command line (188 × `refs/heads/x` fits easily) so the hook sees exactly what is pushed; a `--dry-run` first costs one call and shows `[new branch]` vs `sha..sha` vs `! [rejected]`.

**Preview commit for commit-only checkers:** `scripts/check_evidence_archive.py` reads Git blobs, not disk. Use `scripts/preview_evidence_archive.py prepare <archive> --repo <worktree> --paths <explicit-other-paths>` (introduced on `fix/push-preservation-qc-0923`; confirm it exists in the chosen checkout). A successful result is `preview_only`: pin its base and preview SHA, make a separate pathspec commit and stop immediately if that command fails, then run `verify <archive> --repo <worktree> --preview <sha> --revision <full-real-sha>`. Verify checks parent + whole tree and reruns the archive checker; any mismatch is nonzero. It proves committed bytes, NOT remote preservation or product acceptance.

**Temporary-index scope:** for a manual port, create a unique directory with `mktemp -d`; inside a subshell, `export GIT_INDEX_FILE="$tmp/index"` BEFORE all `read-tree`, `add`, `write-tree` and `commit-tree` calls, and clean that directory on exit. Prefixing only `read-tree` with an environment assignment scopes it to that one command; later `add` would touch the real index. The actual #63 script used `export` safely, but the earlier note here did not. The old script also only printed commit failure / tree mismatch: use explicit nonzero exits, not `echo NO`, and check the final full commit SHA again. Never run the preserved original audit script as a current recipe. On #63 the archive preview exposed 9 missing entries + 3 hash mismatches before committing; the actual final trees matched.

**Why:** re-pushing contained tips and force-pushing diverged ones are the two ways a "push everything" task silently changes history or undoes cleanup; commit-then-amend is the third.

**How to apply:** classify → dry-run → explicit push → fresh ls-remote table; for any checker that takes `--revision`, preview-commit first. Related: [[dangerous-git-hook-matches-tokens-across-the-whole-command]], [[delete-merged-branches-without-asking]], [[pasted-handoff-summary-may-lag-the-branch-tip]], [[committed-handoff-can-point-at-uncommitted-deliverables]].
