# Handoff：工具饥饿信号——把「agent 想要但没有的能力」变成结构化需求数据

日期：2026-08-18
派单人：主 agent（2026-08-18 评估盘点批次，ai-agent-book 第 5 章判定更正的第一步）
关联：与 `2026-08-18-dead-assets-consumption-wiring.md`（死资产接线）天然联动——饥饿数据是「下一批注册什么 dataset」的输入。两单改动面不同文件，可并行。

## 背景

生产 agent 是封闭工具注册表，自己不能造工具；每种新问法都靠人工判断要不要注册新
dataset（今天的死资产单就是拍脑袋选了四张表）。书里第 5 章的元能力（代码=能造工具的
工具）在运行时层是有意缺口；补它之前先要**可观测**：agent 到底在哪些问题上「想要
而不得」。本单只做观测，不做任何自动造工具。

## 已核实事实（派单前实测）

1. `intelligence/runtime/agent.py` `_run_tool()`：模型点名不存在的工具 → 只回
   `未知工具「name」。` 一句话给模型，**无结构化留痕**。
2. `intelligence/services/episode_tools.py` `_finance_query_failure_result()`：语义层
   拒绝（dataset/字段/筛选无效）已产出结构化 `ToolRunResult`（`failure_code=
   "invalid_query"`），但 observation 截 160 字，**被拒的 dataset/metrics 请求名是否
   完整落盘待核实**。
3. 生产 run 目录：`$FORESIGHT_USERS_DIR/<user>/runs/`（linxiaoqi5111 现有 376 个 run），
   sidecar 探针 run 另落 `~/.finance-runtime/live-probe-traceability/.../runs/`。
4. 两条运行时车道：continuous episode（生产 ask 主路）与 inline agent
   （`runtime/agent.py` 12 工具 dispatch dict）。**执行方第一步先核实每条车道的工具事件
   分别持久化到哪**，别照抄本单假设。

## 目标

1. 三类饥饿事件结构化落盘（随 run 持久化，不新建全局服务）：
   - `unknown_tool`：模型点名注册表外的工具（工具名、参数键名、run_id、时间戳）
   - `finance_query_rejected`：语义层拒绝（完整请求 spec：dataset/metrics/dimensions/
     filters 摘要 + failure_code）——若现有 ToolRunResult 已够，只补缺失字段，别重造
   - `capability_denied`：工具在册但本轮 contract 未授权而模型点名要（若装配期已对模型
     隐藏、结构上观测不到，就在交接里写明「此类不可观测」并给理由，不硬造）
2. 聚合器：一条命令扫描 runs 目录出饥饿汇总（按事件类型 × 请求名计数 + 样本 run_id），
   人读 md + 机读 json 落 `intelligence/eval/measurements/`。CLI 形态执行方定
   （`python -m intelligence.cli tool-hunger --since 7d` 或 eval/ 脚本均可）。
3. 台账登记复查节奏建议（例如每周扫一次、进决策队列），最终节奏用户定。

## 非目标（明确不做）

- 不改 agent 行为：回给模型的文案一个字不动，检索/合成/prompt 不动
- 不做答案文本挖掘（「算不了」语义识别是另一档，噪声大，不在本单）
- 不自动注册工具、不造代码解释器（那是有先决条件的后续，见章审追记）

## 实施边界

只动：

- `intelligence/runtime/agent.py` `_run_tool` 未知工具分支（加落痕）
- `intelligence/services/episode_tools.py` 拒绝路径（补字段，若需要）
- 聚合器新文件 + 测试
- `docs/handoffs/inflight/main.md` 登记

不动：#164（数据根）、#165（stale 旁路）、#170 死资产单的实现面；8792；launcher。

## 测试要求（先红后绿）

1. 未知工具调用 → 事件落盘且回给模型的文案不变（逐字节同旧）
2. finance_query 拒绝 → 事件含完整请求 dataset 名（造一个不存在的 dataset 断言）
3. 遥测写入抛异常 → 主流程不受影响（try/except 降级），且该降级有测试
4. 聚合器对 fixture runs 目录出正确计数与样本引用
5. 空 runs 目录 → 聚合器出空报告不崩

## live 验证（合并后，#152 sidecar，不碰 8792）

问一题引导 agent 用 finance_query 查**当前不存在的 dataset**（例：竞价——若死资产单
已先落地，换任意仍不存在者），跑完用聚合器扫 sidecar runs：应看见对应
`finance_query_rejected` 事件与请求名。收据路径写进交接。

## 红线

- 遥测失败不许影响主流程（宁可丢事件）
- 不切 8792
- 事件里不落用户身份之外的敏感内容（记 run_id 即可回溯）

## 验收标准

1. 四件套绿；上述 5 类测试全绿
2. live 收据：一条真实饥饿事件被聚合器看见
3. 交接说明含：两条车道的持久化事实核实结论、capability_denied 可观测性结论
4. 台账 + inflight 登记

## skill 与工具建议

skill：leila-runtime + tdd。工具：git worktree、pytest、live_probe、Gitea API。
