# Session handoff — 验收台方差治理 + 题目缺陷检测（2026-08-01d）

**上一段**：`2026-08-01c-acceptance-baseline-and-three-harness.md`。
本段做完了它的第一优先项 #14，外加 #13。**全程零配额**（没跑过任何一道题）。

---

## 0. 一句话现状

**验收台这个「仪表」修好了两处硬伤：自身噪声 7%→2%，以及会随行情漂移的假红被
识别出来。产品侧一个字没改，A 组通过数仍是 0——这是下一段该盯的地方。**

---

## 1. ⚠️ 先做这个：625 行改动未提交

```
分支 fix/exposure-ranking-truncation @ 0c50a29c（HEAD 没动）
4 files changed, 625 insertions(+), 30 deletions(-)   ← 全部 working tree
+ docs/verification/2026-08-01-acceptance-harness-noise.md（未跟踪）
+ docs/handoffs/2026-08-01d-...md（本文件，未跟踪）
```

| 文件 | 改了什么 |
|---|---|
| `intelligence/eval/acceptance_verdict.py` | 主体：别名窗口对称、等价类、蕴含声明、两处收紧、可复现性检测 |
| `intelligence/eval/cases/acceptance_verdict_contracts.json` | A1/A2/A6/A8 的 `phrase_equivalents` 与 `phrase_discharged_by` |
| `intelligence/eval/acceptance.py` | 看板按判据层分账 |
| `intelligence/tests/test_acceptance_verdict.py` | 16 条新测试（12+4），**16 次突变逐条打红** |

**它现在只存在于这台机器的一个 `tmp/` 工作 clone 里。建议第一件事就 commit。**

## 2. 运行时状态（没动过）

| 角色 | 值 |
|---|---|
| 工作 clone | `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17` |
| 线上 8792 | PID 54180，旧快照 `751ef706`，**本段和上段的改动都没上线** |
| 旁路 canary 8793 | PID 81260，cwd = 工作 clone |

> ✅ 本段**只改判官/CLI 侧，没碰 server 侧**，canary **不需要重启**。
> 下一段若改 `query_understanding` / `daily_review` 等 server 侧，必须重启（见上段 §7 四条检查）。

## 3. 本段已完成

### 3.1 待办 #14：验收台自身方差（handoff 2026-08-01c §4 的第一优先）

**先证伪了原始读数。** 上一段给的三次运行不能直接横比：`034001Z→035325Z` 之间
上了 #12 选章节，A4/A6 的 fail→pass 是**修复生效不是波动**。隔离出真正干净的
对照（`025854Z→034001Z`，中间只有判官侧改动、不重启 server）：

| rule.kind | 稳定 | 翻转 |
|---|---:|---:|
| **数值型 fact** | 20 | **0** |
| **must_mention（措辞）** | 1 | **2（67%）** |
| 字符串型 fact | 0 | 1 |
| 其余全部 | 21 | 0 |
| **合计** | 42 | 3（**7%**）|

**用户假设成立**：波动几乎全在措辞层。**但要加一条修正**——「事实数字层稳」
只在**数值正确性**上成立（三次运行没有一次把数字说错），在**是否提及**上不稳：
run3 的 A1 整个换了答案形状把数字漏光。判官原来把「说错」和「没说」记成同一种红。

**量纲否掉了原定的 (c) LLM 语义判定**：措辞类断言全套只有 **8 条**，而 (c) 要付出
「叠加判官方差（要量化就得重复运行，绕回 n≥3）+ 打破模块纯函数属性 + 每次重渲
看板都烧配额」。改用**确定性等价类 + 蕴含声明**，依据是仓库里已有该模式
（C 组 4 题的 `required_any_phrases`）。

四刀：

