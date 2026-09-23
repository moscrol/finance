# R6 × 研究交付：组合候选离线验证

本轮于 2026-09-18 执行，归档收尾跨至本地 2026-09-19。**只证明下列固定版本的作者工程与有限机械合同；旧 R6/R3 整题仍 0/4、not_passed，无新真实模型验收、无独立 QC（独立质检）。**

## 身份与范围

- 业务提交：`d965721553741b7a1267b8541e7806d088083a8f`，分支 `fix/8792-financial-r6-repair`。
- 工作树：`~/fwp-wt-8792-financial-r6-repair`；父提交 `53f433b6` 为此前 R6 返修的文档封存，旧业务为 `15527aad`。
- 只移入数据链 `a31b572f` 的**交付保护提交**并解决接缝；没有移入该枝资金取数/历史路由祖先，没有合入答案保留或 runtime 最新片。
- 新增最终公开投影、异常恢复拼接后的 R6 有限复查；保留合法绑定引用，合并前置/交付拒句账。删句不能授予完成，只有新稿完整核验才能解除既有补修责任。
- 不增模型调用、预算、权限或第二取数链。公开文本沿既有 `view(TerminalFacts(...))` 出口，不放宽静态门。
- 未 push、未合 main、未部署、未切换 8792。后续文档提交不迁绑业务收据。

## 固定版本读数

| 检查 | 结果 | 包内证据 |
|---|---|---|
| Python 全仓 | **12180 passed / 0 failed / 86 skipped / 2 xfailed**，17 warnings | `pytest.txt`、`pytest-receipt.json` |
| Ruff | exit 0 | `ruff.txt` |
| 前端 lint / typecheck / test / build | 全 exit 0；8 文件、**107 测试通过** | `frontend-*.txt` |
| 浏览器 E2E（端到端） | **34 passed / 2 skipped**；隔离 8931/8934，已退出 | `e2e.txt`、`closeout-state.json` |
| 接缝 `financial-delivery` | **6 组断言红→恢复绿**，基线/恢复各 20P | `integration-mutations.json` |
| 财务 `financial-r6` | **13 组断言红→恢复绿**，基线/恢复各 91P | `financial-mutations.json` |
| 交付 `research-delivery` | **13 组断言红→恢复绿**，基线/恢复各 107P | `delivery-mutations.json` |
| 默认 `extraction` | **35 组测试体失败→恢复绿**，基线/恢复各 165P；失败类型见下 | `extraction-mutations.json` |
| R6 封存原件只读回放 | 四份目标错误仍检出，正确计算件未误判；12 输入哈希不变、连接尝试 0 | `archive-replay.json` |
| 收据条件校验 | 精确 SHA、解释器/依赖、干净树、覆盖范围、基座漂移等八项通过 | `receipt-check.txt` |

四套变异分母不同，不相加；开发态 643P 与材料/公开投影 140P 有重叠，不相加或冒充固定版本全仓。旧 `15527aad` 成绩没有转绑。

### 宿主红灯与固定输入复验分账

`engineering.json.all_passed=false` 原样保留。唯一红叶为默认同级 KB 的 `rag-query` 注册表不一致，见 `registry-ambient-red.txt`。**没有运行 scan 倒退登记，没有改/清理共享 KB。**

在相同金融 SHA 与下列干净输入重跑原生五项：parseability / check / tables / views / ledger-crosswalk 全 exit 0，前后身份与状态不变：

| 仓 | 固定 SHA |
|---|---|
| finance-workspace-private | `d965721553741b7a1267b8541e7806d088083a8f` |
| knowledge-base-private | `91725ea9ba0252a43665f9e3130142f946c289ae` |
| finance-research-site | `9f60bef076749cdba13cf228ffa6f22141876eb8` |

见 `registry-pinned.json` 和 `registry-pinned-*.txt`。这不是在 pinned 目录重跑 Python/前端，也不把宿主红灯改绿。该轮临时 finance/site 检出已正常移除，复用 KB 树未动。

### 撤保护失败类型复核及旧文案勘误

运行器拒绝空收集、跳过和 JUnit error，要求非空测试体产生 failure；**JUnit failure 并不保证异常类是 AssertionError**。

