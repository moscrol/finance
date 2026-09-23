# #86/#87 验证收口（隔离候选分支）

## 范围与结论

本目录记录隔离分支 `fix/workorders-86-87-0923` 的工程验证。候选基线是 `gitea/main@626d8a508`；本轮曾在业务代码 head `6f14ed215184d5c97fae3c03513468c6c9ee9cd4` 上完成 K3 和合并树检查，之后只追加本验证文档、QUEUE/INDEX 与交接，不改业务代码。K3 因此只对它的精确审查 head 成立，不能伪称审查了后续 docs head。最终 revision 以分支 `git rev-parse HEAD` 为准。没有合并、push、部署、重启、切 8792、真实 IMA 抓取或生产写入。

#87 的独立 K3 finance 会话绑定代码 head `6f14ed215184d5c97fae3c03513468c6c9ee9cd4`，在 1080 秒截止时为 `INCOMPLETE`：28 次已准入请求、模型错误 0、候选树首尾 revision/tree/status 一致，但未写出 `REPORT.md` 或 `verdict.json`。按工单纪律记为 `BLOCKED`，不是 PASS，也不是 `REVIEW_EVIDENCE_DISPUTED_NO_APPROVAL` 的批准替代。原始收据在树外：`/Users/a77/.finance-runtime/reviews/briefing-k3-r2-20260923/finance-review/execution.json`。

#86 有单独的 K3 审查，精确绑定同一业务代码 head，11 次请求、无模型错误、候选树未变，正式 `REPORT.md`/`verdict.json` 为限定离线 `PASS`。报告记录部署脚本的 P3 非原子 rsync 风险为基线已有问题，不构成本工单阻塞；原始证据在 `/Users/a77/.finance-runtime/reviews/deploy-help-k3-r2-20260923/finance-review/`。

## 作者测试与静态检查

- #86 部署测试：24 passed；#87 IMA + 晨汇验收测试：14 passed。最终可采信收据存于 `/Users/a77/.finance-runtime/test-receipts/`，报告时必须用 `scripts/check_test_receipt.py --expect-revision "$(git rev-parse HEAD)"` 重新绑定具体文件。
- 对 Python 文件的 ruff：通过；`zsh -n scripts/deploy_workbench_runtime.sh`：通过；`git diff --check`：通过。
- 正式 `scripts/run_main_gate.sh` 的全量 Python 叶在 1200 秒截止，没有收据，不计为通过；并行机器负载存在，但不把它归因成测试缺陷。

## 独立合成探针

探针使用真实 `verify_briefing_consumption.py`、生产 schema、`teaching_objects` 和 `slice_river`，只用临时 DuckDB：

- 阳性：`exit 0 / PASS`，sidecar 关闭前后 river 不变，结果 grade 为 `trade_date_only`；strict 只过滤晚写 teaching object。
- 一个 `computed_at` 早于 source `recorded_at`：`exit 1 / FAIL`，逐行标签错误未被对象的较晚聚合时间掩盖。
- 来源为 `NULL` 却写标签零：`exit 1 / FAIL`；`NULL` 与零不等价。
- 行情日历不足：`exit 2 / BLOCKED`，labels DB SHA-256 不变。

可重放文件与日志在树外：`/Users/a77/.finance-runtime/reviews/briefing-k3-r2-20260923/finance-review/synthetic_probe.py`、`synthetic_probe.log`。其中合成日期是专门构造的 fixture，不是生产交易日或 live 结论。

## #86 安装副本调查

在授权的只读范围内检查了 `~/.local/bin/` 和 `~/Library/LaunchAgents/`：没有发现 `deploy_workbench_runtime.sh` 的安装副本或软链。`com.a77.finance-workbench.plist` 指向的是启动器 `/Users/a77/.local/bin/start-finance-workbench`，该启动器通过 `/Users/a77/finance-workspace-runtime` 加载 8792，不是部署脚本副本；没有替换命令需要执行。仓内部署脚本也只更新 standalone runtime 的 `intelligence/`，不会自动更新启动器或 LaunchAgent。

## 边界与下一步

live 晨汇消费仍依赖 #61 把 `fact_market_daily` 补到目标日；本轮没有造行情行，也没有授权重跑 live。ordinary river 只证明 `trade_date_only`，strict 只证明教学对象日期过滤，不能证明全部行情事实冻结或全文晨汇 RAG。

#157/#847 的合入顺序、半合行为见 `docs/handoffs/2026-09-23-briefing-consumption-coupling.md`。保持候选 WIP，等待用户明确合入确认；合入前需在新 main tip 重新绑定四叶门禁和 live 前置状态。
