# strategy-evolve 口径与保证

> 本文件由 `skills/strategy-evolve/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

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
