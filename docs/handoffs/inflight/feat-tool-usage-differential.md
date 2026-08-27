# 在途交接 · feat/tool-usage-differential

更新：2026-08-27 · **两份工单已落，均为 docs-only，未合 main、未切端口。**

## 一句话

一轮 harness 审查 + 一轮产品面审查的产出，各收口成一份可认领工单，
台账号与工单同提交（crosswalk 正向门要求），**两件互相独立，可各自领单**。

## 现状

- 分支 `feat/tool-usage-differential`，已 push gitea，PR 未开。
- 基座 `gitea/main@fea0633e`。干净树 `/Users/a77/fwp-wt-tool-usage-differential`，**用后待删**。
- 两个提交，均 docs-only，八道 pre-commit 全绿：
  - `be00f83c` 工具「授权→调用」差值遥测工单 + `R-20260827-08`
  - `0c29c036` 市场数据停更披露工单 + `R-20260827-09`
- crosswalk 正向绿、无重号、反向仍 88 行（两条新行都回指工单路径，未增孤儿）。

⚠ 本地 `main` 已前进到 `e4276e00`（一行 ledger 表头改动，未合 `gitea/main`）。
本分支只在 Open 表**表尾追加行**，不动表头；若 `e4276e00` 先合，表头取主干版即可。

## 两份工单

### 1. `2026-08-27-tool-usage-differential-workorder.md`（`R-20260827-08`）

工具面只装了「要了没有」一侧传感器（`tool_hunger`），「有了没要」零遥测。

**关键发现：两半数据本来就在同一个产物里**——`continuous-episode.json` 的
`satisfiability_precheck.contributing_tools` × `events[kind=tool_request].payload.name`。
所以 P0 是**零运行时改动**的离线审计，不是加传感器。

本轮已实测基线（747 份产物，2026-08-08→08-27，含 360 份探针/评测）：
output 实例级差值 **425**、`suspicious` **1193**、可算差值 run **698**、有差值 run **572**；
`kb_search` 未调率 **67.3%**（分母 603）——与 08-22「KB 只参与 5/9」同形、n 大 67 倍。

**成立边界（§4，别跳过）**：425 **双向污染**——
§4.1 让它**低估**（空 produces 的工具进不了分子；`suspicious` 1193 是它的 2.8 倍，
**看不见的比看得见的多**），§4.1b 让它**高估**（`contributing_tools` 全未调 ≠ 那格空着，
仍可能被声明表没覆盖的工具或 harness 预取填上）。
**它是「值得看一眼」的信号，不是可下结论的度量。**
禁止据 425 单独下「模型路由差」结论；**不把预检升级成拦截门**（理由见 adapter:535-543）。

**判据口径已在 §3.0 逐字钉死**（本单基线的原始脚本未留存）。
数对不上时**先核对是否同口径**再判失败。
⚠ 归一（`_normalize_output_id`）是 **runtime 写入侧**注入的，产物里存的是原始
`output_id`、归一只用于匹配——所以离线脚本**不带也不应带**归一步骤
（基线表里 `direct_assessment` 与 `direct_answer` 分列两行就是证据）。

### 2. `2026-08-27-staleness-disclosure-workorder.md`（`R-20260827-09`）

站立日可见、落后不可见。**根因不是缺一句话，也不是某个 `min()` 写错**——
现有几处 `min()` 对各自消费者都是对的（PIT 保证）。根因是**全系统只有
「从数据自身派生」这一个日期参照系，缺少外部日历参照的第二信号**。
所以修法是**加法**（新增日历参照的信号），**不是改法**。

> ⚠ **本文件初稿在此处有两条错误结论，已于 `a6d7efad` 撤回，不要照旧稿施工：**
> 1. ~~「`R-20260826-01` 预登记过第二处钳制，本单是那句预言的兑现」~~ —— **错**。
>    该行 outcome 是 `confirmed`，其预登记的条件失败**从未发生**；
>    `episode_tools.py:212` 与之**同形状但非同因果**。
> 2. ~~「新鲜度基准取 min 错误 → 改 `episode_tools.py:212`」~~ —— **错且危险**，见下条红线。

**⛔ 实施方第一红线：不要动 `_structured_freshness_floor`（`episode_tools.py:212`）**

