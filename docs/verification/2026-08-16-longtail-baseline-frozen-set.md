# 2026-08-16 长尾骨架 15 题冻结集

## Verdict

- outcome: FREEZE_ONLY
- live_ab_ran: false
- failure_criterion: 未开对照窗。本文件只锁题面、分层、触发观察和护栏，不报告剥句率。
- baseline_tip: `ef5c3821`（gitea/main at freeze；含 outlook #72/#75、长尾注入 #77、perspective #76）
- fixture: `intelligence/eval/fixtures/longtail-baseline-frozen-15-2026-08-16.questions.json`
- loader: `intelligence/eval/longtail_baseline_frozen_set.py`

## Freeze

- frozen_at: 2026-08-16T12:01:44+08:00
- fixture_sha256: `f617c82cbca35aa17c0b88dc2966401ce12ae7988b36d1603e3bfdddcc4264b0`
- mined_from: `default` + `linxiaoqi5111` 共 540 条 `report.json`
- predicate: 最新一次完整 report 仍是 `general_finance_qa` 且 TaskFrame.confidence < 0.6（触发 2）；或历史 trace 出现 `安全降级` / `unparsable_response`（触发 1）
- do_not_use_as_off_arm: 8792 快照 `437cd5e9`；handoff 初稿里的 `268a0605`（缺 #75/#77）

| 臂 | 代码 | 开关 |
|---|---|---|
| 现状 | `ef5c3821` | `ASK_LONGTAIL_BASELINE` 默认 off |
| 注入 | 同一 tip | `ASK_LONGTAIL_BASELINE=on` |

今天两问已是 outlook 形 × 残差置信。#72/#75 已在 tip 上，剥句率差的是骨架增量，不是 grounding_mode / 「据此判断：」前缀。真残差档（无观点题面）才是本刀独有信号。

## Longtail 15

分层规则：题面含「你认为 / 你觉得 / 怎么看 / 机会在哪 / 会怎么走」→ outlook，否则 residual。最新分类已翻成 `market_forecast` 的题不进本集。

| id | stratum | triggers | as_of | question | source |
|---|---|---|---|---|---|
| L01 | outlook | t2 | 2026-08-14 | 基于8.15的行情现状，你认为周一的机会在哪 | `run_20260816_102941_554059` / `run_20260816_103318_230845` |
| L02 | outlook | t2 | 2026-08-04 | 以 2026-08-04 收盘数据为准，分析当前行情，你认为哪个方向、哪只个股比较有机会？ | `run_20260805_234517_604873` |
| L03 | outlook | t2 | 2026-08-13 | 今天市场的抱团结构怎么看，主线有没有松动迹象？ | `run_20260814_034019_629497` |
| L04 | outlook | t1+t2 | 2026-08-14 | 立新能源怎么看 | `run_20260815_180819_122294` |
| L05 | outlook | t2 | 2026-08-14 | 超纯应材你认为合理估值是多少 | `run_20260806_153812_267573` |
| L06 | residual | t2 | 2026-07-23 | 2026-07-23 涨停热度前四的题材里，哪些同时也是双红板块 | `run_20260815_182537_751801` |
| L07 | residual | t2 | 2026-07-23 | 2026-07-23 涨停集中在哪些题材 | `run_20260815_180937_200598` |
| L08 | residual | t2 | 2026-07-23 | 什么是双红题材 | `run_20260731_193821_892916` |
| L09 | residual | t1+t2 | 2026-07-23 | 2026-07-23 连板梯队什么情况，有没有断层 | `run_20260815_181108_139591` |
| L10 | residual | t2 | 2026-07-24 | 2026-07-21 到 07-24 量能和情绪是怎么演化的 | `run_20260815_182731_454211` |
| L11 | residual | t1+t2 | 2026-07-21 | 2026-07-21 的新高家数结构说明什么 | `run_20260815_181526_643177` |
| L12 | residual | t2 | 2026-08-14 | 现在最强的方向是什么，为什么 | `run_20260805_234632_906886` |
| L13 | residual | t2 | 2026-08-14 | 最近哪些板块比较强，双红的那种 | `run_20260815_183554_189780` |
| L14 | residual | t2 | 2026-07-23 | 2026-07-23 的市场情绪怎么解读 | `run_20260815_181410_204134` |
| L15 | residual | t1+t2 | 2026-08-14 | 立新能源的技术面快照给我看一下 | `run_20260815_183146_885845` |

