"""活代码引用的 ``scripts.<name>`` 模块必须存在（`R-20260828-04`）。

## 治的形状

2026-08-20 的 `a41e86df`「24 个全仓零引用的孤儿脚本移入 scripts/archive/」用的
「零引用」判据**只认静态 import**，不认**字符串形式的模块引用**——而
`python -m scripts.X` 的模块名在源码里就是一个普通字符串：

    subprocess.run([python, "-m", "scripts.sync_akshare_market_snapshot", ...])
    /usr/bin/python3 -m scripts.forecast_learning_loop prompt --limit 5

于是同一个洞复发了三轮，每轮都靠事故发现：

| 轮次 | PR | 移回 | 发现方式 |
|---|---|---|---|
| 1 | #453 | 5 个脚本 | main 测试收集炸 |
| 2 | #472 | `theme_radar_quality_rules` | 两处生产引用 |
| 3 | 本单 | `sync_akshare_market_snapshot` / `forecast_learning_loop` | 逐个反查 |

前两轮修的都是**实例**，判据本身没动，所以第四次复发只是时间问题。本测试是
**判据**：对未来任何一次归档 sweep 一律生效，不需要维护实例清单。

## 两类故障都是静默的（所以门禁必须在测试层）

- `sync_akshare_market_snapshot`：子进程非零退出被吞成「AkShare 今天没取到」，
  与真实网络失败在读数上不可分辨——兜底 provider 死了 8 天无人知。
- `forecast_learning_loop`：launchd 工作日 09:10 的双盲链，三处调用两处 `|| true`，
  第三处 `LEARNING_CONTEXT=$(... prompt ...)` 拿到空串继续跑——每日答卷**静默地
  不再注入已批准的 lessons/rules**。

## 判据形状（为什么不是「扫所有 scripts. 出现」）

只认两种**无歧义**的引用形式：

1. ``-m`` 后面跟的模块名（子进程/shell 调用），跨 .py 与 .sh 同一条正则；
2. 真 import 语句——经 **AST** 取，不是正则。

AST 而非正则是关键：`intelligence/tests/test_rag_worker.py` 把
``from scripts.rag_freshness import IMPORT_CONTEXT`` 写在一个**字符串**里，
那是喂给临时目录的合成夹具（模拟知识库仓），不是本仓引用。正则会误报，
AST 看到的是 `Constant` 不是 `Import`，天然分得开。

同理排除掉的正则噪声：``scripts.mkdir()``（变量名恰好叫 scripts）、
``market_feature_store.scripts.verify_mainline_sector_daily``（另一个包的尾巴）、
注释里的 ``import scripts.x`` 举例。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

# 不扫的树：归档区自身、外部/临时检出、文档。
_SKIP_PARTS = {".git", "tmp", "archive", "node_modules", ".venv", ".venv-workbench"}

# ``-m`` 与模块名之间可能隔着引号、逗号、空白（python 列表参数 / shell 命令行）。
# 前置 (?<![\w.-]) 防止匹配到 `--some-m` 之类的尾巴。
_DASH_M_RE = re.compile(
    r"(?<![\w.-])-m['\"]?[,\s]+['\"]?scripts\.([A-Za-z_][A-Za-z0-9_]*)"
)


def _live_files(suffixes: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for path in REPO.rglob("*"):
        if path.suffix not in suffixes or not path.is_file():
            continue
        if _SKIP_PARTS & set(path.relative_to(REPO).parts):
            continue
        # 扫描器不扫自己：本文件的说明文字里就有 ``-m scripts.X`` 这样的
        # 举例，那是文档不是引用。
        if path.resolve() == Path(__file__).resolve():
            continue
        out.append(path)
    return out


def _dash_m_references() -> dict[str, list[str]]:
    """``-m scripts.X`` 形式（.py 字符串字面量 + .sh 命令行）。"""
    found: dict[str, list[str]] = {}
    for path in _live_files((".py", ".sh")):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name in _DASH_M_RE.findall(text):
            found.setdefault(name, []).append(str(path.relative_to(REPO)))
    return found


def _import_references() -> dict[str, list[str]]:
    """真 import 语句，经 AST 取——字符串里的 import 不算（合成夹具）。"""
    found: dict[str, list[str]] = {}
    for path in _live_files((".py",)):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("scripts."):
                        found.setdefault(
                            alias.name.split(".")[1], []
                        ).append(str(path.relative_to(REPO)))
                continue
            if module.startswith("scripts."):
                found.setdefault(module.split(".")[1], []).append(
                    str(path.relative_to(REPO))
                )
    return found


def _missing(references: dict[str, list[str]]) -> list[str]:
    bad = []
    for name, sites in sorted(references.items()):
        target = SCRIPTS / f"{name}.py"
        if target.is_file() or (SCRIPTS / name).is_dir():
            continue
        archived = SCRIPTS / "archive" / f"{name}.py"
        hint = "（就在 scripts/archive/，移回即可）" if archived.is_file() else ""
        bad.append(f"scripts/{name}.py 不存在{hint}；引用点：{', '.join(sorted(set(sites)))}")
    return bad


def test_dash_m_module_references_resolve() -> None:
    """``python -m scripts.X`` 的 X 必须在 scripts/ 下真实存在。

    这是归档 sweep 唯一漏认的引用形式，两次生产静默故障都出在这里。
    """
    references = _dash_m_references()
    # 判据自身要有牙：扫不到任何引用说明正则失效了，那是一道假门禁。
    assert references, "未扫到任何 -m scripts.X 引用——正则或扫描面失效"
    missing = _missing(references)
    assert not missing, "活代码 -m 引用了不存在的模块：\n" + "\n".join(missing)


def test_import_statement_module_references_resolve() -> None:
    """``from scripts.X import ...`` / ``import scripts.X`` 的 X 必须存在。"""
    references = _import_references()
    assert references, "未扫到任何 scripts.X import——AST 扫描面失效"
    missing = _missing(references)
    assert not missing, "活代码 import 了不存在的模块：\n" + "\n".join(missing)


def test_scanner_ignores_imports_written_inside_string_fixtures() -> None:
    """反向锁：合成夹具字符串里的 import 不得被算成本仓引用。

    没有这条，把 AST 换回正则也能让上面两条绿——那是一道会误报的假门禁
    （`test_rag_worker.py` 写进临时目录的 `scripts.rag_freshness` 就会中招）。
    """
    assert "rag_freshness" not in _import_references()
    assert "rag_freshness" not in _dash_m_references()
