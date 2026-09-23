# 2026-09-22 自适应研究回路 · 传输层绝对截止复核（工单 #72）

接手方独立复核，不复用作者收据。被测提交 `aa0509d61fb063be6fd2d2ac3ddc15732e6fd16e`（分支 `feat/adaptive-research-loop`），
隔离树 `~/fwp-wt-adaptive-deadline-0922`（`git worktree add --detach … aa0509d61`，首尾 `dirty=false`），
解释器 `~/finance-workspace-private/.venv-workbench/bin/python`，独占 `basetemp`，开跑时 load 5.18。
原始日志根 `~/.finance-runtime/adaptive-deadline-0922/`。

当前读数以「`7ad61a0d3` 三次前向」节为准，早期读数保留为历史。文档合流 `a663ec524` 已包含 main@9a0227986；全量收据仍绑定 `7ad61a0d3`，不是在文档 head 上重跑取得。

## 目标 1：严格探针（13 场景）

`PYTHONPATH=. python scripts/review_probes/diagnose_llm_timeout.py --assert-deadline --output strict-deadline.json`
→ **exit 0，`deadline_violations: []`**，本目录 `strict-deadline.json`（容差 0.2 s，`source_before == source_after`）。

| 场景 | 获批 | 实测墙钟 | 台账 status/reason |
|---|---:|---:|---|
| fast | 0.8 | 0.109 | success |
| header_delay | 0.8 | 0.805 | failed/timeout |
| body_stall | 0.8 | 0.802 | failed/timeout |
| headers_then_body | 0.8 | 0.808 | failed/timeout |
| body_trickle | 0.8 | 0.808 | failed/timeout |
| tools_stream_trickle | 0.8 | 0.805 | failed/timeout |
| tools_stream_partial_line | 0.8 | 0.806 | failed/timeout |
| synthesis_stream_trickle | 1.2 | 1.214 | failed/timeout |
| synthesis_stream_partial_line | 1.2 | 1.211 | failed/timeout |
| zero_deadline | 0.0 | 0.000 | 无请求、无预占 |
| judge_window_stalls | 0.8 | 0.807 | failed/timeout |
| judge_late_report | 0.8 | 0.812 | failed/timeout |
| judge_root_expired | 0.0 | 0.000 | 无请求 |

作者在 `a9ba35159` 上测到的 7 个越窗（+0.25 ～ +3.16 s）在 `aa0509d61` 上全部归零；接手方独立复现，与作者
`final-strict-deadline.json` 结论一致。非流式场景 `content_present=False`，流式场景 `emitted_chars>0` 但正文未被采纳。

## 目标 2：判官迟到回包

`judge_late_report`（批 0.8 s、对端 ~2.9 s 才吐完）：`report_received=False`、`unavailable=True`、
台账唯一一行 `status=failed / reason=timeout`、`request_count == reserved_count == len(records) == 1`、
`remaining_root_seconds=8.79`（根预算按实际消耗扣，不再按「对方守约」记）。
常规回归 `test_real_late_judge_report_is_rejected_at_the_transport_boundary` 守这一条。

## 验收「阳性对照」：变异存活 → 补用例 → 杀死

工单要求：把 `_open_deadline_http_response` 的 `deadline` 改为不传，至少一条**常规** pytest 用例红。

| 步骤 | 命令 / 改动 | 结果 |
|---|---|---|
| 变异 | `llm_refine.py:222` `deadline=deadline` → `deadline=None`（`git diff` 1 行） | — |
| 定向套件（作者版 25 条） | `pytest intelligence/tests/test_llm_timeout_diagnostic.py` | **25 passed，变异存活** |
| 广域（另 13 个引用传输层的测试文件） | `pytest conformance_transport test_ask_call_provenance … test_served_model_receipt` | **351 passed，变异存活** |
| 补用例 | 新增 `test_refine_wrapper_forwards_the_shared_deadline_to_the_transport`：单发片 10 s、共享截止 0.5 s、对端 ~2.9 s 滴流，断言 `LLMDeadlineExceeded` 且墙钟 < 2 s | 变异下 **1 failed（DID NOT RAISE）** |
| 还原 | `git checkout -- intelligence/services/llm_refine.py`，sha256 `ff587c50…a424` 与 `HEAD` 一致 | 26 passed，ruff 通过 |

