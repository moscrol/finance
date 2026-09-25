# #813 Quality continuation batches 04-06

状态 **SPEC_SCOPED_DELIVERED_QUALITY_FINAL_REJECTED**。固定候选 `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59` / base `4cc15e703f81bce8abadee00f68caacdb0c72b4d`，观察到 main `d21707ca6`；本归档不构成合入或生产批准。

- 04：网关4、探索7；首执行阶段10次请求，首 bash 控件通过，但 pytest 自动选择审查根目录并被沙箱拒绝，未交付。宿主同沙箱补 `--rootdir=quality/work` 后诊断为10 passed；该诊断不是独立模型证据。
- 05：网关4、探索8；探索未在配额内交付，未进入执行。
- 06：网关4、探索5、执行9、报告1。首 bash exit 1 且含 `intentional probe_bug`；给定来源探针10例由模型真实执行并10P。报告交付被硬门禁拒绝：缺 `verdict`、C1-C7 的 `id/status/evidence`、标准计数对象和 `positive_control.status/classification/evidence`。
- 全部批次52次请求均结束；无自动重试。C3生产形64/39/161、C1/C4-C7及当前main组合仍未验证。

原始脚本、请求、响应、命令、XML和报告包逐项保存并按 manifest 原字节校验；排除候选工作树、凭据/auth、临时DB、用户目录、缓存和软链。
