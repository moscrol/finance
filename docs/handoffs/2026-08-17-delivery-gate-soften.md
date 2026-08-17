# 交接：交付门禁改力度（claim/术语不整答退稿）

- 日期：2026-08-17
- 树：`/Users/a77/fwp-wt-delivery-gate`
- 分支：`fix/delivery-gate-soften`
- 基线：`gitea/main` `dd9f10b9`
- spec：`docs/superpowers/specs/2026-08-17-delivery-gate-soften-design.md`
- 代码：`2ed2fbb9`
- PR：**#144** http://127.0.0.1:3300/a77/finance-workspace-private/pulls/144 （open，mergeable，未合）

## 0. 一句话

防幻觉还记账、还抠问题行，**默认不再因为没绑 claim 或漏了内部词把整篇 LLM 答卷丢掉。** 数字血缘只删未核验句，**不再改写** `stop_reason`。两发 live：答卷都在，绑定警告都在，8792 未动。

## 1. 改了什么

| 闸 | 现在 |
|---|---|
| claim 绑定（`llm_missing_claim_binding` 等 6 个码） | `warning`，合成链不退稿；无效 ID 行展示层丢掉，无 marker 句子留下 |
| `llm_engineering_term_leak` / `grounded_composer_engineering_term_leak` | `warning`，展示层抠含漏词的行 |
| 数字血缘（benchmark `_numeric_lineage_projection`） | 只删 `material_numeric` 且无 `source_ids` 的句；删光才用缺口稿；**禁止**把臂级 `stop_reason` 改成 `numeric_lineage_gap`（仍写 `issues`） |
| **展示层抠空**（复核时补，`dd494133`） | 抠成空串 → 退稿，不发空白稿。旧合成链走 `quality_gate_rejected` + `reason_code=presentation_emptied`；WARN 回灌修订抠空则保留初稿 |
| `llm_added_number` 等仍是 `error` 的 | 不动，仍整答退稿 |
| 语义闸、休市/退役表罐头、结构 verifier、层级审计、未读字段 | 不动 |
| 市场复盘 `grounded_required_fallback` | 不动 |
| 超时 / 8792 / 900 | 未切、未开 |

入口：`intelligence/services/answer_model.py`、`ask_synthesis.py`（警告写入 `result.warnings`）、`scripts/run_agent_runtime_benchmark.py`。

## 2. 怎么验的

相关单测 206 绿（`test_answer_model` / `test_p0_hardening` / `test_answer_orchestrator` / `test_run_agent_runtime_benchmark` 等）。

两发 live，Provider `gpt-5.6-terra` @ `x.ailzd.com`，`FORESIGHT_LLM_KEYCHAIN=0`，`WORKBENCH_GROUNDED_PRESENTER=0`（专门走刚改的合成门禁，不是默认 Grounded Presenter）。

| 发 | 题 | 检索 | 答卷 | 退稿 | 绑定警告 | 8792 |
|---|---|---|---|---|---|---|
| 薄证据 | `2026-07-23 今天市场怎么样` | 关模块/RAG | 475 字 | 否 | 有（3 行未绑） | `model_load_count=1` |
| 带检索 | `人形机器人还能追吗` | 开模块 + wiki RAG | 1237 字，题材「机器人」，31 条引用 | 否 | 有（6 行未绑） | 仍 1 |

收据：

- `~/.finance-runtime/delivery-gate-soften-20260817/live-ask-a1.json`
- `~/.finance-runtime/delivery-gate-soften-20260817/live-ask-retrieval.json`

n=1，不读快慢。带检索那发 wiki-rag 有一条「约 2.2s 跳过」警告，W 引用仍出现。

### 2.1 复核补充（2026-08-17，`dd494133`）

两发 live 的 `structured_claim_count` 都是 **0**——模型没出 marker。所以 live 只压到
三项放松里最轻的一项（未绑定散文照发）；**无效 claim ID 抠行、术语抠行 live 没碰过**，
那两项只有单测覆盖。别把「两发都没退稿」读成「三个闸都验过了」。

复核发现并已修：展示层抠空能发空白答卷（详见 spec §1.4）。三条守卫都做了变异测试，
抽掉即红：

| 变异 | 变红的测试 |
|---|---|
| `ask_synthesis` 抠空守卫改 `if False` | `test_presentation_emptied_answer_is_rejected_not_published` |
| `ask.py` 抠空守卫改 `if False` | `test_emptied_revision_keeps_the_draft` |
| `ask.py` 抠空守卫改 `if True`（假门禁形状） | `test_nonempty_revision_replaces_the_draft` |

收据：`intelligence/tests` 全量 **4766 passed / 11 skipped / 0 failed**
（`~/.finance-runtime/test-receipts/20260817T072959Z-dd494133.json`，clean tree）。
另注：交接页原写的「206 绿」那份收据是 `dirty: True @ dd9f10b9`（测的是未提交工作树），
已在 clean `9ffae56f` 补跑同一目标集 206 绿（`20260817T071658Z-9ffae56f.json`）。

## 3. 合进去会怎样

生产默认仍是 `WORKBENCH_GROUNDED_PRESENTER=1`。合入后：

- Grounded 成功：走影子成文；术语泄漏改为抠行，不再因漏词整篇 `deterministic_gate_rejected`（`added_number` / 越界公司仍 error）。
- Grounded 失败且落到旧合成链：未绑定散文会出答卷 + 警告，不再 `quality_gate_rejected`。
- 评测臂：repair 恢复率不再被血缘闸改写 `stop_reason` 吃掉。

## 4. 同日未并进本 PR 的事

T-F 摘接（Scope+工具阶段）工程门红，结论 **摘不干净**，5×5 未开。臂 1 树 `/Users/a77/fwp-wt-tf-arm-1-subset` 11 路 staged 未提交（`unread-fields` 读者在禁止的 `glm_agent_runtime.py`）。读数页 `docs/handoffs/2026-08-17-tf-subset-attach-readings.md` 在 `/Users/a77/fwp-wt-tf-readings` `a45a9fe3`，**当时未 push**。不要把摘接树推进本分支。

## 5. 下一任不要做的

- 不要开 900、不要切 8792、不要动 T / 档位 / `ASK_TOOL_BATCH_TIMEOUT`。
- 不要把 `llm_added_number` 也改成 warning（未授权）。
- 不要把未读字段钩子 `--no-verify` 拿去提交臂 1 摘接。
- 不要把 n=1 live 写成「更快」或「吸收兑现」。

下一动：批合 **#144**；或先审 diff。T-F 下一块仍是 Handle+§9.2 或改判形状价值，别再开 Profile/stub 5×5。
