# 进度观测台薄账（L0 / L1）

- 日期:2026-08-16 · 唯一写入者:检阅方 · spec:`docs/superpowers/specs/2026-08-15-progress-observatory.md` · ADR:`docs/adr/0001-observatory-legislative-core.md`
- **未闭合的最低层:P1**（口径=dsh P0 五步完成数/5；第 1–7 步已收口，冲突矩阵未画，第 8 步未开）
- 硬顶 120 行。L2 禁止手写。新 handoff 头部必须带 `roadmap_ref: <L1-ID>`。
- 不是 `docs/layered-rebuild-roadmap.md` / `docs/productization-roadmap.md`（历史长文，禁止往那些文件追加战役状态）。
- L1-DSH 母本仍只在未合入分支 `feat/dsh-absorption-p0-seams`（已 push，tip `b06fb5d5`）；第 8 步 A/B 未开。

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
| L1-DSH | dsh 吸收 P0 五步 | in_flight | 五步完成且冲突矩阵可画 | `feat/dsh-absorption-p0-seams` @ `b06fb5d5`（第 1–7 步已收口；第 8 步未开；未合 main） | 执行方 / `fwp-wt-dsh-seams` |
| L1-S1 | 时间预算可见 | planned | 状态栏 v1 | `2026-08-15-bookgap-s1-time-budget-statusline.md` | 等 L1-DSH |
| L1-S2 | judge 模态切换 | planned | 数据源回查钩子 | `2026-08-15-bookgap-s2-judge-source-recheck.md` | 窗已开，可另开 PR |
| L1-S3 | 超时窗口比例化 | planned | reserve 推导窗口 | `2026-08-15-bookgap-s3-timeout-ratio-derivation.md` | 窗已开，可另开 PR |
| L1-S4 | recall@k 标注集 | done | 基线文档在场 | #40 | 已合；分数走运行平面 |
| L1-S5 | uq15 出题 | done | 题集+协议+QC 在场 | #33 #35 | 已合；判分未开，不挡 P0 口径 |
| L1-S6 | memory 候选链 | done | 候选→gate→归因 | #41 | 已合 |
| L1-S7 | 行情写锁消除 | done | 夜跑 sync 走 staging 换库 | #39 · `2026-08-16-s7-nightly-staging.md` | 18:30 已挂；8792 不因 S7 切 |
| L1-S8 | 记忆质检清扫 | done | Q3/Q4/Q7/Q8 | #37 | 已合 |
| L1-S9 | KB Hybrid rerank | done | 四臂评测闭环；结论不上线 | #44 · KB PR #12 | 已合；8792 保持 off |
| L1-S10 | branch_tool 诊断 | done | Phase A 出 PRIMARY | `docs/verification/2026-08-15-s10-branch-activation.md`（零调用未复现；`ROOT_CAUSE_NOT_CONFIRMED`） | Phase A 已交；Phase B 未开 |
| L1-R24 | E-007 修复部署 | done | 独立部署窗落地 | #49 · `2026-08-16-r24-deploy-window.md` | 已切 `437cd5e9`；live 结案仍看账本 |
| L1-8792 | 生产追平 | done | 已切含 #49 的干净快照；其后 docs-only tip 不追切 | `2026-08-16-r24-deploy-window.md` | 8792=`437cd5e9`；旧快照 `fdb23114` 可回滚 |
| L1-OBS-P1 | 观测台 Phase 1 生成器 | done | render+--check+好/坏夹具 | `scripts/progress_observatory.py` | 检阅方 |
| L1-OBS-P2 | 观测台 Phase 2 趋势曲线 | done | 两条曲线≥3真实历史点 | `scripts/progress_observatory.py` | 检阅方 |
| L1-OBS | 进度观测台 | in_flight | Phase 2 已合（交付率/命中率≥3真实点）；Phase 3 挂载面另案 | `2026-08-15-progress-observatory.md` | 检阅方 |

## 决策队列

| 提出日 | 事项 | 卡在谁 | 关联 |
|---|---|---|---|
| 2026-08-16 | 是否开第 8 步 live A/B 校准窗（先 45× Arm A） | 用户 | L1-DSH |
| 2026-08-16 | 不切 8792 追 S7；夜跑 sync 已挂 staging | 已决 | L1-S7 |
| 2026-08-16 | R-24 独立部署窗已开；8792=`437cd5e9`（为 R-24，不是为 S7） | 已决 | L1-R24 |
| 2026-08-16 | dsh 实施分支已 push 到 `b06fb5d5`（第 1–7 步） | 已决 | L1-DSH |
| 2026-08-16 | 安全 ref `prerebase/dsh-seams-e21c50bf` 保留到合 main；已备份远程 | 已决 | L1-DSH |

Phase 3 挂载面未入列（等 Phase 1 体感，现在不要裁决）。
