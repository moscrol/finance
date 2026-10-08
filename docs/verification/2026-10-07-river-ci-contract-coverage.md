# 时间长河契约进 CI + streak 类型门

> 历史记录：此文描述当时单个补丁的状态与旧解释器读数，不代表最终 20 连交付。`regime_script.py` 已在后续补丁出现；本次迁移/验证口径见 [交付质检](2026-10-08-vidio-finance-transfer-qc.md)。
>
> 日期：2026-10-07
> 分支：`fix/river-ci-contract-coverage`
> 起因：外部质检发现两件事——(1) 河的核心契约在 CI 上一次都没跑过；(2) `derive_streak` 对非布尔标签返回假零。

---

## 1. 问题一：核心契约在 CI 上从未执行

### 实测

四个文件整份 `skipif(not DB.exists())`：

| 文件 | 守什么 |
|---|---|
| `tests/test_river_slice.py` | 六轨联立、幂等、可回溯、无前视 |
| `tests/test_river_window.py` | 区间特征与聚类 |
| `tests/test_river_query.py` | 横扫纵扫 |
| `tests/test_river_cutoff_guard.py` | 无前视守卫 |

而 `.gitignore:78-79` 排除 `db/` 与 `*.duckdb`，`workbench-check.yml` 的 runner 上不可能有真库。

干净 clone 上实测：

```
$ pytest tests/test_river_*.py intelligence/tests/test_river*.py -q
94 passed, 43 skipped
```

**43 个 skip 全部是「需要真库」。** 也就是说 AGENTS.md 里「全仓 pytest 8010 passed、门禁全绿」这个读数**不包含这条河的核心契约**——它们只在开发机上跑过。

这与本仓已经踩过的坑同形：`a41e86dfc` 把活测试误扫进 `scripts/archive/`，全树 pytest 停在 collection error 33 天，同期 187 张「≥10000 passed」的收据全部带着那个坏文件。收据看不出收窄，skip 也看不出未覆盖。

### 为什么不是「把真库测试改成跑夹具库」

那四个文件断言的是**真实数据语义**：

- `test_实体身份跨供应商换源必须稳定` —— 2026 年 .TI → .FP 换源，两套代码重叠九个月、每个板块断点不同
- `test_缺数留_None_不补零` —— 「资金轨只有 12% 的日子有数」
- `test_产业基本面文档接进舆论轨` —— 「只有 5/37 份挂了 linked_sectors」

合成库能让这些断言变绿，但绿得没有意义。那正是 AGENTS.md 反复警告的假门禁。**所以真库测试原样保留，一行未改。**

### 做法

新增 `tests/test_river_contract_on_fixture.py`（26 个用例，**不需要真库**），只承载**换一套数据也必须成立的不变量**：

| 组 | 用例 |
|---|---|
| 结构 | 六轨钦定、不得用空列表冒充零、无覆盖实体报 `no_data`（阳性对照）、缺口原因在白名单、不做模糊匹配 |
| 幂等与回溯 | 两次调用逐字段相同、每个对象带 `ref` + 16 位 `source_hash`、payload ≤ 20 字段、判断轨用稳定 id 且不串轨 |
| 无前视四道门 | `cutoff > as_of` 拒绝、hindsight 签字后不报 strict、与 `require_strict` 互斥、strict 滤成 `pit_filtered`、空切片不得报 strict |
| 实体归一 | 跨换源 `entity_id` 稳定、`alias_applied` 如实标记、`ref` 保留当天真实代码 |
| 轨内口径 | 题材轨读整数列不解析字符串、舆论轨用 `created_at` 不用 `updated_at`、散文不进度量对象、`derivation=frozen_llm` |
| 区间 | 每一片与单点切片逐字节相同、transition 带方向与相邻两天的 refs、派生可拆回到天 |

夹具库 `tests/fixtures/river_mini_db.py` **按 `market_feature_store/schema.sql` 现建**，不手写 DDL——列改了夹具会在 `_require_tables` 或 INSERT 处直接报错，不会悄悄测一个已不存在的形状。

