# Round 5 · 轨道 A：E-007 答案-绑定分道 M1 + tool_exception 详情 + R-23 收口

- 日期：2026-08-15 · 角色：执行方（轨道 A）· 检阅方：本 handoff 作者
- 协议母本：`docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`——§1 红线、
  §1.5 并行协调、§2 七步、§6 打回条件全部沿用。开工前读母本「轮次记录」
  「检阅方批注 · Round 4 收口」的三条勘探。

## 0. 本轮新事实（已由检阅方独立核实）

1. 你的 #24（证据序号契约）已合入 main（`788afd4e` 可及），**尚未部署**；
   8792 仍跑 `cb09f895`。R-23 的 after 测量等用户切新快照 + B 批 #3。
2. B 批 #2 已落盘（`20260815T0302Z-r4-clean-baseline-2.json`，
   `sha256=51e61710…`）。同形誊抄失败本批换人到 B5/C7
   （`invalid_action.reason` 均为 truncated evidence hash）——R-23 的
   before 证据已有两批。
3. 批 #2 中 A 组 7 题 `no_evidence` 是数据层 `finance_query` 故障
   （检阅方已定位，见母本批注），**不是**你的缝，不要顺手修。

## 1. 任务 1：E-007 M1——答案文本与绑定分道（主靶）

标本与对照全部冻结可用：

- **标本**：B3#2 `run_20260815_111907_054023`。episode 两格 fulfilled
  （direct_assessment 3 哈希、chain_mapping 8 哈希）、counterpoint 真缺口、
  末条 finish `repair_model_stop` `slips=2`、structural partial 仅剩
  counterpoint 缺口——契约侧全对。但交付 answer 122 字**只含 counterpoint
  内容**（模型自述「chain_mapping 中的未核验表述已删除」），
  citations=0 → `evidence_bound=0`。
- **对照**（同 `repair_model_stop`、slips>0、eb>0）：A9#2
  `run_20260815_...`（eb=7）、B2#2（eb=6）、C6#2（eb=11）、B5#1
  `run_20260815_034650_133624`（eb=3）。run_id 从批产物 turns[-1] 取。

M1 要回答的：交付层从哪一步组装最终 answer？为什么标本里 fulfilled 格的
正文内容缺席而绑定保留？（候选缝：修复轮 FINAL_JSON 的 answer 字段 vs
draft 合成路径 vs adapter 的公开投影。）产出 PRIMARY + fix_type +
可证伪预测进账本（你的命名空间）。

- **单变量纪律**：若根因落在 `continuous_turn_adapter.py`——R-04 的
  挂起理由（与 F-001 修复轮收尾缝叠变量）已随 R-21 confirmed 解除，
  可以提议动它，但**本轮只出 M1 + 提案**，实现等检阅方裁决，避免与
  R-23 部署窗重叠。
- 注意投影 fail-closed 本身是对的：绑定声称交付而正文缺席时给 0 引用
  **不是** bug；修的是「正文为何缺席」或「绑定为何未随删改收缩」。

## 2. 任务 2：`tool_exception` 吞详情（小修，你的缝）

批 #2 里 `finance_query` 异常落盘为 `{"error":"tool_exception","detail":""}`
——异常类型/消息被吞，trace 无法诊断。修：runtime 工具包装层把异常类名 +
首行消息写进 `detail`（截断到合理长度，不落敏感路径）；单测：抛内置异常
断言 detail 非空。**不改**工具本身、不碰数据层。

## 3. 任务 3：R-23 收口（等部署 + 批 #3）

用户切新快照、B 跑批 #3 后：按 R-23 行判据读批 #3——同形 case（主路径
deadline 耗尽、修复轮携证据收尾）绑定成功且 eb>0；`unknown evidence hash`
/ truncated 誊抄拒收再现即 refuted。收口写进账本你的行。若批 #3 因数据层
未修而 A 组仍污染：R-23 判据只看修复轮绑定形状（B5/C7 同形题），
数据层污染不阻塞收口，但要在 outcome 里注明窗口条件。

## 4. 边界与缝

- 可改：`intelligence/runtime/`（含 adapter——仅 M1 提案）、
  `intelligence/services/episode_protocol.py`、工具包装层、对应测试。
- 不可改：`intelligence/eval/`（B 缝）、数据层（`finance_query` 本体、
  DuckDB、行情源）。
- 独立 worktree + 独立分支；不碰主 checkout；8792 只读。

## 5. 交付四样（不变）

报告（validate-report.sh RC:0）、账本 diff（你的段）、PR（gitea）、
轮次小结（≤10 行，追加母本「轮次记录」）。
