# 2026-09-15 · E2 P3h：确定性旁路收口——约束轮禁入无合同意识的执行面

分支 `fix/e2-boundary-closeout`，提交 `50687c0b`。前情：P3g（`f05d0681`，澄清挂起恢复重验）见 `2026-09-15-e2-p3g-pending-clarification-recovery.md`。

## 背景（不读会误判后面每个决定）

P3a–P3g 的全部读取收窄都实现在 **Episode 装配层（引擎 A）**。但 Workbench 有第二个执行面：引擎 B（skill 路由 + Ask 检索管线）与确定性 owner 交接——它们按题型直接检索、读库、外呼，**对 material_contract 零引用**（grep 实测）。任何一条把约束轮送进引擎 B 的路，都让 P3 的收窄整体失效。这就是门页从 P3a 起反复点名的「确定性旁路」。

三个掉落口（探明实测）：
1. `continuous_turn_adapter.py` 对 `DETERMINISTIC_OWNER_TYPES`（external_market / dated_market_review / market_watch / watchlist_digest / disclosure_scan——全是必然外呼/读库的题型）**主动让路**（declined）给引擎 B；
2. `ASK_CONTINUOUS_RUNTIME` 缺省是 **off**——env 一丢，所有 research 轮（含 material_only）都掉进引擎 B；
3. knowledge lane 的 fallback 检索直接调 `answer_query`。

可达反例（真实 decide_turn 输出）：「只用本地已有数据，不要联网。美股隔夜表现如何？」编译出 `('real','local_only')` 合同 + `question_type=external_market` → adapter 让路 → 引擎 B 外部行情 owner 拉外盘——local_only 被违反。

## 按发现顺序

1. 选片：余下 P3 按影响面排序，确定性旁路一条就能让 P3a–P3g 全部失效，先堵它。
2. 探明三个掉落口与可达形状（上节）；确认 orchestrator 的 P3d 过滤（stance/先验/视角）已含 needs_clarification，但只护「先验注入」，不护「整轮进引擎 B」。
3. 反例先红：20 个 adapter 反例（4 种约束合同 × 5 个确定性题型）+ 3 个 run_turn 全链反例。
4. 实现两道防线 + 共享谓词。
5. **误伤回归**：全量回归红了两个既有测试——query「继续检索」。根因：`compile_material_contract` 把**所有**「继续/接着」开头的日常追问（无 inherited 基底时）都编成 `state_unavailable`，而我的谓词把一切 needs_clarification 算进禁区。「基底未知」≠「声明了受限边界」——普通续轮必须保持既有引擎 B 行为。
6. 谓词加材料语境分界（见决策 2），全量回归恢复 813P/4S 零破坏。

## 决策与被否方案

### 决策 1：两道防线 + 一个共享谓词

| 方案 | 评价 | 结果 |
|---|---|---|
| 防线1（adapter 不让路，约束轮留在 Episode 收窄执行）+ 防线2（orchestrator 掉落总闸，含 knowledge fallback 条件）+ 谓词单一来源 | 防线1 是主路径正确性；防线2 兜 mode=off（env 缺省！）/adapter 未配置/让路后的所有掉落；两道正交、各有承重针（撤1→20红、撤2→2红） | **选** |
| 只修 adapter 让路 | mode=off 时 adapter 根本不在场，全线裸奔 | 否 |
| 只加 orchestrator 总闸 | 确定性题型的约束轮会被降级拒答，而 Episode 明明能按材料语义答它（题组槽+空授权） | 否 |
| 给引擎 B（ask.answer_query）内部加合同意识 | 治本但工程量数倍（providers/owner 全链），且引擎 B 是写死流程的 legacy 面，投入产出不划算；列入后续可选 | 否 |

### 决策 2：state_unavailable 的分界——「基底未知」不是「受限边界」

| 方案 | 评价 | 结果 |
|---|---|---|
| material_only / local_only 恒拦；boundary_uncertain 恒拦（材料粘连本身就是材料语境）；state_unavailable 仅在**带材料语境**（题组、frame.materials、可信历史条目）时拦 | 「继续检索」「接着看看丙公司」这类日常追问全都编出 state_unavailable——拦它们等于把普通会话降级；材料语境的 unavailable（P3g 恢复轮、T3 八题）仍然拦 | **选** |
| needs_clarification 一律拦 | 误伤所有普通续轮（全量回归实测红了两个既有测试，那只是词面恰好带「继续」的冰山一角） | 否 |
| 改 compile_material_contract 让普通续轮不编 unavailable | 动 D1/D2 已审定层，且「续轮+无基底=unavailable」语义本身是对的（P3f2 靠它发澄清），错的是把它当边界声明用 | 否 |

### 决策 3：材料语境在 frame 级单点推导

`frame_blocks_contract_blind_pipelines(frame)`（task_frame.py）组合合同级谓词与 frame 级语境（materials / conversation_materials.items），adapter 与 orchestrator 都用它。否决两处各拼条件——「键里的派生字段必须共用同一个推导函数」的既有教训。

### 决策 4：总闸的降级形状

诚实降级文案（「本轮声明了数据边界…未调用任何外部数据管线」）+ `add_degrade` + trace 事件（`engine_b_material_gate`），复用 `_complete_lane_turn` 出口。否决静默吞掉（不可审计）、否决在总闸里起一个「只按材料答」的旁生成路径（那是 Episode 的职责，兜底线不长第二个脑子）。

## 验证与收据

- 反例先红：adapter 15 红（首版 3 种合同 × 5 题型；调整后 20 用例）；run_turn 3 用例先红（probe 注入 `answer_query_fn`/`route_skills_fn` 构造参数——TurnOrchestrator 的这两个是实例属性不是类方法，monkeypatch 类会 AttributeError）。
- 全绿：e2+改动模块+adapter 全集 **813P/4S**（805 基线恢复 + 新用例；含误伤的两个既有测试复绿），收据 `20260915T104611Z-9fa2a269`；Ruff 通过；engine_b ×10、adapter 集 ×5 稳定。
- 变异（已提交还原点 `50687c0b`，替换数自检=1，还原后 151P 复绿）：
  - 撤防线1（无条件让路）→ **20/20 adapter 反例红**，run_turn 反例全绿；
  - 撤防线2（总闸 if False）→ **2/2 run_turn restricted 反例红**，adapter 反例全绿。
  - 两道防线完全正交，无邻近吸收。
- 不成立的读法：本片不证明引擎 B 内部安全（它仍无合同意识——被挡在门外≠有免疫力）；不覆盖 fictional×full 的前提标注送达（B 轴合规、A 轴语义是 P4/P6 纯度范围）；作者自验非独立 QC。

## 后续要做的

1. 余下 P3：②组 prime/知识前缀、系统级默认市场摘要注入路径；歧义（非缺失）的预取前澄清；D7 跨轮权限继承（P5）。
2. 可选：引擎 B 内部合同意识（决策 1 被否方案四，若未来引擎 B 要独立承接材料题再做）。
3. P4–P7；合并回 main 前全仓等价 CI + 用户确认。

## 不要做的

- 不把「继续 X」类普通续轮算进引擎 B 禁区——基底未知的处置是 controller 层澄清/继承，不是执行面降级。
- 不在总闸里生成第二套「按材料作答」逻辑——那是 Episode 的职责。
- 谓词的任何扩展（新 scope、新 classification）只改 `blocks_contract_blind_pipelines` 一处，两个调用面自动跟随。
