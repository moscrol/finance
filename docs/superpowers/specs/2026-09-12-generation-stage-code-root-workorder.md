# 工单 #50：夜跑生成段仍从共用脏树 import `intelligence`

> 单类型：接线修复（小到中单，半天到一天）+ 一道回归闸。
> 主仓：金融。优先级 **P2**（不是事故，但它让「夜跑跑的是哪份代码」无法回答）。
> 分支：`fix/generation-stage-code-root`。状态：**作者实现及冻结版本检查完成；待独立复核/用户合并授权，未部署**。
> 来源：`fix/sync-code-root` 第三轮复核 P2；该分支已修同族前四处，此处刻意不顺手改。

## 0. 一句话

`nightly_full_review.sh` 的生成段 `python -m intelligence.cli daily` 跑在
`cd "$WORKSPACE"` 之后，`-m` 把 cwd 放进 `sys.path[0]`，于是 `intelligence`
从**各 agent 共用的主检出树**加载——而质检闸门与同步段已各自钉住代码根，只剩它没钉。

## 1. 读数（2026-09-12 实测，可复跑）

```bash
cd /Users/a77/finance-workspace-private && \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  -c "import intelligence, sys; print(intelligence.__file__); print(repr(sys.path[0]))"
```

| 项 | 值 |
|---|---|
| 加载的包 | `/Users/a77/finance-workspace-private/intelligence/__init__.py` |
| `sys.path[0]` | `''`（即 cwd） |
| 那棵树的状态 | detached `b4a35fa2`，**落后 `gitea/main` 548 个提交**，64 个未提交改动 |

同族已修四处（都在 `fix/sync-code-root`）：sync 子进程代码根、三处质检闸门、
`run_sync()` 裸相对路径、两个手动入口的缺省。**本单是第五处。**

## 2. 为什么不在那一单里顺手改

闸门与同步器只需要「哪个文件」对；生成段要连 `FORESIGHT_USERS_DIR`、episode 目录、
模型网关一起验——同一个进程还会写用户态与 episode，改错根等于把产物写到另一棵树下。
改动面与验收面都比闸门大一档，混进去会让那一单的绿灯说不清覆盖了什么。

## 3. 要做什么

1. 生成段改从显式代码根调用，与 `REVIEW_CHECKER` 同规矩：取不到就 **fail closed**，
   **不回退**到 `$WORKSPACE`（回退会以「看起来合理的理由」产出错版本产物）。
2. 确认同进程写出的用户态 / episode / 导出产物仍落在**数据根**而不是代码根
   ——代码根与数据根这次必须分开验，不能只验 import。
3. 一道回归：钉住调用点不依赖 cwd。

## 4. 验收条件（可证伪，缺一不可）

| # | 判据 | 怎么验 | 期望 |
|---|---|---|---|
| 1 | 加载树 = 钉住的代码根 | 生成段内打印 `intelligence.__file__` | 在钉住的根下，**不含** `finance-workspace-private/intelligence` |
| 2 | 不依赖 cwd | 在任意 cwd 下跑同一命令 | 读数不变 |
| 3 | 产物仍落数据根 | 跑完查 `market_feature_store/exports/`、用户态、episode 目录 | 全在数据根，代码根下零新增文件 |
| 4 | 缺根 fail closed | 把代码根指到不存在的路径 | 非零退出 + 指名原因，**不静默退回** `$WORKSPACE` |
| 5 | 回归可证伪 | 把调用点改回裸 `-m` + cwd | 测试转红；还原转绿 |
| 6 | 全量 | 冻结提交、干净 detached 树 | ruff 绿；pytest 读数与失败项如实记录，不挑绿的那次 |

## 5. 不要做

- 不要把 `WORKSPACE`（数据根）当代码根的兜底——那正是本单要消灭的东西。
- 不要顺手动 `scripts/moneyflow/`：L2 的在途 WIP 就在主检出树里，不是本单的。
- 不要用「跑起来了」当验收：判据 1/3 必须分别量，import 对了不代表产物落对了。

## 6. 作者实现与验收记录（2026-09-15）

代码提交 `0f6c28101b92d654338e705c357778cf1d818a85`；第一版 `2f82d4d3` 只证明外层 argv，已由后续双根启动器与真实子进程测试补齐。未 push/合并/部署。

- 判据1/2/4/5：真实 Python/CLI 和 shell 调用点在隔离双树验证；缺根/错根/包逃出根拒绝；副本改回裸 `-m` 触发旧代码失败，还原通过。
- 判据3的兼容澄清：显式外置 users/episode/DB 保持原位，不迁移存量；相对覆盖按数据根解释。临时库下真实 writer/归档/HTML/队列落盘，代码树哈希不变。episode 是存储接口探针，不是真模型回合；策略矩阵业务 SQL、真实模型及生产数据门仍待验。
- 判据6：干净 `/Users` detached 树全量 **9679P/77S/2x/17 warnings**，Ruff 通过；收据 `20260914T181625Z-0f6c2810.json` 已验 revision/解释器/依赖/干净树一致。前端四步通过（76 tests）、E2E15P、registry四条exit0。跨仓 registry 是现场树检查，见收据边界。
- 完整背景、被否方案、日志路径和下一步：`docs/handoffs/2026-09-15-generation-stage-code-root.md`；活状态：`docs/handoffs/inflight/fix-generation-stage-code-root.md`。

这些检查证明接线，不证明生产日报恢复；独立复核、完整快照部署及生产运行必须分开验收。

## 7. 取号说明

全分支扫描（`refs/heads` + `refs/remotes/gitea`，`git grep '^# 工单 #'`）显示
36–43、46–49 已占用，最大 49，故本单用 **50**。
