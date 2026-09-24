# 8792 R4：四类确定性边界离线返修

**业务提交：`97ca716ba10e1efc5c4558fb6147ad17b5fa88cd`。干净工程检查通过；没有新增真实模型验收，不可晋级。**

用户在 R3 失败收口后授权“执行／继续”，本轮只固化离线回归并返修，不追加 live 预算、不 push/PR、合 main、部署或切判官。R3 固定 `c481272e` 四首题仍为 **0/4、not_passed**，不重发、不改原答案或原判。

- [机器摘要](results.json) · [决策快照](../../handoffs/2026-09-18-8792-boundary-r4.md) · [在途交接](../../handoffs/inflight/fix-8792-boundary-integration.md)
- 私有证据 **R4**：`~/.finance-runtime/reviews/8792-boundary-r4-20260918/`。
- 历史：[R3 真实失败](../2026-09-18-8792-boundary-retest/README.md)、[9655 工程修复](../2026-09-18-8792-boundary-repairs/README.md)。各版本分别签收，不互相借绿。

## 改了什么

| 边界 | 修法 | 必须保留的反面控制 |
|---|---|---|
| 任务中的材料指代 | 按获取动作、来源种类、前后位置和提供者归属解析；系统待检索来源与待生成输出不是用户漏交材料 | 附件、用户上传、先解读后搜索、其他来源种类、否定检索、材料内引述仍不能获豁免；不绑定无关历史材料 |
| 数字阈值跨表达 | 条件标签/章节、表格条件格、比较符及自身含阈值的标题均进入既有数量支持检查 | 已支持数量、日期、协议引用、独立事实段及明确 model_reasoning 授权保留；未知引用仍拒绝 |
| 清单边界 | 独立登记回执和标题 TTL 不算事项；显式列表止于后续非缩进散文；可观察变化的箭头条件可识别 | 回执后真实缺件项仍报缺；只有日期/箭头/占位不能充数；合法单项不等整体完整 |
| 日期归属 | 明确复查日优先；再读时间字段、排除报告期；非法或冲突的明确复查日不登记 | 披露截止/报告期不能抢个人复查日；无安排仍沿用默认到期规则，不从标题 TTL 伪造项内安排 |

没有改变 V8“纯语义异议记 issue”的删除权合同；数字确定性拒绝不能被判官全过降格。没有改模型、预算、写入授权或生产开关。表达缺件继续在同一 Episode 内零工具修复并复验，修不齐仍保留可信正文、诚实 partial。`test_cross_layout_rejection_flows_through_bounded_delivery_repair` 与 `test_receipt_footer_does_not_spend_a_spurious_repair_turn` 验证了这两条接缝。

## 精确工程读数

基线已 `git fetch gitea main`，仍为 `0a1cb8c44aaf2d19ae5f5809bf27119b709b8442`，漂移 0。业务提交上工作树干净，解释器为主树 `.venv-workbench/bin/python`，测试壳 `env -i PATH="$PATH" HOME="$HOME"`、`umask 022`。

| 检查 | 结果 | R4 收据 |
|---|---:|---|
| Python 全量 | **11852 passed / 0 failed / 81 skipped / 2 xfailed**，17 warnings，521.38s | `pytest-97ca716b.log/.exit` |
| Ruff 全仓 | 通过 | `ruff-97ca716b.log/.exit` |
| 前端 lint/typecheck/test/build | 通过，8文件107测试 | `frontend-97ca716b.log/.exit` |
| 浏览器 E2E（夹具服务，无真实模型） | **34 passed / 2 skipped** | `e2e-97ca716b-corrected.log/.exit` |
| registry 六命令 | 全部 exit 0；crosswalk 98 warnings 保留 | `registry-97ca716b.log/.exit` |
| 精确 pytest 收据校验 | 八项通过，基座漂移0 | `receipt-check-97ca716b.log/.exit` |
| 旧独立 QC | 15/15 | `qc-97ca716b.log/.exit` |
| 撤保护反证 | 16组都发生行为断言失败；0加载错误，源文件hash不变 | `mutations-97ca716b/results.json` |
| 新回归/相邻保护（提交前） | 新增175项纳入全量；相关718项通过 | `targeted-release.log/.exit`（dirty定向，不冒充干净全量） |

权威全量收据：`~/.finance-runtime/test-receipts/20260918T065951Z-97ca716b.json`，R4 另存字节相同副本。`dirty=false`、`worktree_dirty_total=0`、未绕依赖门禁。跳过/预期失败/警告不是新增通过用例；E2E两个skip为只在desktop执行的绑定测试，不能签其移动端覆盖。

