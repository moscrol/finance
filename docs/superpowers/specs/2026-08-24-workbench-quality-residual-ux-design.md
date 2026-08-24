# 设计：品质优先的残差预算 —— 逼近对照会话，不加无效长循环

- 日期：2026-08-24
- 状态：Draft **v1.1**（v1 审查 **PASS-WITH-NITS** 已收。P1 升档在 `feat/forecast-residual-deep`；P2 未做）
- 性质：产品策略稿。前序组件稿 `2026-08-24-outlook-live-weekly-pack-design.md`（v2）已落地大半；本单回答「加预算会不会更好」和「怎样灵活而不穷尽」。
- 来源：同日对照会话（Cursor ReAct vs 生产 `run_20260824_164201_040215`）+ 干净树 live（`~/.finance-runtime/outlook-live-20260824/receipts/`）+ 用户三轮纠偏 + 2026-08-24 审查。
- 代码树：继续 `/Users/a77/fwp-wt-outlook-live-weekly-pack` @ `feat/outlook-live-weekly-pack`。文档入仓：`docs/workbench-quality-residual-ux`（从 `gitea/main` 只提本稿）。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做）：
  - `docs/superpowers/specs/2026-08-24-outlook-live-weekly-pack-design.md`（座位 + 活周报日期键 + 五日包；P0 椅子是开口预取）
  - `docs/superpowers/specs/2026-08-24-market-watch-component-first-design.md`（当日四袋；共用函数不共用椅。其「方案 A」= 拒收 Engine A + 汇合处跑包，**不是**本稿 §7 否决的「做法 A（只加全局超时）」）
  - `docs/superpowers/specs/2026-08-24-personalized-join-kernel-design.md`（买卖点 StancePack；台账 `-25`…`27`）
  - `docs/superpowers/specs/2026-08-17-followup-angle-composer-design.md`（追问角度；本单 P2 复用，不新造第三条链）
  - `docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md`（公开稿质量事故；本单不重做丢数/对账）
  - `docs/superpowers/specs/2026-08-16-outlook-question-empty-delivery.md` 相关台账：`R-20260816-01` / `-02`（**禁止只把 T 调大当修复**）
  - `docs/superpowers/specs/2026-08-19-residual-retrieval-prime-design.md`（「残差题」= `general_finance_qa` 已需检索的那类题；**不是**本稿的「残差」）

审查方已签：只审本稿。不改代码、不切生产、不把任何台账行标 `confirmed`。v1.1 之后实施 P1 前以本节 + §0.1 / §5 / §9 为准。

### 术语（本稿内）

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **残差** | 开口组件（座位编译 + 活周报 + 五日包）上桌之后，Engine A ReAct 再解释 / 补格的那一层 | `2026-08-19-residual-retrieval-prime-design.md` 的「残差题」（`question_type=general_finance_qa` 且已需检索） |
| **编译** | 开口预取写入账本（`_seed_opening_prefetch`）。无 `content_hash` 则 fail closed | 模型自己点工具 |
| **做法 A / B / C / D** | 仅指 §7 品质路径四选一 | 盘面稿的「方案 A」（拒收 Engine A + 汇合处跑包）；outlook v2 的「拍板 (a)」（开口预取椅） |
| **tier** | `ResearchPolicy.for_tier`：`quick` 3×30s、`standard` 6×90s、`deep` 12×240s（另有 `synthesis_reserve`） | 全局环境变量超时 |

## 0. 一句话

用户要的是**体验和品质**，不是省 token。逼近对照 agent 的路径是：**先把对照会话里那几刀开场菜收成开口组件，再只给对的座位加长残差，再用下一回合深挖**。只加全局超时、只加 prompt、把默认聊天做成半小时翻箱，三条都否决。

**判别变量**（本单验收只锁这一条）：冻结展望题在同一次 Engine A run 上同时满足「座位对 + 活周报进账本（有 `content_hash`、E 号、`date=max(article.date)`）+ 五日包在开口 + 公开稿可用」。加长残差之后，用户能多看到**至少一格增量**（多一条情景，或续走/失效里多一条可核验条件），且不出现「同一工具连打 / 首动作 `deadline_exhausted` / 空转修轮」。不是「总时长更长」，不是「文笔像对照会话」。

