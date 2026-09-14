"""夜跑生成段的双根启动器：代码只从显式快照加载，运行态仍沿用数据配置。

由 nightly_full_review.sh 以绝对路径调用；不提供数据树代码兜底。
这不是另一条日报流程，验证加载位置后仍调用 intelligence.cli daily。
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


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
        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        parser.add_argument("--summary-json")
        known, _ = parser.parse_known_args(arguments)
        if known.summary_json and (data / Path(known.summary_json).expanduser()).resolve().is_relative_to(code):
            raise ValueError("generation writable path is in CODE_ROOT: --summary-json")

        import intelligence
        import market_feature_store
        from intelligence import cli
        from intelligence.paths import default_paths
        from intelligence.services.episode_store import resolve_episode_store_root
        from intelligence.userspace import users_dir

        for module in (intelligence, cli, market_feature_store):
            if not Path(module.__file__).resolve().is_relative_to(code):
                raise ValueError(f"generation import outside CODE_ROOT: {module.__file__}")
        paths = default_paths()
        for path in (paths.market_exports, paths.review_daily_root, paths.review_workbench.parent,
                     users_dir(), resolve_episode_store_root()):
            if path.resolve().is_relative_to(code):
                raise ValueError(f"generation writable path is in CODE_ROOT: {path}")
        print(f"generation_import={intelligence.__file__} cli={cli.__file__} "
              f"data_root={data} users={users_dir()} episodes={resolve_episode_store_root()}",
              file=sys.stderr, flush=True)
        # 历史相对数据参数（summary-json 等）保持数据根语义，与启动者 cwd 无关。
        os.chdir(data)
    except (OSError, ValueError, ImportError) as exc:
        print(f"generation code/data root invalid: {exc}; refusing workspace fallback", file=sys.stderr)
        return 2
    return cli.main(["daily", *arguments])


if __name__ == "__main__":
    raise SystemExit(main())