夹具数据是故意构造来触达具体分支的，不是模拟真实行情：

- `BARE_ENTITY`（冷门板块）一份研报都不发 → 舆论轨 `no_data` 有阳性对照
- `ALIAS_ENTITY`（半导体）第 8 个交易日把代码从 `.TI` 换成 `.FP` + 别名表 → 换源归一可测
- 研报的 `updated_at` 全设成区间最后一天（复刻真表被 09-02 批量重写抹平的形状）→ 舆论轨读错列会红
- `up_stat` 字符串与 `up_stat_days / up_stat_boards` 整数列同时填 → 守「不要再去解析字符串」

### 读数

```
$ pytest tests/test_river_contract_on_fixture.py -q
26 passed in 6.16s          # 无真库
```

CI 上这条河的契约覆盖从 **0 → 26**。

---

## 2. 问题二：`derive_streak` 对非布尔标签返回假零

### 实测

```python
>>> rd.derive_streak(win, "market_stage")
payload: {"status": "ok", "longest": 0, "longest_end": null, "current": 0, "days": 15}
```

`market_stage` 取 `'震荡' / '主升' / '分歧'`，内层循环是 `if d.value is True`，永远走不进去。于是返回 `longest=0` 且 **`status="ok"`**——一个看着完全正常的读数，调用方没有任何线索知道自己问错了问题。

注册标签实测分布：

```
ALL_LABELS              17
SLICE_EVALUABLE_LABELS   4   （dual_red_strict / market_stage / limit_heat_rank / volume_surge）
其中布尔型               1   （dual_red_strict）
```

**4 个可求值标签里 3 个传进 streak 都是假零。** `scripts/river_window.py --label` 从 CLI 收标签，等于把这个口子开在命令行上。

### 做法

`_require_boolean()`：区间内取到任何非 `None` 的非布尔值就抛 `LabelNotSliceEvaluable`（复用已有异常类），错误信息点名标签、类型、样例日与取值，并说清正确做法是先把分类标签投影成谓词再数连续段——**不替调用方猜一个取值**。

### 回归面

全仓 `derive_streak` 调用方只有 `dual_red_strict`（布尔）与 `scripts/river_window.py` 的 CLI 入参。前者不受影响（已加阳性对照用例 `test_streak_对布尔谓词仍然正常工作`），后者从「静默假零」变成「明确报错」。

---

## 3. 收据

```
$ pytest tests/test_river_*.py intelligence/tests/test_river*.py \
         intelligence/tests/test_teaching_framework_river_objects.py \
         intelligence/tests/test_scenario_trees.py -q
189 passed, 44 skipped

$ ruff check tests/test_river_contract_on_fixture.py tests/fixtures/ \
             intelligence/services/river_derive.py
All checks passed!
```

> 环境说明：本轮在 Python 3.11 + 独立 venv 上跑（`FWP_ALLOW_ANY_PYTHON=1`），
> **不是** `test-environment.json` 声明的 3.12.13 / `.venv-workbench`。
> 按本仓纪律，这个读数不可与正常环境的全量数字比较，合并前须在
> `.venv-workbench` 上复跑 `ruff check . && pytest -q` 取正式收据。
> 本轮改动面只有三个文件、无新依赖，但这条限制照写不省。

---

## 4. 未做（留给后续）

质检同时发现、本轮**没动**的四条，都已在报告里记账，不在本 PR 范围：

1. `window()` 默认只产 `cumulative`，另外四类派生要手工调；`cumulative` 的 `member_refs` 为空。
2. `resolve_entity` 只认板块；指数 / 题材 / 个股实体入口未开（`config_theme_sector_link` 0 行）。
3. `opinion_stage.dislocation()` 只比 题材 × 舆论 两维，盘面维未进——三维对照实际是二维。
4. `environment_script`（环境剧本 / G-08）全仓零命中。

第 1 条是小工单；第 2–4 条依赖 G-01 母本与标签词表扩充，是设计顺序问题不是欠债。
