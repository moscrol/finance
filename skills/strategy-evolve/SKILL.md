---
name: strategy-evolve
description: 策略1/3/4 可验证·可回溯·可迭代的进化生成流水线（scripts/evolve.py + evolution/ 目录）。触发：进化、evolve、自动进化、策略生成迭代、可回溯记录、确定性生成、generate/validate/log/suggest/audit、策略一/三/四确定性名单、前瞻收益验证、参数升版台账。命令驱动、不自动定时；复盘仍由人输口令触发；改规则只改 params.json 并升 version，suggest 只给建议不自动改。
---

# 策略进化系统（evolve）

## 核心定位

一条**命令驱动**的策略进化流水线，独立于人工矩阵（人工矩阵仍由
`scripts/validate_strategy_matrix_forward_returns.py` 验证，两套并行、可互相对照）。

三条铁律：
1. **不自动定时**——复盘由人输口令全量触发；本系统只在你敲命令时运行。
2. **不自动改规则**——`suggest` 只产出建议；改参数必须人工改 `params.json` 并升 `version`。
3. **不解析人工矩阵 HTML**——直接用确定性生成器从 DuckDB 复现名单（无前视）。

代码位置：`evolution/`（策略模块 + 参数）+ `scripts/evolve.py`（CLI）。

## 强制开场（每次先报）

```bash
cd "/Users/lbq/Desktop/c c/金融"
git status --short
git branch --show-current
export PYTHONPATH="$(pwd)"     # 所有 evolve 命令都要在仓库根目录且设 PYTHONPATH
```

## 日常 5 步

```bash
# ① 复盘：你输口令全量复盘，产出当日 fact 层（fact_market/sector/sector_stock/stock/stock_high_daily 入库）
# ② 生成（确定性，策略1/3/4 一起出 + 写生成记录）
python3 scripts/evolve.py generate --date YYYY-MM-DD
#    批量回补：generate --start 2026-04-08 --end 2026-06-12
# ③ 验证（对所有已生成日重算 T+1/3/5，缺数据记 pending）
python3 scripts/evolve.py validate --strategy 1     # 再跑 --strategy 3 / --strategy 4
# ④ 回写 进化.md 的 AUTO 区块（三策略各一张表，手写内容保留）
python3 scripts/evolve.py log
# ⑤ 调参建议（策略一；样本够时给证据，人工确认才生效）
python3 scripts/evolve.py suggest
# 随时体检：前视/格式/缺数据/参数漂移
python3 scripts/evolve.py audit
```

## 三策略口径（scope）

| 策略 | 可选 scope | 默认 | 计入名单 |
|---|---|---|---|
| 1 | `ALL` / `NEWHIGH` / `T1CORE6` | `T1CORE6` | T1CORE6 ⊂ NEWHIGH ⊂ ALL |
| 3 | `S3_ALL` / `S3_FIRST_TOUCH` / `S3_WINDOW` | `S3_ALL` | first_touch + window（SELL/RISK 离场不计入）|
| 4 | `S4_ALL` / `ENGINE_A` / `ENGINE_B` / `OVERLAP` | `S4_ALL` | 引擎A(合格) + 引擎B；OVERLAP=两边都入选 |

`validate --strategy N [--scope X]` 不指定 scope 用默认；结果写 `evolution/validation/cumulative-sN-{scope}.json`。

## 无前视保证（改代码前必读）

三个生成器只读 D0 当日及以前的列，**绝不引用 D0 之后任何字段**：
- `strategy1.py`：D0 三表（成交前三行业 / 当日双红题材 / 行业内开根加权 pct*sqrt(amount) / 新高）。
- `strategy3.py`：口径照搬 `scripts/backfill_strategy3_touch_matrix.py`——核心池=严格前 15 个交易日单日加权 Top20；MA26+0.764σ 通道、dev/pdev 全 D0 回看。
- `strategy4.py`：口径照搬 `scripts/render_strategy4_dual_engine_matrix.py`——引擎A 的 prior7、引擎B 的 hi5 都是"当日及以前"窗口。

`audit` 会持续报研究版 `research/.../strategy1_full_window_0408_0605.py` 的 `rel_strong`（用了次日 `divergence_date` 相对强度＝前视），其 `strategy1-*-selected-detail.csv` **不可当点位名单**。

## 可回溯 / 确定性

- 每天一份 `evolution/records/{date}.json`：
  `{date, params_version, generated_at, strategies:{"1":{top3_industries,coverage,counts,picks}, "3":{coverage,counts,picks}, "4":{gate,coverage,counts,picks}}}`，
  每只票带命中条件（策略4引擎A：`weighted_top20/in_top3_industry/limit_or_repeat7`；策略3：`prev_dev_gt_thr/dev_in_touch_band/in_pool_15d`）。
- **同参数 + 同库 → 100% 复现**：验证方法 = 同日两次 `generate`，剔 `generated_at` 后比 sha256（应逐字节相同）。
- 各生成器 ORDER BY 都加了**代码兜底排序**；极端"完全平手"时入选可能与人工矩阵随机顺序差 1 个名额，属预期。

## 可迭代（改参数的唯一正确姿势）

1. 只改 `evolution/params.json`（唯一可调入口，含 strategy1/3/4 三段）。
2. **升 `version`**，并在 `evolution/params_history.md` 记一行：谁 / 何时 / 为何 / 依据。
3. 重跑 generate → validate → log，旧版结果留痕。

## 验证基准（口径搬对了应复现）

实跑 2026-04-08~06-12（45 天）：
- 策略1 (T1CORE6) 203 名：T+5 胜率 60.1% / 均值 +4.03% / 强命中 42.6% / 失败 22.4%（与独立脚本完全一致）。
- 策略4 (S4_ALL) 479 名：T+5 58.1% / +3.22%（对齐旧 40 天 478 名 / +3.11%）。
- 策略3 (S3_ALL) 436 名：T+5 45.2% / +0.55%（偏弱、失败率高，与旧 +0.85% 同画像）。
- 排序结论：**策略1 > 策略4 > 策略3**。

## 坑 / 注意

- **绝不直接跑** `backfill_strategy3_touch_matrix.py` / `render_strategy4_dual_engine_matrix.py` 来取名单——它们 `main()` 会**重写矩阵 HTML**。只用 `evolution/strategy3.py`、`strategy4.py`（已把 SQL 移植成只读结构化输出）。
- DuckDB 连接：strategy1 用 `market_feature_store.db.connect(read_only=True)`；strategy3/4 用 `duckdb.connect()` 内存库 + `ATTACH '<db>' AS db (READ_ONLY)`（为建 TEMP 表），多个只读句柄可共存。
- Mac 上 **pyyaml 不可用**——参数用 JSON 不用 YAML。
- 生成产物 `evolution/records|validation|suggestions/` 已 `.gitignore`，**不入库**（可由 params.json 重建）；提交只跟踪代码 + params.json + params_history.md。
