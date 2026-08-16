# 2026-08-16 书面豁免：不调 compose / 修复帽预算

roadmap_ref: 另案（P5；outlook 核验预算回归的闸 2 处置）

> 权威版在 `docs/outlook-r03-judge-exemption`。不要在 `docs/dsh-absorption-spec` 提交。

一句话：长尾 off 45 槽分型后，**豁免**把 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`、`_REPAIR_SECONDS_CAP=30` 或生产 T 调大当作本窗修复。窗口主症是有稿后 judge transient，不是 L01 空稿合成超时。翻闸 2 仍要用户拍板。

证据等级：**[实测]** = 2026-08-16 读过 `score.json` + 50 份 episode；8795 sidecar 已起。

## 1. 豁免范围 [实测]

豁免：

- 上调 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`（现 300）
- 上调 `repair_coordinator._REPAIR_SECONDS_CAP`（现 30）
- 上调 standard/deep `ResearchPolicy.total_seconds` / `synthesis_reserve`
- 把「调大预算」写成 outlook 四层回归的修后臂配方

不豁免（另案，未证实前不准改）：

- `ASK_SEMANTIC_JUDGE_WINDOW` 或 `derive_stage_caps` 的 judge 比例
- provider / 中转换型
- #72 / #75 / #79 行为

`R-20260816-02` 原文是条件句（「若动预算则…」）。本豁免让该条件不成立，行保持 `pending`，不写 confirmed/refuted。

## 2. 为什么豁免 [实测]

对齐键：`slot` + `run_id`（长尾收据 §0.4）。off 45：

| 形状 | n | 含义 |
|---|---|---|
| 无 episode（L04/L12/L15 chat） | 9 | 不是核验路径 |
| 空稿、judge 未调用 | 10 | 原 L01 形状；L01 三重复不同形 |
| 有稿、judge 已调用、transient | 22 | **窗口主症** |
| judge 跑完（passed/repaired） | 3 | 路径能成功 |

G01–G05：theme-research 5/5 degraded，draft>0，同一 transient。**无 off 基准**，不归因长尾开关。

调 T/30 修的是空稿修复帽，修不到 22 个已写出草稿的 judge 失败。08-08 先例是换 terra、**不**抬档位表；launcher 写明抬 judge 窗会饿死草稿。本轮没有新的延迟实测，不准拍数。

identity 另钉：空稿子集里非 finalize 轮被 60s reserve 扣到 8–20s。那是 `_BALANCED_SYNTHESIS_RESERVE` 杠杆，**不是** T。动它须另附 08-08 实测（账本 `R-20260816-09`），不进本豁免、不进闸 2。

## 3. 翻闸 2（用户拍板）

10 题窗闸 2 =「预算回归处置落地：修复已合 main，**或**分诊结论明确豁免」。

本文件是豁免草案，**不是**自动翻闸。用户须选：

1. **接受豁免并翻闸 2**：10 题修后臂仍是 `773b3d7e`（或之后含 #84 但不含预算改动的 tip）。收据必须单列 judge transient，不得算进 #72/#75/#79 判断句存活。
2. **不翻闸，先修 judge**：等 `R-20260816-06`（judge `timeout_asked` + 原始异常）分出 H8/H9，再按 08-08 给延迟实测 + 全路由影响面。
3. **不翻闸，先做完 R-03 三臂**：只回答 L01 空稿必要性；不修窗口主症。

台账：决策队列 row 58 是快照卫生（用户），row 59 是 prewarm SOP（已决）。本项应新立一行，owner=用户，关联闸 2。不要改观测台薄账（写入者=检阅方）。

## 4. 已做 / 未做

已做：45 槽三元组分型；G01–G05 并案；8795 sidecar @ `21dbf6c1` ready，不占 8792；identity 臂（L01×3 + L03×1）已收齐。

identity 要点：原 68s 空稿 finalize 0/3。非 finalize `asked=remaining−60`（GLM `_BALANCED_SYNTHESIS_RESERVE`）。L01 r3 / L03 有稿 + judge transient，**无** judge `timeout_asked`（#84 未埋）。调 T 不改 `min(90, T−40)`。

未做：3-tool / #72-off 单变量（停泊树保持干净）；judge 窗改动；`_BALANCED_SYNTHESIS_RESERVE` 改动；8792 链切 / kickstart。

## 5. 边界

- 不放宽 5pp；不改 `_CLAIM_POLICY`；不翻 `ASK_LONGTAIL_BASELINE` / `ASK_JUDGE_RECHECK`。
- 杀进程用 `ps -p`，不用 `pgrep -f`。
- 分诊正文：`docs/verification/2026-08-16-outlook-off-arm-typology-judge-case.md`。
