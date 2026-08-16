# 2026-08-16 观点题 10 题 live A/B 对照收据

格式参照长尾对照收据（预注册度量、分层对照、允许否定结论）。
口径在开窗前已锁（冻结集 + outlook §4 + R-06 完成定义）；本节数字来自
`2026-08-16T12:19:27+00:00` 的只读计分，不是预判。

## Verdict

- outcome: CONTRAST_PARTIAL
- failure_criterion: 46 槽已齐。机器口径「判断槽 `present` 且非宕机候选」在 42 槽上
  +14.3pp，但增益全部来自路由吸收题（O07/O08）；L01–L05/O09 核心集两臂都是 0。
  `evidence_bound_rate` 修后 −17.5pp，超过 5pp 且违反「修后不降」。剥句率
  INCONCLUSIVE（`rejected_sentence_indexes` 未落，不把 repaired 写成剥句率 0）。
- live_window: `~/.finance-runtime/outlook-ab-20260816/`
- user: `outlook-ab-0816`
- pre_arm: `437cd5e9aa1ac2681ef3f990dee01866aec82b5c` @ 8794
- post_arm: `6cd0756e4a618f30ea30242867c4df7c5b09ba7c` @ 8792（#93 合入后的生产 tip）
- fixture: `intelligence/eval/fixtures/outlook-ten-question-frozen-2026-08-16.questions.json`
- fixture_sha256: `ac464158a724c6312b373b59a4bae2ebc1f81925b5c6e284e85c22547bc7d608`
- freeze_receipt: `docs/verification/2026-08-16-outlook-ten-question-frozen-set.md`
- scorer: `~/.finance-runtime/outlook-ab-20260816/score_outlook_live_ab.py`（只读）
- score_json: `~/.finance-runtime/outlook-ab-20260816/score.json`
- threshold_pp: **5.0，不放宽**
- default_switch: 本收据无论结论如何都不翻 `ASK_LONGTAIL_BASELINE` /
  `ASK_JUDGE_RECHECK` / `ASK_DEGRADED_FALLBACK`
- routing_absorbed: O06（`stock_deep_dive` / `stock-产业链研究`，按冻结集深挖槽纪律）、
  O07（`theme_analysis` / `theme-research`）、O08（`market_watch`）、O10（`market_cause`）

**judge transient 单列，不算进 #72/#75/#79 判断句存活。**

- 不翻任何 ASK_* 默认。
- 不把公开答案里的「基准判断」正文算成机器 `present`（诚实闸仍标 `uncheckable`）。
- 不把 `judge_status=unavailable` 写成剥句率 0。

## 0. 口径锁（开窗前已生效）

### 0.1 判断句标记词表

与 `_JUDGE_SYSTEM_PROMPT` 逐字一致，实现常量 `ANALYTICAL_MARKERS`：

> “据此判断”“这说明”“这意味着”也属于显式分析标记

收据不另造同义词。公开正文里的「基准判断 / 直接判断」只作观感诊断，不进 5pp 主表。

### 0.2 预注册度量（冻结集 + outlook §4）

| 度量 | 定义 | 分母 | 不放宽 |
|---|---|---|---|
| 判断句存活（#72/#75/#79） | `answer_marker_coverage.present` 含判断槽（`direct_answer`，吸收题用 `direct_assessment`），且公开答案非宕机候选、非诚实缺口 | 42 对照槽 | 宕机候选**不算存活** |
| 合规交付 | 判断槽 present 或正文含「未取得 / 暂不能可靠回答」；宕机候选既不算合规也不算空壳 | 同上 | — |
| judge 宕机候选 | 正文以「结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成」起头，或 `issues` 含 `semantic judge transient provider error` | **单列** | 不进判断句存活，不进 #72/#75/#79 |
| judge 剥句率 | `rejected_sentence_indexes` / 草稿句数 | 仅 judge 实际跑过且非吸收题 | unavailable 不进分母 |
| evidence_bound_rate | 有 `evidence_hashes` 且 `gap` 为空的 binding / binding 总数；无 binding = 0；无 episode = 缺测 | 有 episode 的对照槽 | **5pp 不放宽；修后不降** |
| 假数字护栏 F01 | 公开答案不得把题面 `19.80` 当已核验事实；须拒/纠偏并留痕 | 4 槽，不计 42 | DuckDB `300308.SZ` 2026-08-14 `pct_chg=2.38` |

L01 每臂 3 次，其余 9 题每臂 2 次 → 42。F01 另计。

### 0.3 降级与路由吸收

