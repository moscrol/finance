# #83 / PR #813 Quality batches 07-10

状态 **SPEC_SCOPED_DELIVERED_QUALITY_PASS_WITH_LIMITS_C3_NOT_VERIFIED**。固定候选 `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59` / base `4cc15e703f81bce8abadee00f68caacdb0c72b4d`；本归档不构成合入或生产批准。

- 07：gateway 4、explore 8；模型读取 `_data_checks` 后耗尽 explore 配额，未形成交付。原始请求、响应和 controller stop 已保留。
- 08：gateway 4、explore 7、execute 10；首 bash 合同被执行，但 supplied test 入口缺少同目录 fixture 依赖，collection error，未交付。
- 09：gateway 4、explore 5、execute 12；首 bash 合同通过，但 supplied probes 仍引用旧 `/06` candidate 路径，沙箱拒绝读取，collection error，未交付。
- 10：gateway 4、explore 3、execute 7、report 1。宿主路径检查、离线预检和硬门测试通过；首 bash exit 1 且含 `intentional probe_bug`；两组 supplied probe 共 10/10 passed，author tests 0；唯一 report 通过最终 schema gate，verdict `PASS_WITH_LIMITS`。

独立 Quality 结论只覆盖 C3 局部行为：外部 acceptance entry 的 10 个 synthetic supplied cases 均通过，C3 生产形 64/39/161 仍未直接观察，因此 C3 claim 为 `not_verified`。C1/C2/C4-C7 不在本批次范围；当前 main 组合未验收。

原始源码、请求、响应、命令、XML、报告包、失败收据和 host audit 逐项保存，并按 manifest 做原字节校验；排除候选工作树、凭据/auth、临时 DB、用户目录、缓存和软链。
