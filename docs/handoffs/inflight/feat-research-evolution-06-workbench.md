# feat/research-evolution-06-workbench 在途交接

最近更新：2026-09-14 · HEAD 99d6e193（+未提交第五轮返修；提交后 HEAD 见 git）· 基于 b481804c

## 当前任务（第六轮 QC 复审等待中）

第五轮 P1 返修 V1–V4 已完成、全绿待复审。根因一句话：第四轮把「文本」当身份、「同会话有消息」当因果；
时钟域分裂下唯一可信归属坐标是**请求实例（item_id + request_event_id）**。

## 本轮改动

- 消息合同 `maintenance_launch {item_id, request_event_id}`（首轮可带）；Message 台账同名字段，revise 保留。
- continuation 载荷带 `request_event_id`（= rejudge 事件 event_id）；App rejudge 流程回传坐标。
- `bind_pending_rejudge_run` 只认坐标（`_verify_launch_coordinate` 四条件：rejudge 台账回查会话/项/requested/当前代）；文本匹配（`_is_launch_utterance`/`_request_launch_texts`）**已删除**。
- V4：运行中登记前查旧代归属，已登记 → 400。R7 合同不变（无消息 running run 可登记）。
- V1：终态补偿 `_compensate_terminal_link` 只认源消息当前代坐标（同一验证器），时间窗检查弃用。
- V3：auto-pick 收窄——同会话待复核 >1 必拒（ERR_DEPENDENCY_MISSING+pending_item_ids+hint）；
  已被其他闭环消费的 judgment 从候选排除。U4 闸（attempts>1/last_failure）保留在前。
- 产品入口：视图 `maintenance.run_links`（含 run_status）；面板「确认成果」（rejudgment_requested 项：
  选当前代已完成 run + 成果判断 → link_run 带 new_judgment_ref）。运行中带 ref 会被忽略（文档化，不对运行中开放）。
- 旧探针 setup 升级带坐标（round-3 T1 / round-4 U2/U3，裁决许可，核心断言不动）；新四针原样。

## 验证（本机多树并发，收据按 tree 区分）

- 新四针 4/4 原样；组合门禁（5 套件+三轮历史探针）127 passed。
- 全仓裸 pytest **10051 passed / 0 failed**，收据 `~/.finance-runtime/test-receipts/20260914T033709Z-99d6e193.json`。
- 前端 92 tests / lint / typecheck / build 全绿；e2e 31 passed / 2 skipped。
- 勘误：第四轮 10043 全量收据实为 `20260913T202240Z-b481804c`（旧交接 T201520Z 写错）。

## 细节快照与证据

- `docs/handoffs/2026-09-14-re06-round5-v1-v4.md`（改动矩阵、被否方案）。
- `docs/verification/re06-ecd90a3c/`：REVIEW.md（裁决原文）+ REWORK.md（返修说明）+ 探针。

## 合并顺序（通过后再走，等用户确认）

spec 链 → 主链原序；不合并、不部署、不动其他 worktree。

## 留痕（下轮注意）

- judgments 写入侧不扩展（登记依赖）；归属只靠坐标+唯一性。
- 观察器终态收尾无 payload：显式 ref 只走 HTTP link_run。
- 探针台账：round2 在 ~/.finance-runtime/reviews/research-evolution-06-ba10747d/，round3/4/5 在 docs/verification/re06-*/。
