# S8 · 记忆质检遗留清扫：Q3 / Q4 / Q7 / Q8

- 索引：`2026-08-15-bookgap-index.md` · 靶：08-13 质检遗留 · 仓：finance · 优先级 P2
- 并行安全：记忆/时间线 services 面；**与 S6 并行时 `memory_status.py`
  归本 spec 改，S6 只读**（索引 §2 之外的局部约定）

## 1. 背景

`docs/superpowers/specs/2026-08-13-memory-quality-review.md` §1.2 的
四条 0/1 档缺陷，至今未清（Q1/Q2 归 S4，Q5 是文档口径不是 bug，
Q6 明确「不要为接线而接线」不做，Q9 顺手改状态行）：

| # | 缺陷 | 原判 |
|---|---|---|
| Q3 | 记录身份 = `ts`，同秒并发碰撞 | 新增时写 `id=sha256(kind+ts+content)[:12]`，旧行仍认 ts |
| Q4 | 跟踪契约 prompt-only，live 遵守不全 | 接到已有 `repair_coordinator.missing_outputs`——能程序判定的约束进程序，不堆 prompt |
| Q7 | 板块口语名对不上 `fact_sector_daily.sector_name` | 别名走已有 `resolve_query_themes` / `dim_sector`，时间线入口收敛 |
| Q8 | 时间线 25 段仍偏碎 | 最短阶段时长（<3 日切段合并），滞回已解决的回流抖动不重做 |

## 2. 目标 / 非目标

- 目标：四条按原判处方逐条落地，每条独立提交（可单独 revert）。
- 非目标：不动 `memory_gate.py`；不改 experience cards 的退出语义
  （Q5 判过「两套出口是对的」）；不动 D10 接线（Q6）。

## 3. 改动面

| 条 | 文件 |
|---|---|
| Q3 | `user_memory` 记录写入处 + `memory_status.py`（覆盖行 target 兼容 id/ts 双键）+ 迁移说明（不迁旧数据） |
| Q4 | `track_contract.py`：契约要求的输出项对 `repair_coordinator.missing_outputs` 做程序核对，缺项写进收据字段（EVAL 可读），prompt 原文不动 |
| Q7 | `theme_lifecycle_timeline.py` 入口加别名解析（复用 `resolve_query_themes`），解析不到仍显式降级 |
| Q8 | `theme_lifecycle_timeline.py` 加 `min_phase_days`（默认 3），与滞回参数正交 |
| 测试 | 每条 1–2 个：Q3 同秒两条记录 id 不碰撞且旧 ts 行可退出；Q4 缺项收据字段在场；Q7 「液冷」别名命中；Q8 固态电池夹具段数 25→明显下降且无 <3 日段 |
| Q9 | `2026-08-13-memory-analog-lifecycle-design.md` 文首状态行改「已实施（六 slice）」 |

## 4. 验收判据（预注册）

1. 四条各自测试绿，且四个提交能独立 cherry-pick（检阅方会抽验一条）。
2. Q4 红线：不新增任何 prompt 文本（diff 里 prompt 文件零改动）。
3. Q8 用 08-13 live 同一夹具（固态电池 53→25 那份）对照出段数，
   报告前后段数与被合并段清单。
4. 全量记忆面相关单测（`test_memory_status`、`test_track_contract`、
   `test_theme_lifecycle_timeline`、`test_market_regime_analogs`）绿。

## 5. 风险

- Q3 双键兼容面窄：只兼容「旧行按 ts 退出」，不做全量回填——写清就够。
- Q8 的「明显下降」不预设具体数：以「无 <3 日段」为硬判据，段数只报不判。
