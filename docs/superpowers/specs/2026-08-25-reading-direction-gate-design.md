# 设计：读向一致性闸（影子先行）+ ReAct 判读质量追赶路线（判读质量第二批）

- 日期：2026-08-25
- 状态：Draft v1（未实施）
- 来源：同码同题同预取的 glm-5.2 vs 5.3 A/B（收据 `~/.finance-runtime/glm53-ab-20260825/comparison.md`，2026-08-25）钉出两类**现无闸可抓**的错误：① 5.2 把医药医疗/半导体的放量/缩量方向词**互换写反**（数字引用全对，方向词全错）；② 5.3 读向全对但自造「约 1.8 万亿」阈值。同日用户拍板生产切 glm-5.3（`~/.finance-runtime/cutover-20260825j-8792.md`）——换强模型只降频，不消灭；确定性错误要确定性兜底。上游战略讨论：「追赶 live ReAct 判读质量，但不穷举问句」（2026-08-25 用户确认，五杠杆之二、三）。
- 代码树：spec 落 `docs/reading-direction-gate`（基线 `gitea/main@be67eb27`）；实施另从 `gitea/main` 开干净树 `feat/reading-direction-gate`。**禁止**在主检出脏树改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `2026-08-25-step-trajectory-qualification-design.md`（台阶/资格盘观察值是本闸的**判定源**；其 §3 #6 已实测 general_finance_qa 两删句闸都不适用——正是本单要补的空档）
  - `2026-08-25-substitute-observation-probe-design.md` §8 P2 `probe.menu` 预留原样有效，本单不实施不重复
  - `feat/reading-rules-baseline-r2`（Gitea #343，在途未合）：判读规则**入口侧供给**是它的地盘；本单是**出口侧兜底**，互补不替代，不依赖其合入
  - `2026-08-24-workbench-quality-residual-ux-design.md` D2/D4 管住本单：加的是确定性闸，不是模型回合/加时
  - `R-20260825-08`（删句闸活性事件，#385 已合）：「闸跑了零命中」也留痕的先例，本闸 trace 步同款

## 0. 一句话

公开稿里「放量下跌」「缩量回踩」「边际量转正」这类**读向词**，模型读反了照样出门——语义验证器只管数字编造（数字全对时不响），删句闸只对 market_watch / market_forecast 两路由的特定词面生效。5.2 在冻结题上把两个板块的量向标签互换写反（库实况：医药医疗 08-21/08-24 边际量 -16.83/-20.34 = 缩量，半导体 08-24 +16.25 = 放量，5.2 全写反），这正是台阶组件立项要供数的「跌但边际量转正」形状被**拿着正确数据读反**。本单加一道确定性读向闸：能唯一锚定（板块 × 日期）的读向断言，对照注册观察值 `diff_ratio` 的符号，矛盾先**影子记账**（P0 不改稿），基线率拿到后再上**revise-once 执法**（P1）。判读规则同席、形状标签中间层、点菜钉在 P1/P2，不与 P0 绑。

**判别变量**（验收只锁这一条）：人工植入读向互换的残差稿过闸 → trace 出现 `reading_direction_gate` 步、`mismatches` 逐条带（板块, 日期, 稿内读向词, 注册符号, 注册值）；干净稿过闸 → `checked>0`、`mismatches=[]`、**公开稿逐字节不变**。不是「多删了句子」，不是「稿子更保守」。

人话：厨师端菜前，专门有个人对着台账念一遍——「你说这盘是加了量的，台账写的是减量」。P0 这个人只记小本本不拦菜（先搞清厨师多久错一次），P1 才让他把菜退回去重做一次。

## 1. 范围

### 1.1 做（P0，全部影子）

- 新模块 `intelligence/services/reading_direction_gate.py`：
  - **读向断言提取**：从公开稿/owner 残差稿逐句提取（subject, date, direction）三元组。subject 只认**精确等于**本轮注册观察值 subject 的板块名（宽松匹配是量子科技陷阱同族，禁止）；date 只认显式 `YYYY-MM-DD` / `MM-DD`，或「当日/站立日」（映射 standing）；读向词典冻结为模块常量：`放量` / `缩量` / `边际量转正` / `边际量转负` / `量能放大` / `量能萎缩`（收小词族，宁漏勿误）。
  - **判定**：查同轮注册 `StructuredObservation`（`metric="diff_ratio"`，subject/as_of 精确命中）。`>0` = 放量/转正，`<0` = 缩量/转负；无注册值、值为 0、锚定不唯一 → skip 不判。
  - **产出**：payload `{checked, skipped, mismatches: [{subject, date, word, registered_sign, registered_value, excerpt}]}`。
