# 设计：研究工具目录收口（一份 ToolSpec，循环只查表）

- 日期：2026-08-31
- 状态：Draft v3（只落本文 + `scripts/audit_tool_admission_branches.py`。未改 `intelligence/`，未切 8792）
- v2 修订（2026-08-31 质检）：§7 验收表重做——闸门从 `rg` 换成 AST（旧正则漏检 7 条里的 2 条）、修正两个错误路径、补「不许唤醒中央表文案」判据；§2 补两条容易记反的现状
- v3 修订（2026-08-31 复检）：**v2 的闸门挡不住本稿自己的 P0**——判据一锁死函数名 `build_episode_registry`，而 P0 第一步就是抽出 `assemble_episode_specs`，7 条 if 原样搬过去闸门立刻发绿；判据二只扫字面量 `ToolSpec(...)` 构造器，而「把三个 runner 塞进 `tools` 走 `default_registry`」这条最顺手的收法在那边完全沉默。现改为：判据一**按装配模块 + 预取白名单**（`catalog.py` 一出现就自动进射程），判据二**真跑 `build_episode_registry` 看装配产物**。另修 §0/§8 与 §2 口径不一致三处
- 来源：2026-08-31 会话（对照 Agent book ch4 / 马书「一张脸」→ 本仓痛点是目录没收口，不是循环不认表）
- 父稿 / 姊妹（本单不重做）：
  - `2026-08-15-agent-base-dsh-absorption-design.md`——生产主线留 Python；金融层继续拥有截止日 / 证据账本；**不上完整 Plugin Loader**
  - `2026-08-22-capability-switchboard-design.md`——开关板是**消融夹具**，生产路径永不 `import`；`information-cutoff` 不进可并排两本的开关
  - `2026-08-22-harness-seams-to-learn-design.md`——动态 Plugin Loader 禁止再造
  - `2026-08-30-optimized-orchestration-contract-design.md`——目标态只留包椅与一台 ReAct；本单只动研究循环的**工具目录**，不改出稿分流
  - `2026-08-30-coverage-without-number-ownership-design.md`——记忆/联想是开口必取，数字所有权不交还；本单不改预取清单
- 代码树纪律：从 `gitea/main` 开干净树再改 runtime。本稿允许落主树 untracked。**禁止**把目录收口做成运行时装包 / MCP 插座 / 开源 Skill 热挂。**禁止**把截止日做成生产可关的 flag。

## 0. 一句话

循环已经只认 `ResearchToolRegistry.authorized_specs()`。要收的不是心跳，是**一张脸的材料**：今天元数据、装配 if、题型授权、契约文案、真正怎么跑，散在四处。目标态是**一个工具交一份 `ToolSpec`，显式目录组装，合同只勾能力**。加工具不再改循环、不再加一条装配 if。

**判别变量**（P0 验收只锁这两条）：

1. `build_episode_registry` 里不再按工具名写 `if "<capability>" in allowed_capabilities:` 再手工 `tools[...] =` / `specs.append(ToolSpec(...))`。改成对**一份显式目录**做同一套「授权 + 准入谓词 → 收进注册表」。
2. 循环文件（`agent_episode` / `episode_tool_batch` / `episode_scope`）**不因本单新增按工具名的分支**。减工具仍只改合同授权。

人话：菜单已经印好了，别在后厨再抄一份菜单、炒菜时再手写「有芹菜才上桌」。每种菜一个抽屉，出门只交一份说明书；今晚开哪些菜，合同勾。炒勺只看说明书，不认某道菜的私房写法。

> ⚠️ 「合同勾」有两道菜是例外：`finance_query` 和 `evidence_search` **每题无条件恒开**，不由合同挑（§2）。别照这句人话去推它们的准入。

---

## 1. 术语：截止日不是个税，也不等于完整 PIT 库

