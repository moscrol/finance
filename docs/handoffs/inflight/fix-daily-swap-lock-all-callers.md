# daily-swap 换库契约：门禁 v3 入候选提交 + 收据入证据包，待合并与生产换库授权

## 这个分支做什么

公共 staging 编排的换库契约加固（叠在 hithink 重建 601db6dd 上）。**生产库未动、未合并 main。**

## 决策与被否方案

- 七轮 P2：分类钉死首次观察；否了「再加 stat」「探针返回值下传」。一般 IO 裸抛另案不夹带。
- 十二轮：门禁随候选提交走；FAIL 报告只落仓外。

## 当前状态

分支代码 tip `ce67fe6a`（本文件提交即分支 tip）。十二轮裁定：数据有条件通过、门禁 v2 不通过（脚本/收据在仓外）→ 已修：**v3 门禁入候选提交 `affe282d`（`scripts/reconcile_hithink_gate.py`），收据 22/22 PASS 随证据包入候选**。候选 `integration/daily-swap-hithink-candidate-0913` @ **48242bd4**（merge 044d1661 = main@e40f22b8 + ce67fe6a；tip 层全是落账/证据）。等用户**分别**授权合并与生产换库。
证据：候选树 `docs/handoffs/2026-09-13-daily-swap-candidate-gate.md` + `docs/handoffs/evidence/20260913-hithink-{gate,repair}-report.json`（收据绑定 revision=affe282d、tree_clean、脚本自哈希、parquet 冻结哈希）。
合并完整性复验（三点 diff）：16 payload 文件仅 lessons_learned.md 与分支 tip 不同（冲突解决）。

## 已验证（候选代码态，干净树收据）

- 全量 9,608p / 0f（`20260913T131316Z-044d1661.json`）；ruff、前端四步、E2E 15、registry 五条全绿。
- 门禁 v3：精确 revision+干净树、parquet 先冻结再 hash 再执行、异常结构化 FAIL、mkdtemp、ops 全字段+时间窗绑定、备份 run_id 绑定、EXCEPT ALL；**22/22 PASS，exit 0**。负面证据：两次错误调用均判 FAIL 且 exit 1（仓外 `reconcile/fail-closed-demo/`）。
- 数据面：5,553 行、钉值全中、非目标日期零差异、拼接 403、302132 置缺、备份指纹链相等、生产库未动。

## 未验证 / 已知边界

- 既有库 assert→replace 末端窗口不闭合；裸字节直写（同 inode）看不见。
- codex sandbox 抖动本轮恰好绿，根因未查清——绿不等于修好。
- 一般 IO 裸抛未修（另案）；合并范围：payload 16 文件为稳定锚，tip 层以 --stat 实况为准（当前 20）。

## 下一步（各需单独授权）

1. 合并候选 → main（是否再要复审由用户定）。
2. 生产换库：`repair-stock-daily-hithink --trade-date 2026-09-11` 正式跑生产（细节见 repair-plan.md）；换后核对 ops_sync_run derived 段。
3. 302132 历史回填、并跑表补齐：单独授权，不在本次范围。

## 踩过的坑

- QC 树里跑探针脚本会 import 到 QC 树旧代码导致假红；复跑须拷进施工树。
- 收据绑定 revision+dirty 位；先跑后提交=脏树收据；共享收据目录认领先核 tree/branch。
- 全量前看别的树是否在跑；退出码别隔着管道测。
- 对账脚本是 fail-closed 门禁不是报告生成器；证据随提交走；先冻结再 hash 再执行。
