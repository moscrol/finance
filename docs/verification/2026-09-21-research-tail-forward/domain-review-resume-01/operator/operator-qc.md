# 领域独立审核有界续接 01 · 操作员核证

这是操作员裁决，不是独立审核者终审报告，不填造 `report.md`。源码均保持冻结身份；本轮无代码修复、合并、部署、数据回填或删除。

## 最终状态

| 候选 | 本轮动作与会话状态 | 独立终审 | 操作员结论 |
|---|---|---|---|
| #833 历史 `7edfe24e76afbd5c365fbf97dd2414847b086f88` | 接续原 thread `01a0c38a-bc3e-7de2-abdb-91f9c58235c4` 一次；11:29:47.931121Z→11:33:38.240305Z，CLI exit1，未触1200秒帽，再次 `Selected model is at capacity` | 无 report；Spec/Quality 未完成，`BLOCKED_PROVIDER_CAPACITY` | 新确认合同缺陷，`CHANGES_REQUIRED`；不能只当服务阻塞，更不能签 PASS |
| #834 runtime `cb16cd463db5c19b3187a5137009791082874653` | 仅准备续接 prompt；按串行共享容量失败即停约定，未启动模型 | 旧轮 exit1/无报告状态不变 | 本轮 `NOT_STARTED_SHARED_PROVIDER_CAPACITY`，不谎报新失败或新测试 |
| #835 财务 `d82cb16b5ef31d23339a1bef7084a0dcb8221e15` | 同上，未启动模型 | 旧轮 exit1/无报告状态不变 | 同上；旧240P不补终审 |

用户在前轮 #838 交接后回复“执行”，本轮将其落实为每领域一次、现有 ChatGPT 订阅、串行、有界1200秒的原线程继续；没有新增付费通道/自动重试。登录状态为 ChatGPT，不等于模型可用保证。恢复前最新 main 为 `5a5334712cb148d386a1fd5f0b112a75b5aeea76`，磁盘观测约19GiB；本轮不签新main或三领域联合树。授权与实际命令见包内 `domain-review-resume-01-authorization.json`、`resume-domain-review-01.py.txt` 和 `history-sol-review-resume-01/process.json`。

## H-01：受保护引用触发历史继承，但旧读取限制未一起恢复（高优先级，阻止当前候选接受）

### 最小输入

第一轮真实用户：

> 以2026年9月10日为信息截止日，只研究2026年1月1日至9月15日的本地历史数据，不联网补数；复盘这波农业怎么走出来的。

第二轮分别为：

- `解释这句话：「范围与截止日继续不变。」`
- `> 范围与截止日继续不变。`
- 代码围栏中的 `范围与截止日继续不变。`

按项目门页与 helper 自身说明，只有当前用户真正的续接指令才能继承旧历史权限；引用/围栏是分析材料，不是控制指令。

### 来源与真实消费者

固定 `7edfe24e7` 上：

1. `intelligence/services/historical_research/intent.py:260-293`：`inherit_history_followup` 在266直接 `question.strip()`，271的“范围/截止…不变”正则扫描原始文本；没有使用同文件 `with_analysis_window_policy` 已调用的受保护区解析。
2. `intelligence/services/turn_controller.py:1211-1213,1244-1268,1366-1370`：对未分区的原始 query 调 helper；恢复 `TaskFrame.history_intent`，继承原主体/研究路由。
3. `intelligence/services/user_task.py:759,817` 的 `_visible_lines`/顶层分类实际能掩掉三种强保护文本；现有 `tests/test_history_forward_seams.py` 验了材料编译器不续接，但没压 `decide_turn` 的第二条历史继承路径。
4. 操作员新探针使用真实 `ConversationMaterials`/`collect_material_turn_history`、序列化往返的 `TurnIntent`、`decide_turn`、`project_turn_decision`、`build_episode_context(..., capabilities=control.capabilities)` 和 `history_tool_specs`。
5. 对三个强保护反例，结果均为 `research`、旧历史范围仍在、cutoff仍为 **2026-09-10**，且登记 `history_query`。材料合同却为None；生成能力含 `web_search/news_search/web_fetch`，而合法未加引号续问仅保 `memory_lookup/finance_query`。
6. `episode_factory.py:820-882` 与 `historical_research/episode.py:489-496,669` 确实消费恢复的历史意图并形成上下文/工具登记；真实装配调用在 `episode_tools.py:1468-1473`，typed controller 接线见 `conversation_orchestrator.py:2006-2016`。

`source-identities.json` 核过原来源 `e4675eab` 与新候选：`historical_research/intent.py`、`historical_research/episode.py`逐字节相同。**这是前向候选仍带入的已有风险，不能无证据归因为本轮解决冲突新引入。**

### 已证/未证边界