- 接线：orchestrator 既有删句闸调用点**并挂**（与 `market_watch_delivery_gate` 同族双消费点：owner/合成路径 + Engine A 回退防线），applied 即落 trace 步 `reading_direction_gate`——**零命中也留痕**（R-20260825-08 先例）。
- 门控：本轮有台阶/资格盘观察值注册才开（判定源在才有闸；无源 run 完全无感）。
- 影子纪律：不改稿、不删句、不占 degrade 通道、异常回空不杀 run。

### 1.2 不做

- **不执法**——P0 不删句不修订；revise-once 在 P1，且须先拿影子基线率过正负控（无基线率就执法 = 盲杀）。
- **不做语义近义扩词**——「承接乏力」「资金流出」不是读向词，不判；扩词走词典常量 + 测试，不走正则泛化。
- **不判窗口聚合句**（「连续两天放量」）——date 锚定不唯一，P1-b 再议。
- **不重做 #343**——判读规则进开场消息是入口侧（它的单）；本单只管出口侧对账。两侧词汇对齐即可，无代码耦合。
- **不管未注册阈值**（「约 1.8 万亿」形状）——那是无格阈值闸家族扩路由的问题（须先解决「画像原文阈值 vs 自造阈值」判别），P2-c 钉方向另立单。
- 不实施 `probe.menu`（P2 预留原样）；不加模型回合、不改 tier、不动既有删句闸词面与路由。
- 不动台阶/资格盘组件本身（判定源零改动；其既有测试必须逐字节同绿）。

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **读向词** | 对「量的方向」的定性词：放量/缩量/边际量转正/转负 | 涨跌方向词（pct_chg 符号另族，P1 可扩）、资金流向词 |
| **读向断言** | 稿内一句话里可唯一锚定的（subject, date, direction）三元组 | 任何提到板块的句子 |
| **判定源** | 本轮注册 `StructuredObservation(metric="diff_ratio")` | grid 渲染文本、库直查（闸不开新查询）|
| **影子闸** | 判定 + trace 记账，稿件字节不动 | 灰度删句 |
| **revise-once** | mismatch → 一轮定向修订消息 → 复检；仍错才删句（P1） | 无限重写循环 |
| **同席** | 判读规则切片与对应数据组件一起进开场消息（P1-c，衔接 #343） | 把整本画像塞进 prompt |

## 3. 已核实事实（2026-08-25 实测，实施时不要再探一遍）

1. **[实测]** A/B 两发（同码 `52eba880`、同题、同 7 件预取、`task_frame_hash` 一致）：5.2 `run_20260825_143634_143023` 写「医药医疗…连续两天**放量**下跌（边际量 -16.8/-20.3）」「半导体…08-24 **缩量**续跌」；5.3 `run_20260825_151705_506786` 写「-3.17% 但边际量 +16.25% 的**放量**下跌」。库实况（`fact_sector_daily`）：医药医疗 08-21/08-24 diff_ratio **-16.83/-20.34**、半导体 08-24 **+16.25**（额 2500.31→2906.55）。→ 5.2 两处互换全错、5.3 全对；错误形态是**引用数字正确、方向词错**。
2. **[实测]** 判定源构造：`asof_prefetch._TIMELINE_METRICS = ("pct_chg", "amount", "diff_ratio")`；`sector_timeline_observations` 产 `StructuredObservation(subject=板块名, as_of=日, metric, value)`，**同日同指标冲突值不产观察值**（run_20260821_114642 事故注释在案）；资格盘三 metric（`total_amount`/`amount_avg_20d`/`amount_vs_avg20_pct`）subject=全市场。
3. **[实测]** 现有闸零覆盖：`outlook_delivery_gate` watch 闸只对 `market_watch`、outlook 闸只对 `market_forecast`（词面 `MA\s*20`/`110–120%` 带/旗型蓄能）；语义验证器管「残差数字不等于任何注册值」，数字全对方向词错时**不响**；冻结题路由 `general_finance_qa` 两闸都不适用（台阶单 §3 #6 实测原话）。
4. **[实测]** 活性事件先例：`market_watch_delivery_gate` applied 即落 trace 步、payload `{applied, dropped}`、零删不占 degrade（#385 已合，R-20260825-08；生产 live 首证 `run_20260825_120218_405339`）。本闸 trace 步同款构造。
5. **[实测]** 生产已切 glm-5.3（`cutover-20260825j`，`ps eww` 进程 env 验证）；5.3 本发读向全对——**基线错误率未知**，这正是 P0 影子先行的理由：执法与否用数据定，不用单发定。
6. **[实测]** E 号/观察值注册链路沿用台阶单 §3 #10：预取先进证据账本，`evidence_ordinal_table` 同表同号；闸读注册表即读到与模型所见同一份数。
7. **[代码级推断，实施第 0 步核]** orchestrator 删句闸双消费点（owner/合成路径 + Engine A 回退防线）可并挂本闸——实施时以 `market_watch_delivery_gate` 的两处调用为锚找准，不得只挂一处（单点挂 = Engine A 回退路径漏网）。
8. **[实测]** 台账号 `R-20260825-12/-13` 经 rg 全库（main + `fwp-wt-*`）未被占用。

