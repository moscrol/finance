# A/B继续推进与检查层取证 — 2026-10-07

## 背景：权限闸不是任务终点

用户目标仍是 A：逐张合入现有优化、部署并完成验收；B：提高harness真实回答能力。
此前只围绕#50合并许可描述后续，误把同步/核查准备当终点。本轮已用既有纠偏入口记录到隔离私有台账，
并在FINANCEWORKS-1说明。没有修改生产用户纠偏记录，也没有取得批量合并/部署/写库/删除授权。

等待单张许可只限制该副作用。其间继续B的源码定位、离线探针和新实验准备；
安全事件独立处理，不再要求先私有化/撤销才能推进已授权准备，也不说风险已经消失。

## 按发现顺序

1. 查明#62真实测试失败：`test_deploy_script_and_chain_cut_docs_call_record_cli`仍找文档里的`ln -sfh`，
   新文档已改统一`switch_8792.sh`。已在#62通知owner迁移消费者测试，保留端口/账本/启动/回滚合同。
   不是早先计费阻塞，未重跑同一确定性失败，也未改他人树。
2. 源码核对表明judge off仍走确定性门，数字标注不是全层不删句。
3. 构建同草稿/证据的20条开关观察，补20条晚期交付helper观察，发现forecast否定句误删。
4. 使用真实`TurnOrchestrator.run_turn`、脚本化Controller/Adapter和新隔离store复现：
   “不能说已经验证了剧本。”从最终返回/落盘正文同时消失；outlook门1次、legacy原因过滤器0次。
   仅证明交付消费者可达，不证明自然模型路由、真实质量或HTTP端到端。
5. 初次真实store尝试被探针全禁SQLite的守卫拦截；允许且仅允许两份新隔离用户库后完成。
   失败目录保留，未放开生产数据。不是产品失败，也没有把失败观察拼进成功报告。
6. 提交 `55fbc3f645893f09bb2c487ba191024354187d42`：探针/5项取证合同测试、
   [检查层地图](../verification/2026-10-07-answer-check-layer-map.md)、
   [新三臂比较草案](../verification/2026-10-07-answer-check-comparison-draft.md)。**没有运行时产品改动**。
7. 干净提交重跑：136P/4.59s，生产解释器，6个定向目标；独立#51 checker判`is_full_scope=false`。
   另在干净提交重复20+20+1取证，源hash/HEAD/干净树稳定、真实模型/网络/越界数据库尝试均0。

## 平台回读（11:42 +08）

`platform-b-probe.json`记录准确时点/heads：main=`ea217633ceeaceeb41d3b3f30fa58708fe14ecc9`，protected。

| PR | head | 状态与动作 |
|---|---|---|
| #50 | 570142a2498a6486cc1558b18982bf224cbc8d5e | 五检查成功/CLEAN；仍待用户单张确认 |
| #62 | 8d61a715468e57321bc17b8cc1293f44b6806e52 | python/workbench-check失败；其余绿，尚无新head/owner修复回复 |
| #66 | d7294e3e470c84d86ef00c3d7c286d03a7427c7c | 五绿、Draft；真实内容修订未验，不因CI绿出Draft |
| #67 | cdaf54a6485a6d1ce1c4bc8b91e4a0a786b2e579 | 已明确五绿/CLEAN；本轮后续提交不得沿用该版CI |

#53此前两组十检查均绿，旧10:50“仍跑”是历史。其他owner分支和#63/#67邻接冲突未动。
本轮没有合并、切换生产、生产写库、清理目录或新真实模型调用；只有隔离取证写入、代码/文档提交及协作更新。

## 决策及被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| A/B继续分账推进 | 把等#50许可等同全部停止 | 权限不是目标缩减；准备不能冒充交付 |
| #62迁移测试到统一脚本合同 | 为字符串断言恢复文档手工换链 | 新流程有意收束副作用，不能以过时测试倒逼退回 |
| 全调用链处置地图后再实现候选 | 仅设off/mark或只改verifier | 本轮证明还有adapter后晚期删句 |
| 探针保存观察，不测试“否定必须删” | 以现状当金标准 | 会把缺陷固化；测试应守测量与隔离合同 |
| 24新题配额/真值分权草案 | 自己出题解题再宣称独立留出 | 题作者/复算/运行/盲评角色未落实；草案不能铸“未见”资格 |
| 由#66 owner协调候选 | 本会话并改核验器/抢树 | #64/#66重叠且内容债未清，避免竞争实现 |

## 能力审计：本轮能说到哪里

- 用AST解析`research_tool_registry._DEFAULT_TOOL_METADATA`，19个直接注册工具名没有独立交易日历工具；
  `trading_calendar`已由`task_frame`消费，不等于“系统没有日历能力”。语义查询/模型可发现性仍待验。
- `skills/daily-full-review/scripts/run_review_sync.py`的local计划源码未列新外盘写入步骤；
  #65准确head也没有修改这段计划/消费注册表。#65有取数实现，不等于夜跑已接线。
- `kb_rag.py`有多种降级原因：预算、managed generation、worker和dense依赖等；
  其中dense失败会记原因并回退BM25。存在代码路径不证明当前生产是哪一种原因；未实际查询重排服务。
- `research_workflow_guidance.workflow_guidance`按最终题型给分析纪律，默认开，可关；
  不应把它笼统说成固定输出模板。跟踪/排序硬模板接缝仍由#30对照追踪。
- 外盘覆盖、估值历史3天/47只本轮未重新读主库，不称最新读数；外盘新写入/历史回填先G1–G8，
  当前采访未答，未抓数/写库。访谈参考旧`db/market.duckdb`是退役路径，后续只认canonical主库。

## 收据与后续

私有证据根 `~/.finance-runtime/reviews/release-resume-20261007/`：

- `answer-check-55fbc3f-clean-pytest.json`、`.log`：136P/4.59s，collected136，0F/0E/0S；
  `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python3.12.13，依赖`e1c50cb821a30f00`。
- `answer-check-55fbc3f-scope-audit.json`：准确#51源码哈希独立审计，明确6目标定向；
  原分支checker虽写“未收窄”，只采其SHA/环境校验，不采范围断言。
- `answer-check-modes-clean-55fbc3f/mode-results.json`：完整原稿、证据、公开稿、判决账与隔离会话ID。
- `answer-check-55fbc3f-delta-summary.json`：默认Gitleaks新增可达提交0命中，不清除继承历史风险。
- 开发105P/106P dirty收据和`answer-check-modes-01..04`均保留，不覆盖或移签。
- 代码地图开发时即使build完成仍因未提交代码而stale；干净55f重建后ready，vault仍unavailable。

工具沉淀：反复开关排查已进入仓内具名脚本，有取证合同测试；复用现有重放/盲评工具，未重建评测平台。
暂未改共享harness-reference脏树。发现的产品误删已定位，但修复需owner与新候选验收，不靠文档宣布关闭。

下一步继续A逐张确认与B单owner候选实现/新题组织。首张只请求#50，后续main前进仍同步重验。
C1尚不存在；24题尚未创建；模型/费用/隔离/盲评授权未冻结。没有最终main全量/前端E2E、真实新质量分数、
部署或备份验收；#51候选20712P与本轮136P不能代签这些缺项。
