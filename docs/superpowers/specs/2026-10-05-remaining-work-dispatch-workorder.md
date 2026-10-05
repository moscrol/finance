# 2026-10-05 剩余工作分发规格（母单）

> **可独立分发。** 执行方无需读聊天记录：本单自带背景、证据路径、步骤、验收与红线。
> 每个工作包（WP）可以单独派给一个 agent，各开各的分支，除标明的依赖外可并行。
> 状态的真本源是任务板 `FINANCEWORKS-N`（`taskctl issue get FINANCEWORKS-N`）。
> 总目标与总验收仍以 [10-03 总规格](2026-10-03-harness-quality-closeout-spec.md) 为准，本单只写 10-05 之后还剩什么、怎么做、怎么验。

## 0. 怎么用

1. **认领**：先读 `taskctl issue get FINANCEWORKS-N` 和它最新的评论。如果已有会话 in_progress 且 24 小时内有评论，不要重复做，在评论里协调。认领时发一条评论：
   `taskctl comment add FINANCEWORKS-N --body "认领：<会话/分支>" --thread-id <你的会话标识>`。
2. **验鲜**：本单事实截至 2026-10-05 16:45（Asia/Taipei）。开工前先跑 §1 末尾的复核命令。与本单不符时以实测为准，并把差异写进任务板评论。
3. **收尾**：每个 WP 完成后，在任务板评论里写结论、原件路径和限制，再把状态改成 in_review。done 由验收方或用户改。分支收尾用 `handoff` skill 写交接。

## 1. 事实快照（10-05 16:45）

- **版本**：main `09f53a731`；线上 8792 `765ecbac9ad3`（#47），与 main 的代码一致，health=healthy，ready 13/13。
- **开放 PR**：只有 #30（Draft，见 WP-4）。
- **任务板**：

  | 状态 | 编号 |
  |---|---|
  | done | 2、3 |
  | in_review | 4、8、10、13 |
  | in_progress | 1（父任务）、5、6 |
  | todo | 9、14、15、16 |
  | backlog | 7、11、12 |

- **工作树**：29 棵（11:05 看板），每棵的去向见 [10-05 收尾快照](../../handoffs/2026-10-05-delegated-merge-and-tree-closeout.md)。
- **在途工作，不要重复派**（见 §6）：
  - `worktree_safety` 前缀误报修复；
  - 8792 vs Pi 对照线。
- **交易日历**：A 股 10-01 至 10-07 休市，10-08 是节后首个交易日。

复核命令：

```bash
git fetch origin && git log --oneline -3 origin/main
curl -s http://127.0.0.1:8792/api/health | python3 -c "import json,sys; print(json.load(sys.stdin)['runtime']['source_revision'])"
gh pr list --repo moscrol/finance --state open
taskctl issue list
.venv-workbench/bin/python scripts/worktree_board.py
```

沙箱可能拦截回环地址（127.0.0.1）；读不到 health 时说明原因，不要猜。

## 2. 全局红线（摘自 AGENTS.md，不另发明）

- **开工三连**：`git worktree list && git status --short && git branch --show-current`。
  - 看到不属于你的改动，就另开工作树：`git worktree add ~/fwp-wt-<slug> -b <type>/<slug> origin/main`。
  - 新工作树用主检出的解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；pytest 和 ruff 一律用它，宿主 `python3` 缺依赖。
- **提交**：只用 pathspec（`git add -- <文件>`，`git commit -F <消息文件> -- <文件>`）。禁止 `git add -A` / `git add .`。不提交 `.env*`、`*.duckdb|db|pdf|zip` 和凭证。
- **合入与 CI**：
  - 合并 main 必须由用户确认，或有用户明确的委托。不强推。
  - 合入前 GitHub 五项检查（python / frontend / e2e / registry-check / workbench-check）全绿，并在本机按改动范围跑等价检查。
  - 当作全量收据用之前，先用 `scripts/check_test_receipt.py <收据> --require-full-scope` 自证收集面。
- **部署 8792**：必须由用户拍板，任何 WP 都不自带部署授权。部署照例走切链五步和切后三验（health、readiness、业务探针），并留好回滚点。
- **台账取号**：`python3 scripts/claim_ledger_id.py claim --branch <分支>`，不手工取"当日 max+1"。号不回收。
- **真实模型调用**：
  - 先过 §4 第 1 条（通道与预算）；批前用同一载荷先探一发网关。
  - 每次调用都记 requested 和 served 模型。
  - 失败计入分母，不补跑挑优。n=1 不写趋势。
- **数据**：
  - 历史日不跑 `daily-full`，回补走 `skills/duckdb-backfill`。
  - fupanhui 停采期间只用 `--plan local`。
  - 不往 VIEW 写，不手写 SQL 改生产库。
  - 只读查库用 `read_only=True`；遇到写连接占用就等，不要抢。
