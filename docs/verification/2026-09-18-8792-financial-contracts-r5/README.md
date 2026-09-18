# R5 财报/计算合同：离线验收

**只签固定业务提交 `dfd7b4ff6c52f76f342b2abeecc24c9045589d79` 的工程行为。**
本目录后续文档提交不声称全量又跑一遍；源码 hash 与父提交 diff 可复核同一业务代码。
没有新增自然模型会话，旧 R3 四首题仍0/4、not_passed，0重发、0澄清续答；不可据此晋级。

- [实现、发现顺序与被否方案](../../handoffs/2026-09-18-8792-financial-contracts-r5.md)
- [机器摘要](results.json)
- 证据根：`~/.finance-runtime/reviews/8792-financial-contracts-r5-20260918/`（下文文件名均相对此根）
- 全量原始收据：`~/.finance-runtime/test-receipts/20260918T094440Z-dfd7b4ff.json`，证据根留逐字节副本。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；测试壳 `umask 022`、`env -i PATH="$PATH" HOME="$HOME"`；前端 pnpm。

## 最终工程矩阵

| 检查 | 结果 | 证据 |
|---|---|---|
| 干净全仓 Python | 11929 passed / 0 failed / 0 error / 81 skipped / 2 xfailed / 17 warnings；672.08s | `pytest-dfd7b4ff.log/.exit`、收据副本 |
| 收据条件核验 | revision/解释器/Python/依赖指纹/clean/未绕依赖门/指定revision/base drift0，八项一致 | `receipt-check-dfd7b4ff.log/.exit` |
| Ruff＋注册表六命令 | 全过；61技能解析/文档表/视图/catalog一致；crosswalk98条既有warning保留 | `registry-dfd7b4ff.log/.exit` |
| 前端 | lint、typecheck、8文件107测试、build过 | `frontend-dfd7b4ff.log/.exit` |
| 前端依赖 | offline frozen-lockfile；294包复用、下载0，忽略esbuild构建脚本提示保留 | `frontend-install.log/.exit` |
| fixture浏览器E2E | 34 passed / 2 skipped，36个已登记测试；不是36全通过 | `e2e-dfd7b4ff.log/.exit` |
| R5撤保护 | 14/14组达到真实断言失败，全部errors0，源码不变 | `mutations-dfd7b4ff/results.json`及逐组log/XML/exit |
| R4旧门撤保护 | 16/16组仍有效，全部errors0，源码不变 | `r4-mutations-dfd7b4ff/results.json`及逐组证据 |
| 旧独立QC | 15/15，无加载错误 | `qc-dfd7b4ff.log/.exit` |
| 旧原文机械重放 | 57事件；file URL仍拒、冻结参数JSON可投影；退出0写、授权阳性1写due10-21（临时目录） | `original-replay-dfd7b4ff.json` |
| R3原件只读诊断 | 四题原件不变；F2不再误缺材料、F3三处数字条件被检出，仍不是新答卷 | `archived-dfd7b4ff.json` |
| R3原题R5解析 | 截止依次09-17/09-16/09-17/09-17；复查日不抢报告年份，F2无最近N义务 | `archived-question-contracts.json` |
| 旧封印只读复核 | R219、R2 131、R3 334、R4 494逐文件hash匹配；未调用旧启动/关闭脚本 | `prior-seals-checked.json` |

收据 SHA256：`168d9d9473914b799100ec16a80bac2ac935be4454439962160eece6de198860`。
全量原始JSON不含xfail/warnings/耗时，这三个字段取同次完整日志尾部，不由passed差额猜。
全量内含77个R5参数化回归；提交前17文件定向599P只签当时dirty树，不冒签最终提交。
`engineering-summary.json`与仓内results逐字节相同；两套mutation测试可能重复选中，不加总成独立样本数。

## R5撤保护目标

| 变体 | tests / failures / errors |
|---|---|
| cutoff_forwarding_removed | 6 / 6 / 0 |
| cutoff_provenance_removed | 14 / 3 / 0 |
| report_year_role_removed | 6 / 5 / 0 |
| cashflow_rows_removed | 2 / 2 / 0 |
| historical_disclosure_filter_removed | 3 / 2 / 0 |
| report_binding_gate_removed | 3 / 3 / 0 |
| draft_period_check_removed | 5 / 5 / 0 |
| calculation_product_gate_removed | 6 / 6 / 0 |
| calculation_id_binding_removed | 2 / 1 / 0 |
| conflicting_report_rows_accepted | 2 / 1 / 0 |
| calculation_error_projection_removed | 4 / 4 / 0 |
| same_episode_calculation_cache_removed | 1 / 1 / 0 |
| metric_obligation_optionalized | 5 / 3 / 0 |
| all_financial_answers_rejected | 3 / 3 / 0 |

