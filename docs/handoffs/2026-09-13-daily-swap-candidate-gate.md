# 整合候选门禁与 hithink 隔离库对账（2026-09-13 晚）

候选：`integration/daily-swap-hithink-candidate-0913` @ **044d1661**（merge commit）。
双方 tip 固定：`gitea/main@e40f22b8` + `fix/daily-swap-lock-all-callers@ce67fe6a`。
唯一冲突 `.claude/lessons_learned.md`（append-vs-append，双方保留）。
授权口径：只组装候选 + 跑门禁 + 隔离库对账；**未合并 main、未切运行时、未碰生产库**。

## 合并完整性（十一轮 P2 修正后口径）

- **merge payload**（merge commit 044d1661 携带，稳定锚）：16 文件 / 3,941+ / 51-。
- **候选 tip 层**（payload 之上）：全部是落账/证据提交——两份交接文档、门禁脚本
  `scripts/reconcile_hithink_gate.py`、证据包 `docs/handoffs/evidence/*.json`，无额外
  代码改动；tip 相对 main 的文件数随落账增长，**审计以
  `git diff --stat e40f22b8..<tip>` 实况为准**（十二轮时曾写作 17/3,993，随后还会变）。
- 分支携带的 16 个代码/文档文件与分支 tip 逐字节相等（合并完整性核验过）。
- 唯一冲突解决差异：lessons_learned.md 保留双方（+20 行）。

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
| 非目标日期不变 | 三张主/派生表非目标日期 **EXCEPT ALL 双向全 0**（含重复行 multiplicity；四表另有主键约束）；fact_market_daily 全表 EXCEPT ALL 双向 0（复盘会口径未动） |
| 板块拼接 | dry_run 同条件对照：修后 **403/403**（对照克隆同 403；接受值源行 5,549→5,550） |
| 备份 | receipt.backup_sha256 == 备份文件 sha256 == 换前克隆 sha256（`c44a0f50…f9ca`）；恢复步骤 6 条在场；只读验证 66 张表 |
| ops 收据 | 最新行 kind=`repair-stock-daily-hithink`，ok=true，plan=`staging-swap` |
| 生产库 | 前后 sha256 + (ino, mtime_ns, size) 完全不变（未动） |

## 十一轮审查后的 P1 修补：严格门禁 v2

十一轮裁定：候选代码通过；本次对账结果有证据支持；但 v1 脚本不是
fail-closed（旧报告/旧备份污染、rc 不作硬门禁、备份按 mtime 挑），且两处
口径过强（合并范围少算本文档；「逐行精确」超出 EXCEPT 实际保证）。

修补（`reconcile/reconcile_gate.py`）：

- 每轮**唯一 run 目录**（`run-<UTC ts>/`）：报告/克隆/备份全落目录内，无旧证据残留；
- CLI **rc != 0 立即失败**（写部分报告后 exit 1）；
- 备份按 **run_id 绑定本轮 ops_sync_run 收据**（`98467e4f5a25` == `98467e4f5a25`），
  并校验 source_db 指向本轮克隆、created_at 在本轮时间窗；
- 绑定链：候选提交链（044d1661 是 HEAD 祖先）、trade_date、parquet sha256
  （子进程报告内指纹 == 本地冻结输入指纹）、克隆 sha256 == 生产换前指纹；
- 非目标日期改 **EXCEPT ALL**（含 multiplicity）；
- **任一检查失败 → exit 1**（fail-closed）。

严格复跑收据：`reconcile/run-20260913T141836Z/gate-report.json`——
**21/21 检查 PASS（我当时写成 20/20，数错，十二轮已指正），verdict=PASS，exit 0**；生产库前后 sha256/stat 仍不变。
v1 脚本与十轮报告（`reconcile_hithink.py` / `recon-report.json`）保留为历史证据。

## 十二轮审查后的修补：门禁 v3 纳入候选提交

