# 封上限形状收口 R1：判官降级权 · 契约可满足性 · 映射反推 · 预算归因 · 常驻传感器（2026-08-21）

> 上游：[`docs/verification/2026-08-21-tracediff-cxo-ceiling.md`](../../verification/2026-08-21-tracediff-cxo-ceiling.md)（双臂 trace diff 终态）+ 台账 `R-20260821-02..-06`（全 confirmed）。
> 本 spec 收口那轮工作的残余队列。**按母形状立项，不按单点症状立项**——验收判据押「形状在全量 run 上归零/可观测」，不押「某道题变好」。
> **角色分离**：spec 作者 = 验收方（不接单、不写实现）；实施方 = 接单 agent。合并需验收方复算通过 + 用户确认。
> 基线锚：`gitea/main = f1c9727f`（本文所有行号引用以此为准）。

## 0. 母形状总表（为什么是这五单）

2026-08-21 的六案证明：单点症状（某题某句被删）的根都在少数结构性形状上。规则无法穷尽，形状可以。

| 形状 | 一句话定义 | 已修实例 | 本轮收口 |
|---|---|---|---|
| **A** 二级声明否决一级事实 | 同一事实的近端声明（正文引用/桌上的行/hash）与远端记账（bindings/编号表）不一致时记账赢，记账缺陷显影成「证据缺陷」，判官按入参为真、按事实为假 | #287 编号对齐、#289 槽保护、#298 引用反解 | 已清账。W5 只装传感器 |
| **B** 契约必填与运行时供给不对账 | mandatory 清单设计时静态写死，证据供给/预算/工具授权运行时动态，从不对账；联立无解时让模型在「违禁编造」与「缺格被删」间二选一，结果记成模型失败 | #296（题形枚举，个案） | **W2**（形状级兜底） |
| **C** 破坏粒度>错误粒度，破坏权晚于修复权 | 句级错误块级连坐；post-repair 删除无补偿通道；deadline_exhausted 全稿成于修复窗后暴露面极大 | C3 全灭闸（只兜「全灭」极端） | **W1**（主修） |
| **D** 入口有损变换无对账 | 中间层收短/枚举映射丢信息，下游拿不到原始输入对账 | #288（预取回看问句原文） | **W3**（映射反推） |

横切元判据（可迁移）：任何约束进 harness，先问它否决的是**机械事实**还是**语义判断**——否决机械事实的约束一律有嫌疑（三筛「模型变强会怎样」的操作化）。权威边界画在「可机械判定」的分界线上：机械可判的圈给 harness 确定性代码，语义判断留给判官但只给有护栏的权力。

## 全局纪律（每单必守）

1. 从 `gitea/main` 新开 worktree（**必须在 /Users 下**——codex 沙箱探针以 `__file__` 推 live root，/tmp 树会 unproven），独立分支 `fix/<单名>` 或 `feat/<单名>`，独立 PR。
2. 解释器一律 `.venv-workbench/bin/python`；交付前全量 `pytest`（基线 **5888 passed / 0 failed**，只升不降）+ `ruff` 绿；动了 webapp 才跑 pnpm 四连。
3. **变异测试前先 commit**——`git checkout --` 还原的是已提交态，未提交实现会被冲掉（2026-08-21 已两次踩坑在案，把它当变异流程第 0 步）。
4. `git worktree move` 后先清 `__pycache__`（旧 .pyc 记旧绝对路径，`inspect.getsource` 炸）。
5. live 探针用 `scripts/workbench_probe.py`（字段是 `user` 不是 `user_id`，传错静默落主用户）；烧题检查（探针题文查重）跑在 **gitea/main 树**，特性分支树会漏检当天已合并文档。
6. 部署走 worktree 快照 + symlink 切换 + `launchctl kickstart`，**不用 rsync**（#296 的 rsync 就地部署导致 health `source_revision` 标签滞后、取证只能看指纹的教训）；回滚指针保留。
7. 台账行随实施 PR 立案，判据**从本 spec §各单「台账」小节逐字抄**，不得开行文字自拟（开行文字不能当 PRIMARY 是台账既有纪律）。
8. 交付物清单（每单）：PR 链接、测试收据路径（`~/.finance-runtime/test-receipts/`）、变异测试记录（改了什么→哪条红）、重放/live run id、验证文档、台账行 diff。缺一项验收不开始。

---

## W1（形状 C 主修）：必需输出块的否决改「降级保留」，删除权收窄到机械硬违规