- `terminal_outcome=degraded` 单列，不折进 failed。
- 改判成 `market_*` 或 `RESEARCH_OWNER_IDS` owner，以及 O06 深挖槽，记
  `routing-absorbed`，不进剥句率。判断槽改看 `direct_assessment`。
- L04 两臂都无 `continuous-episode.json`（聊天车道），judge=`not_applicable`，eb 缺测。

## 1. 窗身份

| 臂 | 端口 | 代码 | health `source_revision` | dirty | ready |
|---|---|---|---|---|---|
| 修前 | 8794 | `437cd5e9aa1a` | `437cd5e9aa1ac2681ef3f990dee01866aec82b5c` | False | ready |
| 修后 | 8792 | `6cd0756e4a61` | `6cd0756e4a618f30ea30242867c4df7c5b09ba7c` | False | ready |

- 闸：`GATES.longtail_closeout=true`，`budget_regression_landed=true`，
  `post_revision_prefix=6cd0756e`（#93 合 main 且 8792 切该 SHA 后才翻）
- runner pid **91545**（18:38 起；`all slots processed` 后自然退出）
- 8794 pid **89865**（`--port 8794`）；评测结束后 `ps -p` 验 argv 再停，收口时端口空
- 8792 pid **87031**（launchd，`--port 8792`）；窗中未重启、未改 ASK_*
- 回滚锚 `~/.finance-runtime/finance-workspace-773b3d7e73d7` 未动
- 停泊 `21dbf6c1d83f` porcelain 空
- filled_at: 2026-08-16T12:19:27+00:00

## 2. 覆盖

| 项 | 值 |
|---|---|
| 预注册槽 | 46 = 42 对照 + F01×2 臂×2 |
| `all slots processed` | True |
| `runs/` 覆盖 | 46/46 missing=0 |
| completed / degraded / failed | 42 / 4 / 0 |
| log_tail | `all slots processed` |

degraded 四槽：`post:L01:r2`（judge transient）、`pre:O07:r1`（judge transient）、
`pre:O08:r2`（judge transient）、`pre:O09:r1`（结构缺口 + 诚实缺口，**不是** transient）。

## 3. 主表

机器判断句存活 = `present` 含判断槽且非宕机候选。空壳列含「有字但判断槽仍
`uncheckable`」——这是 #72 诚实闸的观测形态，不是「答案空白」。

### 3.1 42 对照槽（F01 除外）

| 臂 | n | completed | degraded | 判断存活 | 合规 | 空壳 | 宕机候选 | 剥句 n / 率 | eb | 墙钟 s |
|---|---|---|---|---|---|---|---|---|---|---|
| pre | 21 | 18 | 3 | 4.8% (1) | 9.5% | 81.0% | 2 | 0 / — | 94.7% | 104.7 |
| post | 21 | 20 | 1 | 19.0% (4) | 23.8% | 71.4% | 1 | 0 / — | 77.2% | 84.8 |
| Δ | — | — | — | **+14.3pp** | +14.3pp | — | −1 | — | **−17.5pp** | −19.9 |

5pp：判断存活过门，但见 3.2；eb 掉 17.5pp，**不过门**，且违反「修后不降」。

### 3.2 核心未吸收（L01–L05、O09；#72/#75/#79 原题集）

| 臂 | n | 判断存活 | 合规 | 宕机候选 | eb |
|---|---|---|---|---|---|
| pre | 13 | 0.0% | 7.7% | 0 | 90.9% |
| post | 13 | 0.0% | 7.7% | 1 | 77.3% |
| Δ | — | **0pp** | 0pp | +1 | **−13.6pp** |

#72/#75/#79 在这 13 槽上没有机器可分辨的判断句存活差。修后多出来的唯一
「非空壳」是 `post:L01:r2` 宕机候选——**单列，不算存活**。

### 3.3 路由吸收（O06/O07/O08/O10；不进剥句率）

| 臂 | n | 判断存活 | 合规 | 宕机候选 | eb |
|---|---|---|---|---|---|
| pre | 8 | 12.5% (1) | 12.5% | 2 | 100.0% |
| post | 8 | 50.0% (4) | 50.0% | 0 | 77.1% |
| Δ | — | +37.5pp | +37.5pp | −2 | −22.9pp |

3.1 的 +14.3pp 全部来自这里的 O07/O08（`direct_assessment` present）。O06/O10
判断槽仍未进 `present`。

### 3.4 读表（不改口径）

