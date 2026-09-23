# 2026-09-23 main 四叶验收：27ca084f9ffc

## 结论

2026-09-23 16:05 CST 回读远程 main 为 `27ca084f9ffcb9d148b749944beca340e5f4fa6c`。该提交四叶齐绿，Python 收集面和读数对账可审计。后续 main 或 PR #886 的候选提交不自动继承此结论。

这是一次绑定 SHA 的验收，不是永久的 main 健康声明。旧 `5f35` / `bbd5` 快照不改写；本轮补齐新批次，不继续为文档自身 merge SHA 追开文档 PR。

## 执行与独立复核

开工时 load1=20.75 且多会话 pytest 并行。发现 #856 正在锁定的干净 detached 树执行与本轮完全相同的 main SHA，因此没有再启动重复的全量任务，也未修改、停止或清理其工作树。相同 revision 的合格收据可以跨树复核；被禁止的是共享 latest 指针误选、脏树或不同 SHA 的结果移签。

原始执行根目录：
`~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/merge-20260923T0736/`

本轮独立复核目录：
`~/.finance-runtime/reviews/gate-closeout-qc-20260923/main-27ca/`

| 门禁 | 原始结果 | 独立核验 |
| --- | --- | --- |
| Python | 14618 passed、0 failed、0 error、85 skipped、2 xfailed；ruff 通过；门禁 exit 0 | receipt revision/解释器/依赖指纹/干净状态一致，未绕依赖门；target 为执行树仓根，scope 无筛选；collected=14705；JUnit 实际 testcase 数与收据一致，0 failure/error |
| frontend | install、lint、typecheck、test、build 全部 exit 0，Vitest 120 passed | 起止 SHA 精确相等，dirty=false、complete=true、identity_stable=true；runner 与六份日志 SHA256、字节数一致 |
| E2E | 正式 frontend runner 第六步：34 passed / 2 skipped，exit 0 | 与前五步同一收据、同一干净 SHA |
| registry | reviewer 自己的精确 main 检出重跑五项，全部 exit 0 | 起止 git status 为空，revision 为 27ca；反向台账 98 条既有 warning，正向与重号检查通过 |

原始全量收据：`python/gate-B7yRdKb4/pytest.json`；原始 frontend 收据：`frontend/frontend.json`（均在原始执行根）。本轮复核保存原字节副本于 `python-source/`、`frontend-source/`，不改其执行树与 revision。`python-independent-audit.json`、`frontend-independent-audit.json` 记录来源、哈希和核验结果，不伪装为新执行收据。

原始 Python 于 16:03:50 CST 完成，耗时 1498.65 秒；其后 runner 校验通过并自动删除本轮显式 basetemp，`python.exit=0`。这段时间有其他任务争用，不能从耗时推导低负载性能或稳定性趋势；本次完整执行为零失败，不存在需要归因或剔除的红项。

## 防假绿对照

- 在 reviewer 精确 SHA 树执行 `check_test_receipt.py <明确原始收据> --expect-revision 27ca084f9ffcb9d148b749944beca340e5f4fa6c --require-full-scope --base-drift-max 5`，exit 0；基座漂移 0。
- 同一张全量收据把期望改为 `bbd53487f4ce`，exit 1，原因明确为 revision 与期望不符。日志 `receipt-check.log`、`wrong-revision-control.log`。
- 指针隔离和归档守卫 11 passed；收据 `targeted/receipts/20260923T075636Z-27ca084f-8fcc02ac900c.json`，只作定向证据。
- 临时归档探针 `scripts/archive/test_zz_gate_closeout_probe.py` 被守卫点名拒绝（exit 1）；删除后恢复 exit 0，树回到干净状态。日志 `targeted/archive-positive.log`、`archive-restored.log`。

## 后续边界

#59 的这个 main 批次可以收口。#886 文档分支已前向整合 27ca，但其候选 head 的四叶须单独验；最终候选结果、解除 WIP 或合入身份只认 PR 页对应 SHA 的记录，不从本页猜测。#851 的原授权与合入缺口留痕不重写，只补新的 main 基线评论。

主检出的他人改动未动，未部署生产、未换库。后续按 SHA 复用完整证据，不按目录名、PR 标题或共享 latest 指针归属；同一批次避免重复全量任务，资源不足时不另起一份竞争。