### 现状（一手引用）

- `_marker_loss_partial_public`（`intelligence/services/episode_semantic_verifier.py:2330`）对修复救不回的必需格**物理删除正文** + 设 `gap_output_ids`。`fix/r24-marker-loss-binding` **已合入 main**（`git merge-base --is-ancestor` 实测 MERGED；台账 R-24 段「outcome pending 等部署窗」是 08-15 旧文字）：lost 格在 `semantic.verified` 上改 `missing` 并清空绑定哈希——**记账诚实化已做，正文仍物理删除**。W1 是它之上的增量。
- 个股换形探针 `run_20260821_171744_955225`：判官删对了块内一句真算术错（3.15→3.51 写成「基本回吐」），但 `direct_assessment` **整块强制输出跟着没了**，道歉横幅收场——错误是句级，破坏是块级。
- R-05 A 臂 `run_20260821_185226_491046`：marker_loss 横幅 + 194 字残稿。
- post-repair 的判官删除**无第二修复窗**（repair 已耗尽）；deadline_exhausted 路径全稿一发成于修复窗（见 W4），此后任何块删除即终态。
- B 臂 `run_20260821_164659_624916` 已演示终态形态：`rejected_claim_indexes=[]`，判官的真实批评以「输出质检」段呈现而非删稿——**呈现通道已存在**。

### 目标行为（验收判据的行为面）

1. **句级错误句级删，残块保留降级**：判官对必需输出块内句子的合法删除（机械硬违规）照常执行；删除后块不完整时，处置从「删整格正文 + 横幅」改为：格状态按 r24 口径记 `missing`/进 `gap_output_ids`、清绑定，**剩余正文保留**，判官批评进「输出质检」段，块级挂显式质疑标注。
2. **删除权白名单（机械可判定的硬违规，纪律不动）**：无据数值/发明阈值（`numeric_unsupported`）、口径分歧下的越界合成、表外引用（E 号反解失败）。这些继续 fail-closed 删句。
3. **语义质量类否决**（「这块质量不够/证明不了」）对必需块**只有降级权，没有删除权**。
4. 残块为空（块仅一句且该句被合法删除）→ 格记 missing、正文无该块、**不挂道歉横幅**；道歉横幅只归 C3 全灭闸（`repair_wiped_all_outputs`，verifier:1033/1168/1293，语义不动）。
5. 降级块必须**可识别**：公开稿带显式质疑标注（结构化生成），禁止静默保留——否则等于放行未复核内容，破诚实红线。

### 禁区

- 不改 `acceptance.py` 的 `episode_fulfilled_hashed` 口径（历史夹具 `b3-r4-batch2-episode.json` efh=2 vs eb=0 冻结，台账有明文）。
- 不破判官 **never-add** 不变量：标注文本由 harness 结构化生成，判官只产 issue 不产正文。
- **不加第二修复窗**（修复窗产的稿又要判，无限递归）。
- 不动 #298 投影选集、#289 槽保护、#296 题形降级。

### 前置核查（实施第 0 步，各一条命令级）

- r24 合入后 marker_loss 的现行为：跑既有 marker_loss 测试夹具确认「删正文+记账收缩」是当前基线。
- 「输出质检」段呈现通道的机制名与写入口（B 臂 run 工件里可反查）。
- 道歉横幅的生成点与触发条件（区分「部分 marker_loss 横幅」与「全灭横幅」两条路径）。

### 判据

- **离线 TDD（先红后绿）**：① 块内 N 句、判官合法删 1 句 → 残块正文保留 + 格状态 missing + 批评进质检段 + 块级标注；② `numeric_unsupported` 句仍被删（白名单回归钉）；③ 残块为空 → 无横幅；④ 全灭 → 横幅保留（C3 回归钉）；⑤ 降级块标注在公开稿可见。
- **变异 ≥2**：把降级改回删整格 → 至少一钉红；把块级标注去掉 → 至少一钉红。
- **机制证明（live 不可按需强触发，沿 #298 模式）**：原始工件重放 before/after——个股 direct_assessment 案（`run_20260821_171744_955225`）与 R-05 A 臂 marker_loss 案（`run_20260821_185226_491046`），after = 残块保留 + 降级标注 + 无横幅；冻结夹具进 CI（`intelligence/tests/fixtures/` 相邻目录，命名跟 `pv-perovskite-e4.json` 惯例）。
- **live 前瞻观测**：部署后凡 run 记 marker_loss，公开稿不得再现道歉横幅且降级块带标注；探针打一发同族题（个股走势复盘）确认判官正常路径无回归。

