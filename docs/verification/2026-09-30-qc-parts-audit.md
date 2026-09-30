# 质检：finance agent 各部件优化与日常工作线（2026-09-30）

> 范围：用户要求按「底座 / 领域 harness / 工具层 / skill / 记忆 / 优化迭代机制」逐部件质检，并覆盖三条日常线：数据接入与消费、Knevo 对照借鉴、ReAct 对照。
> 基线：`main@75693271`（浅克隆，只有 1 个提交，所以**没有做历史 / 变更频率分析**）。
> 环境：Linux 沙箱，Python 3.11.2（仓内要求 3.12，装不上）。没有 Mac 上的 `~/.finance-runtime` / `~/agent-memory` / `~/harness-reference`，所以**所有 live 读数都引自仓内文档，不是本次复算**。
> 修复：P0 三项、台账体检工具，以及质检中新发现的一个测试泄漏，已在 `arena/01a0f120-finance` 分支落地，见 §3。

## 0. 总评

**纪律很强，但力气花在了流程、格式和自检上，瓶颈却在内容正确性。**

- 09-29 能力线地图原话：「格式和流程层的改进没有换来内容正确」（`docs/handoffs/2026-09-29-8792-answer-capability-lines-map.md`）。
- 台账把 76% 的修补归到 harness 层，没有一条归到模型。
- 唯一一次和外部基线（ReAct）的对照，同时换了模型（Claude vs GLM）和 harness，所以「harness 不如 ReAct」这个读法**至今没有证据支撑，也没有被证伪**。

## 1. 分部件评级

🟢 健康 · 🟡 有明确缺口但不致命 · 🔴 方向性问题或关键判据缺失

| 部件 | 评级 | 主要证据 | 主要缺口 |
|---|---|---|---|
| 底座（模型 / 运行时） | 🟡 | 代码默认 `glm-5.2`（`llm_refine.py` provider 默认段）；生产 09-16 起按用户决定跑 `glm-5.3-flash`；三态 `served_model` 已逐 turn 落盘 | ① 09-29 消融预设 `glm-5.3`、实际 `-flash`，**准入没有机器判定** → 已修（§3-③）；② 429 时 0.6 秒内连打三次就放弃、冷却提示丢失（`docs/lessons_learned.md` 09-09 条）→ 已修（§3-②）；③ `market_feature_store/db.py` 的 `hold_swap_lock` 用 `flock(LOCK_SH)`，DuckDB 写锁是 fcntl POSIX 锁：Linux 上两者互不可见，`test_market_feature_store_staging_swap` 6 例红。推测 macOS 上两者可见所以本机绿——**平台相关的隐性假设**，迁 Linux 即失效 |
| 领域 harness | 🔴 | 台账 `HARNESS_FIX` 122 / 160 = 76%；`intelligence/` 非测试代码 519 模块、27.3 万行（`services/` 约 15 万）；300 行以上的函数 32 个，最长 `_run_turn_ledgered` 2,279 行、`_answer_query_impl` 1,751 行；`re.compile` 816 处 | 模型与 harness 从未分离测量 → 预注册 2×2（§3-C）；超长函数与大量正则路由让「改一处影响哪里」难以推断；`route_table.py` 头部自带一条误路由记录 |
| 工具层 | 🟡 | 19 个工具；`finance_query` 一个工具的 schema 就有 24,074 字符（40 个数据集），其余 18 个合计约 1.5 万 | 没有按路由收窄工具面：每轮都把 40 个数据集的说明塞给模型 |
| skill | 🟡 | `skills/` 39 个 SKILL.md，注册表与视图有生成器和检查 | `stock-technicals` 未暴露，被它取代、已跑不通的 3 个旧 skill 反而暴露 → 已修（§3-①）；`up-line` 硬编码 Mac 路径；`advancers-chart` 依赖已退役的飞书，但没有 skill 级替代，保留 |
| 记忆 | 🟡 | 用户记忆是词面重叠打分（窗口 200，取前 5）；纠错写入侧已合 | 开场自动召回仍在 `feat/architecture-audit-0924` 分支；开发记忆 AGENTS.md 22.6KB、lessons 106.7KB，已经超出「每次会话读完」的量 |
| 优化迭代机制 | 🔴 | 552 份 handoff（09-23 单日 70 份）、282 份 spec、115 份 plan；git 跟踪 297.7MB，其中 `docs/verification` 137.9MB / 14,467 个文件 | 台账：pending 107 行里 104 行已挂超过 14 天（最老 57 天）；最新条目 `R-20260916-03`，之后 14 天没有新预测入账；`SYSTEM_PROMPT_FIX` 一次都没出现过 → 体检脚本已补（§3-④） |
| 数据接入与消费 | 🟡 | 09-24 读数：主线板块 69 行成交额 / 强度 / 涨幅为 NULL；新高 389 只，而 `high_status` 为 NULL 的有 3,443 只；桥每天 3~10 只股票静默缺行、无报警（`docs/superpowers/specs/2026-09-29-bridge-silent-gap-decision-request.md`） | 同花顺切换未完成；8e45 事故一次 −204,670 行；缺一张每日红绿表和新鲜度 SLO（服务等级目标：数据最晚几点必须到） |
| Knevo 对照借鉴 | 🔴 | 57 个文件；e2e 0/12（判官 3、来源被拒 3、无效或漏答 5、越界 1） | 抄了形状，但端到端一题没过；缺每周固定题的成对回归 |
| ReAct 对照 | 🔴 | unseen 10 题：react 0.857 > 8796 0.595 > 8792 0.567 ≫ component 0.111（`docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md`） | react 臂是 Claude，产品臂是 `glm-5.3`，差距来源分不开 → 预注册 2×2（§3-C） |

