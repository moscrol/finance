# 工单 #39：工具面收尾三小件——#567 工具窗地板前向合并、#568 候选口两臂读数、`sub_research` 分支 × 全局 worker 争用量测

> 日期：2026-09-08
> 上游：`docs/handoffs/inflight/main.md`（09-03 段「两项待用户拍：`would_grant<1s` 时无地板工具照旧可见；`kb_search` 刚预热首查超时」）；`docs/handoffs/inflight/feat-sub-research-tool.md`（「未验证 / 已知边界」：分支 ×3 与全局 8 worker 争用未量；sol 12/12 不交 PLAN）；`docs/verification/2026-09-07-branch-level-trace.md`（§6：每批帽 4 在第 3、4 遍一次都没咬，**帽 4 不动的决定不变**；§7 未做 / 待拍）；`2026-09-03-subagent-tool-design.md`
> 优先级：P1（三件都小；都是 09-03 能力放大线的遗留，拖着会一直占 PR 列表）
> 规模：小单（各半天；#568 的 live 两臂要额度，先看 `quota-pool-state.json`）
> 分支：#567 / #568 在各自分支上前向合并；量测走 `docs/sub-research-contention-0908`
> 依赖：无。**两处要用户拍**：#567 合不合、#568 合不合（都改生产行为）
> ⚠️ 已排除的假方向：`sub_research` 的 quick 每批帽 4 **不是**瓶颈——09-07 四遍 live 里第 3、4 遍模型每批只点 1 个工具，帽一次没咬；分支 partial 的真因（分支契约无 `required_outputs`）已由 `64428242` 修掉。本单**不碰帽 4**，任何「把帽调大试试」的提议要先拿 `rejected_by_cap > 0` 的收据

---

## 0. 一句话

工具面近两周上了 `sub_research`（模型可点的子研究，live n=1 好）、`web_fetch`、`min_window_seconds` 菜单裁剪、max 档三开关、分支预算与保险丝。剩三件没收口：#567 给 `web_search / news_search / web_fetch` 补 5s 零授予护栏（main 的 `MIN_WINDOW_SECONDS` 只有 `kb_search / evidence_search / sub_research` 三条，**没被后来的提交覆盖**，但与 main 在同一个 dict 和同一个测试文件上冲突）；#568 让 deep 升档不必经模型 PLAN（sol 12/12 不交 PLAN，这条路在 sol 上是死的）；`sub_research` 三支并行与全局 8 个 worker 争不争，没量过。

---

## 1. 现状 [实测 2026-09-08]

| 件 | 现状 | 差距 |
|---|---|---|
| #567 `feat/tool-window-floors` @ `2c31f363`（09-03） | 改 `research_tool_registry.py:MIN_WINDOW_SECONDS` 加三条 5.0（注释写明：`web_search` p95 4.76 → 5.0 压住；`news_search` p50 1.53 / p95 8.68 → 有意给 5.0 当零授予护栏而非 p95 保证；`web_fetch` 无样本 → [推断] 同族 5.0）+ `test_episode_tool_batch.py` 102 行测试 | `conflict-check`：`research_tool_registry.py`（main 后来在同一 dict 加了 `sub_research` 行）与 `test_episode_tool_batch.py` 两处冲突；behind main 很多。**内容仍有效**：main @ `8e452e72` 的 `MIN_WINDOW_SECONDS`（`:1366`）没有这三条 |
| #568 `feat/deep-observable-without-plan` @ `18922dcf`（09-03） | 治理侧按 observable 信号自行发起 deep 升档 | `conflict-check` clean 但 behind main 很多；改生产行为，09-03 后 max 档 / 分支预算 / 判官窗都变过，**旧的 live 读数不能沿用** |
| `sub_research` 争用 | 分支 ×3 并行；全局工具线程池 8 worker（`feat-sub-research-tool.md`）；`runtime/sub_research.py:BranchBatch` 有「派发时钟三元组取自本批第一条 `tool_request`」 | 没有一份收据回答「分支等 worker 等了多久」；父臂在分支跑时是否也在派工具、抢同一个池 |

---

## 2. 三件

### 2.1 #567 前向合并 + 门禁（半天）

1. 在 `feat/tool-window-floors` 上 `git merge gitea/main`；`MIN_WINDOW_SECONDS` 冲突解法：**四条都留**（`kb_search / evidence_search / sub_research` + 三条 5.0），注释块保留 #567 那段「零授予也是一种授予」的实测依据；`test_episode_tool_batch.py` 冲突按两边测试都保留解。
2. 重新核一遍地板数字是否仍成立：从最近 7 天 8792 的工具收据（`~/.finance-runtime/live-probe-traceability/` 与 episode 收据）重算三条工具的 p50 / p95；若 `web_search` p95 已 > 5.0，数字改并写理由；`web_fetch` 若已有样本，把 [推断] 改成 [实测]。
3. 门禁（干净树、`.venv-workbench`）绿 + `conflict-check` clean → 交接写「等用户拍：合不合」。合入后**不单独切 8792**，随下一次切流带上（零授予护栏是行为改动但只影响「菜单上少一个必超时的项」，回滚粒度跟着下一刀走即可；交接里写明）。

