# daily-swap 换库契约：候选代码审查通过 + 严格门禁收据在手，待合并与生产换库授权

## 这个分支做什么

公共 staging 编排的换库契约加固（叠在 hithink 重建 601db6dd 上）。**生产库未动、未合并 main。**

## 决策与被否方案

- 七轮 P2：existing/absent 分类钉死本轮首次观察；否了「发布前再加 stat」「探针返回值下传」。
- 一般 clone IO 裸抛另案，不夹带；收据只对被测快照成立，不外推。

## 当前状态

分支 tip `c11c1e25`。**十一轮裁定：候选代码通过、本次隔离对账结果有证据支持；P1（对账脚本非 fail-closed）已修成严格门禁 v2 并复跑 PASS。** 候选 `integration/daily-swap-hithink-candidate-0913` @ e12307f1（merge 044d1661 = main@e40f22b8 + ce67fe6a；tip 另含两份落账文档）。等用户**分别**授权合并与生产换库。
证据：候选树 `docs/handoffs/2026-09-13-daily-swap-candidate-gate.md`；严格收据 `~/.finance-runtime/gate-checkouts/daily-swap-candidate-20260913/reconcile/run-20260913T141836Z/gate-report.json`（20/20 PASS，exit 0）。
威胁模型在 db.py 顶部；背景 `docs/handoffs/2026-09-13-daily-swap-round7-fixes.md`。

## 已验证（候选 044d1661 代码态，干净树收据）

- 全量 9,608p / 0f / 77s / 2x（`20260913T131316Z-044d1661.json`）；ruff、前端四步、E2E 15、registry 五条全绿。
- 严格门禁 v2：fail-closed、唯一 run 目录、备份 run_id 绑定 ops 收据、parquet/克隆/提交链全绑定、EXCEPT ALL（含 multiplicity）；20/20 PASS。数据面：5,553 行、钉值全中、非目标日期零差异、拼接 403、302132 置缺、备份指纹链相等、生产库未动。

## 未验证 / 已知边界

- 既有库 assert→replace 末端窗口不闭合；裸字节直写（同 inode）看不见；分类钉死只覆盖首次观察之后的消失。
- codex sandbox 抖动本轮恰好绿，根因未查清——绿不等于修好。
- 一般 IO 裸抛未修（另案）；合并范围口径：merge payload 16 文件 / tip vs main 17 文件（含落账文档）。

## 下一步（各需单独授权）

1. 合并候选 → main（审查已放行代码；是否再要独立复审由用户定）。
2. 生产换库：`repair-stock-daily-hithink --trade-date 2026-09-11` 正式跑生产（细节见 repair-plan.md）；换后核对 ops_sync_run derived 段。
3. 302132 历史回填、并跑表补齐：单独授权，不在本次范围。

## 踩过的坑

- QC 树里直接跑探针脚本会 import 到 QC 树旧代码导致假红；复跑须拷进施工树。
- 收据绑定 revision+dirty 位；先跑后提交=脏树收据；共享收据目录认领先核 tree/branch。
- 全量前看有没有别的树在跑。
- 对账脚本必须是 fail-closed 门禁（rc 硬门禁 + run_id 绑定 + 唯一 run 目录），不是报告生成器（十一轮 P1）。