为什么此前无人守：探针与 `test_call_timeout_never_outlives_the_shared_research_deadline` 里「单发片」与「共享截止」
两个值要么相等、要么直接驱动传输层绕过了包装函数，所以丢掉包装函数里的 `deadline=` 转发对它们不可见。
两个入参在所有夹具里同值时，删掉其中一个的变异一定存活——阳性对照必须让这两个值分开。
（同族原则：`~/agent-memory` 的 `two-defence-layers-need-two-separate-assertions`。）

变异全程 `PYTHONDONTWRITEBYTECODE=1`，日志 `mut-broad.log` / `mut-newtest.log` / `post-restore-targeted.log`，
sha256 见 `llm_refine.head.sha256` / `llm_refine.restored.sha256`，结构化记录见本目录 `mutation-record.json`。

## 工单步骤 1 的「2 个未提交路径」处置

工单以 22:20 的分支状态为起点，当时树上 2 个未提交路径。接手时（23:39）作者树 `~/finance-worktrees/adaptive-research-loop`
`git status --short` 为空；`git show --stat aa0509d61`（22:35）恰好只含 `docs/handoffs/2026-09-22-adaptive-deadline-transport.md`
与 `docs/handoffs/inflight/feat-adaptive-research-loop.md` 两个文件。判定：那 2 个路径已由作者以 `aa0509d61` 提交，无需另行落盘。

## 非目标（按工单原样未动）

未改 T900 / 75 / 150 预算；未开 `derived_calculation`；未碰数字门单位错位（issue #852）；未跑真实模型；
未给 `--assert-deadline` 探针加容忍；未动生产 8792。

## 合流尖四叶门禁

`c582d6755` 之上 `--no-ff` 合入 `gitea/main@f24a61a8a` 得 `013eb5c4a`（merge-tree 预检 0 冲突），隔离树 `checkout --detach 013eb5c4a`
跑一次性执行器 `~/.finance-runtime/adaptive-deadline-0922/run_gate.py`（三叶并行、不 fail-fast、每叶记首尾身份与日志 sha256），
收据根 `~/.finance-runtime/adaptive-deadline-0922/gate-013eb5c4a/`，`summary.json` 是索引，九项 exit 0、每叶首尾身份一致：

| 叶 | 读数 | 收据 |
|---|---|---|
| ruff | exit 0 | `ruff.run.json` |
| pytest 全量 | **12879 passed / 85 skipped / 2 xfailed**，exit 0，2030 s（load 9.3 → 16.6，机器上另有两位 agent 的全量 pytest） | `pytest-full.pytest-receipt.json`（`check_test_receipt.py --expect-revision 013eb5c4a…` ✅ 可采信）、`pytest-full.xml` |
| 前端六步 | install / lint / typecheck / test（110 passed，8 文件）/ build / E2E（34 passed / 2 skipped）全 exit 0，端口 19971/19974 | `frontend/frontend.json` |
| registry ×4 + ledger-spec-crosswalk | 五项 exit 0 | `registry-*.run.json`、`ledger-crosswalk.run.json` |
| 严格探针（合流尖） | exit 0，`deadline_violations: []` | `strict-deadline.json`（副本：本目录 `strict-deadline-013eb5c4a.json`） |

当轮验收文档 head 相对 `013eb5c4a` 只有 docs；后续代码前向已另跑门禁，见下文，不沿用这张旧收据。

## 二次前向（00:31 main 合入 #863 之后）

PR #868 开出后 `conflict-check` 变红：`gitea/main@8e7989372`（#863 研究尾单三线合流 squash）与本枝 4 文件冲突。在作者树 `--no-ff` 合入得 `3020e42df`：

| 文件 | 冲突 | 解法 |
|---|---|---|
| `intelligence/runtime/continuous_turn_adapter.py` | 1 hunk | 取 main：`rejected_claims` 同时带 `claim_index:*` 与 `delivery_repair_notes` |
| `intelligence/services/finance_query.py` | 1 hunk | `__all__` 两侧新名都留（`result_has_date_axis` + `validation_diagnostic`） |
| `intelligence/services/episode_semantic_verifier.py` | 3 hunks | hunk1 两侧新函数族都留（main 的 `_retained_delivery_hashes` / `_recheck_research_delivery` + 本枝 `semantic_repair_feedback` 族），补回被共享尾巴吞掉的 `)`；hunk2 两侧新局部量都留；hunk3 取 main 的归一化 + 标题/条件段逻辑，保留本枝的 E-token / 季度 token 剔除 |
| `scripts/review_probes/run_extraction_mutations.py` | 8 hunks | 以 main 的 `SUITES` / `_parse_args` 结构为底，加入本枝 `stock-amount` / `finance-absence` / `finance-return` 三套件与独占 `--basetemp`；main 的 `tests/test_mutation_runner_selection.py` 照过 |

