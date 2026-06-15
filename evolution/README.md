# evolution —— 可验证·可回溯·可迭代进化的策略生成（策略 1/3/4）

**定位**：在你"手动口令全量复盘"产出当日 fact 层之后，由命令触发的一条自包含流水线。
不自动定时、不自动改规则、不解析人工矩阵 HTML；人工矩阵仍由
`scripts/validate_strategy_matrix_forward_returns.py` 验证，两套并行、可互相对照。

## 闭环（每步都要你敲命令）

```
你输口令 → 全量复盘（产出当日 fact 层，入库 fact_market/sector/sector_stock/stock/stock_high_daily）
   │
   ▼
python3 scripts/evolve.py generate --date YYYY-MM-DD   # ① 确定性生成 策略1/3/4 名单 + 生成记录
python3 scripts/evolve.py validate --strategy 1        # ② 对所有已生成日重算 T+1/3/5（到期才算）
python3 scripts/evolve.py validate --strategy 3        #    策略三（默认 S3_ALL）
python3 scripts/evolve.py validate --strategy 4        #    策略四（默认 S4_ALL）
python3 scripts/evolve.py log                          # ③ 把各策略齐备结果写回 进化.md（AUTO 区块）
python3 scripts/evolve.py suggest                      # ④ 策略一样本够时给调参建议（仅建议，人工确认）
python3 scripts/evolve.py audit                        # 随时体检：前视/格式/缺数据/参数漂移
```

> 运行需在仓库根目录且设 `PYTHONPATH`：
> `cd "金融" && PYTHONPATH="$(pwd)" python3 scripts/evolve.py <子命令> ...`

## 三个策略的口径（scope）

| 策略 | 可选 scope | 默认 | 计入名单的层 |
|---|---|---|---|
| 1 | `ALL` / `NEWHIGH` / `T1CORE6` | `T1CORE6` | T1CORE6 ⊂ NEWHIGH ⊂ ALL |
| 3 | `S3_ALL` / `S3_FIRST_TOUCH` / `S3_WINDOW` | `S3_ALL` | first_touch + window（SELL/RISK 为离场，不计入）|
| 4 | `S4_ALL` / `ENGINE_A` / `ENGINE_B` / `OVERLAP` | `S4_ALL` | 引擎A(合格) + 引擎B；OVERLAP=两边都入选 |

`validate --strategy N [--scope X]` 不指定 scope 时用上表默认；结果写
`validation/cumulative-sN-{scope}.json`。`log` 会把 `validation/` 下所有
`cumulative-s*.json` 各出一张表，合并写进 进化.md 的 AUTO 区块。

## 可验证 / 可回溯 / 可迭代 怎么落地

- **可验证**：`validate` 用 `fact_stock_daily` 真实收盘算 T+1/3/5，基准=D0 收盘；缺未来交易日记 pending，绝不拿缺失数据算胜率。`validate.py` 与策略无关，对任意 `{date:[code]}` 名单通用。
- **可回溯**：每天一份 `evolution/records/{date}.json`，结构为
  `{date, params_version, generated_at, strategies:{"1":…,"3":…,"4":…}}`，
  每个策略子负载含 **coverage（数据覆盖）+ counts + 每只票命中的条件**。同参数 + 同库 → 100% 复现（各策略 ORDER BY 均加了代码兜底排序）。
- **可迭代**：改规则只改 `params.json` 并**升 version**、在 `params_history.md` 记一行依据；`suggest` 用历史已到期样本做参数网格回测给证据，但**只建议不自动改**，防过拟合。

## 无前视保证

三个生成器都只读 D0 当日及以前的数据，绝不引用 D0 之后任何列：
- `strategy1.py`：D0 三表（前三行业 / 双红题材 / 行业内开根加权 / 新高）。
- `strategy3.py`：口径照搬 `scripts/backfill_strategy3_touch_matrix.py`——核心池=严格前 15 个交易日的单日加权 Top20；MA26+0.764σ 通道、dev/pdev 全是 D0 回看。
- `strategy4.py`：口径照搬 `scripts/render_strategy4_dual_engine_matrix.py`——引擎A 的 prior7、引擎B 的 hi5 都是"当日及以前"窗口。

（对比：研究版 `research/.../strategy1_full_window_0408_0605.py` 的 `rel_strong` 用了次日
`divergence_date` 相对强度＝前视，其 `strategy1-*-selected-detail.csv` 不可作点位名单——`audit` 会报。）

> 注：策略3/4 生成器的 ORDER BY 加了代码兜底排序以保证确定性，极端"完全平手"时入选哪只可能与人工矩阵的随机顺序有 1 个名额的差异，属预期。

## 目录

- `params.json`        版本化参数（唯一可调入口，含 strategy1/3/4 三段）
- `params_history.md`  参数变更台账（人工记录）
- `strategy1.py`       策略一确定性生成器（`generate_for_date` / `payload_for_date` / `picks_in_scope`）
- `strategy3.py`       策略三确定性生成器（`generate_range` / `picks_in_scope`）
- `strategy4.py`       策略四双引擎确定性生成器（`generate_range` / `picks_in_scope`）
- `validate.py`        前瞻收益验证（策略无关，可复用）
- `records/`           每日生成记录（可回溯；.gitignore 忽略）
- `validation/`        累计验证结果（.gitignore 忽略）
- `suggestions/`       调参建议（仅供人工确认；.gitignore 忽略）
