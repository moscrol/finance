# 研究意图边界修补（R-20260916-05 实锤缺陷）

- 日期：2026-09-16
- 分支：`fix/research-intent-boundaries`（隔离工作树，base `gitea/main@d433b907`）
- 结论：三类**运行时误解用户意图**的缺陷已修复并有变异验证；2026-09-17 独立 QC 复核后
  又补了三族同形漏洞与第三道闸的独立断言（见「QC 复核」节），并在本树起的 sidecar 上用
  隔离用户真跑了一臂：`checkpoints.jsonl` 未被创建、两臂 frame 同型（见「真实会话复测」节）。
  未合并 main，未部署 8792。
- 来源：`docs/verification/2026-09-16-mechanism-workbench-live.md`（R-20260916-05 两场真实会话）。
  **注意**：该文件截至 2026-09-17 只存在于工作树 `~/fwp-wt-mechanism-pilot`（分支
  `feat/mechanism-research-pilot`）且**未提交**，任何分支历史里都 grep 不到；原件在
  `~/.finance-runtime/mechanism-workbench/R-20260916-05/`。

## 修了什么

三个缺陷的共同点：不是「模型答得不好」，而是运行时把用户的话理解错了，所以都能用
确定性代码堵住，不靠改提示词。

### 1. 否定意图必须在写入前生效（最高优先级：有真实写入）

R05 题面写明「不要把本次研究登记为长期跟踪或投资观点」，答案照抄了这句承诺，
运行时仍往隔离用户目录写了 4 条 checkpoint（`track_next_watch` 2 条、
`ranking_flip_condition` 2 条）。承诺在文本层，写入在运行时层，两层没连上。

- `track_contract.persistence_opt_out(query)`：判据 = 否定词 + 登记类动词 + 跟踪类宾语
  **三件齐全**，且三者须在同一小句内（逗号不进间隔字符集）。只认「不」+「跟踪」会把
  「排产不及预期，跟踪一下」误判成退出。
- 拦截点三处：`ingest_next_watch` 开头、`ingest_flip_conditions` 开头、
  `TurnOrchestrator._ingest_track_next_watch` 早退。写入是不可撤销的外部副作用，
  多一道早退比事后清理便宜。
- `parse_track_intent` 先扣掉退出声明再做词面匹配：一句「不登记长期跟踪」原本反而
  打开跟踪契约，是纯词面匹配的经典反噬。句中另有正面跟踪诉求时仍然路由——
  表达纪律和持久化是两件事，不合成一个开关。

### 2. 日历月是时点，不是时长

线上写进用户目录的 `due=2027-07-13` 来自观察项里的「约 2026-10 月底披露」：
`(\d+)\s*(个)?\s*(天|日|周|月)` 把「10 月」读成「10 个月」= +300 天。

- 新增 `track_contract.calendar_month_due()`：`2026-10月底` / `2026年10月` / `2026-02`
  → 该月最后一天（取上界，早到期会让回检提前判空）。
- `ranking_contract._due_from_watch` 把日历月排在时长解析之前，并在时长匹配前
  摘掉年月 token，防止残留数字被当周期。
- 真时长（`30 天内`、`3 个月内`）与显式日期行为不变，有反向对照用例钉住。

### 3. 长研究问题不是「粘贴材料」

同一道题，只有末行排版指令不同，两臂路由却不同：summary 臂 `stock_deep_dive`
（subject 中际旭创），mechanism 臂 `kol_review`（subject null），两臂都把题面
识别成 `pasted_text`。原因在 `user_task._split_user_message_core`：
「末行是短问句 → 前面是材料」这条规则只检查头部**是不是短问句**，而
`_looks_like_question` 有 120 字上限，于是一句 245 字的研究问题因为「太长」被当成
材料，只剩末行格式要求交给路由。

- 新增 `_reads_like_document()`：只认**结构性**材料标记（`【】`、`来源：`、`作者：`、
  行首「一、」「1.」「第二节」），不认「研报/公告/摘要」这类**词**——用户提问里
  天然会说「请使用实际可获取的公告、财务数据」，词面命中就判材料，正是这次踩的坑。
- 没有结构标记时：头部带问句标记且 ≤400 字 → 判为提问；超过 400 字仍按材料走，
  真粘长文的行为不变。

## 变异验证（先证明缺陷在旧代码上真的复现）

同一批真实输入，`git stash` 撤掉修复后再跑一次（`/tmp/probe_intent_boundaries.py`）：

| 探针 | 修复前 | 修复后 |
|---|---|---|
| 用户说了不登记 → 跟踪意图判定 | `True` | `False` |
| checkpoint 写入条数 / 是否落盘 | `1` / 是 | `0` / 否 |
| 「约2026-10月底披露」→ 到期日 | `2027-07-13` | `2026-10-31` |
| 研究问题切出的材料数 | `1`（路由只看到「请按事实条目逐条整理…」） | `0`（路由看到完整题面） |

