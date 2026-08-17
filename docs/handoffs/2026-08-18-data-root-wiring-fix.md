# Handoff：数据根接线错位——`WORKBENCH_REPO_ROOT` 不该参与数据根解析

日期：2026-08-18
roadmap_ref：L1-8792
性质：**代码修复单**（方向已定：代码修，不是改 launcher 配置）。交付 = 修复 PR + 一手验证收据；**切 8792 不在本单内**，由验收方在合并后执行。
前序：2026-08-18 00:47 8792 切 `d1be2d0c` 后 live 复验发现「盘面快照 07-15」「本轮没有连接本地市场数据」两条免责声明常驻；同夜诊断定位为双根接线错位（本单 §1 全部事实已一手复核）。

## 1. 已核事实（2026-08-18 00:50 前后，全部一手）

**病根：一个变量伺候两个主子，语义打架。**

1. `intelligence/paths.py:64 data_repo_root()` 与 `intelligence/services/ask_types.py:42 _data_repo_root()` 是**同逻辑的两份实现**，查找顺序都是 `WORKBENCH_REPO_ROOT → FINANCE_WS → FINANCE_ROOT → 代码根`。
2. 启动器 `/Users/a77/.local/bin/start-finance-workbench`：
   - `export WORKBENCH_REPO_ROOT="/Users/a77/finance-workspace-runtime"`（**代码快照软链**；launcher 第 7 行注释明说这是给 `runtime_provenance.py` 读 git HEAD 做 source_dirty 溯源的）
   - `export FINANCE_WS="/Users/a77/finance-workspace-private"`（真数据仓，指得对，但排序上轮不到它）
3. 症状 A——盘面 DuckDB 静默消失：`default_market_db_path()` = 数据根/`db/market_feature_store.duckdb` → 解析进快照树，快照树**没有 `db/`** → 盘面证据层整层不可用 →「本轮没有连接本地市场数据」。真库在 `/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`（3.4G，2026-08-17 16:58 更新，数据到 08-17）。
4. 症状 B——题材候选冻在 07-15：`DEFAULT_EXPORTS_DIR`（`ask_types.py:56`）同样解析进快照树；快照里最新**可用**（有候选）的 `*-theme-candidates.json` 是 2026-07-15（7 月「抢救入库」批）。私有仓工作树里候选到 **08-13**（每天 50 条、found=True），但 `.gitignore:63` 忽略 `*-theme-candidates.json`，07-16 起从未进 git——就算重切快照也带不进去。
5. `paths.py:75 default_market_db_path()` 的 docstring 就是为修「18 处写死 REPO_ROOT 导致盘面层静默消失」而写的——launcher 的一行配置把同一个 bug 从正门请回来了。
6. 行情快照 `market_snapshot/`（另一个数据面）**没病**：走别的路径，已更新到 08-17、`akshare_exact`、complete。别把它卷进来。

## 2. 消费方清单（改之前逐个过，别只改一处）

| 消费方 | 现状 | 语义 | 处置 |
|---|---|---|---|
| `intelligence/paths.py:70` | 数据根解析含 `WORKBENCH_REPO_ROOT` | 数据根 | **修**：把 `WORKBENCH_REPO_ROOT` 从数据根查找序列里摘掉（`FINANCE_WS → FINANCE_ROOT → 代码根`） |
| `intelligence/services/ask_types.py:48` | 同上的复制粘贴 | 数据根 | **修 + 收口**：删掉重复实现，改为从 `intelligence.paths` 导入（paths 是叶子模块，注释里自己说了这是唯一来源） |
| `intelligence/services/runtime_provenance.py` | 读 `WORKBENCH_REPO_ROOT` 的 git HEAD | **代码根** | **不动**；`test_runtime_provenance.py` 必须保持绿 |
| `intelligence/api/app.py:112` | `REPO_ROOT = env 或 代码树 parents[2]` | **待审** | 追 `REPO_ROOT` 在 app 内的每个下游（`req.repo_root or REPO_ROOT` 喂进 `_run_ask` 后进了哪些路径解析）；数据语义的下游改走数据根函数，代码语义的保留。审计结论写进 PR |
| `intelligence/workbench_skills/daily_review.py:187`、`research_owner.py:118` | 注释自述「数据根，不是代码根。context.repo_root 来自 WORKBENCH_REPO_ROOT」 | 数据根 | 确认它们最终解析走不走本次修复的函数；不走就补上，走了就加回归测试钉住 |
| `intelligence/eval/live_probe.py:136` | sidecar 配方 `export WORKBENCH_REPO_ROOT={repo}` | 代码根（探针树） | **不动**。修后探针的数据根自动落到 launcher 的 `FINANCE_WS`（真数据）——这是改善，验证时确认即可 |

