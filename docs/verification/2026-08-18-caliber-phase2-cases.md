# Phase 2 题集契约读数（2026-08-18）

- 树：`/Users/a77/fwp-wt-caliber-p2` `fix/caliber-phase2-cases`
- 叠在：`fix/caliber-phase1-scorer` @ `165226db`（#199）
- 设计：`docs/superpowers/specs/2026-08-18-measured-value-caliber-contract-design.md`（#198）
- 派单：`docs/handoffs/2026-08-18-caliber-contract-phase1-3-dispatch.md`
- 未切 8792，未动产品代码，未重跑 28 题

## 改了什么

1. 7 道非相对时间题：把 `date` 写进 `query`（A3 / B1 / B2 / B3 / B6 / B8 / C3）。
2. runner 增加 `effective_query`：`date` 不在题面时发送 `f"{date} {query}"`；已带日期不叠写。A8 / C6 正典 query 保持「现在 / 最近」，发送时仍补日期。
3. B6 判据改为「题面未附材料，必须要求澄清」；去掉 `must_mention: [graph_only, 观察列表]`；overlay → `structured` + `required_any_phrases`。
4. A8 / C6 overlay 加 `cohort: relative_time`；看板可判子集只计 `in_main_truth_denominator()`。

## 题面 sha256（判据 H）

正典文件：

| | sha256 |
|---|---|
| 改前 | `a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6` |
| 改后 | `d98a65573862fc461da9b76857a2343187bdf4902dae4b976b849f5f9348abfc` |

逐题 query（未改的 A8 / C6 也列出）：

| id | 改前 | 改后 |
|---|---|---|
| A3-stock-deep-dive | 立新能源怎么看 | 2026-07-23 立新能源怎么看 |
| B1-theme-photoresist | 光刻胶 | 2026-06-11 光刻胶 |
| B2-theme-liquid-cooling | 液冷 | 2026-06-11 液冷 |
| B3-theme-solid-state-battery | 固态电池 | 2026-06-11 固态电池 |
| B6-sellside-distillation | 把这份卖方材料提纯一下，哪些是硬事实、哪些只能进图谱、哪些只能进观察列表 | 2026-07-23 把这份卖方材料提纯一下，哪些是硬事实、哪些只能进图谱、哪些只能进观察列表 |
| B8-valuation-band | 立新能源现在贵不贵，隐含了什么预期 | 2026-07-23 立新能源现在贵不贵，隐含了什么预期 |
| C3-empty-table | 立新能源的技术面快照给我看一下 | 2026-07-23 立新能源的技术面快照给我看一下 |
| A8-market-stage | 现在市场处于什么阶段，第几天了 | （正典未改；发送层补 `2026-07-23 `） |
| C6-strict-definition | 最近哪些板块比较强，双红的那种 | （正典未改；发送层补 `2026-07-23 `） |

B6 `pass_rule` 改为澄清要求；`must_mention` 删除。

## 验收

| 判据 | 读数 |
|---|---|
| H. 题面可追溯 | 上表。正典 sha256 改前/改后各一份 |
| I. 可判子集 16→≥22 | **本 Phase 单独达不到。** 9 道无日期锚里，A8/C6/B1/B2/B3/B8 因相对时间 / `inherit_from` / `semantic_required` 仍不可判；A3/C3 已在可判里（失败）。A8/C6 出主分母不改变 16，因为它们本来就不是 PASS/FAIL。分母上升要等日期真下达到产品的新 28 题 run |
| J. A3 含 12.11 | 08-18 答案抽出数无 12.11（仍是 08-17 价）。旧 artifact 无法验证 date 下达；待 sidecar 重跑 |
| K. 带日期 19 题不降 | 08-18 对照 Phase 1 复算：除 B6 ❌→✅ 外，其余 27 题真值列不变 |
| L. 前置不得 `--force` | 本 Phase 未重跑 |

08-18 同 artifact 复算（Phase 1 尺子 + Phase 2 题集）：

| | Phase 1 后 | Phase 2 后 |
|---|---|---|
| B6 | ❌ 失败（缺 graph_only / 观察列表） | ✅ 通过（澄清命中「缺少 / 你指的是」） |
| 真值 | 通过 6 / 失败 10 / 不可判 12 | 通过 7 / 失败 9 / 不可判 12 |
| 可判 | 6/16 | 7/16 |

08-15 baseline：B6 同样 ❌→✅；可判 7/17（B7 在该份上是 ❔→✅ 进入分母，与 Phase 1 一致；A8/C6 仍不可判，出分母无影响）。

解析：08-18 / 08-15 各 28 题、真值列非空 28。

## 收据

```
ls /tmp/caliber-p2/after-0818.txt /tmp/caliber-p2/after-0815.txt
```

artifact：`20260818T051630Z.json`（#198 树）、`20260815T1005Z-r5-clean-baseline-3.json`（本树）。

pytest：`test_acceptance_verdict` + `test_acceptance_board` 69；acceptance 相关 165 passed。
