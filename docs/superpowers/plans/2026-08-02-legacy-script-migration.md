# Legacy Script Migration Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 将 4 个 broken legacy CLI 收敛到 canonical Market Feature Store：保留并修复板块分析、正式退役旧飞书写入入口、保留日报渲染器，并让全仓 Ruff 在无文件级排除下归零。

**Architecture:** 纯 turning_points 信号引擎负责无前视算法；只读 SectorDataProvider 负责 canonical DuckDB 到旧消费者字典结构的适配；两个分析 CLI 只做参数解析和展示。sync_to_local.py 变成不导入数据库、凭证或网络的退役 shim，日报模板脚本继续调用现有 build_daily_review。

**Tech Stack:** Python 3.9 目标语法、DuckDB read-only connection、argparse、pytest、pre-commit、Ruff 0.11.13。

---

## 文件地图

### 新建

- market_feature_store/analysis/__init__.py：分析子包公开边界，不执行副作用。
- market_feature_store/analysis/turning_points.py：Signal、SignalDetector 与阈值常量，纯输入输出。
- market_feature_store/analysis/sector_data.py：SectorDataProvider，只读 canonical schema 适配器。
- tests/test_turning_points.py：共享信号引擎的前缀稳定性、确认日和阈值回归。
- tests/test_sector_analysis_data.py：临时 DuckDB 的字段映射、滚动 MA5、缺库保护。
- tests/test_legacy_script_cli_contracts.py：四个 CLI 的 help、退出码和零副作用契约。

### 修改

- scripts/backtest_sector.py：删除内嵌 provider/detector，改用共享模块；改为 argparse；增加 --db-path。
- scripts/detect_turning_points.py：改成共享 provider/detector 的薄展示层，删除旧 zigzag 查询和手写参数解析。
- scripts/sync_to_local.py：替换为正式退役 shim。
- scripts/render_daily_review_template.py：保留 root bootstrap，仅为两处延迟 import 添加带原因的 E402 行注释。
- ruff.toml：移除 4 个 legacy 文件的 extend-exclude 条目。
- README.md、CLAUDE.md、docs/learning/current-duckdb-source.md、docs/workflows/daily-review-workflow.md、scripts/archive/README.md：同步 canonical 写入路径、分析入口和退役说明。

---

### Task 1: 提取无前视 turning-point 引擎

**Files:**

- Create: market_feature_store/analysis/__init__.py
- Create: market_feature_store/analysis/turning_points.py
- Create: tests/test_turning_points.py
- Modify: scripts/backtest_sector.py 的 import 和 Signal/SignalDetector 定义
- Test: tests/test_backtest_sector.py

- [ ] **Step 1: 写共享引擎的失败测试**

从 tests/test_backtest_sector.py 的 TestPivotConfirmation 复制三组已验证输入到 tests/test_turning_points.py，断言保持以下精确行为：

~~~python
def test_peak_is_emitted_on_confirmation_day():
    detector = SignalDetector(ma5_min_swing=500)
    dates = [f"2026-01-{day:02d}" for day in range(1, 8)]
    ma5 = [2000, 2100, 2200, 2000, 1700, 1650, 1600]
    signals = detector.detect(
        [{"date": day, "volume": None} for day in dates],
        [{"date": day, "count": 1000, "ma5": value} for day, value in zip(dates, ma5)],
    )
    assert [(item.date, item.type) for item in signals if "peak" in item.type] == [
        ("2026-01-05", "peak_confirmed")
    ]

def test_future_suffix_does_not_change_historical_prefix():
    ma5 = [1000, 1600, 2200, 2000, 1700, 1200, 1900, 2600, 2100, 1900,
           1400, 2000, 2700, 3300, 2600, 2000, 2600, 3200, 2500, 1800]
    dates = [f"2026-01-{day:02d}" for day in range(1, 21)]
    detector = SignalDetector(ma5_min_swing=500)
    market = [{"date": day, "volume": None} for day in dates]
    full = detector.detect(market, [
        {"date": day, "count": 1000, "ma5": value}
        for day, value in zip(dates, ma5)
    ])
    for length in range(1, len(dates) + 1):
        prefix = detector.detect(
            market[:length],
            [{"date": day, "count": 1000, "ma5": value}
             for day, value in zip(dates[:length], ma5[:length])],
        )
        cutoff = dates[length - 1]
        expected = [(item.date, item.type, item.detail)
                    for item in full if item.date <= cutoff]
        actual = [(item.date, item.type, item.detail) for item in prefix]
        assert actual == expected