## 2. 关键读数

### 2.1 预测台账（`scripts/prediction_ledger_status.py --as-of 2026-09-30`）

- Open 主表 **160 行**（按 `audit_ledger_spec_crosswalk.py` 的号型口径）。另有 3 行号型不合规、不计入：`R-20260827-07a`、`R-20260821-03a`、`R-20260823-SPTTECH-04`。
- outcome：pending 107 · confirmed 46 · refuted 2 · partially_confirmed 2 · held 1 · deferred 1 · 未达标 1。
- fix_type：HARNESS_FIX 122（76%）· DATA_CONTRACT_FIX 17 · EVAL_ONLY 13 · ROUTING_FIX 3 · NO_SYSTEM_FIX 3 · TOOL_DESCRIPTION_FIX 2 · SYSTEM_PROMPT_FIX 0。
- 枚举外取值 0。refuted 连击 ≥3：无。
- 按过期规则（§3-④）：证实 46 · 部分证实 2 · 证伪 2 · **过期 101** · 待定 6 · 其他 3（held / deferred / 未达标）。107 行 pending 里，新鲜（≤14 天）3 行，临期（15–30 天）3 行，过期（>30 天）101 行。
- **勘误**：会话里口头报过「181 条定义、HARNESS_FIX 122 条 = 67%」，那是粗解析，把回填段也算进去了。以本节为准。

### 2.2 测试与静态检查（本次在沙箱复算）

- `ruff check`：通过。`layer_audit.py`：ERROR 0。注册表、可解析性、运行时目录三项检查：一致。
- 全量 pytest（收集 18,779 条）：**59 挂 / 18,512 过 / 206 跳 / 2 预期失败**，耗时 1,945 秒。59 条的分类：
  - 49 条：缺 `/bin/zsh`（沙箱环境问题）；
  - 3 条：依赖 macOS 或 vault；
  - 1 条：Python 3.11 语法不兼容。仓内有 2 个文件用了 3.12 语法：`scripts/calc_case_acceptance.py:273`、`skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py:172`；
  - 6 条：**真实潜在缺陷**，swap 锁，见 §1 底座行。
- 全量跑完后沙箱家目录多出 `~/.finance-runtime/rejudge-pending/index.jsonl`（138 行）→ 定位为测试泄漏，已修（§3-⑤）。
- **第二轮推进后在同一沙箱复跑全量**（1,552 秒）：**1 挂 / 18,667 过 / 264 跳 / 2 预期失败 / 1 收集错误**。多出的 58 条跳过 = Mac 专属 52 + 换库锁 5 + clonefile 1，与 §3 逐条对得上。剩下的红只有一个原因：沙箱的 Python 3.11 解析不了一处 3.12 语法，造成 1 条收集错误；另有 1 条用例专门断言「主树收集不得报错」，被同一处连带。Mac 上是 3.12，这两条不存在。

## 3. 本分支已做的修复（`arena/01a0f120-finance`）

