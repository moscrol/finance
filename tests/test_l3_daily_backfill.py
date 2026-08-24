from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "daily-full-review" / "scripts" / "l3_daily_backfill.py"


def _load():
    spec = importlib.util.spec_from_file_location("l3_daily_backfill", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_html_matrix_takes_only_the_requested_date_row(tmp_path: Path) -> None:
    mod = _load()
    html = tmp_path / "matrix.html"
    html.write_text(
        '<table><tr><td class="date">2026-06-05</td><td>688017.SH 绿的谐波</td></tr>'
        '<tr><td class="date">2026-08-24</td><td>T1 002716.SZ 湖南白银</td>'
        "<td>T2 000831.SZ 中国稀土</td></tr></table>",
        encoding="utf-8",
    )

    assert mod._matrix_codes(html, "2026-08-24") == ["002716", "000831"]
    assert mod._matrix_codes(html, "2026-06-05") == ["688017"]
    assert mod._matrix_codes(html, "2026-08-21") == []


def test_html_matrix_without_date_stays_empty(tmp_path: Path) -> None:
    mod = _load()
    html = tmp_path / "matrix.html"
    html.write_text('<tr><td class="date">2026-08-24</td><td>002716.SZ</td></tr>', encoding="utf-8")
    assert mod._matrix_codes(html) == []


def test_custom_md_still_reads_all_codes(tmp_path: Path) -> None:
    mod = _load()
    md = tmp_path / "tonight.md"
    md.write_text("湖南白银 002716.SZ\n中国稀土 000831.SZ\n", encoding="utf-8")
    assert mod._matrix_codes(md, "2026-08-24") == ["002716", "000831"]
