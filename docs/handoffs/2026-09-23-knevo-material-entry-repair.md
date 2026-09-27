# Knevo 材料入口修复与复验边界

## 背景

本轮接续 `2026-09-23-knevo-absorption-closure.md`，旧12题真实入口端到端0/12不撤回。本次修复提交为 `f1fd8aa1a16bea4f3dd4e2ba0e5fd92114aea2c6`，仍基于已纳入的 main `bbd53487f4cefdae97eae90f7322394d36e65462`，不追逐移动主干、不合并或部署。

## 发现与处置

1. 既有 `split_user_message` 未识别“仅使用以下/下列材料”“只分析虚构材料”等范围声明；虚构算例和公司的真实性也有漏识别。补充确定性有限词族，真实性与读取权限分别解析。
2. 编号候选识别和最终接纳使用不同的请求句法，导致“计算”“评价”“给出摘要”等非问号题丢失。两处改用同一判据，保留三份冻结题包完整八问。顿号连接的限制逐句识别。
3. 材料型消息题即使已禁止检索，仍需要消息分层指导。新增 `material_request_question_type`，由请求区识别“消息支持什么结论/意味着什么/有什么影响”等句式；完整编号题包保持多题，不压成单一消息题。
4. `TurnController` 只保留消息题型；材料合同仍将工具能力及证据计划置空。生成指导不是授权器。
5. `test_knevo_material_delivery.py` 覆盖范围变体、保护区域、编号请求、Q14指导和真实 `TurnOrchestrator.run_turn` 装配。冻结题面/哈希未改；受测读取探针在模型前停止，不能替代实际答案测试。
6. 使用独立用户、用户根、Episode根和数据根启动 Workbench 复验；行情库指向明确不存在的测试路径，生产8792不动。health记录 `source_revision=f1fd8aa1a16bea4f3dd4e2ba0e5fd92114aea2c6`、`source_dirty=false`、`code_matches_repo=true`。模型为 `continuous_glm / glm-5.3-flash`，不是独立盲审。
7. 首两题公开稿仍为“本次未完成独立复核（复核服务不可用）”，私有原因均为 `semantic judge returned an invalid tool call`。首题最初一条claim含两句被拒，模型下一轮已修正并交出结构化草稿；故不能把最后的失败继续归为材料范围漏识别，也不能把判官协议错误写成网络故障。
8. G1c公开稿保留读取失败、不可核旧判断、订单不等于验收及恢复条件；判官仍拒绝未绑定来源的缺项/真实性陈述。正确片段不等于整个来源合同通过。

## 方案取舍

| 选择 | 未采用 | 理由 |
|---|---|---|
| 扩展现有有限解析规则 | 新建权限器或交给额外模型猜权限 | 保留已有来源隔离与可重复测试；有限句法不宣称通用自然语言理解 |
| 引用/围栏/材料正文仍作数据 | 在全文扫描指令后直接授权 | 材料中的注入文字不能获得顶层权限 |
| news_impact仅作生成指导 | 为了消息分析重新打开检索 | 题型和读取权限是两个独立维度 |
| 原题原哈希复验 | 加提示、改题或删判官凑绿 | 修复必须作用于入口，不把训练答案混进测量 |
| 分开记录协议、核验和文本质量 | completed或render_from_claims等同成功 | 完整草稿仍可能未审核或未交付 |
| 独立新运行目录 | 覆盖旧observations或给旧收据换SHA | 每份证据只证明当次条件下的结果 |

## 验证与后续收据

- f1fd干净定向门禁：580 passed、4 skipped、0 failed，Ruff通过。收据 `~/.finance-runtime/knevo-absorption-20260923/material-repair-f1fd8aa1a/targeted/gate-WNGQ8erU/pytest.json`。
- 提交前886 passed、4 skipped是迭代证据，不标成f1fd干净全仓结果。
- 十二原题的装配探针证明合同/八问/指导投递与受测读取尝试0；不证明整回合所有IO为0，不证明答案正确。
- 新live原件位于上述 `material-repair-f1fd8aa1a/`，最终逐题检查写入 `observations.json`。该文件缺失时表示尚无完整汇总；`execution.json`的 `semantic_verdict=not_evaluated` 不是语义通过。
- 文档固定候选之后不再修改tracked文件；新工程门禁写入 `~/.finance-runtime/knevo-absorption-20260923/material-repair-closeout/`，完成后以 `current.json` 索引完整revision、tree、dirty、收据和逐叶退出码。本文不预写未完成的门禁结果。
- live加载的是f1fd，后续文档提交不是另一轮live；工程收据按其实际测试revision记录，禁止两者互相代签。

## 未关闭事项

判官协议失败尚缺原始返回与具体字段诊断，不能猜测某字段后放宽验证。逐句来源/缺项陈述、无效finish及漏答继续按原件分桶。Q18真实台账、空集、权限错误、用户身份隔离、跨轮继承仍不由材料代理题证明。未做独立审查、完整消融、胜率/top3或生产画像效果验证。

工具沉淀复用已有 `knevo_regression.inspect_run`、Workbench probe及门禁收据工具；本次增加真实装配回归，没有再建另一套评分器。失败语义仍需逐题阅读，不能用关键词计数代替。PR #877保持WIP，合main、部署、回补和生产画像写入仍需另行确认。
