# 2026-09-26 · #83 / PR #813 接手前向与范围化复核（快照，写完不改）

Pi 会话 `01a0ce4c` 09-25 把 #83 推到 `ENGINEERING_PASS_QC_PASS_WITH_LIMITS_PENDING_PUBLICATION`
后不再推进。用户 09-26 授权「pi 正在做的，你也接手去收尾」，本轮由 Claude Code 接手收尾子代理（Opus 5，
与原作者 gpt-6-astra 不同模型家族）继续。本文件记本轮做了什么、判了什么、为什么。

## 1. 前向与重叠核对

- 起点 `fix/backfill-ready-main1341-0925 = d62a02ca3`（= Pi 候选 `4f12e65e4` + main@`1341f5c22`）。
- 新树 `/Users/a77/fwp-wt-l4-pr813-0926`，新分支 `l4/pr813-fwd-0926`（原分支已被 Pi 的树占用，不抢）。
- 合入 `gitea/main = 346be5d8b`，普通 merge，**零冲突**。

重叠核对用 `comm -12 <(main 新增文件) <(本线改动文件)`，结果**空集**。
incoming main 的非文档文件只有 `.claude/lessons_learned.md`、`intelligence/services/material_claim_review.py`、
`intelligence/tests/test_e2_material_claim_review.py`、`intelligence/tests/test_judge_loss_point_replay.py`、
`scripts/judge_loss_point_replay.py`、`scripts/review_probes/material_claim_occurrence_mutations.json`。
回填工具是 `market_feature_store/cli.py`、`market_feature_store/sync/repair_backfill_stock_history.py`、
`scripts/verify_302132_backfill_acceptance.py`、`scripts/review_probes/rehearse_302132_backfill.py` 与两个测试文件。
`scripts/review_probes/` 只是同目录不同文件，不构成语义重叠。
→ QC 批 22 绑定的 4f12 业务代码在本前向中**逐字节未变**，C1–C7 结论可以延用，不需要重开付费独审批次。

## 2. 撤保护（本轮实做两次）

**M1 / 对应 C2（守卫上界与源过滤）**：把 `repair_backfill_stock_history.py` 里
`AND h.adjusted='none'` 去掉、上界 `max(spec.gap_parallel)` 改回 `spec.main_fill_end`
→ **红**，`test_backfill_keeps_frozen_tail_source_after_parallel_table_advances` 在
`repair_backfill_stock_history.py:111 RepairRefused` 失败（1F/117P）。保护有真测试。

**M2 / 对应 C4（`--child` 直写生产闸门）**：把 `cli.py::_refuse_production_write_direct` 的
`return 2` 改成 `return None` → **绿**，118P，**变异存活**。

两次都在跑完后立即还原，`git status` 只剩有意的改动。

## 3. 发现的缺陷与修法

`_refuse_production_write_direct` 是 **main 既有**的共享闸门（main@346be5d8b 的 `cli.py` 已有 2 处引用），
本线在 `cmd_repair_backfill_302132` 上**新增了一个执行点**（`cli.py:1594`）。
共享闸门自己的单测 `tests/test_write_path_guard.py` 覆盖的是 `daily-update` / `daily-full-exec` 两条旧链路，
**没有任何测试断言本命令真的把闸门接上了**；QC 的 C4 也是「按 CLI 源码阅读」verified，不是行为断言。
这就是「两层防御要两条断言 / 额度必须在执行点被读到」的形状——闸门没坏，坏的是新执行点无断言。

修法（**只加测试，未动源码**）：
`tests/test_repair_backfill_stock_history.py::test_cli_child_refuses_canonical_production_target`
断言 `--child --db <canonical 生产库>` 必须 rc==2、目标文件字节不变、不生成 `.status.json`，
并把 `run_backfill_child` 换成「调用即 AssertionError」的哨兵。重放 M2 变异 → **红**。
因为没碰被测源码，QC 批 22 对 C1–C7 的源码级结论不受影响。

复核记录全文：`~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L4/review.md`
（含日志 `deprotect-m1.log.txt`、`deprotect-m2.log.txt`、`deprotect-m2-after-fix.log.txt`、
`focused-final.log.txt`）。

## 4. 旧线 `fix/backfill-302132-scoped`（09-14，+12 提交）的判定：**重做，不是丢失**

按 patch-id 比，12 个提交（6 个 `fix`/`feat` + 6 个 `docs(handoff)`）与当前候选**共享 0 个 patch-id**——
但这只说明两条链是不同 lineage（候选是在另一条基线上重写的），patch-id 在这里是错的量具。
按**内容**比（MEMORY 的「被接替链看内容比例不看祖先」）：

| 文件 | scoped 末态 | 当前候选 | 差异行 |
|---|---|---|---|
| `market_feature_store/sync/repair_backfill_stock_history.py` | 775 行 | 776 行 | 5 |
| `scripts/verify_302132_backfill_acceptance.py` | 724 行 | 732 行 | 28 |
| `tests/test_repair_backfill_stock_history.py` | 1136 行 | 1335 行 | 227（候选是超集） |
| `market_feature_store/cli.py` 的 302132 段 | +193 行 | +197 行 | — |