新测试在基线代码上直接 ImportError/失败，不是自证绿。

## 测试

- `intelligence/tests/test_research_intent_boundaries.py` 共 21 项：第一版 12 项（含 3 项
  反向对照：正常跟踪题照写、真时长不受影响、带结构标记的粘贴材料照切）+ QC 补漏 9 项
  （含 4 项反向对照与 1 项 orchestrator 层独立断言）。
- 第一版全量 `intelligence/tests`：9724 passed / 19 skipped / 2 xfailed，收据
  `20260916T161214Z-d433b907.json`（脏树读数，`dirty_paths` 正是这 5 个文件）。
- QC 定稿后的全量读数见「QC 复核」节末。
- 目标文件 Ruff 通过，`git diff --check` 通过。

## QC 复核（2026-09-17，另一个 agent 独立复核）

复核方式：不信汇报，自己重跑 12 项与 Ruff（绿）；然后对三条新规则各造一组「同一条规则、
换一种常见写法」的输入，**三条都被打穿**，且都是同一族毛病——第一版只用 R05 原句做夹具，
规则形状对了，但边界只贴着那一句画。

| 规则 | 打穿它的输入 | 第一版行为 | 定稿行为 |
|---|---|---|---|
| 退出登记 | 「别忘了登记跟踪」「不要忘记把这个登记为长期跟踪」「请勿遗漏登记」 | 判成退出，且 `parse_track_intent` 同时为 False → 用户要的跟踪被**静默关掉** | 间隔里出现「忘/漏/遗/只」即不算退出 |
| 退出登记 | 「要不要登记为长期跟踪？」「需不需要纳入长期跟踪」 | 提问被判成拒绝 | 否定词前是「要/需/用」即不算 |
| 日历月 | 「2026年10月15日披露」 | `_item_due` → 10-31（`ranking` 侧因有中文全日期解析得到 10-15，两本 contract 同句不同 due） | 新增 `chinese_full_date()`，两侧共用；`_item_due` → 10-15 |
| 日历月 | 「2026年10亿元订单」「2026年3季度末」「2026/10/15」 | 10-31 / 03-31 / 10-31 | 「年」写法必须带「月」且后面不接数字；`-`/`/` 写法后不接分隔符或数字 → None |
| 材料降级 | R05 题面 + 非问句末行（「输出格式：表格。」） | 走的是另一条分支「整块像文档且无问句 → 全是材料」，题面整段变材料、**问题变空串** | 该分支同样加 `_reads_like_document` 前提 |
| 材料降级 | R05 题面 + 空行 + 末行 | 第三条分支（首/末短段是问题、其余是材料）同样缺前提 | 同上 |

- 顺序是先写用例、在第一版代码上跑出 **5 红 / 15 绿**（红的正好是 5 条缺陷用例、绿的是反向
  对照），再改代码到 21 绿。这比「先修再补测试」多花两分钟，换来的是每条用例都被证明过
  能抓到它声称抓的缺陷。
- 定稿后逐层变异（每次只废一个函数、`PYTHONPYCACHEPREFIX` 每轮新目录、文件哈希核对还原）：
  `persistence_opt_out→False` 红 4；`calendar_month_due→None` 红 3；`_reads_like_document→True`
  红 4；去掉间隔排除 红 2；关掉 orchestrator 早退 红 1（仅新加的第三道闸用例）。五轮里没有
  一条用例在不相关的变异下变红，也没有一个变异零红。
- orchestrator 早退原本没有独立断言（既有测试把整个方法 monkeypatch 掉了）。新用例把内层两个
  ingest 换成**会漏写文件的假函数**，外层仍须挡住；反向对照下两个假函数都被调用。三道闸
  现在各有一条只属于它的红。
- 邻近 12 个测试文件（`test_user_task` / `test_task_frame` / `test_conversation_materials` /
  `test_e2_*material*` / `test_track_contract` / `test_ranking_contract`）323 passed。
- 顺手删掉 `ranking_contract._CN_DATE_RE`（被共用推导取代后成了死代码）。
- QC 定稿树全量 `intelligence/tests`：**9733 passed / 0 failed / 19 skipped / 2 xfailed**
  （544.86s，与探针并行所以比第一版慢），收据 `20260916T170313Z-d433b907.json`
  （脏树读数，`dirty_paths` 5 个）。提交后在干净分支尖再出一份，合并前用
  `scripts/check_test_receipt.py --expect-revision <分支尖>` 采信。
- 离线重放（不调模型）：把两臂题面原文喂给生产同款 `turn_controller.decide_turn`，
  R05 实录是 `stock_deep_dive/中际旭创/materials=1` 与 `kol_review/None/materials=1`；
  本分支两臂**同型** `financial_analysis` / subject `中际旭创` / `materials=0`。
  注意类型不是交接里预期的 `stock_deep_dive`——那个值是旧代码在被切掉主体的残句上算出来的。