### 台账（判据预注册，实施 PR 逐字抄）

立 `R-20260821-07`，fix_type=`HARNESS_FIX`：「post-repair 判官对必需输出块只有降级权（missing+gap+标注+批评进质检段），删除权收窄到机械硬违规白名单；部分降级不挂道歉横幅，横幅只归全灭闸。预测：修复落地后，全量 run 中 marker_loss 记账与道歉横幅解耦——marker_loss>0 的 run 公开稿仍交付降级块正文；重放两案 after 残块保留。」pending → 机制证明 + 部署 → 自然样本（marker_loss>0 的 run）验收 → confirmed。

---

## W2（形状 B 兜底）：必需项可满足性——静态供给预检 + 动态不可达降级

### 现状（一手引用）

- `chain_mapping` 是 `DecisionBrief` 必需输出格（`intelligence/services/answer_model.py:496-499`），其注释本身就记录过一次「必需输出结构性无法满足 → 整份答案被 fail-closed 换成『请补充数据源』」的先例——形状 B 在本仓已二次显影。
- 板块题三约束联立无解（tracediff 文档 §约束三筛）：evidence 模式禁权重知识写产业链角色 + 契约必填 chain_mapping + KB 无该题材链路证据 → 模型必死一格，marker_loss 落账。
- R-05 已按题形修能力 mandatory（#296），但那是**枚举式**：每个题形配一张清单。`quick_fact` 题形分不出主体（茅台多少钱 vs 涨停家数多少）是已知观察——**题形分类器本身有精度极限，枚举地基不牢**。
- R-05 A 臂：修复轮被 mandatory 压着调 `market_data` → 市场总览数字混进个股稿——**满足契约反而污染答案**。已有观测埋点：`repair_goal.unreachable_without_tools`、`reopen_tools`（#289 第 6 刀把不可达必填格投进 trace——观测有了，差裁决协议）。

### 目标行为

- **a) 静态供给预检（contract 下发时）**：题材在 KB relations 无链路证据（机械可查——生成前查一次 relations）→ `chain_mapping` 输出格降 optional + 预置结构化缺口声明（「知识库暂无该题材产业链证据」）。有证据 → 保持 mandatory。
- **b) 动态不可达兜底（形状级，不依赖题形分类）**：`repair_goal.unreachable_without_tools=True 且 reopen_tools=False` 成立时，该 mandatory（能力或输出格）的缺失**一律降级为结构化缺口声明**；禁止：修复轮被压着调错口径替代工具、`missing_mandatory_capability` 触发道歉横幅或删稿。这条对未来所有题形一次成立。

### 否决的替代方案（防实施走偏，形状级论证）

- **补供给**（个股预取补 market/mainline 路）——R-05 A 臂已证：错口径供给当正文 = 污染；90s 档预算内 reopen 工具不现实。
- **放开 evidence 模式禁权重知识**——等于允许无据断言，爆炸半径大，直接违反证据纪律。
- **继续题形枚举**——#296 已做的保留不动，但新题形不再逐个配清单；b) 兜底不变量接住枚举漏网。

### 禁区

- #296 的 `company_current_backdrop` 降级计划与 seam ladder `ROUTED_FACTS` 不动。
- 静态预检只查「机械可判」的供给（relations 里有无该题材链路证据）；**不做**「预测工具会不会返回有用数据」这类不可机械判定的猜测——猜测型预检会引入新的误判层。

### 判据

- **离线 TDD**：① 无链路证据题材 → contract 里 chain_mapping optional + 缺口声明预置；② 有链路证据 → 仍 mandatory；③ `unreachable && !reopen` → 缺口声明、无横幅、修复轮不调白名单外替代工具；④ #296 路径回归钉（公司题形降级计划仍生效）。
- **变异 ≥2**：预检判定反转（无证据仍 mandatory）→ 红；兜底拆除（unreachable 仍压 mandatory）→ 红。
- **重放**：钙钛矿板块题（`run_20260821_171744_929436`）chain_mapping 案 after = 缺口声明、无 marker_loss 落账。
- **live 前瞻**：部署后同形题（KB 无链路证据的新题材发酵题）`missing_mandatory_capability` 与 chain_mapping 类 marker_loss 归零；缺口声明出现在公开稿。

