# 2026-09-15 · E2 P3g：材料类澄清挂起的恢复重验——四个真实入口 bug 与三层修复

分支 `fix/e2-boundary-closeout`，提交 `f05d0681`。前情：P3f2（`e1fc53a7`，已知缺失基底送达 controller 澄清）见 `2026-09-15-e2-p3f2-frame-delivery-and-material-chain.md`。

## 背景（不读会误判后面每个决定）

P3f2 让「基底不可恢复」的续轮在 resolver/模型之前发起澄清。本片回答的问题是：**用户回答了那句澄清之后会发生什么**。答案（探针实测）：澄清等于白问——回答走普通路由，材料被丢、权限声明被当成主体名、待澄清的合同带着 `needs_clarification=True` 直接放行 research。「pending 恢复重验」在 P3f1/P3f2 的边界声明里被点名两次未盖，本片收它。

范围纪律沿用：真实入口反例（run_turn → 真实 decide_turn → Episode 装配）先红后绿；独立审查保持用户已拍的关闭状态，收口标准=作者自验；不盖 P4/P6、不跑正式 T2→T3/Knevo。

## 按发现顺序

1. **选片**：余下 P3 按 D4 四组九类对照，③会话历史组里 episode 压缩（`_compact_history_for_model`）是对本 episode 已过滤工具观察的折叠（减法、缺省关），风险低；`restore_episode` 是「结算+给计划」不注入模型输入。真正未盖的是 controller 层的澄清挂起恢复——离 P3f2 最近、反例设施同族可复用。
2. **探针证伪**（一次性 heredoc，不留文件）：构造 state_unavailable 澄清 → 手工挂 pending → 回答两种形状。实测：裸材料回答 → `materials=[]`（丢弃）、subject=「A股市场」（主体归一改写）、合同 `('state_unavailable', needs_clarification=True)` 残留但 lane=research（矛盾放行）；显式放宽回答 → subject=「不用材料了，可以查真实数据」（声明被当主体名）。
3. **第四个 bug（最上游）**：真实链里 P3f2 的 material clarify 决策**根本没挂 `pending_task_frame`**（rounds=0）——手工挂 pending 的探针都到不了的更早失败：回答轮连恢复分支都进不去。
4. **第五个发现（顺序）**：澄清回答带正规材料区时，顶部 source-aware material 分支（P3f1 放在 pending 恢复之前）会抢先重建 frame——题组照样丢。P3f1 把材料轮放前面是防「旧 intent 当权限」，但澄清回答是对采访的应答，不是新材料轮。
5. **第六个发现（装配层）**：反例跑红后发现 `build_episode_context` 收窄只看 `data_scope == "material_only"`——`state_unavailable` 合同 axes=None 被当无约束放行 8 个能力。合同 docstring 早写了「未确认的值是 None，不能序列化成默认 full」，装配层没执行这半句。
6. 6 个真实入口反例先红（红因逐一与探针对上）→ 三层修复 → 全绿 → 变异验证每层承重。

## 决策与被否方案

### 决策 1：恢复分支的判定用合同状态，不用文案等值

| 方案 | 评价 | 结果 |
|---|---|---|
| 结构化谓词：`material_contract.needs_clarification`（classification 的派生属性） | 文案可以改，结构不会；对 boundary_uncertain / state_unavailable 一体生效 | **选** |
| 给 P3f2 两个新文案加常量、沿用 `is_missing_material_clarification` 的等值比较 | 每加一种澄清就要登记一次，漏登就是本片这个 bug 的重演 | 否 |

### 决策 2：恢复的轴值只能出自 D1/D2 编译器

| 方案 | 评价 | 结果 |
|---|---|---|
| 回答重新过 `classify_top_level_regions` + `compile_material_contract`；显式声明 → 编译结果就是新合同；题组/续轮标记/premise_marks 从挂起合同组合 | 「可以查真实数据」编译出 `('real','full')` 是编译器判的显式覆盖（D7.2），不是猜测（D7.4 禁猜）；组合的是两次编译器输出，不产轴值 | **选** |
| 恢复分支里按关键词自解析回答、手搓合同字段 | 第二套解析必然与 D1/D2 漂移；「键里的派生字段必须共用同一个推导函数」的既有教训 | 否 |
| 把 pending 的 unavailable 合同当 `inherited_contract` 传回编译器 | 编译器 122 行：inherited 带 needs_clarification 时仍编出 state_unavailable——语义上澄清永远无法解除 | 否 |

