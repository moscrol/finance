## 这个分支做什么
修复部署帮助误执行事故。最新跨日收尾 `docs/handoffs/2026-09-22-pr831-authorized-merge-and-main-gate.md`；昨日独立审查/候选门禁见09-21-pr831-merge-gate-and-846-review快照。

## 决策与被否方案
- 帮助先退出，写入需apply/显式源/完整SHA/干净树；Git快照与intelligence软链拒覆盖。
- 用户“执行”仅授权#831合并；否决切含已回滚K3的main到生产，#846无独立结论不合。
- 正式main另验、不移签候选；定向复跑绿不覆盖全量红，收据校验0只认证来源。

## 当前状态
#846源码4f9a2af56+8a82ec780，1bc0e62da之后仅交接文档；WIP未合未部署。独立复审300秒空输出后exit143，无结论不自动重试。
#831已按用户消息1f861c24合入main e82717d9；合并事实/后续红灯见评论5498/5505。正式main全量1F，未部署；源分支/验收树保留。
8792仍adcda94 recovery；旧同rev目录为受损现场，禁作回滚目标。

## 未验证 / 已知边界
- main全量12509P/1F：test_ask_watchdog_returns_partial_and_suppresses_late_progress，worker_started未置位。隔离1P、整模块104P未复现；0.2秒时序因果未确认，失败tmp已不在，不能补造trace。
- #846 NO INDEPENDENT SIGNOFF；standalone成功部署、并发换链/写锁未验，旧主检出禁运行help探测。
- 生产23:46 health200/clean/代码一致；本次readiness15/30秒均超时，无当前结论。23:22的503日期差是历史，不冒作当前。

## 下一步
发布/下一批合流前先处理main红灯；持久basetemp取证，定位后修同步或真实逻辑，不加帽凑绿。#846独立审固定新base/head与反例。数据/生产超时另查，不擅自重启。不得删其他agent材料；本轮进程已结束，无新通用框架。

## 已验证
#831 e82717d9树c4ebdbd4与候选相同；Ruff/registry五项0、前端110P/E2E34P2S。全量红收据 `~/.finance-runtime/test-receipts/20260921T160947Z-e82717d9.json`身份校验0/漂移0；复跑收据161125Z(1P)/161251Z(104P)。证据 `~/.finance-runtime/reviews/831-postmerge-main-20260921/`。旧候选d97fdf77全量12510P保留。#846旧d3d27bce全量12528P不移签新head或新合流。

## 踩过的坑
首次合并被WIP挡405，解除#831后成功，两份原件分开保留。健康/就绪/问答分账；历史同例加压未复现不是因果证明。磁盘一度3.8GiB，本轮未清理；不重复全量凑绿。harness-reference有他人改动不碰。
