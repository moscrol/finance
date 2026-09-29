# 2026-09-29 23:15 主工作树收口：全量快照 → 快进到 main（Claude Code 云端会话）

写完不改；更正走 `record-correction`。授权：用户 09-29 约 23:00「这些也是你来推进，按照最优方案」。

## 结论

- `~/finance-workspace-private`（主检出，分支 `main`）已从 `df3e37744` **快进到 `gitea/main@f02fbaa7a`**，不再停在旧版本上。
- 快进前把全部脏状态（124 项）原样打成快照 `checkpoint/main-workspace-20260929b@8c2f1e47`，已推 Gitea。用的是临时 index + `commit-tree`，没碰工作树和真 index。**任何处置都不丢数据。**
- 剩下的未提交文件（快进后 122 项：9 个已跟踪文件有改动、113 个未跟踪）**有意保留**，理由见下文。

## 分类（逐文件核对内容，不看时间戳）

| 类 | 数 | 判据 | 处置 |
|---|---:|---|---|
| 与新 main 相同 | 2 | 内容等于 `gitea/main` 同路径 | 快进前删掉，快进后由 git 原样重建（已核对哈希） |
| 别处已有 | 84 | 内容等于某个 ref 历史里的同路径版本；全是未跟踪文件 | 保留（见下） |
| 数据产物 | 27 | `market_feature_store/exports/`、`复盘/`、`skills/daily-full-review/state/` 等 | 保留：夜跑写入的正常产出 |
| **独有** | 11 | 内容在任何 ref 里都没有 | 保留在原处，内容已进上述快照 |

独有的 11 项：
- 代码：`intelligence/api/app.py`、`intelligence/services/{episode_tools,finance_query,research_tool_registry}.py`、`intelligence/tests/test_finance_query.py`，共 +159 / −28 行，main 从 `df3e37744` 以来没动过这几个文件；
- 测试：`intelligence/tests/test_finance_query_quality.py`、`test_river_routes_registered.py`；
- 文档：`docs/handoffs/2026-09-29-{agent-consumption-observation,agent-quality-high-status,name-inference-acceptance-920201-0928}.md`、`docs/handoffs/inflight/arena-river-opinion-0929.md`。

其中 `name-inference-acceptance-920201-0928.md` 记录的是用户决定（接受 920201.BJ 09-28 推断名「百瑞吉」），main 里的 `2026-09-29-candidate-0928-publish.md` 已经引用它，本体却没入库。已随收口 PR 补进 main，内容逐字节一致，sha256 前缀 `e5a93cf2bc968e75`。

## 为什么不把剩下的清掉

- **8798 开发服**（PID 92925，`uvicorn intelligence.api.app:app`，09-29 12:17 启动）就从主检出运行。
  - 那 11 项独有改动加上一批未跟踪的覆盖层文件（`intelligence/api/river_routes.py`、`river_daily_routes.py`、`static/{memory-river,sse-kline,limitup-calendar}/…`、`services/river_daily_*.py`、`opinion_attention*.py` 等），是它正在跑的 river 看板和 AI 热点在研功能。
  - 这些覆盖层文件内容在别的分支里有（dashboard、river 等），但在主检出里是一个整体，删掉会让 8798 下次启动时 import 失败。
- 另有 `python -m http.server 8766`（09-22 起）以主检出为根提供静态文件；ChatGPT/Codex 的 node 会话也以它为工作目录。最近 2 小时没有文件改动。
- 今天凌晨 8e45 事故的前提有两个：主检出停在旧版本且脏，并被当作 rsync 源；磁盘上的部署脚本没有闸门。
  - 第一个已消除：HEAD 现在就是 main。
  - 第二个已消除：main 上 `deploy_workbench_runtime.sh` 的闸门 A 拒写 git worktree 目标，闸门 B 默认拒绝脏源，脏主检出做不了部署源。

## 建议的下一步（留给 river 看板那条线的负责会话或用户）

1. 把在研的 river 看板和 AI 热点改动（上述独有项和覆盖层文件）提交到一条功能分支，比如续用 `feat/dashboard-unified-0928`，开 PR 走门禁。
2. 让 8798 改从那条分支的工作树运行，主检出就只剩数据产物。
3. 之后再按 `2026-09-29-main-workspace-dirty-triage.md` 的第 3 步重建 RAG 索引（postmortem 记录「RAG 索引建在脏源上」）。
