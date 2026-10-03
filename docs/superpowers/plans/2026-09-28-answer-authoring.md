# Answer Authoring Implementation Plan

> 用户授权继续实现、评审、真实答卷验证与PR更新；本单不合并或部署。
> **09-29 执行状态**：实现及工程验收完成；自然回答质量仍不通过。勾选表示动作已执行，不表示内容达标。最终代码 `7c16a38ec`；本文件为后续文档，不移签测试收据。

**Goal:** 减少材料任务终稿的重复表示工作，并用实际答卷检验财务口径改进。

**Architecture:** 新作者格式编译到既有完整终稿；验证器继续拥有事实/权限判定；解析反馈定位错误。财务方法独立试验，不改授权或模型配置。

**Tech Stack:** Python 3.12、Episode/ResearchTaskContract、pytest；pytest/Ruff固定 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

## Task 1：紧凑作者协议与解析反馈 — 已执行

- [x] 最小历史合同、原始非法JSON拒收与位置反馈；正例保留direct_answer/evidence_boundary的不同标签。
- [x] 纯编译接口实际命名 `compile_material_author_finish(value, contract)`，位于 `intelligence/services/material_answer_authoring.py`；旧格式原样返回，新格式逐字段校验后生成完整终稿，不改写正文/来源/状态。
- [x] 冻结合同投影M/H短别名；schema、开场与修复共用来源；完整目录仍在合同和判官。
- [x] #819 `prior_evidence.entries` 非空时，开场/修复/finalizer/headless保持旧格式，真实恢复夹具验证零新工具与本轮E重映射，不改标工具事实或扩旧证据资格。
- [x] 新旧格式等价；未知别名、错类/伪来源、重复output、伪quote、多句、不合法字段反例；原始多余 `]` 仍拒，修正后才能进入来源检查。
- [x] 同Episode脚本模型先坏后好，既有预算/截止/取消边界不变；定向测试、Ruff及独立复核。
- [x] 续做：已知冻结来源错误摘录的有界修复 `220693df3`；全稿来源完整性优先 `11f7ce233`；独审发现非冻结检查重排回归后由 `7c16a38ec` 恢复逐binding顺序。有效红测/无效初始夹具/修后绿分别保留。

作者形状仍为：

```json
{"format":"material_claims_v1","status":"completed","answers":[{"output_id":"direct_answer","claims":[{"text":"上一条回答说收盘价为68.78元。","kind":"historical_assistant_statement","sources":[{"ref":"H1","quote":"68.78元"}]}]},{"output_id":"evidence_boundary","claims":[{"text":"本轮未重新核验。","kind":"premise_declaration","sources":[]}]}],"gaps":[]}
```

## Task 2：实际答卷与财务方法有界试验 — 动作已执行，质量未过

- [x] 冻结三臂：legacy `45f0ff860`、compact `09f408194`、method `be1d57cd9`；原题、历史种子、来源、授权、预算与实际模型对照存证。method历史未运行，不补样。
- [x] 财务调查、方法投递选择、新数值边界题及事前评价标准；新数值题来自已知错误家族，不声称完全未见。
- [x] FA-01单变量试验未达到内容保留条件，已撤回；`reading_baseline.py`与compact-only逐字相同，`FINANCE_RESEARCH_REASONING`继续关闭。
- [x] `220693df3` 真实Workbench五题各一次，0工具；公开交付与内部草稿分开。最后历史/消息未答，两财务有重要错误，比较可用。
- [x] 收尾只读19份冻结原件；旧匿名评审发生错配，撤销其验收效力。新五题独审一次：review-19哈希少一位拒收，review-18存在usable/partial分歧；原件与作者裁决保留，不重抽好评。
- [ ] **整体自然质量验收未通过**；没有在 `7c16a38ec` 上新增自然样本，不用旧答卷代签。

## Task 3：工程验收与可审查交付

- [x] 固定 `7c16a38ec`、机器资源准入后完整Python/Ruff；18,595P/74S/2X、0F/E，收集18,671；收据identity/完整范围校验通过。
- [x] 同SHA前端六项exit0（组件125P、E2E34P/2S）、注册表/ledger五项通过；非冻结回归第二次静态独审未发现阻断。
- [x] 生产健康/stat/端口只读快照；01:42生产为 `20d49970a15d`、clean/match，非本任务切换。8832—8837/本任务E2E端口无监听记录。
- [x] 代码已快进推送至#956原分支，WIP保持；验证报告/原件包/本分支≤3KB交接为本次文档交付。PR最新身份与发布动作以Gitea回读为准。
- [ ] 合流新main、合并、部署均未执行，须用户另行确认；7c工程收据不代表后续文档tip或新main组合。

## 证据与接手入口

- [正式报告](../../verification/2026-09-28-answer-capability-evaluation.md)：各revision收据、五题失败、独审分歧与生产时点。
- [选定原件包](../../verification/answer-capability-2026-09-29/README.md)：manifest索引66件原件（45件副本入库、21件日志仅树外），完整大日志仍在树外。
- [当前分支交接](../../handoffs/inflight/fix-8792-answer-closeout-0929.md)、[日期决策快照](../../handoffs/2026-09-29-8792-answer-closeout.md)。
