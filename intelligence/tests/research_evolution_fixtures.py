"""06 验收用的合成夹具与环境搭建（**全部 synthetic**，不得据此宣称任何真实用户效果或方法有效性）。

与 05 的 ``product_value_fixtures.py`` 同一惯例：夹具建造器放测试树，产物落 ``fixtures/research_evolution/06/``。

这里造的是「固定市场输入 + 真实旧写入者」的世界：

- 台账由**现役写入者**写（``judgments.record_judgment`` / ``checkpoints.register_checkpoint`` /
  ``record_verdict``）——不手搓 JSONL，否则测的是我自己编的形状；
- 市场取数由 ``StaticEvidenceSource`` 固定，但它按 ``knowledge_cutoff`` 过滤，与河同口径；
- 01/02/04/05 的判定全是真函数。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from intelligence.services.research_evolution.adapters import EvidenceCatalog, StaticEvidenceSource

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "research_evolution" / "06"
CHAT_REPO = Path(__file__).parent / "fixtures" / "chat_workbench_repo"

OWNER = "default"
ENTITY = "制冷剂"
SLICE_DAY = "2026-09-01"
BIND_DAY = "2026-09-10"
TODAY = "2026-09-14"

SH = timezone(timedelta(hours=8))

# 被绑定的两条依赖。``fact_sector_daily`` 在 09-12 出了新版本（只换了哈希 = 版式/内容变化，
# **不**是证伪）；``fact_research_report_catalog`` 一直没动。
REF_SECTOR = f"fact_sector_daily:{SLICE_DAY}:866006.FP"
REF_REPORT = "fact_research_report_catalog:r-77"

_BASE_VERSIONS: tuple[dict[str, Any], ...] = (
    {
        "ref": REF_SECTOR,
        "source_hash": "h-sector-v1",
        "valid_from": SLICE_DAY,
        "valid_to": None,
        "recorded_at": f"{SLICE_DAY}T18:00:00+08:00",
        "derivation": "deterministic",
        "namespace": "market_feature_store",
        "_track": "theme",
        "_object_type": "label",
        "_entity_id": "866006.FP",
    },
    {
        "ref": REF_REPORT,
        "source_hash": "h-report-v1",
        "valid_from": SLICE_DAY,
        "valid_to": None,
        "recorded_at": f"{SLICE_DAY}T18:00:00+08:00",
        "derivation": "deterministic",
        "namespace": "market_feature_store",
        "_track": "opinion",
        "_object_type": "event",
        "_entity_id": "866006.FP",
    },
)

_REVISED_SECTOR: dict[str, Any] = {
    **_BASE_VERSIONS[0],
    "source_hash": "h-sector-v2",
    "recorded_at": "2026-09-12T18:00:00+08:00",
}


def slice_catalog(*, revised: bool = True) -> EvidenceCatalog:
    """``(ENTITY, SLICE_DAY)`` 的全量目录。``revised`` 决定 09-12 那版新哈希在不在。"""
    versions = list(_BASE_VERSIONS) + ([_REVISED_SECTOR] if revised else [])
    return EvidenceCatalog(
        entity=ENTITY,
        as_of=SLICE_DAY,
        knowledge_cutoff=TODAY,
        versions=tuple(versions),
        observations=(),
        gaps=(),
        pit_grade="strict",
        available=True,
    )


def today_catalog(*, market_stage: str = "反弹", recorded_day: str = TODAY) -> EvidenceCatalog:
    """今天的盘面观测：``market_stage`` 是 01 能编译的四个标签之一。

    ``market_stage=""`` 表示**今天读不到这个标签**——目录里就没有这条观测。
    这跟「读到了一个空字符串」是两回事：后者会被判成条件不成立（false），
    前者才是「还不知道」（unknown）。河的绑定函数也是这么分的（值为 None 时不发观测）。
    """
    observations = (
        (
            {
                "label": "market_stage",
                "entity_id": "",
                "as_of": TODAY,
                "value": market_stage,
                "recorded_at": f"{recorded_day}T18:00:00+08:00",
                "label_version": None,
                "source_ref": f"fact_market_daily:{TODAY}",
            },
        )
        if market_stage
        else ()
    )
    return EvidenceCatalog(
        entity=ENTITY,
        as_of=TODAY,
        knowledge_cutoff=TODAY,
        versions=(
            {
                "ref": f"fact_market_daily:{TODAY}",
                "source_hash": "h-market-today",
                "valid_from": TODAY,
                "valid_to": None,
                "recorded_at": f"{recorded_day}T18:00:00+08:00",
                "derivation": "deterministic",
                "namespace": "market_feature_store",
                "_track": "market",
                "_object_type": "stage",
                "_entity_id": "866006.FP",
            },
        ),
        observations=observations,
        pit_grade="strict",
        available=True,
    )


def evidence_source(*, revised: bool = True, market_stage: str = "反弹") -> StaticEvidenceSource:
    return StaticEvidenceSource(
        catalogs={
            (ENTITY, SLICE_DAY): slice_catalog(revised=revised),
            (ENTITY, TODAY): today_catalog(market_stage=market_stage),
        }
    )


@dataclass
class FakeClock:
    """可推进的服务端时钟。``now()`` 是**服务端**取的，客户端永远不能覆盖它。"""

    moment: datetime = field(default_factory=lambda: datetime(2026, 9, 14, 16, 0, 0, tzinfo=SH))

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **kwargs: Any) -> datetime:
        self.moment = self.moment + timedelta(**kwargs)
        return self.moment



LLM_KEY_NAMES: tuple[str, ...] = (
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
    "KIMI_API_KEY",
    "DASHSCOPE_API_KEY",
    "QWEN_API_KEY",
    "ZHIPU_API_KEY",
    "GLM_API_KEY",
    "OPENAI_API_KEY",
    "LLM_API_KEY",
    "FORESIGHT_BUILTIN_LLM_API_KEY",
)


def service_with(evidence: Any, clock: Any) -> Any:
    """跟 app 同源的一份服务实例：同一个证据源、同一个时钟、同一批磁盘台账。

    不从 ``app.state`` 取：那样会在生产代码里留一个只有测试读的字段（``check_unread_fields``
    正是抓这个）。服务本身无状态，状态全在用户态目录里，所以两个实例看到的是同一份事实。
    """
    from intelligence.services.conversation_store import ConversationStore
    from intelligence.services.research_evolution import ResearchEvolutionService, Resources
    from intelligence.services.run_store import RunStore

    return ResearchEvolutionService(
        Resources(
            evidence_source=evidence,
            conversation_store_for=lambda user: ConversationStore(user_id=user),
            run_store_for=lambda user: RunStore(user_id=user),
            finance_root=CHAT_REPO,
            code_sha="test",
            clock=clock,
        )
    )


def install_env(monkeypatch: Any, tmp_path: Path) -> Path:
    """把进程环境指到临时用户态与夹具仓，并清掉所有 LLM 密钥（本轨不调模型）。"""
    users = tmp_path / "users"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users))
    monkeypatch.setenv("FINANCE_WS", str(CHAT_REPO))
    monkeypatch.setenv("KB_VAULT", str(CHAT_REPO / "wiki"))
    monkeypatch.delenv("FORESIGHT_USER", raising=False)
    monkeypatch.delenv("RESEARCH_EVOLUTION_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("MARKET_FEATURE_STORE_DB", raising=False)
    for name in LLM_KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    return users


# --------------------------------------------------------------------------- #
# 旧台账：一律由现役写入者写
# --------------------------------------------------------------------------- #
def seed_legacy_ledgers(user_root: Path, *, session_id: str) -> dict[str, Any]:
    """写一条带结构化证据的判断、一条到期 checkpoint 与它的回检。返回原始行供逐字节对账。

    正文带上会话短码：``judgments.record_judgment`` 的行 id 是 ``(kind, ts, text)`` 的哈希，
    同一个用户下两个会话写出**逐字相同**的判断会得到同一个 id，进而得到同一个绑定 id。
    那是夹具制造的碰撞，不是产品行为；给每个会话一条自己的判断才是真实形状。
    """
    from intelligence.services import checkpoints as checkpoints_svc
    from intelligence.services import judgments as judgments_svc

    user_root.mkdir(parents=True, exist_ok=True)
    judgments_path = user_root / "judgments.jsonl"
    checkpoints_path = user_root / "checkpoints.jsonl"
    verdicts_path = user_root / "verdicts.jsonl"
    tag = session_id[-6:]

    _, judgment = judgments_svc.record_judgment(
        judgments_path,
        memo=f"配额收紧下三代制冷剂价格中枢上移（{tag}）",
        themes=["制冷剂"],
        stocks=[],
        session_id=session_id,
        ts="2026-09-02T20:00:00+08:00",
    )
    _, checkpoint = checkpoints_svc.register_checkpoint(
        checkpoints_path,
        claim=f"R32 华东报价 9 月 11 日前站上 4.5 万/吨（{tag}）",
        due="2026-09-11",
        category="price",
        source=session_id,
        themes=["制冷剂"],
        session_id=session_id,
        object_type="judgment",
        ts="2026-09-02T20:05:00+08:00",
        user_authored=True,
    )
    _, verdict = checkpoints_svc.record_verdict(
        verdicts_path,
        id=checkpoint["id"],
        verdict="partial",
        reason="报价到 4.35 万，未站上",
        checked_at="2026-09-12T09:00:00+08:00",
    )
    # 第二条到期回检**没有**裁决：配上 coverage 声明后，04 才能把它从「不知道有没有漏」
    # 升级成「确实漏了」。没有 coverage 声明时它只能是 coverage_unknown。
    _, overdue = checkpoints_svc.register_checkpoint(
        checkpoints_path,
        claim=f"配额分配公告 9 月 8 日前落地（{tag}）",
        due="2026-09-08",
        category="event",
        source=session_id,
        themes=["制冷剂"],
        session_id=session_id,
        object_type="judgment",
        ts="2026-09-02T20:06:00+08:00",
        user_authored=True,
    )
    return {"judgment": judgment, "checkpoint": checkpoint, "verdict": verdict, "overdue": overdue}


def coverage_receipt(*, complete_through: str = TODAY, complete_from: str = "2026-08-01") -> dict[str, Any]:
    """回检台账完整性声明：06 在回检收口后写（04 的 ``overdue_unreviewed`` 靠它）。"""
    return {
        "receipt_id": f"cov-verdicts-{complete_from}-{complete_through}",
        "kind": "coverage",
        "occurred_at": f"{complete_through}T16:00:00+08:00",
        "recorded_at": f"{complete_through}T16:00:00+08:00",
        "payload": {"ledger": "verdicts", "complete_from": complete_from, "complete_through": complete_through},
        "provenance": "observed",
    }


def ledger_hashes(user_root: Path) -> dict[str, str]:
    """五本旧台账的 sha256：动作落盘后必须逐字节不变（I12）。"""
    import hashlib

    out: dict[str, str] = {}
    for name in ("judgments.jsonl", "checkpoints.jsonl", "verdicts.jsonl", "scenario_trees.jsonl", "observation_scripts.jsonl"):
        path = user_root / name
        out[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "<absent>"
    return out


# --------------------------------------------------------------------------- #
# 登记件（诊断策略 / 题包）
# --------------------------------------------------------------------------- #
def load_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def diagnostics_policy() -> dict[str, Any]:
    return load_json("diagnostics_policy.json")


def exercise_pack() -> dict[str, Any]:
    return load_json("exercise_pack.json")


__all__ = [
    "BIND_DAY",
    "CHAT_REPO",
    "ENTITY",
    "FIXTURE_DIR",
    "OWNER",
    "REF_REPORT",
    "REF_SECTOR",
    "SH",
    "SLICE_DAY",
    "TODAY",
    "LLM_KEY_NAMES",
    "coverage_receipt",
    "install_env",
    "service_with",
    "FakeClock",
    "diagnostics_policy",
    "evidence_source",
    "exercise_pack",
    "ledger_hashes",
    "load_json",
    "seed_legacy_ledgers",
    "slice_catalog",
    "today_catalog",
]
