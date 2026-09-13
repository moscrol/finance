# daily-swap 换库契约：已合并 main（1fef3d27）+ 生产修复换库完成并验收

## 这个分支做什么

公共 staging 编排的换库契约加固（叠在 hithink 重建 601db6dd 上）。**已合并 main；2026-09-11 生产修复已换库并验收。**

## 当前状态

**全部落地**：gitea/main = `1fef3d27`（fast-forward，零新内容）；生产修复于 2026-09-14 02:19 从干净候选检出（1fef3d27）经正式父进程入口完成——staging 全锁链、clonefile 克隆、子进程写 staging、换前备份、原子换名（run_id=`1ef953440995`，exit 0）。
**生产验收**（只读核对，对照=换前备份）：5,553 行（hithink 5,547 + eastmoney 6）；302132 钉值全中（63.42/64.35/−1.45/5.9863 亿/94,471 手）；600176 amount=113.6006；非目标日期三表 + fact_market_daily 全表 EXCEPT ALL 双向全 0；302132 两派生表 0 行（置缺声明在报告）；technical 5,529 / window 22,115；拼接 403/403（值源行 5,550）；ops 收据与备份 receipt run_id 同轮绑定、备份 sha256=换前指纹 c44a0f50。
证据：`~/.finance-runtime/db-repair/hithink-20260911/prod-repair-report-20260914.json`；备份 `db/market_feature_store.duckdb.bak-20260914T021947-1ef953440995`（+ .receipt.json，恢复步骤在内；确认无恙后可删，3.6G 量级）。
剩：302132 历史回填、并跑表补齐——单独授权，未启动。

## 已验证（组合版 e9a824bf；main tip 1fef3d27 相对它仅落账/证据 3 文件，代码同一）

- 全量 9,617p / 0f（`20260913T171047Z-e9a824bf.json`，dirty=false）；ruff、前端五步、E2E 15、registry 规范四命令+crosswalk 全绿；门禁 22/22 PASS 绑 e9a824bf。细节见 main 上 `docs/handoffs/2026-09-13-daily-swap-candidate-gate.md`。

## 未验证 / 已知边界

- 既有库 assert→replace 末端窗口不闭合；裸字节直写（同 inode）看不见。
- codex sandbox 抖动本轮恰好绿，根因未查清——绿不等于修好。
- 一般 IO 裸抛未修（另案）；合并范围：payload 16 文件为稳定锚，tip 层以 --stat 实况为准。

## 下一步（各需单独授权）

1. ~~合并~~（完成，gitea/main=1fef3d27）。~~生产换库~~（完成并验收，run_id=1ef953440995）。
2. 302132 历史回填：先审计缺口/定日期与数据源，副本验证后再落生产。
3. 并跑表补齐：按端点分别限定日期，结束日 ≤ 2026-09-11；快照不能冒充历史回填。

## 踩过的坑

- QC 树里跑探针脚本会 import 到旧代码假红；收据绑定 revision+dirty 位；共享收据目录认领先核 tree/branch；退出码别隔着管道测；registry 的 --check 是顶层旗标（scan --check 是 argparse 错，不算校验）。
- 对账脚本是 fail-closed 门禁不是报告生成器；证据随提交走；先冻结再 hash 再执行；git 空 stdout ≠ 干净树。
