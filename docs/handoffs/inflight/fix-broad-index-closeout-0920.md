# 宽基指数旧工作前向收尾

## 这个分支做什么
接替 data-source/broad-index-delta 的未提交净增量，不改旧树。

## 当前状态
基底728f327160bbd2485cb635e7ef09d040d718d7b5；代码d4d944cb67f9a91380949e18c33d28e22c3a0c00已推，PR #806 open、未合、未部署。本文件与日期快照为另一个文档提交；后续tip不得继承代码SHA收据。

## 决策与被否方案
- 加科创50/上证50及名字；NULL不覆盖旧名字，非空新名可刷新。
- 不加899050.BJ；拒绝旧补丁吞Unknown thscode，Unknown/429/401继续抛错。
- 不整枝合入或改生产DB；旧996行读数只属09-08。
- 展开及其他旧工作去向见docs/handoffs/2026-09-20-stale-broad-index-closeout.md。

## 未验证 / 已知边界
未跑全量Python、前端、E2E、跨仓registry或独立外审；不是合并签字。
未核今日生产覆盖、真实供应商字段/限流和20日跨源比对，未回补或部署8792。
旧树脏改动仍在；保全补丁不意味着可以删树。

## 下一步
先审#806、固定最终tip补适用准入；用户确认后才合main。
真实行情核验、回补另获授权且走daily-full。不要据历史交接重跑生产。
capability尾提交拆分见#805；材料/重算/两参表格仍未解决，不读成已吸收。

## 已验证
d4d944cb干净树白名单环境、umask022、主树venv：139P（五个hithink相关文件）、全仓Ruff通过，严格收据同SHA通过。新增断言修前3F4P。
证据根：~/.finance-runtime/reviews/stale-work-closeout-20260920/；fixed首尾SHA同、状态空。仓内证据docs/verification/2026-09-20-stale-broad-index/。

## 踩过的坑
一次测试路径写错exit4、零测试，已更正后复跑；不计绿。
首轮red收据写共享目录，后续用既有receipt_redirect只重定向输出，不改断言。
本轮runner是一次性留证，不推广为采集/定时工具。