问句里的「截止日」指本仓的 `InformationCutoff.as_of_date`：**这一趟问答允许用到的最晚一天**。晚于这一天的行情、新闻、wiki 页，不能当「当时已知」送进模型。

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **截止日 / `information_cutoff`** | 本集信息上界。来源三选一：`requested`（问句「站在 X 收盘」解析出来）、`runtime_default`（运行日 `today`）、`latest_available`（类型里有，默认装配走的是前两条） | 个人所得税（PIT）；库里最新交易日；模型自己报的「截至」 |
| **`latest_data_date`** | 盘面快照新鲜度，**提供方元数据**。测试锁死：它**不得**把 `information_cutoff` 截短（`test_information_cutoff.py`：`today=07-26` + `latest_data_date=07-24` → cutoff 仍是 07-26） | 截止日本身 |
| **`cutoff_resolver`** | 个别工具（今天是因果窗上的 `news_search` / `web_search`）可以再收紧。注册表执行时取 `min(任务截止日, 工具请求日)`，**只许收紧，不许放宽** | 工具自己把截止日改到今天 |
| **出门滤网** | `filter_future_dated`：`source_date` 晚于有效截止日的证据进 discarded，不进观察 | 靠模型自觉不写未来 |
| **PIT（point-in-time）** | 量化回测里「站在那天，库里当时能看见什么」（含修订回放、当时未修订财报）。与截止日**同族**（都是时点门、都防前视），**不是同一实现**。本仓做的是问句日上界 + 丢未来日期证据，不是完整 PIT 库 | 个税；「库永远只有最新修订」 |

区间题（「1 日至 5 日」）不把起点当截止日：窗口上界由因果工具自己解析（`requested_information_cutoff` 的注释，C7 实测过「cutoff 落成今天会把更晚盘面送进模型」）。

`finance_query` 的时间窗写在 `requested_time_range`，不是把 `requested_date` 当成「问句日」。结构化查询未授权历史窗口时直接不执行，不是查了没有。

**开关纪律（已有，本单只复述）：** 截止日是焊点。关了系统还能出稿，但安全变成可选——稿会用到不该知道的未来。消融夹具可以测「不传 as-of 会不会偷用今天」；生产路径不读开关板，也不能把截止日做成 `ASK_*` 可关项。

对外 / 面试只说「问句日截止、禁止未来数据」。对方先说 PIT 再对：同族、我们没做完整时点库。

---

## 2. 今天散在哪（收口前的正本）

循环侧已经对：**执行**走 `ResearchToolRegistry.execute` → `resolve` → 授权检查 → `cutoff_resolver`（可空）→ runner → 未来日期滤网。`EpisodeScope.allowed_tools()` 与 `authorized_specs(allowed_capabilities)` 同一条路。

散的是**登记**：

| 材料 | 今天在哪 | 加工具时要不要改 |
|---|---|---|
| 名字 / 能力 / 一句话 / `produces` | `research_tool_registry._DEFAULT_TOOL_METADATA` | 要 |
| 行为契约（何时用、怎样误读） | 同文件 `_TOOL_CONTRACTS` | 要（空串合法，编一句比不写糟） |
| 默认 runner 字典 | `agent_research.build_default_tools` + `build_graph_tools` | 要 |
| 「有能力才挂 runner」 | `episode_tools.build_episode_registry` 一串 `if "market_data" in allowed` … | 要 |
| 后挂的完整 `ToolSpec` | 同函数：`finance_query` / `evidence_search` / `memory_lookup` 再 `specs.append` | 要 |
| 题型 → 能力地板 | `evidence_capabilities._RUNTIME_CAPABILITY_FLOOR` + `episode_factory._authorized_capabilities` | **本单不收**。权威继续在合同派生函数，不抄进目录、不抄进 Profile |
| 身份 / 夹具准入 | `memory_lookup` 还要身份已解析；`web_search`/`news_search`/`l3_lookup` 认 `fixture_policy.external_search_enabled` | 变成该工具自己的准入谓词，不删 |
| 循环心跳 | `agent_episode` / `episode_tool_batch` | **不要改逻辑** |

