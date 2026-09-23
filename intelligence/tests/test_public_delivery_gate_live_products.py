"""最终交付门 × 真实现场产物（live products）的离线回归。

与 ``test_public_delivery_gate.py`` 的区别：那边的夹具是抄进源码的常量；这里
直接读 ``fixtures/live_products/run_20260922_191550_067475/`` 下**冻结的现场文件**
（``answer.md`` / ``report.json`` 逐字，``continuous-episode.json`` 去重投影），并用
``MANIFEST.json`` 里的 sha256 钉住「夹具不许改措辞」——谁改了一个字，先让这里红。

现场（收口批工单 #70）：模型在自由文本里写完 2518 字完整答案，却把结构化
``finish`` 的 ``draft`` 填成一句指针「见正文：……」。运行时按 ``draft`` 交付，用户
收到 154 字、``report.modules == 0``；77 条证据全绑定、语义判官 ``passed``、
``marker_coverage=incomplete`` 却是 ``observation_only``。

本文件不调模型、不做 IO（只读仓内夹具）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import pytest

from intelligence.services import public_delivery_gate as gate
from intelligence.services.public_delivery_gate import (
    VERDICT_EMPTY,
    VERDICT_INCOMPLETE,
    VERDICT_OK,
    contract_output_descriptions,
    review_public_delivery,
)
from intelligence.tests.test_public_delivery_gate import PRODUCTION_POINTER_ANSWER

FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "live_products"
    / "run_20260922_191550_067475"
)
_FROZEN_FILES = ("answer.md", "report.json", "continuous-episode.json")
_NEVER_MATCH = re.compile(r"(?!x)x")


def _manifest() -> dict:
    return json.loads((FIXTURE_DIR / "MANIFEST.json").read_text(encoding="utf-8"))


def _answer_md() -> str:
    return (FIXTURE_DIR / "answer.md").read_text(encoding="utf-8")


def _report() -> dict:
    return json.loads((FIXTURE_DIR / "report.json").read_text(encoding="utf-8"))


def _episode() -> dict:
    return json.loads(
        (FIXTURE_DIR / "continuous-episode.json").read_text(encoding="utf-8")
    )


def _required_outputs(episode: dict) -> tuple[str, ...]:
    return tuple(episode["task_frame"]["required_outputs"])


def _descriptions(episode: dict) -> dict[str, str]:
    return contract_output_descriptions(episode["contract"])


def _model_body(episode: dict) -> str:
    """模型最后一轮自由文本：它才是本该交付的正文。

    按内容定位而不是按下标：那一轮的 ``content`` 里内嵌了模型自己写出来的
    finish JSON，所以它必然包含 ``outcome.draft`` 的原文。
    """

    draft = episode["outcome"]["draft"]
    turns = [
        event["payload"]["content"]
        for event in episode["events"]
        if event.get("kind") == "model_turn"
        and isinstance((event.get("payload") or {}).get("content"), str)
        and draft in event["payload"]["content"]
    ]
    assert len(turns) == 1, "现场只有一轮模型自由文本内嵌了 finish 的 draft"
    return turns[0]


def _sentences_after_pointer(answer: str) -> list[str]:
    """指针后面的每一句：门必须把它们原样留在公开正文里。"""

    _, _, rest = answer.partition("：")
    return [part for part in re.split(r"(?<=[。；])", rest) if part.strip()]


def test_frozen_files_match_manifest_hashes() -> None:
    """夹具不许改措辞：三份冻结件的 sha256 必须与 MANIFEST 一致。

    这不是在测门，是在测夹具本身——现场文本一旦被「顺手改通顺」，下面所有
    用例证明的就不再是那次事故。
    """

    manifest = _manifest()
    assert manifest["run_id"] == "run_20260922_191550_067475"
    for name in _FROZEN_FILES:
        digest = hashlib.sha256((FIXTURE_DIR / name).read_bytes()).hexdigest()
        assert digest == manifest["frozen"][name]["sha256"], name
    assert manifest["frozen"]["answer.md"]["verbatim"] is True
    assert manifest["frozen"]["report.json"]["verbatim"] is True
    # 去重投影只许替换整份重复拷贝，不许动别的路径。
    dropped = {
        item["path"]
        for item in manifest["frozen"]["continuous-episode.json"]["projection"][
            "dropped_paths"
        ]
    }
    assert dropped == {
        "outcome.events",
        "structural_verifier.outcome",
        "semantic_verifier.verified",
    }
    for name in _FROZEN_FILES + ("MANIFEST.json",):
        text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        assert "/Users/" not in text and "probe-preservation" not in text, name


def test_fixture_encodes_the_incident_not_a_paraphrase() -> None:
    """冻结的 report.json 必须仍然写着那次事故的形状：五道门全过、用户拿到指针。"""

    report = _report()
    episode = _episode()

    assert report["status"] == "partial"
    assert report["answer_status"] == "partial"
    assert report["modules"] == []
    coverage = report["answer_marker_coverage"]
    assert coverage["marker_coverage"] == "incomplete"
    assert coverage["observation_only"] is True
    assert set(coverage["absent"]) == {"direct_assessment", "evidence_boundary"}
    assert report["gate_receipt"]["judge_status"] == "passed"

    assert episode["outcome"]["draft"].startswith("见正文")
    assert len(episode["outcome"]["evidence"]) == 77
    assert episode["semantic_verifier"]["judge_status"] == "passed"
    assert episode["structural_verifier"]["verified_status"] == "partial"
    assert _required_outputs(episode) == (
        "direct_assessment",
        "counterpoint",
        "evidence_boundary",
    )
    # 源码里那份常量与冻结文件逐字相同：常量版的端到端用例证明的也是这次现场。
    assert _answer_md() == PRODUCTION_POINTER_ANSWER
    assert _answer_md() == episode["outcome"]["draft"] + (
        "\n\n" + episode["publication_assessment"]["required_public_notices"][0]
    )


def test_live_answer_md_is_judged_missing_and_kept_whole() -> None:
    """现场 answer.md → 门判「正文未随本轮送达」（answer_status=missing），正文全留。

    实现二选一里选的是「原文保留 + 【交付自检】披露」，不是替代正文、不是缺口
    模板：正文里唯一的实质内容一个字不删，只摘掉开头那句悬空指引。
    """

    episode = _episode()
    answer = _answer_md()

    receipt = review_public_delivery(
        answer,
        required_outputs=_required_outputs(episode),
        descriptions=_descriptions(episode),
    )

    assert receipt.verdict in {VERDICT_EMPTY, VERDICT_INCOMPLETE}
    assert receipt.answer_status in {"missing", "partial"}
    # 具体形状：以指针开场 + 必需输出缺覆盖 → 两把钥匙同时命中 → empty / missing。
    assert receipt.verdict == VERDICT_EMPTY
    assert receipt.answer_status == "missing"
    assert "opens_with_dangling_pointer" in receipt.reasons
    assert "required_outputs_absent" in receipt.reasons
    assert receipt.dangling_pointers == ("见正文",)
    assert set(receipt.missing_outputs) == {"direct_assessment", "evidence_boundary"}

    assert not receipt.text.startswith("见正文")
    for sentence in _sentences_after_pointer(answer):
        assert sentence in receipt.text, sentence
    assert "【交付自检】" in receipt.text
    for description in _descriptions(episode).values():
        if description == "提供主要反证或竞争性解释":
            continue  # counterpoint 在现场是命中的，不该出现在缺口披露里
        assert description in receipt.text


def test_live_model_turn_body_passes_unchanged() -> None:
    """同一轮模型真正写出来的 2518 字正文必须原样放行。

    这段正文里内嵌了模型自己写的 finish JSON（含「见正文」），所以形态钥匙**会**
    命中；但必需输出全在正文里，覆盖钥匙不命中 → 单把钥匙不拦。真实产物给出的
    「中段指针 + 覆盖齐全」样本比手写的更有说服力。
    """

    episode = _episode()
    body = _model_body(episode)

    receipt = review_public_delivery(
        body,
        required_outputs=_required_outputs(episode),
        descriptions=_descriptions(episode),
    )

    assert receipt.dangling_pointers  # 钥匙 1 命中
    assert not receipt.missing_outputs  # 钥匙 2 未命中
    assert receipt.verdict == VERDICT_OK
    assert receipt.answer_status is None
    assert receipt.text == body
    assert receipt.substance_chars > 1000


def test_positive_control_key1_lexicon_cleared_releases_live_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """阳性对照：把钥匙 1（指针形态）的词表清空，现场夹具必须放行。

    证明降级确实需要两把钥匙——只剩「必需输出缺覆盖」这一把时，门不拦。
    否则它就是伪装成双钥匙的 marker 阻断（工单里明确划掉的选项 B）。
    """

    episode = _episode()
    for name in (
        "_OUTSIDE_POINTER_RE",
        "_OPENING_POINTER_RE",
        "_LEADING_POINTER_STRIP_RE",
    ):
        monkeypatch.setattr(gate, name, _NEVER_MATCH)

    receipt = review_public_delivery(
        _answer_md(),
        required_outputs=_required_outputs(episode),
        descriptions=_descriptions(episode),
    )

    assert not receipt.dangling_pointers
    assert set(receipt.missing_outputs) == {"direct_assessment", "evidence_boundary"}
    assert receipt.verdict == VERDICT_OK
    assert receipt.text == _answer_md()


def test_positive_control_key2_cleared_releases_live_answer() -> None:
    """阳性对照（反向）：契约不声明必需输出时，光有指针形态也不拦。

    与上一条合起来：任一把钥匙单独命中都放行，只有两把同时命中才降级。
    唯一例外是实质字符不到 8 个的「见正文。」——那条规则在
    ``test_public_delivery_gate.test_no_required_outputs_still_catches_an_empty_body``
    单独钉着。
    """

    receipt = review_public_delivery(_answer_md(), required_outputs=())

    assert receipt.dangling_pointers == ("见正文",)
    assert receipt.required_output_count == 0
    assert receipt.verdict == VERDICT_OK
    assert receipt.text == _answer_md()
