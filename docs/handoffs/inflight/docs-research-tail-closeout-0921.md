# 研究尾单前向整合协调 · 2026-09-21

## 这个分支做什么
封存#831及三领域候选/审核与接替关系；只文档，不合main/部署。

## 决策与被否方案
- #831先行、领域分别冻结；否拼接单枝绿签联合树。
- 正式收据修复沿#814；c35只诊断，否第二实现。
- 原thread有界续审遇共享容量即停；否自动重试/新增付费通道。
- H-01局部修复与H-02权限丢失分账；否用工程绿替整体通过。
- 背景：`../2026-09-21-history-control-boundary-repair.md`及原forward/resume快照。

## 当前状态
WIP #838统一交接；新包3a1c8289b已推，45/45 Git blob及原件核验；旧三包281/28/38不变。#833/#838/#845正文与评论5452/5454/5457已回读；记忆446189f5已同步。包外history-boundary-repair-01-publication-check.json保存发布收据。
WIP #845修复树d91aff9d8已推、clean，叠在#833上；原#833 7edfe24e7不移动。H-01受保护引文不授历史控制权，受测范围已修。H-02正常版两例仍红：省略式合法续问保窗口/截止，却material_contract=None，授权出现web_search/web_fetch。只验合同/工具登记，未执行工具/网络/DB；整体历史CHANGES_REQUIRED。
#831 ea5c3a946有限接受不变；#834 cb16cd463与#835 d82cb16b5原候选未动，不是联合树。历史两次审核容量失败、无终审报告；第二轮runtime/财务未启动，无后台待收。本轮未重开审核。

## 未验证 / 已知边界
#845仅530定向绿，未跑该SHA完整Python/前端/E2E/registry全叶。三领域独立终审缺，历史四自然题、财务R6/R3旧not_passed不翻。runtime非跨进程driver/lease/未知效果对账闭环。新main、联合树及#841组合未验。无合main/8792部署/生产回填/清树；邻线不接管。

## 下一步
先读新包frozen-regressions/adjacent-unresolved.txt，修H-02：可信用户权限须随历史意图同步，不能从助手文字/无条件复制旧合同猜授权。新SHA验证正负例与执行前上限，再补授权范围内的门禁/独立审核；不继续求绿。交接集中docs枝，冻结源码不因归档移动。

## 踩过的坑
首版变异量具恢复__code__抛错不计有效；v2/frozen另验。39例曾漏单撤resolution保护，补2例后击中1F。误编辑无boundary后缀原树已精确撤回、核clean。wrapper失败/pytest成功/回放分账，c35中断不称全量绿。

## 已验证
d91固定三组530P=168+169+193，含新41例；Ruff/diff-check通过。五变异24/15/6/1/4断言红、零夹具错、源码前后哈希相同；邻接2F独立保留。旧四候选全叶收据不移签新代码。
证据根`docs/verification/2026-09-21-research-tail-forward/`，新包history-boundary-repair-01；详情/首错/命令在README及收据。
