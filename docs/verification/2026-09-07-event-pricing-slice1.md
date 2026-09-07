# 事件定价第一刀 · 验证（2026-09-07 晚）

设计稿：`docs/superpowers/specs/2026-09-07-event-pricing-slice1-calendar-reaction-design.md`（待拍板六条全按推荐执行）。
代码：`intelligence/services/event_pricing/`（`params / schedule / classify / event_calendar / anchors / reaction / readouts / store`）、
`scripts/event_reaction.py`、`intelligence/tests/test_event_pricing.py`（29 条）、参数 `methodology/events/event_reaction_params.v0.1.json`、
官方日程 `references/calendars/official_release_schedule.{2025,2026}.json`。
真库读数：`methodology/receipts/event_pricing/2026-09-08-ev-v0.1_dd4c4389.{json,md}`（gitignore，可重建）。
解释器 `.venv-workbench/bin/python`；主树 HEAD `88363e43`（代码脏：本刀新增文件 + BP 相关三个未提交文件）。

> **读数不是结论。** 本文只记「验收条过没过」与「真库跑出来的形状」，不解读任何一条四态。

## 1. 验收（设计稿 §8）逐条

| # | 条 | 结果 | 证据 |
|---|---|---|---|
| 1 | 两次重建三张表哈希相等 | ✅ | `test_rebuild_is_idempotent`（首跑抓到横截面并列排序不稳，已按实体代码定序） |
| 2 | 分类器正 / 反例；未匹配 100% 进 `unparsed` | ✅ | `test_classifier_positive_and_negative_examples`（财新 PMI / 香港 CPI / FOMC 纪要 / 发布会 → unparsed）；真库 unparsed 1966、ambiguous 1 |
| 3 | 反应日：FOMC 美国周三 → 周四；周五盘后金融数据 → 周一；周日 PMI → 周一；假日顺延 | ✅ | `test_reaction_day_rules`、`test_calendar_merge_grades_and_conflict`；真库 FOMC 2025-01-29 → 02-05（春节休市）|
| 4 | `latest_known(cn_cpi, 2026-07-08) = 2026-05`；`(cn_cpi, 2026-09-07) = not_yet_released / 09-09`；返回无数值字段 | ✅ 形状 / **真库读数见 §3** | `test_latest_known_shapes_and_no_numbers`；真库：07-08 → `period=2026-05, release 06-10, next 07-09`；09-07 → `period=2026-07（08-09 发布，08-10 知）, next 2026-09-09` |
| 5 | 前视夹具：价格后移一天只改事后侧 | ✅ | `test_lookahead_mutation_shifting_prices_changes_only_forward_side`：D0 fwd_5 从 1.03⁵−1 变成 0.96·1.03⁴−1 |
| 6 | 板块 `fwd_return_5` 与 `history_outcomes` 同键相等 | ✅ | `test_positive_control_windows_exclude_d0_and_match_outcomes` 对账 0 条不等 |
| 7 | 形状读数经 `stats.readout`，四态齐，N<10 → insufficient_n；expectation / state_only 分表；收据无禁词 | ✅ | `test_receipt_uses_stats_readout_and_has_no_forbidden_words`；另加**族内 BH**（六形状一族，`verdict_single` 与 BH 后 `verdict` 并列） |
| 8 | 横截面只含板块 / 申万一级，无个股代码 | ✅ | `test_cross_section_has_no_stock_codes` |
| 9 | 三代理：前两列有值率、第三列 100% `gap{not_wired}` | ✅（有值率见 §3） | `test_shape_semantics_and_status`；真库 `crowding_pct_dm1` 对 ok 记录有值率见收据 |
| 10 | `source_grade` 分布、conflict 计数可查、无官方日程的类 0 条 official | ✅ | `test_source_grade_distribution_in_receipt`；真库 cn_credit_data / policy / industry 全 editorial |
| 11 | 参数或日程改动 → 版本变 | ✅ | `test_version_changes_with_params_and_schedule`、`test_anchor_build_refuses_stale_calendar_version` |
| 12 | pytest / ruff / 门禁 | ✅ | 见 §4 |

