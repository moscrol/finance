# 06 研究进化 · 第五轮 QC 返修（V1–V4）收口说明

对应裁决：`docs/qc-re06-ecd90a3c` 分支 `docs/verification/re06-ecd90a3c/REVIEW.md`（候选 99d6e193 / 代码 ecd90a3c）。
探针原样回放（未改判定路径、未改断言阈值），旧探针 setup 按裁决许可升级为携带真实坐标。

## 一句话根因

第四轮把「文本」（full_prompt 逐字 / label 前缀）当请求身份、把「同会话有消息」当因果证明。
文本不是身份（跨代 full_prompt 逐字相同）、消息存在不是因果（普通聊天也有消息）。
时钟域在验收环境刻意分裂（领域 FakeClock vs 真实时钟），时间窗检查一律不可用——
**唯一可信的归属坐标是请求实例（item_id + request_event_id）**。

## V1（1270–1292 补偿登记认「有消息」）→ 补偿只认源消息坐标

- 消息合同新增 `maintenance_launch {item_id, request_event_id}`（首轮也能携带，不依赖 origin run）；
  落在 `Message.maintenance_launch`（`conversation_store.py`），revise 时随原文保留。
- `_compensate_terminal_link` 重写：run 的源用户消息必须携带指向该项**当前代**的坐标，
  与接受侧共用同一验证器 `_verify_launch_coordinate`（rejudge 台账回查 owner/会话/项/代际）。
  旧聊天（无坐标）→ 400，项不动、无登记行。
- 回归：`test_v1_old_ordinary_message_cannot_be_compensated_into_new_request`（仓内）+ 探针 V1 原样回放。

## V2（987–1009 文本匹配不分代际）→ 文本匹配整体移除

- `_is_launch_utterance` / `_request_launch_texts` 删除；`bind_pending_rejudge_run` 只认坐标。
  跨代逐字相同的 full_prompt 不再产生任何关联。
- continuation 载荷新增 `request_event_id`（顶层 + inherits），值就是 rejudge 落盘事件的 event_id。
- 回归：`test_v2_cancelled_generation_prompt_cannot_claim_replacement` + 探针 V2 原样回放。
- 旧探针 setup 升级（裁决许可）：round-3 T1、round-4 U2/U3 的启动消息带 `maintenance_launch`，
  核心断言（快速终态可收尾、跨会话拒绝）不变。

## V3（924–945 首次复核跨项自动认领）→ auto-pick 收窄 + 面板确认入口

- auto-pick 新闸：同会话待复核项 >1 → 一律拒（`ERR_DEPENDENCY_MISSING`，detail 带 pending_item_ids + hint）；
  首次复核不豁免——「首次」只证明本项没撞自己别代，证明不了不撞别人的成果。
- 已被本会话其他闭环消费的判断（rejudgment_linked 的 new_judgment_ref）从候选里排除——顺序确认也不串单。
- 显式确认的产品入口闭环：视图投影新增 `maintenance.run_links`（补 run_status）；
  维护面板对 `rejudgment_requested` 项开放「确认成果」（选当前代已完成 run + 成果判断 →
  link_run 带 new_judgment_ref，服务端闸门照旧）。面板单测 2 条。
- 回归：`test_v3_first_attempt_cannot_consume_other_items_judgment` + 探针 V3 原样回放；
  Q2 单条待复核自动关闭不变。

## V4（运行中登记绕旧代闸）→ 登记前置旧代检查

- `_link_run_event` 运行中分支：写入前查既有归属，run 已登记在上一代 → 400（不转挂）。
  旧代检查从终态分支前移到登记分支，运行中与终态共用同一代际纪律。
- 回归：`test_v4_running_registration_obeys_stale_generation_gate` + 探针 V4 原样回放；
  R7（运行中裸 run 可登记）合同不变。

## 证据

- 新四针 `test_review_round5.py`：**4 passed**（原样）。
- 组合门禁（api/falsification/io/store/rework + 三轮历史探针）：**127 passed**。
- 全仓（裸 pytest，与上轮 10043 同口径）：**10051 passed / 0 failed / 77 skipped / 2 xfailed**，
  收据 `~/.finance-runtime/test-receipts/20260914T033709Z-99d6e193.json`（本机多树并发跑测，
  收据按 tree 区分，本树 revision 均为 99d6e193）。
- 前端：lint ✓ / typecheck ✓ / **92 passed**（含确认入口 2 条新增）/ build ✓；e2e **31 passed / 2 skipped**。
- 勘误（裁决附言）：第四轮 10043 全量收据编号实为 `20260913T202240Z-b481804c`，此前交接写 T201520Z 有误。

## 明确没做 / 留痕

- `judgments.record_judgment` 写入侧不扩展（登记依赖）：时间窗只保留为弱闸，坐标与唯一性才是归属依据。
- 运行中 link_run 携带 new_judgment_ref 会被忽略（终态折回时才读）——面板只对已完成 run 开放确认，合同内无触发面。
- 观察器终态收尾（fold_run_terminal）的显式 ref 入口不变：payload 传 ref 的显式确认走 HTTP link_run。
- 快照不重建（m08）；多会话同题竞合保持原状（i10 注册表）；合并等用户确认。
