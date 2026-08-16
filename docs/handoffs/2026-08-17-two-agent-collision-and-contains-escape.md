# 2026-08-17 双 agent 撞车归位 + `contains` ESCAPE 根因交接

roadmap_ref: 另案（运行时可用性 / 协作纪律）。分支 `fix/finance-query-contains-escape`，base = **生产实际部署的 `1594394c`**（gitea/main 线）。

> 写给在 gitea/main 线上工作的那位（下称 **A 方**）与后来者。
> 本文件的第一目的不是交代我做了什么，而是**说清楚我们在哪儿撞了、以后怎么不撞**。

---

## 0. 一句话

**我们俩在 2026-08-16 夜里对同一个 run（`run_20260816_221823_213588`）各做了一遍完整 M1 分诊，产出五条相同的发现、两套不同的编号；A 方的已合并部署，我的没有。账本因此分叉且 `R-20260816-13` 撞号。我唯一没被覆盖的产出是 `finance_query` 的 `contains` ESCAPE 根因修复——生产至今仍带着这个 bug。**

## 1. 撞车全貌

### 1.1 五条重复发现（同一个 run，同一套结论，两套编号）

| 内容 | A 方（已合并部署） | 我（未合并） |
|---|---|---|
| provider 链 ≥2，中转 5xx 时转移 | `R-20260816-16` | `R-20260816-06` |
| 成因行从 `ASK_DEGRADED_FALLBACK` 拆出 | `-17` | `-07` |
| 三份 artifact status 同一投影 | `-18` | `-08` |
| 缺口模板整体标 `uncheckable` | `-19` | `-09` |
| 补齐 `_OUTPUT_DESCRIPTIONS` 10 个缺项 | `-20` | `-10` |
| repair 窗随生效 provider 的实测 p90 | `-21` | `-11` |

A 方的 `-21` 条目里直接引用了 `run_20260816_230528_976709`——**那是我的 canary 跑出来的 run**。生产的 `intelligence/services/repair_coordinator.py` 第 24–39 行是我写的注释与 `_resolve_seconds_cap` 函数原文，但我的三个 commit（`d0869d1c` / `8e855c71` / `9633b979`）**都不是 `1594394c` 的祖先**——即我的产物被搬过去重新提交，分支本身没进线。

**这里不追责，只记事实与后果**：同一份活做了两遍，且事后无法从 git 历史看出归属。

### 1.2 账本已分叉，且 ID 撞号

| | 住址 | 分支 | 条目 |
|---|---|---|---|
| A 方 | `docs/prediction-ledger.md` | **gitea/main** | …`-01`~`-11`、`-13`~`-21`（无 `-12`） |
| 我 | 同一路径 | `docs/dsh-absorption-spec` | …`-01`~`-13` |

**`R-20260816-13` 是两件不同的事**：

- A 方 `-13` = 宽题取证饿死 M1（`run_20260816_205439_732198`），`EVAL_ONLY`
- 我 `-13` = `finance_query` 工具描述补字段清单，`TOOL_DESCRIPTION_FIX`

账本自己的 header 写着「住址固定，否则闭环会静默断裂且不报错」。**住址确实固定了，但分支没有**——同一路径在两条分支上各写各的，正是它要防的那个失效，只是换了个维度发生。

## 2. 我唯一没被覆盖的产出：`contains` ESCAPE 根因

**生产 `1594394c` 的 `intelligence/services/finance_query.py:1323` 至今仍是两字符 ESCAPE，bug 还在。** A 方账本里没有任何一条涉及它。

### 根因

`_filter_sql` 的 `contains` 分支写的是 `f"... ESCAPE '\\\\'"`，f-string 求值成 SQL 字面量 `'\\'`。SQL 字符串里反斜杠不是转义符，故那是**两个字符**，而 `ESCAPE` 只接受一个：

```
_duckdb.SyntaxException: Invalid escape string. Escape string must be empty or one character.
```

