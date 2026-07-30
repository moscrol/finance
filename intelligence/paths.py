from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    finance_root: Path
    knowledge_wiki: Path
    finance_site: Path
    market_snapshot_dir: Path
    vector_index_dir: Path

    @property
    def market_exports(self) -> Path:
        return self.finance_root / "market_feature_store" / "exports"

    @property
    def review_daily_root(self) -> Path:
        return self.finance_root / "复盘" / "daily"

    @property
    def review_workbench(self) -> Path:
        return self.finance_root / "复盘" / "matrices" / "strategy-review-workbench.html"


def default_paths() -> ProjectPaths:
    home = Path.home()
    finance_root = _env_path("FINANCE_WS", "FINANCE_ROOT") or home / "Desktop/c c/金融"
    knowledge_wiki = _env_path("KB_VAULT", "KNOWLEDGE_WIKI", "CONCEPT_VAULT", "ENTITY_VAULT") or home / "Desktop/c c/知识库/wiki"
    finance_site = _env_path("FINANCE_SITE") or home / "Desktop/c c/windsurf/finance-research-site"
    market_snapshot_dir = _env_path("MARKET_SNAPSHOT_DIR") or finance_root / "market_snapshot"
    vector_index_dir = vector_index_dir_for(knowledge_wiki)
    return ProjectPaths(
        finance_root=finance_root,
        knowledge_wiki=knowledge_wiki,
        finance_site=finance_site,
        market_snapshot_dir=market_snapshot_dir,
        vector_index_dir=vector_index_dir,
    )


def vector_index_dir_for(knowledge_wiki: str | Path) -> Path:
    return _env_path("VECTOR_INDEX_DIR", "RAG_INDEX_DIR") or Path(knowledge_wiki).expanduser().parent / ".rag_index"


def data_repo_root() -> Path:
    """盘面/exports/DuckDB 等数据根目录。

    双根架构：PYTHONPATH 指向 runtime 代码快照，真实数据在 private 仓。
    未设置任何变量时回退代码根（intelligence 的父目录）。
    """
    return _env_path("WORKBENCH_REPO_ROOT", "FINANCE_WS", "FINANCE_ROOT") or (
        Path(__file__).resolve().parents[1]
    )


def default_market_db_path() -> Path:
    """盘面 DuckDB 默认路径。唯一来源，供 intelligence 各层共用。

    优先级：``MARKET_FEATURE_STORE_DB``（与 market_feature_store.db 同一个变量，
    保证两层对"库在哪"的认知一致）→ 数据根下的 ``db/``。

    为什么不能回退代码根：18 处调用点原先都写死
    ``REPO_ROOT / "db" / "market_feature_store.duckdb"``，而 REPO_ROOT 是代码
    快照根。库不在仓树内时（例如独立 clone 的开发副本）整个盘面证据层会静默
    消失——实测 5 个真实问题全部命中"本轮没有连接本地市场数据"，同期 exports
    因为走数据根反而正常，两者不一致正是这个 bug 的表征。
    """
    return _env_path("MARKET_FEATURE_STORE_DB") or (
        data_repo_root() / "db" / "market_feature_store.duckdb"
    )


def _env_path(*names: str) -> Path | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return Path(value).expanduser()
    return None
