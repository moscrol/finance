# feat/runtime-base-p2-durable-store · 运行底座 P2（工单 #29）

更新：2026-09-07 下午 · 树 `/Users/a77/fwp-wt-runtime-base-p2` · 叠在 `feat/runtime-base-p1-messages-cancel`（PR #624，未合）之上

## 做什么
母单 #27 §6.3：每步落盘（`events.jsonl` 追加 + `state.json` 覆写）、意图/结算三明治、重启后 `restore`、`configure` 快照、`EPISODE_LOG_VERSION`。用户「继续按最优路径推进」，§12 第 1 / 3 题按推荐（JSONL / 只登记）。工单正文 `2026-09-07-runtime-base-p2-durable-store-workorder.md`（§0 记了两处与母单 G1 有出入的实测：`tool_request` 今天是事后记录不是意图；预留的是关联 id 不是 sequence）。

## 当前状态
- 四刀四 commit：A store（`d1e77051`）、B 三明治 + oracle（`78789f6f`）、C restore + Tier A（`f1110c7f`）、D 接线（`e59f03ea`）。目录 `--check` 一致，ruff 0。
- 门禁：干净树全量 **ruff 0，8063 passed / 0 failed / 77 skipped**（`~/.finance-runtime/test-receipts/20260907T102315Z-e59f03ea.json`），对 P1 基线收据（c6807038，8021P）red set 相同、passed +42（全是本单新增）。
- **模型可见内容零改动**：`model_intent` / `configure` / `tool_request.replay` 都不进 `derive_messages`；`prompt_assembled{finalizer}` 派生器跳过。严格派生模式全套件在验。
- **事件流形状改动两处**（既有断言按意图改）：首条是 `configure`；一批多个工具调用时 `tool_request` 整批先于任何 `tool_result`（单调用批次不变）。

## 已做
- 生产装配传 `JsonlEpisodeStore(resolve_episode_store_root())`：`FORESIGHT_EPISODE_STORE` → `$FINANCE_WS/state/episodes` → `~/.finance-runtime/episodes`。**尚未切 8792**——它是真行为改动，母单 §7 五步规程 + `kill -9` 演练需用户在场。
- `/api/readiness` 加 `open_episodes`（只登记）；`continuous-episode.json` 加 `log_version` 与 `runtime_handle`（含 `scope.derive_mismatches`——探针时发现的「只在内存」补上）。
- conformance 矩阵加 INV-R2 / INV-R3（continuous SUPPORTED，其余臂 UNSUPPORTED_DECLARED 带理由）。

## 与 main 的整合（09-07 傍晚，三级前向合并，不改写历史、不强推）
- 开 PR #638 时 `gitea/main` 已从 0b834d77 走到 92c7826c（#628 派发节奏 / #635 观察瘦身 / #636 历史折叠都碰 `agent_episode.py`），三张 PR 对 main 全部文本冲突。处置：`main → spec/runtime-base-endstate`（3d4a254c）→ `feat/runtime-base-p1-messages-cancel`（0d006a2a）→ 本枝（962aed84），每级一次冲突解决，三张 PR 对 main 重新 clean（`gitea_pr.py conflict-check`）。
- **历史折叠是 INV-R1 的洞，不只是文本冲突**：`compact_history` 就地改 tool 消息正文，P0 的派生只认事件。在 P0 级补：`history_compacted.folded[]` 每项带替换后 `model_content`、`derive_messages` 按 call_id 覆写、投影支持 `list[].field` 剔正文；主循环顺序钉成 折叠 → 对账 → 意图 → 请求。P1 级把 `compact_history` 改在 `EpisodeMessage` 上工作（`replace()`），两份量具测试改读属性。开关开着的 loop 测试在严格派生模式下通过即证据。
- main 新增的派发节奏单元测试直接调 `_append_tool_budget_state` 没带 P0 的 `ledger`——按意图改（传记录账本，并多断言 `tool_budget_state.model_content` 与模型看到的同一份）。
- 整合后本枝头 962aed84（= main 92c7826c + P0 + P1 + P2）干净树全量 **ruff 0，8195 passed / 0 failed / 76 skipped**（`~/.finance-runtime/test-receipts/20260907T105919Z-962aed84.json`），对整合前收据 red set 相同。这一张就是三张 PR 依次合入后 main 的模样。

## 卡点 / 需要用户的
1. #620 → #624 → 本枝三张 PR 依次合并确认（每张合后下一张只需改 base，P1 三 commit 与本枝父链都已含前置）。
2. 8792 切流：合入后单独一刀，切后手工 `kill -9` 一次在飞 episode，重启看 `/api/readiness.open_episodes` 与 `ContinuousAgentEpisode.restore(...)`。

## 下一步
- P3（#30 收件箱）等 §12 第 4 题（Workbench `steer` 端点本轮做不做）。
- P4（#31）：`step()` 单步驱动——`restore` 现在只给 `ResumePlan`，重新开车是 P4 的事；oracle 升公共件。

## 不要做
- 不改 `ToolCallStatus` / `AgentModelClient` / 90/60/30；harness 只加了 `ToolSpec.replay` 字段。
- 不做自动后台恢复（§12 第 3 题）；不做 SQLite。

## 踩过的坑
- `EpisodeState.contract_snapshot` 直接喂冻结的 `configure` payload（mappingproxy 嵌套）时 `json.dumps` 炸——改用 `agent_runtime._json_copy` 递归复制。
- 一批两调用只落一条意图就崩：正确的下一动作是「重跑落了的那条」，不是回模型——测试第一版把它写错了；一次 restore 只给一步，驾驭方迭代收敛。

## 2026-09-08 14:30 · 工单 #38 前向合并 + 三张门禁（等用户确认合入）

- 三张 PR 已前向合并到 `gitea/main@8e452e72`（不 rebase 不强推）：#620 `09e54b5d` ← main；#624 `9a4d5c76` ← #620；#638 `ef5f4c70` ← #624。唯一冲突都在 `2026-09-01-workorders-INDEX.md`，按「只加行、按号排序」解（#27–#31 + main 的 #32）。本机 `merge-tree` 三张对 main 全 clean（Gitea 的 `mergeable` 字段刷新滞后，不看它）。
- 干净树全量门禁（`.venv-workbench`、`env -u MARKET_FEATURE_STORE_DB`）：#620 **8183P/0F/76S/1xfail**、#624 **8215P/0F**、#638 **8250P/0F**；ruff 0；`check_test_receipt --expect-revision HEAD` 三张均「可采信」。三张都不碰 `intelligence/webapp`。
- **下一步要用户**：按 #620 → #624 → #638 顺序确认合入（`gitea_pr.py merge N --yes`）；P2 合入后单独切 8792（0908c）+ `kill -9` 演练，步骤在工单 #38 §2.5。
