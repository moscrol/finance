# 05｜用户价值测量与四周试点材料 · 进度

规格来源：`docs/superpowers/specs/2026-09-13-research-evolution/05-product-value-pilot.md`（分支 `docs/river-next-specs`，提交 `194241dd`）。总合同同目录 `README.md`。

## 任务 0（2026-09-13）

| 项 | 值 |
|---|---|
| 开工基线 | `gitea/main` = `5fb13a8c`（与总合同一致；fetch 后重新核对无新提交） |
| 工作树 / 分支 | `/Users/a77/fwp-wt-research-evolution-05` · `feat/research-evolution-05-product-value`，起步 0 个脏文件 |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（主树 venv，Python 3.12.13，pyyaml 6.0.3 可用） |
| 实际用户态根 | `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`；`userspace.users_dir()` 解析一致。**本轨代码不读它**，只接显式参数 |
| 主工作区脏改动 | 30 个他人未提交代码改动（river/moneyflow/mfs 等），未迁入 |
| 代码地图 | 主树 `ready n=22076 @b4a35fa`；本轮按精确文件与符号定位，未依赖地图 |

### 现有实现映射（只读，实测读过）

| 基线符号 | 位置 | 本轨如何用 |
|---|---|---|
| `RunStore.load_run / run_dir`，`Run.status / error / degrades / artifacts[].sha256 / user` | `intelligence/services/run_store.py:231-300, 578-615` | `RunStoreEvidenceReader` 只读解析真实 run：失败 run 无 report.json 仍可计失败；`run.user != owner` 判跨用户 |
| `verify_run_binding` 三档 | `intelligence/services/self_use_maturity.py:426-577` | **不复用其成功门**：失败 / 降级 run 必须入分母；只借「真实性 ≠ 成功性」的判据思想 |
| `SelfUseEvent.validated` 时区校验、`dedupe_events` 幂等 | 同上 `:103-199` | 事件时间必须带时区、同键去重的写法对齐 |
| `_token_usage_from_events` / `AgentUsage.input_tokens` | `intelligence/runtime/agent_episode.py:122-160` | 用量 ≠ 账单：`cost_item` 以 `quantity/unit` 记用量，缺 `rate_version` 时 `certainty=unknown` |
| `summarize_context_growth` 的 provenance 分层 | `intelligence/services/context_growth.py` | 「逐调用 / 运行 / 子任务」只选一层 → `coverage_scope` 最粗层去重 |
| `userspace.user_space(user).root` | `intelligence/userspace.py:120-143` | 生产落盘由 06 在 `root/research_evolution/` 做；本轨 CLI 只写显式 `--out-dir` |
| 门禁 | `scripts/layer_audit.py`、`check_unread_fields.py`、`check_path_literals.py` | 新模块全部落 `services/` + `eval/`，结构化 JSON 用字符串键 |

## 完成项（revision：基线 5fb13a8c + 本分支首个提交）

| 日期 | 单元 | 文件 | 检查 | 退出码 |
|---|---|---|---|---|
| 09-13 | 06 接线合同（先交） | `docs/research-pilots/research-evolution/06-integration-contract.md` | 人工核对 spec §3 表与 `contracts.EVENT_TYPES` 一致 | — |
| 09-13 | 合同常量 + 协议冻结 | `intelligence/services/product_value/{contracts,hashing,protocol}.py` | `test_product_value_cli.py::test_cli_freeze_template_then_reject_edits` | 0 |
| 09-13 | 事件校验 / 幂等 / 排序 | `intelligence/services/product_value/events.py` | `test_product_value_events.py`（27 条：时区、负区间、渠道白名单、跨 owner、同 ID 冲突、修订、乱序） | 0 |
| 09-13 | 只读证据解析器 | `intelligence/services/product_value/evidence.py` | `test_product_value_evidence.py`（真实 `RunStore`：失败无报告、跨 owner 不泄漏、产物哈希、状态冲突） | 0 |
| 09-13 | `measure_pair` | `intelligence/services/product_value/measure.py` | `test_product_value_measure.py`（32 条：暂停只扣预登记、并集、前端不覆盖、失败 / 降级入账、费用去重与缺口、同意、无效判定） | 0 |
| 09-13 | `summarize` | `intelligence/services/product_value/summarize.py` | `test_product_value_summarize.py`（22 条：确定性、synthetic 隔离、六对配对达标 / 变慢 / 质量降 / 严重错误 / 漏审 / 只留成功样本、主动复用、回检、续费与退款、成本、曝光不进指标） | 0 |
| 09-13 | 离线 CLI + Markdown | `intelligence/eval/product_value/{cli,render,__main__}.py` | `test_product_value_cli.py`（8 条，含夹具漂移守卫） | 0 |
| 09-13 | 夹具（synthetic）与 README | `intelligence/tests/product_value_fixtures.py` → `intelligence/tests/fixtures/research_evolution/05/` | `validate` accepted 69；`summarize` → pair-01 valid / pair-02 incomplete / pair-03 incomplete；engineering_complete / pending / unstarted | 0 |
| 09-13 | 四周试点材料 | `docs/research-pilots/research-evolution/`（协议模板、任务卡、评分表、邀请、同意、时间费用、访谈、团队证据包、总结模板） | 协议模板可被 `freeze` 冻结（测试覆盖） | 0 |

### 收据

- 本轨 5 个测试文件：`100 passed in 1.50s`（`.venv-workbench/bin/python -m pytest -q intelligence/tests/test_product_value_*.py`）
- 全量：`9640 passed, 77 skipped, 2 xfailed`，exit 0，583 s；收据 `~/.finance-runtime/test-receipts/20260913T065932Z-5fb13a8c.json`
- `ruff check .` 0；`scripts/layer_audit.py` 0；`scripts/check_unread_fields.py` 0（无新增未读字段）；`scripts/check_path_literals.py` 0
- 前端 / e2e / registry 未跑（本轨未改前端与注册表；合并前由集成人跑等价 CI）

### 三态自报

- engineering_complete：模块真实计算，合同 / 负例 / 边界通过，可由 06 调用。
- product_verified：**否**，需 06 接真实 UI/API。
- field_evidence：**pending**；commercial：**unstarted**（无外部参与者、无付款）。

## 下一步

1. 06：按 `06-integration-contract.md` 接 writer / 来源盖章 / `RunStoreEvidenceReader` 注入 / `due_rechecks` 供给；先在 ledger-map 登记四类台账。
2. 用户授权后：`freeze` 协议 → 招募 → 按 README 四周表执行；付款只在实际发生后按 `manual_import` 导入。
3. 合并前跑现役等价 CI（含 `intelligence/webapp` 的 lint/typecheck/test/build 与 e2e），合并 main 等用户确认。