十二轮裁定：数据对账有条件通过，但门禁实现不通过——P0 是**证据与代码脱钩**
（v2 脚本与收据都在仓外目录，合并候选不会把门禁带进仓库）；另有四处 P1
（只查祖先关系未锁精确 revision / parquet 未真冻结存在 TOCTOU 窗口 /
异常路径不写部分报告 / run 目录名秒级不保证并发唯一）与 ops 收据绑定可加
强。修补（全部落在候选提交 `affe282d` 的 `scripts/reconcile_hithink_gate.py`）：

- **脚本入仓**：门禁随候选提交走，可复现可审查；
- **精确版本绑定**：`--expect-revision` 要求 HEAD 精确相等 + `git status --porcelain`
  为空，收据记录 tree_revision / tree_clean / 脚本自哈希（sha256 `8f908f60…`）；
- **parquet 真冻结**：先复制进本轮 run 目录，对副本算 hash，CLI 只读副本；
- **顶层异常保护**：任何异常都写结构化 FAIL 报告（run 目录创建失败写仓外兑底
  FAIL 文件）；FAIL 报告只落在仓外 OUT_BASE，不污染候选树的 tree_clean；
- **mkdtemp** 原子唯一 run 目录；
- **ops 收据全绑定**：kind/ok/plan/trade_date/started_at/finished_at 时间窗全校验，
  备份 receipt run_id 必须等于该 ops 行。

v3 严格收据（已提交进候选，证据包自包含）：
`docs/handoffs/evidence/20260913-hithink-gate-report.json`（+ 子进程报告
`20260913-hithink-repair-report.json`）——**22/22 检查 PASS，verdict=PASS，exit 0**，
绑定 revision `affe282d`（即门禁脚本提交；本收据提交紧随其后，属「先跑后提
交收据」的既定次序）。原始 run 目录 `~/.finance-runtime/reconcile-gate/run-t4j_zbc0`。
负面证据：开发中两次错误调用（短 sha / 树被 FAIL 文件污染）均被门禁正确判
FAIL 且 exit 1，FAIL 报告归档在仓外 `reconcile/fail-closed-demo/`——fail-closed
语义经实测不是只写在文档里。

## 十三轮审查后的修补：异常路径契约补齐

十三轮裁定：数据对账通过、原 PASS 收据有证据支持不撤销，但「异常时可靠拒
绝并留报告」有两处未兑现（审查以真实子进程复现，非模拟）：

- **P1-1**：`git status` 失败（rc=128、stdout 为空，如索引损坏）被误读成
  「干净树」，有脏文件仍 22/22 误放行。修法：`git()` 统一检查退出码，rc!=0
  即记 `git_invocation` 结构化 FAIL（含命令/退出码/有界 stderr）并终止。
- **P1-2**：`--output-base` 指向普通文件时，报告兜底写回同一失败路径，只剩
  traceback。修法：报告先序列化，按「run 目录 → OUT_BASE → 独立仓外临时目
  录」降级写入，全失败尽力输出 stderr，绝不回退候选树 cwd。

修补提交 `b98441c5`（含 `tests/test_reconcile_hithink_gate.py` 四条故障回归）。
验证：

- 审查方复现脚本原样重跑：collision 案例 rc=1 + 结构化 JSON 无 traceback；
  损坏索引案例在树有脏文件、git rc=128 下门禁 rc=1 结构化 FAIL（不再误放行）；
- 绑定 `b98441c5` 重放：**22/22 PASS，verdict=PASS，exit 0**（`docs/handoffs/evidence/`
  下两份 JSON 已刷新为此次收据；`affe282d` 版收据留在 git 历史）；
- Python 叶子按新代码态重绑：ruff 全过；全量 **9,612 passed / 0 failed /
  77 skipped / 2 xfailed，exit 0**，干净收据 `20260913T160704Z-b98441c5.json`
  （dirty=false；+4 即新故障回归用例）。前端/E2E/registry 叶子不受 scripts/+
  tests/ 改动影响，未重跑。

## 结论与待授权

候选门禁四叶全绿 + 隔离库对账全项通过。**仍未做**：合并 main、切运行时、
生产库写入/换库、302132 历史回填（需单独授权并验证连续性）、并跑表补齐。
合并授权与生产换库授权须分别申请。
