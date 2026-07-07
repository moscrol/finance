# 每日操作清单 v2（复盘 + 知识库 + 训练闭环）

> 原则不变：机制的运转成本都在系统侧，你只做「喂原料 → 看报告 → 一句话纠偏」。
> 新增总原则：**判断落 checkpoint 前必过反方；每条 checkpoint 必带来源。**
> 时间紧的日子：只保 ★ 项 + IMA。清单完成感不是目标，账本质量才是。

## 一、早上（~3 分钟）

1. **★ 喂晨汇原料**：把早间材料丢给 agent，说「做晨汇」。
   - 原料自动落 `wiki/raw/briefings/<date>/`，产物 `wiki/briefings/<date>.md`。
   - 断更 1 天以上，复盘 preflight 会告警（催化剂归因就会缺档——宇树那次的教训）。
2. **主问句①②**（DuckDB 盘面流 + 晨汇事件流）：问法模板见 §四，两点新要求：
   - 判断落 checkpoint 时带来源：`--source duckdb_flow` / `--source briefing_cross`
   - 事件流挑出的 Tier 1 **先过一遍反方**：
     `python3 -m intelligence.cli red-team --claim "..." --theme XX --category XX`
     ——它把最不利证据、你的历史纠偏、低胜率判断类型摆在你面前。见过最强反面再落账。

## 二、收盘后（~10 分钟，核心）

3. **★ 说「全量复盘」**（触发 daily-full-review skill，全自动）。
   跑完后报告里自动带：
   - **框架解读**：按你的 user_framework 解读当日硬数据，命中判断自动落 T+1/T+3
     checkpoint（自动带 `source=framework_interpretation` + framework_version）。无命中=宁缺毋滥，正常。
   - **T+1/T+3 回检**：前日/前三日判断自动打分（hit/miss/unverifiable）。
   - **时效告警**：晨汇/卖方观点断更会显式提醒你补。
4. **★ 扫回检结果，有异议一句话纠偏**：
   - 「不对，XXX 应该是 YYY」→ 自动落 correction，下次复盘自动回灌。**沉默 = 默认认可。**
   - 这是全清单单位时间价值最高的 2 分钟——你在给自己的判断史记账。
5. 看 daily-agent 简报的**知识库回补任务包**，分两类处理：
   - **新题材（标"做 IMA"）**→ 你做 deep dive（IMA）。⚠️ 它不是待办杂项，是你唯一必须
     亲自动脑的主业；哪天没时间，砍别的保它。
   - **旧逻辑唤醒（找公告/订单）**→ 说「给XX题材的强势股跑 disclosure-archive」。
     口径不变：**L3 测公司端兑现度，不测题材合法性；无公告≠无驱动**。
     （生命周期推演的前瞻判断也会自动落 checkpoint，`source=logic_lifecycle`。）

## 三、晚上（~5 分钟）

6. **★ 喂晚间卖方材料**：拿到研报口播/观点合集/电话会纪要，直接丢给 agent 说「ingest」。
   - 铁律不变：**原文永远先落 `wiki/raw/sellside/`**，再走 opinion-cross 提纯。
     原文丢了就无法重新提纯（6-18~6-28 的教训）。
7. **主问句③**（卖方流）：模板见 §四，同样两点——判「透支/增量」落 checkpoint 带
   `--source sellside_cross`；**重仓相关方向的判断先过 red-team**。
8. （有精力的日子）双盲答卷：流程不变（manifest 冻结→独立答卷→recheck→aggregate）。
   单期噪声大，结论只看聚合。

## 四、每天问 LLM 的三条主问句（可证伪训练流，固定问）

> 每条都要求 LLM 给出「判断 + 数值依据 + 证伪条件」，判断落 checkpoint（带 --source），
> 到期自动回检。训练闭环：问 → 判 → 检 → 纠。

### 1. DuckDB 盘面流（早间，T+1 回检，source=duckdb_flow）

问句模板：
> 基于截至昨日收盘的 DuckDB 数据（manifest 冻结）：① 当前市场处于什么阶段（发酵/加速/分歧/退潮），核心依据是哪三个数值？② 列出今日双红候选板块（≤3 个），每个给出「延续」或「衰竭」判断及数值阈值；③ 涨停热度和连板晋级率的方向判断；④ 给出一条今日最可能的市场路径（如「高开分歧→午后修复」），以及什么盘面信号出现即宣告此路径失败。

