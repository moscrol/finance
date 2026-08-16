# 2026-08-16 长尾骨架 15 题 live A/B 对照收据

格式参照 bookgap S2 对照收据（`fwp-wt-bookgap-s2`：预注册度量、分层对照、允许否定结论）。
口径在窗未齐时已锁（见 §0）；本节数字来自 `2026-08-16T07:38:26+00:00` 的只读计分，不是预判。

## Verdict

- outcome: CONTRAST_PARTIAL
- failure_criterion: 95 槽已齐；剥句率仍 INCONCLUSIVE。residual 上有 ≥5pp 的可分辨差：compliant_delivery +53.3pp；evidence_bound -50.0pp。outlook 档不计入骨架独有信号。
- live_window: `~/.finance-runtime/longtail-ab-20260816/`
- user: `longtail-ab-0816`
- baseline_tip: `773b3d7e`（两臂同一 SHA；`source_dirty=false`）
- fixture: `intelligence/eval/fixtures/longtail-baseline-frozen-15-2026-08-16.questions.json`
- fixture_sha256: `9b43354b2d9af669634d87df6f1e8ae219ebb751156694d0e01dc65a948b3fd8`
- freeze_receipt: `docs/verification/2026-08-16-longtail-baseline-frozen-set.md`
- closeout_handoff: `docs/handoffs/2026-08-16-longtail-ab-window-closeout.md`
- scorer: `scripts/score_longtail_live_ab.py`（只读）
- score_json: `~/.finance-runtime/longtail-ab-20260816/score.json`
- threshold_pp: **5.0，不放宽**
- default_switch: 本收据无论结论如何都不翻 `ASK_LONGTAIL_BASELINE`（权威 handoff §2.4 第 4 刀另开 PR）
- routing_absorbed: 无

- residual 两臂 peel_n=0（judge 未跑），剥句率 INCONCLUSIVE，不是 0
- 不翻 ASK_LONGTAIL_BASELINE 默认。

## 0. 口径锁（窗未齐已生效，避免 HARKing）

### 0.1 判断句标记词表

与 `_JUDGE_SYSTEM_PROMPT` 逐字一致，实现常量 `ANALYTICAL_MARKERS`：

> “据此判断”“这说明”“这意味着”也属于显式分析标记

出处：`intelligence/services/episode_semantic_verifier.py` 的 `_JUDGE_SYSTEM_PROMPT`。
`SKILL.md` / `longtail_baseline.ANALYTICAL_MARKERS` 必须含原词。收据不另造同义词。

### 0.2 四度量（权威 handoff §3 / FREEZE §预注册对照）

| 度量 | 定义 | 分母 | 不放宽 |
|---|---|---|---|
| 非空 direct_answer 交付率 | 公开 `answer.md` 里 `direct_answer` 被 marker coverage 标为 present | 对照槽（见 0.4） | — |
| 合规交付（空壳 vs 诚实缺口） | 正文含「未取得」或「现有证据不足，暂不能可靠回答」算合规；聊天意见「看起来有字」不算成功 | 同上 | — |
| judge 宕机候选草稿 | 正文以「结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成」起头 | 单列，**既不算合规也不算空壳** | 不进剥句分母 |
| judge 剥句率 | `rejected_sentence_indexes` / 草稿句数 | **仅 judge 实际跑过的槽** | judge_unavailable 不进分母，不折进 failed |
| evidence_bound_rate | 有 `evidence_hashes` 且 `gap` 为空的 binding / binding 总数；无 binding = 0 | 有 episode 的对照槽 | **5pp 门槛不放宽** |
| token / 墙钟 | `context_growth.cumulative_input_tokens`；smoke `elapsed_s` | 有读数的对照槽 | 报增量，不作放行门槛 |

分层：outlook（题面含「你认为 / 你觉得 / 怎么看 / 机会在哪 / 会怎么走」）vs residual。
**骨架独有信号只看 residual。** outlook 档剥句/降级叠着 #79 比较集绑定，不算进本刀的账。

