# daily-swap 换库契约：已合并 main（1fef3d27），待生产换库单独授权

## 这个分支做什么

公共 staging 编排的换库契约加固（叠在 hithink 重建 601db6dd 上）。**已合并 main；生产库未动。**

## 当前状态

**已合并**：用户授权后 fast-forward 至 gitea/main = `1fef3d27`（组合版、四叶全绿+门禁 22/22 的那个提交本体，零新内容；两条分支保留）。候选树与门禁/证据随合并进入 main。
剩最后一步：**生产换库**（`repair-stock-daily-hithink --trade-date 2026-09-11` 正式跑生产，细节见 `~/.finance-runtime/db-repair/hithink-20260911/repair-plan.md`）——需用户单独授权；换后核对 ops_sync_run derived 段与 backup receipt。
302132 历史回填、并跑表补齐：单独授权，不在本次范围。

## 已验证（组合版 e9a824bf，干净树收据；main tip 1fef3d27 相对它仅落账/证据 3 文件，代码同一）

- 全量 9,617p / 0f（`20260913T171047Z-e9a824bf.json`，dirty=false）；ruff 全过；前端五步、E2E 15、registry 规范四命令+crosswalk 全绿。
- 门禁 v3：精确 revision+干净树、parquet 冻结副本、异常结构化 FAIL、git rc 检查、报告三级降级、ops 全字段+时间窗、备份 run_id 绑定、EXCEPT ALL；**22/22 PASS，exit 0**（绑定 e9a824bf）。负面证据：审查复现脚本两案例（collision/损坏索引）均 rc=1 结构化 FAIL（仓外 `reconcile/round13-repro/`）。
- 数据面：5,553 行、钉值全中、非目标日期零差异、拼接 403、302132 置缺、备份指纹链相等、生产库未动。

## 未验证 / 已知边界

- 既有库 assert→replace 末端窗口不闭合；裸字节直写（同 inode）看不见。
- codex sandbox 抖动本轮恰好绿，根因未查清——绿不等于修好。
- 一般 IO 裸抛未修（另案）；合并范围：payload 16 文件为稳定锚，tip 层以 --stat 实况为准。

## 下一步（各需单独授权）

1. ~~合并~~（已完成，gitea/main=1fef3d27）。
2. 生产换库：授权后跑 `repair-stock-daily-hithink --trade-date 2026-09-11`；换后核 ops_sync_run derived 段。
3. 302132 历史回填、并跑表补齐：单独授权，不在本次范围。

## 踩过的坑

- QC 树里跑探针脚本会 import 到旧代码假红；收据绑定 revision+dirty 位；共享收据目录认领先核 tree/branch；退出码别隔着管道测；registry 的 --check 是顶层旗标（scan --check 是 argparse 错，不算校验）。
- 对账脚本是 fail-closed 门禁不是报告生成器；证据随提交走；先冻结再 hash 再执行；git 空 stdout ≠ 干净树。
