# 量纲口径契约 Phase 1–3 派单（判分器 / 题集 / 埋点）

- 日期：2026-08-18
- 派单人：本日 KC 批 C/D/E 验收方（完成十张合链、8792 链切至 `3af5c81f9595`、28 题跑测与 trace 分诊的 session）
- 接单人：下一个执行 agent
- 设计源：`docs/superpowers/specs/2026-08-18-measured-value-caliber-contract-design.md`
- 证据源：`docs/verification/2026-08-18-kc-acceptance-triage.md`（trace-first M1 分诊，`validate-report.sh` RC:0）
- 通用规程：`docs/workflows/acceptance-workflow.md`

## 范围

**做**：Phase 1（判分器止血）、Phase 2（题集契约）、Phase 3（埋点解锁归因）。三者**全部不动产品代码**。

**不做**：
- Phase 4（产品侧接线）——**必须等 Phase 1–3 出数后再排**。理由见 spec §5：尺子没修好之前动产品，等于拿读数不准的尺子指导施工。今天的「B7 回归」就是这样一个差点写进主干的误判。
- 不改题面语义（只补日期锚与附件，不改题目问什么）。
- 不新建第二份指标注册表。
- 不动 8792（本单无链切步骤）。

---

## Phase 1 — 判分器止血（`EVAL_ONLY`）

改 `intelligence/eval/acceptance_verdict.py` 与新增等价类文件。四项：

| # | 任务 | 落点 |
|---|---|---|
| 1.1 | 数值分支补中文数量级候选（万亿/亿/万 → 同量纲展开），**只加候选不改原值** | `_fact_rule` 数值分支，手法对齐既有 `_decrease_signed_numbers` |
| 1.2 | 拒答 alternatives 与 `must_mention` 同义词外置成 `intelligence/eval/cases/verdict_equivalence.json` | 与 `MetricSpec.aliases` 同一等价类语义；C1 的「无行情数据」「休市」进拒答类 |
| 1.3 | verdict FAIL 时附 `extracted_numbers`（前 20）与 `matched_aliases` | FAIL 分支；**本项价值最高，让「产品没答」与「判官没认出」一眼可分** |
| 1.4 | `pass_rule` 与 `expect_facts` 自洽门禁 | 新增 CI 断言；A7 是现成反例（`pass_rule` 写「之一」，`expect_facts` 要两个精确值同时命中） |

### Phase 1 验收 —— **零 LLM 成本，用同一份 artifact 复算**

这是本单最重要的性质：**不要重跑 28 题**。判定全部来自 `board` 对已冻结 artifact 的重新计算。

```bash
cd /Users/a77/finance-workspace-runtime   # 或你自己的验收 worktree
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
export FORESIGHT_USERS_DIR=/Users/a77/.finance-runtime/live-probe-traceability/users

$PY -m intelligence.eval.acceptance board --run intelligence/eval/runs/20260818T051630Z.json > /tmp/after-0818.txt
$PY -m intelligence.eval.acceptance board --run intelligence/eval/runs/20260815T1005Z-r5-clean-baseline-3.json > /tmp/after-0815.txt
```

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| **A. B7 转绿** | `20260818T051630Z` 的 `B7-volume-sentiment-evolution` 真值列 `❌ 失败` → `✅ 通过` | 仍失败，或理由变成别的 fact |
| **B. C1 转绿** | 同上，`C1-future-date-no-data` → `✅ 通过` | 同上 |
| **C. 其余 26 题逐题不变** | 与**已入库的改前基线** `docs/verification/baselines/2026-08-18-board-20260818T051630Z.txt` 逐题 diff 真值列，**除 B7/C1 外零变化** | **任何第三题发生变化 = 打回**。哪怕变好也要打回——那说明归一化改宽了，可能制造新的假绿 |
| **D. 08-15 基线同样只动这两题** | `after-0815.txt` 对照 `docs/verification/baselines/2026-08-18-board-20260815T1005Z-baseline.txt`，除 B7/C1 外逐题不变 | 出现第三题变化 = 打回 |
| **E. 正反双向单测** | `2.96万亿` **命中** `29569.03±1%`；`2.96亿` **不得命中** `29569.03` | 只有正向测试 = 打回（那不证明门有下限） |
| **F. 变异测试** | 把 1.1 的归一化那行**注释掉**再跑，B7 必须变回 `❌ 失败` | 抽掉实现测试仍绿 = **假门禁，打回**。先提交实现再做变异，别在未提交状态下改 |
| **G. 1.4 门禁自身可用** | 用 A7 当已知阳性样本，门禁必须报出它 | 门禁对 A7 沉默 = 它没有检出能力 |