| # | 修了什么 | 改动 | 测试 |
|---|---|---|---|
| ① | skill 视图错位 | `.claude/skills/` 链入 `stock-technicals`，撤下被它取代的 `up-line` / `watchlist-ma` / `top-gainers-feishu`（目录按 #729 保留）；frontmatter 加 `metadata.superseded_by`；同步 dispatcher、top-gainers、AGENTS.md、CLAUDE.md、`skills.registry.json` | `tests/test_skill_view_supersession.py`：被取代的不许暴露、取代者必须暴露、不许链式取代。反向验证过：把 `up-line` 链回去，或摘掉 `stock-technicals`，都会红 |
| ② | 429 限流处理 | `llm_refine.py`：只认 429；按 `Retry-After` / `retry-after-ms` 等一次再试（没给就 2 秒加抖动）。以下情况不等、直接失败：要等超过 20 秒；等完剩不到 `MIN_VIABLE_LLM_SECONDS`；本轮调用预算已满；流式已吐字；用户取消。失败原因带「限流：服务端要求 N 秒后再试」，仍归 `provider_rate_limited`。**没有**把 429 加进瞬态名单（那条链会无间隔连打三次）。覆盖 `complete` / `chat_with_tools`（含流式）/ `synthesize_messages` / `synthesize_messages_stream` | `intelligence/tests/test_llm_rate_limit_retry.py` 34 例。反向验证：换回旧行为，6 个调用路径用例红。回归：89 个引用 `llm_refine` 的测试文件共 3,163 例全绿 |
| ③ | 生效模型准入 | `intelligence/eval/model_admission.py` + `scripts/check_model_admission.py --expect-model X <产物>...`。exit 0 准入 / 1 错配 / 2 无证据（fail-closed）；认 `continuous-episode.json`、`events.jsonl`、SDK 臂的 `served_models`；acceptance-workflow §2 第 3 条补了这一步 | `intelligence/tests/test_model_admission.py` 19 例。真实产物冒烟：09-21 judge-mode-k3 两个生产 run，`--expect-model glm-5.3` → exit 1（实际 `kimi-k3`），`--expect-model kimi-k3` → exit 0 |
| ④ | 台账体检 + 过期规则 | `scripts/prediction_ledger_status.py`：fix_type 分布、pending 年龄、枚举外取值、refuted 连击；Open 表取行复用 crosswalk 的解析。之后加了过期规则：pending 分新鲜（≤14 天）/ 临期（15–30 天）/ 过期（>30 天）三档，另出一行结案口径。台账记账规则新增一条：过期不等于证伪，要么重验，要么 outcome 写 `expired` 并写明理由。脚本只读，不改行。五条修复对应的待入账草稿见 §6 | `tests/test_prediction_ledger_status.py`，含「与 crosswalk 行数一致」「枚举与台账规则节一致」两条防漂移；过期规则另有 7 例（档位边界、六格相加等于行数、`expired` 不进也不断连击、阈值顺序、规则原文与常量一致）。变异验证：把边界 `<=` 改成 `<`，或不计已关闭的过期行，都会红 |
| ⑤ | 测试往真实「待重判」队列写假条目（本次质检中发现） | workbench HTTP 用例把运行交给后台线程 `workbench-run_N`，线程在用例结束、pytest 清掉 `PYTEST_CURRENT_TEST` 之后才写 `~/.finance-runtime/rejudge-pending/index.jsonl`，模块自带的「测试中不写」闸失效：一次全量灌进 138 条假「待重判」，Mac 上即污染生产积压。根 `conftest.py` 的 `_FORCED_TEST_ENV` 把 `FINANCE_REJUDGE_PENDING_INDEX` 改道到会话临时文件 | `intelligence/tests/test_rejudge_pending_isolation.py`（复现「比用例活得久的线程」）。插桩复跑 89 个文件：泄漏 68 次 → 0；反向验证：撤掉 conftest 改动即红 |
| C | 预注册 2×2 + 冻结判定工具 | `docs/superpowers/specs/2026-09-30-model-harness-2x2-preregistration.md`，开跑前第 1 次修订：G 改为 `glm-5.3-flash`（生产同款）；20 题（unseen 10 + 按固定种子从 seen 抽 10）× 4 格 × 3 次 = 240 次；判定表补上「ΔH 可判且 P > R」一行；新增只看 unseen 的次要分析。原 10 题设计连 0.10 的最小效应都判不出（主效应 95% 半宽粗估 0.133），20 题约 0.094。`scripts/model_harness_2x2.py`：`plan` 出排程（题集抽样、拉丁方格序、provider 列）；`analyze` 按 §6 出判定（作废口径、取前 N 次有效、噪声底、bootstrap 区间、判定行、敏感性分析、`--json`） | `intelligence/tests/test_model_harness_2x2.py` 51 例，判定表每一行都能从数据端到端走到；另有一条「预注册原文与冻结常量一致」防漂移。变异验证：改重排上限、改 P>R 方向、把区间端点改成含 0、去掉拉丁方轮转，各自都会红。**未开跑**：要在 Mac 上先过 F1–F4 |
| P1 | 冻结正则路由 | `scripts/check_regex_routes.py` + `regex-routes-baseline.json`（8 个路由 / 题型判定模块共 243 处 `re.*` 调用点），挂进 pre-commit。只减不增：新增即拦，删减自动放行；确实要加，须在同一提交里 `--update-baseline` 留痕 | `tests/test_check_regex_routes.py` 6 例 |
| P2 | Mac 专属测试按条件跳过 | 52 条：49 条写死 `/bin/zsh`；2 条依赖本机 agent-memory 记忆库（钩子在记忆库不可达时按设计静默退出）；1 条依赖 macOS 的 clonefile。只给真需要的测试挂 `skipif`，条件在 Mac 上恒真，行为不变 | Linux 实测这 7 个文件：52 挂 → 142 过 / 52 跳 |
| P2 | 换库锁跨平台自检 | 换库锁 `hold_swap_lock` 用 flock，duckdb 的写者锁是 POSIX 记录锁：两者只在 macOS 上互斥，Linux 上这把锁排不掉写者（沙箱实测 duckdb 1.5.4，两个方向都不排）。`db.swap_lock_platform_probe` 用子进程扮演另一个进程里的写者，调真实的 `hold_swap_lock` 测两个方向。daily-full 预检据此 fail closed；直写的 daily-update 不换库，不查。另加 `scripts/check_swap_lock_platform.py`。顺手纠正了锁文档里「duckdb 单写者锁用 flock 实现」的说法 | `tests/test_swap_lock_platform_probe.py`（与「写入落不落得了库」这一真实后果对账、子进程失常时 fail closed、只测一次）。5 条换库锁测试按自检结果跳过；1 条参数用例依赖 `cp -c`，按 darwin 跳过。变异验证：把自检读数反过来即红。相关测试 208 过 / 21 跳 / 0 挂 |
| P1（部分） | 工具面收窄的调用证据 | `scripts/audit_episode_tool_outcomes.py` 加 `--by-dataset` / `--json`：`finance_query` 调用按题型（`contract.question_type`）× 数据集（trace `detail` 里的 `dataset=`）拆开，并列出注册表 `finance_query._DATASETS`（40 个）里在所扫 episode 中一次没被调用的。默认输出不变 | `tests/test_audit_episode_tool_outcomes.py` 9 例（含 2 个真实 episode 冒烟）。变异验证：去掉 `dataset=` 的前缀约束即红 |

