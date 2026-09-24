# #83 / PR #813

## 这个分支做什么
302132固定回填整合；文档树代码旧，不从此验收/生产。不合main、不动8792/launchd/他股。

## 决策与被否方案
固定3c5先限定独审，否反复换候选；已有GLM按09-23偏好允许。独审/作者重跑/宿主诊断分账，否补签与文本包装交付。详见 `docs/handoffs/2026-09-25-backfill-302132-guard-qc-and-oracle-probes.md`。

## 当前状态
**SPEC_SCOPED_DELIVERED_QUALITY_BLOCKED**。#813 WIP/open/unmerged，head `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59`，base4cc15e703；main03352758c新组合未验。未改/推产品、合入或写生产，自有进程已退。
动态 `~/.finance-runtime/reviews/backfill-302132-0923/CURRENT.json`；本轮 `~/.finance-runtime/reviews/pr813-glm-qc-20260925-02/`，65请求（Spec30、Quality35）。-01为端口19899被他任务占用，0请求失败，未停他人；新批用19913。
760原件归仓 `docs/verification/2026-09-25-backfill-302132-qc-contract/`，原失败批不改。

## 未验证 / 已知边界
Spec报告PASS_WITH_LIMITS、独立5P，仅来源守卫/拒绝子集；成功写入链未独立跑，部分拒绝只验行数。其内作者1F因.git沙箱拒绝，宿主同一测试1P另计。
Quality用尽17执行请求只完成语法检查，产品探针0；最终200/exit0只回JSON文本、未调用deliver_stage，无有效终稿，C3未验。宿主7P与去保护控制不代独审。C1/C4-C7仍未审；旧全量绿不移签到main。

## 下一步
1. 新有界Quality批先核 `host-c3/work/probes/test_fixture_adapter.py`（收据随clone新名复制、他股改真实存在日期），优先执行再补独立断言，不从头造夹具。
2. 用自己的原始命令/XML/故意红/终稿闭合；宿主绿不移签。源 `host-c3/set-mutation-control.json` 已证明重复行见证敏感；没有新付费批在跑。
3. 补完整主张后再前向当前main跑门禁。合入等确认；生产命令/日期/冻结输入/本轮父备份另行逐字授权，CLI无--record。

## 已验证
独审Spec5P、两轴首命令故意红均观测。宿主C3原探针7F夹具错；只修夹具保持断言后7P（合法基线+金额/时间/增删/重复/他股六变异）。临时EXCEPT ALL→EXCEPT后重复例1F预期红，原版再7P；候选未变。对账装置11P，760原件无损核验。旧3c5作者全量15457P/85S/2X、四叶及整库37PASS仅历史有效。

## 踩过的坑
语法检查不是执行；JSON文本不是工具交付。复制库不复制派生收据会先被格式门拦住；他股不存在日期的UPDATE是空操作。pytest隐藏栈帧，收据读结构化验收JSON，不依赖展示文本。来源路径代码误判仍未修，回滚只认本轮父收据。
