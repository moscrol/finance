# Harness 接手最终验证记录（2026-10-02）

此文记录工程候选的实际身份、门禁与真实验收边界；不授权 main 合入、生产切换或实验能力启用。

## 当前身份与保全

- 树：`/tmp/harness-opt/tmp/arena-harness-release-1002`
- 分支：`fix/harness-release-1002-takeover`
- 最终候选：`2aea7c27ed469530bc73fb232e65830acc754647`
- 起点：`e25381b24c2c9cbb11193b4b85711e4e9a3d489a`
- 代码修复：`beff372c6f56caf9de35b10d0f01cd513f6223e0`、`1f8a8efb3f5ae11610cbbbb35bea56a679618b34`
- 原发布树仍为 `codex/harness-release-1002@e25381b24`，三个原有未跟踪文档保留；无 push、main 合入、部署、预测台账或业务 DB 写入。

## 工程门禁

最终候选外置产物根：`/tmp/arena-harness-validation-1002/final-candidate-v2/`。

- Python 全量：**19,731 passed / 0 failed / 0 error / 99 skipped / 2 xfailed**，collected=19,832。
- 专用 receipt：`final-candidate-v2/python/receipts/gate-UMh7CWFh/pytest.json`；`check_test_receipt.py --require-full-scope --expect-revision 2aea7c27...` 通过，锁依赖、解释器、clean、scope 对账均通过。
- Ruff：全仓通过。
- Frontend receipt：`final-candidate-v2/frontend-serial-recheck/receipt/frontend.json`；install、lint、typecheck、component test、build、E2E 六项退出 0，SHA clean/稳定；组件 125 passed，E2E 34 passed / 2 skipped。
- Registry：`final-candidate-v2/jobs/registry/status.json`，五项检查通过。
- Code map：`final-candidate-v2/jobs/map/status.json`，36,963 nodes，`built_at_sha=2aea7c27...`，`wiki_generated=false`；vault/narrative 缺层，不宣称架构召回完整。
- 早先同 SHA 的一次移动端 E2E timeout 原件和 trace 保留；没有扩大 timeout、改断言或拿旧结果覆盖新结果，之后完整串行复验通过。

## 独立审查

- 规格审查输出：`release-readiness-2aea/claude-spec-final-result.json`，首行 `SPEC_VERDICT: PASS`，无确认 blocker。
- 代码质量审查输出：`release-readiness-2aea/quality-review-result.json`，首行 `CODE_QUALITY_VERDICT: PASS`，无 blocker。
- 质量审查的非阻断项：existing_complete attempt freshness 可能与受保护文件不一致；休市/未来/UNKNOWN 共用一段可诊断性文案；`_claim_inbox(accumulator=None)` 的未来调用点静默风险；北京时区与本地 date.today 的边界；2026 休市表年度维护；conversation report 未被 `check_model_admission` 识别为 served_model 产物。未在本轮扩大范围修复。
- Codex 独立审查曾因使用额度耗尽无输出；不计为 PASS。Claude 静态审查工具关闭，未把测试收据冒充独立代码阅读。

## 日期一致的 sidecar 真实验收

生产原始快照 readiness 曾因 `2026-10-02` 与业务 DB `2026-09-30` 不一致而 not_ready。没有改生产；在 sidecar 专用目录调用本候选 `sync_market_snapshot`，不配置 AkShare runner、只读业务 DB，生成：

- requested=`2026-10-02`
- calendar=`CLOSED`（交易所公告休市表）
- served/source=`2026-09-30`
- provider=`duckdb_latest`
- freshness=`historical`
- contract `PASS`，sidecar readiness `ready`

sidecar 代码 health 为当前 SHA、clean、`code_matches_repo=true`，用户根为专用 `/tmp/.../real-sidecar/users`；验收后已停止。

## 真实多轮验收边界

验收根：`release-readiness-2aea/real-sidecar/users/`。

- v1：4 条 complete，但第 1 个 run `llm.used=false`，不作为模型准入证据。
- v2：4 条实际模型 `zhipu/glm-5.3-flash`，但第 3 个 run `partial`；保留为失败记录，不放行。
- v3：4 条消息均 `complete`；第 2、3 个 report 的 `llm.used=true, provider=zhipu, model=glm-5.3-flash`，第 1、4 个是 deterministic path；全部 transport/status 完成，无超时。v3 结果：`real-acceptance-v3/acceptance-result.json`。
- v4：4 个实际模型 receipt，但第 3 个 run 再次 `partial`，不放行；保留 `real-acceptance-v4-audit.json`。

这些结果证明隔离 conversation API、持久化、纠正/追问/换题消息链和失败留痕可运行；不证明模型质量净收益，也不证明所有消息必经 LLM。`check_model_admission.py` 对本 conversation `report.json` 只认 `served_model`/episode events，不认 report 的 `llm.model`，所以其 no_evidence 结果原样保留；没有手工伪造准入产物。

## 下一步

交接 docs 更新会产生新的 docs-only SHA。必须在该 SHA 上重跑与当前范围等价的 Python/full-scope、frontend/registry/map 绑定收据；随后可按用户授权 push 分支并开 GitHub PR。GitHub required checks 未通过前不 merge；用户未确认前不切生产。实验能力默认关闭。
