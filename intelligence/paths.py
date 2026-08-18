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
    """解析各数据根。``finance_root`` 与 DuckDB 必须落在同一个数据根。

    这里回退 ``data_repo_root()`` 而不是某个写死的家目录：两者曾各自回退，
    未设环境变量时 DuckDB 落在本仓、exports/快照落在 ``~/Desktop/c c/金融``。
    后果不是报错而是静默失真——``_runtime_market_reference_date()`` 从旧仓
    exports 取出 6 月的日期当 floor，再拿它去查数据已到 8 月的本仓库，于是
    每条结构化查询都被判成「数据仅更新到 …，早于当前所需 …」。实测两次同题
    冒烟：根不一致时 ``direct_assessment`` 缺失、仅 1 个工具取到证据；对齐后
    marker 覆盖转 complete、4 个工具取到 17 条证据。

    ``default_market_db_path()`` 的注释已记过同一教训（库不在数据根时盘面证据
    层静默消失），但当时只修了 DuckDB 一处，本函数没跟上。两个根从此只有一个
    真相源，``test_paths.py`` 锁住这一点。
    """

    finance_root = _env_path("FINANCE_WS", "FINANCE_ROOT") or data_repo_root()
    home = Path.home()
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

    双根架构：PYTHONPATH / ``WORKBENCH_REPO_ROOT`` 指向 runtime 代码快照，
    真实数据在 ``FINANCE_WS``（private 仓）。``WORKBENCH_REPO_ROOT`` 是代码根
    概念（``runtime_provenance`` 用它读 git HEAD），不得参与数据根解析——
    启动器把两者同时导出时，旧查找序会把盘面库和 exports 解析进没有 ``db/``
    的快照树，盘面证据层静默消失。

    查找序：``FINANCE_WS`` → ``FINANCE_ROOT`` → 代码根（intelligence 的父目录）。
    """
    return _env_path("FINANCE_WS", "FINANCE_ROOT") or (
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
