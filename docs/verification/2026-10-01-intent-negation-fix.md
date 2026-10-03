# 否定意图到任务合同边界修复（R-20261001-09）

## 1. 授权、范围与登记时点

用户在 GLM 诊断后回复“执行”。基线为 `94b076fd57259608076cfa69cac529b3126be4d3`，继承 PR12，工作枝 `fix/intent-negation-1001`。R09 已通过 claim_ledger_id 原子领号。

本方案在修前红测之后、修复验收和新模型调用之前提交。此前仅有作用域 helper 的未接入草稿；不倒称在任何编码之前已预注册。只修因果识别读取用户请求的作用域，不改生产，不改预算、重试、记忆、工具、数据或合同槽定义，不合 main，不运行 240。

## 2. 有效修前证据与排除混淆

新增 75 条理解器→最终合同回归：冻结 6 输入、36 组否定词/动词/主体组合、10 条作用域/引用、22 条正向/双重否定/混合意图、本地数据比较约束。原问题必须保持原样，不能通过删掉用户约束让合同“看起来正确”。

有效最终修前读数：**50 failed / 25 passed**（0.80s）；`~/.finance-runtime/intent-negation-20261001/red.log`、`red.exit=1`。

- 首轮夹具复用了 task_id，75F 实为 root budget ID 冲突，已改 UUID；该记录只证明夹具问题，另存 `fixture-id-collision.*`，不充作缺陷红基线。
- 修正夹具后的初稿 53F/22P 包含三个旧主体提取误判：`不得不分析市场下跌的原因。`、`可不可以分析市场下跌的原因？`、`不要解释个股上涨原因，而是请分析大盘上涨的原因。`。三者 `_explicit_company_subject` 分别提取“市场下跌”“市场下跌”“大盘上涨”，先被 company guard 挡住，非本次否定边界所致。原日志留在 `red-with-unrelated-entity-controls.log`。
- 本轮不扩修公司提取；三个集成正控将同义任务动词“分析”替换为“解释”，先在旧码确认为正例后再冻结。新增领域无关 helper 单测应另断言上述原措辞的正向操作仍留在作用域中。**不能宣称所有中文正向归因表达都已正确。**

## 3. 最小实现边界

新增纯函数 `active_request_text`，为识别器提供“未被禁止的请求”视图：

- 区分任务动作否定与事实否定；保留双重否定、礼貌问句、不仅/不要只、转折后的正向任务。
- 处理显式禁止的动词列表、引用/报道的问题与真实指令的边界。
- 使用领域无关的语法操作词/任务动作词，不包含金融实体、日期、指标或冻结题关键词；不新增任务路由正则。
- **仅 `_market_cause_hit` 使用此视图**。其他解析继续读取原题，raw_question、材料限制和模型可见问题保持不变；不在下游硬删 required outputs。
- 这是有界的确定性语法规则，不是完整中文语义理解。未知结构原样保留；未覆盖表达不声称已理解。

## 4. 事前验收与失败判据

1. 上述 75 例全部通过；补充领域无关 helper 回归及已有 query understanding、task frame、controller、episode contract 邻近回归。记录同版本读数；不能借用 d177 全量/CI。
2. 冻结新代码 SHA、plan 和 runner 后，在同 glm-5.3、同只读库上，从隔离的真实产品 create_app 对话入口串行跑三次，每题一次：
   - N：原 S2（逐字相同），预期 comparison，不能强制 causal_chain/counterpoint/cause_attribution。
   - P：原冻结 explicit-positive，预期 market_cause，保留因果槽。
   - D：原冻结 double-negative-positive，预期同 P。
