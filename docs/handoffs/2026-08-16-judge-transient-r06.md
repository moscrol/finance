# handoff: R-20260816-06 judge transient 分诊（闸 2 前置；用户已拍板选 2）

- 日期：2026-08-16
- 接收方：分诊/修复 agent
- 基线：`a8d4d968`（#88 卫生 HOLD、#89 豁免、#90 降级章法合入后的 main）；从它拉分支
- 决策背景：闸 2 三选一（豁免 §3），用户 16:58 拍板**选 2**——不翻闸、先修 judge。
  豁免已合 main：调 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`、`_REPAIR_SECONDS_CAP`、
  生产档位**不准动**（账本 `R-20260816-07` 是绊线：下一份自称「outlook 预算回归修复」的
  PR diff 若含这些上调且无 08-08 式延迟实测，直接 refuted）
- 运行时状态：决策已写入 `~/.finance-runtime/outlook-ab-20260816/GATES.json` 的
  `gate2_decision`；`budget_regression_landed` 保持 false，十题窗不开、8794 不起

## 主症（#89 的 45 槽分型已做完，不用重做）

- off 45：**22 槽「有稿、judge 已调、transient」**是窗口主症；10 槽空稿（L01 形，另案
  `R-20260816-03`）；9 槽无 episode（chat 路由）；3 槽 judge 跑通
- 护栏 G01–G05：theme-research 5/5 degraded、draft>0、同一 transient；无 off 基准，
  不归因长尾开关（绊线 `R-20260816-08`）
- 长尾窗大盘 73/95 槽 judge 降级——系统性，不是个别槽
- identity 已钉（另案 `R-20260816-09`，本轮不动）：空稿子集非 finalize 轮被 60s reserve
  扣到 8–20s，那是 `_BALANCED_SYNTHESIS_RESERVE` 杠杆，不是 T

## 任务

### T1 埋点（不改行为，PR 到 main）

judge 调用路径补齐 #84 同款时钟账：`timeout_asked` / `timeout_configured` /
`remaining_seconds_at_entry` + **原始异常类与摘要**。参照：

- #84 的形状：`intelligence/runtime/agent_episode.py` 的 `model_turn` /
  `repair_reentry` / `repair_model_retry` 事件（三元组记进 episode 台账）
- judge 侧空缺：#89 §4 明确「L01 r3 / L03 有稿 + judge transient，**无** judge
  `timeout_asked`（#84 未埋）」
- 关键坑：`llm_refine.py` 约 L296——provider 侧超时会被**压平成 `timeout`**，而
  `timeout` 在 judge 的瞬时故障白名单里。原始异常类（TimeoutError / HTTP status /
  连接错误）必须在压平**之前**抓，否则 H8/H9 分不开
- 纪律照 #84：观测不干预、离线钉住（fixture 测试），不切 8792

### T2 重放（8795 侧车）

- 8795 现在跑 `21dbf6c1`（无 T1 埋点）。T1 合 main 后，把 8795 切到含 T1 的 tip 再重放
  （侧车树自建，别停泊 `finance-workspace-21dbf6c1d83f`——那棵留给 R-03 identity）
- 重放集：22 个 transient 槽位里分层抽子集（outlook 若干 + theme G 组若干 + residual），
  每槽 ≥2 重复；对齐键 `slot`+`run_id` 沿长尾收据 §0.4
- 杀进程 `ps -p` 精确 pid，不用 `pgrep/pkill -f`

### T3 判定（账本 `R-20260816-06` 预注册判据，逐字）

> 8795/#84 树读数；**asked≤12 且墙钟≈asked → H9**；**asked≥20 且 5xx/连接 → H8**。
> 缺字段不得结案。

混合/其他形状分桶报告，不硬塞进 H8/H9。

### T4 处置与收据

- 收据：`docs/verification/2026-08-16-judge-transient-r06.md`——每槽三元组表
  （stop_reason × timeout_asked × 原始异常类）+ H8/H9 分布 + 处置建议
- **H8（provider 侧）**：换 judge provider（08-08 terra 先例；不抬档位表）
- **H9（客户端窗太紧）**：judge 窗调整（`ASK_SEMANTIC_JUDGE_WINDOW` /
  `derive_stage_caps` judge 比例）——#89 豁免不盖这条（明确「另案」），但必须附
  p50/p95 延迟实测 + 全路由影响面（08-08 式）；compose T / 修复帽仍不准动
- 台账：R-06 行由收据结案（confirmed/refuted，部分验证不写 confirmed）；
  `R-20260816-02` 保持 pending（条件句未触发）

## 完成定义（闸 2 链路，按序）

1. 处置 PR（修复或第二份豁免）合 main
2. 观测台 agent 开部署窗：8792 就地切含处置的 tip；**同窗**做 #88 HOLD 的目录卫生
   （`ln -sfn` → `773b3d7e73d7` 同 SHA 那套，见 #88）；`773b3d7e` 留回滚锚；
   切后必查 ready，失败 kickstart 同快照一次（决策队列 prewarm 行）
3. 眼 agent 翻 `budget_regression_landed=true`（GATES.json 引用处置 SHA + 本 handoff），
   起 8794 修前臂，跑十题窗；收据按预注册**单列 judge transient**，不算进
   #72/#75/#79 判断句存活

## 边界

- 不碰 8792（分诊全程 8795 侧车）；不动 `_BALANCED_SYNTHESIS_RESERVE`（R-09 另案）
- 不放宽 5pp；不动 `_CLAIM_POLICY` 七闸、判断句词表（`ANALYTICAL_MARKERS` 共享常量）
- 不翻 `ASK_LONGTAIL_BASELINE` / `ASK_JUDGE_RECHECK` / `ASK_DEGRADED_FALLBACK`
  （#90 已合但默认 off，其对照窗排在本案之后）
- 观测台薄账不动（写入者=检阅方）；本 handoff 不在 `docs/dsh-absorption-spec` 提交