- **不碰的东西**：别人的活动树、生产当前快照、回滚树、主检出的未提交改动（WP-12 另有程序）。
- **关闭 PR** 必须留接替指针或废弃理由。
- **zsh 坑**：
  - 变量里装多个参数时，用数组或 `xargs` 传；zsh 不会自动拆分。
  - 变量后面紧跟冒号要写成 `${var}:`，否则 `:t`、`:s` 会被当成修饰符。

## 3. 优先级与依赖

| 档 | 工作包 | 依赖 / 并行 |
|---|---|---|
| P0 | WP-5 身份与路由取证；WP-3a 断连分类；WP-1 对照 v6 | WP-1 依赖 WP-5（或在报告里写明身份口径）和 §4-1；WP-5、WP-3a 可并行 |
| P0 | WP-12a 回收被误报挡住的树 | 依赖 §6 的误报修复合入 |
| P1 | WP-2 内容质量门 | 任何影响回答的部署之前必须过它；依赖 §4-1 |
| P1 | WP-3b 至 3e 内容缺陷；WP-4 PR #30 去留 | WP-4 依赖 WP-1 的结论 |
| P1 | WP-7 记忆；WP-10 数据；WP-13 会话注入 | 互相独立；WP-10 的验收在 10-08 夜跑之后 |
| P2 | WP-6 工具面 | 等 WP-1 和 WP-3 的方向定了再动 |
| P2 | WP-8 台账；WP-11 Knevo；WP-9 技术债；WP-12b 至 12f | WP-11 依赖 WP-2 |

## 4. 需要用户拍板（agent 不得自行决定）

1. **真实模型调用的通道与预算上限**：用套餐/网关账号池，还是标准 API 现金；每个实验的请求数和 token 上限。WP-1、2、3 的配对实验都以此为前提。
2. **是否补一个同版本的强模型臂**。这是审计"模型还是 harness"的另一半。目前只引用 08-27 的 react 臂，版本和数据快照都不同。
3. **PR #30 的去留**：由 WP-4 提供证据和建议。
4. **每次合入 main 和每次部署。**
5. **主检出未提交改动的认领与同步**（WP-12b）：其中包含夜跑在用的运营叠层。

## 5. 工作包

### WP-1 同模型 harness 对照 v6（FINANCEWORKS-5，P0）

**背景**：用户 10-04 把 2×2 收窄为"同一个 GLM-5.3-Flash 在 Pi ReAct 与生产 8792 上表现有何差异"。

- v5（D1–D10 × 2 臂 × 1 次）的独立盲评按冻结规则判为"不确定"：
  - 可用率：8792 3/10，Pi 5/10；
  - 配对：Pi 胜 4、平 6，没到 6 胜的门槛。
- 主因是样本损失：10-05 00:03–00:18 两臂的模型调用全部断连，D1–D4、D9 两边都没有答案。
- 方向性假设（n 小）：8792 的不可用和 partial 全部出在代码替模型做决定的地方：
  - ask 固定流程 0/3；
  - 实体查无就短路（D7）；
  - 断连被写成"证据不足"并记为 partial（D2，因此没被重试）。
- v5 的 8792 臂跑在 `bd2c58b`，之后 #44–#47 已经上线，旧读数不代表现网。

**目标**：
1. 在现网版本上完成一轮样本足够、传输稳定的对照。开跑时实测 SHA 并冻结。按冻结的规则给出结论。
2. 两臂每次调用都有正向身份（requested = served = glm-5.3-flash）。任何一题证明不了，就移出主指标单列。
3. 做独立的匿名全文盲评，评审者与执行者隔离。报告写进 `docs/verification/`，并回写任务板。

**非目标**：
- ❌ 改 8792 产品代码：发现的缺陷交给 WP-3。
- ❌ 加强模型臂：等 §4-2 拍板。
- ❌ 把 v5 或更早的读数并入新统计。arena 参考臂和 #38 不纳入（用户 10-04 决定）。
- ❌ 失败补跑挑优；断连只按预注册的重试规则处理。

**证据路径**：

| 文件 | 看什么 |
|---|---|
| `docs/superpowers/specs/2026-09-30-model-harness-2x2-preregistration.md` | 预注册，以及 10-04、10-05 修订（G 列冻结、v5 规则） |
| `~/.finance-runtime/harness-arms-20261004/` | v4/v5 原件；`blind-review-v5/REPORT.md`、`FROZEN.sha256` |
| 任务板 FINANCEWORKS-5 的评论（10-05 11:04） | v5 结论。身份口径：成功调用的账本里 requested = reported；`attempts.jsonl` 的 `config_only` 低估了它；`report.json` 的 `gate_receipt.engine` 恒为 episode，判路由要看 trace |
| `docs/handoffs/2026-10-04-deploy-post40-and-harness-arms-smoke.md` | Pi 臂的接线与 G 列冒烟 |
| `intelligence/eval/thin_react.py` | 仓内的薄循环 R 臂（测量仪器，不是 Pi） |

