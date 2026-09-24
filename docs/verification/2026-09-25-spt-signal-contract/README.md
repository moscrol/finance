# SPT 条件匹配：隔离候选验证（历史）

**后续已否决候选。** 先冻结的12项反例/对照中8项失败；同句不保证同主体/时点，词面命中不证明语义成立。`fa82a73ca` 已撤下运行时接线并拒绝实验字段，详见 [拒收与隔离报告](../2026-09-25-spt-contract-challenge/README.md)。以下3/3及597P保留为当时的有限结果，不再作为采纳此方案的依据。

本地日期 2026-09-25。用户指示「你按照最优方案推进」后，由 agent 采用原三题的风险/机会观察/审计弃权立场作为本分支候选标准。不是用户逐题签字，也不授权生产画像写入或部署。选择与局限见 [合同规格](../../superpowers/specs/2026-09-25-perspective-signal-contract.md)。不再以重复询问三项实现细节作为本分支推进前置。

## 结论

实现及候选先冻结在 `cd2116dbee1d249a779500a22a63b73b7fa74a22`，然后运行真实输入：

| 范围 | 风险题 | 机会题 | 边界题 |
|---|---|---|---|
| 当前真实画像，不增合同 | PASS / risk | FAIL / none | FAIL / none，不等于弃权 |
| 深拷贝中仅加原拟议边界 | PASS | FAIL / none | PASS / abstain |
| 深拷贝中加合同与边界 | PASS | PASS / opportunity | PASS / abstain |

候选 3/3 只说明这组已知题的确定性保真检查成立。机会是观察优先级，不是买卖指令；后续承接仍待验证。预演整体仍 `BLOCKED/exit 2`：不授正式验收、不写用户状态、不补正式考卷、不签 LLM 理解与金融质量。

原题未改，SHA256 仍 `6f627694b119109156d3cbdf52fe32382cdd52ec50ee2f3cbcee6e06d456e933`。画像仍 `01611ea02994286031603f5ecf126b937cbee69a4ddb70afbdf5c8b39e88b8da`，`honest_boundaries` 仍为 0，正式考卷仍不存在。画像、manifest、原文、候选及 patch 前后哈希一致。

只绑定 `opportunity_preferences` 中与 approved `pp-ed109ca9f818` 逐字对应的一个值。其既有审批只证明原规则有票据，不批准新增匹配合同或边界。来源 `pa-af47be9c26e3`；候选哈希 `80559b4f9efb094fa29683d35978b8d210b3014186e7d487620252ceeae8eb4a`。

## 实现范围

- 可选 `signal_match_rules` 要求五组条件同时成立，并设置反证；组内同义短语由候选显式列出，不做宽泛分词召回。
- 绑定值漂移/缺失、重复、结构错误直接报错；绑定规则不得绕回旧整句匹配。未配置规则保留旧逻辑，诚实边界仍优先。
- 只读预演额外核验 patch 身份/字段/内容/状态/原文引用；临时修改只在深拷贝。报告只留哈希、计数与状态。
- 这不是一般语义解析：跨句指代、隐含否定、双重否定、多个主体同句、时间转换与新措辞未解决。已有未配置规则的词面匹配限制也仍存在。
- 模型提示、Workbench/CLI 问答引擎、学习 patch 白名单均未改；旧审批追溯及旧画像质量结论不被本轮覆盖。

## 验证收据

`clean-targeted-receipt.json`：准确绑定 `cd2116dbee1d249a779500a22a63b73b7fa74a22`，干净树，16 个文件、无筛选、597 passed / 0 failed / 0 skipped。包括所有视角相关模块、每日框架解读及原审计/请求接线回归。Ruff、diff-check、提交钩子通过。不是全仓 Python、前端、E2E 或完整发布门禁。

三次进程内故障注入（不改磁盘源码）均抓红，见 `mutations.json`：去否定保护 7F；全部条件改任一条件 5F；跳过绑定/结构校验 15F。故障进程结束后完整定向重跑 597P，不能把故障收据当基线失败。原始收据位于 `~/.finance-runtime/test-receipts/`。

开发中一次新增测试字符串漏闭引号，pytest 在采集阶段报错；修正后重跑。本轮未因真实预演结果改题或改期望。

## 生产前置

01:09:12+08:00 只读 `GET /api/readiness` 返回 HTTP 503、`not_ready`、`missing_critical=["market_data_consistency"]`；本次 `rag_query_protocol=true`。单次成功不能解释/抹去 00:29 的检索协议失败。摘要见 `readiness-summary.json`。

原行情/Workbench owner 交接仍为数据 HOLD，日期、身份、字段和范围未闭合。本任务未恢复采集、补数、换库、建索引或部署；也未发新模型请求或真实问答质量考试。

## 重放

在本审计树中运行，预期退出码 2：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/preview_perspective_exam.py \
  --users-root /Users/a77/.local/share/finance-workbench/users --user linxiaoqi5111 \
  --proposal docs/verification/2026-09-25-spt-exam-proposal/proposal.json \
  --match-candidate docs/verification/2026-09-25-spt-signal-contract/candidate.json
```

后续：先独立检查合同是否忠于原文且未过拟合这道已知题；正式画像/考卷仍走各自批准与写入流程。模型验收等数据/发布/预算前置满足后按原 #76 工作台与 CLI 分验，不能把本候选 3/3 当放行令。合入另冻结最新候选、跑完整门禁并等用户确认。
