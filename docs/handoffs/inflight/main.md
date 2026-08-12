# 在途交接 · main

更新：2026-08-12 · Claude

## 这个分支做什么

对照检索源逐层修缮 agent（工具接口 / 压缩 / RAG），已合并 `fc0540ee`、部署生产
`da27ad01`。**卡在一个已定位未解决的问题上。** 展开见
`docs/handoffs/2026-08-12-tool-interface-and-rag-fixes.md`。

## 当前状态

生产 `rev=da27ad01 code_matches_repo=True rag_runtime=True`，与 main 一致。
工作区脏文件**全不是本轮的**（ingest 产物 + 5 个他人代码文件），别提交别 stash。

**卡点：continuous 路径 `evidence_bound` 恒为 0。** 工具正常取回 24–60 条证据，
答案却输出「现有证据不足」。验收 28 题真值通过 0 就是这个。

## 下一步

查 **continuous_episode 为什么绑定 0**。变量已锁定、可二分、零配额起步：

| `ASK_CONTINUOUS_RUNTIME` | B1 | C1 |
|---|---|---|
| `off` | 30 | 13 |
| `on`（生产） | **0** | **0** |

**与代码版本无关**（合并前后同为 0）。轨迹在
`<用户目录>/runs/*/continuous-episode.json`，先离线比对 evidence 在哪步被丢。
`evidence_bound` = `/api/runs/{id}/context` 里 `status=="hit"` 的条数
（`acceptance.py:198`）。

## 踩过的坑

- **起临时实例做对照必须复刻 `ASK_CONTINUOUS_RUNTIME`**。漏了它我误判成
  「自己造成回归」并回滚了生产——两臂差的不只是代码。
- **双根要分开**：代码根用 cwd/worktree，数据根 `FINANCE_WS` 指主树。搞混的症状
  与 `paths.py` docstring 记的一模一样。
- **`loaded_code_root: None` 只说明从哪加载，不说明何时加载**。canary 进程跑了
  6 天，磁盘新代码、进程里是旧的。
- 工具调用记在 `continuous-episode.json`（300KB+），**不在 trace/stream.jsonl**。
- 变异验证要**先确认变异真的落盘**，且**删整句别改一半**（改后仍是断言子串）。

## 未验证 / 已知边界

- 回灌 / 拆包 / 降级告知三条改动**没触发条件**，效果未测，属长尾保险。
- `probe_tool_arguments.py` 用 `capabilities=ALL_TOOLS` **绕过路由**，其
  「87.9% 参数合法率」只在「工具已授权」前提下成立。
- 规划器对多数问题交白卷（`retrieval_stages: []`），靠 agent loop 自主性兜底
  ——**换个问法可能不兜**。
- 组件 4（记忆）/ 5（多 agent）检索源未精读，**不得下结论**。
- `import intelligence.api.app` 有文件系统副作用，生产码未改；两个大脑目录
  数据分裂互不相通；`scripts/agent_review/` 约 2300 行无人读过语义。

## 已验证

全量 4516 passed / 0 failed @ `.venv-workbench/bin/python`，8 道 pre-commit 全过。
生产实测 finance_query 24/24 参数合法（改前干净对照 55.9%）。`.rag_venv` 已重建，
kb_search 从死到活；就绪门禁与部署闸门均变异验证。
