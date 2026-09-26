# 2026-09-22 市场—板块—个股历史过程研究：completion 分支推送、PR 与门禁工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
姊妹：#67（研究尾单联合候选，决定用哪个历史 head）、#75（独立 QC）、#76（四道真实题）。本单只做「让 completion 分支成为可审对象」，不做真实模型验收。

## 背景与动机

- 这条线的 PR 链：#783（`feat/history-market-anatomy`）→ #800 → #833（`fix/history-forward-0921`）→ **#845**（`fix/history-forward-boundary-0921`，head `442476f7d`，base = #833 分支，标题「补格续问已修，完整 Python 分组通过，待独立验收」）。历史证据绑定另有 #829 → #841。
- 09-22 本地分支 `fix/history-completion-0922`（HEAD `807a75d88`，基线 `a2c8d1f90` + merge `442476f7d`，领先 main 12 提交，**未推**；树 `~/fwp-wt-history-completion-0922` 有 1 个未提交路径）：
  - `101678e89` 合并 #845 与失散的证据绑定补丁链，补回缺失前置 `3765af67b`（跨页保留源行坐标），34 条失败清零；
  - `613376089` `compare_cases` 规则型启动条件——控制组能力（本轮主要业务缺口）；
  - `4e000ee22` 两处「历史算子清单」补齐为引擎声明的六个（BLOCK 级死路）；
  - `c1d4643df` 引错算子按剔除处理而非整格作废；四题离线干跑；
  - `7fc60d279` 「本轮欠不欠一份条件全集比较」改为逐轮判据；
  - `0ee839f14` 四题四种形状全部离线走通（8 条）；`807a75d88` 文档。
- 门禁：干净树收据 `~/.finance-runtime/test-receipts/20260922T141005Z-0ee839f1.json`——12984P / **1F** / 89S / 2X，`exit_status: 1`。唯一失败 `tests/test_code_map.py::test_structure_probe_daily_full`（断言 `'market_feature_store' in '[]'`：`code_map.py query` 结构层在 `search_graph` 取不到结果时给 `unavailable` 返回空命中；本树 `graph.db` 542MB、当时磁盘剩 4%、同机多棵全量并跑）。单跑 `tests/test_code_map.py` 42P/3S。作者未移签为绿，也未改测试容忍失败。历史域 `-k` 面 2050P/9S。
- 真实四题（自然语言、真实模型）仍未跑；`baseline/history-evidence-qc-0921`（`06fca48d4`）保留隔离发现与有限修复收据。
- **已定的形态决策**：控制组用规则判启动而不是按结果筛（结果筛会让对照组消失）；引错算子剔除该引用而不是整题作废；未编号本地多问题仍落 `direct_answer` 一格，切题是 `user_task.py` 的确定性正则，扩到无编号等于改信任模型，属产品判断不在本单。

## 目标

1. 树里 1 个未提交路径处置：是作者文档就 pathspec 提交，是杂物就写进交接不提交；然后 `git push gitea fix/history-completion-0922`，开 PR（base main），描述引用四题四形状的离线走通证据与那 1F 的分诊。
2. 前向到最新 main（`merge-tree` 探冲突），低负载四叶；`test_code_map` 那条在 load ≤ 4、磁盘 ≥ 8G 时复跑：绿则记「环境红」，仍红则查 `code_map.py query` 的 `unavailable` 路径是否被本分支改动影响（`git diff gitea/main..HEAD -- scripts/code_map.py` 应为空）。
3. 给 #67 一句明确结论：本分支是否应替代 `42784d27e` 成为联合树历史层（列出两者的 diff 文件数与是否含 #814 门禁移植）。
4. #845 / #833 / #783 / #841 / #829 关系表：哪些被本分支完全覆盖（`git merge-base --is-ancestor`），哪些有独有提交；覆盖的在本 PR 合入后 `close --pointer-file`。
5. 四道真实题条件卡交 #76：题面路径（四题原文在分支 `docs/handoffs/2026-09-1x-history-*.md` 系列）、固定 SHA、frozen 数据根、控制组要求（启动/控制组证据）。

## 非目标（写死认领）

- ❌ 不跑真实模型四题（#76）。
- ❌ 不修 `test_code_map` 让它容忍空命中。
- ❌ 不扩「未编号多问题」到模型切题。
- ❌ 不在本单合并；合入走 #67 或单独确认。
- ❌ 不改 `baseline/history-evidence-qc-0921` 的隔离发现。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/fwp-wt-history-completion-0922/docs/handoffs/inflight/fix-history-completion-0922.md` | 六个提交各做什么、收据、1F 分诊 |
| `~/.finance-runtime/test-receipts/20260922T141005Z-0ee839f1.json`、`…125353Z-c1d4643d.json` | 两轮全量同一条失败 |
| `~/.finance-runtime/reviews/history-completion-20260922/full-final.txt` | 全量日志 |
| 分支上的 `docs/handoffs/2026-09-17-history-market-anatomy.md` … `2026-09-20-history-closeout-fixes.md` | 四道真题的定义与历次拒收原因 |
| `~/.finance-runtime/reviews/research-tail-formal-gate-20260922/` | `42784d27e` 的正式门禁，对照用 |
| `intelligence/services/user_task.py` 切题正则 | 「确定性切题」的出处 |
| `scripts/code_map.py` `query` 的 `unavailable` 分支 | 1F 的机制 |

## 步骤

1. 开工三连；`git -C ~/fwp-wt-history-completion-0922 status --short` 看那 1 个路径，问所有者意图（看 Pi 会话 mtime，仍在写就等）。
2. 推送、开 PR。
3. `merge-tree` 探 main 冲突；前向；低负载四叶；`test_code_map` 单条复跑三次。
4. 出关系表与对 #67 的结论。
5. INDEX #68 行；inflight ≤3K。

## 验收

- [ ] PR 存在，head == 推送 SHA；四叶收据 revision == head。
- [ ] `test_code_map::test_structure_probe_daily_full` 有低负载三次读数；若仍红，`git diff gitea/main..HEAD -- scripts/code_map.py` 为空的证据落盘并升级为阻塞。
- [ ] 阳性对照：把 `compare_cases` 规则型启动的判据改回按结果筛，对照组用例必须红；还原后绿。
- [ ] 关系表覆盖 #845 / #833 / #783 / #841 / #829 五张，每张一个结论。
- [ ] 给 #67 的结论一句话落在 PR 描述首段。

## 红线

- 只用 pathspec 提交；不合 main；不强推；不动别人的未提交路径。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`；全量前看 `uptime` 与磁盘。
- 不跑真实模型；不动 8792。
- 不写明文密钥。