实测三个消费者全部承重，动它会打穿 PIT：

| 调用点 | 用途 | 既有回归 |
|---|---|---|
| `:327` `_structured_as_of` | 查询上界 | `test_frozen_cutoff_caps_newer_snapshot_freshness_floor`（`test_episode_tools.py:1664`） |
| `:773` | market reference date | — |
| `:1205` | 历史窗口授权判定 | `test_user_dated_task_authorizes_historical_finance_query`（`:1609`） |

它不是「装错参照系的检测器」，是**被多方消费的 PIT 原语**。详见工单 §4.0。

**实施方注意（复核稿两处不准，按工单 §3 走）**：
- `render()` 里**已有** `calendar_disclosure` 分支，但只承载**休市**，
  且 `should_stop` 里 `if self.calendar_disclosure: return True`——
  **复用会让停更日变成「该日无行情」，是行为回归**。停更语义是披露并继续。
- `trading_calendar.py` **已存在**，落后量纲直接用它，不要新建日历。
- **量纲必须是交易日**：按自然日算每个周末假期各误报一次，一周内被训练成忽略。
- §5 巡查带判据：夹到 **cutoff** 是 PIT 保证要保留，**别当 bug 一起改掉**。

## 第三件：crosswalk 加了「订正传播」向（已落地，非工单）

`scripts/audit_ledger_spec_crosswalk.py` 新增第三向（**warning**）：
spec 自称订正过（含 `订正`/`撤回`/`已修正`/`勘误`）时，同号
`docs/handoffs/inflight/` 的交接必须也带订正痕迹，否则报。

**它治的就是本分支自己犯的那次**：停更工单撤回两条结论、spec 与台账都改了，
交接一字未动仍在传播旧结论——而按仓规接手者先读交接。

刻意收窄三处（都在 docstring）：
1. **只在 spec 自称订正时比对**——普通迭代不触发，否则变稳定误报。
2. **只查 `inflight/`**——归档交接是历史快照，本就不该跟 spec 走。
3. **归属靠台账行点名的 spec**，不是「谁提到过这个号」。
   首跑真仓 4 例全是误报（如 `R-20260826-01`：另一份工单引用它当历史证据，
   而那份的「订正」说的是别的号）；收窄后 4 → 0。

**明确不做语义比对**：双方都没写标记的措辞矛盾抓不到。那属语义级检查，
放对抗审查流程、不进门——判定不了还硬拦就是造噪声源。

验证：14 passed；三条变异逐个精确击杀；**真仓验证**（非夹具）——把本文件的
订正痕迹全抹掉重跑，精确报出 `R-20260827-09 → feat-tool-usage-differential.md`
一条，还原后回 0。

## 下一步（等用户裁决，不是在途）

1. 开 PR / 合并——**未做，等确认**。
2. 两份工单派单：建议先 `-08` P0（零运行时改动、验收判据最干净）。
3. 顺手可清（本轮发现、未做）：
   - 能力图谱 `finance-agent-capability-graph.md:210` 说 `memory_lookup` 的 `produces`
     「有意留空」，main 实际是 `frozenset({"prime_memory"})`（`d36f43e2`）。
     `graph_audit.py` exit 0——它校验 `path::symbol` **存在**，不算符号的**值**。
   - 同一审计报 **7 条 MERGED** 待从 `@branch` 提升为常规行。
   - `inflight/main.md` 里「08-26 EMFILE 红了一整天」是两次事故的时间线捏合：
     实为 ~1 小时（18:30→19:35）与 ~40 分钟（18:42→19:20）；
     真正接近一整天且**零告警**的是 `R-20260826-01`。入档前修正，别让下一个人读成一条。

## 坑

- 主检出 `/Users/a77/finance-workspace-private` 当时在**他人分支**
  `docs/macro-map-and-code-map-refresh` 且脏（AGENTS.md / capability-switchboard 交接 /
  复盘 matrices 等），**本单全程未动它**。接手者同样别在那棵树上改。
- `pre-commit` 的 `tool-reachability` 门顺带报了一条值得留意的信息（非本单范围）：
  `memory_lookup` 是**条件装配**，「生产入口若忘了传那个输入，它会静默永不装配」。
  与工单 1 的 §4 盲区讨论同族，可作后续线索。