## 4. 未修的建议

2026-09-30 第二轮推进后的状态。已做的见 §3；下面只列还没做的，并写明卡在哪。

**P1**

- 按路由收窄 `finance_query` 的工具面，不要每轮都给 40 个数据集。统计工具已补（§3）：`scripts/audit_episode_tool_outcomes.py --by-dataset <runs 目录>`，按题型 × 数据集拆开调用次数，并列出注册了却一次没被调用的数据集。沙箱里只有 2 个真实 episode，40 个里只看到 3 个被调用，样本太小，不下结论。在 Mac 上对全部 episode（台账记过 747 份）跑一次，才有收窄的证据；收窄本身要用户拍板。
- 内容正确性题包：时点、存量与流量、CFO 起点三类，对应 09-29 地图「下一步」第 2 条。题面和真值要按台账纪律从真实 run 里取，要在 Mac 上做。
- **更正：记忆召回题包早就有了**，质检时漏看了。尺子是 `intelligence/eval/retrieval_recall.py`，标注集是 `intelligence/eval/cases/retrieval_recall_v1.jsonl`（20 条真实标注，其中 user_memory 15 条），另有合成夹具。08-15 首份基线（`docs/verification/2026-08-15-recall-baseline.md`）：user_memory hit@5 = **46.7%**（7/15），8 条漏召回的主因登记为「中文无分词」。
  - 真正的问题是这把尺子量出来的缺口 46 天没闭环。08-05 定了两步：第一步是把上游抽好的实体传进召回，`episode_tools` 已接（`_memory_recall_intent`），`ask.py:1046` 仍只传原始问句；第二步是用户拍板的「用语义检索，不用关键词匹配」，至今未做（`user_memory.select_relevant` 仍是字面重合打分）。
  - 标注集有来源纪律（「不许造」），所以本轮没有编合成改写题。评分器也没改：改了在沙箱里量不出真实效果。下一步在 Mac 上一条命令出当前基线：`python -m intelligence.eval.retrieval_recall --cases intelligence/eval/cases/retrieval_recall_v1.jsonl --users-root "$FORESIGHT_USERS_DIR"`，再以它为验收尺子做语义检索。
