## 这个分支做什么
收口 Knevo 材料处置与入口修复；保留真实失败，PR #877 仍 WIP，不是语义验收通过。

## 决策与被否方案
- 揭盲套件不进冻结28题分母；不改原题、不开审稿闸、不写生产画像。
- 在既有解析器补有限句法；引用/围栏/材料正文不能授予权限。Q14只保留news_impact指导，不恢复工具。
- 运行完成、有效草稿、判官有效报告、公开回答满足题目分账；判官invalid tool call不称网络故障。
- 快照：`docs/handoffs/2026-09-23-knevo-material-entry-repair.md`；旧观察原件不覆盖。

## 当前状态
- 代码 `f1fd8aa1a16bea4f3dd4e2ba0e5fd92114aea2c6` 已提交；材料范围、虚构身份、编号请求与Q14题型接线已修。
- 隔离Workbench复验绑定上述干净代码，证据在 `~/.finance-runtime/knevo-absorption-20260923/material-repair-f1fd8aa1a/`。最终逐题结论读该目录 `observations.json`；缺文件不是通过。
- 后续文档固定候选的工程门禁与推送结果读同根 `material-repair-closeout/current.json`（含完整SHA、tree、dirty、退出码与收据）；旧 `final-closure/current.json` 只签89780ac77，禁止移签。
- 不合main、不部署8792、不回补、不写画像；不接管其他树。主干漂移只记录，合并前另验组合候选。

## 已验证
- f1fd干净定向门禁580P/4S/0F，Ruff通过；收据在新live目录 `targeted/gate-WNGQ8erU/pytest.json`。886P/4S为提交前迭代读数，不代签新HEAD。
- 真实run_turn装配探针覆盖12原题：材料合同、原始问题、三包answer_q1至q8送达；受测resolver/先验/预取/网络读取尝试0。探针在模型前停，不是答案验收。
- 新首两题公开稿仍为复核不可用，内部均invalid tool call；G1c有有效正文但逐句来源核验仍拒绝。完整终态以后述索引为准。
- 旧live仍9 completed/3 failed、端到端0/12；旧89780ac77工程全量绿不翻案。

## 未验证 / 已知边界
出稿/判官协议与逐句来源核验未闭环；Q18真实台账、空集、权限、身份及跨轮前置未验。非独立审查、非Knevo胜率/top3增益、非完整消融。

## 下一步
1. 从新observations逐条定位invalid finish、missing output、judge协议失败和内容拒绝；缺审计记unknown。
2. 不凭结构化草稿放行；先复现最小失败再修，原题同正门重验，旧失败不覆盖。
3. 等用户确认合并/部署；批准前固定届时组合版本跑完整门禁。

## 踩过的坑
目标树无venv，用主树`.venv-workbench/bin/python`；run_main_gate必须从目标树cwd启动并验完整收集面。四份冻结原件文末空行导致PR diff-check exit2，哈希正确，不改原件凑绿。端点diff的D不是删除历史，#879只改四份claim-scope文档。
