# Knevo 材料吸收续修

## 这个分支做什么
PR #877 WIP：原题/八问/原审稿闸修交付，不合main、不部署8792、不回补、不写生产画像。

## 决策与被否方案
- 86692c7b5补首轮/修复共用逐句构造指引：全输入锚点、主体/指标/单位/期间、收入不等于利润；未改schema/预算/重试/闸门。指引送达不代表模型遵守。
- 不自动改kind、拆句借锚点或截断，不加JSON模式，不再追加写手重试凑成功。详情`docs/handoffs/2026-09-24-knevo-claim-inputs.md`。

## 当前状态
运行代码86692c7b57dc06e73b48ed8d5d7ccc5e56fa9a71已提交。首轮仅material_grounding两处rule变化，载荷19035→19415字符，原题/八问/来源/系统/终局模板相同。
原入口run_20260923_235628_399142：首稿63.967秒分句失败，格式续轮35.279秒缺evidence_boundary，有界补写38.691秒后44条声明结构完成。判官两次75秒超时、首层150.011秒无报告；请求/结构completed、语义partial、作者not_passed、driver not_evaluated。
旧冻结稿重放150.031秒首层超时；两次HTTP哈希均5d091c4f…，与历史70.228秒成功首审相同，未到非事实复核。不证明稳定性。
所有本轮进程已停，8817无监听。证据索引`~/.finance-runtime/knevo-absorption-20260923/claim-inputs-20260923/current.json`。

## 已验证
86692c7b5干净定向2154P/2S/1X，收集2157，Ruff/收据验签通过；接线302P、撤保护5F/恢复5P。非全仓/前端/main组合。
原题逐字保真/material_only/0 Episode工具请求，非全IO零；七份原件不变。writer-only采集不留隐藏推理，私有判词不进写手。

## 未验证 / 已知边界
提示未修好生成：q6仍把厂商出货125→110写量增、40→30未绑40；q7库存60被写远超消耗100，价格/收入事实仍标reasoning无锚点，q8八成计算缺基期。
一次正确分句/全输入、两层判官稳定性与金融语义未过。旧low同hash超时、f1fd 0/12、G1b、包3、Q14、真实Q18、unsupported/nonfactual反例未翻案。开工base落后93提交，不签最新main。

## 下一步
1. 定位规则在场仍错的句子构造环节，别把继续堆提示当已验证修复；仍需原八问验收。
2. 固定稿检验判官重复性/协议规模，不提高预算、不用重放代签Episode。
3. 续修旧反例，删句后重验交付义务。

## 踩过的坑
主树.venv-workbench/bin/python，从目标树cwd跑gate；test_id用uuid。撤保护脚本需保留future annotations，原NameError不算有效反证。采集argv须保留--port；字符不是token，stop/合法JSON/结构完成都不等于接纳。