- **更正：数据检查大体已有三件**，质检时说成「要做红绿表」不准确。
  - 已有：跨日质检 `market_feature_store/quality.py` 的 `check_daily`（断档、行数收缩、值域、空壳板块）；当日完整性闸门 `scripts/check_daily_review_data.py`；日运营台账 `scripts/build_daily_ops_ledger.py`（查当日产物在不在）。换数据源前另有覆盖对账 `scripts/source_switch_coverage_diff.py`。
  - 真正的缺口有两处。一是跨日门禁 09-09 起处于 disabled，原因是 09-03 / 09-04 四张表有洞、门禁必红（`docs/verification/2026-09-09-cutover-0909.md`），要先补洞再启用。二是 `check_daily` 以库里的 `fact_market_daily` 为日历，整条管线一起停时库内自洽、会报「通过」。这是有意的设计（有测试钉住「用库里最新日、不用墙钟」），所以这一层只能靠日运营台账查当日产物来兜底。
  - 补洞和启用都要用真实库，要在 Mac 上做。
- **更正：Knevo 回归的工具和题集已有**：`intelligence/eval/knevo_regression.py` + `knevo_absorption_regression.json`（12 题）。09-23 首批读数是 9 条交付、3 条失败，整链接纳 0 题（`docs/learning/knevo-distill/batches/2026-09-23-regression/README.md`）。缺的是固定周期：只跑过这一次。每周跑要在 Mac 上起 Workbench 探针服务，照那份 README 的正门流程执行。
- 冻结一个永不用于修复的留出集。它和 2×2 预注册 §9 的「新留出集」是同一件事，题面与真值要在 Mac 上定。

**P2**

- 拆超长函数（32 个超过 300 行，最长的 `_run_turn_ledgered` 有 2,279 行）。拆之前先补行为快照测试，单独立项。
- 把收据移出 git：`docs/verification` 占了 git 体积的 46%。这要改 CI、改交接纪律，需要用户决定。
- 给 AGENTS.md / lessons 瘦身，分「每次必读」和「按需查」两层。这会影响所有代理的行为，需要用户决定。
- 非生产循环移出主进程。
- Linux 全量复跑后只剩一个红因（§2.2）：沙箱的 Python 3.11 解析不了 3.12 语法（`skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py:172`；`scripts/calc_case_acceptance.py:273` 同类，但没有测试在收集期加载它）。项目钉的是 3.12，不必改。以后若在 Linux 上接 CI，用 3.12 即可全绿。

## 5. 复现

```bash
FWP_ALLOW_ANY_PYTHON=1 python scripts/prediction_ledger_status.py --as-of 2026-09-30
FWP_ALLOW_ANY_PYTHON=1 python scripts/check_model_admission.py --expect-model kimi-k3 \
  docs/verification/2026-09-21-judge-mode-k3/evidence/production-verification/runs
FWP_ALLOW_ANY_PYTHON=1 python -m pytest -q tests/test_skill_view_supersession.py \
  intelligence/tests/test_llm_rate_limit_retry.py intelligence/tests/test_model_admission.py \
  tests/test_prediction_ledger_status.py intelligence/tests/test_rejudge_pending_isolation.py \
  intelligence/tests/test_model_harness_2x2.py tests/test_check_regex_routes.py \
  tests/test_swap_lock_platform_probe.py tests/test_daily_full_preflight.py
FWP_ALLOW_ANY_PYTHON=1 python scripts/check_regex_routes.py          # 正则路由棘轮
FWP_ALLOW_ANY_PYTHON=1 python scripts/check_swap_lock_platform.py    # Mac 上应 exit 0
```

