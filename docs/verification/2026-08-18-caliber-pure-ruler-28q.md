# 「纯尺子」28 题读数 —— 量具贡献与产品贡献的分离（2026-08-18）

- 树：`/Users/a77/fwp-wt-caliber-land` `land/caliber-stack` @ `ceb9a5a7`
- 被测代码：`#198` + `#199` + `#200` + `#201` 合入后 = **Phase 1+2+3，零产品改动**
  （断言：`git diff 82f99b26 ceb9a5a7 -- intelligence/ ':(exclude)intelligence/eval/runs/'` 为空）
- 上游要求：`docs/handoffs/2026-08-18-caliber-contract-closeout-dispatch.md` T4
- 8792 全程未切；跑前跑后两次 `/api/health` 均 `healthy` / `source_revision=3af5c81f` / `dirty=false`

## 1. 跑法与前置（判据 T4-a / T4-d）

```
$PY scripts/live_probe.py start-sidecar --port 8796 --repo-root /Users/a77/fwp-wt-caliber-land
FORESIGHT_USERS_DIR=/Users/a77/.finance-runtime/live-probe-traceability/users \
  $PY -m intelligence.eval.acceptance run --base http://127.0.0.1:8796 --user live-probe \
  --output intelligence/eval/runs/20260818T2100Z-caliber-p123-pure-ruler.json
```

| 项 | 读数 |
|---|---|
| sidecar `source_revision` | `ceb9a5a7` == 被测树 HEAD，`dirty=false` |
| 前置检查 | **自然通过，未用 `--force`**：`revision=ceb9a5a7 backend=continuous_glm users_dir=…/live-probe-traceability/users data_probe: finance_query=ok` |
| 完成度 | 28/28（正常完成 24、降级完成 4：B3 / C4 / C5 / C10）。前三题跑时日志打了 `⚠降级`，C10 没打——**跑时日志与看板的降级口径不一致**，以看板为准 |
| 收尾 | 8796 已 `stop-sidecar`，端口监听进程数 0 |
| 8792 | 跑前 `healthy`；跑中抽查 `healthy`；跑后 `healthy` |

> 跑前 8792 的 `/api/readiness` 就已经是 `not_ready`（`missing_critical=["market_data_consistency"]`）。
> **这是跑之前就存在的**，不是本次旁路测量踩出来的——先记基线再加载，正是为了不把
> 既有红算到自己头上。

## 2. 本批产品的真实水平（**这份读数取代旧结论**）

| 口径 | 改前基线 | **纯尺子（本次）** | 参考：含 Phase 4/4.5 |
|---|---|---|---|
| 真值 通过 / 失败 / 不可判 | 4 / 12 / 12 | **6 / 12 / 10** | 6 / 9 / 13 |
| 可判子集 | 4 / 16 | **6 / 18** | 6 / 15 |
| 完成 | 28/28 | 28/28 | 28/28 |

收据：
- artifact `intelligence/eval/runs/20260818T2100Z-caliber-p123-pure-ruler.json`（218 KB，已入库）
- 看板 `docs/verification/2026-08-18-caliber-pure-ruler-board.txt`
- 对照看板 `docs/verification/2026-08-18-caliber-p4-board-same-ruler.txt`
  （把 `20260818T1749Z-caliber-p4.json` **用同一把尺子重算**，不是复用 p4 分支那份——
  Phase 4 改过判分器，直接拿两份不同尺子算出的看板对比会把尺子差异算成产品差异）

## 3. 量具贡献 vs 产品贡献

### 3.1 量具贡献 —— 零方差，同一份 artifact 复算

拿 `20260818T051630Z.json`（改前那次跑的**同一批答案**）用新尺子重算：

| | 改前尺子 | 新尺子（Phase 1+2+3） |
|---|---|---|
| 真值 | 通过 4 / 失败 12 / 不可判 12 | 通过 **7** / 失败 9 / 不可判 12 |
| 变化题 | — | **3 题**：B6 ❌→✅、B7 ❌→✅、C1 ❌→✅ |

**这是唯一没有抽样噪声的对照**：答案完全一样，只换尺子。三题里
B7 / C1 是 Phase 1 修的判官假红，B6 是 Phase 2 改的判据。

### 3.2 产品贡献 —— 只有 C3 可归因，其余是 n=1 噪声

纯尺子跑 vs 含产品跑（**同尺子、同题面**，只差产品代码与一次抽样）：

