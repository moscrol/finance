# 研究进化 06：会话计时竖切（未结案）

2026-09-14；代码 `a4ace074`，树 `/Users/a77/fwp-wt-re06-closeout-check`，分支 `fix/re06-visibility-timing`；基点 `c5359120`。未合、未推、未部署。

## 背景与实施顺序

E2 P1独立审查工具不可用期间推进不依赖真人授权的I14。先在f4c82fa8原样复跑第八轮Y1/Y2，后固定c5359120重验；作者后来的3add63d5只增加文档和收编探针，并无新应用代码，不能把旧合并候选0bd11ece当本次版本。

最初仅有05计时合同与后端events writer，前端未接可见性生命周期。本次新增ResearchActivityControl、researchActivity及其单测，经ResearchInspector挂入既有会话，api.ts加收包确认；保留同一后端writer，无新金融调用或生产试点。

初次实现的任务选择器被撤回：02优先队列task_id不是05冻结分配，没有可信任务、参与者及试点身份，不能靠前端选一项就称配对测量。最终仅会话自用，task_id=null、pilot_id=workbench:<conversation>，服务端原有gap/protocol分区生效。

## 方案与理由

| 选择 | 被否 | 理由 |
|---|---|---|
| 默认关闭，点击同意收到确认才启动；停时补撤回 | 默认收集/启动真人试点 | 工程接线不授予研究参与许可 |
| 可见user_active、隐藏pause/tab_hidden连续区间；文案说明可见不等于键鼠操作 | 隐藏时结束任务、推断外部查阅 | 隐藏不应产生虚假提速，也不能猜用户在做什么 |
| 单调时钟量经过时间，墙钟只定起点 | 每段直接Date.now做耗时 | 校时会制造重叠、倒退或凭空加时；仍为client时钟，不冒充server |
| pagehide/卸载停止，末段与撤回同批立即keepalive发送 | 卸载末段排在慢请求后的Promise队列 | 页面销毁时队列可能根本没机会发；异常关闭送达仍无保证 |
| 撤回effective_at晚于最后区间event_at至少1毫秒 | 同毫秒撤回 | 05按event_at看同意，不应把末段误判成撤回后事件 |
| scope仅当前会话自用，不用候选task_id | 凭空注册实验任务 | 配对任务要先冻结、归属核验，当前不能宣称I14任务闭环完成 |

关闭测量只停止本控件的区间采集，不改变已有研究/服务端run生命周期事实。网络失败当前页显示缺口；不实现离线持久队列/自动重试；多窗口一致授权、异常退出送达和全局撤回机制不在本竖切的已验范围。

## 固定版本验证

全部以下最终读数在a4ace074、dirty=false：
- 全仓Ruff通过；pytest -q -rs：**10146 passed / 79 skipped / 2 xfailed**，17既有数值/弃用warning。
- 研究进化全部test_research_evolution_* + 原Y1/Y2复制针 + product_value_measure：**152 passed**。
- 前端lint/typecheck/test/build绿，Vitest **101 passed**。
- 完整Playwright **34 passed / 2 skipped**（旧绑定测试按设计仅desktop，tablet/mobile两skip）。新增计时三视口均过；trace on。
- registry check、提交钩子、diff检查通过。

全量Python skip逐条原因见原始-rs日志：57依赖本地真实市场库；13尚未提交的build_bp_public脚本；3协议桩不适用；2真实模型opt-in；1历史clone冲突夹具缺失；3已建本地代码地图导致空图CLI跳过（临时夹具仍测空图）。未新增skip绕行；相比作者77 skip的读数不能仅看差额推断退步——本树建了地图，且作者额外收编测试路径不同。

浏览器首轮全套33绿/1红/2skip保留：服务8894但绑定spec默认8794，补RE06_E2E_URL后整套重跑绿，不修改判据。

证据根：`~/.finance-runtime/verification/re06-visibility-a4ace074/`，manifest.json记各文件SHA256。含原始日志、full-python-receipt.json和三视口trace（含I14-events附件）。全量原收据 `~/.finance-runtime/test-receipts/20260914T093239Z-a4ace074.json`。

复跑前端需主树解释器，并同时给WORKBENCH_E2E_PORT=8891、RE06_E2E_PORT=8894、RE06_E2E_URL=http://127.0.0.1:8894；隔离服务不复用生产8792。build会更新跟踪的api/static，本提交包含其真实构建产物。

## 结论边界与下一步

浏览器只投递合成visibilitychange，经真实DOM监听、API、临时台账核对；不冒称OS真人后台实测。05测试单独证明30分钟任务含10分钟tab_hidden时主动20分钟、端到端30分钟、扣时0。两者还不是同一个冻结任务事件流，**I14仅部分工程已验**。

独立复核本提交的同意/页面生命周期及计时边界；随后实现服务端核验的冻结分配上下文，验模型等待→完成→不可变MeasurementReceipt才关I14。I13真人试点/I15真实前向仍需用户授权和结果源。a4ace074还不是与最新main组合后的验收候选；合并/推送/部署各自待确认。

本轮复用现有Playwright/pytest/manifest，不新建通用工具或改harness-reference脏树；方法已落成生命周期与计时回归针，避免只留手工检查口令。
