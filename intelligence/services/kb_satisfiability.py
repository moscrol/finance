"""W2a 静态供给预检：contract 下发前查一次 KB relations 的链路证据在场性。

形状 B（封上限形状收口 R1 spec）：evidence 模式禁权重知识写产业链角色 +
契约必填 ``chain_mapping`` + KB 无该题材链路证据 → 三约束联立无解，模型必死
一格，最终显影为 marker_loss/道歉横幅。本模块把「必死」提前到花预算之前，
翻译成契约层的显式缺口（``chain_mapping`` 降 optional + 预置缺口声明）。

判定口径是**机械事实**：``entity_exposures`` relations 里该题材的命中行数。
不做「预测工具会不会返回有用数据」这类猜测型预检（spec 禁区——猜测型预检
会引入新的误判层）。

Fail-open 方向与 ``check_satisfiability``（工具 produces 预检）同源：查不了
（空主体 / relations 读取失败 / relations 自报错误）→ 报「有证据」，保持
mandatory 现状。让一次坏的 relations 读取拥有降级权，等于造一个新的静默
失败源。只有「机械确认无证据」才触发降级。
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["chain_evidence_present", "CHAIN_EVIDENCE_GAP_NOTE"]

# spec W2-a 逐字：预置结构化缺口声明的公开口径文案。
CHAIN_EVIDENCE_GAP_NOTE = "知识库暂无该题材产业链证据"


def _default_adapter(wiki_root: str | Path | None) -> object:
    from intelligence.adapters.knowledge import KnowledgeAdapter
    from intelligence.paths import default_paths

    root = Path(wiki_root).expanduser() if wiki_root else default_paths().knowledge_wiki
    return KnowledgeAdapter(wiki_root=root)


def chain_evidence_present(
    theme: str,
    *,
    adapter: object | None = None,
    wiki_root: str | Path | None = None,
) -> bool:
    """题材在 KB relations 里有没有链路（entity exposure）证据。

    返回 ``False`` 仅当机械确认无证据；一切无法判定的情形返回 ``True``
    （= 保持 mandatory，不降级）。
    """

    cleaned = str(theme or "").strip()
    if not cleaned:
        return True
    try:
        knowledge = adapter if adapter is not None else _default_adapter(wiki_root)
        result = knowledge.get_exposure_matches(cleaned, limit=1)
    except Exception:  # noqa: BLE001 - 预检失败不得拥有降级权
        return True
    if not isinstance(result, dict):
        return True
    if result.get("errors"):
        return True
    total = result.get("total_matched")
    if not isinstance(total, int):
        return True
    return total > 0