> **判据 C 是本 Phase 的核心防线，不要跳过。** 本单最贵的教训就是「一份看起来干净的零回归结论，实际是拿 None 跟 None 比出来的」——字段名猜错，每格都是 `None`，脚本照样输出「回归 0 题 / 持平 28 题」。
>
> **所以 diff 脚本必须先自证读到了值**：两份基线各应解析出 **28 题、真值列非空 28 题**（本单已自检通过）。解析数不等于 28 就先修脚本，别看结论。真值列取 markdown 表的**第 5 列**。

---

## Phase 2 — 题集契约（`EVAL_ONLY`）

| # | 任务 |
|---|---|
| 2.1 | 9 道无日期锚题：把 `date` 拼进 `query`，或让 runner 把 `date` 作为显式时间上下文传入。**两种都不改产品** |
| 2.2 | B6 补附件（题面说「把**这份**卖方材料提纯」但无材料），或改判据为「应当要求澄清」 |
| 2.3 | A8/C6 相对时间题（「现在」「最近」）单独分组，不进主判定分母 |

**受影响的 9 题**：A3、B6、C3、A8、B1、B2、B3、B8、C6（本单实测：该组通过数 **0/9**）。

### Phase 2 验收 —— 需要重跑，走旁路 sidecar

```bash
$PY scripts/live_probe.py start-sidecar --port 8796 --repo-root /Users/a77/finance-workspace-runtime
# 等 /api/health 的 runtime.source_revision 与被测树一致后：
FORESIGHT_USERS_DIR=/Users/a77/.finance-runtime/live-probe-traceability/users \
  $PY -m intelligence.eval.acceptance run --base http://127.0.0.1:8796 --user live-probe
```

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| **H. 题面改动可追溯** | 改动前后题面 sha256 各一份入台账，逐字 diff 附在 PR | 只说「改了日期」不给 diff = 打回 |
| **I. 可判子集分母上升** | 真值口径行的「可判子集」从 `4/16` 的分母 **16 升到 ≥22** | 分母没升 = 2.1 没生效，查 date 有没有真下达到产品 |
| **J. A3 拿到正确收盘价** | A3 答案含 `12.11`（A6 已证同一份数据可得，是现成对照） | 仍答 `14.40`（08-17 收盘）= date 没到产品 |
| **K. 带日期的 19 题不变差** | 该 19 题真值列无一题下降 | 任一题下降 = 打回 |
| **L. 前置检查不得 `--force`** | runner 的 preflight 必须自然通过 | 用 `--force` 绕过 = 打回。本单踩过一次：客户端 `FORESIGHT_USERS_DIR`（`~/.zshrc` 那份 `agent-memory/.foresight`）与 sidecar 的不一致，**要修好再跑，不是强跑** |

---

## Phase 3 — 埋点解锁归因（`HARNESS_FIX`）

`episode_tool_batch` 的 `tool_result` 落盘增加 `payload_field_names`（字符串数组）与 `payload_sha256`，**不落正文**。

