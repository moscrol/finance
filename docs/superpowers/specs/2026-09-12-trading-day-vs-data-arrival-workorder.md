# 工单 #52：交易日判定拿行情行数当代理——同步失败被判成「非交易日」，L2 静默 exit 0

> 单类型：判定契约拆分（小到中单，半天到一天）+ 三个调用方改造 + 四例验收闸。
> 主仓：金融。优先级 **P0**（正在流血：2026-09-11 已实测命中，周一 09-14 同步再失败会重演）。
> 分支：`fix/trading-day-calendar`。
> 来源：工单 #51 §3 第二问「非交易日与日包缺失怎么区分」——答案是**区分不了**，这是那条问的收口单。

## 0. 一句话

`market_feature_store/trading_days.py` 用「当日 `fact_stock_daily` 行数 ≥ 3000」代理「今天是不是交易日」。
于是**行情同步失败的真交易日**被自信地判成非交易日（`approximate=False`），
L2 流水线打印「非交易日，跳过」并 `exit 0`——**静默报成功，什么都不做**。

「今天开不开市」是日历事实，与「今天的数据到没到」是两个问题。现在它们是同一个布尔。

## 1. 读数（2026-09-12 实测，可复跑）

```sql
-- 09-11 在 fact_stock_daily 里整天缺席（不是行少，是 0 行）
SELECT trade_date, count(*) FROM fact_stock_daily
WHERE trade_date >= '2026-09-01' GROUP BY 1 ORDER BY 1;
--  ... 2026-09-09 | 5551
--      2026-09-10 | 5550
--      （无 2026-09-11 行）
```

```python
from market_feature_store.trading_days import is_trading_day_detailed
is_trading_day_detailed("2026-09-11")   # -> (False, False)
```

2026-09-11 是**周五、真交易日**。返回 `(False, False)`：第二个分量 `approximate=False`
意思是「这个判断不是近似，是确定的」——**它把同步失败确定地判成了休市**。

连带后果（`ops_pipeline_run_daily`，同日实测）：

| 日期 | limitup | top100 | quant |
|---|---|---|---|
| 2026-09-10 | complete | complete | complete |
| 2026-09-11 | complete | **failed** | **（无行，从未执行）** |

## 2. 缺陷在哪一行

`market_feature_store/trading_days.py::is_trading_day_detailed` 第 4 步：

```python
n = _fact_stock_daily_count(d, path=db_path)
if n is not None:
    result = n >= MIN_DAILY_ROWS
    _DB_CACHE[cache_key] = result
    return result, False          # ← 库可读但当天 0 行时，这里返回 (False, False)
```

`n is not None` 只证明**库可读**，不证明**当天该有数据**。库可读 + 0 行有两种成因：

1. 真休市（节假日）——该判非交易日 ✅
2. 真交易日但同步没跑/跑失败——该判**数据缺失**，不是休市 ❌

模块 docstring 第 5 条写的「DuckDB 不可读时按工作日近似判定，并标记 approximate」
只覆盖了「库打不开」，没覆盖「库打得开但当天空着」。后者才是 09-11 命中的那条。

**只把 `approximate` 改成 `True` 不够**：三个调用方全部只取布尔（见 §3），
标记会在 `is_trading_day()` 的返回值里被丢掉。必须改判定的**值域**，不是它的旁注。

## 3. 三个调用方，全部只取布尔

| 调用方 | 行 | 现在的行为 | 误判后果 |
|---|---|---|---|
| `scripts/moneyflow/run_l2_pipeline.sh` | 48–58 | 子进程打印 `1`/`0`，`"0"` → `exit 0` | **静默跳过整条 L2**，退出码 0，外层看不出异常 |
| `scripts/moneyflow/write_to_duckdb.py::mark_failed` | 185 | 非交易日不落 failed | 真失败不入账，台账看起来干净 |
| `scripts/check_daily_review_data.py::check_l2` | 644 | 非交易日自动放行 | 缺数被放行，质检不报 |

三处都会把「同步失败」翻译成「今天不用干活」。`run_l2_pipeline.sh` 那处最重：
它是 `exit 0`，**对外等价于成功**。

> `skills/limit-advance/scripts/scrape.py` 里的 `is_trading_day` 是 fupanhui 返回 JSON 的字段名，
> 与本模块无关，不在本单范围。

## 4. 契约（改完必须同时成立）