## 2. 真库跑出来的形状（ev-v0.1+dd4c4389，主库 max 2026-09-07，旁路日历 2024-12-20 → 2026-09-02）

日历 278 行：cn_cpi_ppi 48 / cn_pmi_official 24 / fomc_decision 16 / cn_lpr 25（含 4 条 rule_derived_future）/ cn_credit_data 7 /
policy_release 52 / industry_event 107。来源等级 official 74、both 26、rule_derived 9、editorial 162、editorial_ambiguous 4；**conflict 0**。

锚点 1054：market 77（cpi_ppi 20 / pmi 20 / lpr 21 / fomc 13 / credit 3），sector 977（industry 796 / policy 181）；`unmapped_sector` 0。

反应记录 1054：ok 222、pending 25、**missing 807**。missing 几乎全是板块锚点（803）——原因见 §3 第 1 条，不是 bug。

四态（族内 BH 后）：五个 market 类全部 `not_distinguishable`（N 13–21）。sector 类 `industry_event` state_only n=111：
`pre_down_post_up` 23/111 vs 基准 481/4303 → supported；`continuation_up` 3/111 vs 430/4303 → refuted；其余不可区分。
`policy_release` n=39：`continuation_up` 单次 refuted、BH 后 not_distinguishable。**这些是读数**：sector 类是非预期事件（state_only）、
编辑挑选过板块（谁在事件里谁被打标）、且只覆盖 2026-06-30 起的两个多月——见 §3。

`latest_known @ 2026-09-02`：cn_cpi / cn_ppi 最新 2026-07（08-09 发，08-10 知）、下一期 09-09；cn_pmi_official 最新 2026-08（08-31）、下一期 09-30；
cn_lpr 最新 2026-08、下一期 09-21（rule_derived_future，周末顺延）；fomc 最新 07-29、下一期 09-16；cn_credit_data 最新 2026-07、下一期 —（无日程，如实）。

## 3. 数据现实（跑出来才知道的，都进了缺口表或收据）

1. **板块价格序列换了宇宙。** [实测] `.TI` 系列 223 个板块 2024-12-25 → **2026-07-24 止**；`.FP` 系列 407 个板块 2026-04-29 起（密集覆盖从 06-23）。
   编辑日历的 `sectors` 全是 FP 代码 → 07 月之前的板块锚点没有价格行 → `missing`（缺口表 `reaction/no_price_row_on_reaction_day` 757 条）。板块级读数实际只有 2026-06-30 起。
   **按名映射已核、结论是不能做**（2026-09-08 重叠窗口实测）：131 对同名 FP / TI 板块，重叠 20–43 个交易日，**无一对逐日涨跌幅相等**；
   最大偏差中位数 0.57pp，68 对 > 0.5pp，最差「机器人」9.11pp、「锂电池」相关系数 0.497；成交额相对差中位数也在两位数百分比。
   两套是不同成分篓子恰好同名（FP 内部还有 8 个重名）。板块级历史只能各算各的，已登进词表歧义。第二刀第一条拍板由此关闭：**不桥**。
2. **编辑日历 FOMC 记的是北京日期**（决议次日），对它套「美国日期 +1」会双重顺延。参数加 `editorial.reaction_rule=same_day_or_next`，官方骨架吸收后全部 `both`；
   两日会议的第一天那条作别名吸收并记 `absorbed_adjacent_editorial`（9 条，含 3 条明显错日的 CPI 编辑行：4 月 CPI 记到 05-20、6 月 CPI 记到 07-24）。
3. **金融数据类同所属期两天两个日期**（3 月 M1 04-10 / M0 04-13；6 月 07-10 / 07-14），无官方仲裁 → 双双 `editorial_ambiguous`、不入锚点（4 条）。
   `cn_credit_data` 锚点只剩 3 个。这是 fail-closed 的代价，如实。
4. `fact_market_daily.sh_index_pct_chg` 在 **2026-08-17 为 NULL**（416 行里 2 行空，另一行是 2024-12-20 首日）→ 含该日的窗口全部 missing，
   杀掉 3 个 market 锚点（08-10 CPI、08-11 金融数据、08-20 LPR）。主库数据缺口，不在本刀补。
