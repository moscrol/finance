# 8792 边界组合候选

## 这个分支做什么
组合登记退出/请求身份/日期关系与引用数字隔离；本轮固定3faf64fb验真实会话，不是#770整合或切流。

## 当前状态
树`~/fwp-wt-8792-boundary-integration`；代码`3faf64fb`，原文档e857d594，基线gitea/main@0a1cb8c4。本轮仅新增验收文档。
四次首题提交、零重发：3次completed有正文、1次failed；**整体验收未通过**。8828已停、自己的锁已移除；8792仍bf662e9310ff healthy，模型/判官未改。未push/PR/合main/部署。

## 未验证 / 已知边界
- F3保住中际旭创/financial_analysis，但mappingproxy转JSON中断；末请求web_fetch，无stack，未定根因。
- F1退出不写入成立，但无依据阈值被删后清单缺触发条件；同答案离线允许写会误收后续“缺口”段/历史due。live阳性只写1条。
- F2未来日期+E45/E43计划保留；report partial，不代签金融质量。最近两期选年报+中报却跳过Q1；上下文cutoff默认09-18与提问09-16/17未对齐，均待核。
- 失败用量丢失、5次判官tokens未知，不报价；四题不证稳定性/时延。市场快照固定，财务F10/知识库/网页仍在线。
- #770、RE06/#53、#56观察未签；旧sector口径/invalid_query另线。

## 下一步
1. 读[本轮决策/失败史](../2026-09-18-8792-boundary-live-acceptance.md)和[索引](../../verification/2026-09-18-8792-boundary-live/README.md)。原件R=`~/.finance-runtime/reviews/8792-boundary-live-20260918/`；acceptance-summary、closure与cases逐题定位。
2. 优先用失败原件离线复现F3序列化；再补清单结束边界、删坏条件后的必需输出。新代码新revision重验，勿改写旧失败。
3. 新模型预算/远端交付/合main/部署分别确认；upstream是gitea/main，推枝须显式目标。

## 决策与被否方案
- 最终交付+实际写口验组合，否旧绿拼签；每题一次，否反复重采样。
- 保留坏事实门，否关判官修绿；只读谓词对照与live分开标。
- R下独立资源，否生产试写；条件rejudge索引遗漏后停两题终态再隔离重启，不重发。

## 已验证
3faf原工程：Python11612P/81S/2x，前端107P，E2E34P2S，Ruff/registry通过；精确收据`20260917T152129Z-3faf64fb.json`，非本轮重跑。
live F1拒写/F2计划保留/live阳性1条；F3路由正确但交付红。真证据离线6门对照通过、connect尝试0。快照hash/生产身份前后不变；敏感扫描词形误报逐条核销，不是全系统无泄漏证明。

## 踩过的坑
completed不等于report完整；失败存根非空不是成功。通用probe打印的默认路径不是R/users实际路径。
E99999不属E1..E999协议；首次离线红保留，改夹具E999才命中未知引用门。finalizer exit0只代表归档完成，业务not_passed。
