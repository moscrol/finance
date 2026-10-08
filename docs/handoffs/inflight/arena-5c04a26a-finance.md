# arena/5c04a26a-finance 在途交接（质检后续优化）

基线：快进合入 `arena/a3bfea49-finance@d340e3a6`（连板日历修复 + 连续复盘 + 人/Agent证据合同），在其上按质检结论推进。未合并到 main、未部署。

## 本轮改了什么

### 连板日历：离开名单 ≠ 断板
- `board_calendar.py`：断板先算“候选”（前一计划交易日 ≥5 板、当日不在名单），再按个股行情 `fact_stock_daily` 核验：
  - 当日有成交、收盘低于涨停价 → 断板，`verification="traded"`，附 `close_pct_chg`；
  - 当日无成交行/成交额 ≤0 → `no_trade`（停牌或缺行情）；
  - 名称含 ST → `st_scope`（本地名单规则不纳入 ST）；
  - 收盘仍在涨停价 → `closed_at_limit`（名单疑缺，是“名单完整性”的直接信号）；
  - 当日个股行情整体未入库 → `quote_day_missing`；
  - 无行情表的库：保留断板但标 `verification="unverified"`。
  以上不能确认的进入 `high_board_unresolved`（逐日 + 汇总），不计入断板数。
- 前后两日名单 `source` 集合不同 → `high_board_comparison_status="source_mismatch"`，候选全部记为 `source_mismatch` 待核，月度状态 `partial`。
- 今天是计划交易日但收盘未入库 → `calendar_status="pending"`，不再显示“市场数据缺失”，也不把整月打成 `partial`。
- 前端：断板芯片区分“已核行情/未核”；新增“待核”虚线芯片（原因短标 + 完整原因 title）；摘要写明待核数量；`pending` 独立样式与文案；跨页面带新日期进入时月份跟随；切换月份时不再用新月份的星期偏移排旧月份的格子。

### 时间记忆长河（实际入口 RiverHome → `river/RiverWorkbench.tsx`）
- 历史日不在窗口返回数据中时保留所选日并显式提示，不再静默跳到最新日（`DailyRiverDashboard` 也去掉了“找不到就显示第一天”的回退）。
- 刷新同时重取六轨：自定义窗口下不再只刷新日期目录（effect 依赖改为 start/end 值 + 刷新令牌）。
- 板块候选菜单按所选历史日重新排序（`/api/river/entities?q=&as_of=`），不借用最新日热门名单；读取失败明示。
- K 线底座失败、六轨失败、目录失败均有原地重试和说明。

### 连续复盘：为什么没有数据要说清楚
- 矩阵逐日状态：`available` / `empty`（入选但无行）/ `not_in_scope`（当日非重点行业，日报按设计不生成）/ `not_reported`。
- 发动机新增 `engines_status`：`available` / `empty`（进了前三但原日报写“暂无可排序个股”）/ `not_in_scope`（不在前三）/ `not_reported` / `unknown`。
- 合同 `review-evidence/v1` 补充：各组 `selection`（入选条件）、`selection_bias`、发动机以“代码”列为跨日对齐键、`not_in_scope`/`empty` 缺失语义。
- 页面矩阵单元格区分 缺档 / 未覆盖 / 无行 / 未报 / 未列 / 截断外，不再统一显示“—”。

### 发布一致性
- `intelligence/api/static` 已从当前源码重建（含连续复盘与待核 UI），与新构建逐字节一致。
- CI 新增“committed static 与源码构建一致”检查。
- `serve_review_evidence_fixture.py` 改用 `setattr` 覆盖 STATIC_DIR，修复字段契约门禁误报（该门禁在 d340e3a6 上即失败）。

## 已验证（本沙箱，Python 3.11 + requirements-dev.lock，FWP_ALLOW_ANY_PYTHON=1）
- 后端：日历 + 日报复盘 + Workbench API + 交易日：220 passed；全仓 Ruff 通过。
- 前端：25 文件 237 passed；tsc、ESLint、vite build 通过。
- 新测试先在旧代码上确认失败（六轨日期漂移、自定义窗口刷新），再在新代码上通过。
- 门禁脚本：check_path_literals / check_regex_routes / check_unread_fields 通过。