~~~

再保留 next-day-entry 和 last-day-no-trade 两个现有回归。

- [ ] **Step 2: 运行测试确认当前模块尚不存在**

Run: python3 -m pytest tests/test_turning_points.py -q

Expected: FAIL，原因是 market_feature_store.analysis 尚未建立。

- [ ] **Step 3: 提取纯实现**

创建 market_feature_store/analysis/turning_points.py，逐字迁移 scripts/backtest_sector.py 当前已通过测试的 Signal、SignalDetector、VOLUME_SURGE_PCT、MA5_MIN_SWING 实现；模块不得导入 DuckDB、Path、网络库或打印函数。保留构造函数和 detect(market_data, advancers) 签名。

在 backtest_sector.py 顶层导入并重新暴露：

~~~python
from market_feature_store.analysis.turning_points import (
    MA5_MIN_SWING,
    VOLUME_SURGE_PCT,
    Signal,
    SignalDetector,
)
~~~

删除脚本中原来的重复定义，保持既有 tests/test_backtest_sector.py 的 bs.SignalDetector 兼容路径。

- [ ] **Step 4: 运行共享与兼容测试**

Run: python3 -m pytest tests/test_turning_points.py tests/test_backtest_sector.py -q

Expected: PASS。

- [ ] **Step 5: 提交纯逻辑提取**

~~~text
git add market_feature_store/analysis tests/test_turning_points.py scripts/backtest_sector.py tests/test_backtest_sector.py
git commit -m "refactor: extract no-lookahead turning point engine"
~~~

### Task 2: 建立 canonical 只读数据适配器

**Files:**

- Create: market_feature_store/analysis/sector_data.py
- Create: tests/test_sector_analysis_data.py

- [ ] **Step 1: 写临时 DuckDB 映射测试**

测试使用 tmp_path / 'market_feature_store.duckdb'，创建最小关系：

~~~python
con.execute("""
    CREATE TABLE fact_market_daily (
        trade_date DATE, total_amount DOUBLE,
        amount_vs_yesterday_pct DOUBLE, limit_up INTEGER,
        limit_down INTEGER, sh_week_ma DOUBLE,
        sh_deviation_pct DOUBLE, advancers INTEGER
    )
""")
con.execute("""
    CREATE TABLE fact_sector_daily (
        trade_date DATE, sector_ts_code TEXT, sector_name TEXT,
        diff_ratio DOUBLE, pct_chg DOUBLE, amount DOUBLE
    )
""")
~~~

断言 get_sector_price_matrix、get_sector_marginal、get_market_data、get_advancers、get_trading_dates 的返回字典与旧 engine 契约一致；ma5 是按日期排序的最近 5 行滚动平均，首几行使用实际可用行数。

- [ ] **Step 2: 写缺库不创建测试**

~~~python
missing = tmp_path / "missing.duckdb"
with pytest.raises(FileNotFoundError):
    SectorDataProvider(missing)
assert not missing.exists()
~~~

- [ ] **Step 3: 运行测试确认红灯**

Run: python3 -m pytest tests/test_sector_analysis_data.py -q

Expected: FAIL，适配器模块和类尚未存在。

- [ ] **Step 4: 实现适配器**

SectorDataProvider 接受 db_path，默认值来自 market_feature_store.db.DB_PATH。构造函数先 Path.is_file()，不存在则抛出包含路径的 FileNotFoundError，再以 duckdb.connect(path, read_only=True) 打开；不调用 init_db、不创建目录。

get_advancers 使用参数绑定和窗口函数：

~~~python
SELECT trade_date, advancers,
       AVG(advancers) OVER (
           ORDER BY trade_date
           ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
       ) AS ma5
FROM fact_market_daily
WHERE trade_date BETWEEN ? AND ?
ORDER BY trade_date
~~~