1. **交易日判定不读行情表。** 判据只用：env 覆盖 → 周末 → 交易所公告休市表。
   与同步、与 DuckDB 是否可读、与当天有几行，全部无关。
2. **值域是三值，不是二值。** `trading` / `closed` / `unknown`。
   休市表没有该年份 → `unknown`，不得猜成任意一边。
3. **`unknown` 不得静默跳过。** 调用方必须落一条可读记录（日志 + 台账），
   并选择**继续执行**而非跳过——L2 的上游日包自己会失败得很响，比静默 exit 0 好。
4. **「数据到没到」是另一个函数。** `market_data_rows()` / `market_data_state()`
   返回 `present / partial / missing / unknown`，与交易日判定正交。
5. **休市表单一事实源。** 仓里已有一张 `_SSE_CLOSURES`
   （`intelligence/services/trading_calendar.py`），**不得再造第二张**——
   把它下沉到 `market_feature_store/`（低层），由 `intelligence/` 反向 import。
   方向合法：`layer_audit.py` 只圈 `intelligence/services/** ↛ intelligence.runtime.*`，
   且 `intelligence/services/external_market.py:154` 已有同向先例。

## 5. 验收（四例，全部要求「不静默成功」）

每例都要在**真启动脚本**上跑，不能只测 Python 函数——静默 exit 0 是 shell 层的行为。

| # | 条件 | 期望 |
|---|---|---|
| 1 | **交易日零行**：2026-09-11，`fact_stock_daily` 无该日行 | 判 `trading`；L2 **执行**；不 exit 0 跳过 |
| 2 | **部分入库**：同日只有 1200 行（< `MIN_DAILY_ROWS`） | 判 `trading`（不受行数影响）；数据面另报 `partial` |
| 3 | **工作日休市**：2026-06-19（端午，公告休市表命中） | 判 `closed`；L2 跳过、exit 0；**不落 failed** |
| 4 | **库不可读**：`MARKET_FEATURE_STORE_DB` 指向不存在的路径 | 判定不受影响（不读库）；数据面报 `unknown` |

加一例反向：**休市表没有的年份**（如 2025-03-03）→ `unknown` → L2 **执行**并打印
一行 `calendar=unknown` 告警，退出码由真实执行结果决定。

> **§5 两处日期订正（实施时实测）**：初稿写第 3 例用 `2026-10-01`、反向例用
> `2024-03-05`，两条都测不到想测的分支——`future` 判据排在休市表**之前**，
> 今天（2026-09-12）看这两个日期：`2026-10-01` 得 `closed(future)` 而非
> `closed(sse_closure)`，`2024-03-05`⁠…⁠是过去的年份所以确实是 `unknown`，但
> **任何 2027+ 的日期都会被 `future` 吃掉**，反向例必须取过去的表外年份。
> 已改为 `2026-06-19`（端午，过去的工作日休市）与 `2025-03-03`（过去、表外年份）。
> 这类「验收用例自己选错日期」很隐蔽：用例照样绿，但绿的是另一条分支。

**证伪要求**：每条测试都要先在**未修版本**上跑红。
参考教训 `verification-tools-can-be-silent-on-the-defect` —— 绿的探针不算证据，
要先证明它在已知坏样本上会红。

## 6. 不在本单范围

- 09-11 的行情补数（要打上游，有副作用，走 `/daily-full-review`）——工单 #51 §6 的欠账。
- 补数后 L2 的自动补跑机制（「不靠人记着」）——单独一刀，本单只保证**判定不再骗人**。
- 闲鱼日包迁移收口、生成段代码根（#50）——各自独立。

## 7. 交接

完工覆写 `docs/handoffs/inflight/fix-trading-day-calendar.md`。
合并前本机跑等价 CI：`.venv-workbench/bin/python -m ruff check . && .venv-workbench/bin/python -m pytest -q`。

---

## 8. 交付记录（2026-09-12 实施）

### 8.1 改了什么

| 文件 | 改动 |
|---|---|
| `market_feature_store/trading_days.py` | 重写。`trading_day_verdict()` 三值纯日历判定（不读库）+ `market_data_state()` 数据面判定（`present/partial/missing/unknown`）+ `closed_dates(year)` 公开访问器；`is_trading_day()` / `is_trading_day_detailed()` 保留签名兼容，**`UNKNOWN` 返回 True**（判不出来按「要干活」处理） |
| `intelligence/services/trading_calendar.py` | 删掉本地 `_SSE_CLOSURES`，改 import 低层 `closed_dates()`——休市表归一为单一事实源 |
| `scripts/moneyflow/run_l2_pipeline.sh` | 守卫改吃三值：`closed` 跳过 / `trading` 跑 / `unknown` **跑 + 告警**。另加行情缺口说明行与探针代码根校验（见 §8.3） |
| `tests/test_trading_day_vs_data_arrival.py` | 新增 18 例：模块层 13 + 守卫层 5（守卫层**真跑 shell**） |