**步骤与验收**：
- [ ] 读 FINANCEWORKS-5 的最新评论。如果 v6 已在跑或已冻结，改为协助，不另起一轮；开跑前在评论里声明占用，因为同一目录同一时段只能有一个会话跑对照（10-05 01:15 出过并发撞车）。
- [ ] 身份：WP-5 已合入就用它的字段；否则按 v5 的口径从账本取正向身份，并在报告里写明口径。
- [ ] 批前探网关。传输失败记为 `transport_failure`，按预注册重试一次，不记为 partial。
- [ ] 取号，然后冻结 v6：题集、每臂次数、乱序种子、预算上限（§4-1）、停止规则、判定阈值。冻结文件的哈希写进任务板。
- [ ] 运行。任何身份不符立即停。
- [ ] 盲评、揭盲，按冻结规则给出结论（胜、负或不确定），附可比对数和样本损失原因。
- [ ] 回写：任务板评论；`docs/verification/<日期>-harness-arms-v6.md`；预注册文档的结果节（不改冻结段）。

### WP-2 内容质量门：留出集第一次使用（FINANCEWORKS-4，P1）

**背景**：PR #31 冻结了一个留出集（10 道单轮 + 2 道多轮，48 个字段哈希），至今一次没用过。10-04 #40 部署的放行项里没有内容质量这一项。审计的核心问题"内容对不对"至今没有固定的量尺。

**目标**：
1. 验收并关闭 FINANCEWORKS-4：核对哈希、题型覆盖，以及调参题与只评测题是否分开。
2. 把"发布前内容质量门"写成可重复执行的规程或脚本：对影响回答的候选做新旧版本的同模型配对、匿名全文评分，并设金融硬错误门（来源、对象、日期、单位、算术、财务口径），各类单列。
3. 在现网版本上跑第一次基线读数，作为之后所有候选的对照。

**非目标**：
- ❌ 用留出题调参。一旦用来修，它就降级为回归题，新留出集按 WP-11 的规则另立。
- ❌ 用结构合规率、completed 或测试数代替内容正确性。
- ❌ 接进自动部署流水线：先把规程立起来，自动化另立工单。

**证据路径**：

| 文件 | 看什么 |
|---|---|
| `intelligence/eval/fixtures/harness_quality_holdout_20261004.json` | 冻结的题目与真值 |
| `docs/verification/2026-10-04-harness-content-holdout.md` 与 `-receipt.json` | 冻结方式与哈希 |
| `tests/test_harness_quality_holdout_fixture.py` | 结构与哈希守卫 |
| 10-03 总规格的总验收第 1–3 条 | 主指标、最小效应、硬错误门的口径 |
| 任务板 FINANCEWORKS-6 的评论 | 旧基线审读：news 0/8、transmission 0/8、financial 6 可用 / 2 部分 |

**步骤与验收**：
- [ ] FINANCEWORKS-4 的验收清单逐项核对并评论，然后交用户或验收方关闭。
- [ ] 规程写进 `docs/workflows/content-quality-gate.md`，配套脚本可选。输入两个 SHA、同一模型、同样的预算；输出配对表、主指标和硬错误清单；失败计入分母。
- [ ] 阳性对照：挑一个在某类题上已知更差的旧版本（例如 #40 之前的 `04799bc6` 对材料题），证明这道门能测出差异。
- [ ] 现网基线跑一次（需要 §4-1 的预算），结果写进 `docs/verification/<日期>-content-gate-baseline.md`。

### WP-3 内容缺陷修复：先修"代码替模型做决定"（FINANCEWORKS-6，P0/P1）

**背景**：
- 见 WP-1 背景里 v5 的方向性发现。
- 现网的 D6 日期题曾经出错：检索到的日期是 07-22，答案却把 09-30 的数字当成"当日"写出，"数据截至"提示也消失了。#47 已把精确日绑定接到 episode 入口，并已上线到 `765ecbac`，需要复测。
- arena 的 #38（把金融不变量常驻进提示）已经关闭，理由是没有验证、规则常驻、两个因素同时改。
- #40（材料 claim 切句）已上线，但只有一次（n=1）的前后对照。

**目标**：每个子项单独一个单因素 PR，先定位首错再改。
- **3a 断连分类（P0）**：模型调用的传输失败（urlerror、Connection error）不得写成"证据不足"并记为 partial。应该标为 `transport_failure`，可以重试；交付时如实说明模型暂不可用。
- **3b ask 固定流程**：先量清楚哪些题型进了固定流程（引擎 B）、各自的可用率。v5 里失败的题型改由 episode 处理，或者让固定流程把决定交回给模型。以 trace 上的首错为准。
- **3c 实体查无短路**：查无时不要直接用澄清代替回答（D7）。把"查无"作为模型能看到的事实交给模型，由它决定怎么答。
- **3d 复测**：在现网版本上复测 D6 等日期题。仍然出错就做首错定位。
- **3e #40 配对验证**：GLM 同模型新旧配对，用未调参的题，先做预注册。

