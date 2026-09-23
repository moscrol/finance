# Knevo 判官思考强度隔离实验（2026-09-23）

## 背景与范围

续 `2026-09-23-knevo-writer-diagnostics.md`。旧包1的八问稿已进入材料判官，但两个75秒尝试只收推理片段，未形成报告。本轮目标是检验思考控制能否解决该阻塞，不调整题面、提示、schema、接收规则、原预算、重试权或工具权限。

代码 `6d472c523b963a33f2f8fd1519aca422f2a8b3b5` 仅新增可选 `LLM_JUDGE_REASONING_EFFORT`：复用 `call_purpose("judge")` 上下文，在现有 `_apply_thinking_controls` 处覆盖全局强度；空白/未配置保持原行为，嵌套 writer 修复及普通写手不受影响。生产启动器未改、默认不启用。不代表供应商强制落实，也不是关闭判官。

## 按发现顺序

1. 代码地图刷新至 b0ab979a0，查询到原判官和传输链。实际启动器没有设置全局 `LLM_REASONING_EFFORT`；冻结调用原请求是 `thinking.type=disabled`，却仍收到 reasoning_content。这只能证明观测到推理字段，不能证明具体供应商如何处理该开关。
2. [智谱GLM-5.3官方文档](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3.md)列明强制思考、low/high/max、默认max。文档是GLM-5.3，不是本次端点/模型身份认证；本次请求及对端声明均为glm-5.3-flash。
3. 固定旧 run_20260923_193125_229673 的私有材料首层 request，在干净 b0ab979a0 做两次单物理调用。先显式 enabled+low，64.478秒返回合法工具报告，44条claim回执、8条output回执完整，报告passed=false；后原配置75.208秒超时。除thinking/reasoning_effort外的请求摘要一致。样本非随机、各一次，不证明因果或稳定性；报告合法不代签判断正确。
4. 新增作用域回归先得到2F/3P，接入后局部58P；进程内把判官环境变量查找改到不存在的键，作用域两测再次失败，磁盘未改。固定6d472c扩大定向1874P/2S/1X/0F/0E，Ruff及收据验签通过，收集1877。不是全仓/前端/main组合门禁。
5. 固定干净6d472c，经原launcher与Workbench Conversation入口仅复跑包1一次。显式设置判官low，写手配置不变，独立users/episodes/data根。新run_20260923_204255_417562，probe exit2，117.39秒，failed / continuous_runtime_failed / repair_model_unavailable；没有完整八问稿、未到判官。首稿75.014秒（首content7.276秒，7961 content字符、630 reasoning字符）；原补写39.870秒（首content4.703秒，3440 content字符、343 reasoning字符）。均到期，无工具参数。收到正文不代表生成完成。
6. 为隔离前置写手阻塞，另在干净6d472c重放旧材料request，调用真实 `_run_judge`，原max档、单次75秒、连续共享150秒，沿既有重试逻辑。两次实际请求均为enabled+low，完整请求SHA256均与第3步成功调用相同；两次仍75.007/74.994秒超时，仅8856/9546 reasoning字符，0 content/工具参数。首层150.005秒无报告，未进非事实复核。这直接反证“显式low即可稳定收口”，不是新增产品重试或一次完整Episode验收。

## 决策与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 判官专属、显式可选思考参数 | 可以隔离写手，默认行为不变，实际请求可核 | 实现并测试；不升为默认，不部署 |
| 全局改low | 同时改变写手与判官，难以归因 | 仅用于独立单判官诊断进程，不改产品全局配置 |
| 把首次64秒返回称为修复 | 同请求随后两次超时，原入口未交付 | 明确否决 |
| 加时/加重试/关判官/改报告凑合法 | 改变冻结验收合同 | 不做 |
| 换模型、强制结构化解码、删减审稿输入 | 本轮没有控制实验支持 | 未实施，不签效果 |

## 证据与边界

根：`~/.finance-runtime/knevo-absorption-20260923/judge-effort-20260923/`。

- `probe.py`、`low-summary.json`、`baseline-summary.json`：冻结单调用；`low-private-message.json`私有原返回，无隐藏推理正文，不送修复提示。
- `stage-probe.py`、`stage-summary.json`、`stage-private-calls.json`：真实判官完整阶段重放，非Workbench验收。三次low物理调用中一次返回合法报告、两次超时，仅是执行计数，不是成功率估计。
- `live/health.json`、`live/execution.json`、`pack1-inspection.json`、`live-configuration.json`：原入口一次执行。health revision=6d472c、source_dirty=false、code_matches_repo=true，指纹967860cf8bc8ef0ec2a7cc71979983184a38ef61474384d9de4b599413171cc6。live未额外抓HTTP请求体，配置请求与供应商落实分账。
- `tests/gate-nlICuZE9/pytest.json`、`gate.log`、`receipt-check.log`、`initial-red.log`、`mutation-scope.log`：工程证据。收据只签6d472c与定向目标，不代签后续文档或移动main。
- `source-hash-check.txt`：七份冻结原件全部匹配。原入口问题逐字一致，material_only，Episode工具请求0，非全IO零。两类诊断都不是新盲测分母。

本轮原入口作者not_passed、driver not_evaluated。冻结旧稿已有主体/基期、输入绑定与无成本盈利方向问题未修复，不因一次可解析报告翻案。阶段timeout/余额来自最后一次尝试，elapsed包含两次。字符计数不是token或内部思考长度；请求参数不是服务端遵守证明。

服务/诊断进程均已结束，8817无监听，生产8792未动。PR #877保持WIP，未合/部署/回补/写画像。旧f1fd 0/12、7cfc两题写手失败、G1b认领、包3自洽、Q14漏判与真实Q18前置均保留。

## 续接

1. 写手原75秒/补写40秒窗口内稳定完整生成仍未解决；已有render_from_claims/draft空字符串去重机制，不应臆断重复draft是当前根因。
2. 判官相同low请求可返回也可耗尽150秒；优先量化真实请求/响应差异及报告规模，再设计固定条件实验，不以一次返回签修复。非事实复核本轮未运行。
3. 逐句全输入绑定、厂商出货与终端消耗、比较基期、无成本盈利方向仍须独立修复；不能靠少答八问或补引用掩盖内容错。
4. 通用件已复用既有上下文与传输控制点，没有新增预算器或判官链。实验脚本仅是冻结私有证据的单次诊断，不提升为产品门；方法写入共享知识，harness-reference脏旧树不接管。