### 0.3 护栏：改用 FREEZE 已登记口径，不补跑 off 臂

设计 handoff §3 原文要「高置信路由行为零变化，取 5 题回归对比字节级 diff」。
FREEZE_ONLY 后写、更具体，已改成：

> 护栏 5 题只跑注入臂，确认 `【长尾回答骨架】` 不出现。

本收据采用 FREEZE 口径，**不**在收口阶段补跑 5 槽 off 臂。理由：

1. 冻结收据是后写的操作协议；runner 按它只排了 on ×1，不是执行偏差。
2. 收口交接 §7：收口前 8792 不跑任何其他 live 批。补跑会占用 off 臂，也是重开窗。
3. `【长尾回答骨架】` 是 prompt-only 注入标题，公开产物里本来就不会出现；on 臂长尾题的 episode 里也搜不到该标题（14:00 抽查 on:L01:r1）。字节级公开答案 diff 会被 theme-research 正文方差淹没，测不到「有没有注入」。
4. 护栏另加三条可观察断言，全部只读：标题不在 5 个 on 臂 run 产物里；`question_type` 仍是 `theme_analysis`（或至少不是 `general_finance_qa`）；`answer_owner` 仍在 `RESEARCH_OWNER_IDS` 且 confidence ≥ 0.6。

假骨架含市场数字必须被 review 拒绝——那是单测门，不在本 live 窗重跑。

### 0.4 清污（不入对照统计）

引 closeout handoff §2。workbench 目录里这些 run **账留全史，收据不算**：

| 类别 | run_id | 说明 |
|---|---|---|
| 带病期已删槽 | `run_20260816_125145_832107` … `run_20260816_130525_453745`（8 个，progress.jsonl 前 8 行） | 两臂健康不对称；墙钟 151.0/152.5/151.5/37.0/153.0/93.0/81.5/104.0s 只作取证 |
| kickstart 中断 | `run_20260816_130709_427017` | off:L09:r1，13:08:50 打断，无 smoke json、无账行 |
| 启动孤儿 | `run_20260816_124504_615880`、`run_20260816_124957_138951`、`run_20260816_131020_573635` | 12:45 / 12:49 / 13:10 |

对照起点：`run_20260816_131941_597875`（13:19:41 双臂健康后的 off:L01:r1）。
对齐键：smoke `slot` + `run_id`，不以 workbench 目录时间猜。

### 0.5 降级与路由吸收

- `terminal_outcome=degraded` **单列**，不折进 failed。
- 某题在 `773b3d7e` 上改判成 `market_*` 或 `RESEARCH_OWNER_IDS` owner → `routing-absorbed`，不进剥句率。L04 尤甚。
- `judge_status=unavailable`（预算/核验没跑到 judge）→ 剥句率缺失，不是剥句率 0。这与 `2026-08-16-outlook-verification-budget-regression.md` 同形；outlook 档这类降级不记骨架账。

### 0.6 环境坑（杀进程纪律）

本机 `pgrep/pkill -f` 对这批长 argv/大 env 进程系统性失明。停 8793 前必须：

```bash
sid=$(cat ~/.finance-runtime/longtail-ab-20260816/sidecar.pid)
ps -p "$sid" -o pid,args=
# argv 须含：uvicorn ... --port 8793
```

三次事故（12:48-12:51 叠启、13:06 假杀、13:09 叠启）都是这个坑。是否升格 lessons 由 owner 决定。

## 1. 窗身份（收口重读）

| 臂 | 端口 | 开关 | health `source_revision` | dirty | ready |
|---|---|---|---|---|---|
| off | 8792 | 默认 off | `773b3d7e73d7` | False | 200 |
| on | 8793 | `ASK_LONGTAIL_BASELINE=on` | `773b3d7e73d7` | False | 200 |

