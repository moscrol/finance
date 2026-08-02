"""候选公司必须出现在正文里，不能被压成「无公司证据」。

实测 2026-07-30「固态电池现在怎么看」：
- AnswerSpec 的「公司判断」小节有 12 家候选，带产业链角色与层级
  （三祥新材/东方锆业/中一科技 core、万顺新材/中仑新材 related、万润新能 peripheral）；
- claim registry 里有 12 条 company: claim；
- 正文一家都没提，只写「公司层面尚未形成可回查证据，不能把任何公司列为核心受益者」。

那句话本身是对的——12 家全是 candidate/peripheral，证据来自图谱（G2），没有一家
够 L3 硬证据，系统拒绝叫它们「核心受益者」是正确的。错的是把 12 个有名有姓的候选
压成「什么都没有」。

后果是连锁的：chain_mapping 要求 claim 文本出现在正文里才算绑定，正文不提就判缺，
fail-closed 再把整份答案（905 字、57 条证据链、27 条分歧反证）换成 190 字的
「请补充数据源或稍后重试」。
"""
from __future__ import annotations

from intelligence.workbench_skills.research_owner import THEME_RESEARCH


def test_contract_requires_listing_candidate_companies() -> None:
    joined = "".join(THEME_RESEARCH.output_contract)

    assert "候选必须逐个列出" in joined
    assert "产业链环节" in joined
    assert "还缺什么证据" in joined


def test_contract_forbids_collapsing_candidates_into_nothing() -> None:
    """「都还是候选」不是省略它们的理由——候选清单本身就是研究结论。"""
    joined = "".join(THEME_RESEARCH.output_contract)

    assert "无公司证据" in joined
    assert "不得" in joined


def test_no_upgrade_rule_is_kept_alongside_it() -> None:
    """列出候选不等于放宽分层：不绑硬证据仍然不许升级为核心。"""
    joined = "".join(THEME_RESEARCH.output_contract)

    assert "不因概念关联直接升级" in joined


def test_chain_mapping_claims_use_the_company_namespace() -> None:
    """正文提到候选后，chain_mapping 才能绑到 company: claim 上。

    两端要对齐：evidence_providers 发的是 claim_id=company:<名>，
    task_fulfillment 的 chain_mapping 命名空间要认得它。
    """
    from intelligence.services.task_fulfillment import _OUTPUT_CLAIM_NAMESPACES

    assert "company" in _OUTPUT_CLAIM_NAMESPACES["chain_mapping"]


def test_no_consumer_resolves_the_market_db_from_the_code_root() -> None:
    """盘面库在数据根下，不在代码根下。

    WORKBENCH_REPO_ROOT 按部署契约是候选代码根，FINANCE_WS 才是私有数据根。
    写成 repo_root/db/... 的调用点在蓝绿运行时会静默拿到空数据——今天已经在
    daily_review、research_owner 和 api/app 三处踩到同一个坑。
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = [
        f"{path.relative_to(root.parent)}:{i}"
        for path in root.rglob("*.py")
        if "tests" not in path.parts
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if 'repo_root / "db" / "market_feature_store.duckdb"' in line
        and "local_path" not in line
    ]

    assert offenders == [], f"这些调用点仍从代码根解析盘面库：{offenders}"
