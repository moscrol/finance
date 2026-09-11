"""本地自选股清单。

原先这份清单只活在飞书多维表格里，要用它得先拿 token 再拉表——所以清单一旦
断网/掉权限就整条链失效，事实上它已经三个月没人写了。这里把它落到本地：
纯文本，一行一只，`#` 起头是注释。

位置默认 ``~/.finance-runtime/watchlists``，可用 ``FINANCE_WATCHLIST_DIR`` 改。
**故意不放进仓库**：这是用户的持仓意图，不是代码。
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DIR = Path.home() / ".finance-runtime" / "watchlists"


def watchlist_dir() -> Path:
    return Path(os.environ.get("FINANCE_WATCHLIST_DIR") or DEFAULT_DIR)


def watchlist_path(name: str = "default") -> Path:
    safe = str(name).strip() or "default"
    if "/" in safe or safe.startswith("."):
        raise ValueError(f"清单名不合法: {name!r}")
    return watchlist_dir() / f"{safe}.txt"


def load_watchlist(name: str = "default") -> list[str]:
    """读一个清单。不存在就返回空列表——让调用方决定是报错还是忽略。"""
    path = watchlist_path(name)
    if not path.exists():
        return []
    items: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry and entry not in items:
            items.append(entry)
    return items


def save_watchlist(items, name: str = "default", header: str | None = None) -> Path:
    path = watchlist_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if header:
        lines.extend(f"# {ln}" for ln in header.splitlines())
    seen: set[str] = set()
    for item in items:
        entry = str(item).strip()
        if entry and entry not in seen:
            seen.add(entry)
            lines.append(entry)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def list_watchlists() -> list[str]:
    directory = watchlist_dir()
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.txt"))
