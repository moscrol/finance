## 这个分支做什么

合成可审查的 harness 发布候选；保留模型任务与工具决策，不把工程绿冒充模型净收益。

## 当前状态

- 自有树 `/tmp/harness-opt/tmp/arena-harness-release-1002`，分支 `fix/harness-release-1002-takeover`。
- 当前 HEAD `d58d7dcd30e83d704f3e3fe697734c1203193515`（docs-only，clean）；代码候选 `2aea7c27ed469530bc73fb232e65830acc754647`。起点 `e25381b24`。
- `beff372c6` 修正子研究实际交付后的阅读覆盖；`1f8a8efb3` 修正快照日期身份；`2aea7c27` 只冻结 conformance 正向夹具时钟。
- 原发布树 `codex/harness-release-1002@e25381b24` 与三个原有未跟踪文档未改；无 main 合入、生产部署或业务库写入。

## 范围

`evidence_read` 仍默认关闭、须显式 capability；不强制补读、不加工具地板、不改变模型工具选择。排除 #20 档位硬政策、11/16/17/19 硬语义路由、A7/数字候选/工具差分。快照两入口复用 `trading_day_verdict`：历史/未来/休市/UNKNOWN 不取现货；dated DuckDB、source/requested/served/captured、freshness 与 latest/meta 单调保护均保留。

## 验证

- 最终 HEAD 全量：**19,752 passed / 0 failed / 0 error / 78 skipped / 2 xfailed**，collected=19,832；full-scope/revision receipt 与全仓 Ruff 通过。
- 前端六项均通过：组件 125 passed；E2E 34 passed / 2 skipped；registry 五项通过；code-map 36,963 nodes、no wiki，不宣称架构召回完整。
- 独立规格审查 `SPEC_VERDICT: PASS`、代码质量审查 `CODE_QUALITY_VERDICT: PASS`，均无 blocker。质量审查的 freshness 旁路口径、错误文案、accumulator 可选参数、时区、年度表风险列为后续非阻断项。
- 隔离 sidecar readiness 通过：只读 DB、候选 sync 生成 requested=2026-10-02、served/source=2026-09-30、provider=duckdb_latest、historical；sidecar 已停止。
- 真实 v3：4 条消息均 complete；2 个 `glm-5.3-flash`，2 个确定性路径。v2/v4 的“4 个模型但第 3 个 partial”保留为失败记录。conversation report 的 `llm.model` 不被 `check_model_admission` 识别，原样记录 no_evidence，不伪造准入。

## 下一步

最终 HEAD 的 Python receipt=`gate-NOXB0zmf/pytest.json`、frontend/registry/map 均已按 d58 绑定；可按用户授权 push 分支、开 GitHub PR。required checks 通过前不 merge；用户确认前不切 8792/生产。实验能力默认关闭。