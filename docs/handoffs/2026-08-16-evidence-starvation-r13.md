# handoff: R-20260816-13 宽题取证饿死分诊（评估型：先判形状，再谈修）

- 日期：2026-08-16
- 接收方：分诊/修复 agent
- 基线：`5b1a3869`（#94 勘误后十题窗收据、两轮检阅批注、#97 eb 案开行合入的 main）；
  从它拉分支
- 决策背景：R-06（judge 窗）已结 H9、部署 8792=`6cd0756e` 并过十题窗。生产首发用户实测
  `run_20260816_205439_732198` 暴露上游新缝：**judge 修复未回归**（judge repaired 正常），
  取证层被饿死。
- 相邻案（**不同缝，别抢结案权**）：`R-20260816-11`（#97，
  `docs/handoffs/2026-08-16-outlook-eb-judgment-slot.md`）正在对十题窗「判断槽
  0-hash → eb 下跌」做 M2 差分。本案的工具批读数若在其冻结样本上同形，作为
  **移交证据**供其「独立 PRIMARY 候选」评估；eb 结案权在 R-11，本案不代结、不并案。

## 主症（检阅方已做 M1 分诊，run 已冻结，归因不用重做，重放要做）

run_20260816_205439_732198（20:54，user=default，standard，8792 @ `6cd0756e`）：

- 问题「分析一下医药板块，板块有哪些个股有机会」（宽题：板块扫描+选股）
- 事实链（episode 事件毫秒级时间戳）：3 分支跑 55s（branch-2「核验候选公司业务催化」
  `deadline_exhausted`、0 证据）→ 56:34 model turn 思考 60s 才发工具 → 57:34 四发
  `evidence_search` **瞬时** `tool_timeout`（`queued_ms` 0.1–2.9ms，零执行）+ 一发
  `finance_query` `tool_budget_exhausted` → 20s 后主道 `deadline_exhausted` → repair 30s
  救回 → judge **repaired**，9 句判断被证据边界打回 → partial 交付（降级链路诚实，正常）
- 代码锚点（两个不同的闸，别混）：
  - **时间闸**：`intelligence/runtime/episode_tool_batch.py` L355-366——
    `context.deadline.stage_timeout(tool_batch_timeout_seconds(policy))` ≤0 时全批
    直接标 `tool_timeout`，零执行。四发 evidence_search 走的这里。
  - **次数闸**：同文件 L340-352——`_select(candidates, remaining_slots)` 落选者标
    `tool_budget_exhausted`。第五发 finance_query 走的这里。
  - 映射：`intelligence/runtime/agent_episode.py` L381（timeout→tool_timeout）、
    L698（finalization_reason）
- 已排除：provider 故障（五发全是本地闸门字符串，非 5xx/断连）；R-06 回归
  （judge repaired；standard 地板 50 在服务树生效）；judge 那次 transient attempt
  因 repaired 出口无时钟无法分类（见 T1 顺路条款）

## 任务

### T1 埋点（不改行为，PR 到 main）

- 工具批派发点补 #84 同款时钟账，落进 `tool_request`/`tool_error` 事件：
  `batch_grant_asked`（`tool_batch_timeout_seconds(policy)` 名义值）/
  `stage_timeout_granted`（实授）/ `episode_remaining_at_dispatch` /
  `remaining_slots_at_dispatch` / `turn_elapsed_at_dispatch`
- 关键坑：`tool_timeout` 与 `tool_budget_exhausted` 是两个闸（时间 vs 次数），
  现在事件里只有错误字符串，分不开「窗关了」和「次数用完」——两闸各自读数都要落
- **顺路条款（同 PR 或紧邻小 PR，R-10 前置，两轮检阅批注均已点名）**：
  judge 时钟补 repaired/passed 出口（`_attach_judge_clock` 现仅 2 个调用点，
  `episode_semantic_verifier.py` L711/712）+ `judge_attempt_index`。
  本 run 的 repaired+transient 混合形（issues 带 transient、三元组全 None）是活证
- 纪律照 #84：观测不干预、fixture 钉住（本 run 冻成夹具）、不切 8792

### T2 重放（8795 侧车）

- T1 合 main 后，8795 从 `02fa203e`（已过时）切到含 T1 的 tip；**一次切到位，
  R-10 结案重放与本案共用同一侧车同一窗**（判据互不混）。R-11 案若需含读数的
  重放，也用这棵树，按其自己的冻结样本跑
