# E2 设计稿 v8（完整自含版）：材料题边界——强弱保护分级、含基底的权限交集、逐轴继承与来源身份

日期：2026-09-14（v8 按 QC 复审 abd03989 的 2 P1 + 1 P2 + 文档修补定点补齐）
状态：**设计待评审（未实现）** · 分支：feat/e2-material-contract-design
立项：QC-2026-09-13 E2（P1，正式 PK 前置）
本稿自含：D1–D7 与 A1–A17 全部直接定义，不依赖旧版正文。版本沿革见 §7。

## 0. v8 定点补齐总览

| # | 级别 | 问题 | v8 落点 |
|---|---|---|---|
| 1 | P1 | 两空格缩进可把真实禁令吞成材料（「分类完成但分错了」） | D1 保护分级：**强保护**（闭合围栏/闭合引号/有终点引导块）与**弱材料候选**（仅缩进/仅长度）；弱候选内出现疑似约束且无法证明属于材料 → boundary_uncertain；验收成对（A17） |
| 2 | P1 | 孤立片段交集可能比已确认/继承权限更宽 | D2 候选改**完整状态解释**：P=已确认/继承后的权限；按材料→P；按约束→P∩allow(约束)；再求交。含糊片段永不放宽；确认「无新增约束」≠复位继承权限；§6 风险加前提 |
| 3 | P2 | 自含回退（「触发短语同 v6」、premise_marks 字段形状被压缩） | §3.2 恢复完整触发映射表与 premise_marks 完整字段形状 |
| 4 | 文档 | 交接标题仍 v5；「八类注入路径」需分组；数据流旧行号 | 交接重写；注入路径四组九类；数据流改文件+符号定位（行号附后仅供索引） |

QC 本轮已确认关闭（不重开）：state_unavailable 澄清出口与禁猜权限；B 轴仅消息级；
local_only 按实际 IO 行为；历史纠错句分类/豁免/混句处理；legal_gap→partial 口径；
注入路径统一权限过滤。

## 1. 失败样本
e2-evidence/MANIFEST.json（v2 schema）：21 项原件哈希 + 14 项仓内副本哈希（3 件
HOME→~ 脱敏已登记）+ 7 项 external-only；QC 多轮复核全部匹配。
T2=`run_20260913_035722_162700`，T3=`run_20260913_041146_035132`，产生代码=2ee664fa。
原 T3 会话含失败残桩，验收必须另起全新会话（A7）。

## 2. 数据流现状（文件+符号定位）
```
raw user message
→ user_task.py: split_user_message（三分区+三态，D1）
→ query_understanding.py: kol_review 分支（envelope 路由段）
→ task_frame.py: TaskFrame（user_premises 字段；to_dict 默认省略）   ← D2 载体
→ episode_factory.py: _grounding_mode                                ← D3 投影
→ turn_controller.py: 检索硬触发下限（_needs_retrieval_floor 段）     ← D4 让路点
→ episode_factory.py: 合同冻结点（_authorized_capabilities /
   mandatory 回补段）+ episode_tools.py: _opening_prefetch_evidence   ← D4 收口
→ research_contract / required_outputs                               ← D5 逐题槽
→ episode_semantic_verifier.py: 语义裁判（user_premise 语义段）        ← D6 纯度
→ 会话状态 / continuous-episode                                       ← D7 跨轮
```
（行号随实现漂移，符号名为准。）

## 3. 设计决策（D1–D7 完整定义）

### 3.1 D1 顶层三分区：保护分级、先保护后解释、三态分类

有序五步，全部确定性：

**第 1 步 保护范围冻结（分级）**：

*强保护*（边界可信，冻结后内部不再参与指令/题组识别；其内命令字样结构上不可能
升级）：

