# fix/issue-contract-codes

## 这个分支做什么
W1：验证器→放行门握手从自然语言前缀改为 `IssueCode` + `RELEASE_POLICY`。改 `Issue.message` 不得改放行。规格 `docs/superpowers/specs/2026-08-19-loop-robustness-r1.md` §W1。基线 `gitea/main@b42a82d6`；C/D 未合，后合方 rebase。

## 当前状态
**已实现、未推、未合。** 单一真本源 `intelligence/services/episode_issues.py`。G7 产 `Issue`；`VerifiedEpisodeOutcome.issue_items` 是门控源，`issues` 为 `code=<value> subject=<slot> :: <message>`。G11 `_can_semantically_release_partial` 只调 `allows_partial_release`，零 `startswith`。缺 `RELEASE_POLICY` 项 = BLOCK。

## 已验证
- 解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13）；ruff 目标 py39 → 用 `(str, Enum)` 不是 `StrEnum`。
- 定向 215 passed（issues/verifier/protocol/semantic）。
- 全量 **5610 passed / 16 failed / 12 skipped**，收据 `~/.finance-runtime/test-receipts/20260819T081916Z-b42a82d6.json`（dirty）。16F = ceiling 权限位环境项，与 #224 基线同形，非本单回归（本单 +6 = 5604→5610）。
- 穷尽性 `frozenset(IssueCode)==frozenset(RELEASE_POLICY)`；文案防倒退；monkeypatch 缺项 BLOCK；G11 源码无 `startswith`。
- #224：stripped → STRIP_OK；unsupported type → PARTIAL_OK；财务锚 floor / unknown hash → BLOCK。

## 未验证
**SPT 三题 sidecar 重放未跑**（任务允许跳过）。#224 语义只钉在单测。

## RELEASE_POLICY
PARTIAL_OK：`required_output_gap` / `evidence_type_unsupported` / `missing_mandatory_capability`。STRIP_OK：`evidence_type_stripped`（G11 与 PARTIAL_OK 同等放行）。其余 BLOCK（含 `financial_anchor_missing`、`numeric_unsupported`、`marker_loss`、日历/路径预检）。

## 下一步
1. 用户确认后开 PR；不合并 main、不推除非另嘱。
2. C/D 若先合，本分支 rebase。
3. 若要 SPT 对拍，sidecar 重放 #224 三题。

## 踩过的坑
Marker loss 会 `replace` 到 `VerifiedEpisodeOutcome.issues`。只改 G7 字符串、G11 读 `issue_items`，会把 marker loss 从门控里「隐身」变成误放行。已把 `MARKER_LOSS` 登记为 BLOCK。
