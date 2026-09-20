# Financial Ratio Units Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在 R6 已接线的财务复算与最终正文检查中识别“含金量”，并阻止差值单位被认证为绝对比例。

**Architecture:** 沿现有 `calculation_ratio_gaps`、`financial_claim_mismatches`、`calculation_copy_findings` 三个有限检查入口修改，不加验证器、模型调用或预算。仍由既有 `verify_episode_outcome` 和 `SemanticEpisodeVerifier.verify` 出具局部缺口；归档草稿、证据和原始输入不改。

**Tech Stack:** Python `re` / `Decimal`；pytest；Ruff。解释器固定 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

---

设计已获协调者确认，依用户“先复核设计，然后推进”的授权顺序执行，不再等待二次设计确认。设计源：`/Users/a77/fwp-wt-research-closeout-0920/docs/superpowers/specs/2026-09-20-research-closeout-design-review.md`。基线固定 `d8d6196baebdb1108a81ae01466e9df6397dc4fc`，树 `/Users/a77/fwp-wt-financial-ratio-units-0920`。外部证据目录 `/Users/a77/.finance-runtime/reviews/research-closeout-20260920/financial-ratio-fix/`。

## 文件与边界

- `intelligence/services/financial_claim_checks.py`：有限比例别名、按已绑定同主体同报告期原始输入复算；差值单位形成缺口。
- `intelligence/services/research_delivery_checks.py`：从产物列、表头、单元格和明确正文值槽识别单位；任何明确差值单位均不能成为比例值。
- `intelligence/tests/test_financial_r6_regressions.py`：已有财务公共函数和结构出口行为。
- `intelligence/tests/test_research_delivery_checks.py`：已有抄数公共函数行为。
- `intelligence/tests/test_financial_delivery_integration.py`：真正语义出口在判官关闭与确定性通过两种模式下的局部缺口、引用、原件不变和修正清债。

支持无单位、倍、百分比，声明精度仍决定舍入。`bp/BP/bps`、基点、百分点/个百分点只判不适用，不除以 10000。不吸收 q 的约 292 行后续语法；不同报告期、多主体、无绑定、非比例列、同比/环比增长/变化列沿既有范围处理。

### Task 1: 含金量进入同一条财务复算链

- [x] 在 `test_financial_r6_regressions.py` 增补三个别名的同值对照，直接用已有财务证据夹具；已知正确 `0.132`，错误 `0.133`，同时用交付夹具独立检验 `706.91/445.17` 的产物 `9.999`。正文仅“2026中报含金量为0.133。”也必须拒绝，防止外层 financial 词面过滤架空新别名。

```python
assert calculation_ratio_gaps(evidence, (calc.content_hash,), subject="600519.SH")
assert financial_claim_mismatches(
    [{"index": 1, "text": "2026中报含金量为0.133。"}],
    inputs, tuple(item.content_hash for item in inputs), subject="300308",
) == (1,)
```

- [x] 跑新增测试，日志保存 `alias-red.log`，确认失败来自“含金量”漏检；原净现比/OCF别名通过。
- [x] `_RATIO` 加 `含金量`；正文 financial 前置判断使用同一 `_RATIO` 的识别结果。

```python
financial = bool(re.search(r"现金流|OCF|存货|净利润", text, re.I) or re.search(_RATIO, text, re.I))
```

- [x] 同一批断言转绿，保存 `alias-green.log`。

### Task 2: 单位进入列、表头、单元格、正文合同

- [x] 在两个现有测试模块补表头 `bp/BP/基点/百分点`，单元格 `1.588bp`，正文 `2026中报含金量为1.588bp`，产物列 `含金量(bp)`，以及表头 bp + 单元格倍的行为断言。非法单位统一期望 `calculation_value_unverified` 或财务 gap；无单位、倍、`158.8%`、增长列对照保留。

```python
draft = "| 报告期 | 含金量(bp) |\n|---|---|\n|2026中报|1.588倍|"
findings = calculation_copy_findings(draft, _financial_evidence())
assert len(findings) == 1
assert findings[0].code == "calculation_value_unverified"
assert "待核对" in remove_findings(draft, findings)
```

- [x] 跑新增单位断言保存 `units-red.log`，确认是无 finding 或错误认证导致失败。
- [x] 两模块各保留本地有限单位词面。交付模块统一 `_ratio_unit` 提取，差值单位优先；`failure_code` 先检查表头与值单位，再比较数值；产物差值列标记该报告期不可核验，不能被同期间另一好值覆盖。百分比产物仍除以 100 归一。

```python
_DELTA_UNIT = re.compile(r"百分点|基点|(?<![A-Za-z])bps?(?![A-Za-z])", re.I)
_RATIO_UNIT = r"个百分点|百分点|基点|bps?|百分比|%|倍"
```

- [x] 财务产物在已具同期间输入时检测差值单位形成 gap；正文正则接收可选括号单位和数值后缀，任一明确差值单位为不适用。保持非比例/变化列排除和原主体/报告期选择。
- [x] 同一批单位断言转绿，保存 `units-green.log`；不修改原外部探针。

### Task 3: 真出口、承重验证与交付

- [x] `test_financial_delivery_integration.py` 沿既有夹具构造单一 metric 槽，财务含金量错误复算在结构出口形成缺口；表格单位错误在语义出口仅替换坏格，保留 `706.91`、`445.17`、邻句与 `[E1]`，状态 `partial` 且既有 repair IDs 非空。修正值/单位后完整复验可清债。
- [x] 按 `off` / `llm` 两模式运行上述出口测试；`llm` 仅传本地 passed stub，禁止网络连接。
- [x] 运行三个改动测试模块及相邻 `test_financial_contracts_r5.py`、`test_financial_publication_integration.py`、`test_research_delivery_repair.py`、`test_frozen_research_delivery.py`；保存命令、退出码、SHA与源码 hash。不得并跑全量。

```sh
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_financial_r6_regressions.py intelligence/tests/test_research_delivery_checks.py intelligence/tests/test_financial_delivery_integration.py intelligence/tests/test_financial_contracts_r5.py intelligence/tests/test_financial_publication_integration.py intelligence/tests/test_research_delivery_repair.py intelligence/tests/test_frozen_research_delivery.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check intelligence/services/financial_claim_checks.py intelligence/services/research_delivery_checks.py intelligence/tests/test_financial_r6_regressions.py intelligence/tests/test_research_delivery_checks.py intelligence/tests/test_financial_delivery_integration.py
```

- [x] 用临时撤保护分别去掉含金量、表头差值优先与产物单位拒绝，原行为断言应失败；每次只撤一处，`finally` 恢复文件并核实 hash。证据外置 `mutation-*.log`。
- [x] `git diff --check`；只以 pathspec 提交上述五个文件和本计划。普通推送本补丁分支，禁止合 main / 强推。
- [x] 用 handoff skill 写 `docs/handoffs/inflight/fix-financial-ratio-units-0920.md`（≤3KB），写固定代码提交、红绿证据、验证范围、q 合流/独立复核/自然验收/完整门禁仍待办；文档单独 pathspec 提交并推送。

## 自审

三个预先确定的接缝覆盖设计中的复算、正文、公开交付。单位位置与覆盖优先关系均有行为反例，正常值与排除范围有对照；未加入网络、数据库、真实模型、预算、运行恢复或保稿政策修改。最终评审由协调者另派，本计划只含实施自审。