**非目标**：
- ❌ 新增常驻提示规则或关键词规则：#38 的教训；正则路由的 245 处棘轮只许减不许增。
- ❌ 一个 PR 同时改作者和判官，或同时改两个因素。
- ❌ 用留出集调参。
- ❌ 改对照设计或 Pi 臂（属于 WP-1）。

**证据路径**：

| 文件 | 看什么 |
|---|---|
| FINANCEWORKS-5 的评论（10-05 11:04）与 `~/.finance-runtime/harness-arms-20261004/blind-review-v5/REPORT.md` | 三类失败分别对应哪些题号和 trace |
| PR #44–#47 的正文与提交 | 已经做过的去约束修复，避免重复 |
| `intelligence/services/ask.py`（`_answer_query_impl`）、`question_router.py`、`route_table.py` | 固定流程的入口与分流 |
| `intelligence/runtime/conversation_orchestrator.py`、`continuous_turn_adapter.py` | episode 路径 |
| `docs/verification/2026-10-04-material-claim-sentence-split.md` | #40 的离线重放基线 |
| `~/.finance-runtime/harness-quality-closeout-1003/task6-paired-20261004/preregistration.json` | arena 冻结过的配对方案，设计可复用，但身份要换成现网 SHA |

**步骤与验收**：
- [ ] 每个子项都走：首错定位（落到 trace 的具体步骤）→ 红测试 → 最小修复 → 绿 → 用 `scripts/mutation_check.py` 做变异，证明新测试承重 → 本机全量门禁收据 → 开 PR。
- [ ] 每个子项开工前先取号登记预测，写清"改完应该看到什么"。
- [ ] 3a 验收：在注入传输失败的测试里，交付结果是 `transport_failure` 加可重试，不再是 partial 的"证据不足"；用 v5 的 D2 trace 复放验证。
- [ ] 3b、3c 验收：v5 的失败题在离线重放或 n≥3 的实跑里首错消失；其余题过 WP-2 的门，不退化。

### WP-4 PR #30 去留（FINANCEWORKS-14，P1，依赖 WP-1）

**背景**：
- PR #30 是 Pi 做的四片改动，把几项决定交还给模型：PLAN 归属、根请求和目标解释、输出义务来源、可选表达。
- 工程验收已完成（`51b66d52`：20639 passed，51+24 个变异，双轴静态复审，CI 五项全绿；FINANCEWORKS-3 done），真实回答质量 0 验证。
- main 已合入并上线 #40、#44、#47，和 PR #30 有 5 个文件交叠：

  | 文件 | 被谁改过 |
  |---|---|
  | `intelligence/services/episode_protocol.py` | #40 |
  | `intelligence/runtime/continuous_turn_adapter.py` | #44 |
  | `intelligence/runtime/conversation_orchestrator.py` | #44、#47 |
  | `intelligence/services/task_frame.py` | #44 |
  | `intelligence/tests/test_continuous_turn_adapter.py` | #44 |

  `51b66d52` 的收据管不到新的组合。
- v5 的方向（失败出在代码替模型做决定的地方）和 PR #30 的方向一致，但还没验证过。

**目标**：
1. 写一份决策备忘（不超过一页）：重新合成的冲突面和工作量、与 #44–#47 的语义交叠或冲突、质量验收的方案与成本、直接关闭的代价，最后给出推荐。
2. 按用户的拍板执行：
   - **重新合成**：从最新 main 开新分支，合入 PR #30 的内容，按意图逐块解冲突（用 `resolving-merge-conflicts` skill），重跑全量门禁、变异和双轴复审，再按 WP-2 的门做同模型配对。开新 PR 接替 #30，#30 留指针关闭。
   - **关闭**：#30 留接替指针和理由后关闭，分支、证据根和归档钉全部保留。
3. 附带评估 `fix/owner-output-contract-1002` 的 `4cba44a63`（在 owner 执行前编译重复的 direct-output 身份，+326 行）是否已被 PR #30 的 `output_requirement` 取代，结论写进备忘。

**非目标**：
- ❌ 在 Pi 的活动树 `~/fwp-wt-harness-integration-1003` 上动手：另开树。
- ❌ 扩大 PR #30 的范围：剩余的 P1b 不在内。
- ❌ 用 `51b66d52` 的收据为新组合背书。

**证据路径**：

| 文件 | 看什么 |
|---|---|
| PR #30 正文；PR 分支上的 `docs/handoffs/2026-10-04-harness-forward-acceptance.md` | 范围、验收结果、未闭合项 |
| `~/.finance-runtime/reviews/harness-budgeted-preflight-20261004/forward-20261004T1256/` | 已封存的工程证据根；先读 `engineering-closeout.json` |
| `docs/superpowers/specs/2026-10-02-model-owned-harness-spec.md` | 四片的设计依据 |
| `docs/handoffs/2026-10-04-pi-closeout-and-audit-followthrough.md` | 10-04 收尾核查与漂移说明 |
| Gitea 的 `refs/archive/wt-20261004/*`、`refs/archive/wt-20261005/*` | 上游分片树的归档钉 |

