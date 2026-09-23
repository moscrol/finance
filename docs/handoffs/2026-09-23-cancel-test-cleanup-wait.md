# 取消测试等待 worker 清理 · 2026-09-23

## 新全量失败

#883 的组合候选 `264bc9d0ddfa2711d959e1528820b50d2c1aa7c3` 在干净树完整运行：14581 passed / 1 failed / 85 skipped / 2 xfailed。唯一失败为 `test_cancel_missing_run_and_idempotence`：run 已 completed，但 `cancellation_registry` 仍有当前 `(alice, run_id)`。Ruff、前端六项和 registry 五项均成功，整体仍为 RED，不合入。

原件根 `~/.finance-runtime/reviews/claim-scope-authorized-merge-20260923/`：`gates/runner.log`、`gates/python-junit.xml`、`gates/receipts/gate-U9OMHJDV/pytest.json`，原现场 `gates/basetemp-python` 保留。它不覆盖旧 `9a0227986` 的 queued 红项，也不否定 #885 旧 head 的绿收据。

## 原因与最小修复

`RunSupervisor._execute` 调用 runner；测试 runner 写完成态后返回。Future 随后结束，再调用 `_forget` 清理信号表。旧测试 `_wait_terminal` 返回就立即断言 registry 为空，把两阶段误当成了一个同步时点。

只改 `intelligence/tests/test_workbench_api.py` 的该用例：

- 用例参数化普通路径和 worker 尾段被屏障暂停的路径；屏障只挂到本测试的 supervisor 实例，不卡住别的 app/worker。
- 暂停路径显式确认 run 已终态且当前信号仍在，再释放尾段；有界轮询当前 `(user, run_id)` 消失，然后保留原来的空表、跨用户 404 与重复 cancel 幂等断言。
- `finally` 释放屏障；不改生产代码、终态发布顺序、`shutdown(wait=False)` 或取消语义。

受控旧断言 1P/1F（`cancel-red.log` / `.xml`），错误与全量一致；修后相关场景 5P（`cancel-green.log`），两相关测试文件 145P（`modules.log`）。这些是脏开发树定向读数，不是新提交的整仓收据。

| 采用 | 否决 | 理由 |
|---|---|---|
| 等待本次实际要断言的 registry 清理完成 | 固定 sleep 或放宽断言 | 直接观察目标条件；真实泄漏仍会失败 |
| 用实例级 worker 尾段制造必现窗口 | 循环重跑等偶发窗口消失 | 测试明确覆盖 completed 先可见的合法执行顺序 |
| 修测试后再冻结候选跑完整门禁 | 用定向 145P 或旧 head 绿收据放行 | 代码已变，必须验证新 revision |

## 下一轮与合入

新候选的门禁只读 `~/.finance-runtime/reviews/claim-scope-authorized-merge-20260923/retry-02/gates/`：`runner.log`、唯一 `receipts/gate-*/pytest.json`、`frontend/frontend.json`、`registry-*.log`、`receipt-check.log`。最终计数及确切 revision 由这些原件提供，不预填结果。

用户合入授权与 #883/#885 承接方案不变，见 `2026-09-23-claim-scope-authorized-closeout.md`。`merge-883.json` 和 `pr-885-resolution.json` 仍写在上述证据根，不写到第一轮红目录里。任一叶子红或无结论都不合。#75 K3、#76 L5、运行时接入、8792 与生产部署均未动。