### 为什么一直没被发现

**危害形状是静默降级，不是报错。** `episode_tools` 把 `FinanceQueryExecutionError` 归进兜底分支（`episode_tools.py:1113`），返回 `ok=true` + 「结构化数据源暂不可用」+ 零证据。**模型看到 `ok` 以为查过了**，实际一行没拿到。

对照实验（同表、同窗口，纯 SQL 生成问题，与数据/编码/库路径无关）：

| 查询 | 结果 |
|---|---|
| 无 filter | ✓ 10 行 |
| `eq 'AI算力'` | ✓ 4 行 |
| `in ['AI算力']` | ✓ 4 行 |
| **`contains '算力'`** | **✗ SQL 语法错** |
| **`contains 'AI'`（纯英文）** | **✗ SQL 语法错** |

### 影响面

`contains` 是模型按主题名筛选的**唯一自然写法**（`theme_name contains 算力`）。2026-08-16 国产算力题 6 个样本里 4 个用了它，4 个全部空手而归；24 次工具调用只有 8 次拿回证据。**题材类问题几乎必然命中。**

### 交付

分支 `fix/finance-query-contains-escape @ dc686065`，base = `1594394c`，cherry-pick 无冲突。

- 修复：`ESCAPE '\\'` → `ESCAPE '\'`。转义语义不变（`_` / `%` / `\` 仍按字面量匹配，单独钉住）。
- 新增 8 条**打真库**门禁（`intelligence/tests/test_finance_query_contains.py`）。mock connection 测不出来——该 bug 只在 SQL 执行期暴露。
- **变异验证**：改回两字符后 8 条全红；还原后全绿。
- 读数：新增门禁 8 passed、`finance_query` 既有测试 67 passed、ruff clean、七道 pre-commit 钩子全过。
- 库路径走 `paths.py` 数据根，缺库时 skip 不假红。

## 3. ⚠️ 生产基线自带 18 条红（升格用户）

在 `1594394c` 上跑全量：`18 failed, 4679 passed, 11 skipped`。

**做过对照**：抽掉我的修复，同样 18 条红 → **非本改动引入**。

```
intelligence/tests/test_continuous_turn_adapter.py
  test_adapter_closes_session_on_success_path
    assert result.status == "completed"
    实得: 'degraded'
