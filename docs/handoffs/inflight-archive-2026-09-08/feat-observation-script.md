# feat/observation-script

## 这个分支做什么

终局 spec `2026-09-06-personal-research-calibration-endstate-design.md` 的 V1 第三件：
**观察剧本对象 + 合规硬门 + 带读管线 + T+1 回检登记**（roadmap G-03 与 G-12a 的前半）。

产品语义：观察剧本回答「明天要看什么，以及什么条件会让它升级、降级或放弃」，**不回答「明天买什么」**。
它是「第二天的方向」这类提问的产品答案——翻译成可回检的观察项，而不是拒绝对话。

新增 `intelligence/services/{compliance_gate,observation_script,guided_reading}.py`；
改 `checkpoints.py`（`object_type` 三类判断轨对象）、`userspace.py`（`observation_scripts_path` property）、
`river.py`（`to_dict()` 补 `alias_applied`）、`cli.py`（`observation read/confirm/skip/list`）、
`scripts/validate_marketing_contracts.py`（接同一份合规词表）。测试 74 条。

## 当前状态

**未提交给用户合并、未切 8792。** 收据 `docs/verification/2026-09-06-observation-script-g03.md`。

⚠ **基线不是 main**：本分支从 `feat/river-slice-v0@8e3383c8` 起，因为 G-03 依赖那条分支上尚未合并的
`river.slice`。`feat/river-slice-v0` 自己也未合（相对 `gitea/main@4ed8b62c` 领先 4 个提交）。
**合并顺序必须是 river-slice-v0 先、observation-script 后**；单独把本分支合进 main 会因为缺 `river.py` 而炸。
两棵树都在主工作树 `/Users/a77/finance-workspace-private` 上（未另开 worktree），主树还带着
BP 相关的未跟踪 / 未提交改动（`docs/bp/*`、`UBIQUITOUS_LANGUAGE.md`、`scripts/build_bp_public.py`），
**那些不属于本分支，提交时逐个 `git add`，不要 `git add -A`**。

## 三条设计取舍（改这块代码前先读）

1. **不新开回检引擎**。剧本确认后登记进既有 `checkpoints.jsonl`（`object_type=observation_script`），
   到期由既有 `checkpoint recheck` + resolver 判。红线是「不建第二套台账」——判断轨已经有一套
   可证伪点机制，再造一套就有两个胜率口径。
2. **回检判「变量是否按条件触发」，不判涨跌**。所以机检规格走 `market_daily`（盘面字段阈值），
   不走 `stock_return`。没有机检条件的剧本到期是 `unverifiable`（非终态、不计胜率、下次仍进队列），**不猜**。
3. **`late` 是标记不是拒绝**。晚登记照样入台账（用户的记录不该被吞），但 `enters_calibration` 为假。
   判不出登记时刻时按 late 处理——不能证明及时，就不能算及时。

## 两个实测发现（写给下一个人，别再踩）

### 带读会把个股节点渲染成名单

真库第一次跑，带读被自己的用词 lint 拦下 22 处 `E_STOCK_SCOPE`。`_stock_track`（成分股按成交额降序 10 条）
和 `_theme_track`（`fact_theme_limit_stock_daily` 涨停节点）**两条轨都在发个股级对象**。

数据层管它们叫「节点，不是推荐名单」，这话在 river 那个**查询面**上成立；但带读是**小白产品面**，
十条带涨幅的个股行渲染出来读者看到的就是名单。带读因此把个股级对象折叠成计数 + 标签，
判据按**对象形状**（payload 有 `stock_ts_code` / ref 含个股代码）而不是轨名——按轨名收边界，
下一个 provider 接进来就漏。可迁移的一条：**同一份数据在「操作者查询面」和「小白产品面」上的合规边界不同，
边界要画在产品面，不能指望读者理解「这不是推荐」。**

### 按自然日判 late 会把周末补课判成迟到

周五的剧本周六补做，按自然日 +1 就是 late——但周五收盘到周一开盘之间没有交易，用户看不到任何后续行情。
`default_next_open` 因此跳周末，`default_due` 用同一条规则。节假日仍从严：**本库没有交易日历表**
（实测 `dim_*` 只有板块维度），`next_trading_open(db)` 只能解历史日期——库里最新一天就是已收盘的交易日，
所以「今天登记今天的剧本」这条主路径必然回落到周末规则。要覆盖节假日得先有日历表，本刀不造。

## 下一步（按依赖顺序）

1. **合并顺序**：`feat/river-slice-v0` → 本分支。合前在干净树跑全量 + `check_test_receipt --expect-revision`。
2. **带读接进每日复盘**（`market_watch_pack` / `exports/<date>-daily-agent.md`）：这一刀才让
   「关掉后逐字节不变」这条验收变得非平凡——现在它平凡成立（没人调用带读）。接线要自带 diff 收据。
3. **G-01 授课框架母本**（创始人写）：写完后带读的「判读」段才有内容，对外才能说「授课框架带读」。
   在那之前所有物料只写「带读管线跑通」。
4. **G-12a 后半**：判官「不得出现概率数字」，`compliance_gate.scan(codes=...)` 接口已备好。
5. **G-09**：胜率面板按 `framework_version × market_stage × object_type × horizon` 分列（依赖 #24 与 G-05）。
   本刀只保证 `object_type` 在**登记时**写下；存量记录进 `unknown_legacy` 单独一格，不折进 `judgment`。
