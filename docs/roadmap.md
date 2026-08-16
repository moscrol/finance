# 进度观测台薄账（L0 / L1）

- 日期:2026-08-16 · 唯一写入者:检阅方 · spec:`docs/superpowers/specs/2026-08-15-progress-observatory.md` · ADR:`docs/adr/0001-observatory-legislative-core.md`
- **未闭合的最低层:P2**（口径=trace_depth 档位 + 盲区清单未清项；五步+冲突矩阵已收口；Arm A 45× 已跑，对照未开）
- 硬顶 120 行。L2 禁止手写。新 handoff 头部必须带 `roadmap_ref: <L1-ID>`。
- 不是 `docs/layered-rebuild-roadmap.md` / `docs/productization-roadmap.md`（历史长文，禁止往那些文件追加战役状态）。
- L1-DSH 实施已合 main（#61）；#69 已按 0.1375 锁 30×15=450/臂。对照仍未开。

## L0 阶段线

列名:`层 | 闭合 | 当前刻度取数口径 | 本层 L1`。闭合三值:`是` / `否` / `未评`（下层未闭合则禁止宣称本层闭合）。

| 层 | 闭合 | 当前刻度取数口径 | 本层 L1 |
|---|---|---|---|
| P0 领域契约 | 是 | uq15 密封题集存在 + 判分协议版本 | L1-S5 |
| P1 底座 | 是 | dsh P0 五步完成数 / 5 | L1-DSH · L1-S1 |
| P2 观测 | 否 | trace_depth 档位 + 盲区清单未清项 | — |
| P3 量具+诚实性 | 未评 | 假绿事故数(月)+ 探针在场率 | L1-R24 |
| P4 基线+循环 | 未评 | 账本 confirmed/refuted 命中率 + 最新干净基线批龄 | — |
| P5 质量战线 | 未评 | recall@5 / 交付率 N=3 / uq15 分 | L1-S4 · L1-S9 |
| P6 记忆/资产 | 未评 | memory_gate 裁决量 + corrections 累计 | L1-S6 · L1-S8 |

## L1 战役表

列名冻结:`ID | 战役 | 状态 | 完成判据 | handoff/spec 指针 | 谁在做`。
状态枚举:`planned / in_flight / blocked_on_user / done / dropped`。

| ID | 战役 | 状态 | 完成判据 | handoff/spec 指针 | 谁在做 |
|---|---|---|---|---|---|
| L1-DSH | dsh 吸收 P0 五步 | done | 五步完成且冲突矩阵可画 | #61 · #69 · `2026-08-16-dsh-arm-a-calibration-receipt.md`（锁 450/臂；对照未开） | 已合 main |
| L1-S1 | 时间预算可见 | done | 状态栏 v1 | #65 · `2026-08-15-bookgap-s1-time-budget-statusline.md` | 已合；默认开；`ASK_EPISODE_BUDGET_STATUS=off` 可关 |
| L1-S2 | judge 模态切换 | done | 数据源回查钩子 | #60 · `2026-08-15-bookgap-s2-judge-source-recheck.md` | 已合；默认 off；10 题对照实验未跑 |
| L1-S3 | 超时窗口比例化 | done | reserve 推导窗口 | #63 · `2026-08-15-bookgap-s3-timeout-ratio-derivation.md` | 已合；3 题冒烟未跑；不追切 8792 |
| L1-S4 | recall@k 标注集 | done | 基线文档在场 | #40 | 已合；分数走运行平面 |
| L1-S5 | uq15 出题 | done | 题集+协议+QC 在场 | #33 #35 | 已合；判分未开，不挡 P0 口径 |
| L1-S6 | memory 候选链 | done | 候选→gate→归因 | #41 | 已合 |
| L1-S7 | 行情写锁消除 | done | 夜跑 sync 走 staging 换库 | #39 · `2026-08-16-s7-nightly-staging.md` | 18:30 已挂；8792 不因 S7 切 |
| L1-S8 | 记忆质检清扫 | done | Q3/Q4/Q7/Q8 | #37 | 已合 |
| L1-S9 | KB Hybrid rerank | done | 四臂评测闭环；结论不上线 | #44 · KB PR #12 | 已合；8792 保持 off |
| L1-S10 | branch_tool 诊断 | done | Phase A 出 PRIMARY | `docs/verification/2026-08-15-s10-branch-activation.md`（零调用未复现；`ROOT_CAUSE_NOT_CONFIRMED`） | Phase A 已交；Phase B 未开 |
| L1-R24 | E-007 修复部署 | done | 独立部署窗落地 | #49 · `2026-08-16-r24-deploy-window.md` | 已切 `437cd5e9`；live 结案仍看账本 |
| L1-8792 | 生产追平 | done | 已切含 #49 的干净快照；其后 tip 不追切（含特性合并） | `2026-08-16-r24-deploy-window.md` · `2026-08-16-deploy-window-773b3d7e.md` | 8792=`773b3d7e`（目录名仍 `437cd5e9aa1a`）；卫生 HOLD 并进修复+#84 |
| L1-OBS-P1 | 观测台 Phase 1 生成器 | done | render+--check+好/坏夹具 | `scripts/progress_observatory.py` | 检阅方 |
| L1-OBS-P2 | 观测台 Phase 2 趋势曲线 | done | 两条曲线≥3真实历史点 | `scripts/progress_observatory.py` | 检阅方 |
| L1-OBS | 进度观测台 | in_flight | Phase 2 已合（交付率/命中率≥3真实点）；Phase 3 挂载面另案 | `2026-08-15-progress-observatory.md` | 检阅方 |

