from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    finance_root: Path
    knowledge_wiki: Path
    finance_site: Path

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
    finance_root = Path(os.environ.get("FINANCE_ROOT", "/Users/lbq/Desktop/c c/金融")).expanduser()
    knowledge_wiki = Path(os.environ.get("KNOWLEDGE_WIKI", "/Users/lbq/Desktop/c c/知识库/wiki")).expanduser()
    finance_site = Path(os.environ.get("FINANCE_SITE", "/Users/lbq/Desktop/c c/windsurf/finance-research-site")).expanduser()
    return ProjectPaths(finance_root=finance_root, knowledge_wiki=knowledge_wiki, finance_site=finance_site)
