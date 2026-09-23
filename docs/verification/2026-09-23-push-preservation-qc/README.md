# #63 质检整改证据（2026-09-23）

## 范围

用户授权“你来推进”后，修复方法/失败退出语义、压缩交接、统一历史计数、保全两条真正未远端留存的分叉内容。**不是 market-cutoff 产品验收，也不是本仓全量门禁。**

- 工具代码：`fdaf35251235958b34314a0df74344b0f571e4fa`，分支 `fix/push-preservation-qc-0923`，基线 `8e79893729da43c6e66f707ee28cbca99abb0c74`。
- cutoff 交接：`4a6e18da6f1469da2df9f79438d26ce8d2759e5f`，只改其 inflight 一文件；已推、2601字节、归档181/181、正式tree等于预览。
- harness编目：`7effba042aae14fe7597b422c37d2cc76d24a4db`，`docs/evidence-preview-qc-0923`，已推未合。
- 共享记忆：补充已有知识笔记、项目任务行/一行索引；自动同步提交 `9c5aae5413e95fbd7619f6650f44e966666255cd`，回读Gitea main一致。

## 可采信读数

规定解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`：

- 干净 `fdaf35251` 定向 **44 passed / 0 failed / 0 error**；JUnit与精确收据对平，`check_test_receipt.py --expect-revision` exit0。此前脏树44P另存，不移签。
- 五处撤保护变异均断言失败而非导入/收集错误；`mutations.json.source_sha256` 与已提交工具字节相同。
- 新工具真实用于cutoff交接：prepare和verify都181/181；实际commit的退出码单独核对。
- 两个保全头分别等于原本地固定tip；原同名远端不变，见 `closeout-check.json`。
- vault lint前后均33 errors/17 warnings；比较具名ERROR集合无新增，不称全绿。harness check_refs exit0，但存量行数漂移/两仓缺席仍在输出中，不能称完整跨仓引用验收。
- 本证据包另用 `check_evidence_archive.py` 对提交字节核验；该完整性结论不改变上述边界。

## 文件索引

- `sources.json`：36份原件的来源绝对路径、长度与SHA256；`raw/` 为逐字节副本。
- `raw/closeout-check.json`：01:06:24 +08:00 实测汇总，不是当前远端原子快照。
- `raw/tool-targeted*`、`raw/tool-receipt-checked.txt`：干净/脏树测试分账与收据复核。
- `raw/mutation-*`、`raw/mutations.json`：五处撤保护的具名断言失败。
- `raw/run_preview_mutations.py.txt`：本轮诊断原件，改用新输出目录后才重跑；常规回归在仓内tests，不能直接重跑此原件覆盖旧收据。
- `raw/cutoff-*`：真实预览、提交、正式复核、推送、远端回读。
- `raw/preservation-plan.json`、`raw/preserve-*`、`raw/remote-after-preservation.txt`：新命名保全前后证据。
- `raw/method-after.md`、`raw/legacy-finish-*`：方法更正与旧/tmp脚本退役。旧脚本不再操作仓库，直接exit2；审计目录中的原件不改。
- `raw/harness-*`、`raw/memory-lint-*`：跨仓归位与存量问题分账。

原只读质检保持原样：`~/.finance-runtime/reviews/push-s1-63-qc-20260923T001455/report.md`。
本轮完整外置证据：`~/.finance-runtime/reviews/push-s1-63-followup-20260923/`。
决定与下一步：`docs/handoffs/2026-09-23-push-preservation-qc.md`。
