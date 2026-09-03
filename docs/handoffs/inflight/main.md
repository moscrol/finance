# 在途交接 · main

更新：2026-09-03 16:40 CST（0903e 切流）。08-13→09-03 时间线归档 `docs/handoffs/2026-09-03-main-inflight-archive-0813-0903.md`，本文只留接手要的。

## 这个分支做什么

生产基线：合并、8792 切流、台账回填的落点。合入/可拆状态跑 `scripts/worktree_board.py`，不手抄。

## 决策与被否方案

- 切流分两批：#531–#535（零 live 判据）与 #537（生产行为改动）分开切；否一次切完——回滚要能归因。
- 预算 P1 工具侧选菜单裁剪+worker 保活（#544/#545），否 RAG asked 缩短——等 live 读数。
- 弃权率与均分并列不折进总分；判官不可用是协变量（#541）。
- `_recover_finalization` 不动不删：生产零触发，首现时重开。
- 8792 auth 先 off：`cf_access` 缺 AUD 会启动即抛→崩溃循环。

## 当前状态

8792=`f4c03b9ae610`（0903e：web_search 修复、判官拒句账、墙钟用例容差、门禁/PR 脚本）。回滚锚 `~/.finance-runtime/cutover-20260903e-rollback-8792.txt`（回滚目标 `c88c81da5120`），启动器未动（备份仍 `.bak-20260903-admission`）。足迹分支 `wip/mainline-move-footprints-20260903` 待认领。

⚠ **`gitea/main` 已不等于 8792**（此处原写「== 8792」，17:01 起失真）。`f4c03b9a..aa3d87e4` 多了三个 merge，其中两个**是运行时改动**：#562 画像整表回写按长度棘轮（`perspective_learning.py`）、#555 复盘台账落 JSON 真本源（`daily_review.py` + `DailyReportView.tsx`），另 #558 为 chore。合起来 `intelligence/`+`webapp/` 74 文件 / +5417 行。**0903f 切流窗口开着、无人认领** —— 那两张不是能力放大线合的。

另有 0903f 三张 PR open 未合：#566 RAG 超时处置 / #567 工具窗地板 / #568 deep 升档（见 `inflight/spec-capability-amplification-output-gate.md`）。

## 已验证

0903e：health 三读 match、账本 check ok、探针 `run_20260903_162024_399965` rev 自证 / `fact_stock_daily`×4 / degrade 0；readiness 12/13——`market_data_consistency` false 是 16:15 快照定时刷新后到晚间 daily-full 前的**每日常规窗口**，非本批回归。门禁 @`f4c03b9a` 7581P/5F 同一组红、`check_test_receipt` exit 0、webapp 四件套绿。细节 `docs/verification/2026-09-03-cutover-0903e.md`。

## 未验证 / 已知边界

- Cloudflare Access 未建，隧道未开前 8792 不对外。SSE 每连接占一线程（≤10 人可接受）。
- `kb_search` 66% 超时**根因已查清并有修**（#566：except 子句顺序让两个超时处置器成了死代码，超时被判 worker 不可用→回退 CLI 重载 4.3G 模型）。收据 `docs/verification/2026-09-03-kb-search-timeout-root-cause.md`。**「预热后首查仍慢」那条推断已撤回**：修后同机实测 11.93s/13.58s。
- KB 索引 stale（建于 08-31，知识库仓已前移）：#566 修完 `kb_search` 不再超时，但 24 条命中被 `require_fresh` 全丢、`hits=0`。**拿不到证据这件事没被修**，需重建索引，另立单。
- `would_grant<1s` 时无地板工具照旧可见：09-03 三次 live 3/3「web_search 授 0 秒白烧一轮」→ #567 已给 web/news/fetch 补 5s 地板（用户已拍）。
- 消融壳走 legacy `cli ask` 不经 episode 链，弃权效果须会话链重跑。

## 下一步（待用户）

1. 真人步骤：Cloudflare Access（+`/api/health` Bypass）→ AUD 进向导 → ingress+DNS → 启动器 source `alpha.env` → kickstart → `hosted-alpha-gate.md` §3 验收；VPS 给 `user@host` 即装备份+拨测。
2. P1 第二步：D 组 8 道会话链重跑，先看 `judge_unavailable_count`。
3. P4 `sdk_glm` 两臂（剩 `run-reference-loop.sh:48` 走 finance-base-ab）。
4. 08-22 起挂起无后续：V11 派单、黑名单扩展单、V9c `R-20260822-03`（台账 pending）、W2b。

## 踩过的坑

- 另一会话在本会话树里并行改文件（09-03 两次）；开工先 `git status`。
- 探针兑现多行台账要逐行回抄；部署脚本被环境收割时按原参数手工补 switch 行。
