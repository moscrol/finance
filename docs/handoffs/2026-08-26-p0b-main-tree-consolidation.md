# 2026-08-26 P0-B 主检出收拢（执行收据）

来源 spec：`docs/superpowers/specs/2026-08-26-post-disclosure-execution-queue.md`（#408，含复核补丁：P0-B 等价判据、sync 时刻 18:30 勘误、r2 冲突点勘误）。
执行树：`/Users/a77/fwp-wt-main-sweep`（`chore/main-tree-artifact-sweep`）。
回滚锚：#408 前 `main=3f802821`；#409 前 `e259956a`；#410 前 `2fdd178b`；#365 前 `e500d609`。

## 合并链（每步合前本机等价检查）

| PR | 内容 | 为什么 |
|---|---|---|
| #408 | 执行队列 spec + 复核补丁 | 排队依据 |
| #409 | 夜跑行为收编：sw-l1 `heavy_timeout` + 双盲回检退役 | **等价判据产物**——夜跑读主树，这两处只活在脏树未提交区，不收编则清树当晚行为回退。public-assets 步 / L2 挂账开关 / market-daily 退役经查 main 已有等价物，不在本 PR |
| #410 | fupanhui 韧性补丁（P0-A，`ff08b2b7` 原样 push，无 force） | 08-24 三源同断的根治；生效前提是本次 P0-B |
| #365 | 退役策略1 md 池 + 追加一笔 SKILL.md 工作区演化版 | SKILL.md 工作区版是该分支版的超集演化（S7 staging 补洞、双 python 辨析、canonical 渲染器表、KB 仓根勘正），追加到它自己的 PR 避免抢文件 |
| 本 PR | 主树 201 条脏区收编 | 台账/handoff/exports/eval runs/复盘 daily/quality 收据 |

## 等价检查读数

预演合并树（main+#409+#410+#365 octopus，零冲突）：ruff 绿；全量 pytest **6551P / 12S / 1F**。
唯一红 `test_installed_codex_sandbox_denies_network_and_unix_socket` 在干净 main **同断言同值**
（本机 codex sandbox 佐证态 `unproven`，环境性存量红，非本批引入；存量红对照法沿 08-23 r2 先例）。

## 处置决策

- **16 份「脏树 untracked 草稿 vs main 已合正式版」碰撞**（7 份 2026-08-16 handoff + 9 份 superpowers spec/plan）：弃本地旧稿。方向抽查证实 main 版带后续收口批注（如 deploy-window 的「#81/#83 已合」、retrieval-tier 的 Implemented 状态行），本地是批注前草稿。
- **6 份双向演化文件**（`lessons_learned` / `prediction-ledger` / `trace-profile` / `2026-08-18-recovery` handoff / `inflight/main.md` / `skills.registry.json`）：按时间线并集。registry 取 main 版（`aed85302` 刚重扫 hash，脏树手改是未同步旧稿；IMA 纪律正文活在 CLAUDE.md）。台账 theirs 侧的 `R-20260815-21`(pending) 是旧稿重复，弃；4 条 SPTTECH 行并入。
- **fix_type refuted streak 按合并后全表重算**（135 行 verdict）：`DATA_CONTRACT_FIX=1`（`R-20260823-SPTTECH-02` refuted 是该型最新 verdict）；`HARNESS_FIX=0`（08-24 refuted 被 08-25 两条 confirmed 归零）——两边原值（main 全 0 / 脏树 1,1,1）都是各自视角的旧数。
- `inflight/feat-reading-rules-baseline-batch1.md`：main 已删，不复活（内容在分支 ref + 归档 diff）。
- **流浪文件归档** `~/fwp-p0b-archive-20260826/`：`knevo-upload-probe.csv`（6 行探针玩具）、根目录 `package.json`（leila-codex-mac 项目误落）；另存全量未提交 diff `worktree-uncommitted-all.diff`。
- **gitignore 新增** `/state/` `/work/` `/.playwright-mcp/`（锚定根目录：运行时旗标/锁/部署账本/调试快照；`skills/daily-full-review/state/` 收据不受影响）。`state/l2-paused.flag` 保留在盘（运行态开关，等 ClickHouse 鉴权恢复后删除即恢复 L2）。
- **已知残缺不修**：`perspective-distill/SKILL.md` L122/L135 共 5 个 U+FFFD 为 main 存量损伤（main 版同位同量），原文不可靠重构，留待有原稿者修。

## 验收状态

- 主树 `git status` 空 + 回 `main` 同 SHA：本 PR 合并后执行（spec §P0-B 验收句）。
- 判别变量（下一交易日 18:30 sync / 20:40 finalize 免人工 same-day COMPLETE）：**今晚出读数**，届时夜跑首次吃 main 树（含 #409/#410/#365 全部行为）。
- P0-C（#343 三树收口 → r3）与 P2（盘中 L2，等 ClickHouse 鉴权 Code 516）本轮未动。
- 19 张历史积压 PR（#122–#308）不在本队列（spec §3 事实 8）。