- 财务/交付/接缝三套：每一组至少有实际 AssertionError，本轮分别共 82/57/21 条断言失败（这是断言条数，不是新题数）。
- 默认 extraction：28 组有断言失败，7 组仅有 KeyError 或 UnicodeDecodeError：`M7/M14/M23/M30/M31/M34/M35`。缺保护字段或撕裂 UTF-8 解码发生于真实测试体，不是收集错误；还原后均通过。
- 对旧 `15527aad` 封存 XML 只读复核也是上述 28/7。旧 R6 包里“35 组均实际断言红”表述过强，**由本补充记录纠正**；旧包与原 XML 不修改，不把本轮复核描述成重跑旧测试。见 `mutation-failure-classification.json`、`prior-extraction-failure-audit.json`。

## 首红与修复顺序

1. `transplant-first.txt`：2F/296P。两条 R5 老测试假定空计算先成功；更新前提为协议拒收，仍要求不能完成财务义务，不撤空产物保护。
2. `seams-first-red.txt`：16F，其中 2F 是新夹具漏传 `semantic_verifier`，其余 14F 是行为断言；不能全称产品缺陷。
3. `seams-repair-first.txt`：2F/338P，剩余仍是上述夹具问题；`seams-fixed-fixture.txt` 随后 16P。
4. 后补引用资格/旧债不升级/前后拒句账等边界；最终接缝基线 20P。`related-development-valid.txt` 为 643P，`material-projection-development.txt` 为 140P。
5. `related-development-invalid-target.txt` 是误指定不存在的 `test_e2_delivery.py`，exit 4、零测试，不能当产品失败或有效回归。

最终检查在正常与异常恢复路径故意注入后置坏句。这证明保护覆盖相应接缝，**不表示自然日历提示真的会生成财务错误**。

## 回放及未证明的事

封存根仍为 `~/.finance-runtime/reviews/8792-financial-live-r6-20260918/`。只读机械脚本未运行完整 Episode 或最终公开发布；`retained_for_mechanical_inspection_only` 不是新答案，可能仍含原假缺件提示。临时用户目录登记计数为 0/0/0/1，授权 due=`2026-10-22`，不写原用户台账。

尚未证明：自然模型能沿原预算补查/复算并正确交付、跨进程恢复、完整根预算链、来源真实性、多公司或任意公式。F2 实际报告取回故障未修。工程绿、正确计算件与登记成功都不替整题质量。

并行枝只读观察见 `closeout-state.json`：数据链文档 `b4757709`；答案保留文档 `68e0c8dc`（其记录的最新完整工程仍有 RAG 读缓冲红灯，且有他人后续 WIP）；runtime 文档 `e20f5c1d`、业务 `6b70e540`。均未在本轮整合或代签，后续重新核身份。

## 沉淀与证据完整性

- 能力图谱 `graph-audit.txt` exit 0，只核路径/符号，不是质量结论；工具包候选 `aa87df5`，`harness-refs.txt` exit 0，仍报告旧行数漂移/未解析引用，未合 main、未覆盖受保护镜像。
- Vault：方法补充由自动同步 `4ba3af24` 承接，图谱/项目行由 `db683c32` 承接；未手工 push。lint 前后均 **20 errors / 17 warnings、exit 1**。错误集合不变；跨本地午夜有 11 条 inbox 年龄警告加一天，原始差异保留，归一化后无新增。不能称全 vault 通过。
- 外置根：`~/.finance-runtime/reviews/8792-financial-delivery-integration-20260918/`。`manifest.json` 记录包内副本与外置日志、定义、JUnit、diff 的 SHA256（内容指纹）和字节数；不把临时用户数据、pytest 临时目录、软链和工作树纳入证据正文。
- `.txt` 仅是日志展示副本：去行尾空白与末尾多余空行；原始 `.log` 字节不改。若转换发生，清单分别记录 `source_sha256/source_bytes` 与副本 `sha256/bytes` 及 `transformation`；JSON 收据逐字节复制。
- `SHA256SUMS` 覆盖包内除自身外的全部文件。manifest 中旧 R6 输入/旧变异 XML 的外部指纹仅作只读追溯，不改变其版本或判决。

决策背景见 [`../../handoffs/2026-09-18-8792-financial-delivery-integration.md`](../../handoffs/2026-09-18-8792-financial-delivery-integration.md)。下一步只能以新的固定组合重新验收；真实模型验收、合 main、发布分别等授权。