```

疑似 `-18`（status 投影统一）改了语义但未同步更新 18 条测试期望。

**影响面已核**：部署后唯一一单生产 run（`verify-r21-wire-08`，00:33）仍报 `completed`，**不是全面回归**，是测试期望没跟上。但按本仓纪律，18 条红的 revision 不该在线上跑。**请 A 方确认是语义有意变更（则更新期望）还是漏改。**

## 4. 我这边还剩两条未被覆盖的发现（含撞号那条，建议改号）

按 gitea 线现有编号，下一个空位是 `-22`。建议：

| 我原编号 | 建议改为 | 内容 | 状态 |
|---|---|---|---|
| `R-20260816-12` | **`R-20260816-22`** | 主线表新鲜度门禁应区分「过期」与「已退出主线」 | `pending`，**等用户拍板**，未动代码 |
| `R-20260816-13`（撞号） | **`R-20260816-23`** | `finance_query` 工具描述补按 dataset 的合法字段清单 | `pending` |

### `-22` 的实质（值得 A 方看一眼）

修完 `contains` 后，`mainline_sector_daily` 的错误从「数据源暂不可用」变成新鲜度门禁：

> `结构化市场数据仅更新到 2026-08-07，早于当前所需 2026-08-14；旧数据未用于当前判断`

查库坐实：

```
AI算力 在 fact_mainline_sector_daily 里的最后一天 = 2026-08-07
08-10 起主线只剩：有色金属、医药、消费零售
```

**「算力于 08-07 后掉出主线」本身就是「发酵/共识/透支」的强信号**，而当前策略把它当过期数据整批丢弃。这是产品口径取舍（放宽 floor 会让真过期数据混进当前判断，那是该门禁的原始设计意图），**不是 bug，我没擅自改**。

### `-23` 的证据

模型三次写出不存在的维度名：`not a dimension: strength` / `index_return_pct` / `rank`。`dataset_field_hint()` 这个函数**已经存在**，只是没进模型可见面——属「事实投递 > 提醒」那条既有模式，不要靠加 prompt 训话。

## 5. 归属分工建议（怎么不再撞）

### 5.1 立即

1. **账本合并 + 改号**：我的 `-12`/`-13` 按 §4 改成 `-22`/`-23` 并入 gitea/main 那份。**以 gitea/main 为账本唯一真本源**，我在 `docs/dsh-absorption-spec` 上那份不再更新（它已含 `-06`~`-11` 的重复条目，合并时按 §1.1 映射表去重，不要两套并存）。
2. 我在主 checkout（`docs/dsh-absorption-spec`）上还留了两份未提交改动：`docs/prediction-ledger.md`、`docs/trace-profile.md`，以及 handoff `2026-08-16-provider-outage-and-glm-failover.md`。**trace-profile 的 7 条字段陷阱 + 3 条盲区值得并过去**（尤其「`ok=true` 不等于有数据」「`/v1/models` 200 不代表出口可用」两条），其余按去重表处理。

### 5.2 分工线（建议）

| 面 | 归属 | 理由 |
|---|---|---|
| 预算 / 窗口 / status 投影 / 缺口模板 / 输出描述 | **A 方** | 已合并部署，历史在 A 方手里 |
| 工具层：`finance_query` SQL 生成、字段可发现性、新鲜度门禁口径 | **我** | `contains` 根因与 `-22`/`-23` 都在这一面 |
| 生产部署与 revision 切换 | **A 方** | 已在做，避免两方都切 |

### 5.3 开工前三件事（两边都做）

1. **先看 8792 现在跑的是哪个 revision**：`curl -s localhost:8792/api/health` 读 `source_revision` + `loaded_code_root`，再对那个目录 `git log -1`。三读数并列。本次事故里 8792 在我工作期间被切了两次（`6cd0756e` → `0df86612` → `1594394c`），我基于旧快照的 live 读数因此不可复现。
2. **确认在哪条线上**：权威线是 **`gitea/main`**。本地 `origin/main` 停在 `a189d6bd`，落后 20+ 提交。我整晚基于 `origin/main` 工作，这是重复劳动的直接原因。
3. **认领 run**：对某个 run 开分诊前，先在账本搜该 `run_id`。A 方的 `-16`~`-21` 与我的 `-06`~`-11` 都锚在 `run_20260816_221823_213588`，任一方开工前搜一下就能发现对方在做。

## 6. 现场状态

| 对象 | 状态 |
|---|---|
| 8792 | A 方在管，`1594394c`，**未动** |
| 8795 / 8796 | 已停（8796 是我的 canary，用完即停） |
| `fwp-wt-contains` | 分支 `fix/finance-query-contains-escape @ dc686065`，**待 review/合并** |
| `fwp-wt-repair-window` | 3 commit，**已被 A 方 `-21` 等价覆盖，建议删除 worktree 与分支** |
| cursor-agent pid 17907 | 已 SIGTERM 停止（路径找错的那个） |
| 生产配置 | 启动器 GLM 三件套是我加的（`start-finance-workbench.bak-20260816-glm` 可回滚）；A 方后续部署沿用了 |

## 7. 下一个人从这里接

1. 合 `fix/finance-query-contains-escape`——它是目前唯一在生产上未修的根因。
2. 请 A 方裁定 §3 的 18 条红：语义有意变更还是漏改。
3. 账本按 §5.1 合并改号，**以 gitea/main 为唯一真本源**。
4. `-22` 需用户拍板产品口径后才动代码。
5. `-23` 可直接做（`dataset_field_hint()` 已存在，接进模型可见面即可）。
