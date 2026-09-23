# 研究求证意识候选：接线成立，行为验收未通过

## 范围与裁定

本轮落实的是默认关闭的生成指导，不是已经验证有效的研究能力。
用户希望稳定的是求证习惯，而不是流动性视角、固定顺序、固定栏目或封闭视角菜单。
开关为 `FINANCE_RESEARCH_REASONING=on`；未设、off、未知值都保持旧行为。

**裁定：保留实验候选，不能启用生产或宣称质量改善。**
真实 Workbench 共 4 组、8 个 run，每组每臂仅一次；其中第四组是看过前面答卷后追加的人工挑战，
不是预注册留出测试。行情材料没有冻结成相同快照，模型自行选取了不同证据；不据此推断开关导致收益或回归。
实验在 2026-09-20 夜间开始，09-21 凌晨结束。两份测试服务已经停止；8792 未修改、未重启。

## 实现

- `research_reasoning.py` 是文本唯一真源，按既有研究题型显式启用。题型集合是接线范围，不是视角清单。
- Episode：初始指导进入动态 `question_type_rules`，不改变静态系统提示。
- 工具返回后：短提醒走原 `tool_budget_state.runtime_budget.research_reasoning`，原样持久化并送进下一轮。
  与 `WORKBENCH_RESEARCH_PROGRESS` 独立，不追加反思轮、不增预算、不改工具菜单、证据或完成权限。
- Engine B：AnswerSpec 合成、旧市场复盘合成、`prepare_existing_answer` 回退共用指导；不声称能改变此前检索。
- 普通查数、定义、技术位等不注入；研究题型误承接简单问题时，指令也要求直接回答。
- 不改知识注入门控；不接每日复盘离线生成；不引入新的视角状态对象。

既有 `feat/adaptive-research-loop`（469ba766）提供自定视角与 PLAN 修订载体，尚未合主干；
本片复用当前循环的提示入口，不复制该载体，也不通过 cherry-pick 默认接入未经验收的复核轮。

## 自动检查

三组不重复计数的相关测试通过：329 + 101 + 140 = **570 passed**。
覆盖新开关、未知值关闭、动态输入、权限不增、material_only 空工具、知识门控不变、
两条合成路径、真 loop 的批后送达与无强制调用、工具批执行、预算及恢复。
最初两次测试命令含不存在的旧文件名，均为 no tests ran；未计入通过数。

测试收据：
- `~/.finance-runtime/test-receipts/20260920T155222Z-728f3271.json`
- `~/.finance-runtime/test-receipts/20260920T155341Z-728f3271.json`
- `~/.finance-runtime/test-receipts/20260920T155520Z-728f3271.json`

全仓 Python：**11957 passed, 85 skipped, 2 xfailed**，776.70 秒；使用主树 venv，
清洁环境 `env -i PATH="$PATH" HOME="$HOME"`。日志与 JUnit XML 在上述实验根的
`python-tests.log` / `python-tests.xml`，完整收据为
`~/.finance-runtime/test-receipts/20260920T160916Z-728f3271.json`。
这是未提交候选树的全仓运行，原件由代码包与指纹标识。
全仓 Ruff、`git diff --check`、场景 JSON 唯一 ID 与非空题面校验通过。
以上是隔离工作树的候选代码检查，不是合流 main 的四叶收据。

## 真实入口与身份

使用原有 `intelligence.eval.live_probe start-sidecar` 启动，原有
`scripts/workbench_probe.py` 发 `POST /api/conversations` 与消息请求，未用 CLI ask 冒充。
两臂均 `skill_mode=hybrid`，独立用户目录；只有研究意识开关不同，其他 launcher 设置相同。
通用 sidecar helper 在两臂都关闭 grounded presenter，故这不是生产展示配置的完整复刻。
未改模型提示、答案或中途修正输入以凑成功。