**首红不抹除：** 新回归最初108项51F/57P；后续参考归属、条件标题/箭头、日期冲突、比较符前缀控制继续暴露失败，所有原日志保留。组合测试首次6F包含两项跨层原因：原清单形状不识别 `≥`，导致更早的结构修复消费替身答案；补齐符号形状后才真实走到“删句→表达缺件→复验”，没有削弱“两次核验、零工具”的断言。

E2E首轮 **33P/1F/2S**：只设置 `RE06_E2E_PORT=8795`，漏设测试使用的 `RE06_E2E_URL`，浏览器访问默认8794被拒绝。`e2e-97ca716b.log` 与 `e2e-first-test-results/`（含trace）保留；补为 `http://127.0.0.1:8795` 后同revision重跑通过。没有改产品或放宽断言，不能把首轮写成绿。

## 原件只读诊断（不是重答）

`inspect_boundary_retest.py` 在新输出 `R4/archived-97ca716b.json` 上执行，原R3资料hash不变，网络连接尝试0：

| 原件 | 新代码的局部判定 | 不代表什么 |
|---|---|---|
| F2题面 | `references_material=false`，不要求用户交材料 | 原64字澄清仍未交付研究；没有生成新答案、引用或复查句 |
| F3最终稿 | 旧索引13/21/23三处无依据阈值均进入数字拒绝集；清单提取两条定性项，不再把TTL/尾注算额外缺件 | 未完整重放Episode；没有据此自动改旧partial/completed或重写登记 |
| F1最终稿 | 事项due从报告期09-30改为明确复查日10-22 | 原退出登记仍是0写；10-17全局TTL矛盾与未列项尾句吞入claim仍未解决 |
| 阳性最终稿 | 一条合法形状due10-22，独立“已登记”不再造成缺件 | “不低于两期较低值”的比较基线仍不存在，结构通过不是证据支持认证 |

旧R原文机械重放也通过：F1仍不登记，阳性授权1条/退出0条；57条durable事件末端非法URL仍被拒绝，但进展可JSON序列化。`original-replay-97ca716b.json` 只签parser/progress接缝，不是真实模型、完整Episode或新的失败恢复覆盖。

## 仍然阻塞

1. 最近两期报告选择跳过已取得Q1；信息截止未完整透传，来源元数据日期与正文发布日期需要逐条审计。元数据晚于截止不直接证明未来信息泄漏。
2. 定性条件依赖缺失财务基线；数量“出现在证据里”也不是完整金融语义蕴含证明。
3. F1整体复核TTL矛盾、未显式列表的尾句归属；当前修复不宣称通用自然语言日期/指代解析。
4. 计算工具 `ok=true` 内含领域失败，以及工具要求计算ID、判官却视为内部标识的合同冲突，仍另线分诊。
5. R4自然真实模型行为未验；旧非法URL/mappingproxy和可信旧稿异常恢复没有新增live覆盖。费用仍unknown，不能由离线0调用推算旧账单。
6. 旧疑似凭证只在当前文档脱敏，真伪、撤销/轮换与Git历史治理未做；其他agent候选未并入。

## 关闭与证据边界

R4 `engineering-summary.json` 核验了旧219、工程131、R3 334份封存原件逐hash不变，绝不改旧封印。8793/8795测试服务已退出，8828仍关闭；一次只读8792 health确认六项报告身份与R3关闭时一致、仍 `bf662e9310ff`，没有切流或改判官。health只证明启动身份自述，不是重新全文件系统审计。

共享记忆三文件更新被既有自动同步提交 `3b13661bde4a4852228d6546137dd0a7ba1c3579` 收走，未重复手工提交；后续其他任务的项目行与索引保留。新基线 `b8fafdba` 前后图谱均74节点/168断言/117在途未校验，无漂移；vault仍19 errors/17 warnings，finding集合无增减（只归一原有项目体积warning的字节数）。`docs-memory-validation.json` 记录写回归属，不借其他任务的新测试读数。

初扫79处命中按30个精确值核查：Python导入/属性访问、反证代码字符串里的模块名，以及日期/数量格式化局部变量，未整文件豁免。审查辅助脚本先因“源码字符串不是AST导入节点”、再因对含符号名的整个VARIANTS字典使用literal_eval失败；原脚本/日志保留，仅解析已检查的代码字符串后完成审查。两次量具失败不是产品回归，也未运行变体代码或模型。

封存/敏感扫描以 `evidence-index.json`、`secret-scan-reviewed.json` 与后续 `post-seal-index.json` 为准：hash仅证明身份；扫描只签实际文本清单及本轮memory补丁，不含Git历史、全文件系统或浏览器二进制trace。R4夹具数据与trace仅留私有证据根，不提交。没有新增真实用户研究/登记；不泛称多轮历史“生产用户文件零改动”。业务源码全量收据只签97ca716b，后续文档提交通过源码同一性核验，不冒称重跑全量。