人话：钱花在「菜上桌之后让厨师多解释两句」，不花在「菜单写错了再多炒十分钟」。对照 agent 全面，是因为他先做了开场刀；Workbench 要把那几刀变成每盘必做，再用对话第二轮去学他的追问，而不是第一轮学他的耗时。

### 0.1 已拍板（审查 2026-08-24：D1–D5 **维持**，无替代判别变量）

| ID | 决定 | 不是 |
|---|---|---|
| D1 | 品质 / 体验第一；省成本不是本单目标 | 不等于无限循环、不等于全局 90→600 |
| D2 | 灵活来自「短座位表 + 固定格 + 残差 ReAct + 用户纠偏」，不来自穷尽措辞 | 不新开「像 Cursor 一样」的第四条 runtime |
| D3 | 加预算只加在**编译之后的残差**，且按座位（先 `market_forecast`） | 不加在错座位上；不先改 8792 全局超时 |
| D4 | 默认聊天保持「先出一盘能用的」；更深的对照级分析走**下一回合** | 第一轮不做成对照 agent 的半小时翻箱 |
| D5 | 无效循环的定义是可观察的：同工具连打、修轮不增格、首动作耗尽 | 不是「秒数超过 N」本身 |

同构已有闸：`should_reenter` 的 `progressed`（`repair_coordinator.py`）= D5 的修轮不增格。`_seed_opening_prefetch` 无 `content_hash` 不入账 = D3 的「P0 必须先于 P1」。

### 0.2 前序事实（不要再发现一遍）

Outlook v2 在干净树两刀已提交（`5cc48554` 无序合取，`6b4af952` 开口预取）。离线 6322 过 / 0 红。Live（8810，未碰生产口）：

| run | 题型 | 五日包 | 活周报进账本 | 稿 |
|---|---|---|---|---|
| `run_20260824_211029_527268` | `market_forecast` | 有（窗接到库尖 08-24） | prefetch 有 4 条 `kb_search`，无 hash，**账本没有** | 1243 字，可用 |
| `run_20260824_211751_532307` | 同上 | 空（主库被 `/tmp/fph_auth_backfill_0824.py` 写锁） | 有，`2026.34` / `2026-08-17` | 缺口稿 |
| `run_20260824_211246_749148` | `market_forecast` 中立 | 有 | skipped | 可用 |
| `run_20260824_211353_060560` | `theme_analysis` | 预取支未跑 | 无 | 路由对；稿是证据不足（质量另开） |

**PRIMARY（live 拆的）**：`_seed_opening_prefetch` 认不出 `content_hash` 就 fail closed。`live_weekly_evidence` 当初不写 hash → 模型在开场散文里能看见 2026.34，公开 E 袋没有活周报。工作区未提交修补已写（脏：`perspective_live_weekly.py` / `episode_tools.py` / 对应测试）。**同一次 run 两盘齐还没绿**，outlook 树 ledger 的 `R-20260824-20`…`24` 保持 `pending`。

对照 run 不是超时交白卷。它调了工具也出了稿。差的是闲聊座位、旧周报、开场没有五日结构。因此「加预算就能全面」对那次 **不成立**。

`strip_outlook_violations` 在 outlook 干净树，**`gitea/main` 未见**。策略稿引用合理；P0-c 实施前须符号落地，禁止按 main 行号找闸。

## 1. 范围

### 1.1 做

