# 审查发布与 owner 原件复核 — 2026-10-07 14:02 +08

本快照接续[日期承接与数据消费者](2026-10-07-boundary-and-data-consumer-review.md)，只记录此后动作。
A（逐张合入/部署）与B（真实回答内容获益）均未完成；没有新增合并、部署、生产写库、删除或真实模型请求。

## 按发现顺序

1. #66从3f0cc758a更新到`f03d9a97e80d08383470324934ac05a28f8ed2fc`，仍仅改交接。
   拟发的“优先撤附加义务”评论被head前置断言挡住，没有发出过时指示。回读新正文后更正本方草案及对用户说明：
   **全面性是harness的职责，目标是相对Pi增加有效视角/证据/反证、减少重要遗漏**；删重复语义裁决、僵硬套版与误伤交付。
   四项→两项原型仅作消融，不是产品目标；不能因Pi没有就撤总览/主线/风险。
2. 提交`c8eb03057da53f939a2e4da3232881c1d9733d9a`，三文件均文档，接续6b探针主体。
   在准确clean c8树用生产解释器重跑151项定向、独立范围校验、全仓Ruff/registry/crosswalk和增量扫描。
3. 13:36:49普通快进push本分支，推前远端df9552c、推后c8回读一致，main前后ea21763未动。
   推送没有强推。该次脚本推前核ref/main但未再次GET保护；保护随后13:40与14:02回读仍开启，不能倒写成推前新回读。
