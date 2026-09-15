# 2026-09-15 · #592 / #673 / #593 发布门禁与运行面收口

## 范围与结论

用户授权「按最优方案推进」。只处理这三张及其门禁，不扩至其余开放 PR。**未合 main，未切8792，不豁免红灯。** 主检出树的原有代码/文档改动全部保留；获授权的共享副作用只有旁路库及正式方法论收据。

- #673 已于20:44合入 `ce9643b175819191655b36588bdcaaf30a6cfbf7`；#593 已于20:45合入 `1bcb1ebc6a5b411752cacf30b801769711beb677`（Gitea API 核实）。
- #592 原 head `2a0fc382` 真冲突，仅 INDEX #23/#24。独立树前向 merge `fe733616`，保留 main 的 #23 与本单 #24；注册表刷新提交 `9550a9313b7b3353c5f229629d3e56ac1126dff6`。已普通 fast-forward 推回原 PR，**仍 open，待用户确认合并**。PR 评论4588留正式裁决。
- #673 共享旁路库重建、四条规则重跑和漂移登记完成；人工一致率未完成。
- #593 生产样本不足，BP未填，未发付费请求凑20次。

## 1. 独立门禁（不是脏主树）

解释器统一 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python3.12.13，依赖指纹 `3328bed61f3e21ea`。测试采用 `env -i PATH="$PATH" HOME="$HOME"`、umask022。两树均无主库软链；前端在各树按 `pnpm install --frozen-lockfile` 独立安装，非引用主树node_modules。

| 叶子 | main@1bcb1ebc / fwp-wt-release-gate-closeout（修改前） | #592@9550a931 / fwp-wt-checkpoint-bias-sync |
|---|---|---|
| Ruff | 0 | 0 |
| pytest | 9692 passed / 0 failed / 77 skipped / 2 xfailed，369.71s | 9745 passed / 0 failed / 77 skipped / 2 xfailed，393.15s |
| 前端lint/typecheck/test/build | 全0，76 tests | 全0，76 tests |
| Playwright浏览器端到端 | 15 passed | 15 passed |
| registry四check + ledger crosswalk | check红，其余4项0 | 全0 |

Python收据（`~/.finance-runtime/test-receipts/`）：
- main：`20260915T132946Z-1bcb1ebc.json`，产生时干净；此后该树新增审计工具，不能拿该收据证明工具已全量验过。
- #592：`20260915T133709Z-9550a931.json`；在**对应树**执行 `check_test_receipt.py --expect-revision 9550a9313b7b3353c5f229629d3e56ac1126dff6 --base-drift-max 5` exit0，基座漂移0。
- 定向：fe733616六个checkpoint/methodology文件221P；后续新增只读漂移工具4P是另一份dirty定向收据，不混入9745。

**Codex红灯裁决**：本轮未复现两条红，参数化安装探针2P，全量0F。`6d709cfd` 的 runtime文件与main逐字节相同，修复早已等价进入main；没有重复cherry-pick、没有禁网绕过/skip/xfail。上轮失败确切原因未重现，不能仅凭这次绿就追认具体环境根因。

**注册表红灯**：知识库7项skill的computedHash漂移，已核实源文件无未提交改动且KB HEAD=gitea/main=`8a413cde59cd0d6a7757c845243024a3016b50bc`。scan只更新7个hash和generated_at，不删除条目、不改skill正文。main原始全量叶子并非全绿；#592候选携带修复后才全绿。

## 2. 共享旁路库：21:56发布v6

只读冻结主库至 `~/.finance-runtime/release-gate-closeout-20260915/source.duckdb`，源max日期2026-09-15。不是所有fact表同鲜：例如theme_flow仍09-02、hithink仍09-08；完整逐表检查在`data-before.json`，本单不补这些事实。

旧共享库实际v4 / 数据至09-10。复制完整旧库到候选，调用既有 `scripts/methodology_backtest.py build-labels` + `outcomes`，不是新建空库抹掉事件/授课框架产物。

发布前核对源/目标inode、size、mtime无变化、无WAL；复用 `hold_run_mutex` + `hold_swap_lock` 排除协同替换与DuckDB写者；锁内备份、hash核对、fsync、`os.replace`。未写主库。

| 项 | 发布读数 |
|---|---:|
| history_labels | 1,736,327 |
| history_outcomes | 2,277,800 |
| lifecycle_stage | 99,111 |
| opinion_stage | 145,168 |
| labels/outcomes版本 | v6，数据日09-15 |
| 其他表逐行保留 | 15/15（EXCEPT ALL 双向，含重复行） |

- 目标：`db/history_labels.duckdb`
- 备份：`db/history_labels.duckdb.bak-v4-20260915-release-closeout`
- 发布hash：`395eb874bb72b86304fc1214c5ab0bdf3ac6269614a8e48c34c2ecbd2cf7dd2c`
- `data-publish.json`、`labels-published-report.log`为发布/读回凭据；元数据source_db指冻结快照，保留该快照便于重算。
- 保留下来的event系列仍是ev-v0.1 / 09-07，并未伪称随本单刷新。