- 检测点（T+1 收盘后查）：双红板块当日红盘数/边际量、涨停家数与晋级率实际值、指数与情绪路径实际走法。
- 证伪点（让 LLM 自己填具体数）：「判衰竭的板块当日仍双红且边际量>前日 → 证伪」「晋级率判回升但实际 <X% → 证伪」「路径判断：宣告失败信号当日出现即记 miss」。

### 2. 晨汇事件流（早间，当日/T+1 回检，source=briefing_cross）

问句模板：
> 今日晨汇三维交叉结果中：① 挑出你认为最可能兑现的 1 条 Tier 1（或升级中的 Tier 2），说明公告增量 × 库内认知 × 盘面状态三维分别是什么；② 该事件今日的兑现形态预判：直接涨停/高开低走/盘中脉冲/不反应，四选一；③ 哪些情况说明这条 Tier 分级本身分错了？

- **落账前先 red-team 这条 Tier 1**（制度化反方，判断落账前的最后一道工序）。
- 检测点：该标的/题材当日开盘、盘中高点、收盘表现；同题材其他标的是否联动（区分「事件兑现」vs「板块 beta」）。
- 证伪点：「判直接涨停但收盘涨幅 <5% → 兑现形态 miss」「判 Tier 1 但当日题材内无一标的异动 → 分级证伪，回查三维中哪一维评估错（通常是盘面维）」。

### 3. 晚间卖方流（晚间，T+3/T+5 回检，source=sellside_cross）

问句模板：
> 今晚卖方研报经覆盖密度交叉后：① 挑 1 个方向判定为「信息增量」或「跟风透支」，依据是第几篇覆盖、库内证据硬度、当前盘面位置三项；② 若判信息增量：T+3 内该方向应出现什么确认信号（板块转双红/龙头新高/成交额放大到 X）？③ 若判透支：T+3 内应出现什么衰竭信号（覆盖再加密但板块不再创新高/龙头滞涨）？④ 什么走势会推翻你的判断？

- 检测点（T+3、T+5 各查一次）：该方向板块双红状态、龙头相对强度、成交额变化、后续覆盖密度变化。
- 证伪点：「判增量但 T+3 无任何确认信号 → miss」「判透支但 T+3 板块创新高且边际量扩张 → 证伪（说明覆盖密度阈值定早了，这本身是要沉淀的教训）」。

### 4. 复盘验证模版（双盲答卷流，收盘后/晚间）

一句话触发（agent 会按 `docs/learning/dual-blind-forecast-template.md` 走完整工装流程）：

> 「按双盲答卷模板出今天（<日期>）的复盘验证答卷：先跑 `dual_blind_forecast.py manifest` 冻结输入（DuckDB 截止昨日 + 今日复盘材料），然后按模板 §0-§5 独立答卷——阶段/量能/广度/双红/涨停/新高/核心股全部落数值，主判断一句话，方向排序，标的池 5 只（绑定 §1 字段证据），验证条件给 T+1/T+3 强制数值阈值和证伪信号；落 `forecast-review-ledger/<date>.answer.<agent>.json` 并 validate 通过。」

- T+1/T+3 回检：说「回填 <日期> 答卷的 recheck 块」（统一客观指标，非考生自填）。
- 跨期看趋势：说「跑 dual_blind_forecast aggregate」——单期噪声大，结论看聚合；
  系统性偏差确认后才沉淀经验卡。
- 双盲比较时让 Claude / Codex 各答一份（互不可见），你只做批注和裁决。

> **已自动化（2026-07-07 起）**：launchd `com.financeworkspace.dual-blind-forecast` 每交易日 09:10
> 自动跑 `scripts/dual_blind_auto.sh`——manifest 冻结（视角日=DuckDB 最新交易日，依赖 09:00 deltapull）
> → Codex（`codex exec`）/ Claude（`claude -p`）双盲各落一份答卷 JSON → validate 收卷 → index 重建。
> T+1/T+3 数值回检由 18:30 全量复盘链自动追加（recheck + index，人工字段不覆盖）。
> 你只剩：看 index.html 并排对比、批注裁决、跨期说「跑 aggregate」。

### 其他随手可问（挑着问）

- 「今天框架解读哪条判断我不认可」→ 直接说出来，落 correction。
- 「XX题材今天的驱动是什么？叙事驱动还是纯盘面异动？」（催化剂归因）
- 「XX题材做一个题材雷达 / 发酵链路回溯」（theme-radar / fermentation-tracer）
- 「查一下XX公司近30天的公告和互动」（L3 兑现度，测兑现不测合法性）
- 「强势股入库 / 均线回踩筛选 / 涨家数走势」（各盘面 skill）
- 「checkpoint status」——看台账概览：登记数/待回检/胜率。

