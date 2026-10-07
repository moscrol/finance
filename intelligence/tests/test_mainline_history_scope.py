"""The dataset snapshot date is not a theme's observed/current membership date."""
from pathlib import Path

import duckdb
import pytest

from intelligence.services.agent_research import block_lines_to_evidence
from intelligence.services.ask_blocks import _mainline_context_block_for_llm


@pytest.fixture
def scope_db(tmp_path: Path) -> Path:
    path = tmp_path / 'scope.duckdb'
    with duckdb.connect(str(path)) as con:
        con.execute('''create table fact_mainline_sector_daily(
          trade_date date, theme_name varchar, sector_ts_code varchar, sector_name varchar,
          sort_no integer, cycle_status varchar, cycle_level varchar, today_pct double,
          limit_up_count integer, startup_date_small date, high_status_label varchar,
          near_breakout_label varchar, amount double)''')
        con.execute('''create table fact_sector_daily(
          trade_date date, sector_ts_code varchar, sw_l1 varchar, pct_chg double,
          diff_ratio double, amount double)''')
        rows = [('2026-06-19', '旧甲', 'before'), ('2026-06-20', '旧甲', 'boundary'),
                ('2026-07-09', '旧甲', 'old1'), ('2026-07-09', '旧甲', 'old2'),
                ('2026-07-09', '现甲', 'current1'), ('2026-07-10', '现甲', 'current2'),
                ('2026-07-10', '现乙', 'current3'), ('2026-07-11', '未来甲', 'future')]
        con.executemany('''insert into fact_mainline_sector_daily
          (trade_date,theme_name,sector_ts_code,sector_name,sort_no,today_pct,amount)
          values (?,?,?,?,1,1.2,100000)''', [(day,theme,code,code) for day,theme,code in rows])
    return path


def render(path: Path, **kwargs) -> str:
    return _mainline_context_block_for_llm('市场结构', None, path, as_of='2026-07-10', **kwargs)


def history(block: str) -> str:
    return next(line for line in block.splitlines() if line.startswith('- 主线持续性：'))


def test_explicit_calendar_window_not_implicit_twenty_trading_days(scope_db):
    line = history(render(scope_db))
    assert '本表查询窗口2026-06-20~2026-07-10（含边界，回看参数20自然日）' in line
    assert '非截止日主线排名' in line
    assert '近20日出现' not in line


def test_historical_occurrence_does_not_become_snapshot_membership(scope_db):
    line = history(render(scope_db))
    assert '截止日2026-07-10' in line
    assert '旧甲：出现2天、板块行3，已观测日期2026-06-20~2026-07-09，截止日记录=未见' in line


def test_current_membership_positive_not_blanket_historical_rejection(scope_db):
    line = history(render(scope_db))
    assert '现甲：出现2天、板块行2，已观测日期2026-07-09~2026-07-10，截止日记录=有' in line
    assert '现乙：出现1天、板块行1，已观测日期2026-07-10~2026-07-10，截止日记录=有' in line


def test_missing_row_is_scoped_to_table_not_world_absence(scope_db):
    line = history(render(scope_db))
    assert '截止日记录仅指本表是否收录，不等于市场存在或不存在' in line
    assert line.index('不等于市场存在或不存在') < line.index('旧甲：')


def test_distinct_day_count_is_not_sector_row_count(scope_db):
    line = history(render(scope_db))
    assert '旧甲：出现2天、板块行3' in line
    assert '旧甲：出现3天' not in line


def test_as_of_excludes_future_facts_and_membership(scope_db):
    block = render(scope_db)
    assert '未来甲' not in block
    assert '2026-07-11' not in block
    assert '旧甲：' in history(block)


def test_window_boundary_inclusive_without_changing_query(scope_db):
    line = history(render(scope_db))
    assert '2026-06-20~2026-07-09' in line
    assert '2026-06-19' not in line


def test_nondefault_lookback_renders_actual_boundaries(scope_db):
    line = history(render(scope_db, lookback_days=1))
    assert '本表查询窗口2026-07-09~2026-07-10（含边界，回看参数1自然日）' in line
    assert '旧甲：出现1天、板块行2，已观测日期2026-07-09~2026-07-09，截止日记录=未见' in line


def test_current_membership_does_not_depend_on_thirty_row_preview(scope_db):
    with duckdb.connect(str(scope_db)) as con:
        con.executemany('''insert into fact_mainline_sector_daily
          (trade_date,theme_name,sector_ts_code,sector_name,sort_no,today_pct,amount)
          values ('2026-07-10','AAA',?,?,?,1.2,100000)''',
          [(f'a{i}',f'a{i}',i) for i in range(31)])
    block = render(scope_db)
    assert '现乙核心板块' not in block  # deterministic current-row preview was truncated
    assert '现乙：出现1天、板块行1，已观测日期2026-07-10~2026-07-10，截止日记录=有' in history(block)


def test_snapshot_freshness_retained_and_scope_survives_evidence_projection(scope_db):
    block = render(scope_db)
    items, _ = block_lines_to_evidence('mainline_context', block, 'fixture',
                                      limit=12, detail_chars=1000, source_date='2026-07-10')
    card = next(item for item in items if item.detail.startswith('主线持续性：'))
    assert card.source_date == '2026-07-10'
    assert card.detail == history(block).removeprefix('- ')
    assert '截止日记录=未见' in card.detail and '截止日记录=有' in card.detail
    assert card.content_hash


@pytest.mark.parametrize(('limit_up_count', 'expected_label'), [
    (None, '涨停未提供'),
    (0, '涨停0'),
    (7, '涨停7'),
])
def test_current_sector_limit_up_count_preserves_missing_and_observed_values(
    scope_db, limit_up_count, expected_label,
):
    with duckdb.connect(str(scope_db)) as con:
        con.execute('''update fact_mainline_sector_daily set limit_up_count = ?
          where trade_date = '2026-07-10' ''', [limit_up_count])

    block = render(scope_db)
    items, _ = block_lines_to_evidence('mainline_context', block, 'fixture',
                                      limit=12, detail_chars=1000, source_date='2026-07-10')
    for theme_name in ('现甲', '现乙'):
        line = next(line for line in block.splitlines()
                    if line.startswith(f'- {theme_name}核心板块：'))
        assert f'亿，{expected_label}，' in line
        card = next(item for item in items
                    if item.detail.startswith(f'{theme_name}核心板块：'))
        assert card.detail == line.removeprefix('- ')
        assert f'亿，{expected_label}，' in card.detail


def test_existing_current_sector_facts_remain(scope_db):
    block = render(scope_db)
    assert '现甲核心板块：' in block
    assert '涨1.20%' in block
    assert '现乙核心板块：' in block


def test_missing_database_still_has_no_invented_scope(tmp_path):
    assert render(tmp_path/'missing.duckdb') == ''
