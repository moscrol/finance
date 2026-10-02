# 四格接线 R-20261002-16

独立树 fwp-wt-model-harness-f4-1002，分支 eval/model-harness-f4-1002。产品基线main3a2718c6，评测依赖PR18/a57。不合main、不部署。R16工程confirmed，仅零模型接线；累计仍100；未创建live批。

## 已做
- 固定私有旧scorer SHA/magic，CPython3.12单次读取执行，独占CLI/题尺答案hash；source_restored=false，semantic_acceptance恒未建立。
- 原D9四项检查保持。但D1指标与数值错配仍1.0（正确1.0/空0.0），只能作兼容分，不能作质量充分证据。
- 原完整会话API断网预检：两GLM各16拟发请求、均stream=true、0外发，绑定请求型号正确；回答终态failed。不是served身份验证、不是F4、不是浏览器E2E。
- 复用6d8的thin/admission两模块两测试及CLI；生产API/runtime/services零diff。
- 28新增/131相关P（4.64s）；6/6加载器变异；Ruff绿。失败登记语法错、缺CLI62P1F、入口422、Ruff E702原件均留。
- DB快照官方APFS克隆、只读hash前后71c03b7e…；原scorer空源/缓存未动；旧R14未重开。

## 下一步
先提交/双push/Draft PR，clean重验（以动作实际收据为准，本文尚不声称完成）。真实四格另冻结严格内容评分、HTTP完整入口、每个父子物理请求、两GLM共池串行90秒与绝对预算。P当前是流式，R15非流式接线不能移签；若缓冲完整body须披露不验逐字/首字延迟。先四格，不开240，不称已标定强弱，不按模型档位硬路由。

证据 ~/.finance-runtime/model-harness-f4-preflight-20261002/；详情 docs/verification/2026-10-02-model-harness-f4-preflight-results.md。共享httpx漂移/地图unavailable、既有PR红门均不豁免。