所以「加一个工具改好几处」是真的；「循环按工具名分支」已经不是真的。不要把后者当缺口重做一遍。

**两条容易记反的现状（2026-08-31 质检实测，改稿前先按这个对表）：**

1. `finance_query` / `evidence_search` **不是按题型条件授权的，是每一题无条件并上**——`episode_factory._authorized_capabilities` 里 `_MODEL_OWNED_READ_CAPABILITIES = ("finance_query", "evidence_search")` 直接并进 `projected`，不看 frame。所以「今晚开哪些菜，合同勾」这句话对这两道菜不成立：它们恒开，builder 的能力轴准入对它们恒真。（`episode_factory.py:412` 那句「残差题」注释讲的是另一件事：残差题没有子 skill 菜单，只扩大 `allowed_capabilities` 不给契约槽。）
2. 后挂的三个 `ToolSpec` **都没传 `contract` 和 `produces`**，吃的是默认 `""` 和 `frozenset()`。而 `_TOOL_CONTRACTS` / `_DEFAULT_TOOL_METADATA` 里这三个都有真内容（`finance_query` 的 25 行截断契约、`evidence_search` 的三轮闭环说明、`memory_lookup` 的「先验不是证据」、以及 `{data_date,…}` / `{counterpoint,…}` / `{prime_memory}`）。因为 `default_registry` 用 `if name in tools` 过滤，这三个不走那条路，**那些文案今天是死的**。见 §5 P0 的红线。

`authorized_specs` 的消费方不止判别变量点名的三个，还有 `intelligence/runtime/openai_agents_runtime.py`、`intelligence/runtime/headless_tool_gateway.py`、`intelligence/runtime/continuous_turn_adapter.py`。最后一个是鸭子类型 + `getattr` fail-open：registry 换形状它静默返回 `()` 不报错。收口时它不会转红，别把「没转红」当成「它还好」。

现籍 12 个能力名（`DEFAULT_RESEARCH_CAPABILITIES`，能力名今天等于工具名）：`finance_query`、`evidence_search`、`kb_search`、`web_search`、`news_search`、`graph_lookup`、`evidence_lookup`、`memory_lookup`、`l3_lookup`、`market_data`、`financial_data`、`mainline_context`。本单不增第 13 个，除非另立需求。

---

## 3. 目标形状

### 3.1 一张脸

继续用现有 `ToolSpec`，不新发明第二套接口。一份合同至少带：

- `name` / `capability` / `description` / `contract`
- `parameters` / `parse_arguments`
- `runner`（只读；副作用只能是本机已授权的检索，见 §6）
- `query_scope` / `cost` / `freshness` / `produces`
- 可选 `cutoff_resolver`（只许收紧）
- **准入谓词**（新，本单补）：`admit(frame, context, deps) -> bool`。身份未解析、夹具关外呼、能力未授权，都在这里否决。否决 = 目录里根本没有这行，模型看不见。

循环继续只认 `authorized_specs`。马书那句落到本仓：先全登记进目录，再按本集合同过滤；不是运行时扫盘发现新包。

### 3.2 一工具一模块，目录是显式名单

建议落点（实施时名字可微调，原则不许改）：

```text
intelligence/services/research_tools/
  catalog.py          # CATALOG: 显式 tuple[ToolBuilder, ...]
  <tool_name>.py      # 只交 build_spec(deps) -> ToolSpec | None
```

`catalog.py` **手写 import + 元组**。禁止 `pkgutil.walk_packages` / 扫目录热发现 / 读外部 JSON 装 runner。那是 Plugin Loader，父稿已禁。

`build_episode_registry` 收成：准备 deps（库路径、wiki、身份、夹具、截止日、因果窗）→ 对 `CATALOG` 逐个 `build_spec` → `None` 跳过 → `ResearchToolRegistry(tuple(specs), opening_prefetch=...)`。

题型合同**只勾能力**，不写工具类名、不写模块路径。未知能力继续 `unknown runtime capability` fail-closed（`episode_factory._authorized_capabilities`）。