5. 编辑日历里 CPI 行混境外（香港 / 新加坡）、FOMC 行混纪要 / 讲话、M2 行混澳门——排除词全部命中，进 unparsed。
6. 官方日程：统计局 2025 表公布于 2024-12-30（页面标注）；2026 表栏目页无公布日，按惯例取保守上界 2025-12-31；美联储页面亦无公布日，同法取上界。
   LPR 接口只给一年历史（2025-09-22 起 12 期），更早 9 期按规则派生（`rule_derived`），2025-04-21 / 07-21 两次顺延与规则一致。
7. ~~旁路日历止于 09-02~~ **2026-09-08 00:30 已重跑** `build-labels` → `outcomes` → `event_reaction.py all`：日历到 2026-09-07（416 日），
   事件日历 279 行、锚点 1054、反应 ok 223 / pending 16 / missing 815，`latest_known` 各指标不变。
   **注意版本**：重建前旁路库 labels 是 `v3-…-market_stage_normalized`（来自未合入分支 `fix/g05-market-stage-normalize` 的代码，2026-09-06 构建），
   本树 HEAD 的 `LABEL_VERSION` 是 v2，重建后旁路库回到 v2——`market_stage` 标签未归一（两套写法并存），事件读数的按阶段分桶名随之变为原始供应商字串（只作对照，不影响四态主表）。
   G-05 分支继续工作时用它的代码重跑 `build-labels`/`outcomes`（各 2–3 s）即可；旁路库本就是「任何时候可删可重建」。
8. `UBIQUITOUS_LANGUAGE.md` 已写入六条新词（事件锚点日历 / 反应日 / 事件反应 / 预期内事件 与 非预期事件 / 形状标签 / 已定价代理）与四条歧义登记（「定价」两义、「事件」三源、口语不是标签、编辑 FOMC 是北京日期）。

## 4. 门禁

- `.venv-workbench/bin/python -m pytest intelligence/tests/test_event_pricing.py` → 29 passed。
- `ruff check --config=ruff.toml`（新增文件）→ All checks passed。
- `scripts/layer_audit.py` → ERROR 0；`scripts/check_path_literals.py` → 无新增；`scripts/check_unread_fields.py` → 无新增（首跑抓到 `ScheduleEntry.source_url` 写了没人读，已删——URL 只留在文件头 `sources[]` 与 build meta）。
- 全仓 pytest（`.venv-workbench`）：**8010 passed, 8 skipped, 1 xfailed**，1 条 deselect——
  `test_conversation_orchestrator.py::test_completed_stream_persists_human_readable_answer` 在本树 HEAD 上就红：
  答案里多出 `market_watch_pack` 的「## 指定日盘面组件包 · 隐式最新交易日：2026-09-07」块，把 `MARKET_FEATURE_STORE_DB` 指到不存在的路径仍红，
  与本刀无关（orchestrator 不 import `event_pricing`）。留给该组件的负责人。
- 其余门禁：`audit_dataset_registration`（事件表在旁路库、不在 `schema.sql`，不触发）、`audit_tool_reachability` 均通过。

## 5. 未闭合 / 第二刀

- ~~板块序列 FP ↔ TI 的名称映射~~ 已核：不同义，不做（§3 第 1 条）。板块级 N 只能靠时间积累（FP 序列每天 ~403 个板块，横截面是它转起来的地方）。
- `consensus_stage_dm1` 接线（G-02b 舆论轨 provider）；资金列。
- 20 日窗（拍板：v0 不做）。
- `EventReaction` 改走 `river.window` 并带 `pit_grade`（G-02c 契约落地后的迁移义务）。
- 主库 2026-08-17 指数涨跌幅 NULL 的回补（数据侧）。
- 词表六条新词与两条歧义（设计稿 §9 第 6 条）尚未写入 `UBIQUITOUS_LANGUAGE.md`——等你过一眼真库收据再写。
