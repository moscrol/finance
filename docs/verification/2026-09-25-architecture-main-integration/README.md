# 架构审计分支：冻结主干整合与工程门禁

## 身份与结论

- 工作树：`/Users/a77/fwp-wt-architecture-audit-0924`，分支 `feat/architecture-audit-0924`。
- 整合前：`9c2fdc5bab42ac6a8c919aaaef22710a74cbe538`；冻结主干：`9d5b9800a5500e6f64875432f8df3a06713d6f52`。
- 合并提交：`fa7b8094253d3f0887a1e7e85127a75a30a9f9da`。唯一文本冲突为 `.claude/lessons_learned.md`，保留双方独立经验；其他文件按自动合并结果保留。
- 测试修正及受测候选：`698fd172d290f292792d35a69349bd196f8fae23`。相对合并提交只改 `tests/test_daily_agent.py`，没有放松运行时审计规则。
- 四叶工程门禁 PASS，仅对上述干净候选及本机环境成立。未 push、创建 PR、合回 main 或部署；不是生产发布认证。

| 验收层 | 状态与证据 |
|---|---|
| 冻结主干整合 | PASS，双方历史保留，组合测试完成 |
| Python | PASS，Ruff 全仓通过；16423P / 0F / 0error / 74S / 2X，收集 16499 项 |
| frontend | PASS，安装、lint、typecheck、123 项组件测试、build 均 exit 0 |
| e2e | PASS，34P / 2S；绑定链路只跑 desktop，tablet/mobile 两项按既有配置跳过 |
| registry-check | PASS，四个注册表检查及台账 crosswalk 均 exit 0；反向索引仍有 98 条 warning，不签其完整溯源 |
| HTTP 首请求记忆送达 | PASS，原进程内三场景随全仓回归；另设 `WORKBENCH_ADAPTIVE_RESEARCH=on` 的三文件回归 17P |
| 合入 main | BLOCKED，尚待验收与用户确认 |
| 生产装配、真实模型采用、金融质量 | UNKNOWN，本轮没有执行这些验收 |
| 生产发布 | BLOCKED，尚无当前生产前置及发布授权 |

`data-quality-check` 按路径触发；本分支相对冻结主干未改其 workflow、增量导入导出或 report-search 触发路径，本轮不触发。

## 首轮红结果与修复

`fa7b80942` 干净全仓为 **16421P / 1F / 74S / 2X**，收集 16498 项，1060.53 秒。失败为 `tests/test_daily_agent.py::DailyAgentTest::test_daily_agent_summarizes_daily_surfaces_and_logic_routes`，单独重跑仍失败。该红收据在修复前经 `--require-full-scope` 校验可采信；可采信不等于通过。

原因是本分支阶段 A 已将“缺审计报告、缺库存目录”从假绿改为 WARN，旧每日摘要成功夹具却仍缺这些输入、要求 ledger 为 PASS。修复补齐有效空审计及三个库存目录，保留严格 PASS 断言；新增缺失夹具反例，要求未知计数保持 `None`，ledger、工作流步骤及 Markdown 均传出 WARN。没有把缺文件改判为零债务，也没有仅把原断言放宽为 WARN。

相关两文件修复后 14P；提交后加 HTTP 三场景、设置自适应研究开关为 on 的回归 17P，收据为 `adaptive-http-receipt.json`。随后重新执行四叶门禁，不将局部回归拼成全仓通过。

## 收据与复现

- `python-red/`：首轮完整 stdout、收据、运行器日志及退出码，绑定 `fa7b80942`。
- `python/`：新候选完整 stdout、收据、运行器日志、退出码及收集面校验输出。pytest 用时 1155.73 秒，外层退出码 0；全绿后运行器已清理其显式 basetemp。
- `frontend/`：`run_frontend_gate.py` 收据及六条命令原始日志；首尾 revision 相同且均干净。
- `registry/`：五条命令的退出码、首尾身份及原始日志哈希。
- `manifest.json`：上述原始产物的字节哈希。日志保留运行器原有空行，不做格式化。

解释器为 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13；新候选收据依赖指纹 `e1c50cb821a30f00`。本轮在受测提交上执行的完整收集面校验命令：

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
cd /Users/a77/fwp-wt-architecture-audit-0924
"$PY" scripts/check_test_receipt.py /tmp/architecture-integration-698fd172d/python/gate-hXWVYnFP/pytest.json --expect-revision 698fd172d290f292792d35a69349bd196f8fae23 --require-full-scope
```

以后复验须在 `698fd172d` 的干净检出中运行该脚本，并传入本目录归档收据的绝对路径；临时目录不保证长期存在。后继文档 HEAD 不移签，不能在新 HEAD 上将旧收据的版本不符解释成测试失败。

全仓实际命令为 `bash scripts/run_main_gate.sh --pytest-args "-q -p no:cacheprovider --basetemp=/tmp/architecture-integration-698fd172d/pytest-temp"`；启动环境只保留 HOME、受控 PATH，并设置临时 `FORESIGHT_USERS_DIR`、独立 `FWP_TEST_RECEIPT_DIR`，umask 022。重跑应另起临时目录，不复用旧收据或旧用户根。

## 边界与后续

- 首轮与新候选开始前资源采样均无其他 pytest。新候选运行中观测到另一棵树启动测试，见 `resource-during.json`；未干预对方。本次不是全机独占，也不据耗时作性能比较。
- 主干的空结果约束、自适应研究默认关闭及 RAG 启动恢复保留；分支记忆的授权/身份、可选先验、非市场事实及 gap 引用约束保留。语义复核由本执行者完成，不称第三方盲审。
- 常规隔离 e2e 不等于本分支纠偏的生产浏览器验收。HTTP 纠偏仍为 TestClient、合成上一答案、无回答模型替身；17P 不签自适应选择质量、真实模型采纳或金融质量。
- 本轮未读写真实用户，未补数、换库、重建生产索引、恢复采集或新增真实模型运行。生产 readiness 沿用上轮超时的 UNKNOWN，本轮未重新采样，不将历史 503 当现状。
- SPT 词面合同仍拒收；风远追溯、行情及 KB 发布仍由原 owner 处理。阶段 B 真实消费与 C/D 尚未完成。
- 收据签 `698fd172d`，不签后继文档 HEAD。合入前须复核届时主干、冻结实际候选、取得对应门禁及用户确认；真实 Workbench/CLI 验收另按母规格 #76 前置与预算办理。

决策背景：`docs/handoffs/2026-09-25-architecture-main-integration.md`。