观察帧一律 `general_finance_qa` / 0.4 / owner=None。注入键是 **TaskFrame.confidence**，不是 controller decision.confidence（L01 两问 controller 为 0.78）。L01 题面写 8.15（周六），eval `as_of` 用两问报告里的前一交易日 `2026-08-14`。加载器拒绝休市日 `as_of` 和会触发 `question_non_trading_note` 的题面。

## Guard 5

高置信 + `RESEARCH_OWNER_IDS`。本地 540 条 report 里，落在该集合且 confidence≥0.6 的只有 `theme-research`。`stock-产业链研究` 不在 `RESEARCH_OWNER_IDS`，不能当护栏（让位逻辑认不到它）。

| id | owner | conf | question | source |
|---|---|---|---|---|
| G01 | theme-research | 0.98 | 液冷题材现在怎么看？我之前的判断还成立吗 | `run_20260808_001411_773938` |
| G02 | theme-research | 0.98 | 固态电池 | `run_20260815_181915_197222` |
| G03 | theme-research | 0.98 | 光刻胶 | `run_20260815_181626_954956` |
| G04 | theme-research | 0.98 | 2026-07-23 电网设备为什么涨，给出证据来源 | `run_20260815_183924_701039` |
| G05 | theme-research | 0.98 | 电网设备是怎么发酵到 2026-07-23 双红的，把链路回溯一下 | `run_20260815_182037_434217` |

## 故意排除

| question | 原因 |
|---|---|
| 2026-07-21 收盘了，明天怎么看 | 最新分类 `market_forecast` 0.92，#72 之后是公路 |
| 站在 2026-07-21 收盘，给出对 07-22 的研判 | 同上 |
| 明天怎么看 | 同上 |
| 查一下 sector_marginal 表里 07-23 的边际量 | 表结构探针；T1 历史里出现最多，但不是用户金融问题 |
| 只回复两个字：收到 | 噪声 |
| 卖方材料提纯… | 附件任务 |
| 刚才你说的双红板块… / 那这些板块里成交额最大的是哪个 | 无上下文的追问 |
| 2026-07-25 市场怎么样 | 周六；`question_non_trading_note` 必触发，是休市闸原例，不是骨架对照题 |

T1 在语料里几乎只有三句固定探针在打转。本集用 L04/L09/L11/L15 带上真实金融题的 fallback 观察，不把 schema probe 算进 15。

## 预注册对照（仍未跑）

- 设计：15 × 2 臂 × 3 次 = 90；护栏 5 题只跑注入臂，确认 `【长尾回答骨架】` 不出现。
- 主度量：非空 `direct_answer` 交付率；judge 剥句率（rejected_sentence/总句数）；`evidence_bound_rate`（**5pp 不放宽**）；token / 墙钟。
- 空壳 vs 诚实缺口：chat 兜底无检索时，正文写「未取得」算合规，不算空壳。
- 路由吸收：若某题在 `ef5c3821` 上改判成 `market_*` 或 `RESEARCH_OWNER_IDS` owner，单独记 `routing-absorbed`，不并进剥句率。L04 题面尤其不稳定。
- L01 两问的剥句率差是骨架增量，不要归因到 #72/#75。
- 对照通过前不翻 `ASK_LONGTAIL_BASELINE` 默认值，不部署 8792。
- 不另开 PR-2：`SKILL.md` §5 已在同一 `prompt_block()` 里。

## 与交接的差

handoff §3 初稿把现状臂写成 `268a0605`。冻结时 main 已含 #75 与 #77，再用那个 SHA 会把两刀和骨架叠在一起。权威基线以本文件和夹具 `baseline.tip` 为准。