契约 §4 五条全部落地。`write_to_duckdb.py::mark_failed` 与 `check_daily_review_data.py::check_l2`
**无需改代码**：它们取的布尔值语义已经由底层修正——0 行的真交易日现在判 `trading`，
于是 `mark_failed` 会照常落 failed（不再让真失败不入账）、`check_l2` 会照常去查（不再放行缺数）。

### 8.2 反向对照（证伪，非「跑绿了」）

按 §5 证伪要求，同一夹具（2026-09-11 + `fact_stock_daily` 零行的临时库）、
同一套 stub 步骤脚本，只换 `trading_days.py` 与守卫段：

| | 旧代码 | 新代码 |
|---|---|---|
| 判定输出 | `非交易日 date=2026-09-11` | `verdict=trading source=sse_calendar data=missing` |
| 真跑的步骤 | **0 个** | 5 个全跑（write_to_duckdb → limitup → top100 → quant → render） |
| 退出码 | 0（**静默成功**） | 0（stub 链真跑完） |

变异对照（证明闸门没被拆掉，只是换了判据轴）：新代码跑 `2026-06-19`（端午）
→ `closed(sse_closure)`、0 步骤；跑 `2026-09-12`（周六）→ `closed(weekend)`、0 步骤。

**休市表可承重性校验**：拿生产库 2026-01-01..2026-09-11 的实际有行日期反向验表，
两个方向都查——「表说休市但库里有行」**0 条**，「表说交易日但库里 0 行」**唯一 1 条 = 2026-09-11**。
即 168 个交易日与休市表零冲突，唯一不符正是事故日。这条比任何单测都硬：
它证明当天是真交易日、判错的是行数代理，而不是休市表漏登。

### 8.3 实施中新发现的第二个洞（已一并修）

写守卫测试时做反向对照——把假 `CODE_ROOT` 里的 `market_feature_store` 拆掉，
**探针照样答 `trading`**。原因：`python3 -` 会把**当前工作目录**塞进 `sys.path`，
而脚本的 `cd "$moneyflow_dir"` 在探针**之后**。于是探针可能从 cwd 兜到**另一棵检出**
取休市表，而日志里完全看不出来。

这与工单 #51「夜跑代码根钉死」是同一条纪律的漏网处：`$CODE_ROOT` 被传进去了，
但没人验证**真正被 import 的那份代码**来自它。已修为：清掉 `sys.path` 里的 cwd
条目 + 校验 `trading_days.__file__` 落在 `$CODE_ROOT` 内，不符即 `unknown`
（→ 照跑 + 告警），并带上 `probe_wrong_code_root` 判据。

顺带：旧守卫的 `2>/dev/null || true` 会把「判定挂了」和「判定说休市」在日志里
压成同一个形状（都是空输出）。已去掉吞 stderr，探针异常一律归 `unknown`。

### 8.4 门禁读数

- 新增测试 18/18 绿
- `tests/` 1119 passed / 62 skipped / **0 failed**（64 s）
- `intelligence/tests/` 8309 passed / 15 skipped / 1 xfailed / **0 failed**（293 s）
- `pre-commit` 11 道全 Passed（含层级审计 ERROR 0、路径字面量、字段契约）
- 解释器：`.venv-workbench/bin/python`；基线 `fix/trading-day-calendar@c703e068`

### 8.5 本单**没有**解决的（仍欠）

1. **09-11 行情补数**——本单只保证判定不骗人。补数后 `top100/quant` 才补得了。
2. **补数后 L2 的自动补跑**（「不靠人记着」）——判定修好只是前提，补跑编排是另一刀。
3. **装机副本同步**：`~/.claude/skills/`（或装机路径）下的 `run_l2_pipeline.sh`
   副本与仓内已分叉（闲鱼日包迁移在途，见 #51 §3 第三问）。本单改的是仓内那份，
   **装机副本需要同样的守卫改造**，否则夜跑真正执行的还是旧逻辑。⚠️ 这条是本单
   交付的**实际生效前提**，必须紧接着做。
