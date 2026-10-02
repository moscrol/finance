# PR16：CI红灯及基座回放（2026-10-02）

被测HEAD `da86baa439aadd1a28ba21cf4abedee1fe616e06`，产品仍 `07a2879b7`。
本页补充工程结果，不改启动预测，也不把以下失败从CI验收分母剔除。

> 后续核验（原审查快照，非本返修的远端 CI）：`75af45fc0` 的 run `36965829455`
> 已结束，Python/frontend 成功，E2E 31P3F2S，聚合 workbench-check 失败；
> registry-check run `36965829397` 成功。下文“Python仍运行”仅是 da86 撰写时状态。
> 本轮独立后端根因定位见 [追问诊断](2026-10-02-pr16-followup-diagnosis.md)，
> 不是产品修复或浏览器 E2E 通过。

## 已取得的CI读数

- registry-check：36964386478 success。
- frontend：110704831336 success（lint/typecheck/components/build）。
- e2e：110704831519 **failure，31 passed / 3 failed / 2 skipped**。
- Python全仓：撰写时仍运行，不能拿本地383P代替。workbench-check 36964386458没有通过。

三项E2E失败是同一stock-deep-dive二轮追问在desktop/tablet/mobile的覆盖，
`intelligence/webapp/e2e/workbench.spec.ts:283` 等不到第二答中的公司名。
原trace显示不是单纯界面未刷新：回答已经终态，正文是缺口提示：

> TaskFrame 要求的输出：direct_answer（工具目录 里没有该输出对应的 claim）

trace工件11208164152，SHA256
`fc106286836ea903c056099d4a7ee59bad0653b7a1a4324c075e07f2b26b22fe`，私有原zip及日志保留。

## 另做一次基座/当前后端对照，未重跑原CI洗绿

先写 `ci-baseline-replay-plan.json`，真实模型帽0；在独立19c detached树与当前da86树，
各一次运行同一CI fixture的两轮请求：
1. 请个股深挖英维克的液冷业务
2. 那它的主要风险和下一步验证是什么？

使用同一共享解释器的ASGI（服务接口后端）TestClient、各自隔离用户态；无provider、
禁Keychain、阻断Python网络连接。两次父进程网络连接尝试均0，真实模型请求0。
没有改任务、改判据、改Controller或加公司名规则。基座临时树跑完确认干净后已移除。

| 修订 | 第二答含公司名 | 同一direct_answer/claim缺口 | 正文 |
|---|---|---|---|
| 19c820824 | 否 | 是 | 与当前逐字相同 |
| da86baa439 | 否 | 是 | 与基座逐字相同 |

正文SHA256：`32ce560097813cddf6569e61e4ee60c3b0ec376b11535b10996330bda45e8e7c`。
证据：`ci-baseline-comparison.json`、`replay-{base,current}/`、脚本及两份日志。

**能说**：这个后端失败形状在19c已存在，不能只归因于本次资源政策差异。
**不能说**：已完成干净依赖的基座浏览器E2E、已证明所有路径无回退、可以把CI红改绿。
共享httpx版本漂移限制依然存在。两个回放不是模型A/B或正式模型×引擎四格。

## 处理边界

R12仍仅本地工程契约限定confirmed，合入状态blocked，PR保持draft；不扩大本PR的修复清单。
不为追这条坏例加主体名称规则，不松开direct_answer验收，不删除E2E断言。
新通用工具界面尚未实施，新模型请求仍0，旧累计96；不合并、不部署。
GitHub原失败说明：https://github.com/moscrol/finance/pull/16#issuecomment-5945674133 。
