# 在途交接 · main

更新：2026-09-08 11:30 CST（评审整改·授课框架一致率配对检验）。对 09-08 评审「46.6% 是训练期撑起来的、验证集被当选择集用」跑了 McNemar：A=`6c00d6c2` / B=`d3350cd1` 在同一快照 `/tmp/mfs-snap2.duckdb` 上重建，**验证期 159 天翻 22 天（15 对 7）p=0.13，训练期 45 对 3 p<10⁻⁶**；旁路库快照里数出 `tf-v0.2` 下 29 个版本各读过一次验证期。结论：+4.7 点分不出真涨与噪声，全期 46.6% 不得单独上游引用，写法见收据 §0。新增 `scripts/teaching_framework_paired_compare.py` + `stats.mcnemar_exact`（6 测试，变异 2 红）。slice2 spec 状态行加了限定句。细节 `docs/verification/2026-09-08-teaching-framework-mcnemar.md`。同批：`feat/event-pricing-slice1` 已推 gitea（此前只有本地一份）；g05 / event-pricing 两张 PR 与 314 天回补工单见后续行。

更新：2026-09-08 02:10 CST（0908b 切流）。8792 `af370f529681 → 0060da5c1a08`（只带 #656：判官窗与单次帽跟合同档位走，max 档 75s/150s，`R-20260908-01`）。三项验证：readiness 13/13、health 三读 match、探针 `run_20260908_020235_111517` completed / rev 自证 / judge passed / `fact_stock_daily`×4 / degrade 0；**判官收据 `timeout_configured=75.0`——台账首读命中**。门禁 @`0060da5c` 8162P/0F、ruff 0、webapp 四件套绿、`check_test_receipt` exit 0（在快照树里跑）。回滚锚 `cutover-20260908b-judge-window-rollback-8792.txt`（回 `af370f529681`）。生产变化只有判官帽/窗放宽（50→75 / 50→150）。同晚立稿未上线：写作成本 × 三处预算协调改（#657，实施中）。细节 `docs/verification/2026-09-08-cutover-0908b.md`。

更新：2026-09-08 00:40 CST（0908a 切流）。8792 `b594a5e7f8ae → af370f529681`（#642/#644/#647/#651 + 两张台账 + 他人的 #645/#646/#648/#650/#652）。三项验证：readiness 13/13、health 三读 match、探针 `run_20260908_003653_195370` completed / rev 自证 / `fact_stock_daily`×4 / degrade 0 / 数据日 09-07。门禁 @`2c5e81ba` 8158P/0F、`check_test_receipt` exit 0、webapp 四件套绿。回滚锚 `cutover-20260908a-core-stock-wo32-rollback-8792.txt`（回 `b594a5e7f8ae`）。备份 `~/backups/gitea-20260908-post651.tar.gz`。坑：bootout 后立刻 bootstrap 报 error 5，等注销落地再起。细节 `docs/verification/2026-09-08-cutover-0908a.md`。

更新：2026-09-08 00:30 CST（工单 #32 合入）。`fact_stock_daily` 五天坏数据（06-22/06-23 半数无价、07-20/08-06 整天次日复制、**08-13 北交所 335 行是次日盘中价**——后者是新 QA 规则量出来的）沪深部分已修并验收（fupanhui 核心 50 只四天 50/50、总额比 0.9998~1.0）；三层拦截入库（快照 `f297` 日期闸拒写 / QA「相邻日复制」+「写入时刻越过下一交易日开盘」全历史扫描 / 日门禁复制检查）；runbook 坑⑤原文声称的 QA 检查从未实现，已改写。特征层 06-22~09-07 重算；周期阶段模型产物在修好的数据上重训替换（CV 43.7→41.6%，三天标签不变）。批次门禁 main tip `2c5e81ba150a` **8158P / 76S / 1xfail**、ruff 0、webapp 四件套绿、`check_test_receipt` exit 0（收据 `20260907T162407Z-2c5e81ba.json`）。**北交所七天**（#32 五天 + 上一单卡住的 09-03/09-04）等 push2his 解封，轮询 `/tmp/wo32_bj_after_unblock.py` 通了自动补，随后上一单 `local_chain_finish → mainline → core_leader` 链自动续跑；`~/fwp-wt-stock-daily-fix` / `~/fwp-wt-backfill-qa-gate` / `~/fwp-wt-core-stock` 三棵树被这些轮询引用，**先别拆**。**8792 仍未切，待裁决**。细节 `docs/handoffs/inflight/fix-stock-daily-misdated-snapshot.md`。

更新：2026-09-07 22:50 CST（核心个股批次验收）。#642 → #644 → #647 堆叠链独立复算后合入；质检推翻 #647 两条结论并随枝修补（07-20 / 08-06 个股日线是次日复制而非「快照偏小」→ 立单 #32；置换检验噪声底量纲错，「噪声内」改「按前瞻收益显著有害」）。批次门禁 main tip `f5805c72db66` 干净树 **8143P / 76S / 1xfail**、ruff 0、webapp 四件套绿、`check_test_receipt` exit 0（收据 `~/.finance-runtime/test-receipts/20260907T144519Z-f5805c72.json`）。**8792 未切，待裁决**：main 领先 8792（`b594a5e7f8ae`）多张与本批无关的合并。裁决全文在 #647 评论；细节 `docs/handoffs/inflight/feat-core-stock-local.md`「质检修补」节。

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

8792=`af370f529681`（0908a 切，= main tip，见顶部更新行；上一版 `b594a5e7f8ae`）。此前：8792=`b594a5e7f8ae`（main `e1d22b89` 比它多 #632 spec / #635 lean / #636 折叠——两刀 env 缺省关、零行为差异，未切；0907i：#628 预算注入加派发节奏（分支跟、父臂不跟，见收据 §12），main tip 同时带 #627 授课框架；回滚锚 `cutover-20260907i-pacing-rollback-8792.txt`（回 `d4cb6484`）；此前 0907h：#623 L3 互动易答复 + 「无法解析公司」指令，启动器 `FINANCE_L3_COMPANY_CMD` 加 `irm_szse`，备份 `.bak-20260907-pre-irm`，回滚锚 `cutover-20260907h-l3irm-rollback-8792.txt`（回 `1010970acc85`）；#622 frontier 向量；此前 0907g：#619 分支秒按墙钟记一次 + 父臂预留尾段 + 分支契约 `branch_findings` + 分支级 trace；此前 0907f：#617 LLM 保险丝；#616 修复轮表达槽；#615 分支预算；#612 方向硬门；#610 `sub_research`；#608 max 档、出口 cockpit `:57244`）。回滚锚 `~/.finance-runtime/cutover-20260907g-branchtrace-rollback-8792.txt`（回 `d65ed0155eb9`）；启动器未动，备份 `.bak-20260907-pre-max`。收据 `docs/verification/2026-09-07-branch-level-trace.md`（切后探针 `probe-cutover-0907g/run_20260907_123827_249342`：judge repaired、`judge_unavailable_count=0`、`content_degraded_count=0`、分支 3/3 `model_finish`、父账本秒分支前后 525.3 → 525.3）。**登录钥匙串 09-06 被重置**（`login_renamed_1.keychain-db`），GLM / 中转 key 未恢复。

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