- 重放集（standard，除注明外）：医药宽题原题 ×3；同形宽题（板块扫描/选股形）×2；
  窄题对照 ×2；医药宽题 **deep 档 ×2** 取「自然完成值」（各阶段不被截断时的
  真实耗时——按 serial-phase 笔记「扫描相邻 artifact 自然完成值」方法）
- 对齐键 `slot`+`run_id`；杀进程 `ps -p` 精确 pid，不用 `pgrep/pkill -f`

### T3 判定（账本 `R-20260816-13` 预注册判据，逐字）

> 8795 含工具批埋点 tip 读数；**deep 自然完成值合计（分支+取证+合成+核验）>
> standard 总窗 → H-a**（总工作量与档位预算不相容，allocator 无解，走架构支）；
> **evidence_search 自然时长小（单发 ≤10s）且失败仅出现在 dispatch 时
> `stage_timeout_granted`≤0 或 slot 耗尽的槽 → H-c**（顺序/信号可救，窗内可修）。
> 缺字段不得结案。混合形状分桶报告。

对 R-11 冻结样本（`post:L01:r3` / `post:L03:r2` / `post:L05:r2`）的工具批读数：
同形则整理为移交证据附收据，**判定权在 R-11**。

### T4 处置与收据

- **H-c**：最小修复候选各自独立小 PR + 预注册预测——①派发前把「批窗剩余」作为
  信号给 model turn（预算可见性给到花钱的人）；②取证类调用顺序前移（planner 侧）。
  不动 T / 批窗值 / slot 上限 / 档位
- **H-a**：不调参。开架构案文档：预计算证据包 / 异步 track 承接
  （接 knevo q8 report→track 接力，在途账板「下一步」第 2 条）/ 宽题显式路由 deep 档。
  **路由与产品档位变更升格用户拍板，不代决**
- 收据 `docs/verification/2026-08-16-evidence-starvation-r13.md`：每槽表
  （dispatch 五元组 × 错误类 × 自然时长）+ H-a/H-c 分布 + 对 R-11 的移交证据段 +
  处置建议
- 台账：R-13 由收据结案（confirmed/refuted，部分验证不写 confirmed）；
  R-14 绊线常在

## 边界

- 不碰 8792（分诊全程 8795 侧车）；处置若合 main，部署走观测台窗口协议
  （就地切 + ready 查验 + 回滚锚），不由本案执行方切
- 不动 judge 窗（R-06 已结）/ T / `_REPAIR_SECONDS_CAP` / 档位 / reserve（R-09 另案）；
  不放宽 5pp；不翻 `ASK_LONGTAIL_BASELINE` / `ASK_JUDGE_RECHECK` / `ASK_DEGRADED_FALLBACK`
- **绊线 `R-20260816-14`**：下一份自称修「宽题取证饿死」的 PR，diff 含
  `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot 上限 / 档位上调且无
  08-08 式延迟实测 + 全路由影响面 → 直接 refuted
- 观测台薄账不动（写入者=检阅方）；#94 勘误链路已闭，本案不重开 F01；
  不改写 R-11 行原文、不动其冻结样本判定
- 与 R-10 共享侧车但**判据不得互混**：R-10 看 judge 首轮 asked；R-13 看工具批派发读数

## 完成定义（按序）

1. T1 埋点 PR（含 judge 时钟顺路条款）合 main
2. 8795 切含 T1 的 tip（同窗供 R-10 + R-13，R-11 可搭车）；T2 重放；T3 判定；
   收据 + 账本结案
3. H-c → 处置小 PR（预注册预测，合 main 后走观测台部署窗）；
   H-a → 架构案文档 + 升格用户拍板
4. 检阅方复核（住址：本 handoff「轮次记录」节）

## 轮次记录

### 2026-08-16 执行方 T1（未合、未切 8792）

- 分支 `fix/r13-t1-dispatch-clock`：工具批派发五元组进 `tool_request`/`tool_error`（不进模型消息）；judge `passed`/`repaired` 出口补 `_attach_judge_clock` + `judge_attempt_index`。
- 夹具 `intelligence/tests/fixtures/r13-evidence-starvation-732198.json` 钉住 732198 两闸形状。未动 T / 批窗 / slot / 档位。
- 下一步：PR 合 main 后按交接切 8795 做 T2。
