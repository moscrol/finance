# 8792 局部失败返修：工程通过，真实验收仍待重做

> 后续：固定 c481272e（业务同9655）的[四题真实复验](../2026-09-18-8792-boundary-retest/README.md)已完成，整体仍未通过。下文及 results.json 是本轮工程收口时的历史快照，不改写其“未复验/新调用0”口径。

**被验业务代码：`9655b16d37b95c9f16e201cf41811c2999e1c5bf`。未 push / PR / 合 main / 部署；没有新增真实模型调用。**

旧 `3faf64fb` 四首题的 `not_passed` 不改写。本轮证明 F3 记账崩溃、F1 解析边界与删句后输出完整性的工程路径，不代签模型答题质量、财务解释、时效、稳定性或费用。

- 原件 **R2**：`~/.finance-runtime/reviews/8792-boundary-repairs-20260918/`；`evidence-index.json` 封存131份文件，后续提交收据另入post-seal索引，不覆盖原封印。
- 旧封存 **R**：`~/.finance-runtime/reviews/8792-boundary-live-20260918/`；219 份封印文件逐项复核一致。
- [决策与首次失败](../../handoffs/2026-09-18-8792-local-failure-repairs.md) · [在途交接](../../handoffs/inflight/fix-8792-boundary-integration.md) · [机器摘要](results.json) · [旧真实验收](../2026-09-18-8792-boundary-live/README.md)。

## 修复与可证范围

| 问题 | 修改 | 已核 / 不外推 |
|---|---|---|
| F3 工具拒绝后整轮崩溃 | `research_progress.normalize_query` 在 JSON 投影时复制 Mapping；冻结实参不变，其他非 JSON 对象仍 TypeError | 原 durable 事件最后实参 `file:///nonexistent`；无 `query` 的只读参数在进展账 fallback 中引发 mappingproxy TypeError。URL 仍 invalid_query、不派发；另测 provider 假异常，同 episode 可继续，旧证据/绑定保留。不证明其他 manual mappingproxy 同源 |
| F1 下期关注吞后续段 | 本章节边界、粗体/编号/换行字段；日期和占位符不算条件 | 原 F1 缺条件，不登记；原阳性仍 1 条、due=2026-10-21；后续段即使有貌似合法条件也不吞。语法形状不等于金融语义 |
| 删坏条件后假完成 | 对语义核验后的公开答案重算表达缺件；同 session 有界补全并复验；未补齐 partial+缺口 | 双判官模式下，坏数字仍删，可信正文保留；合法定性修复可完成。纯表达补全工具额度为 0；未增加根预算 |
| 修复/复验异常丢旧答案 | 仅恢复同轮此前核验成功的公开稿，仍走统一 `session_projection.view`、公开脱敏与领域限制 | 不发布新但未核验的候选。无可信前稿/身份不符/结构或完整性拒绝/取消不恢复；原异常和恢复来源保留。恢复本身异常仍回原 fail-closed 路径 |

测试里的定性修复为脚本化答复，判官为固定替身；组合经过真实 semantic verifier 和 adapter，不是实际 GLM 质量证明。原输入重放只验 parser/进展投影，完整 loop 的失败反馈由另外的脚本化 Episode 测试承重。

## 固定 revision 工程收据

| 叶子 | `9655b16d` 结果 | R2 原件 |
|---|---|---|
| Python 全量 | **11677 passed / 0 failed / 81 skipped / 2 xfailed / 17 warnings**，696.78s | `pytest-9655b16d.log/.exit` |
| Ruff | exit 0 | `ruff-9655b16d.log/.exit` |
| 前端 lint/typecheck/test/build | 全过；107 tests | `frontend-9655b16d.log/.exit` |
| 浏览器 E2E | 34 passed / 2 skipped，约 1 分钟 | `e2e-9655b16d.log/.exit` |
| registry/catalog | 六命令 exit 0；crosswalk 98 warning，非 error | `registry-9655b16d.log/.exit` |
| 精确收据校验 | 八项通过，基座漂移 0（fetch 后 main=0a1cb8c4） | `receipt-check-9655b16d.log/.exit` |
| 原边界 QC | 15/15 | `qc-replay-9655b16d.json/.log/.exit` |

权威全量收据：`~/.finance-runtime/test-receipts/20260918T034028Z-9655b16d.json`，干净树、标准解释器、未绕依赖门。旧 a969 首轮 **1F/11676P** 保留，不能充当通过；更早 ed25 上 588P 是 dirty 定向补丁结果。