### 历史标签漂移（不是零漂移）

旧标签主键无丢失、旧日期无新增旧标签行；新日期追加量按标签分列于`label-drift.json`。历史值变化只有：

| 标签 | 变化 | 行数 |
|---|---|---:|
| diff_ratio_turn_up | NULL→0 | 9 |
| dual_red_strict | NULL→0 | 1966 |
| dual_red_streak | NULL→0 | 1966 |

合计3941。它们与已合 #49 `b4d72eab` 的v4→v5三值逻辑修复一致（确定为假的合取式不再记unknown）；其余旧标签值完全不变。#673合并点diff仅加lifecycle标签与版本，不改既有标签算法。**不是严密同源v4/v5/v6消融实验，不宣称所有规则统计变化都已单因子归因**。此前「新增列预期零漂移」只适用于v5→v6，不适用于这次共享库v4→v6。

只读复核工具：
```bash
.venv-workbench/bin/python scripts/audit_methodology_label_drift.py \
  --before db/history_labels.duckdb.bak-v4-20260915-release-closeout \
  --after db/history_labels.duckdb
```

### 四条规则正式重跑

用同一套当前runner先在旧副本跑，再在新副本跑，发布后又对共享库跑。正式唯一写入者仍是CLI `scan`，未手写收据：

```bash
.venv-workbench/bin/python scripts/methodology_backtest.py scan \
  --rules-dir methodology/rules \
  --labels-db /Users/a77/finance-workspace-private/db/history_labels.duckdb \
  --receipts-dir /Users/a77/finance-workspace-private/methodology/receipts \
  --refuted-dir /Users/a77/finance-workspace-private/methodology/refuted
```

| 规则 | 旧库N/命中 | 新库N/命中 | 当前整体结论（含BH） |
|---|---:|---:|---|
| diff_ratio_turn_up_5d | 27787/14978 | 28244/15019 | not_distinguishable |
| dual_red_streak3_continuation | 88/60 | 88/60 | insufficient_n（有效日期块不足） |
| first_board_new_high_1y_5d | 4934/2369 | 4934/2369 | not_distinguishable |
| limit_heat_rank_jump_3d | 13398/7631 | 13632/7647 | not_distinguishable |

旧/新库在**当前runner**下整体结论一致，但不等于与09-11旧算法收据一致。尤其rank_jump独立假设supported被依赖感知统计保守降级；不可沿用09-11整体supported。新库阶段桶「主升」n1588的supported与整体结论分开，不自动晋升方法论。新增lifecycle主题universe也扩大部分规则基准率分母，不把全部统计漂移说成新增交易日。

正式scan汇总：`methodology/receipts/scan/2026-09-15-135611765163-76764d481c5cfe06ae0ef5e6c8a68d7c.json`，其receipt_paths指向四条独立收据。未生成新refuted条目、未改正式规则、未改生产判断台账。

## 3. 人工与生产观察边界

- `stage-agreement`实跑：42条 / 已填0 / min_n30 / `insufficient_n`；未填人工字段。G-04只能标代码及运行面完成，不能标一致率验收完成。
- 生产health实读8792：`source_revision=e40f22b837178322169f47e565282450b4381a3a`、source_dirty=false、code_matches_repo=true；未切生产。
- `research_cost --runs-root ~/.local/share/finance-workbench/users --since 2026-09-15T20:45:59+08:00`：扫描1318，符合统计条件新run0。此时间是**合入时间不是上线时间**；没有把旧run或旁路n=1当生产闭环。
- CLI自报成本对账未完成：需要同一次生产调用的raw成本和metrics；没有冒用旧探针。BP未动。
- 作者handoff仍含运行/人工待办，不整份归档删除。顶部加当前更正与新收口指针，旧正文明确标历史，保留作者决策证据。

## 4. 证据索引与后续

原始日志：`~/.finance-runtime/release-gate-closeout-20260915/`，main-* / candidate-* / rules-before / rules-after / rules-published.log / build-labels.json / build-outcomes.json / label-drift.json / drift-transitions.json / data-publish.json / cost/。`evidence-manifest.json`列初轮文件hash（不含其后新增文件）。

1. 用户确认后才合#592；合并时fetch、merge-tree、复核候选head与基线漂移，main合并点重跑全套。不把本文件分支尖收据冒充main批次收据。
2. 本收口分支的审计工具与文档增量单独审查/合入；原作者树不动。
3. 创始人填至少30条人工标签后再跑stage-agreement并归因。
4. 独立授权部署窗口后切8792、看第一条生产judge_usage，再自然积累≥20 run、同调用成本核对、回填BP。