| # | 修了什么 |
|---|---|
| 1 | 别名窗口 `-8/+40` → 对称 `-40/+40`。中文「21949.97 亿元的成交额」数字在别名前 13 字被切掉。窗口宽度扫描证明：放宽到**完全不设窗口**也只多救回这一条，**即不会引入假绿** |
| 2 | `phrase_equivalents` 同义等价类，两条守卫：必须含正典短语本身、不得跨枚举值 |
| 3 | `phrase_discharged_by` 冗余断言蕴含声明（A1 缩量←`fact:amount_vs_yesterday_pct`、A2 证伪←`falsifiable`）。**更严规则没过时措辞要求原样生效**；规则名打错进 diagnostics fail-closed |
| 4 | 两处**收紧**：字符串型 fact 全文缺席判 FAIL（A9 别名表里「沸点」既是定位别名又是期望值，害 #11 的不可判规则误触发）；矛盾断言锚定到声明的操作数（杀掉 A9 前两次「正文别处有『矛盾』就判过」的**假绿**）|

**效果：噪声 7% → 2%**，fact 层与 semantic_marker 层归零。剩余唯一翻转是 A6，
**那是真信号**（run1 的答案连「梯队」都没提，本身就更差）。
**题级通过/失败数一个没变**——改的是稳定性与归因，不是门槛。

收据：`docs/verification/2026-08-01-acceptance-harness-noise.md`

### 3.2 待办 #13：A8 题目不可复现 —— 比预想严重

**根因实测（不是读代码推断）**：`acceptance.py:250` 只把 `case["query"]` 发给产品，
**`date` 字段从不传**，它只供判官做 cutoff。

- A8 query =「现在市场处于什么阶段，第几天了」（**正文无日期锚**）
- 产品答「截至 **2026-07-30**，**底部横盘阶段**，第 **2** 个交易日」——**完全正确**
- 而 `expect_facts` 冻结在 `反弹阶段 / 第 3 天`（2026-07-23 的事实）

**这条红不仅是假的，还会随行情漂移、永远不会变绿。**
对照 A1：query 是「2026-07-23 今天市场怎么样」，日期写进了正文，可复现。

落地为确定性检测 `_reproducibility_diagnostics`：query 含相对时间词
**且** `date` 未出现在 query 里 **且** 声明了随日期变化的期望值
（`expect_facts` / `expect_answer_set`）→ 报 contract diagnostic。

精确命中 **A8 + C6**，且：
- B8「立新能源现在贵不贵」正确**未**命中（只断言实体在场，与日期无关）
- A1 / A2 正确**未**命中（日期已写进正文）

配套：`CaseContract.reproducible=False` 时 `_evaluate_truth` **短路成不可判**。
因为 `_aggregate_rules` 里 FAIL 优先于 UNJUDGEABLE，不短路的话那些无意义的
fact 红会盖掉缺陷标记，让**题目缺陷长得和产品缺陷一模一样**。

`test_all_cases_compile_without_mutating_frozen_assets` 里用**具名清单**钉住
`{A8, C6}`——这条断言本身就是待办：修好日期锚就把它删掉，新冒出的缺陷会让它变红。

> 🔴 **C6 在 C 组。跑 C 组前必须知道这件事，否则那批读数一样是脏的。**

## 4. 关键约束（下一段必读）

**`acceptance_cases.json` 被 `CANONICAL_CASES_SHA256` 密封冻结**
（`test_all_cases_compile_without_mutating_frozen_assets`）。

- 28 题的正典定义**不许改**，判据表达力**只能走 additive overlay**。
- 这是好设计：它逼着「放宽判据」这类改动必须显式、可审计。
- 所以「删掉冗余的 must_mention」不能真删条目，得表达成 overlay 机制（即 §3.1 第 3 刀）。
- **A8/C6 的根治需要改 query 写进日期锚 = 破封 + 更新 hash 常量 + 使那两题的
  参照快照失效**（codex/knevo 回答的是相对时间版问题）。**这是用户决策，本段没做。**

## 5. 验证状态

- 判官模块 **33 条测试全绿**；本段新增 16 条（#14 的 12 + #13 的 4），
  **16 次突变逐条打红对应那条**。
