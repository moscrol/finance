"""正则路由棘轮：只数路由模块、只数 re.* 调用点、新增即红、基线与源码同步。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_regex_routes", REPO / "scripts" / "check_regex_routes.py")
assert _spec is not None and _spec.loader is not None
routes = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("check_regex_routes", routes)
_spec.loader.exec_module(routes)


def test_counts_re_call_sites_including_aliases_but_not_text_or_compiled_objects():
    source = '''
import re
import re as regex
_A = re.compile(r"研究|分析")          # 1
_B = regex.compile("x")                 # 2 (alias)
def f(text):
    if re.search(r"复盘", text):        # 3
        return _A.search(text)          # compiled object: not counted
    note = "re.compile(this is a string)"
    # re.match(r"comment")
    return re.sub(r"\\s+", " ", text)   # 4
'''
    assert routes.count_regex_calls(source) == 4


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_scan_covers_routing_modules_only(tmp_path):
    _write(tmp_path, "intelligence/services/route_table.py", "import re\nX = re.compile('a')\n")
    _write(tmp_path, "intelligence/services/new_intent_router.py", "import re\nre.match('a', 'b')\n")
    _write(tmp_path, "intelligence/services/numbers.py", "import re\nre.compile('\\\\d+')\n")
    _write(tmp_path, "intelligence/tests/test_route_table.py", "import re\nre.compile('a')\n")
    assert routes.scan(tmp_path) == {
        "intelligence/services/new_intent_router.py": 1,
        "intelligence/services/route_table.py": 1,
    }


def test_growth_and_new_routing_file_are_flagged_and_shrink_is_reported():
    baseline = {"a/route_table.py": 4, "a/user_task.py": 10}
    current = {"a/route_table.py": 5, "a/user_task.py": 8, "a/new_router.py": 1}
    grown, shrunk = routes.compare(current, baseline)
    assert grown == {"a/route_table.py": (4, 5), "a/new_router.py": (0, 1)}
    assert shrunk == {"a/user_task.py": (10, 8)}


def test_main_fails_on_new_regex_and_update_baseline_accepts_it(tmp_path, monkeypatch, capsys):
    _write(tmp_path, "intelligence/services/route_table.py", "import re\nX = re.compile('a')\n")
    monkeypatch.setattr(routes, "REPO", tmp_path)
    monkeypatch.setattr(routes, "BASELINE_PATH", tmp_path / "regex-routes-baseline.json")
    assert routes.main(["--update-baseline"]) == 0
    assert routes.main([]) == 0
    _write(tmp_path, "intelligence/services/route_table.py", "import re\nX = re.compile('a')\nY = re.compile('b')\n")
    assert routes.main([]) == 1
    assert "1 → 2" in capsys.readouterr().out
    assert routes.main(["--update-baseline"]) == 0
    assert routes.main([]) == 0


def test_broken_baseline_exits_2(tmp_path, monkeypatch):
    (tmp_path / "regex-routes-baseline.json").write_text('{"files": {"x": -1}}', encoding="utf-8")
    monkeypatch.setattr(routes, "REPO", tmp_path)
    monkeypatch.setattr(routes, "BASELINE_PATH", tmp_path / "regex-routes-baseline.json")
    (tmp_path / "intelligence").mkdir()
    assert routes.main([]) == 2


def test_committed_baseline_matches_source():
    """仓内基线必须与源码同步：新增规则却没更新基线，这里和 pre-commit 一起红。"""

    grown, _shrunk = routes.compare(routes.scan(REPO), routes.load_baseline(REPO / "regex-routes-baseline.json"))
    assert grown == {}, f"路由模块新增了正则：{grown}（确需新增请 --update-baseline）"
