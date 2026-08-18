# 派单：技术位取数支持指定日期（根治 2026-08-18 那条假绿）

- 日期：2026-08-19
- 派单人：链切 `8bbfc4e41a5a` 的那个 session（冻结 30 题实测 → 定位 → 只做了披露式缓解）
- 接单人：下一个执行 agent
- 上游证据：`docs/verification/2026-08-18-frozen-thirty-live-baseline.md` §3.1
- 当前缓解（**已上线，不是修好**）：`intelligence/runtime/continuous_turn_adapter.py`
  `_run_fast_path`（第 308 行）里的口径对账段（commit `2dea979d`）

## 0. 为什么这单必须做

现在的状态是**「不再假装答对」，不是「能答对」**。

历史日期的技术位问题，产品会给你一段按**今天**算的支撑压力位，前面加一句
「（口径提示：以下结论按 X 计算，非基准日 Y。）」并降级为 `degraded`。

这在诚实性上是对的（对齐 C3 空表披露那条纪律），**但能力缺口一点没补**：
用户问「7 月 24 日科创50的支撑位」，仍然拿不到 7 月 24 日的支撑位。

上游实测后果（别当理论风险）：冻结 30 题里 `index-rebound-space` 与
`sci-tech-support` 两题锚在 `2026-07-24`，快路径按 `2026-08-18` 算完交付，
**判分器给了 `completed` / `passed` / `task_alignment 1.0`**——0 次模型调用、
0.8 秒、用错日期的数，三个轴全绿。缓解只是把这个满分打成 `degraded`。

## 1. 病根：函数签名里没有日期这个概念

```python
# intelligence/services/market_technical.py:498
def resolve_market_technical(
    query: str,
    *,
    count: int = DEFAULT_BARS,      # 120
    timeout: float = _TIMEOUT_SECONDS,
    opener=None,
) -> TechnicalLevels | TechnicalGap:
```

**没有 `as_of`。** 它 `fetch_market_series(instrument, count=count, ...)` 拉「最近 N 根日线」，
然后按最后一根算——所以永远是今天。

而本轮的锚点**一直在手边**：`ContinuousTurnAdapter._latest_data_date`
（上游按题目 `as_of` 注入，benchmark 侧是 `scripts/run_agent_runtime_benchmark.py:504-505`
的 `today=case.as_of, latest_data_date=case.as_of`）。**从来没人把它往下传。**

好消息是数据结构支持：`DailyBar` 带 `date: str`（`market_technical.py:59`），
所以拿到足够多根之后**按日期截断**即可，不需要换数据源。

## 2. 要做什么

### 2.1 `market_technical.resolve_market_technical` 增 `as_of`

```python
def resolve_market_technical(
    query: str,
    *,
    as_of: str | None = None,     # 新增，None = 保持旧行为（最新）
    count: int = DEFAULT_BARS,
    ...
)
```

语义：`as_of` 非空时，把取回的 series **截断到最后一根 `bar.date <= as_of`**，
再走既有的确定性计算，`TechnicalLevels.as_of` 报截断后那根的日期。

**三条边界必须显式处理，别让它静默滑过**：

| 情形 | 要求 |
|---|---|
| `as_of` 早于可取窗口（120 根拉不到那么久以前） | 返回 `TechnicalGap`，`reason` 写明「窗口不足，最早可得 X」。**不得回落到最新日期** |
| `as_of` 落在非交易日 | 取该日之前最近一个交易日，并在 `as_of` 字段报**实际那天**，不报请求的那天 |
| 截断后剩余根数不足以算 20/60 日高低点 | 返回 `TechnicalGap`，别用不足样本硬算 |

第一条是本单的核心：**认不出来就 fail closed**。现在这条路径的毛病正是「拿不到就用手边的顶上」。

### 2.2 把锚点传下去（两个调用点，别只改一个）

| 调用点 | 现状 | 要改成 |
|---|---|---|
| `intelligence/services/episode_tools.py:1311`（`run_deterministic_fast_path`） | `resolve_market_technical(frame.raw_question, timeout=...)` | 增参数接收锚点并透传 |
| `intelligence/services/ask.py:909` | `resolve_market_technical(options.query, timeout=...)` | 同上，锚点从 `options` / plan 取 |

`run_deterministic_fast_path(frame, *, timeout)` 需要多一个 keyword（如 `as_of`），
由 `ContinuousTurnAdapter._run_fast_path` 传 `self._latest_data_date`。