**语义冲突一处**：#863 的新测 `test_research_delivery_repair.py::test_same_turn_repairs_without_extra_fetch_or_restoring_false_inference` 直接把第二次模型请求当 `REPAIR_GOAL` 读（12 个 `reserved` 参数化全红，`KeyError('evidence')` 被运行时吞成 `sdk_run_failed`）；本枝 `3c30eceb9` 起把修复目标包进 `REPAIR_CONTEXT` 信封（`repair_goal_message` + `evidence` 行随信封走）。解法：测试解信封后再断言，**产品行为未改**（与本枝 `test_continuous_turn_adapter.py:2101` 同一解法）。
定向回归（verifier / adapter / repair / harness / runner-selection / timeout 等 10 文件）**641 passed / 1 skipped**，ruff 0，日志 `merge2-fix3.log`。

### `3020e42df` 四叶重门禁：8/9 绿 + 全量 pytest 4 红

`gate-3020e42df/`：ruff、合流尖严格探针（0 越窗）、registry ×4、crosswalk、前端六步（118 单测、E2E 34P/2S，00:48 跑，Playwright 浏览器当时在；01:55 磁盘清理把 `~/Library/Caches/ms-playwright` 删了，此后复跑前端要先 `pnpm exec playwright install chromium`）全 exit 0。
全量 pytest 第一次在 83% 被系统低内存杀掉（01:00，磁盘一度只剩 416 MiB，机上 9 个 pytest 并发）；01:47 重跑得 **14612 passed / 4 failed / 85 skipped / 2 xfailed**（1544 s，日志 `pytest-full-rerun.log.txt`，收据 `pytest-full-rerun.pytest-receipt.json`）。4 红都是 #863 新测撞本枝改动，修在 `b7a479e6a`：

| 红 | 根因 | 解法（产品行为改动？） |
|---|---|---|
| `test_episode_numeric_citations::test_non_citation_numeric_tokens_are_not_exempted[E0]/[E027]` | 本枝 `00d35ae80` 的裸 E-token 剔除 `E\d{1,3}` 把 `E0` / `E027` 也当引用免检；main 的引用语法 `strip_evidence_ordinals`（`[1-9][0-9]{0,2}`）已覆盖真实引用 | 删本枝那一行与常量，main 语法为唯一事实源（**是**：`E0`/`E027` 这类非引用 token 不再免检，与 main 一致；本枝「（E6）/ Q3 不算数量」测试照过） |
| `test_model_turn_completion_boundary::test_transport_preserves_truncation_reason[False]/[True]` | 该测 `patch` 的是 `urllib.request.urlopen`，本枝 HTTP 边界已是 `llm_http_transport` 子进程 worker，假响应进不去、真去连假域名报 `URLError` | 改走 `llm_refine.http_transport_override`（本枝文档化的测试缝）注入 `nullcontext(response)`（**否**） |

定向六文件 471 passed、ruff 0（`merge2-fix4.log`）。

### `b7a479e6a` 四叶：九项全绿（PR #868 的代码尖）

`gate-b7a479e6a/`，隔离树 `checkout --detach b7a479e6a`、首尾干净：

| 叶 | 读数 | 收据 |
|---|---|---|
| ruff | exit 0 | `ruff.log.txt` |
| pytest 全量 | **14616 passed / 85 skipped / 2 xfailed**，exit 0，1753 s（load ~11–14） | `pytest-full.pytest-receipt.json`（`check_test_receipt.py --expect-revision b7a479e6a…` ✅ 可采信）、`pytest-full.xml` |
| 前端六步 | 全 exit 0：单测 118 passed、E2E 34 passed / 2 skipped（Playwright 浏览器由另一会话 02:3x 装回后才跑） | `frontend/frontend.json` |
| registry ×4 + crosswalk | 五项 exit 0 | `registry-*.log.txt`、`ledger-crosswalk.log.txt` |
| 严格探针 | exit 0，`deadline_violations: []` | `strict-deadline.json` |

`registry-tables` / `registry-views` 第一次 exit 2 是我的 shell 把 `backfill-tables --check` 当成一个词传给 argparse（zsh 不分词，同 `~/agent-memory` 的 `zsh-no-word-split-fakes-a-gate-red`），不是树红；拆词重跑 exit 0，两个日志都留了。
`3020e42df..b7a479e6a` 只改 `episode_semantic_verifier.py` 一行常量 + 一处剔除、以及一个 Python 测试，前端叶在两尖都独立跑过。