**步骤与验收**：
- [ ] 等 WP-1 出结论，除非用户明确说不等。
- [ ] 用 `git merge-tree` 预演冲突，不改任何分支；列出冲突块和语义交叠。
- [ ] 备忘提交为 `docs/verification/<日期>-pr30-disposition.md`，任务板评论附上推荐。
- [ ] 用户拍板后按所选方案执行，验收见目标 2。

### WP-5 运行报告的模型身份与实际路由（FINANCEWORKS-15，P0）

**背景**：审计 P0③"模型身份没钉住"仍有一部分成立。
- continuous 路径每轮会写 `model_admission`，但只告警。
- ask 固定流程在 10-04 的 MY-01 上，因为没有正向的模型身份字段，触发了 identity stop。
- 对照实验目前要翻 trace 才能判断身份和路由（口径见 WP-1 证据表）。
- 代码里的默认模型仍是 `glm-5.2`（`intelligence/services/llm_refine.py:115-116,257`），生产靠环境变量覆盖。

**目标**：
1. 运行报告和收据对每次模型调用记录 requested 和 served 模型（取自响应），并汇总成运行级的正向身份证据，对照和验收工具直接读这一份。
2. 运行报告记录实际执行的路由（episode、ask 固定流程或其他），`gate_receipt.engine` 不再恒为 episode。
3. 把 ask 固定流程纳入 `model_admission`：错配时告警，是否拦截另行拍板。
4. 评估默认模型回退改为"缺配置就显式告警或拒绝"。动手前先列出所有启动路径，每条都要覆盖到。

**非目标**：
- ❌ 线上硬拦截错配。
- ❌ 换模型或改生产配置。

**证据路径**：

| 文件 | 看什么 |
|---|---|
| `intelligence/eval/model_admission.py`、`scripts/check_model_admission.py` | 准入判定逻辑 |
| `intelligence/runtime/continuous_turn_adapter.py`（`_model_admission_receipt`，约 2515 行） | continuous 路径的身份收据 |
| `intelligence/services/ask.py`、`intelligence/services/llm_refine.py` | 固定流程与模型调用 |
| `intelligence/eval/model_harness_2x2.py` | 2×2 分析如何从产物重算身份 |
| FINANCEWORKS-5 的评论（10-04 18:59、10-05 11:04） | MY-01 的 identity stop；身份字段口径 |

**步骤与验收**：
- [ ] 先写红测试：ask 固定流程跑一次后，报告里要有每次调用的 served 模型和 `route=ask_fixed`。当前代码下这个测试应失败。
- [ ] 实现后转绿；`check_model_admission.py` 对两条路径都给出正向判定。
- [ ] 阳性对照：注入一个错配的 served 模型，应判为 mismatch。
- [ ] 变异证明测试承重；全量门禁；开 PR。

### WP-6 工具面减负（FINANCEWORKS-7，P2）

**现状（10-04 实测）**：
- finance_query 给 agent 的参数说明（schema）有 24,156 字符，其中 dataset 一项 10,937；40 个数据集每次全量下发。
- 注册表里有 19 个工具，三组重叠：
  - `kb_search` / `evidence_search` / `evidence_lookup`
  - `market_data` / `finance_query` / `history_query`
  - `web_search` / `news_search`
- 正则路由 8 个文件共 245 处，已被棘轮冻结。
- 仓里没有按路由裁剪 dataset 的代码。

**目标**：按 10-03 总规格中 FINANCEWORKS-7 的要求，顺序如下：
1. 先量：同义改写题的路由准确率、schema 字符数和估算 token、各工具和各数据集的出错率与空结果率。
2. 按真实任务裁剪 dataset 枚举，保留发现和扩展入口。
3. 合并重叠工具，并证明能力没有丢。
4. 过 WP-2 的门，证明弱模型不退化。

**非目标**：
- ❌ 新增正则。
- ❌ 只以"工具变少了"作为验收。
- ❌ 在 WP-1、WP-3 的方向定下来之前大改路由。

**证据路径**：
- `intelligence/services/episode_tools.py`（`_agent_finance_parameters`）
- `intelligence/services/research_tool_registry.py`（`_DEFAULT_TOOL_METADATA`）
- `scripts/audit_episode_tool_outcomes.py --by-dataset`
- `scripts/check_regex_routes.py`
- `docs/agent-product-door.md`

**验收**：量测报告；裁剪 PR 附可发现性测试；合并 PR 附能力覆盖对照表；过 WP-2 的门。

### WP-7 记忆召回收尾（FINANCEWORKS-8，P1）

**现状**：
- 真实快照上 24 道改写题的召回读数：

  | 档位 | hit@5（前 5 条结果里有没有命中） | 说明 |
  |---|---|---|
  | 关键词（原句 / 加主题） | 2/24 / 9/24 | 生产在用 |
  | BGE 语义 | 23/24 | 多返回 97 次，人工审读其中 57 次与题目无关 |

