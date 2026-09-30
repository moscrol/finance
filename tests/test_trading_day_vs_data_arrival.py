"""「今天开不开市」与「今天的数据到没到」必须分开判（工单 #52）。

事故形状（2026-09-11 实测命中）：旧 `is_trading_day` 用当日 `fact_stock_daily`
行数 `>= MIN_DAILY_ROWS` 代理「今天是不是交易日」。库可读但当天 0 行时返回
`(False, approximate=False)`——把**同步失败的真交易日**自信地判成休市，连「这是
近似」的标记都不给。`run_l2_pipeline.sh` 随即打印「非交易日，跳过」并 `exit 0`：
静默报成功，L2 整天没跑。

反向校验（2026-09-12 实测，读生产库）：2026-01-01..2026-09-11 区间内，休市表与
库里实际有行的 168 个交易日**零冲突**，唯一一条不符就是 09-11——足以证明当天是
真交易日、判错的是那条行数代理，而不是休市表。

两组断言，缺一不可：

* **模块层**：用户点名的四种情形（交易日零行 / 部分入库 / 工作日休市 /
  数据库不可读）各自判成什么，外加 `UNKNOWN` 不得被当成「不用干活」。
* **守卫层**：真的去跑 `run_l2_pipeline.sh`（四个步骤脚本换成 stub，全程离线），
  断言**哪些步骤真的跑了**。缺陷住在那层 shell 胶水里——模块判对了但 shell 只取
  布尔值，一样会丢掉一天，只测 Python 抓不到。
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import duckdb
import pytest

from market_feature_store.trading_days import (
    CLOSED,
    DATA_UNKNOWN,
    MISSING,
    PARTIAL,
    PRESENT,
    TRADING,
    UNKNOWN,
    closed_dates,
    is_trading_day,
    is_trading_day_detailed,
    market_data_state,
    recent_trading_dates,
    trading_day_verdict,
)

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "moneyflow" / "run_l2_pipeline.sh"

#: 事故日：周五、真交易日、fact_stock_daily 当天 0 行。
INCIDENT = "2026-09-11"
#: 过去的工作日休市日（端午，周五）。**必须取过去的日期**——`future` 分支排在
#: 休市表之前，拿 2026-10-01 之类的未来休市日会得到 source=future，测不到休市表。
WEEKDAY_CLOSURE = "2026-06-19"
#: 休市表里没有 2025 年，且该日已过去（周一）→ 判定 UNKNOWN。
UNKNOWN_YEAR_DAY = "2025-03-03"
SATURDAY = "2026-09-12"


def _seed(path: Path, trade_date: str, rows: int) -> None:
    """建一张只有 `trade_date` 的 `fact_stock_daily`。

    这里用最小夹具是成立的：被测查询只有
    `SELECT COUNT(*) FROM fact_stock_daily WHERE trade_date = ?`，除 `trade_date`
    之外一列都不碰，没有 ON CONFLICT 之类依赖主键的路径。类型照生产取 `DATE`
    （schema.sql:306），免得夹具用 VARCHAR 时字符串比字符串恰好也过、把类型处理
    测成假绿。
    """
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE fact_stock_daily (trade_date DATE, stock_ts_code TEXT)")
    if rows:
        con.execute(
            "INSERT INTO fact_stock_daily "
            f"SELECT ?::DATE, 'x' || i FROM range({int(rows)}) t(i)",
            [trade_date],
        )
    con.close()


# ---------------------------------------------------------------------------
# 模块层：四种情形 + UNKNOWN 的处置
# ---------------------------------------------------------------------------


def test_trading_day_with_zero_rows_is_still_a_trading_day(tmp_path):
    """① 交易日零行 —— 事故复现位。行情没到，日历该说什么还说什么。"""
    db = tmp_path / "m.duckdb"
    _seed(db, INCIDENT, 0)

    assert trading_day_verdict(INCIDENT).verdict == TRADING
    assert market_data_state(INCIDENT, db_path=str(db)) == MISSING
    # 旧实现这里返回 False，于是 L2 被跳过。这一条钉住的就是那个回归。
    assert is_trading_day(INCIDENT) is True


def test_partially_synced_day_is_still_a_trading_day(tmp_path):
    """② 部分入库 —— 同步跑了一半，是数据面 partial，不是「今天不开市」。"""
    db = tmp_path / "m.duckdb"
    _seed(db, INCIDENT, 10)

    assert trading_day_verdict(INCIDENT).verdict == TRADING
    assert market_data_state(INCIDENT, db_path=str(db)) == PARTIAL
    assert is_trading_day(INCIDENT) is True


def test_fully_synced_day_reports_present(tmp_path):
    """变异对照：行数够时数据面必须是 present，否则 partial 这档等于恒真。"""
    db = tmp_path / "m.duckdb"
    _seed(db, INCIDENT, 3200)

    assert market_data_state(INCIDENT, db_path=str(db)) == PRESENT


def test_weekday_exchange_closure_is_closed(tmp_path):
    """③ 工作日休市 —— 工作日但在交易所公告休市表内，判 CLOSED。"""
    db = tmp_path / "m.duckdb"
    _seed(db, WEEKDAY_CLOSURE, 0)

    verdict = trading_day_verdict(WEEKDAY_CLOSURE)
    assert verdict.verdict == CLOSED
    assert verdict.source == "sse_closure", "应由休市表命中，不是被 weekend/future 抢先"
    assert is_trading_day(WEEKDAY_CLOSURE) is False


def test_unreadable_db_does_not_change_the_calendar_verdict():
    """④ 数据库不可读 —— 日历判定根本不读库，库挂了也不影响它。

    这是本次拆分最实在的收益：判「开不开市」不再有数据依赖，
    连 duckdb 没装都能答对（`market_data_rows` 内 import 是惰性的）。
    """
    missing_db = "/nonexistent/nope.duckdb"

    assert trading_day_verdict(INCIDENT).verdict == TRADING
    assert is_trading_day(INCIDENT, db_path=missing_db) is True
    # 库读不了 ≠ 库里没有：前者不知道，后者知道没有。两者不能合并成一个值。
    assert market_data_state(INCIDENT, db_path=missing_db) == DATA_UNKNOWN
    assert market_data_state(INCIDENT, db_path=missing_db) != MISSING


def test_unknown_year_is_unknown_and_still_gets_work_done():
    """休市表没有该年份 → UNKNOWN，且 `is_trading_day` 必须返回 True。

    「判不出来」不能走成「不用干活」——那正是静默跳过的形状。宁可跑到上游
    真实失败（上游会失败得很响），也不要 exit 0 装作没事。
    """
    verdict = trading_day_verdict(UNKNOWN_YEAR_DAY)
    assert verdict.verdict == UNKNOWN
    assert verdict.source == "calendar_year_missing"
    assert is_trading_day(UNKNOWN_YEAR_DAY) is True

    ok, uncertain = is_trading_day_detailed(UNKNOWN_YEAR_DAY)
    assert (ok, uncertain) == (True, True), "不确定要能被调用方看见，不能悄悄抹平"


def test_weekend_is_closed_without_consulting_the_closure_table():
    verdict = trading_day_verdict(SATURDAY)
    assert (verdict.verdict, verdict.source) == (CLOSED, "weekend")
    # 周末不依赖休市表，所以表里没有的年份照样判得准。
    assert trading_day_verdict("2025-03-01").source == "weekend"


def test_future_date_is_closed_with_future_source():
    future = date(date.today().year + 1, 3, 4).isoformat()
    verdict = trading_day_verdict(future)
    assert verdict.verdict == CLOSED
    assert verdict.source == "future", "未来日期不预写，但判据要和真休市区分开"


@pytest.mark.parametrize(
    "flag,expected",
    [("L2_FORCE_TRADE_DAY", TRADING), ("L2_FORCE_NON_TRADE_DAY", CLOSED)],
)
def test_env_overrides_win(monkeypatch, flag, expected):
    monkeypatch.setenv(flag, "1")
    verdict = trading_day_verdict(SATURDAY if expected == TRADING else INCIDENT)
    assert verdict.verdict == expected
    assert verdict.source == "env_override"


def test_closed_dates_distinguishes_unknown_year_from_no_closures():
    assert closed_dates(2027) is None, "未登记年份必须是 None，不能是空集合"
    assert closed_dates(2026) is not None
    assert date(2026, 10, 1) in closed_dates(2026)


def test_recent_trading_dates_skips_closures_and_weekends():
    days = recent_trading_dates(3, end=date(2026, 6, 22))
    assert days == [date(2026, 6, 22), date(2026, 6, 18), date(2026, 6, 17)], (
        "6-19 端午休市、6-20/21 周末，都该跳过"
    )


def test_recent_trading_dates_terminates_on_unknown_years():
    """表外年份全是 UNKNOWN，凑不满 n 也必须退出，不能死循环。"""
    assert recent_trading_dates(3, end=date(2024, 5, 6)) == []


# ---------------------------------------------------------------------------
# 守卫层：真跑 run_l2_pipeline.sh，断言哪些步骤跑了
# ---------------------------------------------------------------------------

_STUB = """import os, sys
with open(os.environ["L2_STEP_LOG"], "a") as fh:
    fh.write({name!r} + "\\n")
