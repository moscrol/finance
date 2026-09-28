# Answer Authoring Implementation Plan

> **For agentic workers:** Use subagent-driven-development for bounded implementation, then spec review and code quality review. User has authorized continuation; execute without intermediate approval pauses.

**Goal:** 减少材料任务终稿的重复表示工作，并用实际答卷检验财务口径改进。

**Architecture:** 新作者格式编译到现有完整终稿，验证器继续拥有事实与权限判定；错误反馈指出解析位置。财务方法独立试验，不改取证授权或模型配置。

**Tech Stack:** Python 3.12、现有 Episode/ResearchTaskContract、pytest；固定解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

## Task 1：紧凑作者协议与解析反馈

文件：新增 `intelligence/services/material_answer_authoring.py`；修改 `material_grounding.py`、`episode_protocol.py`、`runtime/codex_headless_runtime.py` 的格式选择接缝。测试新增 `intelligence/tests/test_material_answer_authoring.py`，更新真实材料 prompt 及相关 headless 测试。

- [ ] 固定最小历史合同，先证明原始非法 JSON 被拒且反馈缺解析位置；正例保留绑定标签不同的 direct_answer/evidence_boundary。
- [ ] 实现纯编译接口 `compile_material_answer(value, contract)`：无新格式返回原对象，有新格式逐字段验证并生成完整终稿。具体作者形状：

```json
{"format":"material_claims_v1","status":"completed","answers":[{"output_id":"direct_answer","claims":[{"text":"上一条回答说收盘价为68.78元。","kind":"historical_assistant_statement","sources":[{"ref":"H1","quote":"68.78元"}]}]},{"output_id":"evidence_boundary","claims":[{"text":"本轮未重新核验。","kind":"premise_declaration","sources":[]}]}],"gaps":[]}
```

- [ ] 作者目录由冻结合同按顺序投影 M/H 别名；完整目录留在合同与判官。格式 schema、开场和修复模板共用同一来源。旧格式继续接受，非材料题不切换。
- [ ] 将新格式接入 validate_episode_finish，在现有完整校验之前编译；不修改来源准入判据。未知别名、跨来源类型、重复 output、伪 quote、多句及不合法字段分别有反例。合法新旧格式得到相同公开正文与完整 bindings。
- [ ] JSON 拒绝反馈提供错误位置，原坏稿仍拒绝；连续 Episode 以脚本模型先坏后好，验证修复看见位置且没有额外工具或预算。
- [ ] 定向测试、Ruff、提交指定文件；独立规格后质量复核，发现问题同轴复验。

## Task 2：实际答卷与财务方法有界试验

文件：树外本次新证据目录；如方法候选成立，单独修改现有方法所有者及其投递测试，不将财务路由/新授权混入。

- [ ] 冻结 Task 1 代码与健康身份，隔离侧车重跑原历史和原财务题，记录完整模型请求/答卷/判官/耗费；原失败不覆盖。
- [ ] 根据只读财务调查写出方法投递选择及新数值边界题，提前冻结评价标准。检查新格式是否已改善内容后再决定额外候选。
- [ ] 一次独立的方法差分试验，原题加新数值边界题；评价语义而非关键词/标题，不能通过默认放宽判官或增加预算。
- [ ] 无收益的候选撤回，不默认开启；保留实验记录。若保留代码，按规格→质量复审，适当回归后冻结。

## Task 3：工程验收与可审查交付

- [ ] 固定最终源码后检查机器资源，再跑完整 Python/Ruff 与需要的接口/前端检查；收据严格绑定 revision，不移签。
- [ ] 记录生产只读身份和数据范围，停止本任务侧车。
- [ ] 更新实际结果报告、产品入口、PR #956 描述、≤3KB 在途交接与记忆索引，推送分支。没有质量通过证据继续 WIP；合并部署需用户另行确认。