- 全量回归 / ruff：**见 §9，本段最后一次运行的结果填在那里**。
- 密封夹具 sha256 **未变**：`a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6`

> ⚠️ **踩坑记录**：突变验证时 `VerdictState.PASS,` → `VerdictState.FAIL,` **字节长度相同**，
> 且突变+还原在同一秒内完成，Python 的 `.pyc` 按 `(mtime, size)` 校验源文件会认为
> 缓存有效，于是一直跑突变版字节码，**伪造出两条「新回归」**。
> 任何 mutate-run-restore 循环后先清 `__pycache__` 再信全量结果。

## 6. 当前看板（从已存 run 重算，零配额）

```
运行：28 题里跑了 10（A 组），未跑 18（B 组 8 + C 组 10）
      正常完成 7、降级完成 3
真值：通过 0、失败 6、不可判 4     ← 可判子集通过率 0/6
失败按判据层：fact 7、product_language 3、semantic_marker 2
体验：已盲标 0 / 28
参照：knevo 22/28，codex 0/28
```

**A 组跑了四轮，通过数从来没离开过 0。这是最该盯的数字。**

**A 组 6 条红的性质（已分清，别再重新分类）**：

| 题 | 性质 | 抓手 |
|---|---|---|
| A7 芯片 66、A10 新高 339 | **真缺口**：章节选了但数没取到 | 明确（A10 锚定日是 07-21，别拿 07-23 的导出核对）|
| A9 沸点 / -66.3 | 三次运行**都没出现** → 数据没送到答案 | 明确 |
| A2 | **降级桩**，运行层未完成 | 待办 G（synthesize 说不出降级原因）|
| A1 | 答案**形状不稳**，run3 跳去写别的把数字漏光 | 难，生成侧稳定性 |
| A6 | 有时根本不提梯队 | 同上 |
| A3/A4/A5 不可判 | **判据表达力**不够，需要 typed observation sidecar | 非产品问题 |

> ⚠️ **更正上一段 handoff §5**：A2 **不是**「表达层——数据到位了没下结论」。
> 它三次运行逐字节相同的 232 字降级桩、`degrades` 非空、看板 🟠 降级完成。
> #10 宣称的「降级桩 5→0」没覆盖到它。**归错类会让人去改表达层而不是查降级原因。**

## 7. 待办总表

| ID | 内容 | 状态 | 谁定 |
|---|---|---|---|
| 14 | 验收台方差 | ✅ 本段完成（7%→2%）| — |
| 13 | A8 题目不可复现 | ✅ 本段完成（检测器，非根治）| 根治要用户定 |
| **—** | **commit 本段 625 行** | 🔴 **建议第一件事** | agent |
| 5 | B 组 8 题基线 | **已解封**，约 8 次调用 | agent |
| 4 | C 组复跑 | **已解封，但先看 §3.2 的 C6 缺陷** | agent |
| 3 | 看板拆三轴三列（可信度/送达率机判，信息量用 knevo 快照做 few-shot 锚）| 待做；本段已加「失败按判据层」打底 | agent |
| 6 | 待办 I：选择器分辨率（用 `evidence_coverage` 量化）| 待做 | agent |
| 7 | 待办 G：synthesize 说不出降级原因（**A2 卡在这**）| 待做 | agent |
| 2 | knevo head-to-head | 等 codex 参照 | 等 #9 |
| — | A8/C6 根治（破封改 query）| 未做 | **用户定** |
| **8** | **待办 K：夜跑 sync 失败连带丢 L2** | 🔴 **阻塞 origin/main** | **用户定 a/b** |
| **9** | codex 快照 0/28（ChatGPT app sidecar 503/401）| 🔴 | **用户重登** |
| J | 留证强制进正文 | 未做 | 用户 |

## 8. 验收命令