### 台账

立 `R-20260821-08`，fix_type=`HARNESS_FIX`：「mandatory 可满足性两级对账：contract 下发时按 KB 链路证据在场性降级 chain_mapping；运行时 unreachable_without_tools && !reopen_tools 一律降级为缺口声明。预测：结构性不可满足的必填格不再显影为 marker_loss/道歉横幅/错口径污染，显影为显式缺口声明。」

### ⚠ 验收方修订（2026-08-21 22:10，实施方必读——归因更正，影响重放案例与预检基准）

输入侧排查（`docs/verification/2026-08-21-inputside-kb-dark-asset.md`）实证：**钙钛矿 chain_mapping 案的「KB 无该题材链路证据」不成立**——KB 概念图谱有奥特维/捷佳伟创/京山轻机带 role/strength/reason（`query_relations.py graph --concept 钙钛矿` 可复算）。死格真因是 `evidence_plan.requirements` 不含 KB 工具、模型顺计划走零调用（5/5 案例 run 全同形）——**供给通道不通，不是供给不存在**。据此修订：

1. **静态预检的判定基准**：从「KB 里存了什么」改为「本次供给通道会送什么」。三段决策替换原二段：
   - KB 无链路证据（如减肥药，概念层实测零节点）→ 降 optional + 预置缺口声明（原设计，保留）；
   - KB 有证据**且**本次计划/预取会送 → 保持 mandatory（原设计，保留）；
   - KB 有证据**但**计划不含 KB 检索 → **不属 W2a 范围**，挂 W2b（下）。本轮先按「本轮通道未检索知识库」出结构化缺口——**缺口文案必须区分「库无」与「未查」**（机械可判：有无 kb_search/evidence_search 调用收据）。
2. **W2a 重放案例更换**：钙钛矿案（KB 有证据）不再是 W2a 的合法重放靶——换用**减肥药题**（`run_20260821_165210_889002`，KB 概念层真·零节点，`evidence --theme 减肥药` 0 条）。判据不变：after = 缺口声明、无 marker_loss。
3. **新拆 W2b（通道打通，另行派单，本单不做）**：evidence_plan 对「KB 有该题材证据」的题形补 KB 检索引导（或预取补链路块）。前置：先量 KB 检索耗时分布——W4 已证预算紧张是常态，且在途 plan `retrieval-tier-by-remaining-budget` 会在 <15s 剩余时把 hybrid 降 BM25，通道打通必须带预算账，否则重演「满足契约反而污染/超时」。
4. 动态兜底（`unreachable && !reopen` 降级）**不受本修订影响**，照原判据执行。

---

## W3（形状 D）：issue-backfill 回填目标按缺口主体反推，废静态映射

### 现状

- `intelligence/services/episode_issues.py:116`：`IssueCode.NUMERIC_UNSUPPORTED: "market_data"`——静态映射。个股题数值缺证被回填**市场总览**（R-05 A 臂实测：上涨4096家/涨停79家混入个股稿；R-05 台账「候选观察不立案」挂账项，本单升级立案）。

### 目标行为

回填目标 = f(缺口主体)：复用 episode 既有锚定主体解析（**不新造分类器**——quick_fact 主体检测是已知精度缺口，别在这上面再摞一层）。锚定主体是个股 → `finance_query`；市场级 → `market_data`；解析不出 → **不回填**（fail closed，宁缺勿错——缺数显影为缺口，好过错数显影为正文）。

### 判据

- **离线 TDD**：① 个股题 NUMERIC_UNSUPPORTED → 回填 finance_query 不调 market_data；② 市场题 → market_data（回归钉）；③ 无主体 → 不回填。
- **变异**：映射改回静态 market_data → ① 红。
- **重放**：R-05 A 臂 run 工件，after 修复轮无市场级数字混入个股稿。

### 台账

立 `R-20260821-09`，fix_type=`HARNESS_FIX`：「NUMERIC_UNSUPPORTED 回填目标由静态映射改锚定主体反推，解析不出 fail closed。预测：个股题修复轮不再出现市场总览数字污染。」

---

## W4（观测单，不修代码）：deadline_exhausted 主稿归零路径复现归因

### 现状

两个换形探针（`run_20260821_171744_929436` / `_955225`）主稿阶段 3 轮全部 LLM `TimeoutError` → `deadline_exhausted`、`carried_draft_chars=0`，**全稿一发成于 40s 修复窗**——生产答案的实际生成预算是修复窗而非主稿窗，主稿三轮纯烧钱零产出，且把形状 C 暴露面放大到极限（修复窗产的稿被删即终态）。当前只是验证文档里一句「预算观察」，无立案。