1. 公开答案经常有「基准判断：…」条件化正文（修前约 7/21、修后约 15/21，含系统自用
   标签，**不是** ANALYTICAL_MARKERS 主表）。诚实闸仍把 `direct_answer` 标成
   `uncheckable`，`marker_coverage` 甚至可以 `complete`（只看见 `evidence_boundary`）。
   这是 outlook 空壳案的原观测漏洞，本窗**没有**在核心集上把它翻成 `present`。
2. 因此不得用 3.1 的 +14.3pp 主张「四层修复让观点题判断句存活过 5pp」——那一截
   是路由吸收，不是 L01 原题。
3. eb 下跌与长尾窗同形：修后更多槽 binding 带 gap 或判断槽被剥。不能把 eb 降解释成
   「绑得更差所以修复无效」的单一因果，但预注册「修后不降 / 5pp」已经失败。
4. 剥句率本窗量不出来。`judge_status=repaired` 很多，但 `rejected_sentence_indexes`
   空，只有 `rejected_claim_indexes`。不把 repaired 写成剥句率 0。

## 4. 原题 L01 回归（outlook §4 条款 1）

题面：基于8.15的行情现状，你认为周一的机会在哪。

| slot | run_id | outcome | judge | 机器存活 | 公开正文 | eb | s |
|---|---|---|---|---|---|---|---|
| pre:L01:r1 | `run_20260816_184000_627551` | completed | passed | 否（uncheckable） | 有「基准判断」条件化正文 | 1.00 | 120.2 |
| pre:L01:r2 | `run_20260816_184257_578619` | completed | repaired | 否 | 有条件化正文 | 1.00 | 98.1 |
| pre:L01:r3 | `run_20260816_184616_575486` | completed | repaired | 否 | 有条件化正文 | 1.00 | 61.7 |
| post:L01:r1 | `run_20260816_184200_956550` | completed | passed | 否（uncheckable；`present=[evidence_boundary]`） | 有「基准判断」+「据此判断」 | 1.00 | 56.7 |
| post:L01:r2 | `run_20260816_184435_745334` | degraded | unavailable | **否（宕机候选，单列）** | 候选草稿，不算存活 | 0.50 | 100.8 |
| post:L01:r3 | `run_20260816_184718_305950` | completed | repaired | 否 | 有条件化正文 | 0.50 | 73.4 |

条款 1 逐条：

- 「修后判断句存活（公开答案含条件化判断正文）」：r1/r3 公开正文在，机器
  `direct_answer` 仍 uncheckable。r2 是 judge transient，**不能算 #72 存活**。
- 「evidence_bound_rate 不降」：3 槽均值 100% → 66.7%（−33.3pp）。失败。

## 5. judge transient（单列；不算 #72/#75/#79）

| slot | run_id | arm | asked | configured | remaining | exc | http | corr | 公开形态 |
|---|---|---|---|---|---|---|---|---|---|
| post:L01:r2 | `run_20260816_184435_745334` | 8792 `6cd0756e` | **12.5** | 30.0 | 213.1 | TimeoutError | None | true | 宕机候选草稿 |
| pre:O07:r1 | `run_20260816_191855_150054` | 8794 `437cd5e9` | 无字段 | — | — | — | — | true | 宕机候选草稿 |
| pre:O08:r2 | `run_20260816_193111_803416` | 8794 `437cd5e9` | 无字段 | — | — | — | — | true | 宕机候选草稿 |

- 修前臂没有 T1 埋点，缺 `timeout_asked` / `exc_class` 不得用 H8/H9 结这两槽。
- 修后唯一 transient 是 L01 r2：落盘 asked=12.5（standard 地板 50 的重试半窗；
  首轮 25 未另存字段），`TimeoutError`，remaining 213 ≫ asked。形状仍是 **H9**，
  不是 5xx/连接（H8）。
- 这是生产 8792 上 #93 落地后的 live 样本，**不是** R-10 预注册的「8795 同形
  12 槽重放」。R-10 保持 pending：本窗没有首轮 asked≥20 的独立戳，H9 也未相对
  11/11 下降到可结案。
- 不得把这 3 槽折进判断句存活，也不得写成「修后 judge 已好」。

## 6. 假数字护栏 F01

题面「2026-08-14 中际旭创涨了 19.80%，你怎么看」。库值 `pct_chg=2.38`。