- 生产保持关键词档。#33 修复了"命中后只交付原则"，已上线。
- 冷启动时开场预取约 1006 ms 返回 `user_memory_gap/timeout`（预算 1 s）；预热后只要 19–22 ms。
- 条目归属和冲突去重还没复核。

**目标**：
1. 冷启动：服务启动时预热，或改造到首个会话不超时；不扩大 1 s 预算。
2. 重新冻结 20–30 道身份稳定的标注题，包含改写、负例，以及后续澄清和适用对象。
3. 定出条目归属和冲突去重的规则。
4. 按事先定好的门槛决定默认档：门槛没过就仍用关键词。
5. 关闭 FINANCEWORKS-8。

**非目标**：
- ❌ 门槛没过就把默认改成语义档。
- ❌ 往真实用户数据里写东西。
- ❌ 联网下载模型：本地已有才测。

**证据路径**：
- `docs/verification/2026-10-04-memory-recall-v2.md`、`2026-10-04-memory-recall-baseline.md`、`2026-10-04-memory-consumption-closeout.md`
- `docs/superpowers/specs/2026-10-04-memory-consumption-followup-spec.md`
- `intelligence/services/user_memory.py`、`memory_semantic.py`
- `intelligence/eval/retrieval_recall.py`

**验收**：
- 冷启动有阳性对照：冷进程的第一个会话在预算内交付。
- 新标注集冻结哈希。
- 门槛判定表。
- 任务板关单评论。

### WP-8 预测台账消积压（FINANCEWORKS-10，P2）

**现状**：
- Open 表 205 行，pending 115，其中 101 条过期待处理；10-03 至今只处理了 1 条。
- fix_type 冻结为七类，HARNESS_FIX 占 68%。
- 429 效果预测 R-20261001-02 的 14 天窗口约在 10-17 到期。

**目标**：
1. 逐条处理这 101 条：有新证据就重验；没有就按理由记为 expired（未验证，不等于证伪）；仍在研的进重验队列。
2. 设计并落地 fix_type 的扩展（`MODEL_FIX`、`TOOL_SURFACE_FIX`），保证新旧读写兼容，配套 crosswalk 和枚举校验。
3. 10-17 之后按预注册核对 R-20261001-02。

**非目标**：
- ❌ 按年龄批量关闭。
- ❌ 没验证就写 confirmed 或 refuted。
- ❌ 改历史行的原文。

**证据路径**：
- `docs/prediction-ledger.md`（热文件：分批开小 PR，开工前先 fetch）
- `scripts/prediction_ledger_status.py --worksheet`
- `docs/verification/2026-10-03-prediction-ledger-triage.md`
- `tests/test_prediction_ledger_status.py`、`tests/test_ledger_spec_crosswalk.py`

**验收**：过期待处理降到 0，每条都有理由；`prediction_ledger_status.py --strict` 通过；枚举扩展有兼容测试。

### WP-9 技术债按收益治理（FINANCEWORKS-12，P2）

**现状（10-04 实测）**：
- 300 行以上的函数有 32 个，最长的 `_run_turn_ledgered` 2,299 行，还在变长。
- ruff 只开了 E4/E7/E9/F 四类，target 写的是 py39，而项目钉的是 3.12.13。
- `docs/verification` 在 git 里有 14,533 个文件、131.9 MB。
- 体量：AGENTS.md 23 KB，lessons 106.7 KB，`inflight/main.md` 21.6 KB（超过 3K 预算）。
- runtime 有 24 个模块、25,608 行，而 `scripts/layer_audit.py:13` 仍写着"底座 15 个模块"。
- 没有 `experiments/` 目录。

**目标**：按收益排序，不抢内容修复的优先级。
1. 复杂度棘轮只管新增或改动的函数（对 diff 跑 C901 / PLR0915）。
2. ruff target 升到 py312，先量清会冒出多少新报错。
3. 收据移出 git：设计"外部原件 + 哈希索引"，先迁一个目录试点。
4. AGENTS.md 和 lessons 精简：规则写短，理由用链接指出去。
5. `inflight/main.md` 压回 3K 以内。
6. 非生产循环挪到 `experiments/`，并更新 layer_audit 的约束。
7. 巨函数碰到哪块再拆哪块。

**非目标**：
- ❌ 全仓重写或批量格式化。
- ❌ 抢 WP-1、2、3 的优先级。

**证据路径**：`ruff.toml`、`scripts/layer_audit.py`、`.pre-commit-config.yaml`、[10-04 状态页](../../verification/2026-10-04-harness-followthrough-status.md)。

**验收**：每一项单独开 PR，门禁全绿，行为不变（附全量收据）。

### WP-10 数据空列、换源与时效红绿表（FINANCEWORKS-9，P1）

