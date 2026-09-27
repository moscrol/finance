# RE06 接手收尾（L6，09-27）

## 当前状态
工单 #73：E2 local_only 原题号交付、同意折叠共用、TOCTOU 锁内复核、计时独立 scope（B）。已前向 main `339676bfe`（合并 `114247663` 重建 bundle 为 `index-BA_Tz2HK.js`；`ed0aa08d1` 无冲突）。代码头 `1e6fca1dc`，之后只有本交接。WIP PR 待合。未部署，8792 仍是旧计时控件：停计时会撤回自用测量。

## 下一步
1. 协调者在合并预览上跑四叶（Python 全量、前端含 build/e2e、registry），通过后去掉 WIP 合入。
2. 部署 8792 需用户另行授权，走链切五步（`docs/workflows/acceptance-workflow.md` §3–§4）。RE06 没有 launchd 或定时组件，「装计时器」指的就是部署这个版本。计时控件默认关闭，台账不迁移。回滚：链回上一快照；用过 v2 计时的 owner，回滚后自用测量会被旧门关掉（旧 T08 规则）。
3. #76 P7 自然金融验收（真实模型，需要额度授权）。

## 已验证
- 定向 33 文件 1215P（`1e6fca1dc`，收据 `~/.finance-runtime/test-receipts/20260926T234554Z-1e6fca1d-7f2a5e270519.json`）；vitest 9P；ruff 通过。
- bundle 确定性：同一工具链能从各自源码逐字节重建 main 与本线旧 bundle。
- 范围化复核 PASS_WITH_LIMITS：C1–C10 共 34 个撤保护探针全红，失败身份逐个核过。原先存活的 7 个是测试缺口（C3×2、C4×3、C9、C10），已补 7 条测试（`c2e82bdcd`、`1e6fca1dc`）。证据在 `~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L6/review.md`。

## 未验证
- 真实模型交付、跨进程并发、浏览器 e2e、生产台账里旧 v1 记录的重算影响。
- K3 独审（QC09）停用，未续跑。Pi 旧证据根 `~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked/` 只签旧候选 a30e。
- 分支带约 7.3 MB 的 QC 过程证据（`docs/handoffs/evidence/2026-09-2x-re06-*`），是否随合入待协调者定。