> ⚠️ **`TaskFrame` 里没有日期字段**（实测：13 个字段全列过，没有 date/as_of/cutoff）。
> **不要为此往 TaskFrame 加字段**——那是跨块契约，动它影响面远超本单。
> 锚点走参数传递，adapter 手上已经有。

### 2.3 缓解逻辑要跟着收窄，不能留成永久噪声

`continuous_turn_adapter.py` 那段口径对账（`2dea979d` 加的）在本单落地后应变成
**兜底**而非常态：`as_of` 能满足时不该再触发。**别删它**——它仍要覆盖
「请求了历史日期但窗口不足」这类返回 gap 之外的残余情形。

## 3. 验收判据

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| **A. 指定日期真生效** | `resolve_market_technical("科创50支撑位", as_of="2026-07-24")` 返回的 `as_of` == `2026-07-24`（或该日前最近交易日），且支撑/压力位与 `as_of=None` 那次**不同** | 两次结果相同 = 参数没接上 |
| **B. 与库对账** | 该日收盘价与 `fact_stock_daily` / 指数源同日收盘**逐位相同** | 对不上先查取数不查算法 |
| **C. 窗口不足 fail closed** | `as_of="2020-01-02"` 返回 `TechnicalGap` 且 reason 含最早可得日期 | 返回了 `TechnicalLevels` = 静默回落，**这是本单要修的病本身** |
| **D. 非交易日** | `as_of="2026-07-25"`（周六）→ 报 `2026-07-24` | 报 `2026-07-25` 或 gap 都算错 |
| **E. 旧行为不变** | 不传 `as_of` 时，输出与改前**逐字节相同** | 变了就是把默认路径也改了 |
| **F. 两个调用点都通** | episode_tools 与 ask.py 两条路径各跑一次，`as_of` 都生效 | 只改一个 = 打回 |
| **G. 那两道题转正** | `index-rebound-space` / `sci-tech-support` 单题重跑，`data_cutoff == 2026-07-24`，且**不再出现口径提示** | 仍带口径提示 = 锚点没到 |
| **H. 变异测试** | 把 2.1 的截断那行注释掉，判据 A 必须变红 | 抽掉实现测试仍绿 = 假门禁。**变异前先提交实现**（本人踩过：未提交时变异，`git checkout --` 把修复一起回滚了） |

## 4. 跑法

单题成本很低，不要为此跑全 30 题：

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY scripts/live_probe.py start-sidecar --port 8796 --repo-root <被测树>
# 等 /api/health 的 source_revision == 被测树 HEAD
FORESIGHT_USERS_DIR=/Users/a77/.finance-runtime/live-probe-traceability/users \
  $PY -m intelligence.eval.acceptance run --base http://127.0.0.1:8796 --user live-probe \
  --case A2-next-day-call --output intelligence/eval/runs/<ts>-astechnical.json
```

判据 G 那两题在**冻结 30 题**集里，不在 28 题集，用
`scripts/run_agent_runtime_benchmark.py --case index-rebound-space --case sci-tech-support`。

## 5. 环境坑（都是本人今天踩过的，别重踩）

1. **测试壳**：`umask 022` + `env -i PATH="$PATH" HOME="$HOME" KNOWLEDGE_WIKI="$KNOWLEDGE_WIKI"`。
   **PATH 要透传真实值**（写死成 `/usr/bin:/bin` 会让 codex sandbox 用例假红）；
   **`KNOWLEDGE_WIKI` 不能漏**（漏了 `test_frozen_thirty` 的契约缺口断言会假红，我误判过一次自己引入回归）。
2. **比 pytest 数字前先读收据的 `target`**：`pytest intelligence` 4975 vs 整树 5565，差的是范围不是回归。
   收据在 `~/.finance-runtime/test-receipts/<ts>-<rev>.json`。
3. **8792 不要切**，本单无链切步骤。要旁路验就起 8796。
4. **落 main 走 Gitea PR API**（`security find-generic-password -s gitea-local -a a77-token -w`），
   不要直推——hook 会拦，而 PR 正是它认可的路径。合前仍自己
   `git merge-tree --write-tree gitea/main <分支>` 探一次，**别信 Gitea 的 `mergeable`**。

## 6. 出口

- 一个 PR，别捆别的改动。
- 台账一行，写明判据 A–H 逐条读数与收据路径（**写行前先 `ls`**）。
- 落地后回到 `docs/verification/2026-08-18-frozen-thirty-live-baseline.md` §3.1，
  把「仍未根治」那句改掉并指向本单收据。
