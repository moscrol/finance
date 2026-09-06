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

8792=`d65ed0155eb9`（0907f：#617 LLM 保险丝；#616 修复轮表达槽；#615 分支预算；#612 方向硬门；#610 `sub_research`；#608 max 档、出口 cockpit `:57244`）。回滚锚 `~/.finance-runtime/cutover-20260907f-*`（回 `0399b980`）；启动器备份 `.bak-20260907-pre-max`。收据 `docs/verification/2026-09-07-*.md`。**登录钥匙串 09-06 被重置**（`login_renamed_1.keychain-db`），GLM / 中转 key 未恢复。

## 已验证

0903e：health 三读 match、账本 check ok、探针 `run_20260903_162024_399965` rev 自证 / `fact_stock_daily`×4 / degrade 0；readiness 12/13——`market_data_consistency` false 是 16:15 快照定时刷新后到晚间 daily-full 前的**每日常规窗口**，非本批回归。门禁 @`f4c03b9a` 7581P/5F 同一组红、`check_test_receipt` exit 0、webapp 四件套绿。细节 `docs/verification/2026-09-03-cutover-0903e.md`。

## 未验证 / 已知边界

- Cloudflare Access 未建，隧道未开前 8792 不对外。SSE 每连接占一线程（≤10 人可接受）。
- `kb_search` 66% 超时是切前生产形状；探针首发作废只采复跑。
- `would_grant<1s` 时无地板工具照旧可见：09-03 三次 live 3/3「web_search 授 0 秒白烧一轮」；`kb_search` 刚预热首查超时 3/3。两项待用户拍（能力放大线 inflight）。
- 消融壳走 legacy `cli ask` 不经 episode 链，弃权效果须会话链重跑。

## 下一步（待用户）

1. 真人步骤：Cloudflare Access（+`/api/health` Bypass）→ AUD 进向导 → ingress+DNS → 启动器 source `alpha.env` → kickstart → `hosted-alpha-gate.md` §3 验收；VPS 给 `user@host` 即装备份+拨测。
2. P1 第二步：D 组 8 道会话链重跑，先看 `judge_unavailable_count`。
3. P4 `sdk_glm` 两臂（剩 `run-reference-loop.sh:48` 走 finance-base-ab）。
4. 08-22 起挂起无后续：V11 派单、黑名单扩展单、V9c `R-20260822-03`（台账 pending）、W2b。

## 踩过的坑

- 另一会话在本会话树里并行改文件（09-03 两次）；开工先 `git status`。
- 探针兑现多行台账要逐行回抄；部署脚本被环境收割时按原参数手工补 switch 行。