在 Mac 上用 `.venv-workbench/bin/python` 执行即可，不需要 `FWP_ALLOW_ANY_PYTHON`。

## 6. 待入账条目（草稿；号在 Mac 上领）

台账自 09-16 起没有新条目，而本分支做了五处修复，按台账纪律每处都该有一条可证伪的预测。号**不在沙箱里领**：登记簿 `~/.finance-runtime/ledger-id-claims.jsonl` 与 `gitea/main` 都在 Mac 上，沙箱领号有撞号风险。在 Mac 上逐条执行：

```bash
.venv-workbench/bin/python scripts/claim_ledger_id.py claim --branch arena/01a0f120-finance
```

领到号后把下表对应行抄进 `docs/prediction-ledger.md` 的 Open 表，ID 列换成领到的号，outcome 写 `pending`。来源都不是标准四阶段分诊，所以来源列写明了溯源（台账规则：这类条目只有 fix_type 与预测可用于连击统计）。

| ID | 来源 | fix_type | verification_prediction | 怎么验 |
|---|---|---|---|---|
| （待取号） | **溯源：非标准四阶段分诊**——2026-09-30 部件质检 §3-①（skill 视图错位） | `ROUTING_FIX` | 在 Mac 上开 5 个新会话，分别问均线、涨停复盘、自选股 MA 类问题：5/5 加载 `stock-technicals`，0 次加载被取代的 `up-line` / `watchlist-ma` / `top-gainers-feishu` | `tests/test_skill_view_supersession.py` 管结构；5 次会话的 skill 加载记录管行为 |
| （待取号） | **溯源：非标准四阶段分诊**——同上 §3-②（429 限流） | `HARNESS_FIX` | 上线后 14 天内，生产 episode 中 `provider_rate_limited` 失败数不到上线前 14 天的一半；同期 `deadline_exhausted` 最多多 2 次（等待不能挤掉作答时间）。前提是上线前 14 天至少有 4 次限流；不到 4 次说明样本不够、无法证伪，按过期规则写 `expired` 关闭 | 按 failure_class 数 `~/.finance-runtime` 下的 episode 产物，窗口取上线日前后各 14 天；失败原因里「限流：服务端要求 N 秒后再试」的 N 应与响应头一致 |
| （待取号） | **溯源：非标准四阶段分诊**——同上 §3-③（生效模型准入） | `EVAL_ONLY` | 对 09-16 以来的验收收据逐份跑准入检查，至少 1 份错配。已知候选：09-29 GLM 重写消融，声明 glm-5.3，实际跑的是 flash。此后新验收收据 100% 附准入判定 | `scripts/check_model_admission.py --expect-model <收据声明的模型> <产物目录>` 批跑；抽查 acceptance-workflow §2 第 3 条是否执行 |
| （待取号） | **溯源：非标准四阶段分诊**——同上 §3-④（台账过期规则） | `EVAL_ONLY` | 规则生效后 14 天（10-14），「过期待处理」从 101 行降到 50 行以内；降下来的每一行要么写了实际 outcome，要么写了 `expired` 且同格有不再验的理由 | `scripts/prediction_ledger_status.py --as-of 2026-10-14`；检查 `expired` 行的理由是否齐全 |
| （待取号） | **溯源：非标准四阶段分诊**——同上 §3-⑤（测试泄漏进「待重判」队列） | `EVAL_ONLY` | 在 Mac 上跑一次全量 pytest，`~/.finance-runtime/rejudge-pending/index.jsonl` 前后行数不变。修复前的同一操作在沙箱实测新增 138 行 | 全量前后各 `wc -l` 一次 |
| （待取号） | **溯源：非标准四阶段分诊**——同上 §3-C（模型 × harness 2×2 预注册）。**开跑当天再领号**，不要提前 | `EVAL_ONLY` | 预注册 H1：ΔM 可判，方向是 Claude 优于 `glm-5.3-flash`，且 \|ΔM\| > \|ΔH\|（08-27 的差距主要来自模型） | `scripts/model_harness_2x2.py analyze runs.jsonl --plan plan.json`，判定只取工具输出；H1 成立写 `confirmed`，不成立写 `refuted`，任一格不完整则按预注册 §7 只报可算的差 |