"""


@pytest.fixture
def guard_env(tmp_path):
    """搭一个假 CODE_ROOT：真 `market_feature_store` + stub 掉的步骤脚本。

    `market_feature_store` 用软链接指向仓内真包——探针走的是产品代码，不是副本。
    步骤脚本（日历台账 write_to_duckdb、日包管线 run_l2_from_share、渲染）换成 stub，
    所以全程不下载日包、不写生产库、不出网；假 DATA_ROOT 里放一个空的分享入口文件，
    否则交易日会在前置件检查处 exit 2。
    """
    code_root = tmp_path / "code"
    moneyflow = code_root / "scripts" / "moneyflow"
    moneyflow.mkdir(parents=True)
    (code_root / "market_feature_store").symlink_to(ROOT / "market_feature_store")

    for name in ("write_to_duckdb", "run_l2_from_share"):
        (moneyflow / f"{name}.py").write_text(_STUB.format(name=name))
    (code_root / "scripts" / "render_moneyflow_html.py").write_text(
        _STUB.format(name="render")
    )

    data_root = tmp_path / "data"
    (data_root / "state").mkdir(parents=True)
    (data_root / "state" / "l2-baidu-share.json").write_text("{}")
    step_log = tmp_path / "steps.log"

    env = dict(os.environ)
    env.update(
        {
            # HOME 指向 tmp：百度网盘 Cookie 库按家目录解析，测试自洽不碰真登录态。
            "HOME": str(tmp_path),
            "L2_LOCK_HELD": "1",  # 不抢全量复盘的锁
            "FINANCE_CODE_ROOT": str(code_root),
            "FINANCE_DATA_ROOT": str(data_root),
            "L2_STEP_LOG": str(step_log),
            # 探针用跑测试的解释器：脚本缺省 python3 且把 /opt/homebrew/bin 排在 PATH 最前，
            # 宿主那份 python3 有没有 duckdb 因机而异（09-30 GitHub macOS runner 上没有 →
            # 库读不了 → data=unknown），测的就成了宿主环境而不是守卫逻辑。
            "FINANCE_PYTHON": sys.executable,
        }
    )
    for leak in ("L2_FORCE_TRADE_DAY", "L2_FORCE_NON_TRADE_DAY"):
        env.pop(leak, None)
    return env, step_log, tmp_path


def _run_guard(env, day, db=None):
    env = dict(env)
    env["MARKET_FEATURE_STORE_DB"] = str(db) if db else "/nonexistent/nope.duckdb"
    proc = subprocess.run(
        ["/bin/zsh", str(GUARD), day],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return proc


def _steps(step_log: Path) -> list[str]:
    if not step_log.exists():
        return []
    return step_log.read_text().split()


def test_guard_skips_only_on_a_real_closure(guard_env):
    """真休市日：跳过全部步骤并 exit 0。这是唯一允许「什么都不干还算成功」的情形。"""
    env, step_log, _ = guard_env
    proc = _run_guard(env, WEEKDAY_CLOSURE)

    assert proc.returncode == 0
    assert "verdict=closed" in proc.stdout
    assert "source=sse_closure" in proc.stdout
    assert _steps(step_log) == ["write_to_duckdb"], "休市日只落日历台账（QC S2），不跑管线步骤"


def test_guard_runs_the_pipeline_on_a_zero_row_trading_day(guard_env, tmp_path):
    """事故复现位：真交易日 + 当日 0 行，必须照跑，不得跳过。

    旧实现在这里 `exit 0`，L2 丢一整天。这条是本工单的核心回归钉。
    """
    env, step_log, _ = guard_env
    db = tmp_path / "empty.duckdb"
    _seed(db, INCIDENT, 0)

    proc = _run_guard(env, INCIDENT, db=db)

    assert "verdict=trading" in proc.stdout
    assert "data=missing" in proc.stdout
    assert _steps(step_log) == [
        "write_to_duckdb",  # --calendar：日历判定落台账（QC S2），每跑必写
        "run_l2_from_share",  # 日包管线：转存 / 下载 / 解包 / 三榜 / 写库都在它里面（进程内调用 write_to_duckdb）
        "render",
    ], "交易日零行必须把整条链跑完"
    # 行情缺口要在日志里说清，别让值班的人误判成 L2 坏了。
    assert "行情缺口，不是 L2 故障" in proc.stderr


@pytest.mark.parametrize("relative", [True, False])
def test_guard_keeps_interpreter_valid_after_chdir(guard_env, relative):
    import sys

    env, step_log, root = guard_env
    python = root / ".venv-workbench" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    env["FINANCE_PYTHON"] = ".venv-workbench/bin/python" if relative else str(python)
    env["MARKET_FEATURE_STORE_DB"] = str(root / "absent.duckdb")
    proc = subprocess.run(
        ["/bin/zsh", str(GUARD), INCIDENT], cwd=root, env=env,
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "verdict=trading" in proc.stdout
    assert _steps(step_log) == ["write_to_duckdb", "run_l2_from_share", "render"]


def test_guard_runs_and_shouts_when_the_calendar_is_unknown(guard_env):
    """判不定：照跑 + 吼一声。绝不允许「什么都没干却 exit 0」。"""
    env, step_log, _ = guard_env
    proc = _run_guard(env, UNKNOWN_YEAR_DAY)

    assert "verdict=unknown" in proc.stdout
    assert "source=calendar_year_missing" in proc.stdout
    assert "交易日判不定" in proc.stderr
    assert _steps(step_log), "判不定时步骤必须真的跑过，不能静默跳过"


def test_guard_treats_a_broken_probe_as_unknown_not_as_closure(guard_env, tmp_path):
    """探针自己挂了也不许跳过：import 失败必须归 unknown，照跑。

    反向对照——把假 CODE_ROOT 里的 `market_feature_store` 软链拆掉，
    探针必然 ImportError。旧写法 `2>/dev/null || true` 会让它变成空输出，
    和「判定说休市」在日志里长得一模一样。
    """
    env, step_log, root = guard_env
    (root / "code" / "market_feature_store").unlink()

    proc = _run_guard(env, INCIDENT)

    assert "verdict=unknown" in proc.stdout
    assert "probe_failed" in proc.stdout or "probe_unparseable" in proc.stdout
    assert _steps(step_log), "探针挂了也要干活，不能当成休市"


def test_guard_still_honours_the_force_non_trade_day_escape_hatch(guard_env):
    """排障开关仍有效，否则值班的人没法手动压掉一天。"""
    env, step_log, _ = guard_env
    env = dict(env)
    env["L2_FORCE_NON_TRADE_DAY"] = "1"

    proc = _run_guard(env, INCIDENT)

    assert proc.returncode == 0
    assert "verdict=closed" in proc.stdout
    assert "source=env_override" in proc.stdout
    assert _steps(step_log) == ["write_to_duckdb"]  # 只落日历台账（QC S2）