## 未验证 / 仍欠
- e2e：首轮 CI 日历 e2e 失败——夹具建了空 `fact_stock_daily`，断板候选按 fail-closed 归为“行情未入库”待核，不再显示为断板。已给夹具补当日行情（合成高标甲有成交未封板 → 已核断板），并新增停牌待核样本（合成停牌戊 → `停牌/无成交`）及断言。本地（npm `@sparticuz/chromium` 替代浏览器）日历 e2e 6/6 通过；主 e2e 45 通过，`workbench.spec.ts` 的 2 个聊天用例在 d340e3a6 基线上本地同样失败，属本地环境问题，以 CI 为准。
- 真实行情库只读抽样：重点核 `closed_at_limit`（供应商名单缺漏）、`source_mismatch` 频率、停牌高标。
- 远端 CI、正式门禁、部署与回滚；Workbench Agent 实际消费证据合同；归档版本留存；长河观察记录服务端持久化。

## 第三轮（合并 main e3f88f29 之后）

- 新增只读抽样脚本 `scripts/audit_board_calendar_breaks.py`：复用 `build_board_calendar` 的判定（不另写规则），把每条已核断板 / 待核候选与原始行并列（收盘、涨停价、涨跌幅、成交额、前后两日名单来源），并标记 `near_limit_price`（收盘离涨停价 ≤1 分）、`high_pct_but_not_sealed`、`verify_list_completeness`（closed_at_limit）。缺行保持 “—”/null。测试 `tests/test_audit_board_calendar_breaks.py`。
  - 真实库运行：`python scripts/audit_board_calendar_breaks.py --db <market_feature_store.duckdb> --start 2026-07-01 --end 2026-09-30 --md /tmp/breaks.md --json /tmp/breaks.json`
- 连续复盘：
  - “按最近归档选择”真正解除行业固定（此前 ref 会继续发送旧行业）。
  - 截止日不是已收盘交易日时提示窗口实际止于哪天；光标不在窗口内时明示。
  - 迷你走势图标注本窗纵轴范围与缺读数日数，提示不同窗口/指标不可比高低。
  - JSON Pointer 前缀：合同 `citation_rule` 说明相对连续证据响应根；交接包 `response_contract.pointer_base` 说明包内一律加 `/evidence`。
- 验证：vitest 25 文件 238 通过；tsc/eslint/ruff/三项 check 通过；本地 e2e：review-evidence 6/6、river 18/18（calendar 6/6 上一轮已过）。

## 第四轮：复盘证据接入对话 Agent（8792 代码，未部署）

- 设计与边界见 `docs/agent-product-door.md`「复盘证据交给对话 Agent」。
- 后端：`intelligence/services/review_evidence_handoff.py`（坐标、核对、卡片）；`river_review_history.window_fingerprint` 并在响应中给出 `window_fingerprint`；`CreateMessageRequest.review_evidence`；`run_store` 旁挂 ref/receipt；`ResearchToolRegistry.with_opening_prefetch`；`asof_prefetch` 开场消息加复盘读法一句。
- 前端：`ReviewReadingGuide`「带着证据去问答」→ `workbench:review-evidence-handoff` 事件 → App 新建对话、预填单段消息、显示「附带复盘证据」条（可“不附带”），发送时附 `review_evidence`；409/422 显示原因并保留附带。
- 8792 影响：仅在 `ASK_CONTINUOUS_RUNTIME=on`（或 canary+ID）且有模型时可用；未启用时按钮流程会被 409 拒收，不会静默降级。普通消息路径不变。部署时需同时更新后端与静态页：旧后端会静默忽略未知字段，新前端看不到响应里的 `review_evidence: "verified"` 时会提示“服务端未确认接收复盘证据”。
- 测试：`tests/test_review_evidence_handoff.py`、`test_workbench_api.py` 末尾 review 段、`ReviewReadingGuide.test.tsx`、`e2e/review-evidence.spec.ts` 第三条。
