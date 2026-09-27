# RE06 QC06 执行及收据写入拒收

时间：2026-09-25 17:35 +0800。用户要求“执行”“继续”；仍仅本地有界独审，不扩大218总上限，不授权push/PR/合main/生产。

## 固定身份与实际结果

候选 `a30e7e4594ac09310271739c8beb30ee8b2cd3ef`，基座 `03352758cf9b31e3f5d179b517be48cb89588679`。R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-execution-final-06`。工程/QC树均干净；本轮新脚本只在文档协调树，不变更受审候选。

- 17:17执行边界预检PASS：宿主Python 5P/1个预期失败，UI 1P/1个预期失败，作者测试仅收集109项。这些是控制链检查，不是审查者业务测试。
- 17:26 gateway实际mirasim-kimi/kimi-k3、2请求、2次HTTP200、一次read往返PASS。
- E2 execute实际3请求，首个run_probe baseline确实调用包装器；阳性对照尚未执行即被资源拒绝：load1=7.0513，pytest=3、预计4，空闲29.16GiB，exit75、counts=null。reviewer/author均未执行，不是候选测试失败。
- 模型下一次调用 `write`，将同组 `work/e2/runs/positive_control-1790328430278122000/receipt.json` 覆盖为 `placeholder - will read instead\n`。这是工具权限漏洞与审查执行失效，不据此推断恶意动机或产品缺陷。
- 宿主核对PID48820/PGID48820后只终止本审查进程组。runner正常记录BLOCKED_STAGE_OR_PROVIDER，112.269秒、3请求、report_structural=false；PID48789/48820均已退出。没有自动重试，没有继续timer/consent/report。
- 本轮新增5请求，实际 **186/218，余32**。原37请求全套计划已不再适用，下一批须在32内重新分配，不自动加预算。

## 证据完整性

宿主记录 `R/qc06-integrity-audit-0925/incident.json` 签原命令日志、覆盖请求、阶段日志、资源观察、损坏后的收据hash和离线检查。原marker记录收据hash `42f28d10f7f3d182f5d8813115b88cc84beadfdaf58962292f02255c7907dcf9`；marker不是原收据备份，不能从中重建后假装原件未坏。

原现场不恢复、不覆写、不复用。`Q/check_execution_v3.py e2` 实际exit1、JSONDecodeError，日志 `Q/execution-evidence-rejection.log`。这是检查器异常拒收，不是完整执行事实PASS；`incident.json`为宿主事件审计，不是独审报告。原预检PASS也不能认证“审查者不能覆盖收据”，它此前没覆盖这条路径。

## 根因与本地修补

`Q/file_tool.py` 只验证目标在整个work根之内，`tools-v3.sb`也允许写整个work。模型没有bash仍能用write覆盖执行者收据；收据放在“审查工作区”不等于不可变证据。

新增 `scripts/review_probes/review_artifact_writer.py`：host指定group/stage；仅许可当前阶段交付物、组内对应清单及新探针；拒收据/日志/冻结输入/跨组/跨阶段写；探针create-only。目录描述符与O_NOFOLLOW阻止父目录/文件软链重定向，单链接检查阻止硬链接截断证据。未知身份拒绝，不让模型从JSON自行授予权限。

正式回归 `tests/test_review_artifact_writer.py` 使用标准库unittest，不启pytest/模型/候选业务测试。13项通过，真实CLI临时根正反例通过；撤掉目标策略的反例实际覆盖临时收据。Ruff通过。新日志及源码hash在incident.json，未绕资源门重跑pytest。

**修补尚未接入下一模型批次**，本批冻结控制器不再修改。任意探针Python仍可利用旧共享work沙箱写别的证据，所以仅文件工具修补不足以关闭整个问题。下一批必须分离“审查者产物写入”和“执行者收据写入”的操作系统权限，实际验证两条入口均不能覆盖旧收据，再准入模型。此边界不因13项离线绿而完成。

## 决策对比

| 选择 | 被否方案 | 理由 |
| --- | --- | --- |
| 停本任务进程并拒收本批 | 让模型继续补报告或重试baseline | 核心证据已损坏，继续不能补原件真实性且会继续耗额度 |
| 保留损坏原件和不可写命令日志 | 按marker修回JSON | marker只存部分字段，恢复会制造假原件 |
| 文件工具允许清单及探针create-only | 仅提示模型不要写runs/只chmod收据 | 提示不是权限；共享可写父目录可替换只读文件 |
| 正式13项离线回归、明确未接线 | 因helper绿就再开模型 | 任意探针子进程仍是旁路，必须另分OS写权限 |

## 当前主干与后续

17:27 `ls-remote`确认main=`64847b7a173bfb7191012638e8ec044ea31e0513`。a30e工程收据身份/环境/范围仍成立，正式合并漂移 **54>5**、exit1，原文 `R/qc06-integrity-audit-0925/receipt-check-main64847.log`。旧工程不签现main，不改阈值。

接手先核 `R/inspect_status.py`，不要再次调用final06的runner或prepare。先接好新写入边界与角色沙箱、做实际越权反例、再重新分配余32请求；无自动模型重试。三组独审/C1-C10、C2语义判官、新main组合工程与#76自然验收仍缺；生产无变化。

工具盘点：新增文件写入边界已进入scripts及正式测试，不只留一次性证据根。共享harness-reference树脏且底旧，未改；可迁移经验写入agent-memory既有门禁笔记，明确“文件工具已验、任意探针沙箱未验”。