- 基座：`728f327160bbd2485cb635e7ef09d040d718d7b5`，候选当时未提交；不是只凭基座 SHA 认版本。
- 两臂 loaded/repo tree fingerprint 相等：`1d713452cd531e570c6d73446f9f9fd6cb77e57d08d08fc60f03ae83690d7dbe`。
- served model 均为 `glm-5.3-flash`，均 max 档、工具上限 40、研究预算 600 秒；探针等待上限 240 秒。
- 生产仍 `bf662e9310ff751a4c31763815ee78fb7d6d5122`，`source_dirty=false`。
- 全部原件：`~/.finance-runtime/research-reasoning-20260920/`。
  `on/health.json`、`off/health.json`、`production-health.json`、`candidate-code.tar.gz` 固定身份；
  `episode-summary.json` 为结构化摘录，完整报告在各臂 `users/<user>/runs/<run_id>/`。

`continuous-episode.json` 的顶层 `events` 是公开精简事件，不含完整开场文本；
确认送达应读 `outcome.events[kind=prompt_assembled].payload.user`。
同一事件还出现在 verifier 副本，不能用递归计数把一批算成多批。

## 结果

| 场景 | 关闭 run | 开启 run | 观察与结论 |
|---|---|---|---|
| 虚构行业供需 | `run_20260920_235333_021805` | `run_20260920_235333_021815` | 两臂均零工具、`provider_attempts=2`，最终 `partial/invalid_model_finish`。虚构材料被路由为 general_finance_qa，合同要求外部 evidence，用户前提不能满足；公开稿均缺口模板。不能算视角选择验收通过。 |
| 本地 9/11 与 9/14 | `run_20260920_235455_940015` | `run_20260920_235455_940042` | 两臂均 `provider_attempts/tool_calls=4/4`。开组开场提示出现，批后两次提醒出现，关组均无。两臂回答均否认成交增加足以证明增量入场，但均有过强归因。 |
| 简单查成交额 | `run_20260920_235546_531745` | `run_20260920_235546_529154` | 两臂 quick_fact 均无新指导，均调用一次本地查询，数值正确；均违反题面“只按给定材料/只回答数值单位”的严格要求，有多余展开。只证明新指导未介入，不能算完整查数体验通过。 |
| 行情题后的反证追问 | `run_20260920_235716_365749` | `run_20260920_235716_365805` | 关组 `provider_attempts/tool_calls=7/2`，公开撤回部分归因但沿用旧轮事实与旧阈值；开组为 `3/1`，`not_json_object` 后修复仍引用未知 E1，最终缺口稿。不能证明自主修订，更不能宣称优于关闭组。 |

表中 `provider_attempts` 是收据汇总记账，包含核验等调用，不等同研究循环轮数；不据此评快慢。

行情开组虽承认缺少两融、申赎及板块净流字段，仍把“抛压衰竭”“中小市值修复”写成确定解释。
现有数据没有直接提供逐笔卖单、市值分组表现，故这些应是待验证假设。
关组亦有同型过强归因、无依据的上涨家数阈值；不能把“双方都错”当成候选过关。

供需开组内部草稿确实使用产业供需而非流动性，但把订单增长等同销量/收入增长，
把成交额下降读成排除市场因素；而且草稿未公开交付，所以不能拿它代替产品验收。

## 未完成与下一步

1. 保持默认关闭。先处理本次实际暴露的任务合同问题：材料前提资格、续轮可用证据身份与窗口，
   不能靠放松证据绑定或把上轮答案升格事实解决；相关 E2 在途工作应由原 owner 协同。
2. 当前 `reading_baseline` 仍声明“全部证据块强制适用”，有“先阶段再板块”等领域规则；
   本片没有改写该层。后续需按适用条件区分领域规则与稳定求证习惯，不能仅继续叠加相互冲突的提示。
3. 机制解释要验证必要前提，不把代理变量等同目标变量；先用新留出题检验，不针对当前几题增设专用禁句。
4. 用 fixture 剩余场景（共振、承接失败、宏观资料过时、简单定义）及未见题复验；
   当前只跑了 fixture 三个首轮场景与一条追加追问，未完成原供需场景的更正续问。
5. 同版本同题重复配对并独立审核后才能谈质量增益；作者单次语义阅读不是盲评。
6. 前端/E2E、完整合流门禁、部署验收均未执行；合 main 与切 8792 仍须用户确认。

测试通过只证明接线和已断言的不变量；提示送达不证明遵守，公开稿不通过就不能启用。