- runner pid **36401**（13:19:41 起；`ps -p` 验过 argv 含 `run_live.py`。15:37:57 `all slots processed` 后自然退出，收口时 `ps -p 36401` 已空）
- sidecar pid **21888**（12:50 起；`ps -p` 验过 argv 含 `--port 8793`）
- sidecar 停机：**15:39:07** 干净退出——`sidecar.err.log` 写 `Shutting down` → `Waiting for application shutdown` → `Application shutdown complete` → `Finished server process [21888]`（mtime `2026-08-16 15:39:07`）。收口时 `ps -p 21888` 已空
- 端口 8793：收口时 `lsof -nP -iTCP:8793 -sTCP:LISTEN` 无行、exit 1，已验空
- 生产 8792 **未重启、未替换**（收口后仍 `773b3d7e` / `source_dirty=false` / ready 200）
- filled_at: 2026-08-16T07:38:45+00:00

## 2. 覆盖

| 项 | 值 |
|---|---|
| 预注册槽 | 95 = 15×2×3 + 5 guard(on×1) |
| `all slots processed` | True |
| `runs/` 覆盖 | 95/95 missing=0 |
| degraded 单列 | 73 |
| failed / cancelled / protocol_error | 0 / 0 / 0 |
| log_tail | `all slots processed` |

## 3. 主表

### 3.1 全样本（routing-absorbed 已剔除）

| 臂 | n | completed | degraded | 合规交付 | 空壳 | 宕机候选 | 剥句 n / 率 | eb | 墙钟 s | input tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| off | 45 | 12 | 33 | 24.4% | 26.7% | 48.9% | 0 / — | 63.9% | 73.9 | 34202 |
| on | 45 | 10 | 35 | 64.4% | 6.7% | 28.9% | 0 / — | 31.9% | 78.2 | 39990 |
| Δ | — | — | — | +40.0pp | — | — | — | -31.9pp | +4.3 | +5787 |

### 3.2 outlook（#79 叠层；不算骨架独有）

| 臂 | n | completed | degraded | 合规交付 | 空壳 | 宕机候选 | 剥句 n / 率 | eb | 墙钟 s | input tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| off | 15 | 4 | 11 | 40.0% | 26.7% | 33.3% | 0 / — | 37.5% | 78.9 | 26642 |
| on | 15 | 4 | 11 | 53.3% | 6.7% | 40.0% | 0 / — | 41.7% | 103.0 | 52948 |
| Δ | — | — | — | +13.3pp | — | — | — | +4.2pp | +24.0 | +26306 |

### 3.3 residual（本刀独有信号）

| 臂 | n | completed | degraded | 合规交付 | 空壳 | 宕机候选 | 剥句 n / 率 | eb | 墙钟 s | input tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| off | 30 | 8 | 22 | 16.7% | 26.7% | 56.7% | 0 / — | 77.1% | 71.3 | 37353 |
| on | 30 | 6 | 24 | 70.0% | 6.7% | 23.3% | 0 / — | 27.1% | 65.8 | 30843 |
| Δ | — | — | — | +53.3pp | — | — | — | -50.0pp | -5.5 | -6510 |

### 3.4 读表（不改口径）

residual 的两列 ≥5pp 差是同一件事的两面，不能拆开只报合规：

- on 臂更多公开答案是诚实缺口（「未取得」/「暂不能可靠回答」），空壳从 26.7% 降到 6.7%，宕机候选从 56.7% 降到 23.3%。L12/L15 的 chat 完成态尤其明显：off 3/3 空壳，on 2/3 合规。
- off 臂更多是「候选草稿 + judge 未跑」还挂着 binding，所以 eb 看起来高（77.1%）。on 臂诚实缺口没有 binding，eb 掉到 27.1%。这不是「绑得更差」，是公开交付从「未核验候选」换成「缺口声明」。
- 73/95 槽 `degraded`，两臂 `peel_n=0`。预注册剥句率本窗量不出来，与预算回归案同形，不把 unavailable 写成剥句率 0。
- outlook 合规 +13.3pp、eb +4.2pp，未过 5pp 门，且叠着 #79，不记骨架账。
- 护栏 5 题 heading 缺席，路由仍是 `theme_analysis` / `theme-research` / 0.98。它们也全是 degraded，说明预算/judge 问题不是护栏注入造成的。