### Phase 3 验收

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| **M. 字段非空且脱敏** | 新 run 的每条 `tool_result` 有非空 `payload_field_names`；**不含正文、不含 `/Users/` 或 `/home/`** | 出现绝对路径或正文片段 = 打回（红线） |
| **N. 体积可控** | artifact 体积增幅 **<5%** | 超过即打回，改为只记字段名不记 hash |
| **O. 真的解锁了归因** | 对 A5/A9/A10/C4/C5 五题，每条 fact 失败能给出「retrieve 侧 / synthesize 侧」二选一，不再是 `DEPTH_INSUFFICIENT` | 仍判不了 = 埋点埋错了位置（应在工具返回消费点，不是发起点） |

---

## 今天踩过的坑（一并交接，别再踩）

1. **不要信 Gitea 的 `mergeable`**。本单十张 PR 全报 `mergeable=true`，实际 #190/#194 有真冲突。自己探：`git merge-tree --write-tree gitea/main <branch>`，exit 0 才是干净。
2. **`acceptance-workflow.md` §4 链切五步已补 `git fetch`**，但要知道为什么：少了它会把 8792 钉在合并前 revision，**而三项验证仍会全过**（它们只校验「加载的代码 == 那个 sha」）。本单无链切，但下次有。
3. **判分器的红要先做反向检查**：「答案里有没有换了量纲/单位/措辞的同一个值」。本单 12 道失败里有 2 道（B7、C1）是产品答对了被判失败，靠人工复算才发现——Phase 1.3 就是为了让这一步自动化。
4. **看板自带方差校准要读**：「fact 层 0% 翻转，product_language 层 33%」。措辞层的单次红不要当定性。
5. **`git status` 不足以判断能不能动手**，本仓多 worktree 共享同一个 `.git`。开工先 `git worktree list`。
6. **测试壳**：`env -i PATH HOME KNOWLEDGE_WIKI` + `umask 022`。继承 launcher 变量 → 31 假红；umask 077 → 16 假红。解释器只用 `.venv-workbench/bin/python`。
7. **本单基线读数**：main tip `3af5c81f`，ruff 绿 / pytest **5511 passed 12 skipped** / webapp 65 test。四件套只许升不许降。

## 出口

- 三个 Phase 各自成 PR，**不要捆一起**——Phase 1 可零成本验，捆进 Phase 2 后就得重跑 LLM 才能验。
- 台账每 Phase 一行，写明：改了什么、验收判据逐条读数、收据路径（**写行前先 `ls` 确认存在**）。
- 三个 Phase 全绿后，用修好的尺子重跑一次 28 题，**那份读数才是本批产品的真实水平**——当前验收报告里的「不通过」结论届时需要重出。
- Phase 4（产品侧）按那份真实读数排序后另行派单。**本单不授权动产品代码。**

## 需要用户拍板的

- Phase 4 的启动时机与优先级（建议：C3 的降级披露契约优先，它踩中产品自称的差异化优势）。
- 若 Phase 1 验收判据 C 出现「第三题变化」，是打回还是接受——本单立场是**打回**，但用户可另裁。

## 附录：本单留存的对照读数

| 项 | 值 |
|---|---|
| 被测 artifact | `intelligence/eval/runs/20260818T051630Z.json`（28/28 完成，已入库） |
| 对照 baseline | `intelligence/eval/runs/20260815T1005Z-r5-clean-baseline-3.json` |
| 改前真值口径 | 通过 4 / 失败 12 / 不可判 12；可判子集 **4/16** |
| 改前逐题真值 | 见 `docs/verification/2026-08-18-kc-final-acceptance.md` §5② 与分诊报告 |
| B7 决定性读数 | 期望 `29569.03±295.69` → 抽出数 0 命中；按万亿 `2.9569±1%` → 命中 `[2.96]` |
| C1 决定性读数 | 答案 `2026-07-25 为周六，A股休市，该日无行情数据。`，三个 `forbid_phrases` 全未触碰 |