4. #67正文PATCH/GET逐字一致；#66协作评论
   [6031735642](https://github.com/moscrol/finance/pull/66#issuecomment-6031735642)POST/GET一致。
   说明结构片与C1不同变量、不抢实现、不再催词面补丁；要求后续晚期门有具名落点。
   FINANCEWORKS-1/-6分别评论并回读，未改owner/status。
5. 读取owner结构报告、thin原型源码/收据和manifest。报告已经补入用户“比Pi更全面”纠偏；
   manifest列出的8份旧原件SHA逐一一致。固定拷贝本轮所读报告与原型，避免owner后续更新覆盖审查依据。
6. 读取owner准确0703完整pytest收据及日志：21133P/76S/2X、938.68s、18 warnings；
   用#51 checker函数独立审范围与计数，21211条收集全对账。**该venv不是生产venv**，见下。
7. 只读发现owner本地`2f601b096ebb2c636642f0c1bf4c8976a27094e6`首片产品实现，保存固定Git diff/设计/计划；
   未checkout或执行其活动树，没有代推。14:00左右平台远端仍f03；14:02回读仍同。
   本地候选已存在，不能再笼统说“只有原型”；但本会话未独立跑该候选，也未签行为或质量验收。
8. 14:02平台main仍`ea217633ceeaceeb41d3b3f30fa58708fe14ecc9`，protected；#50/#62/#66/#67四个准确头各五绿。
   本快照之后任何新文档提交仍须看新head检查，不能沿用c8五绿。

## 本方准确 c8 收据

证据根：`~/.finance-runtime/reviews/release-resume-20261007/`。以下是本会话实际执行，不是owner自述。

| 项 | 结论/原件 |
|---|---|
| 定向pytest | `boundary-review-c8eb030-clean-pytest.json/.log`：151P/5.14s、collected151、0F/0E/0S/0X；05:35:54.123345Z—05:35:59.486121Z |
| 身份 | c8前后clean；生产Python3.12.13、依赖e1c50cb821a30f00，没绕过环境门 |
| 范围 | 7个位置目标，`boundary-review-c8eb030-scope-audit.json`明确full=false、counts_match=true；旧checker身份通过但“未收窄”措辞仍不采信 |
| 收据SHA | `5afbda43dc968667be878ee3fc6e372925a0287212daa7f82ec3af837a048fe9` |
| 其他检查 | `boundary-review-c8eb030-checks.json/.log`：全仓Ruff、四registry、ledger crosswalk均0；反向101 warnings留存 |
| 增量扫描 | `boundary-review-c8eb030-delta-summary.json`：ea217..c8新增可达历史，默认独立规则、redact100，exit0/0命中；不清除继承历史风险 |
| 发布 | `push-review-c8eb030-{before.tsv,after.tsv,summary.json}`及log；`pr67-body-c8eb030-readback.json` |
| 平台 | `platform-after-c8eb030-push.json`为13:40快照，`publication-closeout-platform-01.json`为14:02快照；前者部分运行中，后者四PR五绿 |

7目标与6b阶段相同：日期探针、answer-check探针、judge-mode-off、numeric-condition-mark、
`test_complete_continuous_turn_strips_outlook_verification`、staged-credentials、handoff-budget。
定向绿不签完整仓、自然答案、最终main或生产部署。code-map ready，但doors/narrative missing、vault unavailable、recall untested。

## Owner 原件核对，不冒充本会话重跑

`owner-evidence-audit-01/`保存本轮所读报告/原型/manifest及review.json，目录700。

### 0703完整pytest

- 原件：`answer-quality-closeout-1007/gate-0703ffae7/gate-nkYKg2Vr/pytest.json`及日志。
- SHA：`847063803fbe5d2b0a4e011451e15672d863303950518f54937fce3bd85201f5`。
- revision=`0703ffae7a1057867b5546180dc59ff4d9f6f3b1`，dirty=false、worktree_dirty_total=0、未绕过环境门。
- target为owner仓根，ignore/keyword/markexpr/deselect均未收窄；#51 checker确定full=true；21133+76+2=21211。
- 解释器是owner工作树自己的`.venv-workbench/bin/python`，依赖指纹`66726d345bf37ce5`；本方生产环境为`e1c50cb821a30f00`。
- 本轮只读当前包元数据：owner httpx=0.28.1，生产=0.25.2。当前包表不重建历史环境；不能把整份收据说成生产venv全量。
- 未在owner树执行checker CLI或pytest（其HEAD已前进2f）；这里只校原件范围与总数，没有取消当前revision校验，也没有移签3f/f03/2f。
- 18 warnings含FastAPI/Starlette httpx弃用、toy模型矩阵运行告警及datetime.utcnow弃用，保留不改写。

### 四项→两项原型

- `thin-contract-receipt.json`给出8项不变、quality_accepted=false；输入Episode原件hash与manifest一致。
- 源码在导入后禁socket connect/connect_ex与subprocess.Popen，进程内替换`_required_output_ids`，释放根预算。
- **源码中code_revision、新模型/工具调用数是字面字段**；无独立HEAD/clean或依赖检查，未套本方数据库守卫。
  原收据只证owner这份离线装配对照自述与已保存输入，不借用本方27次SQLite/0越界守卫或自然执行身份。
- 本会话没有重跑；没有覆写原收据。报告解释“方法提示与取证计划仍在，不能叫默认prompt已全面瘦身”成立。
- 安全边界仍保留：原始输入/归属、来源/时点/单位/分母、权限、只读、根预算/绝对时限/取消及存储。

## 本地结构候选：静态发现而非验收

固定`2f601b096ebb2c636642f0c1bf4c8976a27094e6`相对远端f03的内容在
`structural-candidate-review-01/local-2f601b0.patch`；remote快照另存，不把本地当已推。

- `task_frame.research_dimensions_for`仅对无history_intent的dated_market_review给出总览/主线/风险。
- 默认required_outputs变direct_assessment/evidence_boundary；user_goal保原问。
- Episode factory把维度保留在同一个RequiredOutput合同，以required=false表达建议；调用者显式required仍必需。
- 模型输入将非必需维度移到research_dimensions，说明相关性、反证、遗漏、用户原问优先；不以章节数评价全面性。
- 保留编号材料、多日比较、工具/取证/时点/预算路径；正文删改和Controller合并不在此片。
- 新研究维度测试文件197行，AST计10个函数/参数展开12例，使用真实装配/finish helper断言边界；本方未执行，不签通过数。
  测试里的“旧合同”是同候选代码下替换required_outputs，不是跑两份SHA的完整装配比较。
- 对自然原问显式覆盖，直接回答仍需全文语义判断；手工`rebase(required_outputs=...)`测试不等于自然用户要求已识别并完整回答。
  这是待内容验收范围，不能反向要求再加词面白名单或重复控制器。

## 决策、拒绝与后续

| 选择 | 被否方案 | 为什么 |
|---|---|---|
| 保覆盖职责，结构片分开测 | 四项→两项就是产品目标 | 用户要有据的增量视角，覆盖不是固定篇幅 |
| c8收据重新签准确头 | 6b测试移签文档新头 | 文档也可能有路径/消费者合同，工程身份与内容范围分开 |
| 读取owner独立venv收据并披露 | 把21133P当生产环境全量 | 依赖指纹不同，HTTP客户端版本确有差异 |
| 固定复制报告/manifest并hash | 只记可变路径且假设内容不变 | owner仍在推进，后续报告不应倒改本轮依据 |
| 本地2f只读，远端f03分别记 | 越过owner直接推或抢实现 | 单owner避免交叠，静态发现不是验收 |

下一步：owner发布固定候选后，在独占sync树串行切换并做生产venv定向验收；已有日期/否定反例仍作回归，不进未见留出。
C1未实现，晚期门落点需owner落实；独立题作者/复算/映射/运行/盲评与预算尚未冻结，不自行发真实模型请求。
A仍先取得#50@570142a单次合并许可，main前进后逐张同步重验。#30重合成、#63/#67邻接冲突、receipt cwd缺口独立待办。
最终main全量、本机前端/E2E、两档质量、批准切换与切后真实任务/回滚/备份都未完成；磁盘18GiB，不清理未经点名批准目录。

协作原件：`pr66-value-coverage-coordination-readback.json`；任务板评论
FINANCEWORKS-1=`76f1d31e-a925-4f79-a60c-e836a2e79bc9`，
FINANCEWORKS-6=`e1f5db11-82bb-4fb1-8a6e-347bfd6fe3c0`，created约05:39:18Z。
重复日期手工排查已归仓内脚本；没有新增通用审计平台。共享harness-reference底旧且脏，未写其树；receipt cwd缺口未承接修复，不能声称工具沉淀已补齐。