- **P0 收口前序洞，不新开产品面。** 活周报 / analog 进开口必须带 `content_hash`，经 `_seed_opening_prefetch` 进账本并发 E 号。Live 须在**无写锁**时重跑冻结题，一次 run 上两盘齐 + 可用稿。隔板「已验证」句仍按 outlook v2 §7.4 #20/#21，闸接到 `_complete_continuous_turn`（不挂 compose）。库锁诚实态见 §9.1 #5。
- **P1 按座位加长残差。** 加长 = `market_forecast` 升 `deep` tier（`standard` 6×90s → `deep` 12×240s），或同层只调一对 `(max_steps, total_seconds)`。禁止同时拧「轮次 + 墙钟 + 每格剩余预算」三个独立旋钮。每轮必须多兑现一格或显式 gap，禁止同 `(tool, 规范化问句)` 连打。涨停家数、dated 事实题保持短预算。
- **P2 第二轮深挖，不拉长第一轮。** 首轮公开稿带「已上桌 / 未核验格」；用户追问或点建议追问再开一回合。复用已有 followup 稿与 `open_gaps`，不新造第三条链。
- 写清「无效循环」的停机条件（§6），先于加秒。

### 1.2 不做

- 不把 8792 全局 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` 作为本单主杠杆。
- 不把默认路径做成对照 agent（无上限翻文件、人在环里改方向）。
- 不靠 prompt「请先查最新周报」当主修法。
- 不穷尽展望措辞；座位规则仍是 outlook v2 的无序合取。
- 不把「稿子像 SPT / 像对照会话」锁进验收。
- 不重做 knevo28 质量线、join StancePack、盘面 compose 椅。
- 不把有色金属 `theme_analysis` 的「证据不足」并进本单 P0（可单独立项）。
- 不碰 V8 删除权 / optional-forward-slots；边界干净。

## 2. 用户要什么（体验，不是文笔）

对照会话里用户在乎的四段，按优先级：

1. 上周量能 / 主线有没有说清楚（五日包）。
2. 选了 SPT 时，用的是不是**现行**一篇（`date=max(date)`，不是 2026.23）。
3. 有没有判断，以及「什么情况下这句话作废」（展望五件套）。
4. 说错了下一句能不能纠正（已有 `corrections.jsonl`，本单不改入口）。

文笔像不像对照 agent：**不锁**。第一轮耗时接近对照会话：**不锁**（那是反体验）。

## 3. 为什么对照 agent「没这个环节」也能做好

Engine A **已经是 ReAct**（`continuous_turn_adapter`）。冻结 run 也在调工具。差距不是「生产不会 ReAct」。

对照 agent 在对话里用很多轮做了生产缺的开场刀：先定性词序、按日期取周报、按五个交易日对盘面。他不是没做编译，是**手做、做得很慢**。Workbench 不能把默认聊天做成那种慢；要把同一刀收成开口必做。

加预算不代替这三刀。三刀不在，加长只是更贵的错菜。

## 4. 灵活：穷尽问法 vs 短座位

新情况先守这组分诊：

- **旧座位换词序** → 合取 / 无序，禁止再加一条特例正则。
- **新套餐** → 新座位 + 新固定格（买卖点走 join 稿，不塞展望）。
- **认不出** → fail closed，开口说按当前座位做不了，禁止装成对照 agent。

残差 ReAct 只在格缝里即兴。情况靠用户纠偏积累，不靠预先写完自然语言。

## 5. 加预算买得到 / 买不到

| 买得到（P1，座位已对、菜已上桌） | 买不到 |
|---|---|
| 多一条情景、续走/失效多一条可核验条件 | 词序听成闲聊 |
| 少截断、少「4 条证据未绑定」空桌稿 | BM25 把旧周报当活剧本 |
| 用户愿意等时残差更像分析师 | 开口没有周四主线袋 |

有色金属 live 调了 6 个工具仍证据不足：那种**有可能**吃座位级预算。展望冻结题不是。P1 先做展望座位；板块题另开审查，不顺手全局加时。

**P1 加长量纲（审查钉死，禁止三参同调）：**

| 闸 | 符号 | 作用 |
|---|---|---|
| 主闸 | `max_steps` / `repair_cycles`（须过 `progressed`） | 绑定有产出的轮次 |
| 硬顶 | `total_seconds` | 尾部挂死时封顶 |

落点：`market_forecast` 升 tier（`standard` → `deep`），或同层只调一对 `(max_steps, total_seconds)`。现成配对：`ResearchPolicy.for_tier`（`standard` 6×90s，`deep` 12×240s），有测试覆盖。

| 替代 | 优点 | 失败形状 |
|---|---|---|
| 只加墙钟 | 实现简单 | 买到等待，买不到有产出轮次 |
| 只加轮次 | 绑定进展 | 尾部挂死不封顶 |
| **tier 双闸**（采用） | 次数 + 时间已配对 | 须座位对 + 开口收据已齐，否则给错工作流加薪 |

禁止同时调「轮次 + 墙钟 + 每格剩余预算」三个独立旋钮。

## 6. 无效循环（停机条件，先于加秒）

加长残差之前，下列任一出现即停，标 degrade，出已有稿或诚实缺口，**禁止再要一轮**：

1. 连续两次工具调用的 `(capability, 规范化问句)` 相同。
2. 一轮结束，`required_outputs` 的 fulfilled 集合不增，且没有新的显式 gap。
3. 本回合第一个执行层事件是 `deadline_exhausted` / 装配耗尽（盘面稿已禁，展望同样禁）。
4. 修轮 `repair_attempts` 用尽仍无新格。

秒数本身不是停机条件。300 秒但每轮增格 = 合法品质预算。60 秒空转 = 无效循环。

## 7. 体验三截（默认路径）

```
首轮：座位编译 + 开口两盘 + 短残差
      → 公开稿：判断 + 已上桌的 E 袋 + 未核验格（用户语言）
