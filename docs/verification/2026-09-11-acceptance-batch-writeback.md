# 2026-09-11 验收批次回执（合并 + 验收后续）

> 验收 session 按 `docs/workflows/acceptance-workflow.md` 走完 38 张 open PR 的质检。
> 本文记录：合入清单与门禁读数、共享旁路库 v4 重建与四条规则漂移、填充率基线重钉、过程坑。

## 1. 合入清单（12 张）

批次基座 `gitea/main@c714eb60`。11 张顺序集成（`merge-tree` 逐张实探，不信 Gitea `mergeable`——它对 4 张报错）：

#568 #657 #662 #667 #668 #669 #670 #671 #680 #681 #734 → `gitea/main@5907c9f6`（tree `2e92141d`，与预测试集成树逐字节一致）。

- 合并前集成树全量：**9328P / 0F / 77S / 1xf**；合并后 main tip 复跑同绿，收据 `~/.finance-runtime/test-receipts/20260911T150646Z-5907c9f6.json`，`check_test_receipt --expect-revision 5907c9f6… --base-drift-max 5` exit 0。
- webapp 四件套（lint / typecheck / test 76 / build）绿。
- 第 12 张 **#567** 验收补刀后合入 → `gitea/main@e1068bd3`：前向合并 main + `gen_runtime_catalog.py` 再生成 `docs/runtime/tools.md`（web/news/fetch 5.0s 地板进目录）；不补则 `test_runtime_catalog_is_fresh` 红（门禁比分支分叉点新）。

**关闭 2 张**（内容已在 main，tip 是 `gitea/main` 祖先）：#663（随 #722 链）、#682（随 calc-artifacts-04 链）。
**退回 1 张**：#673 与 #671 撞 `LABEL_VERSION v4`（labels.py / rules.py / test_methodology_backtest.py 真冲突）——按 #671 交接预写方案：rebase 升 v5、错位标记双表并一张。
**真冲突留评论 22 张**：#458 #517 #550 #556 #561 #569 #572 #590 #592 #593 #594 #596（堆叠链，等 #590）#597 #659 #660 #664 #666 #672 #674 #678 #679 #685 #730，冲突文件清单已逐张贴 PR。

首轮 12 张集成树全量曾见 `test_workbench_conversation_integration::test_real_conversation_round_trip…` 1 红：单测 5/5 绿、逐张累积也绿，判读为噪声（方差门：单次探针不下结论），复跑全量 0F 收口。

## 2. 共享旁路库 v4 重建 + 四条规则重跑（#671 验收后续，按 #661 做法）

- 备份：`db/history_labels.duckdb.bak-v3-20260911`（211 MB，v3 建于 09-10 14:22）。
- `build-labels` → `outcomes`（主库只读；`history_build_meta.label_version` 现为 `v4-…-opinion_stage_os_v0`，`opinion_stage` 144,136 行）→ `scan --rules-dir methodology/rules --no-write`。

| 规则 | v3（09-06 g05 对账表） | v4（09-11 本次） | 漂移 |
|---|---|---|---|
| `diff_ratio_turn_up_5d` | N=27,186 → not_distinguishable | N=27,787 → not_distinguishable（阶段桶「下跌」refuted） | N +601 |
| `dual_red_streak3_continuation` | N=88 → not_distinguishable | N=88 → not_distinguishable | 无 |
| `first_board_new_high_1y_5d` | N=4,790 → not_distinguishable | N=4,934 → not_distinguishable | N +144 |
| `limit_heat_rank_jump_3d` | N=13,006 → not_distinguishable | N=13,398 p=57.0% p0=54.8% Wilson=[56.1%,57.8%] → **supported** | **翻 supported** |

判读：四条谓词都不引用新标签 `opinion_stage`，v3→v4 标签语义对它们无变化；漂移来自 v3 建库后新增的交易日（数据窗移动），不是口径变化。`limit_heat_rank_jump_3d` 的 supported 是**新读数不是新结论**——按 #681 的认证链，进入结论候选还要走预声明阶段 + 轮次收据（`queue` 档位自查）。

## 3. 填充率基线重钉（#668 交接指派：#662 合入后重钉）

`check_daily_review_data.py 2026-09-10 --update-fill-rate-baseline`（主库只读、只写 JSON）：

- `fact_market_daily.known_null_dates`：移除 `2026-08-17`（四列洞已由 #668 的派生回填治愈）。
- `fact_stock_daily.known_gaps`：清零（2025-09-18/19 `pct_chg` 派生洞已治愈）。
- 方向为**收紧**（豁免变少）；重钉后 data 阶段 fill-rate 扫描问题 0。

同次门禁的非本批观察（移交数据线，不属回归）：`fact_theme_flow_daily` 最新 2026-09-02（日更滞后）；`fact_core_leader_daily` 2026-09-10 staging=20 行未晋升生产。

## 4. 过程坑（可迁移）

- **/tmp 下的工作树跑不得沙箱类测试**：`test_installed_codex_sandbox_denies_network_and_unix_socket` 在 `/private/tmp/…` 树上稳定假红（Seatbelt 放行 /tmp 写入），同一提交在 `/Users/…` 树上绿。验收树一律放 `/Users`。
- `~/.finance-runtime/test-receipts/latest.json` 会被并发 session 覆盖——校验收据用**钉名文件**（`<ts>-<treesha>.json`），不用 latest。
- Gitea 合并后有 mergeable 重算窗口，紧接着 POST merge 会 405「Please try again later」：先轮询 `mergeable=true` 再合，405 退避重试即可。

## 5. 未做 / 待用户

- 8792 切流（本批合并后另行执行，见台账切流行）。
- 路线图 G-14 / G-02c / G-06 行与 UBIQUITOUS_LANGUAGE 四条词回写在 #666 分支（冲突未合），不代写。
- #734 「正门形态三选一」待拍板：补 `missing_outputs` 修复回路 / 放宽判据认实质 / 契约前移。