| 构造 | 起始 | 结束 | 失败分支 |
|---|---|---|---|
| 代码围栏 | ```或~~~行 | 同类型围栏行 | 未闭合 → boundary_uncertain |
| 引号块 | 「『"'"等开引号 | 同类闭引号；嵌套按栈配对；转义不计 | 未闭合 → 不作保护；其后文本含疑似约束短语 → boundary_uncertain |
| 引导块（「材料/报告原文如下：」等） | 引导行 | 空行后首个符合顶层指令/题组句法的行；或文末 | 无明确终点且后文有疑似顶层禁令 → boundary_uncertain |

*弱材料候选*（边界不可信，**需内容复核**）：仅缩进块（≥2 空格起、首个非缩进行止）、
仅长度长文块（多行无空行且 ≥ 阈值）。复核规则：
- 块内**检出疑似用户约束短语**（只依据/不要联网/假设……）且无法证明其属于材料
  内容（指向回答方式而非描述材料内容）→ **boundary_uncertain**（不得冻结了事）；
- 块内无疑似约束短语 → 材料区。
- 反例闭环：「请分析这个案例：\n  请只依据本条消息给定材料……（缩进）」→ 该缩进
  行为弱候选+含约束短语 → boundary_uncertain，**不会**进入 no_constraint_confirmed。

*相邻规则*：材料块与疑似顶层禁令之间有空行且该句符合指令句法 → 指令区；无空行
直接相连 → boundary_uncertain。

**第 2 步 指令区识别**（只扫未保护文本），三类，带位置+作用题号标注：
(a) 行为指令（祈使/限定，指向回答方式）；(b) 前提声明（陈述句，声明本轮前提性质）；
(c) 续轮声明（继续/接着/其余条件不变/同上）。

**第 3 步 题组区识别**（只扫未保护、非指令文本）：`^\s*\d+[.、)）]` 开头段落、
序号连续成组、允许空行分隔；question_id=用户原编号；题文完整保留，标注只作
并行元数据。

**第 4 步 材料区**：强保护范围 + 通过复核的弱候选 + 未认领正文；题内假设留题组区
（scope=q{i} 前提声明标注）。

**第 5 步 三态分类**：
- `constraint_confirmed`：指令区有约束 → 按 D2 执行；
- `no_constraint_confirmed`：全文句法角色全分配（强保护/复核通过的弱候选/指令/
  题组/顶层正文），无未闭合构造、无未复核弱候选、无未分类片段，且指令区无约束
  短语 → real×full。**「分类完成」以「分类正确有保证」为前提**——弱候选未复核
  通过时不算完成；
- `boundary_uncertain`：任何未闭合/未复核/相邻歧义 → a) clarify 先于开场预取与
  任何工具执行；b) 按 §3.2 权限交集继续。禁止静默回 full。

### 3.2 D2 两轴模型 + premise_marks + 含基底的权限交集

**轴定义**：A 前提真实性 real（默认）/fictional；B 数据范围 full（默认）/local_only/
material_only。**B 轴本阶段仅消息级**（题级 B 短语 → boundary_uncertain，§3.7.3）。

**触发映射（完整恢复，仅指令区来源）**：

| 指令区短语 | 轴 | 值 |
|---|---|---|
| 只依据/仅根据（以上）材料、不读取材料外数据 | B | material_only |
| 不联网、不要联网、别查实时、不读外部 | B | local_only |
| 虚构、纯属虚构、假设……成立、如果……会怎样（前提声明） | A | fictional（B 不变） |
| 可以查真实数据、结合最新行情（显式放宽） | B | full（显式覆盖） |
| 无短语 | — | 默认 real×full |

「假设 X，结合当前行情」= A fictional × B full：前提不证伪、真实检索发生（A8）。

**premise_marks 完整字段形状**（并行新字段，不改 user_premises）：
```json
premise_marks: [
  {"text_ref": "<消息内偏移或片段哈希>", 
   "authenticity": "fictional | unverified_belief",
   "source_turn": <会话轮次 int>,
   "scope": "message | q{i}"}
]
```
序列化：空元组时字段不进 payload/hash（task_frame.py to_dict 默认省略模式），
旧哈希不变。user_premises（用户信念/观察，待证伪）行为完全不变。
仅「贴材料没提问」两轴都不动（kol_review 默认核对可核验项）。

**B 轴三值允许集（按实际 IO 行为，不按 provider 名/freshness 标签）**：
- allow(full)=全部读能力；allow(local_only)=IO 纯本地能力（本地 DuckDB/本地 KB/
  向量索引/本地文件/盘上缓存）；allow(material_only)=∅。禁止项：外部 API、网络
  请求、CDP 代理、本地进程但实际外呼。

**权限交集（boundary_uncertain 兜底，v8 修正为含基底）**：
- 数学对象=最终 capability/IO 集合；
- **候选代表完整状态解释**——设 P=已确认约束与继承基底生效后的权限集合：
  - 片段按材料内容 → **P**（不改变状态）；
  - 片段按用户指令 → **P ∩ allow(该约束)**；
  - 最终结果 = 各候选解释之交集（二元候选即两者之交）。
- 性质：**含糊片段只能收窄、永不放宽**——已确认 material_only（P=∅）时再遇
  边界不明「不要联网」，交集仍为 ∅，不会重新允许本地材料外读取（v7 反例闭环）；
  继承 B_base 同理（P 含继承值）。
- **放宽只能来自显式覆盖**（用户在指令区明说可以查/结合行情），不来自交集。
- **不确定状态优先处理**：三态判定与交集计算先于预取/工具冻结；确认「无新增
  约束」不等于复位续轮继承的权限。
- 候选集固定二元；不可映射回 data_scope 时以交集集合直接冻结+
  `resolved_by_intersection` 审计标记；交集无法满足题目必需数据 → clarify 或
  legal_gap（D5），不硬答。

### 3.3 D3 前提域声明槽
「结论仅在材料前提内成立」=前提域声明，绑材料（basis=user_premise），只证明范围
声明自身；事实句只能绑材料锚点；边界槽 grounding=user_premise（QC 已确认可完成
合同）；裁判不关闭；非虚构 material_only 计算题以材料锚点成立。

### 3.4 D4 冻结点：同一权限集合生成一切 + dispatch 兜底
- 冻结点（episode_factory 合同定型处）对 data_scope≠full 原子生成一致三元组，且
  三者从**同一个 capability 集合**（直接检出的轴值，或交集集合）派生：
  authorized capabilities、evidence_plan（requirements 与 mandatory 同步重建，
  material_only 同空）、输出槽（question_id）。
- **同源过滤扩展到全部模型输入注入路径**，四组九类：
  ① 预取组：opening_prefetch（material_only 短路，零播种证据账本）；
  ② 提示前缀组：prime/知识前缀、视角注入、系统级默认市场摘要；
  ③ 会话历史组：历史摘要、episode 压缩上下文、恢复读；
  ④ 研究过程组：子研究上下文、非工具路径产生的 provider 事实。
  material_only 下外部事实型先验零注入；同题链上下文按 D7 来源身份注入。
- 预取/补检/子研究/恢复读同一份冻结授权；检索硬触发下限对 material_only 让路；
  clarify 分支在预取与工具执行之前。
- dispatch 兜底：模型主动请求被禁工具 → 拒绝 + trace 留痕（A9）。
- local_only=摘除一切发生外部 IO 的能力（按实际 IO 行为判定），本地 IO 保留。

### 3.5 D5 逐题一一对应 + 合法 gap 完成状态口径
- 输出槽 `answer_q{i}`；memo 槽仅当题文显式要求（T3 q8→≤200 字）。
- 结构预检三态：遗漏/重复/明确缺口。
- 每题终态 ∈ answered/legal_gap/missing；legal_gap 须绑 question_id+缺什么。
- 汇总：全 answered→completed；有 answered 且其余全 legal_gap→**partial**
  （gap+completed 不允许）；任何 missing→结构预检失败；全 legal_gap→partial 且
  顶部声明无一题可依据材料作答。（与现结构探针「gap+completed 拒、gap+partial
  过」对齐。）

### 3.6 D6 条件化纯度 + 材料锚点 + 历史句正式排除
- 纯度以 data_scope 为条件：material_only→市场事实句必须带材料锚点
  （material_id+片段引用/哈希），外部 IO 绑定即拒；local_only→拒外部 IO 绑定；
  full→不校验。
- basis=user_premise 是类别标签≠已绑定；声明句不替事实背书。
- **historical_assistant_statement**：引用/纠错/撤回历史答案的句子——非当前市场
  事实主张；绑 old_answer_coordinate+assistant_judgment；豁免材料锚点要求与纯度
  扫描；混句（历史引用+当前推断同句）→ 拆句分别归类，无法拆→整句拒绝。

### 3.7 D7 跨轮逐轴继承 + 基底不可恢复 + 来源身份分级
1. 有续轮声明 → 先继承基底（A_base、B_base、marks_base）。
2. 逐轴显式覆盖：只改 A 不动 B；只改 B 不动 A；同值重申幂等；scope=q{i} 的 A 轴
   标记只附着该题。
3. **B 轴仅消息级**：题内 B 类短语——消息级已 material_only → 作该题备注；
   否则不静默局部化、不静默提升，按 boundary_uncertain 处理。（未来若支持题级 B，
   授权/预取/检索/模型输入/语义校验须按题隔离——本阶段明确不做。）
4. **基底不可恢复**：续轮声明命中但会话无可恢复基底 → `state_unavailable`：
   澄清先于预取与任何工具执行，或可证明不超候选解释的权限交集；**禁止猜
   real×full，禁止从助手历史答案推测权限**。
5. 复位：换题（新主语/新材料且无续轮声明）→ real×full。
6. 来源身份分级：用户材料=前提资格（可锚定）；助手历史回答=context-only
   （assistant_judgment）：可见供对照/纠错/撤回，无证据资格；可追溯至合法用户
   材料+推导链的内容以材料锚点重新绑定；用户当面否定→立即失格。
- 原则：**「允许看见」≠「有资格作为证据」**。

## 4. 验收断言（A1–A17 完整定义）

- A1 拆分：空行分隔编号项同组；question_id 稳定；题文完整。
- A2 三分区+三态：T2 开场禁令、T3 续轮声明入指令区；保护范围内命令字样不升级；
  两轴检出 T2/T3=fictional×material_only。
- A3 纯度：material_only 下市场事实句 100% 材料锚点；无外部 IO 绑定；full 不校验。
- A4 逐题+完成状态：一一对应三态；T2 无 memo、T3 q8 memo ≤200 字；合法 gap→
  partial（gap+completed 被拒）。
- A5 回归：无约束纯贴研报行为不变。
- A6 回归：S1/N1 锁绿（192 字 quick_fact、802 字 disclosure 变体）。
- A7 链路+逐轴状态表（五格）：全新会话 T2→T3 原始文本。①只改A→B 继承；②只改B
  →A 继承；③局部假设→消息级原样继承；④同值重申→幂等；⑤换题→复位。
- A8 正向：「假设 X，结合当前行情」前提不证伪且真实检索发生。
- A9 授权+注入路径：被禁工具请求→拒绝+留痕；三元组一致且同源；四组九类注入
  路径逐一断言经同一权限过滤（material_only 外部事实型先验零注入、预取零播种）。
- A10 计算题：非虚构 material_only 完成，结果绑材料锚点。
- A11 误报：材料正文引「假设……」的研报题不触发约束。
- A12 来源身份拆对：A12a 拿旧答材料外数字支撑当前事实→拒；A12b 引用旧答纠错/
  撤回→允许（historical_assistant_statement，豁免锚点）；混句无法拆→整句拒。
- A13 三态行为：未闭合围栏/无终点引导块/相邻疑禁令→boundary_uncertain；澄清
  先于预取与工具执行；不静默回 full。
- A14 基底不可恢复：全新会话直接「继续上一轮……其余不变」→state_unavailable；
  断言未猜 real×full、未从助手历史答案推测权限。
- A15 权限交集数学（含基底）：候选=完整状态解释（按材料→P；按约束→P∩allow）；
  含糊片段不放宽（已确认 material_only + 不明「不要联网」→ 仍 ∅）；显式覆盖才可
  放宽；交集=∅ 且题目必须材料外数据→clarify 或 legal_gap。
- A16 local_only IO 语义：按实际 IO 行为分类（本地放行/外部拒绝），不以 provider
  名或 freshness 标签判定。
- A17 保护分级成对（新）：(a) 缩进的用户禁令（QC 反例形态）→ boundary_uncertain，
  **不丢**；(b) 明确引用材料内部的同一句禁令 → 不升级为指令。

## 5. 实施拆分（过审后）
P1 顶层三分区+保护分级+三态（D1）→ P2 载体+premise_marks+投影（D2/D3）→
P3 冻结点同源三元组+dispatch 兜底（D4）→ P4 逐题槽三态+完成状态口径（D5）→
P5 逐轴继承+基底不可恢复+来源身份（D7）→ P6 条件化纯度+锚点+历史句排除（D6）→
P7 A1–A17 验收（全新会话、原始 T3 文本，不重贴禁令）。

## 6. 风险与回滚
- 弱保护复核漏判 → 落 boundary_uncertain（A17 锁）；宁多澄清不静默放行。
- **权限交集的数学保证有前提**：交集只保证不超过传入候选——若候选漏掉已有边界
  （已确认/继承限制），交集照样可能偏宽。v8 以「候选=含 P 的完整状态解释」补上
  这个前提（A15 锁）。
- 三元组与注入过滤集中在冻结点一处，full 路径零改动；每层独立开关、逐层可回滚。
- 逐轴继承五格与基底不可恢复有 A7/A14 断言；换题复位有覆盖。

## 7. 版本沿革（关闭项，不再重开）
v1→v2：证据归位+消毒；三层抑制；两轴；memo 归 T3；A7 链路。v2→v3：冻结点收口；
前提域声明；跨轮继承；premise_marks；MANIFEST v2；question_id 三态；来源纯度。
v3→v4：顶层三分区；三元组原子化+非工具先验；条件化纯度+锚点；A11。v4→v5：先保护
后解释；历史答案来源身份分级；自含化；声明/锚点歧义统一。v5→v6：三态分类+禁令
不丢；逐轴继承+A7 四格；A12 拆对；_QUOTED_MATERIAL_RE 边界诚实化。v6→v7：保护
边界规则表；交集形式化；state_unavailable（A14）；B 轴仅消息级；local_only 按实际
IO（A16）；历史句正式排除；legal_gap 口径；注入路径清单。v7→v8：强弱保护分级
（弱候选内容复核+A17 成对验收）；交集候选含基底 P（含糊片段永不放宽+A15 修正）；
触发映射与 premise_marks 字段形状完整恢复；注入路径四组九类；数据流符号定位。
QC 已确认关闭：哈希全匹配；边界槽 user_premise 可完成合同；三元组可满足；D6 与
A8 不冲突；原始 T2/T3 未改；自含性（v8 恢复）；state_unavailable 出口；B 轴仅消息级；
local_only IO 语义；历史句分类豁免；legal_gap→partial；注入路径统一过滤；
L2 已收口（main=d7e53805）。