```sh
cd ~/fwp-wt-8792-boundary-integration
umask 022
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
env -i PATH="$PATH" HOME="$HOME" "$PY" -m ruff check .
env -i PATH="$PATH" HOME="$HOME" "$PY" -m pytest -q
# 必须用指定业务 revision 的收据，不能把后续 docs 头当成被验代码。
env -i PATH="$PATH" HOME="$HOME" "$PY" scripts/check_test_receipt.py \
  ~/.finance-runtime/test-receipts/20260918T034028Z-9655b16d.json \
  --expect-revision 9655b16d37b95c9f16e201cf41811c2999e1c5bf --base-drift-max 0
```

前端四命令：`pnpm lint && pnpm typecheck && pnpm test && pnpm build`。E2E 用隔离 fixture 用户/DB、8793/8795、空模型密钥、`FORESIGHT_LLM_KEYCHAIN=0`、独立 rejudge 路径；两项 skip 是仅 desktop 的研究进化绑定，不冒充覆盖。测试服务已退出，8828 未重启。

## 八类撤保护反证

运行 `scripts/review_probes/run_boundary_repair_mutations.py --output-dir <不存在的新目录>`。只在独立子进程内改函数，不改磁盘源码；每项必须是业务断言 exit 1，不能用加载错误/无测试充数。

| 撤掉的保护 | 最终预期失败数 |
|---|---:|
| 冻结映射 JSON 投影 | 3 |
| 清单章节结束边界 | 13 |
| 日期不充当条件 | 7 |
| 语义后完整性重算 | 2 |
| 保留旧核验稿 | 4 |
| 禁止全关 checkpoint 写口 | 2 |
| 数字条件门 | 2 |
| 登记 opt-out | 2 |

原件 `mutations-9655b16d/` 含各补丁、日志、exit 和源码 hash。旧日期/引用/请求身份回归也在本 revision 全量与原 QC 中通过；没有把上一轮七类反证说成本轮重新执行。

原输入重放：

```sh
env -i PATH="$PATH" HOME="$HOME" "$PY" scripts/review_probes/replay_boundary_failures.py \
  --live-root ~/.finance-runtime/reviews/8792-boundary-live-20260918 \
  --output /tmp/boundary-original-replay.json
```

该脚本拒绝输出到封存输入目录，禁 socket，checkpoint 只写临时目录，核原件前后 hash；本次 connect 尝试 0。F1 opt-out/授权均 0，原阳性 opt-out=0/授权=1、due 正确；F3 原 57 个事件的实参保持拒绝且进展 JSON 可序列化。不是重发旧题，也不是全量真实 verifier replay。

## 剩余边界与收尾

- 清单检查仍是启发式，不是任意 Markdown/中文语义解析器；显式指标/时间字段完整性不等于证据支持，隐式“中报”等节点沿用既有默认到期日。
- 最近两期报告跳过 Q1、用户截止日未传到 information_cutoff、失败用量丢失与五次判官 token 未知仍待独立修核；费用 unknown。
- 本轮真实 CLI 用户纠偏已写入 canonical 用户台账；未核下次 prompt 实际注入。不能复述成“所有生产用户文件零改动”。
- 生产只读 health 从 `runtime` 嵌套块核得 bf662e9310ff / dirty=false / code_matches_repo=true；最初错读顶层得到 null 的记录保留，后以 `production-health-runtime-corrected.json` 修正，不当部署事故。
- 原敏感扫描覆盖 130 个 R2 文本/完整改动源码文件，21 个文件/规则命中、103 个具体词形皆逐项核为 Python import/属性表达式。首次漏识两个长 import 的前缀，失败记录保留；`sensitive-scan-reviewed.json` 未决 0，只对原范围成立。
- 后续将文档提交也纳入扫描（152 文件）时，`.claude/lessons_learned.md` 一条旧记录命中疑似凭证字串；它已存在于 9655，不是本轮新增，仍不能按“历史已有”豁免。当前文件做单点脱敏，扫描记录只存 hash/位置、不存原值，见 R2 `post-seal-scan-initial.json`、`legacy-secret-redaction.json`。没有验证凭证或改 Git 历史；若为真实凭证，所有者仍需撤销/轮换，旧 Git 对象风险未消除。不把后续扫描问题藏回原131份封印。
- 新真实验收须先确认预算、revision、首题分母和所有条件写口；不得重发挑绿、擅改模型/判官、合 main 或切 8792。#770、RE06/#53、#56 与数据修复另线。共享记忆随后新增 `feat/research-answer-preservation` 在途工作，本轮未整合、不借其结论。
