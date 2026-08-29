"""T-2 只读保证：工具层不产生写副作用（agent 只读红线）。

注册表层的完整只读性无法在零 IO 套件里对真实下游断言（那需要生产 runner
集成测试）；能钉住且值得钉住的是**连接纪律**：``intelligence/services/``
（工具实现层）里每一处 ``duckdb.connect(`` 都必须显式 ``read_only=True``
（或是把 read_only 作为形参转发的 helper 定义行）。棘轮式：新增一处
非只读连接即红。
"""

from __future__ import annotations

import re
from pathlib import Path

_SERVICES = Path(__file__).resolve().parents[2] / "services"

_CONNECT = re.compile(r"duckdb\.connect\(")
# helper 定义行的形状：def _xxx(path, *, read_only: bool)（转发形参，本身不算违规）
_FORWARDING_DEF = re.compile(r"read_only\s*(:|=)\s*(bool|read_only)")


def test_every_duckdb_connect_in_tool_layer_is_explicitly_read_only() -> None:
    violations: list[str] = []
    for path in sorted(_SERVICES.glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            if not _CONNECT.search(line) or line.lstrip().startswith("#"):
                continue
            window = " ".join(lines[number - 1 : number + 2])
            if "read_only=True" in window:
                continue
            if _FORWARDING_DEF.search(window):
                continue
            violations.append(f"{path.name}:{number}: {line.strip()}")
    assert not violations, (
        "工具实现层出现了未显式只读的 DuckDB 连接（agent 只读红线）：\n"
        + "\n".join(violations)
    )


def test_registry_surface_exposes_no_write_verbs() -> None:
    """注册表公开面不得长出写动词——契约单点强制的形状检查。"""

    from intelligence.services.research_tool_registry import ResearchToolRegistry

    public = {name for name in dir(ResearchToolRegistry) if not name.startswith("_")}
    write_verbs = {
        name
        for name in public
        if any(
            name.startswith(prefix)
            for prefix in ("write", "insert", "update", "delete", "upsert", "save")
        )
    }
    assert not write_verbs, f"注册表公开面出现写动词：{sorted(write_verbs)}"