```bash
W=/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
cd $W

# 回归（先清缓存，见 §5 踩坑）
find . -name __pycache__ -type d -exec rm -rf {} + ; $PY -m pytest -q && $PY -m ruff check .

# 看板（零配额，从已存 run 重算）
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki $PY -m intelligence.eval.acceptance board

# 跑 B 组（烧配额，每题约 30s；canary 无需重启，本段没改 server 侧）
$PY -m intelligence.eval.acceptance run --tier mid_freq \
  --base http://127.0.0.1:8793 --user default

# 可复现性检测实测（免费）
$PY -c "
import json,pathlib
from intelligence.eval.acceptance_verdict import compile_case_contract, load_verdict_overlay
cases=json.loads(pathlib.Path('intelligence/eval/cases/acceptance_cases.json').read_text())['cases']
ov=load_verdict_overlay()
for c in cases:
    ct=compile_case_contract(c, ov[c['id']])
    if ct.diagnostics: print(c['id'], ct.diagnostics[0])
"   # 期望恰好 A8 + C6
```

**跨运行方差探针**（本段用来做测量的一次性脚本，在 `/tmp/variance_probe.py`，
**未入库**）：把已存 run 重新灌进判官、逐规则比对状态、按 `rule.kind` 归类。
下一段若要复现测量，需要重写或从本 handoff 的描述重建。

## 9. 本段最后一次全量回归结果

```
3927 passed / 12 failed / 3 skipped        ruff: 165 errors
```

**零回归，已核对**：

- 基线是 3911 passed（上一段 handoff §1），本段新增 16 条测试 → **3911 + 16 = 3927** ✅
- 12 条红**同名同数**，全是既有的：8 条 `test_subconscious` + 3 条 `test_userspace`
  （环境依赖）+ 1 条 `tests/test_pipeline_p0.py::test_nightly_script_attempts_l2_before_sync_failure_exit`
  （**就是待办 K**）
- ruff **165**，与基线同数，本段没引入新的 lint 问题

> 跑之前清过 `__pycache__`（见 §5 踩坑）。

## 10. 刻意不要做的

- **不要用单次运行的通过数论证小改动的好坏**。本段把噪声降到 2%，但那是**规则级**；
  题级仍受「答案形状不稳」影响（A1/A6）。只有结构性大变化可信。
- **不要为了绿灯放宽判据**。本段两条纪律：等价类必须**从数据模型/pass_rule 已有措辞里取**，
  **不能事后看答案补词**（那是过拟合到某次运行）；蕴含声明在被蕴含规则失败时**必须原样生效**。
  自检信号：**修完之后题级通过/失败数不该变**——变了就说明动的是门槛。
- **不要改 `acceptance_cases.json`**（密封夹具）。判据表达力走 overlay。
- **不要动 `daily_projection_modules`**——工作台 UI（`api/app.py:1014`）共用它。
- **不要把跨概念覆盖度当质量信号**（知名度代理，见上上段探针 §2.3）。
- **不要在 K 未定前 push origin/main。**
- 改 server 侧代码后必须重启 canary（本段没改，所以没重启）。

## 11. 元数据

| | |
|---|---|
| 会话日期 | 2026-08-01 |
| 配额消耗 | **0**（全程离线复算已存 run trace）|
| 复用的 run trace | `intelligence/eval/runs/20260801T{025854,034001,035325}Z.json` |
| 新增文档 | `docs/verification/2026-08-01-acceptance-harness-noise.md`（#14 的详细收据）|
| 记忆回写 | `20_projects/finance-workspace-private.md` 交接记录 ×2 + 任务看板；`10_knowledge/eval-harness-variance-governance.md`（新建，§7 为 #13 的方法论）；`intelligence/users/linxiaoqi5111/corrections.jsonl` +3 条 |
| ⚠️ vault 分支 | 回写落在 `docs/session-tutor-first-principles`，**不是 `main`**（playbook 约定是 main，待用户定）|
| 工作区 | **脏**，625 行未提交（见 §1）|