### 3.3 加工具（目标态）

1. 新模块交一份 `ToolSpec`（含 runner、契约、`produces`、准入）。
2. `CATALOG` 元组加一行。
3. 若新能力：写入 `DEFAULT_RESEARCH_CAPABILITIES` 的派生源（跟目录走，禁止第三份手抄名单）+ 在对应 evidence policy 勾上。
4. 测试：授权可见、未授权硬调被拒、未来日期进不了观察、只读（见 §6）。

不再改循环，不再在 `build_episode_registry` 加一条 if。

---

## 4. 非目标（写死认领）

| 冒出来的「顺手」 | 去处 |
|---|---|
| 上 MCP / 进程外插座 | ❌ 规模未到；父稿明确进程内注册表 |
| 动态装开源 Skill / 运行时 pip | ❌ Skill 在本仓是路由后跑的 Python，不是给研究模型的 SKILL.md；技能桥继续只开 `serenity-alpha` |
| 完整 Plugin Loader / Cordis | ❌ `2026-08-15` / `2026-08-22` |
| 把工具名单抄进 `ResearchProfile` | ❌ 权威在 contract 派生函数，再抄会漂（开关板 §5.3） |
| 生产路径读 `capability_switchboard` | ❌ 夹具不是 flag；测试已钉 serving 不得 import |
| 把截止日做成可关 | ❌ 焊点，见 §1 |
| 把 12 个 runner 揉进一个文件 | ❌ 收的是合同，不是巨型模块 |
| 改包椅 / 卸 B 循环 / 开口预取清单 | ❌ 姊妹单 |
| 数字交还模型「自己搜」 | ❌ 覆盖单红线 |
| 热插：流量还在时换工具实现 | ❌ JD 那句话不是本单；本单是**发版改目录**。最像热的是渠道熔断，不在这里 |

---

## 5. 分阶段

**P0（本单若开工，先做这个）——目录收成一处，模块可以暂不搬家。**

- 抽出 `assemble_episode_specs(deps, allowed) -> tuple[ToolSpec, ...]`，对显式名单循环。
- `build_episode_registry` 只负责 deps + opening prefetch，不再手写 12 条 if。
- `_DEFAULT_TOOL_METADATA` / `_TOOL_CONTRACTS` 可以暂时仍住在 registry 文件，但**只被各 builder 读取**，装配函数不再二次抄。
- **⛔ P0 不许唤醒中央表文案。** 「各 builder 去读中央表」最自然的写法，会让 `finance_query` / `evidence_search` / `memory_lookup` 突然拿到 `contract` 与 `produces`——而 `contract` 直接拼进模型看见的工具描述（`research_tool_registry.py` 的 `f"{spec.description}\n{spec.contract}"`），`produces` 会把这三个拉进 `check_satisfiability` 的 `declared_specs`。**那是行为变更，不是搬家。** P0 里这三个 spec 的 `contract`/`produces` 必须保持今天的空值；要接上另立一单、带 A/B。判据二的闸门钉的就是这条。
- 回归：现有 `test_information_cutoff` / `test_honesty_gates` / 工具授权测试全绿；循环文件 diff 为空或仅 import。**注意这四样都看不见提示词文案变化**——上一条只能靠闸门守，不能靠回归绿灯守。

**P1——物理搬家。** 每个工具一个模块；registry 文件留下 `ToolSpec` 类型、`execute`、`check_satisfiability`。`default_registry(tools: dict)` 若还被测试当夹具，改成「从目录取元数据 + 注入假 runner」，不要维持第二套装配。

**P2 不立。** 没有「目录收完再上热加载」的下一档。

---

## 6. 红线（工具本身，不随收口放松）