## 决策队列

| 提出日 | 事项 | 卡在谁 | 关联 |
|---|---|---|---|
| 2026-08-16 | 第 8 步先半段 45× Arm A 已跑；30×3 半宽 10.8pp，加题/加重复，不许放宽 5pp | 已决 | L1-DSH |
| 2026-08-16 | 按官方 v=0.1375 重锁 30×15=450/臂；草稿 0.125/30×13 dropped（#69） | 已决 | L1-DSH |
| 2026-08-16 | 扩样到 n×r≈423 再上 Arm B，还是先另开窗 | 用户 | L1-DSH |
| 2026-08-16 | 不切 8792 追 S7；夜跑 sync 已挂 staging | 已决 | L1-S7 |
| 2026-08-16 | R-24 独立部署窗已开；8792=`437cd5e9`（为 R-24，不是为 S7） | 已决 | L1-R24 |
| 2026-08-16 | 为长尾对照窗切 8792=`773b3d7e`（就地切树，非 R-24 窗重开）；12:09 后 rag_worker 钉死 ~1h，13:08 kickstart 修复 | 已决 | L1-8792 |
| 2026-08-16 | 回滚梯子已留独立 clone：`finance-workspace-773b3d7e73d7` 与 `finance-workspace-437cd5e9aa1a-rollback`；未启动、未链切。`outlook-pre` 是 10 题修前臂，不作生产回滚 | 已决 | L1-8792 |
| 2026-08-16 | #84 `21dbf6c1` 已合（`timeout_asked` 埋点）；自书不切 8792，也不是 10 题第二道闸。停泊树 `finance-workspace-21dbf6c1d83f` 未启动，不作生产链切目标 | 已决 | L1-8792 |
| 2026-08-16 | 窗间隙 16:09 已确认（#87 已合、8793 停、workers.active=0）。目录卫生 HOLD：并进 B 修复部署（新 SHA 快照消错位 + 顺带 #84），避免两次 kickstart | 已决 | L1-8792 |
| 2026-08-16 | 10 题窗仍等判断正文修复或书面豁免（#84 埋点不是第二道闸） | 用户 | L1-8792 |
| 2026-08-16 | prewarm 不抬 timeout（第三次无失败当次延迟）；切后必查 `/api/health/ready`，失败 kickstart 同快照一次 | 已决 | L1-8792 |
| 2026-08-16 | dsh 接缝已合 main #61；第 8 步 live A/B 未开 | 已决 | L1-DSH |
| 2026-08-16 | 安全 ref `prerebase/dsh-seams-e21c50bf` 已删（本地+gitea）；SHA `e21c50bfdbdb` 仍可解引用 | 已决 | L1-DSH |
| 2026-08-16 | Arm A 校准脚手架已合 #67；live 45× 已跑，对照未开 | 已决 | L1-DSH |
| 2026-08-16 | S1 时间预算已合 #65；默认注入；live 率未读 | 已决 | L1-S1 |
| 2026-08-16 | S2 回查钩子已合 #60；默认 off；对照实验未跑；不追切 8792 | 已决 | L1-S2 |
| 2026-08-16 | S3 窗口推导已合 #63；ASK_* 只下压；3 题冒烟未跑；不追切 8792 | 已决 | L1-S3 |
| 2026-08-16 | 闸 2 三选一（豁免 #89 §3）：用户 16:58 拍板**选 2**——豁免成立但不翻闸，先修 judge transient（`R-20260816-06`：judge 埋点 → 8795 重放 → H8/H9 → 处置 PR），处置部署 8792 后眼 agent 再翻闸开 10 题窗；交接 `2026-08-16-judge-transient-r06.md` | 已决 | L1-8792 |

Phase 3 挂载面未入列（等 Phase 1 体感，现在不要裁决）。
