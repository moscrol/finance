# 研究答案交付共用链：设计复核

复核日期：2026-09-20。只读候选，不调真实模型，不运行全量，不修改生产。解释器固定 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。使用 leila-runtime / codebase-design。主仓共享脏树未写；R6 的未提交验收文档只作近况参考，代码结论绑定提交。

## 固定身份与结论

| 路线 | 固定 tip | 关键已有能力 |
|---|---|---|
| 主干 | `4ace5ec2` | 既有唯一公开出口、材料交付复验；尚无本次比率复算/抄数/保稿新增模块 |
| q | `493824bb`，业务 `6fb37a6e` | a31 交付门 + 后续局部保留、比率角色/单位/对应关系修补 |
| 保稿 | `ce673a9f`，业务 `cdcbc5a8` | 顶层 draft 排版恢复、候选保留、批注、七类有限证据诊断；不含 R6 复算 |
| R6 | `d8d6196b` | R5/R6 财务复算、a31 交付门、49fd 发布屏障、20939 RAG 分帧；未含 q 后续语法修补/整枝保稿 |
| E2 / PR770 | `b1c1c29f`，业务 `df74042c` | claims 单次渲染、逐句材料回执、修复理由与成稿格式重述 |

`module-presence.json` 由 `git ls-tree` 生成，确认 q 没有 `financial_claim_checks.py`、`finish_candidate.py`、`evidence_claim_review.py`，不能把 q 当三线合流底座。代码地图 query 已执行，structure=stale；未在他人树 build，以下均按精确源码核对。

方向合理，值得保留：同任务原稿保留与准入分账；产物可展示与公式正确分账；来源身份/报告期/单位进入核验；最后公开文本再过门；判错后保留局部补修责任；修订沿原会话、绝对 deadline 与额度；发布等待匹配 message/artifact。这里不需要增加第二判官、第二预算或第二公开出口。

## 四个有证据的缺陷

1. **P1：R6 复算漏掉已被交付门承认的“含金量”别名。** `financial_claim_checks.py:28` 的 `_RATIO` 没有含金量，`calculation_ratio_gaps` 在 `:124` 直接跳过；而 `research_delivery_checks.py:74` 承认它。输入 706.91 / 445.17 ≈ 1.587955，产物写 9.999：命名“含金量”时复算/抄数两门都无 finding；同样产物命名“净现比”或“OCF/净利润”则复算拒绝。实际接线 `episode_verifier.py:328–357` 只在 financial_analysis 的 metric_evidence 调复算。证据 `r6-probe.json.formula_alias_cases`。这不是数值容差问题，是两套领域词表不同。

2. **P1：表头单位绕过比例值合同。** q 的 `research_delivery_checks.py:408` 只提取 `%/百分点`，遗漏 bp/基点；`:418` 允许单元格单位覆盖表头。`|报告期|含金量(bp)| ... |2026中报|1.588|` 与基点写法在 judge off、passed stub 两模式都 completed；同数字放单元格 `1.588bp` 则 q 正确 partial。R6 较旧模块连单元格 bp 也漏过。证据 `q-probe.json` / `r6-probe.json`。正确修法是识别并拒绝差值单位；不得按 1/10000 换算后认证。还须防非法表头被 `1.588倍` 单元格覆盖，以及计算产物列本身带非法单位。

3. **P1：R6 保留旧 a31，仍会把安全邻句一起删除。** R6 `research_delivery_checks.py:53–66` 返回整句范围，最后在 `episode_semantic_verifier.py:790` 删除。离线输入“收入为100亿元[E1]，查询为空，所以公司没有公告，利润为20亿元[E1]。”，R6 最终仅剩缺口提示；q 保住收入、利润和原引用。两模式一致。证据同上 `comma_neighbor`。因此“R6 已有 a31”只说明接过旧门，不能代替 q 后续修补；目前约 292 行新增/22 行删除差异，不宜作为首片无说明整文件覆盖。

4. **P2：保稿的存疑句进入批注，却未触发同会话修订。** 保稿 `episode_semantic_verifier.py:1457–1458` 的 claim_indexes 只来自七类有限检查，`:1556` 判官拒句及 `:1465` 机械 reasons 没合入最终 `:1603`。实际给真 verifier 注入确定性判官，拒绝“成交活跃说明盈利必然改善”，结果 partial/rejected、有原句批注，但 rejected_claim_indexes/gap_output_ids/missing_outputs/repair_output_ids 全空。adapter `continuous_turn_adapter.py:809–819` 的 while 为 false。证据 `preservation-feedback.json`；E2 的同名字段仍无写入点（`episode_semantic_verifier.py:552` 仅声明，adapter `:813` 消费），只把理由过桥并未闭环。下一片应以结构化存疑句身份驱动修订，不能从公开批注反解析。