### 仍然知道但没动的边界

- 「1. 收入是否兑现？\n2. 应收是否支持？」这种带行首编号的子问题清单仍被判成材料
  （结构标记命中）。与第一版行为一致，不是本轮引入；要解需要「编号行本身带问句标记」
  的例外，先攒样本。
- `_QUESTION_HEAD_MAX_CHARS=400`：超过 400 字的研究问题仍按材料走。
- 「是不是不需要登记跟踪？」这类嵌套疑问仍判退出；出现频率低，未处理。
- 同族但**未接闸**的第三个写入器：`ask.py::_propose_foresight_judgments` →
  `judgment_extract.propose_from_answer`（engine B，写 `judgments.jsonl`，pending 态）。
  R05 走的是 engine A，未触发。没接的原因：题面「不要登记为…投资观点」要接上，得把
  「观点/判断」加进宾语表，而「不作为投资建议/判断依据」是中文金融文本的标准免责句，
  会大面积误杀。单独立项。
- `parse_ranking_intent` 对 R05 为 True（「优先」+ 三个对象），只影响提示词注入、不写盘，未动。

## 真实会话复测（2026-09-17，sidecar + 隔离用户，一臂）

- 先探网关：`POST $LLM_BASE_URL/chat/completions` 最小请求 HTTP 200（glm-5.3 应答），再起服务。
- sidecar 从本工作树起在 `127.0.0.1:8824`（只取生产 launcher 的 `export` 行；
  `FORESIGHT_USERS_DIR` / `FORESIGHT_EPISODE_STORE` 指向 `~/.finance-runtime/intent-boundaries-qc/`；
  `RAG_WORKER_ENABLED=0`，16 GB 机器 swap 已近满，第二个 BGE worker 会把生产压进 swap——这是
  与生产的**已声明偏差**）。`/api/health`：`code_matches_repo=true`、`users_dir` 是 scratch 目录、
  监听进程 `cwd` 经 `lsof` 核对为本树。生产 8792 全程未动。
- 发题：summary 臂 R05 冻结原文（含「不要把本次研究登记为长期跟踪或投资观点」），
  用户 `qc-intent-0917-summary`（全新），`run_20260917_010451_513107`，`completed`，214s，
  工具：financial_data 1 / derived_calculation 3 / l3_lookup 1 / web_search 1 / web_fetch 1。

| 观测 | R05 旧代码（生产 8792，2026-09-16） | 本分支 sidecar（2026-09-17） |
|---|---|---|
| `task_frame` | `stock_deep_dive` / 中际旭创 / materials=1 | `financial_analysis` / 中际旭创 / **materials=0** |
| 答案里有可登记内容 | 有（下期关注 + 改判条件） | 有（1220 字，含「改判条件表」）→ 闸门挡的是真候选，不是空转 |
| `users/<user>/checkpoints.jsonl` | 写了 **4 行**（含 due=2027-07-13） | **文件不存在**，0 行 |
| 用户目录其它写入 | — | `conversations/`、`runs/`、`workbench.sqlite3`、`research_evolution/product_value_events.jsonl`（2 条产品遥测事件，不是跟踪登记） |

- 没做：mechanism 臂未真跑（离线重放两臂 frame 逐字段相同，见上；再跑一臂 = 再花 4 分钟共享配额，
  收益是把「两臂同型」从离线证据变成线上证据）；不盲评；一题一次，不做决策结论。
- 原件：`~/.finance-runtime/intent-boundaries-qc/R-20260917-QC/summary/`（`verdict.json`、`terminal.json`、
  `continuous-episode.json`、`answer.md`、`health_before.json`）；客户端 `run_arm.py` 同目录，
  刻意不入库（一次性 scratch，长期由单测兜底）。

## 明确没有修的（不假装已解决）

以下是 R05 记录的内容层错误，**都不是**靠词面规则能安全堵住的，另立工单：

1. 选错报告期（用 2025 年报 + 2026 中报，漏掉已取到的 2026 一季报）。
2. 把产能建设/投资现金流混进经营现金流解释；正文先报 OCF +18.00 亿又写「持续为负」。
3. 证据来源层级：股吧评论、搜索摘要与公告原文同等当证据用。
4. `derived_calculation` 的 subject 代码匹配（`300308` vs `300308.SZ`）与
   `base_calc_not_found`、首次调用 `TypeError: table() missing 1 required positional argument`。
5. 语义判官漏检上述内容错误（`correlated_judge=true`，与被审模型同源）。

这些要先有「会不会误杀正常表述」的样本集，再谈门禁，否则只是把一类错误换成另一类。

## 边界

- 未部署到 8792，未在真实会话里复测；本文件只证明代码层判定改变，不宣称线上效果。
- 退出登记的判据是**用户问题**，不读模型答案：模型说「本次不登记」不构成授权。
- 400 字问题上限、月底取上界都是可争议的阈值选择，已写进测试，改动时须同步改测试。
