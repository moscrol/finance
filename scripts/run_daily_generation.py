"""夜跑生成段的双根启动器：代码只从显式快照加载，运行态仍沿用数据配置。

由 nightly_full_review.sh 以绝对路径调用；不提供数据树代码兜底。
这不是另一条日报流程，验证加载位置后仍调用 intelligence.cli daily。
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


def _validate_code_snapshot(code: Path) -> None:
    """Validate source links before importing project code (including this gate's helpers).

    These are code surfaces, not data/asset stores. Walk metadata only, follow
    internal links once, and reject external links before Python can execute them.
    Existing persistent/build directories are not part of the executable snapshot.
    """
    excluded = {"__pycache__", "node_modules", ".git", "users", "webapp", "exports", "outputs", "state"}
    pending = [code / name for name in ("intelligence", "market_feature_store", "scripts", "skills", "evolution")
               if (code / name).exists() or (code / name).is_symlink()]
    seen: set[Path] = set()
    while pending:
        directory = pending.pop()
        resolved = directory.resolve(strict=True)
        if not resolved.is_relative_to(code):
            raise ValueError(f"generation code escapes FINANCE_CODE_ROOT: {directory}")
        if resolved in seen:
            continue
        seen.add(resolved)
        for child in resolved.iterdir():
            if child.name in excluded:
                continue
            if child.is_symlink() and not child.resolve(strict=True).is_relative_to(code):
                raise ValueError(f"generation code escapes FINANCE_CODE_ROOT: {child}")
            if child.is_dir():
                pending.append(child)


def main(argv: list[str] | None = None) -> int:
    try:
        configured = os.environ.get("FINANCE_CODE_ROOT", "").strip()
        if not configured:
            raise ValueError("FINANCE_CODE_ROOT is required; refusing workspace fallback")
        code = Path(configured).expanduser().resolve(strict=True)
        if code != Path(__file__).resolve().parents[1]:
            raise ValueError(f"generation launcher is outside FINANCE_CODE_ROOT={code}")
        for relative in ("intelligence/__init__.py", "intelligence/cli.py",
                         "market_feature_store/__init__.py", "scripts/notify_ops.py"):
            if not (code / relative).resolve(strict=True).is_relative_to(code):
                raise ValueError(f"generation code escapes FINANCE_CODE_ROOT: {relative}")
        _validate_code_snapshot(code)
        data_raw = os.environ.get("FINANCE_DATA_ROOT", "").strip()
        if not data_raw:
            raise ValueError("FINANCE_DATA_ROOT is required")
        data = Path(data_raw).expanduser().resolve(strict=True)
        if not data.is_dir() or data.is_relative_to(code):
            raise ValueError("generation needs separate code and data directories")
        # 不继承另一棵树的 PYTHONPATH/cwd；保留标准库及解释器安装的依赖。
        inherited = {Path(p or os.curdir).resolve()
                     for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)}
        inherited.update((Path.cwd().resolve(), Path(__file__).resolve().parent, data, code))
        sys.path[:] = [str(code)] + [p for p in sys.path
                                     if Path(p or os.curdir).resolve() not in inherited]
        sys.dont_write_bytecode = True
        os.environ.update(FINANCE_WS=str(data), FINANCE_DATA_ROOT=str(data),
                          FINANCE_CODE_ROOT=str(code), PYTHONPATH=str(code),
                          PYTHONSAFEPATH="1", PYTHONDONTWRITEBYTECODE="1")
        # 相对覆盖值统一按数据根解释；先规范化再验，避免 chdir 前后指向两处。
        # 已配置的外置 users/episode/数据库保持原位，不以修接线为由迁移存量。
        writable_defaults = {
            "MARKET_FEATURE_STORE_DB": data / "db/market_feature_store.duckdb",
            "FORESIGHT_USERS_DIR": data / "intelligence/users",
            "FORESIGHT_EPISODE_STORE": data / "state/episodes",
            "DUCKDB_SNAPSHOT_OUT_ROOT": data / "db/snapshots",
        }
        for key, default in writable_defaults.items():
            path = Path(os.environ.get(key, "").strip() or default).expanduser()
            path = (data / path).resolve()
            if path.is_relative_to(code):
                raise ValueError(f"generation writable path is in CODE_ROOT: {key}={path}")
            os.environ[key] = str(path)
        arguments = list(sys.argv[1:] if argv is None else argv)

        import intelligence
        import market_feature_store
        from intelligence import cli
        from intelligence.paths import default_paths
        from intelligence.services.episode_store import resolve_episode_store_root
        from intelligence.userspace import users_dir
        from intelligence.workflows.generation_paths import validate_generation_paths

        for module in (intelligence, cli, market_feature_store):
            if not Path(module.__file__).resolve().is_relative_to(code):
                raise ValueError(f"generation import outside CODE_ROOT: {module.__file__}")
        paths = default_paths()
        for path in (paths.market_exports, paths.review_daily_root, paths.review_workbench.parent,
                     users_dir(), resolve_episode_store_root()):
            if path.resolve().is_relative_to(code):
                raise ValueError(f"generation writable path is in CODE_ROOT: {path}")
        # Parse exactly once with the real daily CLI, including abbreviation,
        # '=' and repeated-option semantics. Dispatch this same Namespace below.
        parsed = cli.build_parser().parse_args(["daily", *arguments])
        validate_generation_paths(cli.daily_options_from_args(parsed), code_root=code,
                                  summary_json=parsed.summary_json, paths=paths)
        print(f"generation_import={intelligence.__file__} cli={cli.__file__} "
              f"data_root={data} users={users_dir()} episodes={resolve_episode_store_root()}",
              file=sys.stderr, flush=True)
        # 历史相对数据参数（summary-json 等）保持数据根语义，与启动者 cwd 无关。
        os.chdir(data)
    except (OSError, ValueError, ImportError, RuntimeError) as exc:
        print(f"generation code/data root invalid: {exc}; refusing workspace fallback", file=sys.stderr)
        return 2
    return parsed.func(parsed)


if __name__ == "__main__":
    raise SystemExit(main())