其余方法映射：sector date/ts_code/sector/pct_chg/diff_ratio/amount 到 fact_sector_daily.trade_date/sector_ts_code/sector_name/pct_chg/diff_ratio/amount；market volume/volume_change/limit_up/limit_down/week_ma/deviation 到 fact_market_daily.total_amount/amount_vs_yesterday_pct/limit_up/limit_down/sh_week_ma/sh_deviation_pct。所有查询用参数绑定；close() 关闭连接。

- [ ] **Step 5: 运行适配器测试确认绿灯**

Run: python3 -m pytest tests/test_sector_analysis_data.py -q

Expected: PASS。

- [ ] **Step 6: 提交适配器**

~~~text
git add market_feature_store/analysis/sector_data.py tests/test_sector_analysis_data.py
git commit -m "feat: add read-only canonical sector data adapter"
~~~

### Task 3: 迁移 backtest CLI

**Files:**

- Modify: scripts/backtest_sector.py
- Modify: tests/test_backtest_sector.py
- Modify: tests/test_legacy_script_cli_contracts.py

- [ ] **Step 1: 写 CLI 失败测试**

用 fixture 数据库执行：

~~~python
result = subprocess.run(
    [sys.executable, "scripts/backtest_sector.py", "--help"],
    cwd=ROOT,
    env={**os.environ, "MARKET_FEATURE_STORE_DB": str(db_path)},
    capture_output=True,
    text=True,
)
assert result.returncode == 0
assert "--db-path" in result.stdout
assert not (ROOT / "db" / "market.duckdb").exists()
~~~

另测不存在的 --db-path：预期退出码 2、stderr 包含 canonical DuckDB、路径仍不存在。

- [ ] **Step 2: 运行测试确认旧 CLI 失败**

Run: python3 -m pytest tests/test_legacy_script_cli_contracts.py -k backtest -q

Expected: FAIL，因为旧脚本没有 argparse、仍查询 sector_marginal。

- [ ] **Step 3: 接入 provider 与 argparse**

删除脚本内的 SectorDataProvider 定义和旧 SQL，导入 market_feature_store.analysis.sector_data.SectorDataProvider。main(argv=None) 先解析参数，再建立 provider；自动日期范围查询 fact_sector_daily，空数据用 parser.error 返回 2。

保留 engine 调用边界：

~~~python
provider = SectorDataProvider(args.db_path or DB_PATH)
try:
    engine = SectorBacktestEngine(
        top_n=args.top,
        hold_days=args.hold,
        min_marginal=args.min_marginal,
        min_pct_chg=args.min_pct,
        allow_overlap=args.overlap,
        provider=provider,
    )
    result = engine.run(start, end)
finally:
    provider.close()
~~~

- [ ] **Step 4: 运行回测 CLI 测试**

Run: python3 -m pytest tests/test_backtest_sector.py tests/test_legacy_script_cli_contracts.py -k 'backtest or next_day' -q

Expected: PASS。

- [ ] **Step 5: 提交 backtest 迁移**

~~~text
git add scripts/backtest_sector.py tests/test_backtest_sector.py tests/test_legacy_script_cli_contracts.py
git commit -m "refactor: migrate sector backtest to canonical DuckDB"
~~~

### Task 4: 迁移 turning-point CLI

**Files:**

- Modify: scripts/detect_turning_points.py
- Modify: tests/test_legacy_script_cli_contracts.py

- [ ] **Step 1: 写 standalone CLI 测试**

对 fixture 数据库运行 --help 和 --from 2026-01-01 --to 2026-01-10 --db-path <fixture>；断言 help 为 0、数据运行成功、输出包含 信号，默认旧库不存在。

- [ ] **Step 2: 运行测试确认旧脚本失败**

Run: python3 -m pytest tests/test_legacy_script_cli_contracts.py -k turning -q

Expected: FAIL，help 在旧脚本中触发旧数据库连接。

- [ ] **Step 3: 替换为薄适配层**

脚本只保留 argparse、provider、shared detector 和打印函数。--from、--to、--db-path 传入 provider；用 detector.detect(provider.get_market_data(start, end), provider.get_advancers(start, end)) 生成信号。删除旧字符串拼接 SQL、独立 zigzag 和 sys.argv.index 解析。

- [ ] **Step 4: 运行 detector 测试**