### 任务

1. 采样近 7 日 runs，判据：`deadline_exhausted && carried_draft_chars=0`，目标 n≥3（含两探针）。
2. 逐 run 取证：每轮 `timeout_asked`/`timeout_configured`/实际耗时/provider/时段。
3. 归因二选一（可证伪）：**provider 暂态**（超时聚集在特定时段/provider，其余时段同题形正常）vs **结构性**（90s 档 3 轮 × 单轮真实延迟 > 窗口，任何时段必现）。
4. 交付：验证文档 `docs/verification/2026-08-21-deadline-exhausted-repro.md` + 台账行。

### 禁区

**不修代码、不改预算参数**。「无实测抬 T」是台账 R-20260816-07 书面豁免的禁令——本单先出实测，修法另行立项。

### 台账

立 `R-20260821-10`，fix_type 待归因后定：「主稿三轮归零、全稿成于修复窗的路径可复现；归因 provider 暂态或结构性预算失配二选一，判据=时段分层复现率。」outcome=pending。

---

## W5（审计工具单）：封上限传感器聚合回读

### 目标

四个母形状各自已有在线传感器，缺一张聚合面。新增 `scripts/audit_ceiling_sensors.py`（名可调）：扫指定日期窗的 runs 目录，聚合输出。

| 形状 | 传感器字段 | 语义 |
|---|---|---|
| A | `projection_cited_unbound_count > 0` | 引了没绑（#298 起才有此字段，**历史 run 缺字段报「不可判」，不报 0**——量纲诚实） |
| B | `missing_mandatory_capability` 非空 / `repair_goal.unreachable_without_tools=True` | 结构性不可满足显影 |
| C | `marker_loss` 落账 / `repair_wiped_all_outputs` / `judge_status=repaired && rejected_claim_indexes 非空` | 破坏发生（repaired+删句是回读线索，不必然是误删） |
| D | 预取观察值 subject ≠ 问句精确名（#288 后应恒等） | 路由收短漏网 |

- 输出：per-形状计数 + 非零 run 清单（run id + 一行摘要），人可回读；形状 B/C 非零 → 非零退出码（可挂夜检）。
- 金标：对已知历史 run 实跑——E4 案 `run_20260821_171744_929436` 应报 C 形状（rejected_claims 非空）、A 形状「不可判」（无字段）；B 臂 `run_20260821_164659_624916` 应干净。
- 落点纪律：审计件 → **回写 `~/harness-reference/TOOLKIT.md`**（按成本档位归档，KIT 纪律：不另建第二份清单）。
- 不立预测行（工具单）。交付 = 脚本 + TOOLKIT 行 + 对最近 7 日窗的一次实跑读数。

---

## 派单表与让位规则

| 单 | 依赖/并行 | 主要文件（预期） | 让位规则 |
|---|---|---|---|
| W1 | 先行 | `episode_semantic_verifier.py`（marker_loss 邻域）、呈现层 | — |
| W2 | 与 W1 **串行**（同 verifier/契约邻域；建议同一 agent 顺次承接，或 W2 等 W1 合入后 rebase） | `answer_model.py`、契约下发点、verifier | 后动工者 rebase |
| W3 | 独立并行 | `episode_issues.py` + 消费点 | 若撞 verifier，后合方 rebase |
| W4 | 独立并行（只读） | `docs/verification/` + 台账 | 无 |
| W5 | 独立并行（纯新增） | `scripts/` + TOOLKIT.md | 无 |

## 验收流程（验收方执行，不抄实施方收据）

1. 交付物清单齐才开始（见全局纪律 8）。
2. 离线判据逐条**重跑**；变异测试**验收方亲手复现**（不看实施方截图）。
3. 重放判据用原始工件核 before/after（工件路径实施方须写进验证文档）。
4. 台账行与本 spec 预注册判据逐字比对，漂移打回。
5. 全量门禁在合流树复跑（`merge-tree --write-tree` 预检 rc=0 才进入）。
6. live 判据独立发探针（`workbench_probe.py`，探针用户独立命名 `probe-w<n>-verify-<date>`）或复算实施方 run 工件。
7. 裁决写 PR 评论；合并等用户确认；部署后回滚指针记入 inflight/main.md。
