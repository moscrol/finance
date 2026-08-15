# 2026-08-16 R-24 部署窗 + 8792 蓝绿切到 main tip

roadmap_ref: L1-R24

00:50 裁决：开 R-24 部署窗；dsh 实施分支不禁 push；安全 ref 按最优处理（保留）。

## 切了什么

- 新快照 `~/.finance-runtime/finance-workspace-437cd5e9aa1a`：从 private 克隆、detached @ `437cd5e9aa1ac2681ef3f990dee01866aec82b5c`（当时 `gitea/main` tip，含 #49）。
- `ln -sfn` `~/finance-workspace-runtime` → 新快照；`launchctl kickstart -k gui/$UID/com.a77.finance-workbench`。
- T+240s `/api/health` 绿。旧快照 `~/.finance-runtime/finance-workspace-fdb231148c0e` 未改，可回滚。
- 切前在新快照上跑 marker-loss 夹具：**5 passed**。

## 验收（R-06 三读数）

- `source_revision=437cd5e9aa1ac2681ef3f990dee01866aec82b5c`
- `source_dirty=false`
- `code_matches_repo=true`
- `loaded_code_root=.../finance-workspace-437cd5e9aa1a/intelligence`
- 新 pid 15841（旧 70403）
- 从快照 cwd 加载：`_shrink_verified_for_marker_loss` 在场

## 与 S7 / S9 的边界

- S7 夜跑仍走 staging（`2026-08-16-s7-nightly-staging.md`）。本次是为 R-24 开窗，不是为追 S7。S7 不在 `intelligence/`，8792 也带不上写锁消除。
- S9 rerank 保持 `DEFAULT_RAG_MODE=hybrid`，启动器未开 rerank。

## 故意没做的

- 不把账本 `R-20260815-24` 写成 `confirmed`（无 live 同形批）。
- 不开 5 题 8792 批；无 `/tmp/finance-8792-live.lock`。
- 不启 S10 Phase B / S1 / S2 / S3（S2/S3 窗已开，另开 PR）。
- 不 rebase dsh 分支（当时 ahead 29 / behind 24，工作区有未提交 `research_profile`）。

## RAG

`/api/health/ready` 在切换后一段时间 503，`missing_critical=['rag_worker']`，worker `state=warming`，prewarm 触到 240s `TimeoutError`。health 已绿。与冷启动预热预算同类，不是回滚条件。

## dsh / 安全 ref

- 已 push `feat/dsh-absorption-p0-seams` @ `feabcb5363312f8a091a55861006788dc922bda6`（只推已提交历史）。
- 安全 ref **保留**：handoff §3 的 `range-diff` 仍靠它解引用。已备份远程同名分支 `prerebase/dsh-seams-e21c50bf`=`e21c50bfdbdbdcc192956bd8f80a99d69d6d84ea`。合 main 或 §3 不再需要旧 SHA 之前不删。

## 回滚

```bash
ln -sfn /Users/a77/.finance-runtime/finance-workspace-fdb231148c0e \
  /Users/a77/finance-workspace-runtime
launchctl kickstart -k "gui/$(id -u)/com.a77.finance-workbench"
```
