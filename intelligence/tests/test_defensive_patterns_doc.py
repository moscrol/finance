"""`docs/runtime/defensive-patterns.md` 不许烂掉：G10 原句在、引用的每个 R-* 编号在预测台账里存在。

三张生成目录由 ``gen_runtime_catalog --check`` 保鲜；这份是手写的，所以另起一道最小的钉。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "runtime" / "defensive-patterns.md"
LEDGER = REPO / "docs" / "prediction-ledger.md"

G10_RULE = (
    "`runtime/` 内部用异常，跨 `services` 契约边界只返回结构化结果；"
    "hooks / sink / 投影一律不抛。"
)
_R_ID = re.compile(r"R-2026\d{4}-\d{2}")


def test_doc_exists_and_states_the_g10_rule_verbatim() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert G10_RULE in text, "G10 抛 / 返回总规则必须原句出现"
    assert "| # | 坑（本仓实例） | 规则 | 出处 |" in text


def test_every_cited_ledger_id_exists_in_the_prediction_ledger() -> None:
    doc_ids = set(_R_ID.findall(DOC.read_text(encoding="utf-8")))
    assert doc_ids, "至少要引一条台账编号——否则「本仓实例」是空话"
    ledger_ids = set(_R_ID.findall(LEDGER.read_text(encoding="utf-8")))
    missing = sorted(doc_ids - ledger_ids)
    assert not missing, f"文档引用了台账里不存在的编号：{missing}"


def test_generated_catalog_check_does_not_own_the_handwritten_doc() -> None:
    """生成器只比对三张目录；手写文档不在它的 --check 范围里（否则一改就红）。"""

    source = (REPO / "scripts" / "gen_runtime_catalog.py").read_text(encoding="utf-8")
    assert "defensive-patterns" not in source
