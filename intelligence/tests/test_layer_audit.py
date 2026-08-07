"""门禁自己的门禁。

`scripts/layer_audit.py` 是唯一拦住「领域层 import loop 底座」的东西，此前零测试——
门禁失效不会有任何信号，只会安静放行。本文件锁住它的识别面。

所有用例都在 tmp_path 里造假树，不往 `intelligence/services/` 写探针文件：全量
测试跑起来时 `_source_files()` 会 rglob 整个包，真探针会被扫进去污染真实审计结果。

八种写法（前五条锁当前行为，后三条锁本轮修复与已知盲区）：

    from intelligence.runtime.agent_episode import X   → ERROR
    from intelligence.runtime import agent_episode     → ERROR
    import intelligence.runtime.agent_episode          → ERROR
    函数体内延迟 import                                 → ERROR（且标 in_function）
    TYPE_CHECKING 块内                                  → WARN（分级正确，不拦截）
    from intelligence import runtime                   → ERROR（本轮修复）
    import intelligence.runtime                        → ERROR（本轮修复）
    importlib.import_module("intelligence.runtime.…")  → 放行（已知盲区，AST 兜不住）
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_AUDIT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "layer_audit.py"


def _load_audit() -> ModuleType:
    """按路径加载：`scripts/` 没有 __init__.py，不是可 import 的包。

    必须在 exec_module 前把模块注册进 sys.modules，否则模块内的 dataclass
    在解析注解时找不到自己所在的命名空间（dataclasses.py 用 sys.modules.get(
    cls.__module__) 拿 __dict__，返回 None 时直接 AttributeError）。
    """
    _MOD_NAME = "_layer_audit_under_test"
    spec = importlib.util.spec_from_file_location(_MOD_NAME, _AUDIT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = module  # 必须在 exec_module 前注册
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[_MOD_NAME]
        raise
    return module


@pytest.fixture
def audit_on(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """把门禁指向一棵假树，返回「喂一段 services 源码 → 拿违规列表」的调用口。"""

    def _run(source: str):
        module = _load_audit()
        pkg_root = Path(tmp_path) / "intelligence"
        (pkg_root / "runtime").mkdir(parents=True, exist_ok=True)
        (pkg_root / "services").mkdir(parents=True, exist_ok=True)

        # 假树必须真有 runtime/ 目录和模块，_resolve_layers 才走目录口径。
        (pkg_root / "runtime" / "__init__.py").write_text("", encoding="utf-8")
        (pkg_root / "runtime" / "agent_episode.py").write_text("", encoding="utf-8")
        (pkg_root / "services" / "__init__.py").write_text("", encoding="utf-8")
        (pkg_root / "services" / "probe.py").write_text(source, encoding="utf-8")

        monkeypatch.setattr(module, "PKG_ROOT", pkg_root)
        monkeypatch.setattr(module, "RUNTIME_DIR", pkg_root / "runtime")
        violations, _criterion, _count = module.collect_violations()
        return [v for v in violations if v.src == "services.probe"]

    return _run


def test_from_submodule_import_symbol_is_error(audit_on):
    violations = audit_on(
        "from intelligence.runtime.agent_episode import EpisodeEvent\n"
    )

    assert [v.level for v in violations] == ["ERROR"]
    assert violations[0].tgt == "runtime.agent_episode"


def test_from_package_import_submodule_is_error(audit_on):
    # `from intelligence.runtime import agent_episode` 经 _imported_modules 返回
    # ["runtime", "runtime.agent_episode"]——包本身和子模块都在 runtime_layer，
    # 所以正确地触发两条 ERROR。两条都要报，才能让工具提示「整个 runtime 层都别碰」。
    violations = audit_on("from intelligence.runtime import agent_episode\n")

    assert len(violations) == 2
    assert all(v.level == "ERROR" for v in violations)
    targets = {v.tgt for v in violations}
    assert "runtime" in targets
    assert "runtime.agent_episode" in targets


def test_plain_import_submodule_is_error(audit_on):
    violations = audit_on("import intelligence.runtime.agent_episode\n")

    assert [v.level for v in violations] == ["ERROR"]
    assert violations[0].tgt == "runtime.agent_episode"


def test_deferred_import_inside_function_is_error(audit_on):
    # 延迟 import 仍是运行时耦合，只是位置更隐蔽；必须标出 in_function 供人工核查。
    violations = audit_on(
        "def build():\n"
        "    from intelligence.runtime.agent_episode import EpisodeEvent\n"
        "    return EpisodeEvent\n"
    )

    assert [v.level for v in violations] == ["ERROR"]
    assert violations[0].in_function is True


def test_type_checking_import_is_warn_not_error(audit_on):
    # 分级正确才是这条的重点：契约耦合要看见，但一刀切会逼人改用 Any 规避。
    violations = audit_on(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from intelligence.runtime.agent_episode import EpisodeEvent\n"
    )

    assert [v.level for v in violations] == ["WARN"]
    assert violations[0].type_checking is True


def test_bare_package_import_is_caught(audit_on):
    # 本轮修复。变异：把 _resolve_layers 里的 `| {RUNTIME_PACKAGE}` 去掉，本条必红。
    # 根因是 RUNTIME_PREFIX 带点，而 `from intelligence import runtime` 经
    # _imported_modules 只返回不带点的 "runtime"，startswith 匹配不上。
    # 非理论形态：services/episode_semantic_verifier.py:26 就在用这种写法。
    violations = audit_on("from intelligence import runtime\n")

    assert [v.level for v in violations] == ["ERROR"]
    assert violations[0].tgt == "runtime"


def test_bare_package_plain_import_is_caught(audit_on):
    # 同上，`import intelligence.runtime` 走 ast.Import 分支，同样只得到 "runtime"。
    violations = audit_on("import intelligence.runtime\n")

    assert [v.level for v in violations] == ["ERROR"]
    assert violations[0].tgt == "runtime"


def test_importlib_string_import_is_a_known_blind_spot(audit_on):
    # 刻意断言「放行」，把盲区钉成已知事实而不是意外。
    # 不为它加字符串扫描：字符串里出现模块名不等于导入（日志/注释/错误消息都会
    # 命中），误报会让门禁失信，代价大于收益。
    violations = audit_on(
        "import importlib\n"
        "mod = importlib.import_module('intelligence.runtime.agent_episode')\n"
    )

    assert violations == []
