# 历史证据来源绑定前向集成（2026-09-21）

## 背景与范围

历史证据绑定片原先只存在于孤儿提交 `9fabd688f588377a429d494f83fd9d6c3775e64b` 和旧QC枝 `2c529cb171a4363a4446571f2ea232146bc12fc5`。本轮不改原作者树，不把它直接塞进#832；在#832前向合流候选 `a14005fc9a9d671d178da6fc91be9cb69ae67e77` 上新建 `feat/history-evidence-integration-0921`，提交 `a69b822b0`、`c827ed749`、`f90fd3dc3`。

目标是先修并核验：旧普通证据兼容恢复、历史来源身份、查询/授权重读同源哈希、跨页行身份、行内分块观察隔离、历史资格门与comparison-analog合同接缝。目标不是完成#793板块排序/同窗候选，也不是#794 Workbench按需展开/预算/取消，更不是自然金融质量或生产放行。

## 发现顺序与动作

1. 合流后普通旧证据因新增`history_provenance=None`被拒，旧存档也可能把历史身份降成普通证据；故把兼容范围收窄为“只缺这一个新增顶层字段的旧普通schema”，历史工具必须严格重建嵌套来源。
2. 对恢复值做严格类型、枚举、ref、行坐标、资格和无损JSON检查；历史卡再检查内容哈希、`internal_locator/result_ref`、`independent_key/query_id`。这证明内部一致性，不替RunStore证明原件真实性。
3. 真实query与授权reader产生同源行但detail键序/observations顺序不同；仅给hash JSON排序不够，必须在投影和分块前规范语义字段。
4. 原先每张块卡带整行observations，导致未展示数值获得引用支撑；改为每块只保留实际detail/features可见且精确相等的int/float，排除bool；行身份跨页稳定，`·块N`只负责公开卡区分。
5. verifier不能由可选provenance是否存在决定资格检查集合；在合同声明`allowed_history_operations`时，历史工具及带历史身份的卡统一进检查，缺身份/错算子/伪身份均拒绝。
6. 新增comparison-analog槽测试后发现夹具把所有槽都按事实证据绑定，误伤新增`comparison_assumptions`模型推理槽；改测试模型读取合同`grounding_mode`，未放宽生产校验，保留真实查询分支/假设变更反证。

## 方案与取舍

| 方案 | 评价 | 结果 |
|---|---|---|
| 所有旧证据缺字段都补None | 会吞未知schema，历史卡可失去来源 | 否决，仅允许一个新增可选字段缺失 |
| 只按hash排序外层JSON | detail键序仍会改变块边界/跨工具hash | 否决，先规范语义payload再分块 |
| 每块携带全行observations | 未展示数值会冒充当前卡支撑 | 否决，按块可见值过滤 |
| 看到provenance才检查资格 | 删除字段即可绕过门 | 否决，合同用途决定检查集合 |
| 用身份hash证明原件真实 | hash只能证明内部一致 | 否决，保留RunStore授权/归属作为来源责任点 |
| 把比较假设当历史事实 | 夹具假绿且模型推理槽被误判 | 否决，按`grounding_mode`区分 |
| 把新枝直接并进#832/main | 混淆主线和历史片验收范围 | 否决，另开WIP堆叠候选 |

## 验证与收据

固定干净代码 `f90fd3dc3ba10a9a00f7264f92d3ec959b2ba682`：

- 全量：`12635 passed / 87 skipped / 2 xfailed / 17 warnings`，0失败/错误，1178.14秒；
  2026-09-21T11:28:53.674761Z–11:48:44.705726Z，首尾同SHA、clean、identity_stable。
  收据`~/.finance-runtime/test-receipts/20260921T114832Z-f90fd3dc.json`，严格checker exit0，
  解释器、依赖指纹、基座漂移5≤5均匹配。相对a140多39P；87 skip和2 xfail名称、类型、理由完全相同，未缩分母。基座漂移门通过不代表执行过后续main的组合。
- 前端六步exit0：单测110P，E2E34P/2S；全仓Ruff/registry/backfill/views/ledger六项exit0。
- 集成focused 763P；最终历史定向v4 177P；八项内存撤保护均由正式行为断言捕获。上述是作者/工程证据，不是独立审查签字。
- 真实历史原件离线回放：225行、9页、累计905次卡恢复（含各页重复元数据，不是905独立样本）；特征全等、初查/授权reader同源行卡及重叠页哈希一致、原件未改、自然模型0次。真实JSON先复制进临时RunStore，只验临时store授权reader路径，不认证原始用户归属、模型自然引用或金融质量。

完整归档：`docs/verification/2026-09-21-history-evidence-integration/`；完整JUnit XML和源工件哈希在`EXTERNAL-SHA256SUMS`。本分支后续若有docs提交，不能把f90收据移签到docs tip。

## 当前状态与后续

固定代码f90已推；WIP #841已建立，以#832分支为diff基线，仅展示增量，不执行合入#832。#829保持WIP/open，评论5416留#841接替指针；原提交不改、不删原树、不自动关闭。工程通过，独立Spec/Quality尚未做，真实自然金融0会话，旧not_passed不变。归档随后以docs-only提交发布，收据不移签。

下一步：#841保持WIP并指向本快照；若要继续，先针对新冻结SHA复核历史来源真实性、#793/#794真实消费者，再确认有界独立复核/自然题范围及预算，分别签工程/独立/金融质量。不得因全量绿或离线回放合main、部署8792、写生产或自动补绑定数字。

## 工具沉淀

保护直接进入正式pytest生产消费者回归，八项撤保护已捕获；前端/收据/归档复用既有门禁工具，不另造框架。`mutate_history_integration.py`及真实原件replay作为版本绑定的审计原件归档为`.py.txt`，不是通用运行入口；其有效行为已由正式query→reader→账本/恢复/公开引用测试承担。共享方法回写`gate-covers-only-its-return-value`：资格检查由必需类型决定，身份规范化须早于分块，分块证据不能借用未展示的整行值。
