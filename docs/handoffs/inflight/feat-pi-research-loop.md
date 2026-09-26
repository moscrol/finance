## 这个分支做什么
#911：Pi 式观察驱动研究链的离线测试（conformance + Workbench HTTP 入口），不改生产代码。#868 已合 main，本 PR 是对 main 的独立 PR，保持 WIP。工作树 `~/fwp-wt-pr911-main-0925`（本地 test/pr911-main-0925 推到本分支）。09-26 起协调者会话接手，Pi `01a0d35f` 不再推进。

## 决策与被否方案
- 只前向加复核，不改测试：复核没有发现要修的缺陷。否了给 conformance oracle 补 match（不是缺陷，补了扩范围）。
- 取消栅栏的变异要一次撤掉全部 7 层：撤单层会被邻层接住，这是纵深防御，不是测试没牙。

## 当前状态
已前向 main@346be5d8b，测试文件自 7aa5a6d86 起未改，已推 PR 头。本交接之后无提交。付费请求 0，未合 main、未部署。

## 未验证 / 已知边界
TestClient 在进程内，不证 TCP/浏览器/8792。模型、判官、数据源是替身，judge=passed 是脚本化。真实来源、子研究、反证修订、自然验收（#76/L6）未验。conformance 三个 oracle 用不钉原因的 raises(AssertionError)。事件序连续、derive_mismatches 没做变异。全仓/前端/E2E 本分支未跑（协调者统一四叶）。

## 下一步
协调者四叶后去 WIP 合入；自然验收仍走 #76/L6。

## 踩过的坑
3S/1X 是既有声明，不是本 PR 引入的。参数 id 形如 [off-bound-lead-a]（fixture-伪造-首观察）。

## 已验证
十目标 806P/3S/1X（7e39fc8d6）；终头收据见 PR 评论。复核 PASS_WITH_LIMITS：入口身份、异常 detail、公开稿一致、被吞外呼、取消栅栏（全层）变异都按预期断言变红，还原干净；夹具仓零残留。记录 `~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L1/review.md`。