- **只读。** 研究工具不准写库、不准发飞书、不准改用户台账。写侧继续走工作台纠偏 / 包，不进 ReAct 菜单。
- **无外呼默认关。** `web_search` / `news_search` / `l3_lookup` 继续认夹具与授权；不是目录收口就默认上网。
- **技能桥不扩。** `skill_tools` 30 个技能只桥 `serenity-alpha`（只读本地 wiki）。其余会拉复盘会 / iFinD 或写外部系统——**不准**因为「也是工具」就挂进研究目录。
- **身份。** `memory_lookup` 缺 `user` / `users_root` 就不注册。禁止回落到 default 用户私有台账。
- **截止日。** 任务截止日必有；工具 resolver 只收紧；未来日期滤网必跑。消融「不传 as-of」只许在开关板独立树，不许进生产默认。
- **git。** pathspec 提交；不合 main；不强推；预注册台账号走 `python3 scripts/claim_ledger_id.py claim --branch <分支>`，禁止手工 max+1。

---

## 7. 验收（机器可判）

P0 合并前：

- [ ] **装配区收口 + 中央表未被唤醒**：`.venv-workbench/bin/python scripts/audit_tool_admission_branches.py` 退 0。
      收口前基线是**判据一 7 条、判据二 0 条**（`gitea/main@19c77a16` / 8792 在跑的 `5be00c4f` / 主树三处一致，2026-08-31 实测）。
      改闸门本身要先跑 `--self-test`（用例数由脚本自报，不写死在这里——写死就是又造一个会漂的数）。

      **退码含义**（页脚每次打印真实 verdict + 理由，以页脚为准）：

      | 判据一 | 判据二 | 退码 |
      |---|---|---|
      | 红 | 跑了 / 没跑 | **1**（判据一红优先，不因为判据二没跑就变 2） |
      | 绿 | 偏离 | **1** |
      | 绿 | **没跑** | **2** — 未执行 ≠ 通过 |
      | 绿 | 绿 | 0 |

      `--static-only` / `--rev` 只是让判据二不执行，**不是恒退 2**：判据一仍红时退的是 1。判据二靠 import 跑真实装配，只对工作树成立，所以 `--rev` 会自动降级。
- [ ] **闸门挂哪（2026-08-31 定）**：合并前 / CI 跑**完整模式**，退 0 才能合。pre-commit 可挂但必须写死 `.venv-workbench/bin/python`——用系统 `python3` 会走到判据二 fail closed 退 2，容易被读成「环境没配好，跳过」。`--static-only` 只给看历史树用，任何情况下不算过关。
- [ ] `rg 'spec\.name ==' intelligence/runtime/agent_episode.py intelligence/runtime/episode_tool_batch.py intelligence/services/episode_scope.py` 不因本单新增分支（存量字符串若是日志字段，保持）。
      ⚠ 这两个文件在 `runtime/` 不在 `services/`——写错路径 `rg` 退 2、stdout 为空，会被读成「0 处新增分支」发假绿。脚本里务必检查退出码。
- [ ] 新增夹具工具（测试内假 runner）能被 `authorized_specs` 看见，且不改循环。
      **走哪条路要写死**：经 `episode_factory` 的话，任何不在 `DEFAULT_RESEARCH_CAPABILITIES`（派生自 `_DEFAULT_TOOL_METADATA`）里的能力名会撞 `unknown runtime capability` 直接抛——所以「只加假模块不碰中央表」在这条路上做不到。要么测试直接构造 `ResearchContract` 绕开 factory，要么承认夹具工具也得进中央表。二选一，别留给实施方各自解释。
- [ ] 未授权硬调仍抛现有 `UnknownResearchTool` 文案（错误契约不混在本单改）。
- [ ] `test_information_cutoff.py`：未来证据不进观察；`latest_data_date` 不截短 cutoff。
- [ ] serving / 生产 import 图仍然不得出现 `capability_switchboard`。
- [ ] 未切 8792、未改包椅出稿路径。
      **8792 有没有被切，看进程启动时间不看目录 mtime**：属主是 launchd，切指针必须重启，`ps -o lstart= -p $(lsof -tiTCP:8792 -sTCP:LISTEN)` 早于本单开工即为未切。那个目录里的历史 cutover 收据会被别的作业 touch 出今天的 mtime。