每组子进程exit1、至少一个行为断言失败；总runner exit0只表示预期反证成立。
runner内存patch不编辑源码，前后hash一致，输出目录拒覆盖；全拒答反证证明不能靠关掉全部答案换绿。

## 真组合接缝与范围

`test_local_report_gap_survives_real_semantic_gate_and_bounded_resume` 使用真实adapter、structural/semantic verifier，judge脚本化；llm/off两模式×repair成功/失败。相同task/session与根budget、剩余工具0、reopen_tools=false，一次resume；结构修前缺metric，结构检查至少两次、随后一次语义检查。成功completed/失败partial，可信邻句保留，不增预算。

真实Episode工具链 financial_data→坏derived→好derived→finish 验证模型/审计同时见失败和成功；坏`table(title=...)`不是好产物，后续真实沙箱ratio产物可履行对应机械义务。同bind成功计算立即复用、新bind仍拒绝越界继承。

新回归阻断Python socket.connect/create_connection/getaddrinfo，provider/model/judge为脚本替身；旧离线量具有各自的socket阻断/计数。**不能外推全套pytest或全机器网络0；不能把替身E2E当自然模型质量。**

## 首红与夹具错误保留

- `regression-*.log`、`adjacent-*.log`、`expanded-*.log`、`reuse-*.log`、`composition-first/second.log`保存早期过程。
- 测试用不存在的OutputBinding、漏content hash、把解析tuple当JSON、缺purpose、deadline.child API不存在，属于夹具错误；修正后才签目标反例。
- `targeted-first.log` exit4：不存在的test_research_tool_registry.py，0tests；不是产品红。
- `targeted-second.log` 真红：预算耗尽metric被optionalize，repair=False仍completed；局部保护后 `composition-third.log` 72P。
- `targeted-third.log` 使用“经营现金流”简称断言，实际规范为METRIC_GLOSSARY的“经营活动现金流量净额”；改夹具取共享词表。
- `ratio-purpose-red.log` 真红：purpose标题给无关产物背书；`duplicate-period-red.log` 真红：冲突Q1版本未留gap。
- `ratio-equivalence-red.log` exit2为pytest保留参数名request；`ratio-equivalence-corrected-red.log`才是三种等价请求漏义务的真红。
- `targeted-fourth.log` 594P，`targeted-release.log` 599P均为提交前；以干净dfd7全量另签最终代码。

## 隔离与收尾

E2E服务8893/8895，`RE06_E2E_URL=http://127.0.0.1:8895`显式配置；users分别在本树test-results/workbench-users和re06-users，RE06库由fixture新建，episodes/deploy/rejudge/vault在证据根。凭证keychain关闭且测试环境清空模型keys。两服务均结束；不停止他人端口/服务。

新证据以 `evidence-index.json` 主封印和 `post-seal-index.json` 后置清单对账；`final-state.json`记录文档提交、源hash一致及端口状态。敏感扫描只承诺列入清单的UTF-8文本，逐位置/匹配值hash/文件hash审查，不整文件豁免；二进制、Git历史和全文件系统不在范围。原始扫描、审阅及最终扫描分别留存。

共享memory回写只改三卡的本轮段，其他agent新增行保留；最新基线20E/17W仍未清偿，图谱通过不代表全vault健康。自动同步可能收走写回，不重复提交别人改动。`harness-reference/BUILD.md`为他人脏改，本轮不碰。

## 不能据此下的结论

- 候选全集、逐期金融分析/比值齐全、公式和比较基线正确、全局期限一致：未证明。
- 用户截止解析成功不等供应商历史窗口已经完整可得；缺披露日期不等公司没有报告。
- 计算有限指标/依赖/ID存在不等实际读入正确、公式正确或正文数字正确；purpose不作证据。
- 旧F2并未补答；旧R3上下文与评分未改。0/4指四份整题未全满足，不是否定每句内容。
- 没有新live、push、合并、部署、生产开关动作；新增自然验收与发布分别等授权。