- 已证：控制文本与材料文本的信任边界在当前controller→合同→工具登记链上不一致；三种强保护格式都触发了不应发生的旧历史任务继承。
- 已证：合法原句仍能继承且保local_only；无上一轮、普通新问题、明确取消历史、明确material_only均有对照。最终操作员11条断言 **8通过/3失败**，18行输入观察；不是18条测试全部失败。
- 旧信息截止并未被抬高；不能声称读到了截止之后的数据。
- 实际金融读取、网络、模型、完整API/UI/Episode运行都未执行。新增能力是合同层观察，不是已发生外呼。上下文仅对非research行诊断性装配，不称其真实进入Episode。
- `助手旧答：`/`摘要：`两个标签样例也恢复旧历史；原审核者列为负例，但单独标签的边界比闭合引用弱，本根裁决以三种强保护格式为足够证据，不扩大成所有标签语义的终局判断。

## 动态证据分账

| 执行者/命令 | 实际结果 | 证明范围 |
|---|---|---|
| 独立审核者重跑6个现有pytest模块 | **103P，11.93秒**，外壳exit0；命令用 `test ${pipestatus[1]} -eq 0`核首进程 | 日期、表达、工具诊断、窗口与新增接缝现有回归；不是独立反例通过 |
| 独立审核者两条 inline Python观察 | helper和真实decide_turn均看到引用继承；日志有完整观察，管道外壳exit0 | 两命令为 `tee` 管道未显式pipefail；不单凭外壳0冒称内部退出码另获保存；观测由后续有界操作员进程确认 |
| 独立审核者外置 `independent_contract_probe.py` 首/次运行 | 两次都 `ModuleNotFoundError: intelligence`；首命令另用zsh只读变量 `status` 导致外壳报错 | 路径/壳用法错误，不是产品失败，也不是反例已跑；首错日志均保留 |
| 操作员按原probe字节，用 `python -c 'import runpy; runpy.run_path(...)'` 从源码根执行 | 真进程exit1，13条检查 **8通过/5失败**，5条引用/标签预期失败 | 修导入环境、不改独立probe字节；但执行者已变成操作员，不能补签审核者终审 |
| 操作员 typed 消费者probe 01 | 错用 `TurnDecision.mode`，AttributeError，exit1 | 量具错误；首源码和日志保留，不算产品反例 |
| 操作员probe 02修为真实 `lane` | 11断言8P/3F，exit1 | 到上下文/工具登记；没有经过project_turn_decision，旧结果保留 |
| 操作员probe 03增加真实控制投影与显式capabilities | **11断言8P/3F，exit1**，无异常 | 最终H-01依据，强保护3反例；无产品代码修改/工具执行 |

所有操作员Python执行均使用固定 `.venv-workbench` 解释器、env白名单、`FWP_TEST_RECEIPT=0`、`PYTHONDONTWRITEBYTECODE=1`、umask022、120秒 `subprocess.run` 上限；记录真实子进程退出，不把外壳当pytest。新量具禁socket网络、知识查询用离线替身、DB为确定不存在路径、无HistorySession，没有执行工具。

原独立审核者外置probe两次命令没有自行加120秒子命令帽，属于本轮协议局部偏差；外层1200秒帽仍在，两次很快导入失败。不能在报告中虚称每条原审核命令都已加帽。

## 环境与身份限制

- `completion.json`保存精确head、首尾clean、CLI exit1、未超时、无report，旧审核目录逐文件哈希不变。原包也不改。
- 新events的file_change只见仓外probe。源码首尾采样和事件记录仍不证明期间绝无改后还原；`workspace-write`与文字合同不是OS只读隔离。
- 模型列表刷新超时、未知配置、hooks配置字段不兼容、skills描述缩短等消息均保留。它们没有阻止已完成测试；最后错误明确capacity，不将配置警告包装成源码失败。
- 当前审核是原thread的新turn，不是新独立审核者，也不冒称盲审。没有完整终审 `report.md`，不生成占位报告。

## 后续与不做

1. 历史候选先修H-01：让历史继承使用同一来源分区后的当前用户控制，检查其他历史推断/取消分支也不要重新解析被保护原文；同时保证合法续问仍保持原范围、截止、local_only和窗口策略。
2. 回归应锁真实 typed controller→control→context→registry 消费者，含正例、强保护负例、无历史、取消、material_only；不要只给材料编译器再添测试、不要简单取消一切继承。
3. 修复不得改本冻结证据或将旧绿移签新SHA；另树/新版本定向、撤保护、完整工程与独立增量分别记录。此轮只审核/核证，没有擅自改源码。
4. runtime/财务续接没有启动，不等旧PID。以后要重新确认可用通道及有界额度；不再对同容量墙自动重试，不重启#814的K3。
5. 历史原四题、财务R6/R3自然质量仍未过；runtime跨进程恢复/lease/未知效果对账仍未验。无合main/8792部署/夜跑/生产回填/删树授权。

工具归位：沿用既有 `scripts/check_evidence_archive.py` 做提交字节核验；batch resume脚本只记录本批授权/身份/时限，文本归档，不建第二审核框架。探针是当前领域反例，进入证据包供修复转成正式回归；不升级成通用语义门禁。