3. 沿用旧 runner/coord 的请求观测、自动身份准入、环境隔离及有限预算。每次最多 12 物理请求/180s、进程 watchdog 220s、起跑间隔 90s；三次总上限 36，无自动重试，不事后增加题目挑样本。新跑只做 P 产品臂，非新 2×2 或普遍 P/R 评比。
4. 同一冻结库 SHA-256 `71c03b7ea8d9c5d5effe41bdc2f089c52d7b846dce97bd6362c02dee1213c023`，只读 0444，3,879,743,488 bytes。沿用官方工具单位合同与旧真值：09-29=14090.71、09-30=14377.22 亿元，差=286.51、幅度≈2.03%；不新增供应商单位定义结论。
5. 三次必须分别核验 HTTP 与原生模型身份、native controller/frame/contract、实际答案的 8 个数值/公式槽及日期出处。P/D 即便因果资料不足，也应保留请求且明示证据不足，不能编造因果。数值槽不等于全面语义评分。
6. 模型错配/缺证据/未完成视为无效，不写作题目 0 分；预算内失败原样登记。N 仍有因果必选槽、P/D 被错误删除、任一明确回归为失败。正向因果内容无法充分回答应与合同是否正确分开登记。
7. 保存库/真实待重判队列前后 hash、生产健康版本、main 状态。全部结果仅为本修复枝验收，不构成部署授权。旧 A/B 11 范围、旧 scorer 源码和 PR8 内容验收阻塞不变。

## 5. 实际结果

### 5.1 接入后的零模型验证

- 首次接入：103P/14F。14F 都到达非因果类型，却被测试里的通用 `counterpoint` 禁令误伤；该槽也属于公司/主题分析，不能一律等同因果槽。未改生产分类、未删合同槽，修正测试为：所有否定例禁止 `causal_chain/cause_attribution`；冻结的纯比较四例另要求无 `counterpoint`，正向例仍要求三槽齐全。
- 修正断言后：75 条集成 + 42 条领域无关 helper = **117P**（4.99s）；禁用唯一接入点（scope view 改回原文）的单变量变异为 **38F/37P**（5.21s）。原 50F 红测中有 12 条混入旧 company 合同的 counterpoint，不能把这 12 条算作成功修复。原日志与第一次接入失败日志均保留，未重写历史。
- 邻近 query understanding / task frame / episode factory / turn controller / material / research contract / tool gate 合计 **512P**（19.05s）；ruff 通过。
- 以上为未提交工作树的读数；提交后的同 SHA 验证及三次真实模型调用尚待执行。不能借用此前全量绿或 CI。

证据留私有 runtime；合成测试、协议、摘要和台账入 Git。

### 5.2 固定代码与真实产品复跑

- 事前协议/红测提交 `79efa09ca`；实现提交 **`9b4a37bd4408e303c6e684a65fc9226d9c432f2c`**，已 push，draft PR13 base=PR12。三次有效运行和全量门禁均固定此实现 SHA。
- runner 完全沿用旧版，SHA `1f2fd3828873521e17027007d97211855fda25394333c51bd43c5c52674e736b`；协议原题/正向/双重否定均取已冻结夹具，不改原问题。旧数值尺原样复用；S2=N 仅为其 self_test 键别名，不是第四题。
- **启动失败保留**：`live/` 无凭据导致 provider discovery 失败，0 请求；停止调度。`live-v2/` 使用字符串替换却未执行现有 Shell 密钥加载表达式，N 两次 HTTP401、0 模型响应、准入2；停止 P/D。两次失败请求照计，不算答题0分，也未把无证据身份放行。
- 人工修正的是凭据加载，不是根据答案挑样本：`live-v3/` 由原 launcher 的四条凭据 export 在子 Shell 正确展开，凭据不输出/落盘；模型仍 glm-5.3。每次请求上限从12**下调至10**，三次≤30，连同401最多32，低于原总上限36；时间/间隔不变，无自动重跑。最终仅用 **13 次物理请求（11有效响应+2失败鉴权）**。
- 各版本 plan 原件不覆盖。v1 hash `f667aee3bfbb5b78beb26d4a3b5084ba66d922677ddfa61c424e5a8811fbef30`；v2 `15a1bcbeafe6770ea4d50146007205c5ff5913c2d37ce165440da0a727c23898`；有效 v3 **`36cc44d500c7fee616b3776181efbf94e8045904bb48dd92bec482ed0cdd95c0`**。

| 输入 | 产品 run_id | 实际类型/因果必选槽 | HTTP/原生准入 | 请求数 | 核心数值槽 | 用时 |
|---|---|---|---|---:|---:|---:|
| N 原S2 | run_20261001_140054_163289 | comparison；无三因果槽 | 0/0 | 2 | 8/8 | 18.266s |
| P 正向 | run_20261001_140224_177151 | market_cause；三槽保留 | 0/0 | 5 | 8/8 | 39.834s |
| D 双重否定 | run_20261001_140354_185121 | market_cause；三槽保留 | 0/0 | 4 | 8/8 | 42.830s |

