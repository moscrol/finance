# Round 5 · 轨道 B：preflight 数据源盖戳 + RU-3 并行字段 + 批 #3

- 日期：2026-08-15 · 角色：执行方（轨道 B）· 检阅方：本 handoff 作者
- 协议母本：`docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`——§1 红线、
  §1.5 并行协调、§2 七步、§6 打回条件全部沿用。开工前读母本「轮次记录」
  「检阅方批注 · Round 4 收口」。

## 0. 检阅结论（先读）

Round 4 全部 PASS 已合：#21/#25 合入，#22/#23 内容随 #25 落地按 supersede
关闭。你报告里 L307 的「A 组大量 no_evidence 描述性对照」检阅方已定位到
根因：批窗口内 `finance_query` 秒抛 `tool_exception`（`detail=""`），
数据层故障，非你缝、非量具问题，你的分类正确。E-007 检阅方钻探结果见
母本批注（答案-绑定分道），M1 归轨道 A，你不动。

## 1. 任务 1：preflight 数据源盖戳（开批 #3 前落地）

批 #2 暴露：身份盖戳只覆盖代码身份，不覆盖数据层健康——A 组 7 题的
no_evidence 与代码行为混在同一批读数里。实现（EVAL_ONLY，你的缝）：

1. 开批前对核心检索工具做冒烟探针（至少 `finance_query` 一条已知可答
   查询），结果写进产物 `preflight_detail`（如
   `data_probe: finance_query=ok/tool_exception`）。
2. 探针失败的处置**写死**：照跑但产物顶层带响亮标注（该批 A 组读数
   视为窗口污染），或中止——二选一，写进代码注释与文档，不留默认。
3. 账本登记新预测（你的命名空间）：探针失败的批，其产物必须可被评审
   一眼识别为污染窗口；静默混批即 refuted。

## 2. 任务 2：RU-3——`episode_fulfilled_hashed` 并行字段

按你批 #2 报告 RU-3 的处方实现：产物每 turn 并行写
`episode_fulfilled_hashed`（episode 层已 fulfilled 且带哈希的格数），
与 `evidence_bound` 同时在场、不互相覆盖。E-007 类冲突（B3#2：episode
fulfilled=2 vs eb=0）从「要人肉开 run 目录」变成产物内一眼可见。
用 B3#2 冻结 run 作夹具断言两字段并存且不相等。

## 3. 任务 3：批 #3（等两个用户前置）

**前置**：①用户切新快照（main @ `788afd4e`，含 A 的证据序号契约）；
②用户处理 `finance_query` 数据层故障（或明确接受污染窗口照跑）。
两者未齐不开批；齐了按下列执行：

1. 同 qc28 全集、同预算，产物 `*-r5-clean-baseline-3.json`（UTC 命名规范），
   sha256 进 git。开批前跑任务 1 的探针。
2. **R-10 N=3 收口**：B 组按题出 3 批交付率表，按你 R-10 行判据结案
   （outcome 引三批 sha256）。
3. **给 A 的 R-23 读数**：修复轮携证据收尾的 case（批 #1 B1/B7、批 #2
   B5/C7 同形）绑定是否成功、eb 是否 >0；`unknown/truncated evidence hash`
   拒收是否再现。你出数，判归 A。
4. **R-09 回填（你的行）**：新快照 finish 应带 `rejection_code`/
   `rejection_reason`（无拒收=`none`/空串）。字段在场性 + 有拒收时
   非空 → 按你行判据回填 outcome。
5. 沿用批 #2 的读法纪律：多条 finish 取末条；`execution_state_aggregate`
   读 case 终态。

## 4. 边界与缝

- 可改：`intelligence/eval/`、其测试、`docs/verification/`、账本你的段。
- 不可改：`intelligence/runtime/`、`episode_protocol.py`（A 缝——E-007
  M1 进行中）、数据层本体。
- live-lock 归你（批 #3 是本轮唯一 live）。独立 worktree + 独立分支。

## 5. 交付四样（不变）

报告（validate-report.sh RC:0）、账本 diff、PR（gitea）、轮次小结
（≤10 行，追加母本「轮次记录」；你批 #2 的小结记得一并补录——上轮
因 #20 未合你没写母本，现在母本已在 main）。