## 4. 方案对比

| 方案 | 做法 | 得 | 失 / 判 |
|---|---|---|---|
| **A. 影子读向闸 → P1 revise-once（采用）** | 确定性符号对账，先记账后执法 | 零误杀风险起步；拿到真实基线率再决定执法强度；判定可复现 | 影子期读反照样出门（诚实代价，执法在 P1 且有数据依据） |
| B. 直接删句执法 | mismatch 即删 | 立刻拦住 | 丢真信息（整句含正确数字一起删）；无基线率即执法=盲杀；否决为 P0 |
| C. 只靠换强模型 | 已切 5.3 | 降频 | 无判定就无回读，off-day 无兜底；已做但不替代闸 |
| D. prompt 加读法提醒 | 开场消息带「边际量为负=缩量」 | 便宜 | 无判定不可回读；且是 #343 入口侧地盘。不在本单 |
| E. 形状标签中间层先行 | 模型先出结构化形状标签再成文 | 判定最干净 | 改 episode 协议，爆炸半径大；P2-a 钉方向 |

## 5. 目标态

```
episode 完成 → owner/合成稿
  → reading_direction_gate(稿, 本轮注册观察值, standing)
      提取读向断言（subject 精确 ∈ 注册 subjects；date 显式或 当日/站立日）
      逐条查 diff_ratio(subject, date) 符号：
        >0 vs 缩量/转负词 → mismatch
        <0 vs 放量/转正词 → mismatch
        无值/为0/锚不上 → skipped
  → trace 步 reading_direction_gate {checked, skipped, mismatches[]}
  → P0：公开稿原样交付（影子）
  → （P1：mismatch → 一轮定向修订 → 复检仍错 → 删句 + degrade）
```

## 6. 契约

1. **判定源唯一**：只读本轮注册 `StructuredObservation`（`metric="diff_ratio"`，subject/as_of 精确等值）。不查库、不读 grid 文本——闸不得开第二条取数口径。
2. **锚定 fail closed**：subject 必须精确等于某注册观察值 subject（「科技」句不得锚到「量子科技」的观察值——宽松匹配禁令与台阶单 §6.2 同族）；日期必须显式或「当日/站立日」→ standing。锚不上 → skipped，不猜。
3. 注册值为 0、同日无值（上游冲突不产值）→ skipped。
4. **影子不变稿**：闸前后公开稿字节相等；不占 degrade 通道；trace 步 applied 即落（`checked=0` 也留痕）。
5. mismatch 记录 `{subject, date, word, registered_sign, registered_value, excerpt}`；excerpt 只截断句内最短片段（trace 落 run 私有目录，与既有稿件落盘同级）。
6. 词典冻结为模块常量；扩词必须带新夹具，不改正则骨架。
7. 异常一律回空 payload——闸不得杀 run（预取件同款纪律）。
8. 门控：本轮注册观察值含 `diff_ratio` 才启用；无源 run 不落步（区别于 #4 的「applied 即留痕」——applied 的前提是门开）。

## 7. 验收（离线红→绿 + 变异；live 影子读数）

夹具自带注册观察值表（diff_ratio 正负零、同日冲突各备）＋ 残差稿文本。

| # | 夹具 | 必须 |
|---|---|---|
| 1 | 稿含「半导体 08-24 缩量下跌」，注册 diff_ratio=+16.25 | mismatch 1 条，四元组齐（半导体, 08-24, 缩量, +）；**变异**：符号判定反转 → 红 |
| 2 | 同数据稿写「放量下跌」 | checked+1、mismatches=[] |
| 3 | 「医药 当日缩量回踩」，standing 日注册 -20.34 | 「当日」映射 standing 后判定通过（checked+1, 0 mismatch） |
| 4 | 稿提「科技」但注册 subjects 只有「量子科技」 | skipped（不锚定）；**变异**：subject 改 contains 匹配 → 红（量子科技陷阱回归锁） |
| 5 | 同日冲突（上游不产值）/ 注册值为 0 | skipped，不判 |
| 6 | 「连续两天放量下跌」窗口聚合句 | skipped（P0 不判聚合）；不误报 |
| 7 | 含 2 处互换错误的稿全流程过闸 | 公开稿**逐字节不变**；trace 步在场含 2 条 mismatch；degrades 无新项；**变异**：把 mismatch 接到删句路径 → 红（P0 禁执法） |
| 8 | 无任何读向词的稿（门开） | checked=0、步仍在场（活性，R-08 同款） |
| 9 | 本轮无 diff_ratio 观察值（门关） | 不落步、稿不变、run 正常 |
| 10 | 闸内部抛异常 | 回空 payload，run 不受影响 |

