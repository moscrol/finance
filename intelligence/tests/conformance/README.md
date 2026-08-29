# 运行时后端契约符合性套件

一套夹具 × N 个后端：同一契约场景（脚本化模型 + 契约 + 注册表）逐后端跑，
让「行为静默缺席」从只能靠人读代码发现，变成 CI 里显式的红 / 绿 / 声明不支持。
零网络、零真实 LLM、零生产代码依赖。

来源工单：`docs/superpowers/specs/2026-08-29-runtime-conformance-suite-workorder.md`；
能力声明初值：`~/Developer/career-ops/interview-prep/runtime-factory-audit-2026-08-29.md`
（后端 × 不变量核查表，2026-08-29）。

## 结构（三件分离）

| 文件 | 是什么 |
|---|---|
| `backends.py` | **参数表 + 能力声明表**：5 个后端（4 个工厂注册 + `dsh_stub` 协议参照桩）各一行 `BackendDescriptor`；每个不变量声明 `SUPPORTED / REDUCED / UNSUPPORTED_EXPLICIT / UNSUPPORTED_DECLARED / NOT_APPLICABLE`，非 SUPPORTED 必须带理由（构造器强制）。统一驱动器把后端无关的 `ScriptedTurn` 场景翻译成各后端真实输入形状。 |
| `fixtures.py` | 脚本化模型三件（`ScriptedModelClient` / `ScriptedSdkRunner` / `ScriptedFakeCodex`，复用既有 doubles 的驱动面）+ frame/context/registry 夹具 + 通用断言辅助。 |
| `baseline.py` | **棘轮 baseline**：存量红登记在案（带原因与日期），`ratchet()` 转 strict xfail。 |
| `test_inv1..8_*.py` | 每个不变量一个文件，`@pytest.mark.parametrize` 逐后端跑。 |

跑法：

```bash
.venv-workbench/bin/python -m pytest intelligence/tests/conformance/ -q
```

## 声明语义（判据，资产的一半）

- **SUPPORTED**：行为断言必须绿。
- **REDUCED**：后端自带缩减版语义，按它自己声明的形状断言（例：SDK 档的
  INV-3 只扣 verifier/delivery 小窗，合成保底归 adapter 层且给零）。
- **UNSUPPORTED_EXPLICIT**：声明不支持，且**链路上游照跑、缺席是隐形的**
  → 必须在运行时可观测面（事件 / gap / stop_reason）显式报告不支持；
  静默跳过判红。INV-5 codex 即此类——判官照跑、修复静默消失，这条红是
  套件有效性的**阳性对照**，长期以 baseline xfail 存在。
- **UNSUPPORTED_DECLARED**：机制整体不在场（装配层从未接入）→ 声明表本身
  即显式化；断言只验证「确实不在场」，防止有人加了机制却不改声明表
  （加了会红，逼人先改声明）。
- **NOT_APPLICABLE**：该不变量对此后端无意义 → 显式 skip，理由必须写在
  `notes`（构造器强制），不是静默跳过。

区分 EXPLICIT / DECLARED 的判据：**上游是否照跑**。判官跑了、修复消失，
事后分诊看到的是「给了缺口然后什么都没发生」——这种半途静默必须有运行时
收据；而 codex 没有 reserve 机制这种「整体不在场」，声明表 + 存在性断言足够。

## 棘轮 baseline 怎么用

规则（`baseline.py`）：

- 红且在 baseline → strict xfail（不阻塞合并）；
- 红且不在 → 正常 fail（新回归当场处理，不许静默入账）；
- 绿但在 baseline → XPASS 报错（strict=True 逼人删行清账）。

清账：缺口修复后跑套件，对应条目会以 `XPASS(strict)` 失败 → 从
`BASELINE` 删那一行即完成清账。**baseline 只许缩不许涨**：新增红条目
意味着行为回归，先修行为，不要往表里加行。

## 怎么加新后端

1. 在 `fixtures.py` 加一个脚本化替身（实现该后端的模型/执行器注入缝，
   参考三个现成替身；关键是把 `ScriptedTurn` 翻译成后端输入、把可见工具
   面与真实执行记进 `ScenarioProbe`）。
2. 在 `backends.py` 加 driver + `BackendDescriptor` 一行，逐不变量声明。
3. **新后端必须全绿**：不得往 `baseline.py` 加行；声明 `NOT_APPLICABLE` /
   `UNSUPPORTED_*` 必须带代码出处理由。

## 能力声明表怎么改

声明表与代码不符时**以代码为准**：改 `backends.py` 里对应格的 verdict 与
note（写清代码出处），同步回写核查表
（`runtime-factory-audit-2026-08-29.md`）。已知的收据词表差异记录在各
测试文件注释里（例：预算收工码 continuous/sdk 是 `tool_budget_exhausted` /
`root_budget_exhausted`，codex/stub 网关是 `research_stage_closed` +
finalization 事件——语义相同、词表不同，是差异不是缺口）。

## 首轮执行结果（2026-08-29）

`43 passed, 3 skipped, 1 xfailed`。skip 均为声明 N/A（stub 无模型窗/不产
FINAL_JSON）；xfail 即 INV-5 codex 阳性对照。INV-4 取消语义工单标注
「待实测」，实测结论：五后端起跑前取消全部如实（`stop_reason=cancelled`、
零 registry 触碰），批次层执行前取消全部 `rejected/cancelled` 零派发——
声明为 SUPPORTED 全绿。
