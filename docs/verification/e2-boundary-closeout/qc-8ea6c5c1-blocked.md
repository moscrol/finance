# P3b 独立复核受阻（不是通过）

2026-09-14。候选 `8ea6c5c11995d8af9f3f24a3f39b3addea8406f8`，独立检出 `/tmp/e2-p3b-qc-8ea6c5c1`，开始/结束均 clean、detached HEAD。未改应用、原题、评分或 46 针。

## 调用与结果

- `codex exec -C /tmp/e2-p3b-qc-8ea6c5c1 -s workspace-write --add-dir /Users/a77/.finance-runtime/test-receipts --ephemeral --color never -o /tmp/e2-p3b-qc-8ea6c5c1-report.md - < /tmp/e2-p3b-qc-prompt.txt`
- 独立审查模型由现有配置选择：`gpt-6-astra` / `openai`，reasoning `ultra`；Codex `0.154.0-alpha.6.2`。
- 原始日志 `/tmp/e2-p3b-qc-8ea6c5c1.log`；退出码 1，无最终报告、无工具执行证据。
- WebSocket 重连后回退 HTTPS，又重连，最终 `503 Service Unavailable: Service temporarily unavailable`。
- 启动另报 hooks 配置含未知字段、code-mode-host 缺失；没有证据能把本次 503 归因于这两条警告。

## 待复核范围

对照设计 D4/A16、门页阶段边界及 `e0051804..8ea6c5c1` 全量 diff：
1. local_only 授权、全部 requirements 与输出 evidence_types 同源收窄；恢复/替换拒绝增权。
2. 四条保留 runner 的真实 IO；不能以 cost/freshness 当认证。
3. EpisodeScope 与 dispatch 共用能力/IO 上限；同名替换、派生、副本、原始 registry + 受限 context。
4. 受限构造器不夹带预取/计算加载器；跳过无关实体和未分类静态预检。
5. 临时 DuckDB/JSON/用户台账的正常、缺库、空表、过期路径；自行写反例，不以作者测试代替判断。

明确未覆盖：全部入口/非工具事实注入、压缩/恢复/子研究、local_only 原题号槽、逐题三态/材料锚点/P4–P7。`io_effect` 是可信装配声明，不是 OS 网络沙箱。

作者在干净候选上的测试另存 `full-8ea6c5c1-tests.txt`（9762 passed / 83 skipped / 2 xfailed）和 `frozen-8ea6c5c1-tests.txt`（286 passed）。这些不是独立 QC 收据。独立报告取得前不标阶段通过，未合并、推送或部署。
