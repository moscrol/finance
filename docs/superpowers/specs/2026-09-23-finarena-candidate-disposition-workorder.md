# 2026-09-23 FinArena 候选处置工单（#82）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
来源：`docs/handoffs/2026-09-23-orphan-inventory.md`。无前置单；与其他单可并行。

## 09-23 接手状态

已完成[两路决策页](2026-09-23-finarena-decision.md)，执行方建议本期归档，**等待用户确认，未关闭 #816/#817、未进入工程合流**。本轮只读确认：#817 与 `ops/arena-recovery-gates-0921` 完整文件树相同；对固定 main `626d8a508` 合并预览无冲突，不代表验收通过。旧 NO-GO 报告自述为同一执行上下文离线复核，不是不同执行者的独立签字。

[三条旧真实样本逐条移交 #76](../../handoffs/2026-09-23-finarena-quality-transfer.md)，18/18 原件哈希复验一致；仅登记待授权补充，不扩原六行预算，尤其追问须另批两轮会话协议。最终产品裁决原话待用户确认后回填。

## 背景与动机

FinArena 是「多个金融 agent 同题作答、公开裁判」的邀请试运行模块（`intelligence/arena/` + `intelligence/webapp/src/arena/`），09-20 由 PR #811 引入，09-21 前向为 #816（三处边界修复：loopback 端点校验、远端 run_id 关联、SQLite 榜单读事务），离线 Spec/Quality 复核判 **NO-GO**（P1：`runner.py` 先 `finish_run(status=completed)` 再单独 `add_match()`，中途失败留下 completed run 却 0 个 Match；P2：stale running 无恢复闭环、publish 审核无持久审计）。同日 #817 修了 P1/P2（单事务、`recover-run`、审计事件 + 故障注入测试），作者叶：Arena Python 45P、前端六步、Arena E2E 8P；**没有新组合的完整四叶，没有独立复审，之后无人接手**。

今天核对 [实测]：#817 对当前 main **0 冲突**；25 个非文档文件在 main 中找到 0 行，即 FinArena 完全未落地。#811 已于今日关闭留指针（→ #816/#817）。另有分支 `ops/arena-recovery-gates-0921`（+4，无 PR，「preserve pilot and enforce endpoint, run and snapshot」）与本线相关。

**本单第一步是产品裁决，不是工程**：用户 09-20 曾问「如果你来做金融 agent 评测会怎么做」，FinArena 是那条思路的实现。要么作为 opt-in 模块落地（不接生产、不外呼），要么归档。执行方先把两条路的成本摆给用户拍，拍完再动手。

## 目标

1. 决策页：两条路各一段（落地 / 归档），含工程成本、维护面（webapp `package.json` / `eslint.config.js` / `scripts/check_unread_fields.py` 都被改了）、与 8792 的隔离方式。
2. **落地路径**：#817 + `ops/arena-recovery-gates-0921` 合成一个候选，前向到 main，四叶齐，独立复审（#75）后等用户确认合入；模块默认关闭，不出现在 `research_tool_registry`。
3. **归档路径**：关闭 #816 / #817 留指针，分支保留，把 P1/P2 修复中可迁移的原则（「完成态与产物必须同一事务提交」）沉淀到 `~/agent-memory/10_knowledge/`。
4. 无论哪条路，#811 handoff 里的三份真实样本结论（财务算例 / 追问被证据合同拦成无答案、行情漏查下跌家数）逐条移交 #76 自然质量批。

## 非目标

- ❌ 调真实远程 agent 参赛端点、真实模型作答——本单只做工程与决策。
- ❌ 合 main、切 8792。
- ❌ 借 FinArena 顺手改 `check_unread_fields.py` 的规则——该文件改动只允许是为让 arena 字段过门禁，超出的另立单。
- ❌ 移签 #816 的组合 `b8292d23` 旧收据到 #817（#817 正文明写不得移签）。

## 证据路径表

| 文件 | 看什么 |
|---|---|
| `python3 scripts/gitea_pr.py show 816` / `show 817` 及评论 | NO-GO 报告要点、#817 修了什么、边界声明 |
| `/Users/a77/.finance-runtime/reviews/arena-main-ready-v2-20260921/offline-spec-quality-review.md` | 独立复核报告与故障注入输出 |
| `/Users/a77/.finance-runtime/reviews/arena-main-ready-v2-20260921/evidence/README.md` | #816 作者工程证据索引 |
| `gitea/fix/arena-main-ready-0921:docs/handoffs/inflight/fix-arena-main-ready-0921.md`、`…:docs/handoffs/inflight/feat-finance-arena.md` | 现状、三份真实样本结论 |
| `git diff --stat gitea/main...gitea/fix/arena-recovery-0921` | 25 个非文档文件全集 |
| `git log gitea/main..gitea/ops/arena-recovery-gates-0921 --stat` | 无 PR 分支的 4 个提交在补什么 |
| `docs/agent-product-door.md` | 新增门 / 引擎 / 积木要登记的位置 |

## 步骤

1. 开工三连 + `git fetch gitea`；读上表前四项。
2. 写决策页 `docs/superpowers/specs/2026-09-23-finarena-decision.md`（两条路各一段 + 推荐），贴到 #817 评论，等用户拍。
3. 落地路径：`git worktree add /Users/a77/fwp-wt-arena-0923 gitea/fix/arena-recovery-0921`；`git merge gitea/ops/arena-recovery-gates-0921`（看是否已包含）；`git merge gitea/main`；跑 `intelligence/tests/test_arena.py` + 全仓四叶 + `pnpm exec playwright test -c playwright.arena.config.ts`。故障注入用例（进程在 `add_match` 前退出）必须仍红→绿可复现。
4. 归档路径：`python3 scripts/gitea_pr.py close 817 --pointer-file <指针>`（指针写明分支保留、可迁移原则去向），#816 同理。
5. 两条路都要：QUEUE.md / INDEX #82 状态行 / inflight ≤3K。

## 验收

- [ ] 决策页存在且 #817 评论有链接；用户裁决原话回填决策页。
- [ ] 落地路径：`merge-tree` 干净；四叶收据 revision == head、`dirty=false`；Arena E2E 8P；`python3 scripts/check_unread_fields.py` 在合流树 exit 0。
- [ ] 阳性对照：把 `runner.py` 单事务拆回两步，故障注入测试至少一条红。
- [ ] 归档路径：#816/#817 关闭评论含替代物与失效对策；`10_knowledge/` 有沉淀文件并在项目笔记留一行索引。
- [ ] INDEX #82 状态行已改。

## 红线

- pathspec 提交；合 main 等用户确认；不强推；关闭必留指针。
- 解释器 `.venv-workbench/bin/python`；前端 `pnpm`。
- 不调真实参赛端点、不写生产、不切 8792。
- 不提交 `arena-evidence.png` 以外的二进制；`.gitignore` 改动逐行说明理由。
