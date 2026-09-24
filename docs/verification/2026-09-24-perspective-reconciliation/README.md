# 视角差异对账与既有考卷

2026-09-24 第三轮，只读真实账户 `linxiaoqi5111`。前两轮见相邻 `architecture-audit/` 与 `architecture-consumption/`。未调用新模型、改用户画像、补生产数据、换库、部署或重建索引。

## 结论分层

| 验收对象 | 风远 | SPT | 适用范围 |
|---|---|---|---|
| 当前四个 patch 管理字段进入离线上下文 | PASS，147/147 | PASS，92/92 | 不包含手工框架字段，不证明批准权属或模型采用 |
| 历史 approved patch 值与当前画像一致 | FAIL，95/105 | PASS，92/92 | 风远十条存在后续改写，不能读成十条方法丢失 |
| 已有确定性考卷 | PASS，2 道已知题 + 1 道边题 | FAIL，无考卷 | 不调模型；已知题不是未见题或金融效果证明 |
| 用户原始授权、全部手工条目来源 | UNKNOWN | UNKNOWN | 旧交接记载授权，不等于本轮核验了原始授权对话 |
| 当前真实 Episode / CLI 回答质量 | BLOCKED | BLOCKED | 数据、发布及 #76 预算前置仍未闭合 |

`--check-exam` 下两份审计报告均 exit 1：风远因历史值漂移；SPT 因缺考卷。上轮 SPT 的 PASS 仅包含原文/补丁/离线上下文，不含考卷，本轮不是将旧收据改判。保留严格失败，不用相似文本自动批准。

## 风远十条差异

对照当前字段逐条阅读，七条去掉未标定数字，三条改写措辞；两类均与 `docs/handoffs/2026-08-28-fengyuan-spt-closeout.md` §2 的历史决策一致。该文还明确：考卷因全量扫描 anti/falsify 字段而命中禁语，改措辞后才通过。因此这三题是已暴露回归题，不能充当独立效果验证。

下表索引从 **0** 开始，绑定 `fengyuan.json` 中画像 SHA-256。每项批准原值及最多三个同字段候选均只存哈希；相似度仅用于定位，最相似项可能错误，不是替代审批记录。

| patch_id | 当前字段及索引 | 人工对账解释 |
|---|---|---|
| pp-0707f95b992a | risk_triggers[14] | 领先月数改为待标定 |
| pp-1a31434f7207 | risk_triggers[16] | 连续周数/季度数改为待标定 |
| pp-3475c68f9308 | opportunity_preferences[6] | 比例改为定性档位、比例待标定 |
| pp-7574978407b8 | falsification_style[16] | 交易动作措辞调整 |
| pp-96dd6c16d908 | anti_patterns[12] | 安全边际/回撤数字改为定性关系 |
| pp-bcaed8dc7640 | anti_patterns[22] | 提高仓位/解除冻结措辞调整 |
| pp-d5bd29548268 | anti_patterns[20] | 交易动作措辞调整 |
| pp-e3cc57aec091 | opportunity_preferences[9] | 回撤幅度/时长改为待标定 |
| pp-f1549d439c69 | risk_triggers[24] | 筹码厚度分档改为待标定 |
| pp-f3e6a8a79cba | risk_triggers[11] | 提前天数改为待标定 |

历史来源足以解释改写意图，但目前没有逐 patch 的替代/撤回事件把旧值与新值连接起来。保留 FAIL 表示记录一致性未闭合，不建议重新应用旧值或为此重新抓文章。

## 52 条无当前 approved 票据的值