### 2.2 #568 前向合并 + 候选口两臂读数（半天 + 额度）

1. 同法前向合并、门禁。
2. **候选口 8799**（不是 8792）起 #568 版本，同题两臂各 n=3：臂 A = main（PLAN 路径）、臂 B = #568（observable 升档）。题用 09-07 那道候选口同题（`branch-level-trace.md` §4），模型 `gpt-5.6-sol`（12/12 不交 PLAN 的那只）。读数只看：deep 是否可达（`served_tier`）、`judge passed` 数、`degrade_count`、`partial` 数、父臂 input_tokens、墙钟。**不出结论词**，六格表交用户拍。
3. 额度：先读 `quota-pool-state.json`；5h 窗 < 40% 不跑，写进交接等窗口。

### 2.3 `sub_research` 分支 × 全局 worker 争用量测（半天）

1. 先从**已有收据**算：`BranchBatch` 时钟三元组（本批第一条 `tool_request` 的 requested / dispatched / finished）能否算出「等 worker」= `dispatched − requested`。能 → 对 09-07 四遍 + 09-08 任一遍的收据算出分支每批等待的 p50 / p95，与父臂同期是否在派工具（父臂 `tool_request` 时间戳重叠）并排。
2. 算不出（字段不够）→ 在 `BranchBatch` 加 `queue_wait_seconds`（从事件流重算，worker 不自报——沿 `test_branch_usage_comes_from_child_budget_not_worker_claims` 同一纪律）+ 1 个测试；**不改任何池大小、不改 ×3**。
3. 读数进 `docs/verification/2026-09-08-sub-research-contention.md`：若 p95 等待 < 1s，写「争用不是变量，关闭此项」；若 ≥ 分支单批工具 p50 的 20%，写候选处置（分支池独立 / 父臂让位 / 降到 ×2）交用户拍，**本单不实施**。

---

## 3. 验收

1. #567：`conflict-check clean`、门禁绿、`MIN_WINDOW_SECONDS` 六条齐全、三条数字有 [实测]/[推断] 标注与来源收据路径；交接写「等用户拍」。
2. #568：`conflict-check clean`、门禁绿；六格两臂表（或「额度不足未跑」+ 窗口时间）进收据 `docs/verification/2026-09-08-deep-observable-two-arm.md`。
3. 争用：一份收据回答「分支等 worker p50 / p95 多少、与父臂派发是否重叠」，或明确写「现有字段算不出，已加 `queue_wait_seconds`（PR #…）」。
4. 三件都没有改 `batch_call_cap`、worker 池大小、分支并行度（`git diff` 证明）。
5. 干净树全量 `ruff 0` + 红集不大于基线（改代码的那件）。

---

## 4. 非目标 / 红线

- ❌ 不动 quick 每批帽 4；不动 8 worker 池；不动分支 ×3——量完交用户拍。
- ❌ 不在 8792 跑两臂；候选口 8799。
- ❌ 不合任何 PR（`gitea_pr.py merge --yes` 要用户确认）。
- ❌ #659（写作成本进预算）的 n=6 验收判据**不在本单**，留给 #657 / #659 作者。
- ❌ 不把「地板数字」调成 p95 保证——#567 注释明写 5s 是零授予护栏；改语义要另立。

---

## 5. 教学注

- **零授予护栏 vs p95 地板**：`kb_search` 的 20s 地板说的是「这活本来就要那么久」，装不下就别上菜单；`web_search` 的 5s 说的是「授 0 秒等于骗模型点一个必超时的工具」。两种地板数字来源不同（前者 p95，后者只要 > 0 且不遮掉常见成功），混成一个语义就会像 `news_search` 那样在 p50 1.5s / p95 8.7s 之间无解。
- **先量再动**：09-07 那条线连续四遍 live 才发现分支 partial 的真因是契约缺 output 而不是帽——如果第一遍就把帽调大，真因会被掩盖且读数变得不可比。争用这件同样：先从已有事件流算等待，算不出再加字段，加了字段再决定动不动池。
- **候选口 vs 生产口**：8799 起一个候选版本跟 8792 同题并跑，是「金丝雀」的单机版：同一数据、同一题、两份代码，差异只来自代码。在生产口上直接试改动，回滚要停服务，而且当天用户的读数被污染。

---

## 6. 交接要求

- #567 / #568 各自的在途交接文件更新（已有 `feat-capability-*.md` 族的话追加，不另建）；争用收据一份。
- `inflight/main.md` 09-03 段那两项「待用户拍」改指向本单的收据路径。
