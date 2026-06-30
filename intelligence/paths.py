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


def _env_path(*names: str) -> Path | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return Path(value).expanduser()
    return None