因此：骨架在残差档抬了诚实交付、压了空壳；剥句率未知；不能凭 eb 下跌主张绑定变差，也不能凭合规上涨主张翻默认。

## 4. 护栏 5 题（on 臂 ×1）

| id | run_id | outcome | heading 在产物 | question_type | owner | conf | 墙钟 s |
|---|---|---|---|---|---|---|---|
| G01 | `run_20260816_152745_016660` | degraded | 否 | theme_analysis | theme-research | 0.98 | 86.0 |
| G02 | `run_20260816_152910_997321` | degraded | 否 | theme_analysis | theme-research | 0.98 | 96.9 |
| G03 | `run_20260816_153047_855569` | degraded | 否 | theme_analysis | theme-research | 0.98 | 134.3 |
| G04 | `run_20260816_153302_304792` | degraded | 否 | theme_analysis | theme-research | 0.98 | 92.2 |
| G05 | `run_20260816_153434_648208` | degraded | 否 | theme_analysis | theme-research | 0.98 | 202.8 |

墙钟 86.0–202.8s（约 86–203s）。五题全 degraded，heading 缺席，路由未漂。

## 5. 逐槽

| slot | run_id | stratum | outcome | 合规 | 空壳 | 宕机候选 | judge | peel | eb | s |
|---|---|---|---|---|---|---|---|---|---|---|
| off:L01:r1 | `run_20260816_131941_597875` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 153.9 |
| off:L01:r2 | `run_20260816_141323_891938` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 94.7 |
| off:L01:r3 | `run_20260816_145303_909828` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 2.2 |
| off:L02:r1 | `run_20260816_132215_514615` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 97.5 |
| off:L02:r2 | `run_20260816_141458_531483` | outlook | degraded |  |  | Y | unavailable | — | 1.00 | 167.8 |
| off:L02:r3 | `run_20260816_145304_914413` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 1.4 |
| off:L03:r1 | `run_20260816_132352_974989` | outlook | degraded |  |  | Y | unavailable | — | 1.00 | 75.7 |
| off:L03:r2 | `run_20260816_141747_352464` | outlook | degraded |  |  | Y | unavailable | — | 1.00 | 85.2 |
| off:L03:r3 | `run_20260816_145306_491085` | outlook | degraded |  |  | Y | unavailable | — | 1.00 | 55.7 |
| off:L04:r1 | `run_20260816_132508_671289` | outlook | completed |  | Y |  | not_applicable | — | — | 32.6 |
| off:L04:r2 | `run_20260816_141911_524579` | outlook | completed |  | Y |  | not_applicable | — | — | 12.6 |
| off:L04:r3 | `run_20260816_145402_111045` | outlook | completed |  | Y |  | not_applicable | — | — | 181.1 |
| off:L05:r1 | `run_20260816_132541_309060` | outlook | degraded |  |  | Y | unavailable | — | 0.50 | 159.2 |
| off:L05:r2 | `run_20260816_141924_151961` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 23.1 |
| off:L05:r3 | `run_20260816_145703_468660` | outlook | completed |  | Y |  | repaired | — | 0.00 | 41.0 |
| off:L06:r1 | `run_20260816_132820_616808` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 152.6 |
| off:L06:r2 | `run_20260816_141947_282925` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 74.1 |
| off:L06:r3 | `run_20260816_145744_255155` | residual | completed |  | Y |  | repaired | — | 0.50 | 72.6 |
| off:L07:r1 | `run_20260816_133053_048944` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 145.3 |
| off:L07:r2 | `run_20260816_142101_432178` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 52.2 |
| off:L07:r3 | `run_20260816_145856_833358` | residual | completed |  | Y |  | passed | — | 1.00 | 79.3 |
| off:L08:r1 | `run_20260816_133318_370660` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 117.4 |
| off:L08:r2 | `run_20260816_142153_584405` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 81.5 |
| off:L08:r3 | `run_20260816_150016_268337` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 81.3 |
| off:L09:r1 | `run_20260816_133515_785894` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 76.3 |
| off:L09:r2 | `run_20260816_142315_062491` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 93.8 |
| off:L09:r3 | `run_20260816_150138_533408` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 52.4 |
| off:L10:r1 | `run_20260816_133632_116697` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 92.7 |
| off:L10:r2 | `run_20260816_142448_834933` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 71.3 |
| off:L10:r3 | `run_20260816_150229_846926` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 54.0 |
| off:L11:r1 | `run_20260816_133804_792028` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 92.6 |
| off:L11:r2 | `run_20260816_142600_147474` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 68.9 |
| off:L11:r3 | `run_20260816_150323_934192` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 52.8 |
| off:L12:r1 | `run_20260816_133937_556962` | residual | completed |  | Y |  | not_applicable | — | — | 29.3 |
| off:L12:r2 | `run_20260816_142709_074150` | residual | completed |  | Y |  | not_applicable | — | — | 10.7 |
| off:L12:r3 | `run_20260816_150416_666327` | residual | completed |  | Y |  | not_applicable | — | — | 14.9 |
| off:L13:r1 | `run_20260816_134006_860925` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 117.4 |
| off:L13:r2 | `run_20260816_142719_739643` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 42.7 |
| off:L13:r3 | `run_20260816_150431_520170` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 67.7 |
| off:L14:r1 | `run_20260816_134204_157437` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 147.9 |
| off:L14:r2 | `run_20260816_142802_470173` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 72.6 |
| off:L14:r3 | `run_20260816_150539_234690` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 73.0 |
| off:L15:r1 | `run_20260816_134431_995915` | residual | completed |  | Y |  | not_applicable | — | — | 29.5 |
| off:L15:r2 | `run_20260816_142915_120504` | residual | completed |  | Y |  | not_applicable | — | — | 10.9 |
| off:L15:r3 | `run_20260816_150652_252468` | residual | completed |  | Y |  | not_applicable | — | — | 12.4 |
| on:L01:r1 | `run_20260816_134501_567111` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 125.9 |
| on:L01:r2 | `run_20260816_142926_045912` | outlook | degraded |  |  | Y | unavailable | — | 1.00 | 85.6 |
| on:L01:r3 | `run_20260816_150704_735781` | outlook | completed |  | Y |  | repaired | — | 0.50 | 61.8 |
| on:L02:r1 | `run_20260816_134707_450640` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 240.5 |
| on:L02:r2 | `run_20260816_143051_597377` | outlook | degraded |  |  | Y | unavailable | — | 1.00 | 70.4 |
| on:L02:r3 | `run_20260816_150806_463950` | outlook | degraded |  |  | Y | unavailable | — | 0.50 | 156.6 |
| on:L03:r1 | `run_20260816_135107_975207` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 93.1 |
| on:L03:r2 | `run_20260816_143201_970729` | outlook | degraded |  |  | Y | unavailable | — | 1.00 | 49.6 |
| on:L03:r3 | `run_20260816_151043_076043` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 24.9 |
| on:L04:r1 | `run_20260816_135241_033691` | outlook | completed | Y |  |  | not_applicable | — | — | 36.0 |
| on:L04:r2 | `run_20260816_143251_595542` | outlook | completed | Y |  |  | not_applicable | — | — | 15.3 |
| on:L04:r3 | `run_20260816_151107_933626` | outlook | completed | Y |  |  | not_applicable | — | — | 20.3 |
| on:L05:r1 | `run_20260816_135317_054634` | outlook | degraded | Y |  |  | unavailable | — | 0.00 | 124.2 |
| on:L05:r2 | `run_20260816_143306_869690` | outlook | degraded |  |  | Y | unavailable | — | 0.50 | 234.8 |
| on:L05:r3 | `run_20260816_151128_245406` | outlook | degraded |  |  | Y | unavailable | — | 0.50 | 205.3 |
| on:L06:r1 | `run_20260816_135521_457493` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 94.2 |
| on:L06:r2 | `run_20260816_143701_843132` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 32.0 |
| on:L06:r3 | `run_20260816_151453_596709` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 188.6 |
| on:L07:r1 | `run_20260816_135656_547632` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 154.6 |
| on:L07:r2 | `run_20260816_144208_249817` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 1.7 |
| on:L07:r3 | `run_20260816_151802_173821` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 108.1 |
| on:L08:r1 | `run_20260816_135930_251231` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 139.4 |
| on:L08:r2 | `run_20260816_144209_529448` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 0.7 |
| on:L08:r3 | `run_20260816_151950_273650` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 62.2 |
| on:L09:r1 | `run_20260816_140149_736465` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 78.6 |
| on:L09:r2 | `run_20260816_144210_204460` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 0.7 |
| on:L09:r3 | `run_20260816_152052_478936` | residual | degraded |  |  | Y | unavailable | — | 0.50 | 93.5 |
| on:L10:r1 | `run_20260816_140308_015595` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 147.3 |
| on:L10:r2 | `run_20260816_144210_837104` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 0.6 |
| on:L10:r3 | `run_20260816_152225_996472` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 68.9 |
| on:L11:r1 | `run_20260816_140535_372157` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 153.9 |
| on:L11:r2 | `run_20260816_144211_455737` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 0.6 |
| on:L11:r3 | `run_20260816_152334_832994` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 73.9 |
| on:L12:r1 | `run_20260816_140809_489335` | residual | completed | Y |  |  | not_applicable | — | — | 37.5 |
| on:L12:r2 | `run_20260816_144212_072613` | residual | completed |  | Y |  | not_applicable | — | — | 81.2 |
| on:L12:r3 | `run_20260816_152448_705880` | residual | completed | Y |  |  | not_applicable | — | — | 15.8 |
| on:L13:r1 | `run_20260816_140846_946829` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 153.6 |
| on:L13:r2 | `run_20260816_145259_437793` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 2.1 |
| on:L13:r3 | `run_20260816_152504_496398` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 79.5 |
| on:L14:r1 | `run_20260816_141120_435868` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 92.5 |
| on:L14:r2 | `run_20260816_145301_547488` | residual | degraded | Y |  |  | unavailable | — | 0.00 | 0.6 |
| on:L14:r3 | `run_20260816_152623_952341` | residual | degraded |  |  | Y | unavailable | — | 1.00 | 68.3 |
| on:L15:r1 | `run_20260816_141252_913293` | residual | completed | Y |  |  | not_applicable | — | — | 30.9 |
| on:L15:r2 | `run_20260816_145302_132176` | residual | completed |  | Y |  | not_applicable | — | — | 0.6 |
| on:L15:r3 | `run_20260816_152732_276162` | residual | completed | Y |  |  | not_applicable | — | — | 12.7 |

degraded 不改写成 failed。清污 8+1+3 不出现在本表。

## 6. 回链

- FREEZE_ONLY `live_ab_ran` 指向本文件，并注明 13:19 清污重跑（引 closeout handoff §2）。
- **不改**夹具 `sample_design.live_ab_ran`：加载器要求该字段保持 `false`。

## 7. 收口后清理（已做）

1. sidecar **21888** 已于 **15:39:07** 干净退出（`sidecar.err.log`：`Shutting down` → `Finished server process [21888]`）。收口时 `ps -p 21888` 已空；`lsof -nP -iTCP:8793 -sTCP:LISTEN` 无 LISTEN。launcher 写明「评测结束即停，不要用它替换 8792」。
2. runner **36401** 已自然退出（15:37:57 `all slots processed`）；`runner.pid` / 日志 / progress / `score.json` 原地留档。
3. 8792 未动（仍 `773b3d7e` / ready 200）；未翻 `ASK_LONGTAIL_BASELINE` 默认。

## 8. 边界

- 不改 runner / 夹具 / 触发条件。
- 不在 `docs/dsh-absorption-spec` 提交本文件。
- 10 题窗仍等分诊/预算回归处置，不在本收据里开。
