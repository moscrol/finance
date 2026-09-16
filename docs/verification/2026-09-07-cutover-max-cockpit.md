# 切流 0907：8792 出口改 cockpit（sol 主 / terra 兜底）+ 能力 max 档（PR #608）

日期：2026-09-06 23:40 → 09-07 00:35 CST。用户决策：「先找到能力 max，然后再根据超限的部分设置约束，而不是上来就约束 agent」；
8792 出口切 `localhost:57244`（sol）；不另开对照臂，直接把 8792 改成 max 形状。

## 0. 起因：登录钥匙串被重置，8792 崩溃循环 1 小时 50 分

- `~/Library/Keychains/` 出现 `login_renamed_1.keychain-db`（282 KB，09-06 20:31 最后修改）+ 新建的小 `login.keychain-db`（88 KB）：
  **登录钥匙串当晚被重置一次**，旧的改名保留。`finance-workbench-test-relay`（中转 key）、`finance-workbench-glm`（GLM key）、
  `gitea-local/a77-token`、`gitea-local/a77-webpassword` 全在旧钥匙串里，新钥匙串 244 条里零命中。
- 8792 ~21:50 一次重启后撞上启动器的 fail-closed（取不到 key 即 exit 1），KeepAlive 每 10s 拉起：`launchctl print` `runs=647 / last exit code=1`，
  err.log 656 行同一句 `✗ Keychain 取不到中转 key`。stdout 最后一次请求是 09-05 23:50。
- 8796 sidecar（旧快照 `40fd5a84`）不受影响，一直健康。

**遗留给用户**：旧钥匙串还在磁盘上，用旧登录密码在「钥匙串访问」里打开 `login_renamed_1.keychain-db` 可把其余条目搬回来；
本次只重建了下面两条。

## 1. Phase 1：出口切 cockpit（纯配置，23:44–23:56）

| 项 | 读数 |
|---|---|
| 57244 网关 | `cockpit-cliproxy` 在跑（23:30 重启）；`quota-pool-state` 1 个活跃 Codex 账号，5h 窗 100% / 周窗 74%；`/v1/models` = sol / terra / luna / codex-auto-review |
| 延迟（同机实测） | 11.5K prompt token：**sol 4.8s、terra 1.6s**；17 token 小探针 3.6s。08-08 弃用 sol 的依据（中转 25/48/50s）对这条线不成立 |
| Keychain | 新建 `finance-workbench-cockpit / a77` = cockpit 自己的网关 key（`~/.antigravity_cockpit/codex_local_access_sidecar/config.json api-keys[0]`，07-25 起指纹未变） |
| 启动器 | 中转 + GLM 两段 → cockpit 一段；两行 `export` 各自查 Keychain（8796 sidecar 只 source `^export` 行）；起服前 `curl 57244/v1/models` 不通即 exit 1。备份 `.bak-20260906-pre-cockpit` |
| provider 链 | `[0] zhipu(名)/gpt-5.6-sol @57244`，`[1] openai/gpt-5.6-terra @57244`。`[0]` 的 name 是 `detect_providers` 给 FORESIGHT_BUILTIN 槽硬编的，无智谱成分；影响两处（repair cap 40s、UI describe）均无害，真值看 `served_model` |
| 验证 | health 三读 `f4c03b9a / dirty=False / matches=True`；readiness 13/13；账本 `startup` 行 ok；探针 `run_20260906_235449_478128` completed、judge passed、degrade 0、secret 0、65s、`served_model` 三轮全 `gpt-5.6-sol` |

## 2. Phase 2：max 形状（PR #608 → main `5cc5aa8b`，00:31 切）

代码见 PR 正文。门禁 `run_main_gate.sh --baseline 20260906T102409Z-7664af48.json`：**7924P / 0F / 76S**，`same_red_set=True`；
11 条新测试，三个变异各精确击杀一条。启动器加五行：`WORKBENCH_RESEARCH_TIER=max`、`WORKBENCH_TOOL_AUTHORIZATION=all`、
`WORKBENCH_TOOL_MENU_HIDE=off`、`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS=900`、`LLM_TIMEOUT=300`；注掉 `ASK_TOOL_BATCH_TIMEOUT=60`
（它是只能往下压的保险丝，留着会把 max 档 540s 的工具批窗剪回 60）。备份 `.bak-20260907-pre-max`（与现役只差这六行）。

五步切流：bootout → `ln -sfh` `finance-workspace-5cc5aa8bf1e9` → 账本 `switch` → bootstrap。health 三读 `5cc5aa8bf1e9 / False / True`，
readiness 13/13，账本 check ok。回滚锚 `~/.finance-runtime/cutover-20260907-max-rollback-8792.txt`。

⚠ 账本 `record --action switch` 按 acceptance-workflow §4 原文（不带 `--port` / `--ledger`）**静默不写**，补 `--port 8792 --ledger ~/.finance-runtime/deploy-ledger.jsonl` 才落行。
切前账本最后一行停在 08-27 `e5d45933`——09-03 五次切流的 switch 行都没落，同因。文档待改。

## 3. 同题两轮对照（长电科技怎么看，同日同模型 sol，唯一变量 = 形状）

| | standard（23:54，`f4c03b9a`） | **max（00:32，`5cc5aa8b`）** |
|---|---|---|
| 授权工具 | 9 | **13**（全部） |
| 工具调用 | 8：5 成 / **2 `tool_budget_exhausted`（首轮点 6 个、帽 4）/ 1 `tool_timeout`（授 8.7s）** | **16：16 成 / 0 错** |
| 藏菜单 | 第 2–3 轮藏 `evidence_search`、`kb_search`；第 3 轮 `would_grant=0` | 无 `tool_menu` 事件（=零藏） |
| 模型轮 | 3 | 4 |
| 结果 | **`partial`** | **`completed`** |
| 判官 | passed / degrade 0 | passed / degrade 0 |
| 耗时 | 65s | 143s |
| bindings / 正文 | 7 / 553 字 | 7 / 741 字 |
| gaps | 4 条，全是预算形状：「缺公告、缺新闻、缺一手复核」 | 3 条，全是数据形状：l3 查了 3 次、公告里没有业务拆分；缺估值口径；缺现金流三项 |

读法：同一个模型、同一道题，放开预算后**零次白烧**、从 partial 到 completed，gap 从「不让查」变成「查了没有」——后者才是诚实缺口。
代价是墙钟 ×2.2。n=1，只断言结构，不读成质量提升。

## 4. 接下来该量什么（约束只加在超限的项上）

每题记：工具调用数、零授予次数、耗时 P50/P95、弃权率（`intelligence/eval/abstention.py`）、判官删句（`sentence_verdicts`）、事实错误。
候选约束及其触发读数：P95 耗时 > 用户可接受值（待定）→ 收墙钟；单题成本 > 阈值 → 收每批帽；判官删句 / 事实错误上升 → 收工具面（先收二手源）。
没有读数不加约束。

## 5. 未做

- `sub_research` 包成模型可点的工具（spec `2026-09-03-subagent-tool-design.md`）：max 档下 PLAN 带 `branch_goals` 时既有协调器已可达，先看 PLAN 率再决定。
- 冻结题集（knevo28 + D 组 10）两形状对照——今晚只跑了 n=1。
- Keychain 其余条目（GLM / 中转 / gitea 网页密码）未恢复；GLM 已按用户决策弃用。
- gitea 备份 `post608` 未打（切流完成判据之一），下一会话补。
