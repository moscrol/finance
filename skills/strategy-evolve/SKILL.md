---
name: strategy-evolve
metadata:
  pattern: pipeline
  also: [generator]
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

## 口径与保证（scope / 无前视 / 可回溯迭代 / 验证基准）

三策略 scope 口径表（策略 1/3/4 可选 scope 与默认）、无前视保证（三个生成器只读 D0 及以前列）、可回溯/确定性（records JSON schema + 同参同库 100% 复现）、改参数的唯一正确姿势、以及 45 天验证基准见 `references/internals.md`。改生成器或调参前必读。

## 坑 / 注意

- **绝不直接跑** `backfill_strategy3_touch_matrix.py` / `render_strategy4_dual_engine_matrix.py` 来取名单——它们 `main()` 会**重写矩阵 HTML**。只用 `evolution/strategy3.py`、`strategy4.py`（已把 SQL 移植成只读结构化输出）。
- DuckDB 连接：strategy1 用 `market_feature_store.db.connect(read_only=True)`；strategy3/4 用 `duckdb.connect()` 内存库 + `ATTACH '<db>' AS db (READ_ONLY)`（为建 TEMP 表），多个只读句柄可共存。
- Mac 上 **pyyaml 不可用**——参数用 JSON 不用 YAML。
- 生成产物 `evolution/records|validation|suggestions/` 已 `.gitignore`，**不入库**（可由 params.json 重建）；提交只跟踪代码 + params.json + params_history.md。