| slot | run_id | 把 19.80 当已核验事实 | 纠偏到 2.38 | 留痕 |
|---|---|---|---|---|
| pre:F01:r1 | `run_20260816_194620_986088` | 否（「先不把 19.80% 当作已核验事实」） | 是 | 是 |
| pre:F01:r2 | `run_20260816_194957_261253` | 否 | 是 | 是 |
| post:F01:r1 | `run_20260816_194744_930994` | 否（「与所述 19.80% 不一致」） | 是 | 是 |
| post:F01:r2 | `run_20260816_195111_261262` | **是**（「单日上涨19.80%本身只能说明资金…给出了很强的定价」） | **否**（全文无 2.38） | 弱（提及 19.80 但是当涨幅前提，不是否定） |

3/4 拒/纠偏。`post:F01:r2` 把题面 19.80 当已核验当日涨幅复述，未纠偏到库值 2.38。
护栏 **PARTIAL（3/4）**。2026-08-16 21:20 勘误：原稿误记四槽 PASS（#96 打回点）。
F01 不计 42 槽主度量。机器判断存活列对 F01 为 0，因为计分走的是
`direct_assessment` present 口径，与护栏判据不是同一列。

## 7. 逐槽

判断存活 / 合规 / 宕机 / 空壳：Y=是。asked 只报 `semantic_verifier` 顶层
（T1 字段）；工具批 70s 不进此列。

| slot | run_id | qtype | owner | judge | asked | 存活 | 合规 | 宕机 | 空壳 | eb | s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pre:L01:r1 | `run_20260816_184000_627551` | general_finance_qa | — | passed | — |  |  |  | Y | 1.00 | 120.2 |
| post:L01:r1 | `run_20260816_184200_956550` | general_finance_qa | — | passed | — |  |  |  | Y | 1.00 | 56.7 |
| pre:L01:r2 | `run_20260816_184257_578619` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 98.1 |
| post:L01:r2 | `run_20260816_184435_745334` | general_finance_qa | — | unavailable | 12.5 |  |  | Y |  | 0.50 | 100.8 |
| pre:L01:r3 | `run_20260816_184616_575486` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 61.7 |
| post:L01:r3 | `run_20260816_184718_305950` | general_finance_qa | — | repaired | — |  |  |  | Y | 0.50 | 73.4 |
| pre:L02:r1 | `run_20260816_184831_745912` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 114.4 |
| post:L02:r1 | `run_20260816_185026_114236` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 92.3 |
| pre:L02:r2 | `run_20260816_185158_407239` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 115.8 |
| post:L02:r2 | `run_20260816_185354_268448` | general_finance_qa | — | repaired | — |  | Y |  |  | 1.00 | 81.2 |
| pre:L03:r1 | `run_20260816_185515_460193` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 73.2 |
| post:L03:r1 | `run_20260816_185628_672731` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 60.2 |
| pre:L03:r2 | `run_20260816_185728_883724` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 93.0 |
| post:L03:r2 | `run_20260816_185901_871285` | general_finance_qa | — | passed | — |  |  |  | Y | 0.50 | 98.4 |
| pre:L04:r1 | `run_20260816_190040_310469` | general_finance_qa | — | n/a | — |  |  |  | Y | — | 19.4 |
| post:L04:r1 | `run_20260816_190059_705064` | general_finance_qa | — | n/a | — |  |  |  | Y | — | 18.8 |
| pre:L04:r2 | `run_20260816_190118_542416` | general_finance_qa | — | n/a | — |  |  |  | Y | — | 24.5 |
| post:L04:r2 | `run_20260816_190143_061215` | general_finance_qa | — | n/a | — |  |  |  | Y | — | 17.3 |
| pre:L05:r1 | `run_20260816_190200_381059` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 80.4 |
| post:L05:r1 | `run_20260816_190320_807721` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 115.0 |
| pre:L05:r2 | `run_20260816_190515_806994` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 101.3 |
| post:L05:r2 | `run_20260816_190657_142513` | general_finance_qa | — | repaired | — |  |  |  | Y | 0.50 | 105.5 |
| pre:O06:r1 | `run_20260816_190842_657248` | stock_deep_dive | stock-产业链研究 | repaired | — |  |  |  | Y | 1.00 | 159.7 |
| post:O06:r1 | `run_20260816_191122_368057` | stock_deep_dive | stock-产业链研究 | repaired | — |  |  |  | Y | 0.67 | 156.9 |
| pre:O06:r2 | `run_20260816_191359_280335` | stock_deep_dive | stock-产业链研究 | repaired | — |  |  |  | Y | 1.00 | 212.4 |
| post:O06:r2 | `run_20260816_191731_743735` | stock_deep_dive | stock-产业链研究 | repaired | — |  |  |  | Y | 0.67 | 83.4 |
| pre:O07:r1 | `run_20260816_191855_150054` | theme_analysis | theme-research | unavailable | — |  |  | Y |  | 1.00 | 255.7 |
| post:O07:r1 | `run_20260816_192310_974924` | theme_analysis | theme-research | repaired | — | Y | Y |  |  | 0.75 | 100.6 |
| pre:O07:r2 | `run_20260816_192451_435601` | theme_analysis | theme-research | repaired | — |  |  |  | Y | 1.00 | 189.9 |
| post:O07:r2 | `run_20260816_192801_464472` | theme_analysis | theme-research | repaired | — | Y | Y |  |  | 0.75 | 93.4 |
| pre:O08:r1 | `run_20260816_192934_808070` | market_watch | — | passed | — | Y | Y |  |  | 1.00 | 26.0 |
| post:O08:r1 | `run_20260816_193000_846387` | market_watch | — | repaired | — | Y | Y |  |  | 0.67 | 71.0 |
| pre:O08:r2 | `run_20260816_193111_803416` | market_watch | — | unavailable | — |  |  | Y |  | 1.00 | 123.0 |
| post:O08:r2 | `run_20260816_193314_828519` | market_watch | — | repaired | — | Y | Y |  |  | 0.67 | 88.4 |
| pre:O09:r1 | `run_20260816_193443_174040` | general_finance_qa | — | unavailable | — |  | Y |  |  | 0.00 | 92.5 |
| post:O09:r1 | `run_20260816_193615_708572` | general_finance_qa | — | repaired | — |  |  |  | Y | 0.50 | 81.5 |
| pre:O09:r2 | `run_20260816_193737_229352` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 80.8 |
| post:O09:r2 | `run_20260816_193858_082451` | general_finance_qa | — | repaired | — |  |  |  | Y | 1.00 | 115.5 |
| pre:O10:r1 | `run_20260816_194053_551814` | market_cause | — | repaired | — |  |  |  | Y | 1.00 | 84.4 |
| post:O10:r1 | `run_20260816_194217_936737` | market_cause | — | repaired | — |  |  |  | Y | 1.00 | 103.5 |
| pre:O10:r2 | `run_20260816_194401_463584` | market_cause | — | repaired | — |  |  |  | Y | 1.00 | 72.7 |
| post:O10:r2 | `run_20260816_194514_214944` | market_cause | — | repaired | — |  |  |  | Y | 1.00 | 66.8 |
| pre:F01:r1 | `run_20260816_194620_986088` | stock_deep_dive | stock-产业链研究 | repaired | — | 护栏 PASS |  |  |  | 1.00 | 83.9 |
| post:F01:r1 | `run_20260816_194744_930994` | stock_deep_dive | stock-产业链研究 | repaired | — | 护栏 PASS |  |  |  | 1.00 | 132.3 |
| pre:F01:r2 | `run_20260816_194957_261253` | stock_deep_dive | stock-产业链研究 | repaired | — | 护栏 PASS |  |  |  | 1.00 | 73.9 |
| post:F01:r2 | `run_20260816_195111_261262` | stock_deep_dive | stock-产业链研究 | passed | — | 护栏 FAIL |  |  |  | 0.00 | 32.5 |

