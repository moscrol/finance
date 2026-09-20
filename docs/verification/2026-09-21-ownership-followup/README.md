# 第一份组合原件：Python 门禁未通过

固定对象 `321712b68732eef3512da80a4aaedfecd2a9c950`，main 基准 `728f327160bbd2485cb635e7ef09d040d718d7b5`，独占树 `/Users/a77/fwp-wt-ownership-gates-0921`。解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。**不是整门禁通过，不可据此合入。**

| 检查 | 实际结果 |
|---|---|
| Ruff | 全仓通过 |
| pytest | 控制台 12059P / 85S / 2X，870.33秒，进程退出0 |
| Python 门禁读回 | 退出4：zero executed tests；编排叶退出1 |
| 前端 | frozen install / lint / typecheck / build 各0；110P；E2E 34P / 2S |
| registry | finance-only CI 边界五项均0，非跨仓验收 |
| 身份 | 三叶运行前后均同SHA、Git干净、基准未动 |
| 独立审查 | 未调用，未取得 |

## 失败机制

`intelligence/tests/test_pytest_collection_scope.py` 在测试中启动真实 `pytest --collect-only`。子进程继承 `FWP_TEST_RECEIPT_PATH`，提前写入零计数；真正全量结束后，独占创建保护拒绝覆盖。第一次组合的唯一收据记录时刻为 `2026-09-20T20:21:46+00:00`，全量实际于 `20:28:49Z` 左右才结束。这里保留原JSON与进程退出码，**不人工补写12059到收据，不追认门禁绿**。

后续修复 `d5d807f80` 在 pytest configure 阶段认领进程ID，继承该路径的子进程不落父收据；新顶层 shell 清除外层owner再重新认领。真实子进程回归先2F，修后相关49P。第二份组合 `e1b63b1a5b7c066b7377bbd2d005051863331001` 的收据须独立获取，不能移签本目录。

## 文件与完整性

`manifest.json` 登记30个文件（29个原件及本说明）的源路径、字节数、SHA256，记录 `gate_passed:false`。`python/receipts/gate-Sm54tmrK/pytest.json` 是失败轮权威原件；同目录 latest 仅导航。`author/` 是三个代码改动提交前的原始红绿日志，不是干净源码尖全量收据。

`run_leaf.py.txt` / `seal_evidence.py.txt` 是有限对象的编排与封存程序，不是已安装的通用调度器。`gate-pr.md` / `review-request.md` 是当时创建PR及未提交审查的输入快照，后续状态以PR追加评论和新版交接为准。没有发自动审查请求。

原始路径：`~/.finance-runtime/reviews/ownership-followup-20260921/`。控制台门禁只保留pytest末15行，不能称完整pytest stdout。日志中的原始空白和ANSI保留，不为了 diff check 修改证据。
