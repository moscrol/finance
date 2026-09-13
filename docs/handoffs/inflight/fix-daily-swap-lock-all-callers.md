# daily-swap 换库契约：候选门禁+对账通过，待合并与生产换库授权

## 这个分支做什么

公共 staging 编排的换库契约加固（叠在 hithink 重建 601db6dd 上）。**生产库未动、未合并 main。**

## 决策与被否方案

- 七轮 P2：existing/absent 分类钉死本轮首次观察；否了「发布前再加 stat」「探针返回值下传」。已见旧库后消失只剩 rc=2（探针窗口内→SwapTargetReplacedError；之后→换库锁开锁失败）。
- 一般 clone IO 裸抛：审查裁定另开小提交，不夹带；错误出口旧债不是数据覆盖。
- 删掉「零漂移→门禁可外推」断言：收据只对被测快照成立。

## 当前状态

分支 tip `ce67fe6a`。**整合候选 `integration/daily-swap-candidate-0913` @ b99f1de3（merge 044d1661 = main@e40f22b8 + ce67fe6a，16 文件 / 3,941+ / 51-）：四叶门禁全绿 + hithink 隔离库对账全项通过，生产库未动。** 等用户**分别**授权合并与生产换库。
候选证据：候选树 `docs/handoffs/2026-09-13-daily-swap-candidate-gate.md`；对账脚本与 JSON 在候选树上一级 `reconcile/`。
审查分支：`docs/qc-daily-swap-{87be884b,ac7e3087,c20abf7d,dfb6ce87,7c89ca81}`（十~六轮，不在本树）。
背景 `docs/handoffs/2026-09-13-daily-swap-round7-fixes.md`；威胁模型在 db.py 顶部。

## 已验证（候选 044d1661，干净树收据 dirty=false）

- 全量 9,608p / 0f / 77s / 2x（收据 `20260913T131316Z-044d1661.json`）；ruff 全过；前端四步全绿；E2E 15 passed；registry-check 五条全绿。
- 隔离库对账：当日 5,553 行（5,547+6）、逐值钉值全中、非目标日期 EXCEPT 双向全 0、拼接 403/403、302132 两派生表 0 行置缺、备份指纹链相等+恢复步骤在场、生产库前后 sha256/stat 不变。

## 未验证 / 已知边界

- 既有库 assert→replace 末端窗口不闭合（无 POSIX 原语）；裸字节直写（同 inode）看不见。
- 分类钉死只覆盖本轮首次观察之后的消失。
- codex sandbox 抖动测试本轮恰好绿，根因未查清——绿不等于修好，不是豁免。
- 一般 IO 裸抛未修（另开提交）；候选尚未接受独立复审。

## 下一步（各需单独授权）

1. 候选独立复审（可选，用户定）→ 授权合并 b99f1de3 → main。
2. 授权生产换库：`repair-stock-daily-hithink --trade-date 2026-09-11` 正式跑生产（命令细节见 `~/.finance-runtime/db-repair/hithink-20260911/repair-plan.md`）；换后核对 ops_sync_run 收据 derived 段。
3. 302132 历史回填、并跑表补齐：均单独授权，不在本次范围。

## 踩过的坑

- QC 树里直接跑探针脚本会 import 到 QC 树旧代码（conftest prepend sys.path）导致假红；复跑须拷进施工树。
- 收据 JSON 绑定 revision+dirty 位：先跑后提交得到的是脏树收据；引用前先核这两字段；共享收据目录会被别树污染，认领先核 tree/branch 字段。
- 全量前看有没有别的树在跑。
