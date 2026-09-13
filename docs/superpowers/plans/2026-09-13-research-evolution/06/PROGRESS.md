# 06 · Workbench 集成与验收 · 进度（换会话先读这里）

> 总合同 `docs/superpowers/specs/2026-09-13-research-evolution/README.md`，本轨 spec 同目录 `06-workbench-integration.md`
> （规格提交 `194241dd`，规格交接 `28804505`，分支 `docs/river-next-specs`，本组合分支已合入）。
> 跨轨缺陷写同目录 `BLOCKED.md`。

## 任务 0 · 开工登记（2026-09-13）

| 项 | 值 |
|---|---|
| 工作树 / 分支 | `/Users/a77/fwp-wt-research-evolution-06` · `feat/research-evolution-06-workbench` |
| 代码基线 | `gitea/main` = `631786ab362f4c2118f65b6a1373ccddb7b0271d`（比总合同所记 `5fb13a8c` 新 3 个合并；重新 fetch 后核对） |
| 组合基底 | `5f931258032c259062edcb3357b0df4d821517c3` = 基线 + 依次 `--no-ff` 合入规格分支与 01–05（六次 `merge-tree` 预演与实合均零冲突，149 文件 / 27450 行新增） |
| 各模块分支与 SHA | 规格 `docs/river-next-specs@28804505`；01 `feat/judgment-maintenance-01@e8db50db`（代码 `9735103c`）；02 `feat/research-priority@a7c9dec1`（代码 `add35fc8`）；03 `feat/research-validation-03@f2a12fa3`（代码 `49197160`）；04 `feat/research-diagnostics-04@b5cee17a`（代码 `4d457d7a`）；05 `feat/research-evolution-05-product-value@46ea6cdd` |
| 解释器 | 主树 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13；新树无 venv，按 AGENTS.md 用主树绝对路径；前端 e2e 需 `PATH=.venv-workbench/bin:$PATH`） |
| 实际用户态根 | `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`（真实用户 `a77` 与若干 probe 用户；本轨代码**只**经 `userspace.user_space(user).root` 解析，测试与 E2E 一律临时目录） |
| 生产服务 8792 | PID 59347，cwd `~/.finance-runtime/finance-workspace-2ee664fae9c4`，`source_revision=2ee664fa`（部署家，非任何工作树）；本轨不接管、不重启；隔离 E2E 用空闲端口（实测 8793 / 8797 / 8798 空闲，8794–8796、8799 被占） |
| 代码地图 | 主树 `ready n=22076 @b4a35fa`；本轮按精确文件与符号定位（Explore 扫描 + 直接读源），未以地图无结果断言缺失 |
| 主工作区 | 30 个他人未提交代码改动（river / moneyflow / mfs 等），本轨不接管；09-06 统一 spec 的未提交段只读参考 |

### 计划修改路径（独占白名单）

- 新增：`intelligence/api/research_evolution.py`；`intelligence/services/research_evolution/{__init__,access,adapters,store,facade,pilot_io,study_io}.py`
- 薄改：`intelligence/api/app.py`（注入 router 与资源）；必要时 `intelligence/services/research_project.py`、`intelligence/userspace.py`
- 前端：`intelligence/webapp/src/components/ResearchEvolution*.tsx` 及其测试；薄改 `App.tsx` / `api.ts` / `types.ts` / `ResearchProjectPanel.tsx`；`intelligence/webapp/e2e/research-evolution.spec.ts`
- 测试与夹具：`intelligence/tests/test_research_evolution_*.py`；`intelligence/tests/fixtures/research_evolution/06/`
- 公共文档（本批唯一修改者）：`docs/learning/ledger-map.md`、`docs/agent-product-door.md`、`UBIQUITOUS_LANGUAGE.md`；能力图谱按现行规范回写
- 不改：01–05 目录内实现、`market_feature_store/schema.sql`、交易日历、LLM 模型 / 预算、全局路由 / 注册表

### 现有实现映射（任务 0 核对）

| 基线符号 | 状态 | 06 用法 |
|---|---|---|
| 01 `assess / validate_action / reduce_actions / wake_if_expired / parse_binding / parse_command / adapters.*` | 组合基底可 import，签名已用 `inspect` 核对 | facade 组装报告；store 落 `ManagementEvent`；bindings 端点用 `parse_binding` 校验 |
| 02 `adapt_candidates / prioritize / render_view` | 同上 | `priority` 段；`evaluation_at` 服务端可信 UTC |
| 03 `Repository / freeze_study / register_forecasts / settle_outcomes / evaluate_study / read_receipt / record_exposure` | 同上 | `study_io` 与收据入口；根 = `user_space(user).root / "research_validation"` |
| 04 `diagnose / evaluate_exercise_response / adapters.load_legacy_inputs / parse_exercise_pack` | 同上 | `diagnostics` 段；练习揭示前先经 03 `record_exposure` |
| 05 `validate_event / prepare_events / measure_pair / summarize / RunStoreEvidenceReader / freeze_protocol` | 同上；`EVENT_TYPES` 19 类带 sources 白名单 | events 端点只放 `frontend` 允许类型；`pilot_io` 走同一 writer |
| 主树 `app.py::create_app`、`conversation_or_404`、`research_project.load_project`、`userspace.user_space`、`RunStore`、`ConversationStore` | 见下节接线矩阵（Explore 扫描 + 直接读源后填） | 注入而非重写 |

## 步骤状态

| 步 | 内容 | 状态 | 证据 |
|---|---|---|---|
| 0 | 基线 / 组合基底 / 所有权 / 用户根 / 8792 归属 / 各模块 SHA 与签名 | 完成 | 本文上表 |
| 1 | 只读资源适配、访问校验、store（单 writer + 原子 revision）、GET 投影（module_status） | 进行中 | — |
| 2 | 接 01 真模块：绑定 → 变化 → 复核 → 继续核查 run | 未开始 | — |
| 3 | 接 02 / 04 真模块；05 事件 / 原流程登记 / 收据；03 收据与 study_io | 未开始 | — |
| 4 | 前端三个内容区 + 组件测试 + E2E | 未开始 | — |
| 5 | 全链 I01–I16 与三项反向证伪；重启重建 | 未开始 | — |
| 6 | 等价 CI / registry / E2E 收据；产品门 / 台账地图 / 术语表 / 能力图谱 | 未开始 | — |

## 接线矩阵

（步骤 1 起逐项填：模块 → 入口 → 真实 / 夹具 → 场景编号 → 收据）

## 收据

按 revision 取 `~/.finance-runtime/test-receipts/<stamp>-<rev8>.json`，不读 `latest.json`（多树并发覆盖）。
