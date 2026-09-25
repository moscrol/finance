# 日期化恢复前向

## 这个分支做什么
承接#913授权恢复；不重问授权、不增模型额度。树 `~/fwp-wt-dated-recovery-forward-0925`。

## 决策与被否方案
固定09-21候选指纹、整日前像及两条身份，只经原owner准备；否放宽普通报价覆盖、复用09-11例外或手工晋升。09-22非现金行动/IPO另立契约；否缺前bar推IPO、发行价直接代前收。展开：`docs/handoffs/2026-09-25-historical-gap-preparation.md`。

## 当前状态
实现b17adc0已提交，基于main7240283；全量叶子绿，但测试期间#933使main到12d91dc，零漂移收据exit1。文档后继不借祖先收据。#913仍WIP，未合入/部署；本轮测试控制器已结束。
证据根 `~/.finance-runtime/reviews/agent-foundation-0924/deploy/authorized-data-10/`，新缺口包 `remaining-evidence-packet-v3.json`。

## 未验证 / 已知边界
四日QA仍84FAIL/4WARN，各日21FAIL。09-21两股仅补进10轮隔离副本；原5551行全列保留，含36处名称差，未修改03原件。09-22三股未写：raw明确300803.SZ前收56.86、301686.SZ前收55.28；920229.BJ只有IPO页发行价15.67，没有raw前收。供应商IPO页不等于交易所证明或同日名称。
80/403板块缺113成员身份；401不重试。完整派生及same-day/cross-day/L2门未过。生产采样仍3b7e473、health200/readiness503，hash同前次；零生产写入/换库/部署/模型。

## 下一步
1. 读v3与 `historical-0922-witness-audit.json`，补09-22仲裁契约及冻结成员原件；官方全集未认证是既定范围边界，不新增授权门。
2. 保留03/final-replay原件；10轮 `offline-positive/prepared` 有受保护来源链但不可发布，只能经owner推进新staging。08夹具不晋升。
3. 数据门闭合后固定最新main窗口，完整重验实际组合；不把b17收据签给#933或文档头。

## 踩过的坑
JSON时间须严格恢复datetime再校验provenance。新浪量已与同花顺一致，不能再加postVol/postAmt。旧08收集后建图失败保留，本轮先建图后全测并核哈希。审计适配不改依赖环境。

## 已验证
16321P/75S/2X，收集16398；frontend123P、E2E34P/2S、registry六项及Ruff/诊断绿。正式收据仅基座漂移拒收。真实父子入口补2行、保留5551行，另43张事实表指纹及其他日期不变；重复拒绝、父子rc2不发布。09-22三份raw重解码及两IPO页哈希复核通过。生产证明仅限采样点。
