# 研究要求与引用身份：有限离线修复

## 背景与范围

代码提交 `8a892290d`，分支 `fix/research-contract-citations-0921`，基线 `028a251a1`。
独立工作树 `~/fwp-wt-research-contract-citations-0921`；不修改脏主树、生产配置或市场数据库。

09-21 三题首答及原始取证冻结于 `~/.finance-runtime/comparisons/knevo-threeway-20260921-2042/`。
Q1/Q2/Q3 的要求清单被误识别为材料，Q3 仅保留部分编号；资料排序与反方解释误触发公司排序模板；公开引用过滤与会话投影又以列表位置替代内部 E 号。完整原始问题仍在，不代表任务合同保住了全部要求。

本轮没有重新提交三题，没有调用模型、使用 Knevo 名额或操作 8792。旧首答不改判。
三方比较仍待用户提供本批 Knevo 原答；当前不是盲评、同模型消融或统计胜率测试。

## 发现与处理顺序

1. 沿 `split_user_message -> TaskFrame -> MaterialContract` 定位编号清单丢失，新增有限识别：研究引导语、独立要求标题、连续顶层编号三者同时存在。保留题前公司池、A/B定义、原编号、嵌套条目和非问句要求。强保护、材料引导、文档字段与不确定边界仍走原路径。
2. 复用 `MaterialContract.questions`，在 `build_episode_input` 与 `SemanticEpisodeVerifier._judge_request` 投递 `explicit_requirements`。判官的命名参数与 `**kwargs` 路径均覆盖。独立的尾部“不要联网”仍是整条消息约束，URL 显式材料不丢失。
3. `parse_ranking_intent` 就请求子句识别公司排序，剥离资料/证据/方向排序与非比较最高级；保留无名单的再排序追问，也保留同句同时要求排公司和资料。
4. 公开引用复用完整账本的 `evidence_ordinal_table`，先定身份后过滤；同标签不同哈希保留两条，重复哈希只出一次。公开只增加 `evidence_id`，不公开内部 hash/locator。
5. 会话去重、保存、`citation.ready`、trace 和 API `_run_context` 沿用该 ID；旧无身份记录不按位置伪造 E1。使用已有面板路径，无 `intelligence/api/app.py` 最终改动，也无前端变更。
6. 清除本轮全文件格式化造成的无关换行，保留功能和测试。清理时比对 AST（抽象语法树，即忽略排版后的代码结构）；`TypeIgnore.lineno` 是位置元数据，比较时需归零，否则会把纯换行误判成语义变化。没有用 HEAD 覆盖业务改动。

## 决策与被否方案

| 选择 | 被否方案 | 原因 |
|---|---|---|
| 沿现有 questions 投递要求 | 新建另一套要求身份 | 重复身份容易漂移；本轮不扩大执行或读取权限 |
| 有限清单启发式 | 把全部编号列表当指令 | 报告、引用和材料内的编号不具有控制权 |
| 子句内移除非公司目标 | 全文名单授权排序，或整句否决 | 前者误触发模板，后者吞掉混合请求中的合法公司排序 |
| 完整账本决定 E 号 | 公开列表 enumerate | 过滤后的序号不能反解原证据，且会把引用指向别的报告期 |
| 旧无 ID 保留原记录 | 补造位置 ID | 缺身份不能伪装为已经绑定 |
| 只宣称送达与身份保真 | 据测试绿宣称语义完成 | 信号数量、对象集合、解释分支仍需独立验收 |

## 验证与收据

- 固定代码 `8a892290d`，干净工作树：定向回归 **1504 passed / 4 skipped / 0 failed**，152.53秒。
- 收据：`~/.finance-runtime/test-receipts/20260921T151228Z-8a892290.json`；JUnit：`~/.finance-runtime/reviews/research-contract-citations-0921/fixed-8a892290d.xml`。
- 范围：新边界/引用测试、连续适配器、会话与 API 重载、episode 协议/语义判官、排名/输入解析、`test_e2_*` 材料权限、TaskFrame/query、预取引用序号、`test_premise_*`、store、judge projection、research harness、capability 与 route gate。精确命令与展开后的文件列表见收据。
- 4项跳过均来自既有 `test_e2_boundary_closeout.py:32`，原因是同类嵌套不能用一个闭符伪装双层闭合；不是新增跳过。
- pytest 使用主树 `.venv-workbench/bin/python`，安装 `sys.addaudithook` 拒绝本进程 `socket.connect`；没有真实模型或生产 API 请求。它不是对子进程任意外呼的通用沙箱认证。
- 五组进程内变异：移除清单识别、移除非公司目标保护、误用整句排除、过滤后重编号、会话丢 ID，分别出现 **1/3/2/1/1** 个断言失败；无收集/夹具错误。正常版前后各29项通过，磁盘源码指纹不变。
- 可复验脚本：`scripts/review_probes/check_research_contract_boundaries.py --output <新目录>`；固定版本产物：`~/.finance-runtime/reviews/research-contract-citations-0921/fixed-8a892290d-mutations/results.json`。
- 全仓 `ruff check .`、`git diff --check` 及提交门禁通过。此前未提交树的1504P与早期夹具失败收据保留，不代签固定版本。

## 未验证与后续

没有跑全仓 pytest、前端/E2E（浏览器端到端测试）、跨仓 registry 或独立审核，不能宣布可合入。生产快照与修复基线不同；未推送、未合并、未部署。

下一步是独立的逐项语义覆盖：候选公司集合与2+2+1一致性、A/B各至少三信号、每条正反结果与第三解释、时间窗/分母吻合，以及零新增证据的修复不得制造新阈值。发送 `explicit_requirements` 不会自动完成这些检查；当前题型模板的 fulfilled 仍不是逐项语义完成证明。

别名未命中不能宣称全库缺数、正增长不能写成未增长、单日量价不能证明估值透支；这些事实推断问题本轮未修。`Run.maintenance_launch` 旧记录兼容也未修。

未经授权不重跑原首答，不自动写 reading_baseline/视角/经验卡，不升级规则或部署。需要真实模型复验时使用另行批准的新样本，并保留旧失败。

## 沉淀盘点

重复反向验证已经入库为脚本，不只停在临时命令；跨场景原则写入共享记忆的 `state-transition-identity-must-survive-dedup`：身份不得由过滤后位置重建，验收到公开保存/重载路径。语义等价需要领域合同，未造通用静态 lint。
格式清理脚本是一次性修复本轮排版噪声，不作为生产工具推广。`harness-reference` 的 `BUILD.md` 有他人在途且本地领先远端，本轮不改该树；工具索引补登留待该树归属澄清。