| 题 | 纯尺子 | 含产品 | 能不能归给产品 |
|---|---|---|---|
| **C3-empty-table** | ❌ 失败（`answer does not explicitly report unavailable/no data`） | **✅ 通过** | **能**。Phase 4.3 的 `empty_caliber_disclosure` 是**确定性罐头短路**，不过 LLM；p5 收据里有原文 |
| A3-stock-deep-dive | ❌（`missing expected entities: 立新能源`） | ❔（`board-height risk interpretation is not structured`） | **不能**，两次失败理由都不同，是答案本身变了 |
| A4-dual-red | ❌（抽到 8.18/8.03/7.82，期望 6.65） | ❔（别名根本没出现） | **不能**，同上 |
| A6-limit-advance-ladder | ❌（`missing product terms: 断层`） | ❔（`prose-only`） | **不能**，同上 |
| B7-volume-sentiment-evolution | ✅ 通过 | ❌ 失败（抽出数含 `2.96`，缺 07-23 那个值） | **不能，且这不是回退** |

**B7 特别说明**：它在三份读数上是 ✅（051630Z 复算）/ ✅（本次纯尺子）/ ❌（含产品）。
Phase 4/4.5 动的是 `honesty_gates` 的 C3/C4/C5/A5 触发条件、`route_table` 的 quick_fact
车道与 `metric_spec`——**B7 不走这些路径**。所以那个 ❌ 是**这次答案只写了 07-21 的
`2.96万亿`、没写 07-23 那个值**，属抽样波动，不是产品退步。

> **别把 n=1 的差异写成归因。** 本仓看板自带的方差校准说「fact 层 0% 翻转」，
> 本次实测**证伪了这条**：同一把尺子、同一份产品代码，A4 / A6 / B6 在
> 051630Z 复算与 2100Z 实跑之间就翻了（题面也变了，所以这三题混了两个变量，
> 但至少说明 fact 层不是零方差）。要做产品 A/B，得先把这条方差量出来。

### 3.3 B6 是一处「只在冻结 artifact 上绿」的假绿

| 数据源 | B6 |
|---|---|
| `20260818T051630Z` 复算（罐头澄清答案） | ✅ 通过 |
| `20260818T1749Z` 实跑 | ❌ 失败 |
| `20260818T2100Z` 实跑（本次） | ❌ 失败 |

Phase 2 把 B6 判据改成「必须要求澄清」，overlay 只认
`你指的是 / 请补充 / 请提供 / 缺少` 四个短语。冻结 artifact 里那句罐头澄清**碰巧命中**，
两次真实跑里产品说的是「材料没传上来…贴过来」，**没命中**。

**判据是照着一份冻结答案调的，不是照着产品的真实说法调的。**
两次独立实跑都红，说明这不是偶发。修法二选一：短语表补齐产品的真实澄清说法，
或改成语义判据——但**不要再拿 051630Z 那份去验它**，那份已经证明会发假绿。

## 4. 判据 I 的新读数

上游判据：可判子集分母 `16 → ≥22`。

| 读数来源 | 分母 |
|---|---|
| 改前 | 16 |
| Phase 2 收据（含 Phase 4 那次跑） | 15 |
| **本次纯尺子实跑** | **18** |

分母确实升了（16 → 18），方向对，但**离 22 仍差 4**。
Phase 2 收据里报的 15 是在含 Phase 4 的树上跑出来的，**不是 Phase 2 单独的成绩**。

判据 J（A3 拿到 `12.11`）此前已过；本次 A3 失败理由变成
`missing expected entities: 立新能源`，与日期锚无关。

## 5. 复现命令

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
export FORESIGHT_USERS_DIR=/Users/a77/.finance-runtime/live-probe-traceability/users

# 两份看板（零成本，纯复算）
$PY -m intelligence.eval.acceptance board --run intelligence/eval/runs/20260818T2100Z-caliber-p123-pure-ruler.json
$PY -m intelligence.eval.acceptance board --run <p4 树>/intelligence/eval/runs/20260818T1749Z-caliber-p4.json

# 三方对照（脚本会先自证解析到 28 题、真值列非空，解析数不对就退出）
python3 scripts/compare_acceptance_boards.py \
  docs/verification/baselines/2026-08-18-board-20260818T051630Z.txt \
  docs/verification/2026-08-18-caliber-pure-ruler-board.txt \
  docs/verification/2026-08-18-caliber-p4-board-same-ruler.txt
```

`scripts/compare_acceptance_boards.py` 是本轮沉淀的通用件：**先自证读到了值再出结论**，
解析数不等于 28 直接退出。它防的就是本批最贵的那个教训——字段名猜错、每格都是 `None`，
脚本照样输出「回归 0 题 / 持平 28 题」。