### `7ad61a0d3` 三次前向：最新 main + 合流尖四叶重门禁

在 `24ada4f80`（父提交 `7deedffba` 与 `gitea/main@3b7e473575`）之后，`gitea/main` 又前进到 `760248ece`（#873 证据归档收口）。本机 `git merge-tree --write-tree` 预检无冲突，再以 `--no-ff` 前向得到 `7ad61a0d3fd9ee63abe2089a4049a0a1b4a8bc16`。冲突测试同时保留 main 的 `complete=False/True` 覆盖与本枝的 `llm_http_transport.urlopen` mock seam；合流相关定向回归 **63 passed**。

隔离树 `/Users/a77/.finance-runtime/reviews/pr868-forward-20260923/finance-workspace-private` 首尾干净，收据根 `~/.finance-runtime/reviews/pr868-forward-20260923/gate-7ad61a0d3/`，九项均 exit 0，所有叶首尾 revision/status 稳定：

| 叶 | 读数 | 收据 |
|---|---|---|
| ruff | exit 0 | `ruff.run.json` |
| pytest 全量 | **14921 passed / 85 skipped / 2 xfailed**，17 warnings，1108 s | `pytest-full.pytest-receipt.json`（revision == `7ad61a0d3`，解释器 / 依赖指纹 / 干净树 ✅） |
| 前端六步 | 全 exit 0：单测 **120 passed**（8 文件），E2E **34 passed / 2 skipped** | `frontend/frontend.json` |
| registry ×4 + ledger-spec-crosswalk | 五项 exit 0 | `registry-*.run.json`、`ledger-crosswalk.run.json` |
| 严格探针 | exit 0，`deadline_violations: []` | `strict-deadline.json` |

最新代码核对还发现 `_open_deadline_http_response` 实际有 **5 处**调用（`llm_refine.py:1167,1219,1424,1546,2304`），均带 `deadline`；其中流式路径另带 `is_cancelled`。此前 PR 描述的「四处」已在更新后的主张清单中改正。该合流尖之后若再产生提交，只允许 docs；门禁读数不自动外推到新的代码提交。

### `a663ec524` 后续文档前向：main@9a0227986

门禁完成后，`gitea/main` 又前进到 `9a0227986`（#858 工单收口与 #879 文字修订）。本枝以 `--no-ff` 前向；唯一冲突是共享 `QUEUE.md` 的 add/add，已保留 main 的 #67/#69 行与本枝的 #72 行，得到本地合流提交 `a663ec524747351531f6d567d860596fdd6f6551`。`git diff --name-only 7ad61a0d3..a663ec524` 全部为 `docs/`，没有代码变化，因此 `7ad61a0d3` 的四叶收据仍是当前代码尖的收据；最新 PR head 只会再多 docs 提交。

## 附加变异（非验收项）：`is_cancelled=` 转发也无人守

同法把包装函数的 `is_cancelled=is_cancelled` 改为 `is_cancelled=None`，跑 `test_llm_timeout_diagnostic.py`、`test_llm_refine_tool_stream.py`、
`test_conversation_orchestrator.py -k cancel`：**15 passed，变异存活**（`mut-cancel2.log`；还原后 sha256 与 HEAD 一致）。
原因同上：`llm_refine` 读流循环每行自查 `is_cancelled()`，现有取消测试都在「有行到达」时取消；传输层 0.05 s 轮询取消只在**停顿期**才有区别。
本单不补代码（不在验收项、会让门禁过的代码尖再漂一层），配方留给下一刀：`body_stall` 端点（1 字节后停 1.6 s）+ 0.3 s 后翻真的 `is_cancelled`，
片 / 截止都给 10 s，经 `_open_deadline_http_response` 断言 `LLMStreamCancelled` 且墙钟 < 1 s；变异下应读到停顿结束才返回（DID NOT RAISE）。

## 交 #76（L6 自适应回路真实改稿复核）条件卡

09-23 离线预检见 `../2026-09-23-adaptive-l6-preflight/README.md` 与 `protocol.draft.json`：#72/#75/#76 的合前/合后顺序存在冲突，候选预合入验收须用户批准修订；独立模型/数据授权尚未给出。下述历史旁车 8797 落在 #76 新禁用端口范围内，不能原样复用；正式执行需选择 8780--8830 之外的端口并完成冻结/收尾。当前只完成旧记录提取，不是自然验收通过。