### Live（实施收尾，sidecar 端口，新目录）

- 冻结题重放一发：trace 步在场，`checked/skipped/mismatches` 与人工对稿一致；公开稿与闸前字节一致。收据落 `~/.finance-runtime/reading-direction-gate-live-<date>/`，不覆盖 `glm53-ab-20260825/`。
- 影子期（合入切流后）：生产自然样本累计读 mismatch 基线率，作为 P1 执法的正负控输入。台账不标 confirmed（等自然样本）。

## 8. P1 / P2（本单不实施，只钉方向）

- **P1-a revise-once 执法**：mismatch → 一轮定向修订消息（引注册值与 E 号）→ 复检仍错 → 删句 + degrade 入账。前置：影子基线率非零 + 开关板原子 + 正负控消融（修订轮不得让稿件其他部分变差）。预注册 `R-20260825-13`。
- **P1-b 窗口聚合句**：「连续 N 天放量/缩量」按窗口逐日符号判定（全同向才算对）。
- **P1-c 判读规则同席**：#343 合入后，按预取组件键选规则切片进开场消息（资格盘⇄量能状态机规则、台阶⇄读向定义）。依赖 #343，另立验收，本单词典与其规则词汇对齐即可。
- **P2-a 形状标签中间层**：模型先对每件预取出结构化形状标签（放量下跌/缩量回踩/双红延续…）再成文；标签可闸、可积累、错误可回灌。改 episode 协议，独立设计。
- **P2-b `probe.menu`**：预留原样（替补/资格/台阶 = 前三道菜），不与本单绑。
- **P2-c 未注册阈值扩路由**：「约 1.8 万亿」形状——无格阈值闸从 watch/outlook 扩到 general_finance_qa 前，须先设计「画像原文阈值（有 E 号）vs 自造阈值」判别，另立单。

## 9. 落点

| 文件 | 职责 | 序 |
|---|---|---|
| New: `intelligence/services/reading_direction_gate.py` | 断言提取 + 符号判定 + payload（纯函数，无 IO） | P0 |
| Modify: orchestrator 删句闸双消费点 | 并挂影子调用 + trace 步（两处都挂，§3 #7） | P0 |
| Test: `intelligence/tests/test_reading_direction_gate.py` | §7 #1–#10 全表 + 变异 | P0 |
| 收尾: `docs/prediction-ledger.md` | `R-20260825-12`（P0）、`R-20260825-13`（P1 预注册） | 收尾 |

## 10. 账本

| ID | 现象 | 类型 | 序 | 验证 |
|---|---|---|---|---|
| `R-20260825-12` | 读向词（放量/缩量/边际转正转负）无任何闸对照注册观察值符号——数字对、方向词错的稿照样出门（A/B 实锤：5.2 两处互换；general_finance_qa 路由删句闸零覆盖） | `HARNESS_FIX` | P0 | §7 #1–#10 / live 影子 |
| `R-20260825-13` | 影子闸只记账不拦截；执法需 revise-once（删句丢真信息）且须基线率与正负控支撑 | `HARNESS_FIX` | P1 预注册 | P1-a 前置三件（基线率/开关板/消融）后另行验收 |

## 11. 实施顺序

1. 干净树 `feat/reading-direction-gate`；第 0 步核 orchestrator 双消费点（§3 #7）。
2. §7 #1 红 → 提取器 + 符号判定 → 绿；#2/#3 逐条。
3. #4 锚定 fail closed（变异先红）；#5/#6 skip 语义。
4. #7 影子不变稿 + 活性步；#8/#9 门控；#10 异常回空。
5. live 一发（§7.Live，sidecar 新目录）。
6. pathspec 提交；合 main 等用户确认。spec 修订随代码同 PR。
7. 合入切流后影子期攒自然样本基线率 → 决定 P1-a 是否立单。

## 12. 自检

- 无 TBD；唯一待核项（双消费点）钉在第 0 步且不阻塞设计判断。
- 判别变量 = 「植入错误被记账 + 干净稿字节不变」，不是「稿子更保守」。
- fail closed 三处：subject 精确锚定、日期显式锚定、无值/零/冲突不判。
- 与 #343 分工：入口供给 vs 出口对账，无代码耦合；与台阶单分工：判定源零改动。
- P0 影子先行的理由写死在 §3 #5：执法与否由基线率定，不由单发定。
- P1/P2 各自带独立验收与预注册号，未混入 P0。