Run: python3 -m pytest tests/test_turning_points.py tests/test_legacy_script_cli_contracts.py -k turning -q

Expected: PASS，输出使用与 backtest 相同的 confirmation-day 类型。

- [ ] **Step 5: 提交 detector 迁移**

~~~text
git add scripts/detect_turning_points.py tests/test_legacy_script_cli_contracts.py
git commit -m "refactor: share canonical turning-point CLI"
~~~

### Task 5: 正式退役 sync_to_local

**Files:**

- Modify: scripts/sync_to_local.py
- Modify: tests/test_legacy_script_cli_contracts.py

- [ ] **Step 1: 写退役契约测试**

~~~python
result = subprocess.run(
    [sys.executable, "scripts/sync_to_local.py", "--incremental"],
    cwd=ROOT,
    env={"HOME": str(tmp_path), **os.environ},
    capture_output=True,
    text=True,
)
assert result.returncode == 2
assert "daily-full" in result.stderr
assert not list((ROOT / "db").glob("market.duckdb"))
~~~

再运行 --help，断言 return code 为 0 且输出含“已退役”。

- [ ] **Step 2: 运行测试确认旧 writer 有副作用**

Run: python3 -m pytest tests/test_legacy_script_cli_contracts.py -k sync -q

Expected: FAIL，旧脚本会导入旧依赖并尝试初始化数据库。

- [ ] **Step 3: 写最小 shim**

文件只保留 argparse、sys 和静态退役说明；argv 先规范化，再区分 help 和普通调用：

~~~python
def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="旧版飞书同步入口（已退役）")
    parser.add_argument("--incremental", action="store_true", help=argparse.SUPPRESS)
    parser.parse_args(args)
    print(
        "sync_to_local.py 已退役；复盘数据统一使用 "
        "python3 -m market_feature_store.cli daily-full --help。",
        file=sys.stderr,
    )
    return 2
~~~

顶层用 raise SystemExit(main())；argparse 自己处理 --help 并在 help 时直接退出 0。不得导入 duckdb、feishu_utils、urllib 或 credential loader。

- [ ] **Step 4: 运行退役测试和静态扫描**

Run: python3 -m pytest tests/test_legacy_script_cli_contracts.py -k sync -q

Expected: PASS。

Run: rg -n 'duckdb|feishu_utils|urllib|load_config|get_token' scripts/sync_to_local.py

Expected: no matches。

- [ ] **Step 5: 提交退役 shim**

~~~text
git add scripts/sync_to_local.py tests/test_legacy_script_cli_contracts.py
git commit -m "chore: retire legacy Feishu sync entrypoint"
~~~

### Task 6: 收紧 renderer 与 Ruff 范围

**Files:**

- Modify: scripts/render_daily_review_template.py
- Modify: tests/test_legacy_script_cli_contracts.py
- Modify: ruff.toml

- [ ] **Step 1: 写 renderer 测试**

断言 --help 退出 0，输出包含 --trade-date 和 --output-dir，且临时工作目录没有报告或图表；用 monkeypatch 替换 build_daily_review，验证 --trade-date 2026-01-05 --output-dir <tmp> 传入正确路径。

- [ ] **Step 2: 添加两处有原因的 E402 注释**

~~~python
# Direct-file CLI adds the repository root before importing the package.
from market_feature_store.db import connect  # noqa: E402
from market_feature_store.reports.daily_review import build_daily_review  # noqa: E402
~~~

- [ ] **Step 3: 移除四个 exclude**

从 ruff.toml 的 extend-exclude 删除四个脚本，不改全局规则、不增加 per-file-ignores。

- [ ] **Step 4: 运行 renderer 与 Ruff**

Run: python3 -m pytest tests/test_legacy_script_cli_contracts.py -k renderer -q

Expected: PASS。

Run: pre-commit run ruff-check --all-files

Expected: PASS，且不再需要 --no-force-exclude 才能检查四个文件。

- [ ] **Step 5: 提交 Ruff 收口**

~~~text
git add scripts/render_daily_review_template.py tests/test_legacy_script_cli_contracts.py ruff.toml
git commit -m "style: enforce Ruff on migrated legacy entrypoints"
~~~

