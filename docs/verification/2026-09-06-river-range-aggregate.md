# 区间聚合 `range_aggregate`：可算的量要算得出来，且不许静默算错

> 日期：2026-09-06
> 分支：`feat/river-range-aggregate`（栈在 `feat/river-recorded-at-ledger` 上）
> 起因：用户问「我们已有的数据是不是可代码化的部分都代码化了，比如区间涨幅你能算出来吗，要方便计算」
> 状态：**未合并**。

## 0. 先回答那个问题

**能算，但个股和板块不是一回事，而且原来每算一次都得现写 SQL、还得自己记住两个坑。**

数据代码化的整体程度（`scripts/review_data_codification_audit.py` 实测，38 张表 / 418 列参与判定）：

| | 列数 | 含义 |
|---|---:|---|
| ✅ 已代码化 | 343（82%） | 有生产读取方、结构化、可重算 |
| ⬜ 空表 | 41 | 表就是空的 |
| ❌ 存了没人读 | 20 | 填满了但全仓无生产消费方 |
| ⭕ 声明了从没写过值 | 7 | 列存在、填充率 **0** |
| 📄 散文 | 7 | 有人读，但进不了统计 / 聚类 / 回放 |

## 1. 三个会静默算错的坑（都不报错）

### 1.1 板块没有收盘点位

`fact_sector_daily` 的列只有 `pct_chg / amount / diff_ratio / strength / multi_period_*`——**没有 close**。
所以板块区间涨幅只能把每日涨幅连乘，**缺一天就少乘一天，结果偏低而 SQL 一声不吭**。

窗口越长坑越大（实测）：

| 窗口 | 板块数 | 缺天的 |
|---|---:|---:|
| 2026-08-01~09-02（23 天） | 402 | **0** |
| 2026-06-01~09-02（67 天） | 549 | **431** |
| 2026-03-01~09-02（128 天） | 549 | **433** |

一个月窗口完全看不出问题——这正是它危险的地方。

个股不同：`fact_stock_daily` 有 `close` / `pre_close`，首尾相除就是精确值。
**两条算法必须分开**：把它们合成一个函数、内部统一用连乘，是最容易过审但最错的做法——
个股本来能精确算，连乘会给它凭空引入缺天误差。

### 1.2 换过数据供应商

`.TI` → `.FP`，且每个板块切换日不同。2026-03~09 区间里 **128 个板块名跨了两套代码**
（信创、化学制品、光热发电…）。直接 `GROUP BY sector_name` 连乘，等于把两套成分不同的宇宙接起来。

### 1.3 列在库里但一行都没写过值

实测 `fact_stock_daily.turnover` 全库**非空 0 行**。这类最阴：SQL 跑得通、不报错、返回 NULL，
读起来像「这段时间没数据」，其实是写入侧从来没填过。同类还有
`fact_sector_daily.strength`、`fact_market_daily.sh_index_amount`。

## 2. 做法：护栏进返回值，不进注释

`river_query.range_aggregate(start, end, entity, *, kind=None, require_complete=False)`：

- 返回值**强制携带** `coverage`（应有 / 实读 / 缺哪几天，应有天数取自 `fact_market_daily`
  这个唯一的交易日历，**不是「实体自己有几行」**——否则缺天永远测不出来）；
- **强制携带** `codes_seen`，跨换源时写成显式 `caveat`；
- 算不出来的量进 `gaps` 并写明原因（全空列判成 gap，不当 0、不混进正常读数）；
- `require_complete=True` → 覆盖不完整或跨换源时**不给数、只给 gap**，与
  `river.slice_river(require_strict=True)` 同一个态度，参数名也照它。回放 / 校准 / 方法检验必须传它。
- `render_range` **永远打印 caveats 与 gaps**——它们被折叠掉的那一刻这个数就变危险了。

支持的量：`cumulative_return_pct`、`max_drawdown_pct`、`peak_return_pct`(+`peak_date`)、
`amount_sum`、`amount_avg`、`turnover_avg`。

## 3. 真库读数

```
$ python -m intelligence.services.river_query range 算力租赁 2026-08-01 2026-09-02
算力租赁（990306.FP）  2026-08-01 ~ 2026-09-02  [sector/compounded_daily]
  覆盖 23/23 个交易日｜代码 990306.FP        可直接使用：是
  cumulative_return_pct  +8.34
  max_drawdown_pct       -7.32
  peak_return_pct       +10.75（峰值日 2026-08-17）
  限制：板块无收盘点位，区间涨幅由每日涨幅连乘得到；缺一天就少乘一天，结果偏低且不报错

$ ... range 600519.SH 2026-08-01 2026-09-02
贵州茅台（600519.SH）  [stock/close_to_close]   覆盖 23/23    可直接使用：是
  cumulative_return_pct  -3.93     max_drawdown_pct  -6.34
  算不出来的：turnover_avg —— turnover 列存在但区间内 0 行有值（写入侧从未填充）

$ ... range 信创 2026-03-01 2026-09-02
  可直接使用：否——先看下面的限制
  cumulative_return_pct  -32.12
  限制：… 区间跨过供应商换源：读到 2 套代码 ('886013.TI', '990062.FP')，两套口径成分不同

$ ... range 信创 2026-03-01 2026-09-02 --require-complete
  cumulative_return_pct  —      （全部不给数）
  算不出来的：* —— require_complete=True：覆盖不完整或跨换源，本层不给数
```

个股那条同时验证了 1.3：`turnover_avg` 被判成 gap 并写明「写入侧从未填充」，不是 0、不是 NULL。

## 4. 测试与变异

14 条，覆盖：个股走 close 精确（-1.0%）、回撤与峰值日、板块连乘（+8.9%）、
连乘 caveat **永远说**（不是缺天才说）、跨换源报出两套代码、缺天被点名、
**缺天确实会让数偏低**（护栏存在的理由本身被钉住）、应有天数取自市场日历、
`require_complete` 拒绝出数、未知实体给 gap 不给 0、渲染层不省略 caveats。

变异测试：

| 变异 | 实测 |
|---|---|
| `require_complete` 分支短路掉 | 1 红 |
| `codes_seen` 只取第一个（丢掉换源检测） | 3 红 |

## 5. 全量

见 §6。`ruff check`：All checks passed。

## 6. 全量读数

同一隔离壳（`umask 022` + `env -i PATH`）：

```
4 failed, 7888 passed, 8 skipped, 1 xfailed in 644s
```

通过数 7874 → 7888，**恰好 +14 = 本刀新增的 14 条**；4 条红与本线前同一组存量红，归因见
`2026-09-06-observation-script-g03.md` §7。耗时比上一轮的 422s 长，是同机另有会话在跑
（load 4.82），不是本刀引入的慢。

## 7. 没做

- **不回填、不加列、不动同步管线。** 1.3 那三列要真能算，得去查是采不到还是写入漏了——那是另一单。
- `turnover` / `strength` / `sh_index_amount` 现在只能报 gap。
- 只做了「一个实体 × 一段日子」。「一批实体 × 一段日子」（区间横扫排行）没做——
  要做的话护栏得原样带上，否则排行榜上混着一批偏低的数，而且**排序会把偏差放大成名次错误**。
