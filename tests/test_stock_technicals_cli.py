"""`stock-technicals` / `watchlist` CLI 的门面契约。

这两个子命令是**替代飞书 skill 的唯一入口**——agent 和人都从这里进。
所以门面本身要有测试：参数名改了、口径少了、退役 skill 的去向没写，都要在这里红。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_feature_store.cli import build_parser

REPO = Path(__file__).resolve().parents[1]


def _parser():
    return build_parser()


def test_stock_technicals_accepts_the_documented_flags():
    args = _parser().parse_args(
        ["stock-technicals", "--codes", "贵州茅台", "601127",
         "--screen", "pullback", "--as-of", "2026-07-10", "--json"]
    )
    assert args.codes == ["贵州茅台", "601127"]
    assert args.screen == "pullback"
    assert args.as_of == "2026-07-10"
    assert args.json is True


def test_all_three_screens_are_reachable_from_cli():
    """三个口径分别来自 watchlist-ma / top-gainers-feishu 两个旧 skill，一个都不能丢。"""
    for screen in ("pullback", "short-pullback", "above-up"):
        args = _parser().parse_args(["stock-technicals", "--watchlist", "default",
                                     "--screen", screen])
        assert args.screen == screen


def test_unknown_screen_is_rejected_by_argparse():
    with pytest.raises(SystemExit):
        _parser().parse_args(["stock-technicals", "--screen", "编的口径"])


def test_top_sectors_exposes_the_double_red_thresholds():
    """原 sector-data 的量价齐升口径：成交额>500、涨幅>0、边际量>10%。"""
    args = _parser().parse_args(
        ["top-sectors", "--min-amount", "500", "--min-pct-chg", "0", "--min-diff-ratio", "10"]
    )
    assert (args.min_amount, args.min_pct_chg, args.min_diff_ratio) == (500.0, 0.0, 10.0)


def test_watchlist_actions():
    for action in ("show", "list", "add", "remove"):
        args = _parser().parse_args(["watchlist", action])
        assert args.action == action
    args = _parser().parse_args(["watchlist", "add", "寒武纪", "--name", "打板池"])
    assert args.items == ["寒武纪"] and args.name == "打板池"


def test_retired_feishu_skills_have_a_documented_successor():
    """旧名字还会出现在用户口中和历史对话里。dispatcher 必须能把它们改道到本地命令，
    否则 agent 会去找已经删掉的目录，然后报「功能没了」。"""
    routing = (REPO / "skills" / "dispatcher" / "SKILL.md").read_text(encoding="utf-8")
    for retired, successor in (
        ("up-line", "stock-technicals"),
        ("watchlist-ma", "stock-technicals"),
        ("top-gainers-feishu", "interval-gainers"),
        ("advancers-chart", "daily-review"),
        ("sector-data", "top-sectors"),
    ):
        assert retired in routing, f"dispatcher 没提已退役的 {retired}"
        line = next(ln for ln in routing.splitlines() if f"`{retired}`" in ln)
        assert successor in line, f"{retired} 的去处没写明 {successor}：{line}"
        assert not (REPO / "skills" / retired).exists(), f"{retired} 又被恢复了"


def test_new_skill_is_registered_with_matching_hash():
    import hashlib

    registry = json.loads((REPO / "skills.registry.json").read_text(encoding="utf-8"))
    entry = registry["skills"]["ws/stock-technicals"]
    md = REPO / entry["skillPath"]
    digest = "sha256:" + hashlib.sha256(md.read_bytes()).hexdigest()
    assert entry["computedHash"] == digest, "SKILL.md 改了但注册表哈希没重算"
    assert "UP线" in entry["triggers"] and "回踩" in entry["triggers"]


def test_interval_gainers_rendering_survives(capsys):
    """回归：新增 stock-technicals 时我在 cli.py 里定义了第二个 `_fmt_num`，
    签名不兼容，把 interval-gainers 的渲染整条打崩了——而当时 71 个相关测试
    没有一个变红。这条就是补上那个洞：渲染路径必须真的被执行过一次。"""
    from market_feature_store import cli

    res = {
        "start": "2026-08-13", "end": "2026-09-10",
        "actual_start": "2026-08-13", "actual_end": "2026-09-10",
        "min_amount": 1.0, "metadata_date": "2026-09-10",
        "stocks": [
            {"stock_ts_code": "601127.SH", "stock_name": "赛力斯", "sw_l1": "汽车",
             "sectors": "新能源车", "avg_amount": 25.2, "interval_gain": 12.5,
             "weighted_gain": 3.1, "up_deviation_pct": -4.5},
            # 每个数值字段都给 None：渲染层用 _fmt_num 的全部意义就是容忍它们
            {"stock_ts_code": "300001.SZ", "stock_name": "某某", "sw_l1": None,
             "sectors": None, "avg_amount": None, "interval_gain": None,
             "weighted_gain": None, "up_deviation_pct": None},
        ],
    }
    cli._print_interval_stock_rank(res, 2, "区间涨幅排行", "interval_gain")
    out = capsys.readouterr().out

    assert "601127.SH" in out and "25.2" in out and "12.50" in out
    # 第二行五个字段全 None，必须渲染成 - 而不是抛异常
    second = [ln for ln in out.splitlines() if "300001.SZ" in ln][0]
    assert second.count("| - |") + second.count("| - ") >= 4, second


def test_cli_has_no_duplicate_top_level_functions():
    """同名函数定义两次时，后者静默覆盖前者——上面那次事故就是这么来的。"""
    import ast
    import collections

    tree = ast.parse((REPO / "market_feature_store" / "cli.py").read_text(encoding="utf-8"))
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    dupes = [n for n, c in collections.Counter(names).items() if c > 1]
    assert dupes == [], f"cli.py 里这些函数被定义了不止一次: {dupes}"
