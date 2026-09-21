# #833 历史前向整合

## 这个分支做什么
将#783/#800及父实现与主干新材料/上一轮复核保护组合，不覆盖旧枝。

## 决策与被否方案
真实用户/可信合同恢复历史窗口；否助手旧答、摘要、引文授权，防信息截止越权。
保留材料真假设与程序条件分区，否程序指令被当虚构市场依据。
直接依赖#831小片，否混入三领域或#829孤儿片；详见`../2026-09-21-research-tail-forward-integration.md`。

## 当前状态
WIP #833已推7edfe24e76afbd5c365fbf97dd2414847b086f88，源码clean；直接基座ea5c3a946（#831），main基座f783f19c8。旧#800接替评论5359，不关闭。
新独立sol审10:42:18Z因at capacity结束exit1，无report、无动态测试；首尾净树，BLOCKED_PROVIDER_CAPACITY。不是仍在跑、不自动重开。
交接集中docs/research-tail-closeout-0921，固定源码树未写文档。

## 未验证 / 已知边界
新组合Spec/Quality未签；历史原四题仍not_passed，未新自然运行。不签main#830/f2c3e9e1或三领域联合树。#829未合入；不能关闭#793/#794。未合main/部署/回填。

## 下一步
先读domain-reviews-blocked中的history事件与操作员裁决，确认可用订阅和单次有界审核，再补真实消费者独立反例。形成新组合需重新全叶验收。

## 踩过的坑
MaterialQuestion字段是premise_marks，不是authenticity；首次测试误用4F保留。runtime目录新鲜度门曾拦提交，重生后再冻。
原包装器rc1来自收据目录无效+UTF-8变量名误读；pytest精确收据exit0，显式回放另计，不覆盖原失败。正式收据方案归#814，c35只诊断。

## 已验证
固定作者Python12631P/87S/2X、Ruff/四registry/crosswalk0；前端110P、E2E34P2S，六步0、首尾净树。新增8接缝通过。精确收据20260921T091040Z-7edfe24e.json。
封档：`docs/verification/2026-09-21-research-tail-forward/`两包；原件`~/.finance-runtime/reviews/research-tail-integration-20260921/`。
