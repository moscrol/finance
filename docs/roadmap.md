# 进度观测台薄账（L0 / L1）

- 日期:2026-08-15 · 唯一写入者:检阅方 · spec:`docs/superpowers/specs/2026-08-15-progress-observatory.md` · ADR:`docs/adr/0001-observatory-legislative-core.md`
- **未闭合的最低层:P1**（口径=dsh P0 五步完成数/5；实施 handoff 记第 4 步未完）
- 硬顶 120 行。L2 禁止手写。新 handoff 头部必须带 `roadmap_ref: <L1-ID>`。
- 不是 `docs/layered-rebuild-roadmap.md` / `docs/productization-roadmap.md`（历史长文，禁止往那些文件追加战役状态）。
- L1-DSH 母本 handoff 现只在未合入分支 `feat/dsh-absorption-p0-seams`；该分支下次追加必须含「收口时更新本账 L1-DSH」。

## L0 阶段线

列名:`层 | 闭合 | 当前刻度取数口径 | 本层 L1`。闭合三值:`是` / `否` / `未评`（下层未闭合则禁止宣称本层闭合）。

| 层 | 闭合 | 当前刻度取数口径 | 本层 L1 |
|---|---|---|---|
| P0 领域契约 | 是 | uq15 密封题集存在 + 判分协议版本 | L1-S5 |
| P1 底座 | 否 | dsh P0 五步完成数 / 5 | L1-DSH · L1-S1 |
| P2 观测 | 未评 | trace_depth 档位 + 盲区清单未清项 | — |
| P3 量具+诚实性 | 未评 | 假绿事故数(月)+ 探针在场率 | L1-R24 |
| P4 基线+循环 | 未评 | 账本 confirmed/refuted 命中率 + 最新干净基线批龄 | — |
| P5 质量战线 | 未评 | recall@5 / 交付率 N=3 / uq15 分 | L1-S4 · L1-S9 |
| P6 记忆/资产 | 未评 | memory_gate 裁决量 + corrections 累计 | L1-S6 · L1-S8 |

## L1 战役表

列名冻结:`ID | 战役 | 状态 | 完成判据 | handoff/spec 指针 | 谁在做`。
状态枚举:`planned / in_flight / blocked_on_user / done / dropped`。

| ID | 战役 | 状态 | 完成判据 | handoff/spec 指针 | 谁在做 |
|---|---|---|---|---|---|
| L1-DSH | dsh 吸收 P0 五步 | in_flight | 五步完成且冲突矩阵可画 | `feat/dsh-absorption-p0-seams`（未合 main） | 执行方 / `fwp-wt-dsh-seams` |
| L1-S1 | 时间预算可见 | planned | 状态栏 v1 | `2026-08-15-bookgap-s1-time-budget-statusline.md` | 等 L1-DSH |
| L1-S2 | judge 模态切换 | planned | 数据源回查钩子 | `2026-08-15-bookgap-s2-judge-source-recheck.md` | 等 L1-R24 |
| L1-S3 | 超时窗口比例化 | planned | reserve 推导窗口 | `2026-08-15-bookgap-s3-timeout-ratio-derivation.md` | 等 L1-R24 |
| L1-S4 | recall@k 标注集 | done | 基线文档在场 | #40 | 已合；分数走运行平面 |
| L1-S5 | uq15 出题 | done | 题集+协议+QC 在场 | #33 #35 | 已合；判分未开，不挡 P0 口径 |
| L1-S6 | memory 候选链 | done | 候选→gate→归因 | #41 | 已合 |
| L1-S7 | 行情写锁消除 | done | staging+原子换库 | #39 | 已合；未切见 L1-8792 |
| L1-S8 | 记忆质检清扫 | done | Q3/Q4/Q7/Q8 | #37 | 已合 |
| L1-S9 | KB Hybrid rerank | done | 四臂评测闭环；结论不上线 | #44 · KB PR #12 | 已合；8792 保持 off |
| L1-S10 | branch_tool 诊断 | planned | Phase A 出 PRIMARY | `2026-08-15-bookgap-s10-branch-tool-activation.md` | Phase A 可开 |
| L1-R24 | E-007 修复部署 | blocked_on_user | 独立部署窗落地 | 母本 Round 6 批注 | 用户 |
| L1-8792 | 生产追平 | blocked_on_user | health.revision = main tip | inflight/main.md（已腐，以 live health 为准） | 用户 |
| L1-OBS-P1 | 观测台 Phase 1 生成器 | done | render+--check+好/坏夹具 | `scripts/progress_observatory.py` | 检阅方 |
| L1-OBS | 进度观测台 | in_flight | Phase 1 已合；Phase 2 曲线另案 | `2026-08-15-progress-observatory.md` | 检阅方 |

## 决策队列

| 提出日 | 事项 | 卡在谁 | 关联 |
|---|---|---|---|
| 2026-08-15 | 8792 是否切到含 S7 的 main tip | 用户 | L1-8792 |
| 2026-08-15 | R-24 独立部署窗何时开 | 用户 | L1-R24 |
| 2026-08-15 | dsh 实施分支仍禁止 push，检阅无法从远程看第 4 步 | 用户 | L1-DSH |

Phase 3 挂载面未入列（等 Phase 1 体感，现在不要裁决）。
