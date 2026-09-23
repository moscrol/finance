# 2026-09-23 main tip gate: `5f35da1`

## 背景

PR #881、#882 是文档收口，先后把 #58/#59 的历史收据与 current tip 分开。本批次冻结的 SHA 是 `5f35da1723f74663a4803c4d1490c402a1d6db40`，不是永久的最新 main；`72be6005`、`760248ec`、`4315d9` 均不能替代它的全量门禁证据。测试结束后 #876 已将 main 推进到 `bbd53487f4ce`，后续见 `2026-09-23-main-tip-gate-bbd5.md`。

## 本轮验证

在干净独占树 `finance-workspace-private-5f35` 上：

- frontend 正式 runner 六步 exit 0：`pnpm install --frozen-lockfile`、lint、typecheck、Vitest `120 passed`、build、E2E `34 passed / 2 skipped`。收据：`~/.finance-runtime/reviews/gate-closeout-qc-20260923/main-5f35/frontend-gate/frontend.json`，`complete=true`、`identity_stable=true`、`dirty=false`。
- registry 五项 exit 0：`main-5f35/registry/summary.txt`；反向台账 98 条 warning 是既有口径。
- targeted 守卫 `11 passed`，收据绑定 `5f35da17`；它只证明收据指针隔离和归档守卫，不是 full gate。

## 未完成与原因

Python full gate 未启动。20 分钟资源准入窗口内始终有 3 条其他 full pytest；最后观测 load1=`15.00`，所以没有并跑污染结果。记录：`main-5f35/python-admission.txt`。不读取其他树的 `pytest.json`，不把历史收据移签。

## 下一步

本批次保留为历史证据，不继续为旧 SHA 补跑以冒充新 main。`finance-workspace-private-5f35` 后来转为文档分支并前向到 `bbd53487f4ce`，目录名不是当前 revision。下一批次必须在独占干净树核对 HEAD 后运行正式门禁；全部完成前，#59 不标记四叶完成。