- 十条是上表对应的改写候选；余下 42 条仍需分别追溯，不能统称非法注入、rejected 泄漏或新规则。
- `docs/fengyuan-distill-0916@0ed7709d6e3c76837a998aaea1419aa86b21df4b` 的交接记载四批共 14 条人工写入、七张策展字段卡手编、用户授权 agent 终审。该分支可从本地/Gitea 跟踪引用读取；本轮所见 `gitea/main@03af215e092cf0da25f3c7e8f60256cb60c2836e` 不含 `1afbfbe484aac3727611c19facc26b0a3f5a8737`。
- 四份私人 `review-policy{,-batch2,-batch3,-batch4}.md` 实际存在，先前 pending 段后附裁决落地段；不能截取旧 pending 当最终状态。`policy-matches.json` 保存四文件哈希及当前画像的 **4 条**去空白后逐字匹配，不保存私人句子。14 是历史交接记载量，4 是本轮字面核验量，两者不可互换。
- Q-002 #12-#30 在上述未合分支的 `evolution/backtest-queue.md`，不是从未登记。当前主干只有 #1-#11；不在本轮审计中重编号、重建队列或替 owner 合并。
- 08-28 文档四字段合计 98 条、当时批准补丁 70 条，与 09-16 增量可在数量上相容；数量相容不能证明其余条目的逐条来源。

## 工具与保护

`verify_perspective_consumption.py` 新增当前画像装配单独读数、同字段漂移候选、`--check-exam`。复用现有 `perspective_exam.run_exam`，缺卷/空卷/不足/失败均不得通过。考卷输入加入前后哈希核验；原本不存在的考卷中途出现也拒收。报告不保存考卷题面、画像规则正文或评分展开，失败原因仅留计数/哈希。

新反例覆盖：相似度不能批准改写、无候选仍失败、缺卷、通过且只读、考卷中途新建/修改、考卷失败隐私、人工规则漏装配及泄漏至 neutral。162 项定向回归通过，未跑全量发布门禁；干净树收据另附，不将脏树执行的 HEAD 当实现身份。

## 生产复查

`readiness.json` / `readiness-http.txt` 为本轮只读 GET。HTTP 503，`missing_critical=[market_data_consistency]`。健康接口或离线视角装配通过不能抵消该生产阻塞。行情、KB、卖方、Knevo 仍由原 owner 推进，未代签其工单。

## 复现

在审计工作树执行；每次输入都可能变化，不能移用本轮收据。

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
USERS=/Users/a77/.local/share/finance-workbench/users
"$PY" scripts/verify_perspective_consumption.py --users-root "$USERS" --user linxiaoqi5111 --perspective fengyuan --query '风远如何判断行情退潮和亏钱效应，什么条件下应降低仓位？' --check-exam
"$PY" scripts/verify_perspective_consumption.py --users-root "$USERS" --user linxiaoqi5111 --perspective sptfei --query 'SPT如何判断主线强度和分歧转一致，出现什么信号应证伪？' --check-exam
"$PY" -m pytest -q tests/test_verify_briefing_consumption.py tests/test_verify_perspective_consumption.py tests/test_daily_ops_ledger.py intelligence/tests/test_rag_readiness.py intelligence/tests/test_perspective_lab.py intelligence/tests/test_perspective_learning.py intelligence/tests/test_userspace.py intelligence/tests/test_perspective_exam.py
git show 0ed7709d6e3c76837a998aaea1419aa86b21df4b:docs/handoffs/inflight/docs-fengyuan-distill-0916.md
git show 1afbfbe484aac3727611c19facc26b0a3f5a8737:evolution/backtest-queue.md
```

`policy-matches.json` 算法：复用 `learning.list_patches` 和 `_norm`，在四字段中筛掉已有 approved 等值票据的值，将剩余值逐条与四份 policy 全文作去空白子串匹配，保存字段、0-based 索引、规则哈希和来源路径/哈希。匹配仅证明文字存在，不证明它位于批准段。政策文件读取前后字节一致；画像哈希与 `fengyuan.json` 相同。该一次性对账不是第二份审批台账。

## 后续

1. 原 Perspective owner 将修订记录与旧 patch 链接；处理未合入文档。既有终审不因本次审计缺机器票据而自动失效，也不由审计器替代确认。
2. SPT 如开展验收，需独立冻结考卷及未见题，不能从当前画像直接生成答案再证明自身正确。
3. 数据/发布/预算前置满足后再跑真实 Episode 和 CLI，分别核对实际采用、边界及回答质量。阶段 B/C/D 仍未完成。