## 四之二、训练问法（减负版：常驻两种，其余按需）

> 原理：AI 对你的理解 = 训练信号的 覆盖面 × 密度 × 保真度。
> 六种全开会稀释认真度——常驻只留两种，其余按需。

**常驻：**

1. **二选一偏好对（每天一对，信息密度最高的标注）**
   「按我的视角，A 和 B 只能上一个，你选哪个？」你再说你选哪个 + 为什么。
   成对比较比绝对打分噪音小得多（RLHF 的基础），每天一对，积累速度远超散装纠偏。
2. **错题解剖（每周一次，有交易的周才做）**
   「我这周最错的一笔，按框架回放：断在哪一步？是画像缺规则，还是有规则没执行？」
   前者补 profile，后者补执行——分开归因才能各自迭代。

**按需（别全开）：**

- **模仿测试**：「不看我的观点，预测我今天会怎么看 XX」。做的话，涉及的判断抽样落
  `checkpoint --source mimic_test`——让"它懂不懂你"和"你对不对"绑在一起验证。
- **决策审计**：「我今天买了/卖了/没动 X，按我的画像给这个决策打分」（有实际动作的日子）。
- **边界探测 / 潜意识模式反问**：每 1-2 周，想起来再用。

所有回答都会按 AGENTS 规则自动落 correction/checkpoint，不用你管格式。

## 五、周期性动作

- **每周看校准**：「checkpoint calibrate」——现在看**两个维度**：
  - 按推演类别：哪类判断靠谱/失真（失真→改表述或补隐式规则）；
  - **按来源（新）**：framework_interpretation / logic_lifecycle / duckdb_flow /
    briefing_cross / sellside_cross / mimic_test 各自胜率——三个月后这张表回答
    「哪个模块在产真信号」，低于基准的模块降级为资料工具。
- **每 1-2 周（回一个词）**：profile 修正 diff，回「确认」或「不要」。
  确认后 framework_version 自动换新，胜率统计能区分新旧框架的判断。
- **每月一次（新）**：知识库仓跑 `python3 scripts/audit_access_log.py --days 30`——三张名单：
  高命中页（值得精修）/ 零命中陈旧页（停维护不删页）/ 命中但陈旧页（ingest 预算优先给这里）。
  审计的目的是**重新分配你的 ingest 时间**，不是清库。
- **PR 审批**：agent 的代码改动都走分支+PR，等你说「合并」才进 main。

## 六、红线提醒（对 agent 说话时不用管，自己动手时注意）

- 不提交 `.env*`/密钥/PDF/duckdb/`.DS_Store`；大任务必开分支；不擅自合 main。
- user_framework.json / corrections / checkpoints 在 `intelligence/users/default/`（gitignored 私有层），
  换机器要单独同步（可设 `FORESIGHT_USERS_DIR` 指向云盘）。
- **共享台账已统一到 `FORESIGHT_USERS_DIR=/Users/a77/agent-memory/.foresight`**（2026-07-07 起）：
  - 交互式 zsh 与非交互 zsh 均自动带上（`~/.zshrc` + `~/.zshenv`）；launchd 走 plist 内 env（launchd 不读 zsh 配置，改路径要两处同步）。
  - **agent（Codex/Devin 等）经 bash/sh 非交互执行 checkpoint / red-team / calibrate 时，必须显式带上**：
    `FORESIGHT_USERS_DIR=/Users/a77/agent-memory/.foresight python3 -m intelligence.cli checkpoint status --user linxiaoqi5111`
    或统一 `zsh -c '...'`；否则会误读仓库内默认空台账。

## 附：四个循环的关系（比旧图多一条反方线）

```
你喂原料 ──→ 复盘自动跑 ──→ 框架解读 ──→ Tier1 判断先过 red-team（循环C：制度化反方）
                                        │
                                  落 checkpoint（带 source）（循环B：执行质量）
                                        │
你扫一眼纠偏 ──→ correction（循环A：学你视角）──→ 回灌 + 喂 red-team 的历史错误库
                                        │
T+1/T+3 回检 ──→ 每周 calibrate（类别×来源）──→ 每 1-2 周 profile diff
                                        │
每月 access-log 审计 ──→ ingest 预算重分配（循环D：知识库维护对齐真实使用）
```

一句话总结整个系统：**AI 负责记性和纪律，你负责判断和拍板；账本负责告诉你们俩，谁在哪里靠谱。**
