# 资源预设与局部分数比较：不按模型强弱分配语义权

2026-10-02，第20号的修正候选；基座 `feat/harness-opt-1001@19c820824`。
本页取代第20号原“frontier 才放开语义策略 + PASS/WARN 闸门”的设计；尚未合并或部署。

## 1. 目标与边界

目标是让弱模型发挥好、强模型有更好发挥空间，不是弱模型靠硬规则追强模型。
权限、来源身份与硬预算必须守住；对题意的判断可能错，不应按强弱标签分配修订权。
本次只是撤掉第20号新增的档位差别，**旧 Controller 硬路由仍在，通用可修订路由尚未实现**。
不根据模型名称自动选档，也不把两个 GLM 型号当已标定的强弱组合。

## 2. 显式资源配置及实际消费者

`FWP_RESOURCE_PROFILE=standard|expanded` 对任何模型都可显式选用。无此配置时，旧
`FWP_MODEL_PROFILE=standard|economy|frontier` 仅作资源兼容：前两者映射 standard，
frontier 映射 expanded。旧名字不再决定策略，未消费的 escalation 身份已移除。
新配置只要存在就优先；空值/未知值回退 standard，**不再落入旧 frontier 配置**。

| 消费路径 | standard | expanded | 边界 |
|---|---:|---:|---|
| `agent_research.max_steps` 旧循环默认步数 | 4 | 8 | 显式 `ASK_AGENT_MAX_STEPS` 仍优先，不是 Workbench Episode |
| `kb_rag.evidence_budget_for_query` 字符预算及封顶 | ×1.0 / 8000 | ×1.5 / 12000 | 只是预算；更多字符不保证更多有效证据或更好答案 |
| `turn_controller` 语义策略 | 共用 | 共用 | 不消费资源 profile；仅撤销第20号新增分权 |
| Workbench `episode_factory` / `ContinuousAgentEpisode` | research tier 决定 | research tier 决定 | 本次不新增 profile 接线，不扩大 Episode 预算或权限 |

资源差异也是实验变量。研究通用工具接口时固定资源，不把“给新版更多预算”当接口收益。
本次不新增生产产品门；入口与引擎区分见 `docs/agent-product-door.md`。

## 3. `harness_tier_gate.py` 现在只做局部比较

名称与四个历史 CLI 参数保留以方便迁移，但 weak/strong 仅是配置 A/B 标签，不能认证强弱。
输入仅支持显式非空 `{"cases":{"case-id":true}}`。旧 summary 抹掉了通过题号，
同题数不能证明同题集；即使计数自洽也拒收，不再按当前题集补猜。带
`total/passed/failures/by_class/pass_rate` 的汇总或混合报告一律报输入错误。
四臂必须有同一组显式题号；布尔值不能由字符串/数字强制转换；重复 JSON 键拒收。
题号相同仍不证明题面内容、模型身份、同数据同预算、未见题、完整答案、来源保真、成本或延迟。

迁移须从原始逐题答卷重新判分：`content_correctness_eval.py score --cases-json`。
漏答仍记 false；逐题导出拒绝陌生/重复/空题号、非对象行、非字符串答案、重复 JSON 键
或坏 JSON，exit 2 且不输出报告，避免把身份丢失挪到导出端。空答卷保留全题 false。
旧 `--json` 汇总展示不变，仍可展示 `unknown_case_ids`，但不是比较器输入。
没有原答卷/逐题记录时保留缺证据，不能把旧汇总自动转换成“可信配对”，
也不因格式迁移重发真实模型请求。

| 输出 | 含义 | `check` 退出码 |
|---|---|---:|
| FAIL | 任一配置至少一题已见回退；净分提升不能抵消。也不自动证明回退因果 | 1 |
| INCONCLUSIVE | 没见回退，可列出分数提升，但通用收益没有被本脚本验收 | 3 |
| 输入错误 | 缺失/空/错误类型/重复键/题号不一致/任何 summary 或混合报告 | 2 |

**不再输出 PASS/WARN，不再把“没有提升”用 exit 0 放行。两边都涨分仍为 INCONCLUSIVE。**
不建议“只给弱模型启用”绕过回退。`selftest` 的 exit 0 只表示软件自检通过，绝不是模型评测。
这是故意收紧的退出码合同；调用方须区分 exit 1/2/3，不能把非 FAIL 都当通过。

```bash
# 用原答卷生成一臂的显式结果；其余三臂同样处理，保持题集版本一致。
python scripts/content_correctness_eval.py score --answers answers-a-before.jsonl --cases-json > config-a-before.json
python scripts/harness_tier_gate.py selftest
python scripts/harness_tier_gate.py check \
  --weak-base config-a-before.json --weak-new config-a-after.json \
  --strong-base config-b-before.json --strong-new config-b-after.json --json
```

## 4. 下一阶段才研究通用界面与行为收益

- 一次只变一种通用接口：简短目录、按需完整 schema（参数说明）、可展开其它已授权能力。
  不按题型永久藏工具，也不把更宽的语义权只交给所谓强模型。
- 合并工具先证职责、来源、权限和返回合同重叠；历史空结果不能单独证明该删。
- 同模型同题同数据、可比资源对照；保留未调试题和“信息已够无需额外工具”的控制题。
- 记录渐进展开多出来的往返与费用；检查完整答案、来源保真、完成/恢复及同质量效率。
  强侧不退步只是底线，不是收益。不能用全量绿、档位名或布尔分数替代行为验收。
- 正式“模型 × 薄 ReAct / 完整 8792”四格先于240题扩量；缺的模型臂明示未验证。

本工程批次 R-20261002-12 真实模型请求帽0；下一接口候选与模型对照单独冻结。
启动预测与结果分开保存：`docs/verification/2026-10-02-resource-profile-contract.md`、
`docs/verification/2026-10-02-resource-profile-contract-results.md`。