### Task 7: 同步文档和历史定位

**Files:**

- Modify: README.md
- Modify: CLAUDE.md
- Modify: docs/learning/current-duckdb-source.md
- Modify: docs/workflows/daily-review-workflow.md
- Modify: scripts/archive/README.md

- [ ] **Step 1: 替换过时命令**

把“飞书 → sync_to_local.py → DuckDB”现役流程改成：

~~~text
fupanhui/Feishu source → daily-full → db/market_feature_store.duckdb
~~~

保留 backtest_sector.py、detect_turning_points.py 的 canonical CLI 示例；将 sync_to_local.py 标为已退役兼容入口。

- [ ] **Step 2: 修正 archive 说明**

说明 backtest/detector 已迁移；writer 的完整旧实现可用 git show a84028e6:scripts/sync_to_local.py 查阅，不复制一个可误运行的死脚本。

- [ ] **Step 3: 检查文档命中**

Run: rg -n 'sync_to_local|market\.duckdb|daily-full|backtest_sector|detect_turning_points' README.md CLAUDE.md docs scripts/archive/README.md

Expected: 每个旧命令只出现在退役说明或历史定位中；现役写入路径只有 daily-full。

- [ ] **Step 4: 提交文档**

~~~text
git add README.md CLAUDE.md docs/learning/current-duckdb-source.md docs/workflows/daily-review-workflow.md scripts/archive/README.md
git commit -m "docs: document canonical data and retired sync entrypoint"
~~~

### Task 8: 全仓验证与交接

**Files:**

- Test: all changed tests and repository gates
- Modify: docs/superpowers/plans/2026-08-02-legacy-script-migration.md to check completed steps

- [ ] **Step 1: 运行定向测试**

~~~text
python3 -m pytest tests/test_turning_points.py tests/test_sector_analysis_data.py tests/test_backtest_sector.py tests/test_legacy_script_cli_contracts.py -q
~~~

Expected: all selected tests pass.

- [ ] **Step 2: 运行全仓 Ruff 和 pre-commit**

~~~text
pre-commit run --all-files
~~~

Expected: all hooks pass；四个 legacy 文件无需绕过 exclude。

- [ ] **Step 3: 运行全量 pytest**

~~~text
python3 -m pytest -q
~~~

Expected: no new failures compared with pre-migration baseline; existing subconscious/userspace environment failures, if present, retain the same identities.

- [ ] **Step 4: 运行 canonical read-only smoke**

~~~bash
DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb
LATEST=$(python3 -c 'import duckdb; c=duckdb.connect("/Users/a77/finance-workspace-private/db/market_feature_store.duckdb", read_only=True); print(c.execute("SELECT MAX(trade_date) FROM fact_sector_daily").fetchone()[0]); c.close()')
MARKET_FEATURE_STORE_DB="$DB" python3 scripts/backtest_sector.py --from "$LATEST" --top 1 --hold 1
~~~

Expected: command reads canonical DB, prints a date range/result, and does not create db/market.duckdb.

- [ ] **Step 5: 运行安全扫描**

~~~text
git diff --check origin/main..HEAD
git status --short
find . -maxdepth 2 \( -name 'market.duckdb' -o -name '*.pdf' -o -name '*.zip' \)
~~~

Expected: diff check passes, only intended source/test/docs files are modified, and no forbidden artifact is tracked.

- [ ] **Step 6: 更新项目交接**

向 /Users/a77/agent-memory/20_projects/finance-workspace-private.md 追加 canonical adapter、退役 writer、共享无前视引擎、测试总数，以及代码分支未合并/未部署的简短记录；运行 vault lint，按记忆手册提交并推送 memory 记录。

- [ ] **Step 7: 提交完成计划**

~~~text
git add docs/superpowers/plans/2026-08-02-legacy-script-migration.md
git commit -m "docs: mark legacy script migration plan complete"
~~~

## Self-review checklist

- [ ] spec 的每个要求都映射到至少一个 task。
- [ ] 没有引用未定义的函数或文件。
- [ ] 没有未决标记、模糊占位内容或未定义的后续动作。
- [ ] 数据写入路径与只读分析路径明确分离。
- [ ] 未授权 push 或 merge 代码分支。
