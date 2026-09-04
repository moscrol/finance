# feat/methodology-backtest-p1-gate

树 `/Users/a77/fwp-wt-methodology-backtest-p0`（沿用 P0 的树，分支切换），基座 `gitea/main`=`75bc6033`
（P0 #573 合入后 + 交接回写）。设计稿 `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §3.4「与学习闭环的接法」。
解释器 `.venv-workbench/bin/python`。**未合 main、未强推。** 这一刀改的是运行时默认值与经验卡晋升规则，合入前请过目。

## 这个分支做什么
把 P0 的统计四态接进学习闭环，两处：
1. `checkpoints.DEFAULT_CALIBRATION_MIN_N` 2 → 10。两个样本就给「靠谱 / 偏差大」标签是「一次错误否定一套方法」的机制来源；
   P0 收据附录里的只读消融给了读数（83 可证伪点、69 终态、2 类别：`min_n=2` → 2 类有标签，10 或 20 → 1 类，掉的是 n=2 的「duckdb_flow/市场路径」）。
   `foresight.ForesightOptions.calibration_min_n` 原来写死 2，改为引用常量；四个消费者同闸（`render_calibration_for_prompt` / `prime` / `red_team.weak_categories` / `user_memory.peer_hit_line`）。
2. 经验卡晋升统计门：卡带 `rule_id` 时，`promoted / methodology / promoted_to_code` 要求该规则**最近一次回测收据为 `supported`**，标 `invalidated` 要求 `refuted`；无收据 = 无证据，一律拒；`candidate` 与无 `rule_id` 的卡走原流程。
   `answer-score --save-card --rule-id <id>` 被拒时打印原因 + 下一步、退出码 2、不落卡；放行的卡带 `rule_id / rule_verdict / rule_receipt` 溯源。

## 决策与被否方案
- min_n 取 10 / 否 20（回测默认）/ 消融上两者同结果，10 给新类别更早进校准的余地；否保留 2 / 那就是病灶
- 五处测试夹具改成按常量生成 n 条判定 / 否把 `min_n=2` 显式传进去 / 那等于把旧口径钉在测试里，常量再改还得再改一遍
- 门放在 `build_card_from_score`（纯函数 `gate_promotion` + 抛 `PromotionGateError`），收据查找放 CLI / 否让 services 读文件系统 / 经验卡模块在 prompt 路径上，保持纯
- 无收据时拒绝晋升 / 否放行 / 「没跑过回测」不等于「支持」，放行就是门上开洞
- `promoted_to_code` 也设门 / 否只门 promoted/methodology / 固化进管线是更强的晋升，没证据更不该
- `latest_receipt` 跨版本按 `generated_at` 取 / 否只看最高版本 / 规则升版还没跑收据时，门看的仍是有读数的那份，并在卡的 `rule_receipt` 里说明

## 当前状态
2 个提交（`7e19cb12` min_n、`22afbdfb` 统计门）+ 本交接。改：`intelligence/services/checkpoints.py`、`foresight.py`、`experience_cards.py`、
`methodology_backtest/receipts.py`（`latest_receipt`）、`intelligence/cli.py`（`answer-score --rule-id / --receipts-dir`）；
测试：`test_user_memory.py`、`test_prime.py`、`test_episode_tools.py`（夹具跟常量）、`test_experience_cards.py`（+5）、`test_methodology_backtest.py`（+2）。

## 已验证（本树、`.venv-workbench`）
- 校准相关 6 个测试文件 158 绿（含 `tests/test_red_team.py`）；经验卡 + 回测 + rubric CLI 67 绿
- 真收据实测：`answer-score --promotion methodology --rule-id dual_red_streak3_continuation`（真库结论 not_distinguishable）被拒、退出码 2、不落卡；`--promotion candidate` 放行，卡带 `rule_verdict=not_distinguishable` 与收据路径
- 无收据的 `rule_id`（`nope_rule`）晋升被拒；`latest_receipt` 跨版本取最近、跳过坏 JSON 与 scan 汇总
- ruff 0；`unread-fields` 无新增；`layer_audit` ERROR 0；pre-commit 每次提交全过
- 全量主门禁：见本文末尾追加行

## 未验证 / 已知边界
- 行为变化：类别不足 10 条终态判定时，foresight 提示词、prime 校准行、red_team 弱类别、KC-11 同类胜率行都不再出现；当前真实用户只有「生命周期推演」（n=67）达标，「duckdb_flow/市场路径」（n=2）退出——这是设计目标，不是回归
- `invalidated` 目前没有写入口（jsonl 里手改），门的 refuted 分支只在纯函数层生效，等有写入口再接
- 卡与规则的映射靠人填 `--rule-id`；「纠偏 → 候选规则」的人工登记入口是设计稿另一条 P1，本分支未做
- 门只看最近一次收据，不看收据的 `source_max_trade_date` 是否过期；P2 可加「收据超过 N 个交易日未刷新视为无收据」

## 下一步
1. 用户过目 → 合 PR；合入后 8792 不必切（CLI / services 侧）
2. 剩余 P1：个股标签（`limit_up / first_board / new_high_1y`）；`lifecycle_stage` 人工对照集；纠偏 → 候选规则登记入口；日期精确配对基准率作对照列
3. 若要让统计门在 Workbench 里可见，P2 再谈 `finance_query` 的 `methodology_verdicts` 数据集

## 踩过的坑
- zsh 里 `$(ls a*.py b*.py)` 有一个模式不匹配就整个 `$(...)` 为空，pytest 拿到空参数会跑全量（7 分钟）——多文件跑测试直接列文件名
- 改一个默认常量，散在 5 个测试文件里写死的「2～3 条就够」夹具全要动；写夹具时从常量派生 n 才不会再来一次