## 不能机械合枝的设计冲突

保稿 `episode_semantic_verifier.py:1417` 明确质量发现没有删除权，R6 `:748` 与 `:790` 仍删句/删值。两者直接叠加，会先保留再被最终门删除。建议整合前把所有有限检查收敛为“原句/坐标、原因、来源、需重开的输出槽”的结果，渲染层只做安全清洗、局部标记/批注；保留原始稿，未解决不 completed。先统一这项行为合同，再迁移保稿，避免同时保留两种政策。

## 首个可实施切片

**从 `d8d6196b` 独立开树，只修“含金量别名 + 比率差值单位”。** 这样已有真实财务槽接线、发布屏障和 RAG 读取，不需要把 R6 新模块嫁到 q。

代码限定：

- `intelligence/services/financial_claim_checks.py`：统一有限比率别名；“含金量”进入既有复算。保持增长/差额列排除、主体与绑定约束。明确 bp/基点/百分点不能充当绝对比率产物，即使数值碰巧等于结果也返回 gap。
- `intelligence/services/research_delivery_checks.py`：表头、单元格、明确 prose 值槽共用有限单位识别；任一明确差值单位均不认证。禁止以单元格覆盖非法表头。识别失败不能误装无单位值。
- 回归放 `intelligence/tests/test_financial_r6_regressions.py`、`test_research_delivery_checks.py`，组合出口复验沿 `test_financial_delivery_integration.py`，不要另造测试运行器。

必须先红再绿的用例：

1. 同一输入链，含金量产物 9.999 → 仅 metric_evidence 重开、原始草稿/证据不改；正确 1.588 不误拒。用净现比/OCF净利润作同错对照。
2. 表头 bp、BP、基点、百分点，cell 数值恰与原比例相等 → partial + repair IDs + 原始输入列/邻句/引用保留；表头 bp + cell“1.588倍”同样拒绝。
3. 产物列“含金量(bp)”而 value=1.588 → gap；不转成 0.0001588 或新正确值。单元格/prose bp/基点同样不能因后缀未匹配而漏过。
4. 正常原比例/倍、158.8% 与声明精度四舍五入仍过；同比增长、收入列、未绑定、混合主体继续遵守原排除合同。判官 off 与显式 passed stub 两种都跑。

首片不吸收 q 整文件，不动保稿/E2/runtime，不把单位差值扩成可支持的数据类型。

## 后续最小整合顺序

1. 上述 R6 有界切片；冻结新代码及离线结果。
2. 移入 q a31 之后的局部保留/比率对应关系增量，保留 R6 的最终复算、repair debt、引用捕获；补 `calculation_value_unlocated` 的公开提示与修复原因（q verifier `:726`）。不要再次移入 a31/49fd/20939。
3. 按统一“保稿 + 批注 + 补修槽”合同移入保稿候选与有限诊断，修第4项修订信号；同时测试正常出口和异常恢复出口，不能把 safe remaining text 当任务完成。
4. 最后接 E2 单份 claims 渲染/逐句锚点/修复原因与格式重述，单独回放材料判官协议失败。保持材料私有坐标过滤与输出覆盖回执。
5. 在新组合固定 SHA 做有界真实会话前置；既往 R6/R3 0/4、保稿三个 not_passed、E2 判官异常均不翻案。本轮离线证据不构成自然质量/可合入/部署批准。

## 复核材料与证据

已读各树 inflight 及引用核心快照：q 的 09-18 data-readiness/delivery-guards、09-19 residue-repair；保稿 09-19 draft-claim-offline-repair；R6 09-18 financial-r6-repair/financial-delivery-integration、09-19 RAG inflight；E2 09-16 claim-rendering/judge-receipts、09-17 repair-feedback。最新失败记录仍分别指向自然抄数/公告推断、原稿格式与金融语义、R6四题和 E2 无效 judge tool call；未重新抽模型。

本目录两个 probe 均直接调用候选真函数、judge 仅确定性本地 stub，不运行服务器。共 24 个公开出口观察（两树各6输入×2模式）、3 个复算别名对照、2 个反馈链观察。它们是反例/对照记录，不宣称 pytest 通过或自然模型得分。
