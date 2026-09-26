本文件区分审查量具校准与候选行为；所有运行都固定同一候选 e0f2a5c7。

1. 初版 `run_pytest.initial.py` 未创建 `--basetemp` 的父目录，8 个历史测试在 fixture setup 阶段得到 FileNotFoundError；未进入历史候选实现。同批真实 code-map 原失败探针通过。修复父目录后，同 9 项得到 9 passed。
2. 初版及仅补父目录版通过预先 import conftest 设置 `_RECEIPT_DIR`；pytest 后来重新加载了仓库插件，覆盖了该模块设置。因此仓库测试钩子意外写入：

   - `/Users/a77/.finance-runtime/test-receipts/20260920T051450Z-e0f2a5c7.json`（UTC 05:14:50，1 passed / 8 setup errors），并更新当时的全局 `latest.json`。
   - `/Users/a77/.finance-runtime/test-receipts/20260920T051806Z-e0f2a5c7.json`（UTC 05:18:06，9 passed），并更新当时的全局 `latest.json`。

   已立即告知 root；原收据未删除，后来的 `latest.json` 未回滚或覆盖。精确副本及 SHA-256 在 `receipt-location-incident.json` 与 `receipts/collected-original-locations/`。最终 runner 在 `pytest_configure` 找到实际已加载的仓库 conftest 插件，只改收据目的目录，不绕过依赖门禁。后续 3 项测试收据确实写入本目录 `receipts/candidate-and-window/20260920T051958Z-e0f2a5c7.json`。
3. 独立探针初版假设 2026-02-01 超出授权，但现有真实任务合同是 2026-01-01 至 2026-09-15。对照源码 `tests/test_history_live_seams.py::FIRST` 后，改为实际 `requested_end + 1 day`；正常同根链已执行通过，错误属于负例输入选择。原脚本/结果保留为 `probe_review.initial.py` 与 `independent-results.initial.json`。
4. 新增“合法不同根”负例时，单独查询 frame 首版只将 `analysis_window_source` 改为 none，却保留 `allow_window_extension=True`，被 HistoryIntent 构造不变量拒绝。校准为无祖先且无扩窗授权后再创建独立排名原件。原脚本/结果保留为 `probe_review.root-intent-invalid.py` 与 `independent-results.root-intent-invalid.json`。

最终 `independent-probes-calibrated.receipt.json`：四组 PASS、退出 0、首尾身份一致。`existing-boundaries-fixed-harness` 的 9 项和 `candidate-and-window` 的 3 项互不重叠，故有效既有测试分母为 12；不把前次同一结构测试再次通过累计进去。4 组自建行为探针单列，不包装成仓库 pytest 项数。

未复制或覆写作者历史反例脚本。独立探针复用了仓库的合成事实夹具与消息交付 setup helper，自己的断言、正常/拒绝对照、并发调度都在本目录保留；运行真实 Registry、HistorySession 与 RunStore，未用真实模型、金融网络或生产库。
