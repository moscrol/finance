# 设计：自选简报包（WatchlistDigestPack）

- 日期：2026-08-26
- 状态：Draft v1（仅落本文 + 词表/台账预注册，未改生产代码、未切端口）
- 来源：用户会话「金融 agent 做出来后怎么办 → 巨头接入哪些能炼 → 落一份 spec 让 agent 执行」。不是四阶段分诊。
- 代码树：从当时的 `gitea/main` 开干净树 `feat/watchlist-digest-pack`。本稿可先以 docs 进仓。
- **禁止**在主检出脏树上改 runtime（今日主树有 daily-full-review state / inflight 脏文件，不要往上叠）。
- **禁止**动 8792 / 8796 / 8802。
- **禁止**再调研 Google / OpenAI / Robinhood。背景已收在 §0.B，一手 URL 只作溯源，不是开工任务。

相邻稿（本单不重做、不抢合）：

| 邻单 | 它管什么 | 本单角色 |
|---|---|---|
| `2026-08-24-market-watch-component-first-design.md` | 全市场四袋；题型 `market_watch` | **委托** `run_market_watch_pack`，不复制 SQL |
| `2026-08-24-personalized-join-kernel-design.md` | 买卖题 StancePack（旧账 × 现价） | 不跑 StancePack。本单主键是画像自选，不是问句里的持仓词 |
| `2026-08-17-claim-tiering-and-revision-design.md` | Grounded 链主张绑定 / 降桶 | 公开稿**复用** fact / inference / gap 三档语义，不新发明第四种 marker 方言 |
| `2026-08-24-outlook-live-weekly-pack-design.md` | 展望题五日包 + 活周报 | 展望仍走 `market_forecast` |
| `intelligence/services/foresight.py` | 根据画像生成「你还没问的问题」 | 简报回答「清单今天发生了什么」，不是「该问什么」 |
| `2026-06-22-daily-agent-entry-design.md` | 日常开工：产物完整性 + 题材候选分类 | 运维总控，不是个性化简报 |
| `复盘/` + `render_daily_review_briefing.py` | 全市场复盘 HTML | 不改、不替代 |
| `2026-08-26-intraday-l2-sidecar-design.md` | 盘中 L2 边车，前置是 ClickHouse 鉴权 | P0 不接 L2 |
| `skills/theme-fermentation-tracer/` | 单题材历史发酵链路 | **P1** 才按 `focus_themes` 挂一条摘要；P0 只做当日盘面接合 |

---

## 0. 一句话

把巨头金融 agent 里**唯一该炼进本仓**的三件事做成一个确定性组件包：对着用户钉住的自选/关注题材，在模型开口之前跑完「当日盘面四袋 × 清单」的接合，冻住当时看到的行，按主张分级写出一页简报。模型只写格与格冲突的残差。不是 50 个新 skill，不是荐股，不是全市场日报换皮。

**判别变量**（验收只锁这一条）：冻结题「按我的自选出今天的简报」，在模型开口之前必须已经跑完 `WatchlistDigestPack`；公开稿里的数字只来自包内冻结行；每条结论带主张档（fact / inference / gap）和方法卡；没有「买入/卖出/现在做多」。不是「多调一次 `market_data`」，不是「稿子像不像 Robinhood Cortex」，也不是「把 Google 那 50 个 skill 抄进 `skills/`」。

人话：厨房里已经有全市场套餐（四袋）和用户的菜单（画像自选）。点菜员一直把「按我的菜单上菜」听成「上今日例汤」。本单让菜单先出锅，厨师只解释两盘对不上的地方，并把当时端出来的盘子拍一张照片存档。

---

## 0.B 背景（执行方必读，不要再搜一遍）

### 为什么会有这一单

用户做了一个自认为很强的 A 股投研 agent（本仓：复盘、题材雷达、研报、L2、chat-first workbench）。问的是产品做成之后走「拉用户」还是「拉投资」。结论已经拍过：**先找 5–10 个会反复用、最好会付钱的设计合作伙伴**，不先融资，不先公开获客。Workbench 目前仍是本机/私网工作台（`docs/workbench/local-site.md`），没有生产级身份认证，公开部署不是本单。