> **闸门为什么不锁函数名。** v2 的判据一钉在 `build_episode_registry` 上，
> 而 P0 第一步明文是抽出 `assemble_episode_specs`——把那 7 条 if 原样搬进新函数，
> 闸门立刻报 0 退 0，**活还在，验收先绿**。锁函数名等于给稿子规定的第一步开后门。
> 判据现在按**模块 + 白名单**：装配模块里字面量 `in`/`not in` 授权表一律计数，
> 只赦免显式白名单里的预取函数（今天就一个 `_should_attach_overnight_news`，每次运行都打印）。
> 搬到哪个函数、哪个新模块都躲不掉；`research_tools/` 下的 `catalog.py` 一出现就自动进射程。
>
> **判据二为什么看装配产物。** 只扫字面量 `ToolSpec(...)` 构造器的话，
> 「把三个 runner 塞进 `tools` 再走 `default_registry`」这条最顺手的收法会让中央表文案醒，
> 而构造发生在 `research_tool_registry.py`，扫构造器那边什么也看不见。
> 所以判据二真跑一次 `build_episode_registry`（沿用 `scripts/audit_tool_reachability.py`
> 那套不碰 DB 的探针题面），拿装配出来的 spec 看字段。AST 扫构造器降级为辅助信号。
>
> **闸门为什么不是 `rg`。** 初版第一条写的是
> `rg 'if "[a-z_]+" in context.contract.allowed_capabilities' …`，实测只看得见 7 条准入里的 5 条：
> `[a-z_]+` 不含数字，`l3_lookup` 带个 `3` **即使写成它瞄准的那个单行 if 也匹配不上**；
> 同行 `if "` 锚点又看不见多行 `if (` 形式（`memory_lookup`）。
> 变异测试里留着这两条分支，闸门照样报 0。
> 正则匹配的是文本形状，而重构改的恰恰是文本形状——**「某个语法结构必须消失」的验收一律走 AST**。
> 这条可迁移到任何「重构后 X 不许再出现」的门禁。

---

## 8. 证据路径（实施先读，禁止臆测）

| 文件 | 看什么 |
|---|---|
| `intelligence/services/research_tool_registry.py` | `ToolSpec`、`execute` 里 cutoff 只收紧、未来日期滤网、`default_registry`、`_DEFAULT_TOOL_METADATA` |
| `intelligence/services/episode_tools.py` | `build_episode_registry` 双段装配（先 dict+`default_registry`，再 append 三个 ToolSpec） |
| `intelligence/services/agent_research.py` | `build_default_tools` / `build_graph_tools` |
| `intelligence/services/episode_factory.py` | `_authorized_capabilities`；`_MODEL_OWNED_READ_CAPABILITIES` **每题无条件**并上 `finance_query`/`evidence_search`（不是残差题才并，见 §2） |
| `intelligence/services/evidence_capabilities.py` | `_RUNTIME_CAPABILITY_FLOOR`（题型授权正本，本单只读） |
| `intelligence/services/research_contract.py` | `InformationCutoff` |
| `intelligence/services/honesty_gates.py` | `requested_information_cutoff`（站立日；区间题不走） |
| `intelligence/tests/test_information_cutoff.py` | 快照日 ≠ 截止日；未来证据滤网 |
| `intelligence/runtime/agent_episode.py` / `episode_tool_batch.py` | 循环心跳（**在 `runtime/` 不在 `services/`**） |
| `scripts/audit_tool_admission_branches.py` | 本单 P0 的机器可判闸门；先 `--self-test` 再信它 |
| `docs/superpowers/specs/2026-08-22-capability-switchboard-design.md` §5.2 | 截止日不进可并排开关 |

实施另开 `docs/superpowers/plans/` 或工单；本稿不是施工清单。落地前先 `claim_ledger_id`，分支从 `gitea/main` 干净树开。
