# 整合候选门禁与 hithink 隔离库对账（2026-09-13 晚）

候选：`integration/daily-swap-hithink-candidate-0913` @ **044d1661**（merge commit）。
双方 tip 固定：`gitea/main@e40f22b8` + `fix/daily-swap-lock-all-callers@ce67fe6a`。
唯一冲突 `.claude/lessons_learned.md`（append-vs-append，双方保留）。
授权口径：只组装候选 + 跑门禁 + 隔离库对账；**未合并 main、未切运行时、未碰生产库**。

## 合并完整性

- 候选 vs main 范围：16 文件 / 3,941+ / 51-。
- 分支携带的 16 文件中 15 个与分支 tip 逐字节相等；唯一差异是 lessons 冲突
  解决（保留双方，+20 行）。

## 四片叶子（各自独立出结果，无跳过）

统一解释器 `.venv-workbench/bin/python`；候选树干净（收据 JSON dirty=false）。

| 叶子 | 结果 |
|---|---|
| python | `ruff check .` 全过；全量 **9,608 passed / 0 failed / 77 skipped / 2 xfailed，515s，exit 0**，收据 `20260913T131316Z-044d1661.json` |
| frontend | `pnpm install --frozen-lockfile` / `lint` / `typecheck` / `test` / `build` 全 exit 0 |
| e2e | `pnpm test:e2e`（WORKBENCH_PYTHON=venv）：**15 passed**，exit 0 |
| registry-check | `build_registry.py` 四条 --check + `audit_ledger_spec_crosswalk.py` 全绿 |

诚实边界：已知抖动的 `test_installed_codex_sandbox_denies_network_and_unix_socket`
本轮全量恰好绿；根因仍未查清，**绿不等于修好**，不据此豁免它将来的红。
skipped 77 与八轮收据的 79 差 2，属环境相关跳过项差异，未逐条追。

## hithink 隔离库对账（冻结输入 + 逐值核对，不只看行数）

脚本与证据：`~/.finance-runtime/gate-checkouts/daily-swap-candidate-20260913/reconcile/`
（`reconcile_hithink.py` → `recon-report.json` + `recon-repair-report.json`）。
冻结输入 parquet sha256 `51f9ee9c…8d17`；隔离库=生产新鲜克隆，修复全锁链
（互斥→基线窗口→子进程→守卫→锁内备份→原子换名）跑在候选代码上，cli rc=0。

| 验收项 | 结果 |
|---|---|
| 主表 | 09-11 共 **5,553 行** = hithink:daily-k-10d 5,547 + eastmoney:snapshot 6；子进程报告 field_diffs 全 0，唯一白名单漂移 600176 amount 113.6007→113.6006 |
| 逐值 | 302132.SZ = 63.42 / 64.35 / −1.45 / 5.9863 亿 / 94,471 手（钉值全中）；600176 amount=113.6006 |
| 派生一致 | technical 重算 5,529；window 22,117 staged − 302132 删 2 = **22,115**（自洽）；600176 十日 avg_amount 93.1063→93.1062（文档漂移值兑现） |
| 302132 置缺 | 两派生表当日 **0 行**，报告声明「历史窗口不足，置缺；回填需单独授权」 |
| 非目标日期不变 | 三张主/派生表非目标日期 **EXCEPT 双向全 0**（逐行精确，不是行数）；fact_market_daily 全表 EXCEPT 双向 0（复盘会口径未动） |
| 板块拼接 | dry_run 同条件对照：修后 **403/403**（对照克隆同 403；接受值源行 5,549→5,550） |
| 备份 | receipt.backup_sha256 == 备份文件 sha256 == 换前克隆 sha256（`c44a0f50…f9ca`）；恢复步骤 6 条在场；只读验证 66 张表 |
| ops 收据 | 最新行 kind=`repair-stock-daily-hithink`，ok=true，plan=`staging-swap` |
| 生产库 | 前后 sha256 + (ino, mtime_ns, size) 完全不变（未动） |

## 结论与待授权

候选门禁四叶全绿 + 隔离库对账全项通过。**仍未做**：合并 main、切运行时、
生产库写入/换库、302132 历史回填（需单独授权并验证连续性）、并跑表补齐。
合并授权与生产换库授权须分别申请。