下一问是：巨头已经把金融 agent 打进产品，哪些可以炼进来；「50 多个 skill」是什么。

### 巨头实际发布了什么（已读原文，2026-08-26）

Google Cloud 2026-08-25 发布 [Gemini Enterprise for Financial Services](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-for-financial-services)（产品页 [cloud.google.com/ai/financial-services](https://cloud.google.com/ai/financial-services)，新闻稿 [Press Corner](https://www.googlecloudpresscorner.com/2026-08-25-Google-Cloud-Launches-Gemini-Enterprise-for-Financial-Services)）：

- **没有公布 50 个 skill 文件名。** 「50+ foundational skills」是包装语。官方定义：skill = 可复用的 instructions + context 包，教 agent 按机构口径跑一件专项（报告格式、某次 data cut、研究方法论）。Agent Skills 标准是按需 `load_skill`，避免 50 个工具一起塞进上下文。
- 公开点名的工作流类别：市场新闻合成 / 调查性投研 / 组合监控与风险 / 信用评估与定价偏差 / KYC·UBO / 顾问洞察 / 债券承销路演 / 久期对冲。设计合作伙伴是 Deutsche Bank Corporate Bank、CME。连接器约 13 个（FactSet、LSEG、Moody’s、MSCI、PitchBook、S&P、SEC Edgar 等）。
- Financial Research agent 的产品承诺是四件套：**confidence scores、explicit methodologies、data snapshots for auditing、precise source citations**。Deutsche Bank 原话强调的是减少手工研究、输出可一致可审计，不是「更会聊天」。

OpenAI [ChatGPT Finances](https://openai.com/index/personal-finance-chatgpt/)（帮助中心 [Finances in ChatGPT](https://help.openai.com/en/articles/20001222-finances-in-chatgpt)）：Plaid 连 12000+ 机构；消费分类、订阅、净资产、持仓分配；Financial memories；**不能转账、不能下单、不当投顾**。这是个人账本，不是 A 股投研。

Robinhood Cortex：[帮助中心](https://robinhood.com/us/en/support/articles/cortex/) · [新闻稿](https://robinhood.com/us/en/newsroom/robinhood-presents-yes-no-event/)：Stock/Portfolio Digest（对着**你的持仓**讲今天为什么动）；预填订单、提交仍要人点。Agentic Trading 是另一条产品，中国监管下不当卖点。

### 炼什么、不炼什么（已拍板，本单不许推翻）

| 巨头能力 | 本仓态度 |
|---|---|
| 可审计输出（方法 / 快照 / 出处 / 置信度） | **炼。** 本单 P0 |
| 对着「我的清单」说话，而不是全市场日报 | **炼。** 本单 P0 |
| Skill 按需加载、产出是工件不是气泡 | **炼形态。** 包是工件；不新开 50 个 SKILL.md |
| 许可边界跟着数据走 | **已有约束。** iFinD / 复盘会 / L2 不得当公开能力。本单不改部署模型 |
| KYC / UBO / DCM 路演 / 久期对冲 / 对公信贷 | **不炼** |
| ChatGPT 消费账本 / Plaid | **不炼** |
| FactSet / LSEG 当护城河 | **不炼供应商。** 本仓等价物是 DuckDB 四袋 + 知识库，数据必须带站立日和出处 |
| Agentic 自动下单 | **不炼** |
| 把「AI 荐股」当产品 | **不炼。** OpenAI 自己都写了不当投顾 |

本仓已经有同构零件，缺的是把它们焊成**可给人看的一页纸**：

- 全市场四袋：`intelligence/services/market_watch_pack.py` → `run_market_watch_pack`
- 画像自选：`intelligence/userspace.py` → `effective_profile`（`profile.json` 钉住 ⊕ `profile.derived.json`）
- 主张分级：Grounded 链 + `2026-08-17-claim-tiering-and-revision-design.md`
- 记忆/纠偏：`foresight-feedback`、`corrections.jsonl`（本单 P0 只读画像，不写记忆）

执行方若把「我们没有 Digest」写成「我们没有四袋 / 没有画像 / 没有主张分级」再去补一套，就是 CLAUDE.md「Agent 能力现状」要挡住的那类误判。

---

## 1. 术语（与 `UBIQUITOUS_LANGUAGE.md` 同步）

实施和公开稿只用这些词。

| 钦定词 | 含义 | 不要写成 |
|---|---|---|
| **自选简报包** `WatchlistDigestPack` | 站立日、用户清单、四袋委托收据、接合行、方法卡、主张档、缺口句组成的冻结对象 | 开盘 Digest、Cortex、50 skills、日报、晨汇 |
| **清单** | `effective_profile` 的 `watchlist` + `focus_themes`（钉住优先，派生未过期项并入） | 持仓、账户、StancePack 主键 |
| **方法卡** | 每条 fact 必须写明用了哪条已有口径（四袋哪一袋、`trade_date = ?`、主线∩双红对齐规则） | prompt 里的「请给出研究方法」 |
| **证据快照** | 包生成时刻冻住的袋行 + 清单 + 站立日；事后对账只对这份，不现场再查邻日 | 再跑一遍 SQL、把 DuckDB 整库拷走 |
| **主张档** | `fact`（袋内锁定数字）/ `inference`（接合解释，不得引入袋外数字）/ `gap`（清单项当日无命中） | 再发明 `claim_id=` 短式方言 |
| **残差** | 袋与袋冲突时模型可写的那几句；不能改口径、不能补数字 | 让模型重写整份简报 |

---

## 2. 已核实事实（实施时不要再探）

行号会漂，导航用符号名。核稿日**本机检出** `/Users/a77/finance-workspace-private` @ `main` `3df795cd`（#412），**落后** `gitea/main` `9a80547a`（#422 盲评重试）。开树必须 `git fetch gitea` 后从**当时的** `gitea/main` 建 worktree，禁止从本机落后的 `main` 起分支。符号名以新树代码为准，下面 1–10 条按核稿日已读文件，若新树漂移以符号不存在为准再探，不要整节重探。

1. `run_market_watch_pack(query, *, market_db_path, calendar_disclosure=None, cutoff=None, substitute_probes=False) -> MarketWatchPack`。四袋名：`market_daily` / `mainline` / `dual_red` / `limit_heat`。显式站立日 `trade_date = ?`，禁止 `<=` 回落邻日。`merge_into_public_answer` 已存在。
2. `DETERMINISTIC_OWNER_TYPES` 在 `continuous_turn_adapter.py`：`external_market` / `quick_fact` / `dated_market_review` / `market_watch` / `disclosure_scan`。进集合 → Engine A `_declined_result()`。盘面包的椅子是编排器 **owner 分叉之前**（`if owner_output is not None` 之前），不是 `handle()` 里。
3. `_MARKET_WATCH_RE` 要「今天/今日」+ 市场主语（市场/行情/盘面/大盘）+ 怎么样/看点/复盘等。冻结题「按我的自选出今天的简报」「我的自选今天怎么样」**不含市场主语**，今日不命中 `is_market_watch_query`。[推断] 仍必须加回归锁，防止以后放宽正则把自选题吞进全市场日报。
4. `route_table.market_watch`：`lane=workflow`，`needs_template=True`。本单新行必须同样是 workflow + template，否则会进 Engine A。
5. 画像：`userspace.effective_profile`。钉住 `watchlist` / `focus_themes` 是字符串列表；派生是 `{name: ...}` / `{theme: ...}`，`stale` 跳过。模板 `intelligence/users/profile.template.json`。默认用户走 `resolve_user_id`。**不要**自己 parse 画像。
6. StancePack 触发面是 `lane=research` 或 `question_type=trade_advice`，加持仓/买卖词面。简报题不得误触发 StancePack。
7. `foresight.py` 已把 watchlist 拼进一段 `digest` 字符串，然后让模型生成追问。那是问题生成器，**不是**本单工件。禁止把 foresight 的 `digest` 列表改名交差。
8. 飞书 IM 正门已退役（`feishu-bot` exit 2）。简报正门是 CLI + Workbench 问答门，不是 bot。
9. `services/` 禁止 import `runtime/`。包必须是纯函数，测试用临时 DuckDB（抄 `test_market_watch_component_first._db` 的夹具形状）。
10. 主树今日脏区含 `skills/daily-full-review/state/*` 与一份 inflight handoff。本单不得把运行产物提交进 feat 分支。

---

## 3. 范围

### 3.1 P0 做

1. 新模块 `intelligence/services/watchlist_digest_pack.py`：`run_watchlist_digest_pack(...) -> WatchlistDigestPack`。
2. 清单来自 `effective_profile`。watchlist 与 focus_themes 都空 → `status=empty`，公开稿只留缺口句，**不**回落到 `market_watch`。
3. 盘面袋**只许**调用 `run_market_watch_pack`。本模块零条新的双红/主线 SQL。
4. 接合：清单字符串对四袋行做名字包含对齐（复用 `market_watch_pack._names_match` 的包含规则，抽成共享函数或直接 import 现有函数；禁止第三套模糊匹配）。命中 → fact 行；未命中 → gap 行。inference 只允许写「清单项 X 出现在袋 Y」，禁止袋外数字。
5. 方法卡：包级一张（站立日、四袋委托、精确日查询、对齐规则）+ 每条 fact 一行（来自哪一袋、served_date、源行主键若有）。
6. 证据快照：`pack.to_snapshot()` 冻住站立日、user_id、清单、四袋 status/served_date/rows、接合行。CLI `--write` 或问答路径写入 `research_context`；瘦收据进 episode（只 status/缺口/行数，不把整袋抄进 git 台账）。
7. 公开稿由包填格，函数形状对齐 `merge_into_public_answer`。默认 `compose=False` 残差关。残差开时模型不得改数字、不得写买卖。
8. 新题型 `watchlist_digest`：
   - `is_watchlist_digest_query`
   - `route_table` 一行
   - 加入 `DETERMINISTIC_OWNER_TYPES`
   - 信封 / 评分链 / `decide_turn(llm=boom)` 三处一致，分类不得为了认题去调 LLM
9. CLI：`python3 -m intelligence.cli digest --date YYYY-MM-DD [--user <id>]`。只读。stdout 出 Markdown。`--write` 才落快照 JSON 到 `~/.finance-runtime/watchlist-digest/<user>/<date>/`（gitignore 运行时目录，不入库）。
10. 词表已在本稿 §1；仓词表同步见本提交对 `UBIQUITOUS_LANGUAGE.md` 的增补。

### 3.2 P0 不做

- 不抄 Google 50 skill、不接 FactSet/LSEG、不接 Plaid、不做 KYC/债券/久期。
- 不写「买入/卖出/加仓/减仓/现在做多」；动作句只许条件（「若跌破袋内数字则再问」），且 P0 默认连条件动作都不写——简报是观察件。
- 不改 `run_market_watch_pack` 的 SQL / 站立日语义。
- 不改 StancePack 触发面，不在简报路径跑 StancePack。
- 不改 foresight 追问生成。
- 不改 daily-review HTML、不改 agent-daily、不改夜跑 plist。
- 不接 L2 / ClickHouse（边车稿未过鉴权前置）。
- 不在 P0 调 `theme-fermentation-tracer`（P1）。
- 不新开 `skills/watchlist-digest/SKILL.md` 当主路径。主路径是 services 包 + CLI + 题型。若要 Claude Code 触发，P1 再加软链，且 description 必须指向本包，禁止第二份口径。
- 不做 Workbench 独立页面/按钮（问答门能走冻结题即 P0）。
- 不把简报题改路由成 `dated_market_review` / `market_watch` / `trade_advice` / `general_finance_qa`。
- 不在产品里做完整 ReAct。
- 不改 8792/8796/8802，不 force push，不提交 duckdb/密钥/运行产物。

### 3.3 P1 / P2（点头后再做，本单只钉形状）

- **P1**：`focus_themes` 命中主线或双红时，附加一条发酵摘要（委托 tracer 的纯函数入口；没有现成可 import 的函数就抽，不 shell 出子进程）。
- **P1**：Workbench 对话里把快照 ID 露成可点的证据页（只读渲染，不新开第三套 marker）。
- **P2**：夜跑在 daily-full 之后给默认用户写一份简报工件。没有设计合作伙伴用起来之前不要做。

---

## 4. 目标态

```
问句 / CLI --date
  → 解析站立日（显式日精确命中；隐式「今天」= cutoff 或库内 max(trade_date)，禁止邻日回落）
  → effective_profile(user) 得清单
  → run_market_watch_pack(...) 得四袋
  → join：清单 × 袋行
  → WatchlistDigestPack（方法卡 + 主张行 + 快照）
  → 公开稿 = 填格（数字只从 fact 行来）
  → 模型残差（可选，P0 默认关）
```

冻结题走问答门时：`question_type=watchlist_digest` ∈ `DETERMINISTIC_OWNER_TYPES` → Engine A 拒收 → 编排器 owner 分叉**之前**已经跑完包（与盘面包同一把椅子，**同一份对象**，禁止 compose 处再跑一遍）。

---

## 5. 路由

触发词面（无序合取）：**自选标记** ∧ **当日/简报标记**。

- 自选标记：`自选` / `我的清单` / `关注的票` / `watchlist` / `按我的自选`
- 当日/简报标记：`今天` / `今日` / `简报` / `开盘` / `该看什么`（「该看什么」必须同时有自选标记，否则会撞 foresight / market_watch）

优先级：自选标记存在时，`watchlist_digest` 压过 `market_watch` 与 `general_finance_qa`。没有自选标记 → 本包不跑。

负样本（必须仍是原题型，本单不得抢走）：

| 题 | 必须保持 |
|---|---|
| 今天市场怎么样 | `market_watch` |
| 今天有什么值得关注的 | `market_watch` |
| 复盘7月16日的A股市场 | `dated_market_review` |
| 宁德时代要不要止损 | `trade_advice` + StancePack |
| 基于上周的行情写一下本周展望 | `market_forecast` |
| 固态电池现在处于什么阶段 | 题材题，不是盘面、不是简报 |

正样本（必须是 `watchlist_digest`）：

- 按我的自选出今天的简报
- 我的自选今天怎么样
- 开盘简报（按自选）
- 我的清单今天该看什么

`decide_turn(llm_complete=boom)` 不得为认题调 LLM。

---

## 6. 工件形状

`WatchlistDigestPack` 最少字段（frozen dataclass）：

- `standing_date: str | None`
- `user_id: str`
- `status: Literal["locked", "empty", "locked_db"]` — 库打不开 = `locked_db`；清单空或四袋应停（休市/无该日）= `empty` 并带 `stop_text`
- `watchlist: tuple[str, ...]`
- `focus_themes: tuple[str, ...]`
- `tape: MarketWatchPack` — 委托对象，不重序列化第二份四袋口径
- `rows: tuple[DigestRow, ...]`
- `method_card: str` — 包级方法卡，固定口径句子，不是模型写的

`DigestRow`：

- `subject: str` — 清单项原文
- `kind: Literal["watchlist", "theme"]`
- `tier: Literal["fact", "inference", "gap"]`
- `bag: str | None` — fact 必填，gap 为空
- `served_date: str | None`
- `text: str` — 填格用的一句人话；fact 句中的数字必须能在 `tape.bags` 对应 rows 里逐字找到
- `source_row: dict[str, Any] | None` — 快照用

公开稿结构（顺序锁死，缺段用缺口句占位，不许跳过）：

1. 站立日 + 休市/无行情句（若 `tape.should_stop`，全文到此为止）
2. 方法卡
3. 清单命中（fact 行）
4. 清单未命中（gap 行）
5. 全市场上下文只允许引用 `tape` 的总量袋一行（成交/涨跌停/阶段），并标明「这是全市场袋，不是你的清单」
6. 主张档图例一句：fact = 袋内数字；inference = 接合；gap = 当日未见

禁止：把主线名单上「有某题材」写成「该题材当天在加量」（沿用盘面包 `mainline_dual_red_gap`）。

---

## 7. 主张分级（复用，不新开方言）

P0 公开稿是确定性填格，**不走 Grounded composer 的 HTML marker**。档写在 `DigestRow.tier`，渲染为可见前缀：

- fact → `（事实）`
- inference → `（推断）`
- gap → `（缺口）`

已取代证据降桶、`claim_id=` 短式修订轮，都不是本单的椅子。若 P1 把简报送进 Grounded 链，必须用现役 `claim_ids=` 复数方言，禁止本包再发明一套。

---

## 8. 实施步骤（按序，每步有完成判据）

开工前：

```bash
cd /Users/a77/finance-workspace-private
git status --short && git branch --show-current
# 从最新 gitea/main 开干净 worktree，不要在今日脏 main 上改 runtime
git fetch gitea
git worktree add -b feat/watchlist-digest-pack /Users/a77/fwp-wt-watchlist-digest gitea/main
```

完成判据：新树 `git status` 空，分支名 `feat/watchlist-digest-pack`，HEAD = 当时 `gitea/main`。

编码任务先 `python3 scripts/code_map.py query "watchlist digest pack market_watch_pack effective_profile DETERMINISTIC_OWNER_TYPES"`。空图不得写成架构结论。

| 步 | 做什么 | 完成判据 |
|---|---|---|
| 1 | 包纯函数 + dataclass + `to_snapshot` / `to_prompt_block` / `render_public_answer` | `intelligence/tests/test_watchlist_digest_pack.py` 先红后绿；夹具 DuckDB 不碰真库 |
| 2 | 路由：`is_watchlist_digest_query` + `route_table` 行 + `understand_query` 优先序 | 正样本四句三层（信封/plan/decide boom）都是 `watchlist_digest`；§5 负样本题型不变 |
| 3 | `watchlist_digest` 进 `DETERMINISTIC_OWNER_TYPES`；编排器 owner 分叉前跑包，收据进 `research_context` | 冻结题进 ContinuousTurnAdapter → `handled=False`；开口前 pack 收据存在 |
| 4 | CLI `digest` | `--date` 对夹具库能打出含方法卡和主张档的 Markdown；清单空 → 缺口句 exit 0（不是 crash） |
| 5 | 公开稿卫生 | 无买卖词；fact 数字都能在快照 rows 找到；休市日全文只有日历/无行情句 |
| 6 | 本机检查 | `.venv-workbench` ruff + 定向测试 + 全量 pytest；webapp 本单不改则不必 rebuild，但不要弄脏 frontend |
| 7 | 台账 | `docs/prediction-ledger.md` 已预注册的三行用实测填「怎么验」列；不得自行标 confirmed |

---

## 9. 验收

离线（必须，合 PR 前）：

1. 冻结题路由：`watchlist_digest`，`decide_turn(llm=boom)` 不调 LLM。
2. 负样本六句题型不被本单改写。
3. 夹具：自选含「甲板块」的别名，站立日双红袋有该板块行 → 公开稿 fact 行含袋内数字，前缀 `（事实）`，方法卡出现 `trade_date =` 或等价「精确日」口径。
4. 夹具：自选「乙」当日四袋无名匹配 → `（缺口）` 行仍在，不得编涨跌幅。
5. 清单全空 → 不跑成 `market_watch`；公开稿声明没有自选。
6. 显式休市日 / 库无该日 → 不回落邻日数字（对偶盘面包洞 2）。
7. 公开稿匹配买卖词面（`买入|卖出|加仓|减仓|现在做多|现在做空`）→ 测试红。
8. 变异：把 `run_market_watch_pack` 换成包内私有 SQL → 必须有测试红（可用 monkeypatch 断言调用次数 = 1）。
9. 变异：分类器去掉自选优先 → 「我的自选今天怎么样」若被写成 `market_watch` 则红。

Live（合 main 后、切 8792 前，执行方跑、不得自己 confirmed）：

- 真画像用户（`linxiaoqi5111` 或当前默认用户）+ 最近一个有四袋数据的交易日。
- CLI 与 Workbench 各一发冻结题。
- 收据：`~/.finance-runtime/watchlist-digest/<user>/<date>/` 快照 JSON 的 `standing_date` 与袋 `served_date` 一致；公开稿数字 ⊆ 快照。

---

## 10. 红线

- 合并前跑本机等价检查；带红不合。
- 不 force push。
- 覆盖不确定归属的脏文件前先问用户。
- 动 8792 前写回滚锚；本单 P0 **默认不切运行时**。
- 知识库大 JSON 走 `query_relations.py`，本单 P0 不读 relations。
- 不把运行时快照 JSON 提交进 git。

---

## 11. 台账（来源非标准四阶段分诊，预注册）

> **改号记录（2026-08-26 实施时）**：本稿预注册时用的 `R-20260826-01…03` 在落台账前
> 被当日其他 session 占用（market_snapshot 站立日 / 宽度袋 / workbench fd，前两者已
> confirmed），同日撞号与 `R-20260824-31` 同形，实施分支按台账下一空位改号为
> `R-20260826-05…07`。语义逐条对应不变。

| ID | fix_type | verification_prediction |
|---|---|---|
| `R-20260826-05` | `ROUTING_FIX` | 冻结题三层都是 `watchlist_digest`；§5 负样本题型不变；Engine A `handled=False` |
| `R-20260826-06` | `DATA_CONTRACT_FIX` | 开口前 pack 收据在；公开稿数字 ⊆ 快照；精确日、无邻日回落；清单空走缺口不走日报 |
| `R-20260826-07` | `HARNESS_FIX` | 四袋只委托一次 `run_market_watch_pack`；公开稿无买卖词；主张档三档可见 |

执行方不得把这三行标 `confirmed`。live 收据路径写回「怎么验」列即可。

---

## 12. Key Decisions

1. **一个包，不是 50 个 skill。** 巨头的 skill 目录是投行工作流；本仓要交付的是可审计的个性化观察件。拆成三个项目会再丢掉接合。
2. **确定性填格，模型当残差。** 与盘面包同一失败形状：Engine A 当第一执行者会空转。选 DETERMINISTIC + owner 分叉前跑包。
3. **委托四袋，不复制 SQL。** 第三套双红口径会漂。
4. **画像清单是主键，不是问句持仓。** StancePack 解决买卖题；简报在用户没说话时也要能出。空清单 fail closed。
5. **观察件，不是投顾。** 与 OpenAI Finances 的「不能行动」同形，且更严：P0 连条件下单句都不写。
6. **P0 不接 L2、不接发酵 tracer。** 没有鉴权收据和可 import 入口之前，挂上只会变成 shell 出来的第二运行时。

---

## 13. 给执行 agent 的开工口令

你在执行 `docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md`。

不要：再打开 Google/OpenAI 页面、不要新建 50 个 skill、不要改盘面 SQL、不要碰 8792、不要在脏 main 上改 runtime、不要把简报做成荐股。

要：干净树 `feat/watchlist-digest-pack`；包纯函数委托 `run_market_watch_pack`；清单走 `effective_profile`；冻结题开口前收据在；测试先红后绿；台账三行只填收据不自行结案。

做完后写交接：分支、SHA、测试收据路径、未做的 P1/P2、已知边界（空画像、库锁、休市）。