用户追问 / 点建议追问
次轮：同一座位，继承账本，只补点名的格
```

P2 才做「首轮露出未核验格 + 接 followup」。P1 只加长首轮残差，不改信息架构。

替代对比（审查已选 **做法 D（组件先上桌 + 对的座位加长 + 追问再深）**）：

| 做法 | 体验 | 品质 | 本单 |
|---|---|---|---|
| 做法 A（只加全局超时） | 人人变慢 | 错座时更差 | 否决 |
| 做法 B（只加 prompt） | 看起来在想 | 一紧就漂 | 否决 |
| 做法 C（默认做成对照 agent） | 偶发很神，默认很慢 | 不可产品化 | 否决 |
| 做法 D（组件先上桌 + 对的座位加长 + 追问再深） | 首屏有货，愿等的人更深 | 底线稳，上限接近对照 | **采用** |

跨稿引用必须写全称。盘面稿的「方案 A（拒收 Engine A + 汇合处跑包）」≠ 本表做法 A。outlook v2 的「拍板 (a)（开口预取）」≠ 本表做法 A。

若改选做法 A/B/C，冻结题 live 会变成「更长耗时但座位 / 账本 / 五日包仍错」——与 §0 判别变量冲突，不可接受。

## 8. 落点（P0-a 已解锁；P1 须以 v1.1 为准）

| 序 | 做什么 | 文件 / 符号 | 不做什么 |
|---|---|---|---|
| P0-a | 活周报/analog 写 `content_hash` | `live_weekly_evidence`；开口拼接处补齐 | 不改编号规则 |
| P0-b | 无写锁 live：冻结题一次 run 两盘齐 | 8810 sidecar；避开主库 writer | 不覆盖冻结 run 目录；**禁止**两次 run 拼「假齐」 |
| P0-c | 隔板「已验证」删句 | `strip_outlook_violations` → `_complete_continuous_turn` | 不挂 compose；无格 `110–120%` 仍属 outlook P1 |
| P0 诚实 | 库锁第三态 `locked` | 五日包收据 `status ∈ {hit, empty, locked}` | 禁止把锁写成「该日无数据」 |
| P1 | `market_forecast` 升 `deep` 或等价一对 `(max_steps, total_seconds)` | `ResearchPolicy.for_tier`；连续回合预算入口（认符号，勿猜行号） | 不改全局默认；不改 `quick` 档字节；不改事实题 |
| P1 | 停机条件 §6 | 与预算同一层，副作用前判定 | 不靠 prompt 自报「我在空转」 |
| P2 | 首轮露出未核验格；追问接 followup 稿 | 公开稿投影 + `open_gaps` + 已有 followup | 不新造第三条追问编排；不与 P1 绑同一 PR |

工作区未提交的 hash 修补算 P0-a 的已写未提，pathspec 提交，禁止 `git add -A`。

## 9. 验收

### 9.1 P0（前序收口）

| # | 必须 |
|---|---|
| 1 | 开口 evidence 里活周报条目有非空 `content_hash`；变异：去掉 hash → 账本无「活周报」、有 E 号的盘面袋仍在 |
| 2 | 冻结原题 + `sptfei`，**同一次** live：`question_type=market_forecast`、活周报 `source_date=max(date)`、五日包（含周四袋或该袋 empty / locked）、可用稿。两次 run 拼证据 = 假齐，不算过 |
| 3 | 中立「展望一下A股后市」：活周报 skipped，五日包仍在，稿可用 |
| 4 | 「分析有色金属板块后续走势」仍 `theme_analysis`，展望预取支不跑 |
| 5 | **P0 诚实，不是可降级项。** 主库写锁时收据必须有第三态 `locked`（与 `empty` 并列）；公开稿能说「复盘写入中，请稍后」；**禁止**把锁写成「该日无数据」或静默 `except: pass` 成「包没跑」。**P1 才是**状态栏 / banner / 重试 / 写入让位。DuckDB 单写者模型下，`daily-full` 期间 connect 会 `IOException`——与「没数据」不可区分是撒谎，不是体验细节 |

### 9.2 P1（座位级加长）

| # | 必须 |
|---|---|
| 6 | **CI 合并闸 = 结构不变量，不是毫秒。** 三条：(i) `DETERMINISTIC_OWNER_TYPES`（`external_market` / `quick_fact` / `dated_market_review` / `market_watch`）不进 P1 加长分支；(ii) `ResearchPolicy.for_tier("quick")` 与 `max_repair_cycles_for_tier("quick")` 逐字节不变；(iii) 加长仅在「座位对 + 开口收据已齐」之后触发。对照题：`2026-02-17 涨停家数多少`（确定性 owner，不进 Engine A 加长支）。`≤5pp` 或绝对值 `≤2s` **只作 live 观测**，不作 CI 合并闸（latency flaky） |
| 7 | 冻结题在 P0 已绿的前提下，加长后公开稿比短残差基线**多兑现至少一格**，或同一格多一条带 E 号的条件句 |
| 8 | 夹具：同问句连打两次 → 第二次停机，degrade 可观察，不死循环 |
| 9 | 不出现首动作 `deadline_exhausted` |

### 9.3 P2（第二轮）

| # | 必须 |
|---|---|
| 10 | 首轮稿含未核验格的用户语言，无「【质检」 |
| 11 | 用户追问「把续走条件写具体」后，次轮补该格，不重跑五日包当新菜（可引用已有袋） |

Live 新目录，不覆盖 `four-arm-knevo-20260823/`、不覆盖 `run_20260824_164201_040215`。执行方不得把台账标 `confirmed`。

## 10. 账本

本稿自用：

| ID | 现象 | 类型 | 序 | 验证 |
|---|---|---|---|---|
| `R-20260824-28` | 活周报进了 prefetch 计数，公开账本无 E 号（无 hash） | `HARNESS_FIX` | P0-a | §9.1 #1/#2 |
| `R-20260824-29` | 主库写锁被写成 empty / 「该日无数据」 | `HARNESS_FIX` | P0 诚实 | §9.1 #5 |
| `R-20260824-30` | 全局加超时当品质杠杆；或展望残差空转 | `HARNESS_FIX` | P1 | §9.2 #6–#9 |

**编号协调（审查 nit，合 main 前消歧，本稿不改号）：**

| 号段 | 谁主张 | 截至 v1.1 的事实 |
|---|---|---|
| `-01`…`06` | 盘面包 | 多行已 `confirmed`（main） |
| `-11` | D4 开关板 | main pending |
| `-12`…`19` | knevo28 | outlook / 相关树 pending |
| `-20` | **双主张** | `docs/optional-forward-slots-addendum` **预占**（注明实施时才立案；当时按 outlook 草稿 `-11`…`15` 避让）。outlook v2 **已在干净树 ledger 立案**「句尾展望词序」（`feat/outlook-live-weekly-pack` 的 `docs/prediction-ledger.md`）。**`gitea/main` 尚无 `-20` 行** |
| `-21`…`24` | outlook v2 | 仅 outlook 树立案，未合 main |
| `-25`…`27` | join kernel | 设计稿占用；#359 合入买卖接线，main ledger 未见这三行 |
| `-28`…`30` | **本稿** | 自用，不改写 outlook 预测句 |

消歧规则：outlook 已立案的 `-20`…`24` 保持原文；addendum 实施立案时必须另取未占用号（先查 outlook 树 + `gitea/main` 的 `docs/prediction-ledger.md`，建议从 `-31` 起或当场向用户确认），**禁止再写 `-20`**。本稿不替它们改号、不标 `confirmed`。

## 11. 合入

1. 本稿入仓：`docs/workbench-quality-residual-ux`（只含本文件）。避免「只有 Mac 树可审」。
2. P0-a hash（outlook 干净树 pathspec，可与已有 outlook PR 同树、单独 commit）→ P0-b live 一次齐。
3. P0-c 隔板闸 + P0 诚实 `locked` 态。
4. P1 座位升 `deep` + §6 停机。**另 PR**，避免和 knevo28 质量线、join 抢同一超时常数。信息架构（P2）不绑这个 PR。
5. P2 followup 露出。可并行设计，实施等 P0 live 绿。

合 main 等用户确认。不强推。

## 12. 审查方必答 — 已答（2026-08-24，PASS-WITH-NITS）

原题保留，答写在题下。缺答曾 = 打回；现已齐。

1. D1–D5 是维持、改写，还是否决？  
   **维持。** 无替代判别变量。
2. 方案 / 做法 D 是否仍是唯一采用？  
   **是。** 做法 A/B/C 否决有据；改选则与 §0 判别变量冲突。
3. P0-b「同一次 run 两盘齐」是否允许拆成两次 live 拼证据？  
   **不允许。** `_seed_opening_prefetch` 在同一 episode 开口写账本；两次拼 = 假齐。
4. §9.1 #5 库锁可见性：P0 还是 P1？  
   **诚实性 P0（`locked` 态 + 文案），全局 UX P1。** v1 的「审查方可降 P1」已删。
5. P1 加长的具体量纲？  
   **轮次主闸 + 墙钟硬顶**（升 `deep` 或等价一对）。禁止三参同调。
6. 事实题「不变慢」的对照题和阈值？  
   对照题 `2026-02-17 涨停家数多少`。CI = §9.2 #6 三条结构不变量。ms 阈值只作 live 观测。
7. P2 是否必须跟 P1 同 PR？  
   **否。** 正交，分 PR 便于二分回滚。
8. 有没有把本稿写成「再造一个 Cursor」？  
   **否。** D2 / §1.2 / §7 约束默认路径；§3 是动机，被 D4 管住。

结论只许：`PASS` / `PASS-WITH-NITS` / `打回`。本轮：**PASS-WITH-NITS**。

可否动手：P0-a（hash）可在 outlook 干净树 pathspec 提交；P1 预算以 v1.1 为准另开 PR。台账 `R-20260824-28`…`30` 保持 `pending`。

## 13. 自检

- 无 TBD。预算加在残差。循环有停机。第一轮不学对照耗时。
- 判别变量是「同一次 run：座位 + 活周报入账 + 五日包 + 可用稿」，加长后锁「多一格」。
- 初判「加预算就会更全面」已按冻结 run 推翻。
- 版权：周报摘录仍 ≤360。文号不写死。
- 可搬走：品质 compute 加在编译之后；加在之前是给错误工作流加薪。v8「slot filling 取代事后裁剪」与本案 P0 同族；本稿不碰删除权。
