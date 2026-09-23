# 2026-09-23 同花顺研究观察值候选（PR #810）收口工单（#85）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
来源：`docs/handoffs/2026-09-23-orphan-inventory.md`。前置：#54（抓取侧 A–D 已合）、#827（已合 main 的四步接线 + 生成根保护已装机）。可与其他单并行。

## 背景与动机

PR **#810**（`feat/hithink-research-data`）在抓取侧之上加「当日异动、完整个股热度轨迹、当前估值观察值」三类研究观察值：`sync_hithink_research.py`、`write_path.py` 共用生产写入守卫（拒绝硬链接别名 / 未知身份）、`recover_local_review.py` 历史恢复显式排除 latest-only、`finance_query.py` 读口、`schema.sql` / `consumption_registry.yaml` 登记，15 个非文档文件。作者叶在代码 `164b02e4` 上全绿（全量 11964P / 85S / 2X、前端 110P、E2E 34P/2S、registry 与台账通过），48 份原件有 SHA256 清单。

停下来的原因有三：① 独立复审没做（Codex 周额度 100%，恢复时间北京 09-27 01:06；K3 桥 `18790/v1 -> 8080` 已被 #847 实测可用）；② 盘中 `Global request rate limit exceeded` HTTP 429 无 `Retry-After`，`get_json` 只重试 `code==4001`，429 会立即中止整轮（第一轮估值失败、热度未发、exit 2）；③ 09-21 15:48 协调决定夜跑部署只装 #827 的已合内容，「不接管 / 合入本单」。之后无人接手。

今天核对 [实测]：对当前 main **1 处冲突**（`.claude/lessons_learned.md`，追加式，union 可解）；主检出树的 32 个未提交代码改动里含 `market_feature_store/{cli,schema,consumption_registry}` 与 `sync_fupanhui_theme_flow_daily.py`——那是 L2 运营覆盖层，**与本单文件有重名但不是同一份改动**，不要合进来。

## 目标

1. #810 前向到当前 main（union 解 lessons），四叶收据绑定新 head。
2. 429 处置：`get_json` 对 429 做指数退避（上限与次数写死为常量，带测试），一轮内三端点任一 429 不再中止整轮，而是记 `partial` 并留下哪个端点缺；不改 4001 语义。
3. 独立复审走 K3 桥（#75 队列），或用户明确豁免。
4. 合入等用户确认；**部署另立**：合入后按 #60/#827 的「正门钉根」方式换夜跑 sync 代码根，本单只写出那条命令，不执行。

## 非目标

- ❌ live sync / 真实采集 / 写生产库 / 重载 launchd / 删生产数据（PR 正文与 handoff 第 4 条原话）。
- ❌ 把 8792 切到含本单的 revision。
- ❌ 顺手把主检出树里同名文件的未提交改动带进来（那是 L2 覆盖层，见 memory `main-tree-is-a-live-ops-overlay-for-l2`）。
- ❌ 扩 agent 外呼：`finance_query` 只读 DuckDB，不加新的实时源。

## 证据路径表

| 文件 | 看什么 |
|---|---|
| `python3 scripts/gitea_pr.py show 810` 及评论 `hithink-review-closeout-164b02e4` | 边界、两项返修、收据身份 |
| `gitea/feat/hithink-research-data:docs/handoffs/inflight/feat-hithink-research-data.md` | 429 现场、四条「不得」 |
| `~/.finance-runtime/hithink-research-guard-20260921/manifest.json` | 48 份原件 SHA256 |
| `~/.finance-runtime/test-receipts/20260920T195746Z-164b02e4.json` | 作者全量收据 |
| `git diff gitea/main...gitea/feat/hithink-research-data -- market_feature_store intelligence scripts skills tests` | 15 个文件净 diff |
| `market_feature_store/sync/sync_hithink_research.py`（分支侧） | `get_json` 重试分支 |
| `docs/data-sources/runtime-and-pitfalls.md` | 同花顺限流与字段坑，429 常量取值参考 |
| `docs/superpowers/specs/2026-09-22-eastmoney-transport-circuit-breaker-deploy-workorder.md`（#60） | 「正门钉根部署」的做法，抄流程不抄结论 |

## 步骤

1. 开工三连 + `git fetch gitea`；`git worktree add /Users/a77/fwp-wt-hithink-research-0923 gitea/feat/hithink-research-data`；`git merge gitea/main`，lessons 用 `git merge-file --union`。
2. 429：先写会红的测试（假 HTTP 429 两次后 200；三端点一个 429 到底），再改 `get_json`；`pytest -q tests/test_hithink_research.py tests/test_review_sync_hithink_wiring.py tests/test_write_path_guard.py`。
3. 四叶；`python3 scripts/build_registry.py check`；`consumption_registry.yaml` 新表要被 `dataset-registration` 钩子认到。
4. 贴读数；QUEUE.md 追加一行（K3 桥）；inflight ≤3K；INDEX #85 状态行。

## 验收

- [ ] `merge-tree` 干净；四叶收据 revision == head、`dirty=false`、failed=0。
- [x] 阳性对照：最终代码进程内将429重试常量设0，两针2F；新进程恢复2P，源码未改。
- [x] 定向验收窗口内，生产库stat、plist、runtime链接与8792身份前后相同；未补造开工前快照。
- [x] QUEUE.md 有本单行，独审仍待#75，不代表已有签字或豁免。
- [x] INDEX #85 已记工程完成、验收阻塞。

## 09-23 执行回写

`fix/hithink-research-85` 承接#810，最终代码 `0f0231553acf788e7d42440ce54d3d101fdca187` 已推。main基座 `626d8a508`，merge-tree干净。冻结干净定向130P、全仓Ruff、registry五项通过（跨仓跳过，台账98 warning）；CLI partial返回3，夜跑重试后仍partial不发布，旧单体也不报成功。其他研究请求继续，4001旧语义保留。

原件 `~/.finance-runtime/reviews/hithink-research-85-20260923/`，最终收据 `final-receipts/gate-3GXIgpu2/pytest.json`。完整Python/前端/E2E未跑，主机高负载下不叠加；无独审结论，不能合入。Gitea创建接口超时后回读确认新WIP PR **#894** 已生成，承接#810，原PR未关闭。下一步、被否方案及仅供后续授权的部署命令见 `docs/handoffs/2026-09-23-hithink-research-observations-85.md` 和 `inflight/fix-hithink-research-85.md`。未采集/写生产/重载launchd/切8792。

## 红线

- pathspec 提交；合 main 等用户确认；不强推。
- `.venv-workbench/bin/python`。
- 不打上游 API（测试全用假响应）；不写 `db/market_feature_store.duckdb`；不 `launchctl load/unload`。
- 不提交 `.env*` / 密钥 / `*.duckdb`。
