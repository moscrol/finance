# feat/cap02-retrieval-deep-read

## 这个分支做什么

能力升级任务包 02「检索找到材料后继续读到能解题」（合同 `docs/superpowers/plans/2026-09-09-capability-upgrade/02-retrieval-reading-goal-brief.md`）。kb_search 命中后自动读整节（表头随片、同页所缺章节、章节目录），过期命中当轮重读原页恢复，web_fetch 按问句定向选段并按发布主体 / 文档类型分类。进度真值 `…/progress/02.md`，范围外阻塞 `…/blocked/02.md`。

## 当前状态

树 `/Users/a77/fwp-wt-cap02-deep-read` ← `gitea/main@5eb24515`。**代码、测试、冻结集、验收脚本已落；未合 main、未切 8792。**

| 检查 | 结果 |
|---|---|
| `test_cap02_deep_read.py`（42）+ kb_rag / web_fetch / agent_research / closed_loop / episode_tools 定向 | 全绿 |
| 全量 `intelligence/tests`（改动中段） | 7481P / 15S / 1x；最终版重跑见 `~/.finance-runtime/cap02/full-tests-final.log` |
| ruff | 过 |
| 离线三段量尺（hybrid=生产检索模式，20 题） | 关键短语进模型可见 **14/20 → 19/20**，无退步；可见字数中位 3675 → 6457 |
| live 第三段（Workbench 真实对话） | **未得读数**：模型网关 cockpit 57244 当时不在运行（blocked B-4），链路已冒烟打通 |

## 关键决策（选了什么 / 否了什么 / 为什么）

- **在 `kb_rag.retrieve` 就地深读，不加新工具。** 否：新 `kb_read_page` 工具（要改注册表，04 的 PR #682 正在改同文件；且 kb_search 参数面被 `parse_query_arguments` 钉死只收 query）；否：接知识库侧 `get_page`（worker 协议只跑 query，要改跨仓）。V9a 已在这一层按 file_path 读源页，顺着它做。
- **段落级证据 ≤240 字。** 模型可见投影 `tool_result_budget.MAX_EVIDENCE_DETAIL_CHARS=240` 不在白名单（blocked B-1）。否：放大该常数（不是我的文件）。代价：每次 kb_search 多 ≤15 条证据、可见字数 +76%。
- **过期命中重读原页标 `recovered`，不冒充 fresh。** 否：全部 stale 直接放行（合同明说不把 stale 当当前事实）；否：保持一律丢弃（09-14 起索引过 14 天龄门会把全部命中丢光，blocked B-3）。核对不过的仍丢，告警写明「已尝试重读」。
- **web_fetch 只分类不改 `evidence_tier`。** 分档规则归 01 判官；本单把发布主体 / 文档类型写进标题前缀与观察值首句。契约文案改动记 blocked B-2（注册表让给 04）。
- **问句切词先切功能词再取二元组。** 第一版滑窗二元组产生「块的 / 是多」碎片，用真实 20 题看出来后重写；离线读数是重写后的。

## 不要做

- 不要为凑 live 读数切回 09-06 已弃用的中转配置，也不要替用户启动 Cockpit Tools。
- 不要把离线 19/20 写成「真实验收通过」——它只到第二段（进入模型可见）。
- 不要改 `research_tool_registry.py`（04 在改）。

## 下一步

1. 用户起 Cockpit Tools 后：`~/.finance-runtime/cap02/launch-8802.sh baseline` → `scripts/cap02_deep_read_acceptance.py live --port 8802 --users-root ~/.finance-runtime/cap02/users --user-prefix cap02-base --out ~/.finance-runtime/cap02/live/baseline`；换 `treatment` 重启再跑；`report` 出逐题表，回填 progress/02.md「live」节。
2. 用户拍板后开 PR 到 main（合并前 `merge-tree` 对 `feat/sandbox-derived-calculation` 核 `episode_tools.py` / `agent_research.py` 相邻改动）。
3. 生产生效需切流 + 重启 worker；本单不做。