## 3. 不做什么

- **不改 launcher**：`WORKBENCH_REPO_ROOT` 指快照的溯源语义是对的，问题在代码把它当数据根。
- **不动 `.gitignore:63`**：候选 json 是数据不是代码，修好接线后直接读私有工作树，不需要进 git。要改数据入库政策另开单。
- **不迁移/复制 DuckDB**，不动 `market_snapshot/`。
- **保留 `MARKET_FEATURE_STORE_DB` env override**（B 路止血口，别删）。
- 不切 8792（验收方切）。

## 4. 测试（先红后绿）

1. `data_repo_root()`：`WORKBENCH_REPO_ROOT`+`FINANCE_WS` 双设时返回 `FINANCE_WS`（现状返回前者——这条先红）；只设 `WORKBENCH_REPO_ROOT` 时**不再**采用它（回退代码根）；只设 `FINANCE_WS` 正常；全不设回退代码根。
2. `default_market_db_path()`：双设时落 `FINANCE_WS/db/...`；`MARKET_FEATURE_STORE_DB` override 仍最高优先。
3. `DEFAULT_EXPORTS_DIR` / `ask_types` 收口后与 `paths` 同源（两处不再可能分叉——直接断言是同一函数或同一返回值）。
4. 既有 `test_runtime_provenance.py`、`test_market_db_path.py`、`test_theme_candidate_disclosure.py` 全绿（provenance 语义没被误伤的证明）。
5. 环境变量用 monkeypatch 显式设，别依赖会话残留。

## 5. 一手验证（修后、合并前，在修复分支树上）

用 launcher 等价环境（`WORKBENCH_REPO_ROOT=本树`、`FINANCE_WS=/Users/a77/finance-workspace-private`）：

1. `default_market_db_path()` 打印出私有库路径且 `Path.exists()==True`。
2. `load_theme_candidates(None, None)` 默认命中 **2026-08-13**（50 条），不再回退 07-15。
3. 确定性 ask 探针（`use_llm=False`）问「长电科技的营收规模怎么看」：warnings **不再**含「本轮没有连接本地市场数据」；S 源快照日期 = 08-13。收据落 `~/.finance-runtime/`（路径写进 PR）。
4. **预期残差写清楚，别追**：S 源 08-13 ≠ DB 08-17 是正常的——08-14 盘面库回补是 taskboard 在审单，08-17 候选等夜间管线。本单只修接线。

## 6. 门禁与流程

- 从 `gitea/main` 开分支；PR 走 Gitea API（token：`security find-generic-password -s gitea-local -a a77-token -w`）。
- 四件套：ruff + 全量 pytest + `intelligence/webapp` pnpm lint/typecheck/test/build，`umask 022`。
- **跑 pytest 前摘启动器变量，只留 `PATH` 和 `KNOWLEDGE_WIKI`**（`PYTHONPATH` 指快照会混树导入，2026-08-17 夜已两次踩坑）。
- 台账：PR 更新 `docs/handoffs/inflight/main.md` 一行（症状、病根、修法、收据路径）。
- 交付后验收方：验收 → 合并 → 切 8792 → 用 grounded 车道复验「无市场数据」消失。

## 7. 红线

- 溯源语义不许变：修后 `/api/health` 的 `source_revision`/`source_dirty` 仍读代码快照。
- 不接受「跑过了是好的」：每条验证给命令 + 收据路径。
- 别顺手修别的（概念袋、stale 旁路、max_evidence 各有各的单）。