- **前置**：最新合流代码尖 `7ad61a0d3` 的严格探针 exit 0、0 越窗（早期 `aa0509d61` / `013eb5c4a` 读数仅为历史）；`judge_late_report` 类迟到回包由常规回归守为 `failed/timeout`，零采纳。
- **固定 SHA**：按 #76 表原文以「#72 合入后的 `gitea/main` SHA」为准；合入前候选 = 本 PR head，被门禁的代码尖 `7ad61a0d3`（当前相对代码尖仅有 docs 差异；开跑前重新核对）。开跑前冻结代码与数据，`protocol.json` 记 revision、`dirty=false`、各 canonical `fact_*` 的 `max(trade_date)`。
- **三题冒烟原题**（逐字，来源 `~/.finance-runtime/adaptive-live-smoke-20260921{,-q2,-q3}/probe/protocol.json`）：
  1. 寒武纪(688256.SH)这轮行情，给我一组可证伪的跟踪条件：需要哪些指标达到什么数值才算逻辑兑现，出现哪些数值算证伪。每个数值请标明它的来源和对应日期。（全工具）
  2. 只用本地已有资料，不联网：东阳光(600673.SH)9月以来的量价表现如何，与所属板块相比强弱如何？给出具体数值、日期和数据来源；本地没有的部分单独列出，不要补。（`local_only` 四只读能力）
  3. 固态电池题材这轮行情发酵到哪一步了？给我一组可证伪的跟踪条件，每个数值标明来源和日期。（theme_track，全工具）
- **预算（不改）**：环境根 T900 s；Episode 研究额度 600 s；单发帽 75 s；修订额度 30 s；判官每次核验共享窗 150 s；不开 `derived_calculation`。
- **模型与入口**：沿用 `docs/handoffs/2026-09-22-adaptive-absence-live.md` 协议——写手 `kimi-k3`（隔离旁车 8797、密钥内存传递、`remember=false`），独立判官 `glm-5.3-flash`；单臂 `off`，每题首发 1 次、重发 0；复用 `scripts/compare_adaptive_research.py` 的 POST 会话/消息入口，隔离 users / Episode / 待重核索引；不碰生产 8792。
- **判定项（#76 L6 原文）**：改稿轮 ≥ 1；改后**有证据的**数值条件句零误删（单位错位属 issue #852 那张单，出现即记 `BLOCKED_BY_852`，不改判、不顺手修）；trace 里迟到判官回包必须是 `failed/timeout`，出现 `success` 即 L6 不过。
- **必须写进协议的代价**：每次 HTTP 调用多一次子进程启动（空闲 ~0.15 s、高负载 >0.35 s，计入调用预算）。对 75/150 s 窗口占比 1–3%，不影响判定；但**机器 load > 20 时不要开跑**（作者实测 load 40 下亚秒窗口提前失败）。批前先探网关 `chat/completions`。
- **不刷绿**：`adaptive-absence-live` 记的东阳光内容错（板块累计涨跌幅、强弱方向反转）依然成立，本单一个字没动内容层；#76 复跑第 2 题是新预注册样本，不覆盖旧原件。

## 交 #75（第二方 Spec + Quality）需求

- **候选**：PR #868 的当前 head 见 PR；被门禁的代码尖 `7ad61a0d3`；`git diff --name-only 7ad61a0d3..<head>` 应只有 `docs/`。main@9a0227986 已由文档合流 `a663ec524` 纳入。
- **候选检出路径（绝对）**：`/Users/a77/.finance-runtime/reviews/pr868-forward-20260923/finance-workspace-private`（加锁隔离树，只读引用；审查者应自建树）。
- **证据目录**：最新四叶 `~/.finance-runtime/reviews/pr868-forward-20260923/gate-7ad61a0d3/`；历史复核与变异 `~/.finance-runtime/adaptive-deadline-0922/`；作者侧 `~/.finance-runtime/adaptive-advance-20260922/`；早期审计 `~/.finance-runtime/adaptive-closeout-20260922/`。
- **主张清单来源**：PR 描述「主张清单」节（Spec 轴输入）。
- **Quality 轴建议探针**：复跑本目录 `mutation-record.json` 的变异；对 `llm_http_transport.urlopen` 复跑作者 M1（父侧截止关）/ M2（子侧硬停关）/ M4（共享截止 `min` 忽略）确认仍被杀。
- **本单未覆盖、请审查者留意**：`_open_deadline_http_response` 的 `is_cancelled=` 转发未做阳性对照；五处调用点的 `timeout` 片是否都经 `Deadline.slice()` 派生未逐点核。