六轮加固的特征串逐个计数相等：`O_EXCL`、`samefile`、`keyset_fullfield`、`golden`、`fingerprint`、
`spec`、`pre_swap`、`oracle` 在两侧同文件里计数一致。

而且候选侧的差异**全是加强**，不是回退：
- sync 模块那 5 行：守卫上界从 `spec.main_fill_end` 收紧到 `max(spec.gap_parallel)`，并加 `h.adjusted='none'`
  源过滤 —— 正是 QC C2 evidence 描述的形状；
- 验收脚本：新增 `spec["code"] == CODE` 授权对象绑定、`math.isfinite` 的 `OverflowError` 兜底、
  把「目标股窗外行数为 0」的 COUNT 检查换成 `target_outside_window_allcols` 全列双向差集。

**建议：关闭 `fix/backfill-302132-scoped`**，接替指针 = PR #813 / 本候选。
它的 6 份 `docs(handoff)` 提交是逐轮自述，内容已被 `docs/handoffs/2026-09-23-backfill-302132-integration.md`
与本线证据根取代，不需要单独保留分支。设计稿
`docs/superpowers/specs/2026-09-14-302132-backfill-execution-design.md` 若确认未随候选带过来，
关闭前单独挑一个 pathspec 提交带上即可（本轮未动，交协调者定）。

## 5. #83 线下可拆的旧候选树（只列，不拆）

下列 worktree 都停在已被取代的旧候选上，合入后可回收（拆前各自确认 `git status` 干净）：

| 路径 | 停在 | 说明 |
|---|---|---|
| `/Users/a77/fwp-wt-backfill-302132` | `fix/backfill-302132-scoped` @ 3736d5bfa | 09-14 旧线，见 §4 |
| `/Users/a77/fwp-wt-backfill-302132-0923` | `fix/backfill-302132-0923` @ 1212ecbfb | 文档树，代码旧，交接已说明不从它验收 |
| `/Users/a77/fwp-wt-backfill-main-ready-0921` | `fix/backfill-main-ready-0921` @ 5994230da | 本地落后远端 PR head |
| `/Users/a77/fwp-wt-backfill-ready-0925` | `fix/backfill-ready-0925` @ f650d9e76 | f650 候选，已被 ae3/4f12 取代 |
| `/Users/a77/fwp-wt-backfill-ready-main648-0925` | `fix/backfill-ready-main648-0925` @ 59c3a87a8 | 中间前向 |
| `/Users/a77/fwp-wt-backfill-ready-main724-0925` | `fix/backfill-ready-main724-0925` @ 47061506f | 中间前向 |
| `/Users/a77/fwp-wt-backfill-ready-main1751-0925` | `fix/backfill-ready-main1751-0925` @ ae3f812e1 | ae3 候选（PR 曾经的 head） |
| `/Users/a77/fwp-wt-backfill-ready-main-e159-0925` | `fix/backfill-ready-main-e159-0925` @ 4f12e65e4 | **QC 绑定身份，建议最后拆** |
| `/Users/a77/fwp-wt-backfill-ready-main1341-0925` | `fix/backfill-ready-main1341-0925` @ d62a02ca3 | 本轮起点 |
| `~/.finance-runtime/reviews/backfill-302132-0923/candidate` | fd6d8cc5b | 旧候选冻结树 |
| `~/.finance-runtime/reviews/backfill-302132-0923/forward-01/tree` | ca4b33316 | 旧前向 |
| `~/.finance-runtime/reviews/backfill-302132-0923/forward-02/tree` | 3c5b3c9a6 | 旧前向 |
| `~/.finance-runtime/reviews/pr813-glm-qc-20260924-01..02` + `20260925-01..10` 的 `candidate`，共 **12 棵** | 3c5b3c9a6 | 批 04–21 的失败/历史 QC 沙箱 |
| `~/.finance-runtime/reviews/pr813-k3-qc-20260924-01/candidate/…` | 3c5b3c9a6 | K3 批（K3 账号已停用） |

注意分母：`~/.finance-runtime/reviews/pr813-glm-qc-*` 一共 **24 个目录**，但只有上表那 12 个是
`git worktree list` 里的真 worktree；其余（含批 22）是独立 clone 或普通目录，
**`git worktree remove` 对它们无效**，要靠 `rm -rf` 单独处理，所以更容易误删。

**必须留的**：
- `~/.finance-runtime/reviews/pr813-glm-qc-20260925-22/`（批 22 全套），其中
  `candidate/` 是 430 MB 的**独立 clone**（不是 worktree），是 QC 报告的被审身份，删了 QC 结论就没有对象；
- `~/.finance-runtime/reviews/pr813-ready-main-e159-0925/`（4f12 工程收据 + 冻结 parquet，生产执行包要用）；
- `~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L4/`（本轮复核与生产执行包）。

## 6. 本轮没做什么

- 没合并、没关 PR、没改标题（`WIP:` 保留）。
- 没写生产库、没跑 `daily-full`、没换库、没重启 8792/8796、没动 launchd。
- 没跑全仓 pytest / 前端 / E2E（共享机准入 + 协调者统一跑四叶）。
- 没花付费模型额度（没开新的 GLM/K3 独审批次）。
- 没拆任何 worktree（§5 只列不拆）。