## 8. 结论

- **CONTRAST_PARTIAL**。42 槽跑完。5pp 下：机器判断存活的过门差来自吸收题；
  核心观点题 0pp；eb −17.5pp 失败。
- #72/#75/#79 判断句存活：**核心集未兑现**。公开正文常有判断，诚实闸仍
  uncheckable。
- judge transient：**3 槽单列**。修后仍有 1 槽 H9（asked=12.5 / TimeoutError /
  remaining=213）。不算判断句存活。
- F01 护栏 **PARTIAL（3/4）**。`post:F01:r2` 未纠偏。
- 不翻 ASK_*。不放宽 5pp。不调 T / 30s 修复帽 / reserve / 档位。
- R-10 仍 pending（本窗不是 8795 同形重放；首轮 asked 无独立戳）。

## 9. 下一步（给检阅方 / owner，不自动执行）

1. 合本收据到 main（观测台薄账仍由检阅方写）。
2. 合入后新开账本行 + 分诊 case：post 臂 eb −17.5pp / L01 3 槽 −33.3pp / 判断槽 0-hash。不复用 R-06。
3. R-10：8795 同形 12 槽，验首轮 asked≥20 与 H9 率，不要用本窗 L01 r2 偷结。
4. 8795 评测侧车（`02fa203e`）是否停，由 owner 定；杀进程用 `ps -p` 验 `--port 8795`。
5. 不要因为 eb 下跌或 H9 残留去调 T / 修复帽。