三次均 completed/error=null，身份由原生完整 episode（包含递归分支检查）和 HTTP 响应两面核验，私有 `verify_live.py` 又独立重算一次。report.turn_intent、task frame、native contract、实际 HTTP 模型输入四面一致；raw_question 逐字未变、local_only 保留、comparison operator 保留。N 只有 comparison_dimensions/key_differences/evidence_boundary/comparison 四个必选输出，不再塞入因果分析。

真实工具：N 一次 finance_query；P 三次 finance_query + 一次 mainline_context；D 三次 finance_query + 一次 mainline_context，其中两次参数无效（decliners 跨 dataset、leading_industry_1 维度误作指标），模型依据官方错误提示修正成功，失败工具原样保留。未改任何工具重试规则。

8/8仅指 amount_29/amount_30/delta/pct/direction/unit/date_29/date_30；公式并不在这8槽之内，另由人工核对日期金额配对、差额/增幅计算式、实际本地观察及出处。不能把8/8叫“全面内容正确率”。同时有全量测试在共享Mac运行，且每题n=1，**不作速度或普遍正确率结论**。

### 5.3 内容验收没有全过——不得用槽分和 completed 洗绿

原题 N 正确回答两日金额 14090.71/14377.22 亿元、差额 +286.51、幅度约 +2.03%，遵守不推测原因。

正向 P 保留归因并明确本地事件证据缺口，但包含“轮动/节前抱团”等带不确定性标签的推断；量价共现不是经过验证的资金迁移或消息因果，本次不为这些推断背书。

**D 有明确内容错误**：写“两日均为温和放量上涨”，而真实工具观察是 **09-29 成交额环比 -17.24%，09-30 +2.03%**。同一答案还列出了负值，构成文字结论与自身数字证据矛盾。不能凭数值槽全中、模型身份正确、contract正确或 completed 状态把它验收成全对。此结论已固化 `live-v3/manual-review.json`，不重跑挑好答案。

本轮没有修前同题正控模型答卷，因此**不能归因“本修复造成了这处内容错误”**，也不能说正常归因回答的全部内容质量已得到保证。已证明的是正向请求及因果合同没有被误删。R09 应记 **partially_confirmed**：合同边界及核心数值成立，更宽的内容要求未全部成立。本轮不顺带扩大修复范围。

### 5.4 同版本门禁、隔离与最终状态

**同实现 SHA 9b4a37bd4408，Mac规范解释器，干净树全量：19,110 passed / 75 skipped / 2 xfailed / 17 warnings，1156.70s，exit0**；ruff全仓通过。`check_test_receipt --require-full-scope --expect-revision 9b4a37bd4408` exit0：收集19,187=实际合计，未收窄范围，revision/解释器/依赖指纹/干净树一致。不是“仅收集未执行”，也不借用d177读数。收据 `final-gate-receipts/gate-fci5Fw2x/pytest.json` SHA `3b2257c3ce9168a2bec6c9002e101eb2fdcd066740984796db25025d90bac36f`。

结束后只读复核：库仍0444/SHA不变；真实待重判队列仍7,385行，SHA `edd22d9cd4694bdb405091540d3270e883e5471edcd76fb65eb89d0faaa525a8`，与测试/实验前相同；生产8792 healthy，revision仍`2c3949786568e50945013aeeb46c168b7fe8bbf9`、code_matches_repo=true；远程main仍`3a2718c6c7dbf5af8ddad249b50835d09deef8a4`。`postcheck.json`保存对照。

有效运行摘要SHA `dab175297a207b7dc900d114db3bcf7fe69df2599d5a5b7877aff8b007031000`；人工内容复核SHA `c5b4a2b71a9791ddb6bc9f10f6d35d22b25bb77b60d18c6db72a9f9d241a6729`。

结果回填时9b4a37bd4的GitHub registry-check/frontend/e2e成功，python仍运行；**不写CI全部通过**。本结果回填提交仅改文档；其最新HEAD的CI单独查看PR13，不挪用旧SHA绿灯。全量和三次模型证据归属于上述固定实现SHA。

R09正式记partially_confirmed，PR13保持draft：边界修复有效，内容验收未全过。未合main、未部署、未跑240。旧 A/B 966/955/11 exit2、11份范围未批准、旧 scorer 空源码及 PR8 内容验收阻塞保持不变。
