# #830 · K3 / 无判官首跑与部署回滚证据

**结论：接线通过，整体部署验收未过，答案质量未签。** 代码 #830 已合；8792 已恢复
`adcda94b5e40` / GLM-5.3-flash / 原判官配置，不是 K3 / judge-off 的生产完成态。
详细时间线、失败与取舍见 [交接](../../handoffs/2026-09-21-judge-mode-k3-cutover.md)。

## 怎么读

| 要验证的断言 | 原件 |
|---|---|
| 作者/部署代码完整门禁，13份步骤日志实核 | `evidence/{author2,main}-*/`、`test-receipts/`、`evidence/main-gates-recheck.json` |
| 曾误选另一脏树收据；手写中间摘要不是哈希核验 | `evidence/main-receipt-check.log.txt`、`evidence/main-gates-verified.json`；订正看 `main-receipt-check-correct-093551.log.txt` |
| 首轮全量失败没有洗掉 | `evidence/author-python/gate.json`、`failure-analysis.redacted.json` |
| K3兼容/无判官统计保护确实被测到 | 定向日志、`evidence/mutations/receipt.json`；正式测试在#830源码 |
| 真实HTTP两题各只提交一次 | `evidence/production-live*`、`evidence/production-verification/runs/`（18个运行原件） |
| K3响应身份、终稿模型判官0调用；无自然KB候选判官路径 | `evidence/production-verification/wiring.json` |
| 独立样本0、no_judge_rate=1，读回落盘报告 | `evidence/production-verification/evaluation.{json,md}` |
| 有限数值对账通过，但日期/范围/资金推断等仍错 | `evidence/production-verification/fact-check.json`、两题 `answer.md` |
| 最终新红触发回滚；回滚前已自然恢复，不证明因果 | `evidence/final-readiness.json`、`rollback-final-precheck.json`、`rollback-final-completed.json` |
| 当前恢复的是旧代码和原判官配置 | `evidence/rollback-final-health-3.json`、`rollback-final-process-config-public.json`；均为记录时点，不是实时探针 |
| 19:17旧生产也超时；随后两个help诊断不到0.5秒 | `evidence/resume-diagnosis-precheck.json`、`evidence/rag-*-profile/receipt.json` |
| 19:43收尾观察仍为旧GLM，RAG恢复、行情仍红；不翻原失败 | `evidence/docs-closeout-observation.json` |
| 备份先延期，后空间回升时写成；未停机未验恢复 | `evidence/post830-backup-{deferred,result}.json` |
| 首跑与部署接受/质量接受分账 | `traceability/20260921-post830-k3-first-runs-rolled-back.json` |

## 来源、脱敏与完整性

- `sources.json` 记录99份选择性来源及本地/归档哈希（含19:43收尾观察），**不是整个证据目录的全量备份**。
- 首轮失败日志的 tail 检出 JWT / secret assignment 形状，未查证它们是否有效凭证，原文没有入库。
  `failure-analysis.redacted.json` 是明确标记的派生副本；`sources.json` 保留原件SHA与替换计数。
  本机原件及pytest原日志设为0600，保留失败现场。其他来源逐字节复制。
- 选择性归档扫描16511个字符串、0敏感形状命中，不等于绝对无泄漏认证。
  原生产运行扫描15388、0命中是另一项检查，不相加为独立扫描覆盖率。
- 启动器、密钥、数据库、4.2GiB Gitea包、失败fixture tar、scratch与无关run不入本目录。
- `sha256-manifest.txt` 覆盖本目录所有文件（仅排除manifest自身），路径相对仓根。
  已提交后可用现有工具核对**Git里的字节**，不是只核本机未跟踪文件：

```bash
.venv-workbench/bin/python scripts/check_evidence_archive.py \
  docs/verification/2026-09-21-judge-mode-k3 --revision <证据提交SHA>
```

本目录只给既有固定版本留证。新增这批文档的提交没有继承#830全量收据，未替后续main或重新部署签字。

## 工具沉淀盘点

| 工件 | 归属及限制 |
|---|---|
| no_judge分类/落盘、K3精确去temperature | 已成为正式源码、回归及变异保护，见#830，不靠交接提醒兜底 |
| `scripts/verify_first_production_runs.py.txt` | 本案两run的只读证据重算器，固定事实/身份；不是通用质量门，不重发题目 |
| `scripts/diagnose_rag_*.py.txt` | 两次有界help导入诊断；不做检索/索引写入，不调整生产5秒超时 |
| `scripts/archive_selected_evidence.py.txt` | 本案选择性复制/脱敏来源程序；归档检查复用正式 `scripts/check_evidence_archive.py`，不另造哈希门 |
| `scripts/{cutover,retry_cutover,rollback_after_final_readiness}.py.txt` | 已执行的本机副作用程序原件，固定身份及授权，**不是下一次部署入口** |
| `scripts/{run_gates,mutation_checks,archive_own_test_scratch,backup_after830}.py.txt` | 本轮门禁/反证/归属清理/容量守卫留痕；不能把固定路径脚本称通用部署器或恢复工具 |

`.py.txt` 是不可直接执行的源码证据，保留原字节；未新增受支持CLI。
重复手工选择证据已变成脚本，但通用化仍需参数/权限/失败恢复合同及回归，故没有假称已完成工具推广。
共享 `harness-reference/BUILD.md` 有他人在途修改，本轮不碰；稳定方法回写既有证据卫生知识卡。