### 决策 3：范围未声明时如实保留待澄清合同，靠装配层收窄执行

| 方案 | 评价 | 结果 |
|---|---|---|
| 裸材料/无法识别的回答：材料并入，合同保持 `state_unavailable`（诚实），`clarification_question` 清空（预算一轮），装配层把待澄清合同按 material_only 收窄执行 | 不猜 full（D7.4）、不二次采访（产品预算）、不撒谎说 confirmed；「宁多澄清不静默放行」的预算耗尽版=按最严执行 | **选** |
| 二次澄清 | 违反「在线预算一轮」的产品约束 | 否 |
| 翻转合同为 material_only constraint_confirmed | 手搓轴值 + 谎报「已确认」；用户从未确认过范围 | 否 |

### 决策 4：顶部 material 分支让路的条件

| 方案 | 评价 | 结果 |
|---|---|---|
| 材料类澄清挂起（`_pending_material_clarification` 非 None）时顶部分支让路，回答统一走 pending 恢复 | 澄清回答是采访应答不是新任务；恢复不授予旧权限（合同 restricted 或按回答显式声明，都出自编译器），与 P3f1「旧 intent 不是权限」不冲突 | **选** |
| 在顶部分支内部感知 pending 并合并 | 恢复逻辑出现两份（顶部一份、pending 分支一份） | 否 |
| 把 pending 恢复整体提到顶部分支之前 | 会连非材料类澄清（entity tristate、主体归一）一起提前，动到 P3f1 已验证的顺序 | 否 |

### 决策 5：装配层收窄条件补 `needs_clarification`（`_material_restricted`）

| 方案 | 评价 | 结果 |
|---|---|---|
| 执行层（能力/证据计划/输出槽）与提示层（材料规则文案、可信历史块）统一用 `_material_restricted` = material_only OR needs_clarification | 轴 None 不能当 full 执行；提示与执行一致，否则模型被鼓励调工具再被 dispatch 拒，白烧轮次 | **选** |
| 只改执行层 | 提示词仍说「可检索」，每轮都撞 dispatch 拒绝 | 否 |
| 在装配层把合同改写成 material_only | 改写冻结合同 = 破坏「同一权限集合生成一切」的可审计性；收窄是执行档位决策，不是合同篡改 | 否 |

## 验证与收据

- 反例先红：6 个新用例首跑全红，红因逐一与探针对上（pending 未挂、合同 None、题组 0、装配 8 能力放行）。
- 修复后：文件 ×10 连跑 290/290；e2+改动模块选集 689P/4S（=683 基线+6 新用例，零破坏），收据 `20260915T101544Z-a20935f5`；Ruff 通过；提交 `f05d0681` 过 11 道 pre-commit。
- 变异验证（每层一撤，已提交还原点，`grep -c` 自检替换数=1，还原后 54P 复绿）：
  - 撤 A（clarify 不挂 pending）→ **6/6 红**；
  - 撤 B（恢复分支禁用）→ **3/6 红**（材料并入/显式放宽/正规恢复三针）；另三个被 C 层兜住——邻近吸收，按既有原则读作「B 对它那类反例承重」，不是门冗余；
  - 撤 C（装配收窄回退 data_scope-only）→ **3/6 红**（bare/unrecognised/run_turn 全链三针）。
- 不成立的读法：689 与 446/683 是不同 -k 口径；作者自验≠独立 QC；本片不证明「所有澄清类型的恢复」正确（entity tristate、主体归一等旧类型走原路径未动）。

## 后续要做的

1. 余下 P3：②组 prime/知识前缀、系统级默认市场摘要注入路径；静态路由配置旁路（P3e 未关）；D7 跨轮权限继承；歧义（非缺失）的预取前澄清。
2. P4–P7；合并回 main 前全仓等价 CI + 用户确认。

## 不要做的

- 不给澄清恢复加第二轮采访——预算一轮是产品决定，改它先问用户。
- 不把 `_material_restricted` 的收窄改写回合同本体——收窄是装配层执行档位，合同必须保持编译器原样（可审计）。
- 不用澄清文案字符串做任何新判定——文案是 UI 层，会改；判定一律走合同状态。