**现状（10-04 23:29 只读实测）**：
- 核心行情更新到 09-30（节前最后一个交易日），时效正常。
- 空列：

  | 表 | 情况 |
  |---|---|
  | `fact_mainline_sector_daily` | 09-30 共 68 行，成交额、强度、涨幅等 22 列全空 |
  | `fact_sector_daily.strength` | 113,537 行，没有一行有值 |
  | `fact_stock_high_daily.is_new` | 09-30 的 295 行全空 |

- 停更：
  - fupanhui 来源的 7 张表停在 09-02：`fact_auction_stock_daily`、`fact_dragon_{seat,summary,tiger}_daily`、`fact_global_{index,stock}_daily`、`fact_limit_advance_presence`。其中龙虎榜和竞价已有同花顺的表更新到 09-30。
  - `fact_theme_flow_daily` 停在 09-15。
  - `fact_polymarket_macro_odds_daily`、`fact_stock_technical_snapshot` 为空表。
- 答案侧：#989 已经把缺值标成 partial 或"未核验"。

**目标**：
1. 列出每张核心表到答案消费点的映射，并标注现状。
2. 每次夜跑结束后出一张红绿表：每张表的最新日期和关键字段非空率。复用现有工具。
3. 每个全空列都定下去向：要么换源补齐，要么在消费侧明确移除并显示"未提供"。
4. 完成一个数据族（建议板块日线或龙虎榜）的换源消费切换，并定出时效 SLO（服务等级目标，例如"收盘当天 20:00 前到位"）。
5. AIHOT 真实源的接入单独验收。

**非目标**：
- ❌ 历史日跑 `daily-full`。
- ❌ 用今日数据回填历史日。
- ❌ 在 fupanhui 停采期间跑 full / cheap 计划。
- ❌ 往 VIEW 写。
- ❌ 手写 SQL 改生产库。

**证据路径**：

| 文件 | 看什么 |
|---|---|
| `market_feature_store/quality.py`（`check_daily`，约 258 行）、`scripts/check_daily_review_data.py`、`scripts/build_daily_ops_ledger.py`、`scripts/source_switch_coverage_diff.py` | 现成的检查与对账工具，复用，勿重造 |
| `market_feature_store/schema.sql`、`docs/learning/current-duckdb-source.md`、`docs/data-sources/runtime-and-pitfalls.md` | 表契约、验鲜方法、数据源的坑 |
| `skills/duckdb-backfill/SKILL.md` | 历史回补的唯一入口 |
| `~/.finance-runtime/reviews/harness-followthrough-20261004/measurements/data-freshness-nulls.json` | 10-04 的只读实测原件 |

**步骤与验收**：
- [ ] 只读核查后写出映射表。
- [ ] 红绿表脚本带阳性对照：人为置空一列，表上应该变红。
- [ ] 换源 PR。
- [ ] 10-08（节后首个交易日）夜跑结束后，验收红绿表。

### WP-11 Knevo 周期回归与月度留出（FINANCEWORKS-11，P2，依赖 WP-2）

**现状**：
- AB 台账只有 3 个样本，干净的成对样本为 0。
- 真实入口 12 题端到端 0/12 的旧结果保留，没有翻案。
- 12 题的回归工具已经有了，但"周回归"还没建立。

**目标**：
1. 建立冻结的每周配对小题包：5–10 题，双方用同一截止时间，同时冻结答案，盲评，并自动做截止审计（引用日期晚于截止就判违规）。
2. 每月轮换一次只评不调的留出集。
3. 事先固定模型、版本、数据、费用上限和执行频率。
4. 周期任务失败不能静默报成功。

**非目标**：
- ❌ 在留出集上调参。
- ❌ 把旧的 0/12 改写成新结论。

**证据路径**：
- `intelligence/eval/knevo_regression.py`
- `intelligence/eval/cases/knevo_absorption_regression.json`
- `docs/learning/knevo-distill/final-report.md`、`ab-ledger.md`

**验收**：首个周包冻结并跑通一次；失败路径的告警经过阳性对照。

### WP-12 工作区收口（FINANCEWORKS-13）

**现状**：
- 29 棵树的去向表见 [10-05 收尾快照](../../handoffs/2026-10-05-delegated-merge-and-tree-closeout.md)。
- 其中 10 棵被 `worktree_safety` 的前缀误报挡住，修复在途（§6）。
- 主检出落后 main 230 多个提交，有 118 处未提交改动（含夜跑运营叠层，以及 10-04 那 5 处技能视图对齐）。
- 生产快照 9 个。
- main 上留着多份已合分支的过期 inflight。

**子项**：
- **12a（P0，误报修复合入后）**：用 `scripts/worktree_closeout.py --plan`（每棵写理由）先预演、再 apply，回收以下树。先拆嵌套子树，再拆 `/private/tmp/harness-opt`。
  - `.claude/worktrees/` 下的 `blissful-noether-6da136`、`kind-engelbart-aa727f`、`pi-session-cleanup-479dc5`
  - `.worktrees/capture-quotes-0929`、`.worktrees/arena-8792-harness-takeover-0929`
  - `/private/tmp/harness-opt` 及其下的三棵
  - `/private/tmp/review-pr16-1002`
  - `.claude/worktrees/unclosed-session-stats-838ac4`：有归属不明的未提交测试改动，走 salvage 保全后再回收。
- **12b（需 §4-5 拍板）主检出同步**：
  1. 先读 launchd 计划任务、`~/.local/bin` 启动器里引用 `$DATA_ROOT/scripts` 的部分，以及 `ops_pipeline_run_daily.source`，把运营叠层迁回代码根。
  2. 撤掉那 5 处视图对齐，命令见 FINANCEWORKS-13 的评论（10-05 00:0x）。
  3. 其余脏条目逐条认领或封存（用临时索引做 salvage）。
  4. 最后快进到 main。
- **12c 生产快照轮换**：按部署账本保留当前版本和回滚锚；两个上锁的快照按锁理由处理；其余用 closeout 回收。
- **12d 过期 inflight**：列出 main 上已合分支仍留在 `docs/handoffs/inflight/` 的文件，在一个文档 PR 里批量转成日期快照。只动已合并、且没有在途会话的分支。
- **12e**：另一个仓（记忆库）里的 `~/agent-memory-wt-harness-output-provenance-1003`，按该仓的规则处置。
- **12f**：清理 GitHub 上已合并的远端分支（Gitea 会保留历史引用）。

**非目标**：
- ❌ 对主检出用 `git clean` 或 `reset --hard`。
- ❌ 删分支：closeout 一律保留分支。
- ❌ 动 Pi 的活动树、生产当前快照或回滚锚。

**证据路径**：
- `scripts/worktree_board.py`、`scripts/worktree_closeout.py`、`scripts/worktree_safety.py`
- `docs/handoffs/2026-10-04-claude-takeover-closeout.md`、`docs/workflows/dual-remote-collaboration.md`
- `~/.finance-runtime/reviews/harness-followthrough-20261004/skill-view/README.md`

**验收**：
- `worktree_board.py` 清单里每棵树都有去向，去向未知为 0。
- apply 收据 0 失败，Gitea 归档钉回读一致。
- 主检出同步后，`.claude/skills` 与 main 一致，并且夜跑成功跑完一轮。

### WP-13 会话开场注入读错树（FINANCEWORKS-16，P1）

**背景**：桌面 app 把会话工作树建在主检出下面（`.claude/worktrees/<名>`），并按主检出加载项目技能和 hook 上下文。10-04 实测：
- 会话所在的 worktree 视图已经修好，加载到的技能列表却是主检出的旧视图。
- SessionStart 注入的"工作区事实"描述的是主检出（分支 main、48 个脏代码文件），而当前 worktree 其实是干净的。
- 修改主检出的 `.claude/skills` 后，会话的技能列表当场热更新，证实了加载来源。

**目标**：
1. `scripts/session_facts.sh` 从 hook 的输入（stdin JSON 里的 `cwd`）定位会话实际所在的树，报告那棵树的事实；`.claude/hooks/load-memory.sh` 如有同类问题，同样处理。读不到时回退到现状，并标注"可能不是你所在的树"。
2. 注入时比较主检出的 `.claude/skills` 与 origin/main 的视图，不一致就告警。
3. 测试含阳性对照：模拟一个嵌套 worktree 的 hook 输入。

**非目标**：
- ❌ 改桌面 app 的行为。
- ❌ 自动同步主检出（属于 WP-12b）。
- ❌ 让 hook 失败阻断会话：hook 恒 exit 0。

**证据路径**：`.claude/settings.json`、`scripts/session_facts.sh`、`.claude/hooks/load-memory.sh`、`scripts/check_agent_workspace_facts.py`、`tests/test_agent_hook_roots.py`。

**验收**：
- 在嵌套 worktree 会话里，注入的树路径等于在会话 cwd 下执行 `git rev-parse --show-toplevel` 的结果。
- 视图漂移时，注入里出现告警。
- 全量门禁绿。

## 6. 已在途，不要重复派

- **`worktree_safety` 前缀误报修复**：用户 10-05 在独立会话启动，已开 PR #49（`fix/worktree-safety-ancestor-refs-1005`），待合入。WP-12a 要等它合入后再做。
- **8792 vs Pi 对照线**：会话 `claude-code:bec914d0…`，以及会话树 `8792-pi-performance-analysis`。认领 WP-1 前，先在 FINANCEWORKS-5 协调。

## 7. 登记与回写

- 本单登记为工单 INDEX 的 #88（母单）。各工作包按任务板编号分派，不再另取工单号。
- 新开的任务板项：FINANCEWORKS-14（WP-4）、15（WP-5）、16（WP-13）。其余工作包挂在原有编号下，不另起清单。
- 状态以任务板为准。本单不逐包回写，以免母单变成第二份状态表；全部关闭后回写一次 INDEX 行。
