"""收件箱单元：三事实 durable、领域拒收、收口关箱、派生一致（INV-R5，终态稿 §6.4 P3）。

账本用最小替身：只要 ``add(kind, payload)`` 能记下 ``EpisodeEvent``。loop 级行为在
``conformance/test_inv_r5_inbox.py``。
"""

from __future__ import annotations

import threading

import pytest

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_inbox import INBOX_DISCARD_REASONS, INBOX_TARGETS, Inbox
from intelligence.services.episode_messages import (
    DerivationUnavailable,
    assistant_message,
    derive_messages,
    sha256_text,
    to_provider,
    user_message,
)
from intelligence.services.agent_runtime import ModelTurn


class _Ledger:
    def __init__(self) -> None:
        self.events: list[EpisodeEvent] = []
        self._lock = threading.Lock()

    def add(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        with self._lock:
            event = EpisodeEvent(len(self.events) + 1, kind, dict(payload))
            self.events.append(event)
            return event

    def kinds(self) -> list[str]:
        return [event.kind for event in self.events]


def test_send_then_claim_leaves_inserted_and_claimed_and_derives_the_message() -> None:
    ledger = _Ledger()
    inbox = Inbox(ledger)

    receipt = inbox.send(user_message("先看北向资金", source="steer"), target="next_step")

    assert receipt.accepted and receipt.message_id == "inbox-1"
    assert ledger.kinds() == ["inbox_inserted"]
    inserted = ledger.events[0].payload
    assert inserted["target"] == "next_step" and inserted["source"] == "steer"
    assert inserted["content"] == "先看北向资金"
    assert inserted["content_sha256"] == sha256_text("先看北向资金")
    assert inserted["chars"] == 6 and inserted["wakeup"] is False
    assert inbox.pending() == 1 and inbox.pending("next_turn") == 0
    # 入箱 ≠ 模型可见：派生此刻不产生消息。
    assert derive_messages(ledger.events) == []

    claimed = inbox.claim("next_step")

    assert [message.content for message in claimed] == ["先看北向资金"]
    assert ledger.kinds() == ["inbox_inserted", "inbox_claimed"]
    assert ledger.events[1].payload["message_id"] == "inbox-1"
    assert inbox.pending() == 0
    # 认领后派生出同一条 user 消息（线格式相等——source 不进线格式）。
    assert to_provider(derive_messages(ledger.events)) == to_provider(claimed)


def test_harness_rejection_is_recorded_as_inserted_then_discarded() -> None:
    ledger = _Ledger()
    inbox = Inbox(ledger, admit=lambda message: "买入" not in message.content)

    receipt = inbox.send(user_message("买入茅台", source="steer"))

    assert not receipt.accepted and receipt.reason == "rejected_by_harness"
    assert ledger.kinds() == ["inbox_inserted", "inbox_discarded"]
    assert ledger.events[1].payload["reason"] == "rejected_by_harness"
    assert "detail" not in ledger.events[1].payload
    assert inbox.pending() == 0
    assert inbox.claim("next_step") == []
    assert derive_messages(ledger.events) == []


def test_broken_admission_fails_closed_with_detail() -> None:
    def explode(_message):  # noqa: ANN001 - 替身
        raise RuntimeError("harness down")

    ledger = _Ledger()
    inbox = Inbox(ledger, admit=explode)

    receipt = inbox.send(user_message("任何话", source="steer"))

    assert not receipt.accepted and receipt.reason == "rejected_by_harness"
    assert ledger.events[-1].payload["detail"] == "admit_error:RuntimeError"


def test_discard_all_closes_the_box_and_later_sends_are_not_recorded() -> None:
    ledger = _Ledger()
    inbox = Inbox(ledger)
    inbox.send(user_message("a", source="steer"), target="next_step")
    inbox.send(user_message("b", source="steer"), target="next_turn")

    dropped = inbox.discard_all(reason="episode_finished")

    assert dropped == 2 and inbox.closed and inbox.pending() == 0
    assert ledger.kinds() == ["inbox_inserted", "inbox_inserted", "inbox_discarded", "inbox_discarded"]
    assert {e.payload["reason"] for e in ledger.events[2:]} == {"episode_finished"}
    assert {e.payload["message_id"] for e in ledger.events[2:]} == {"inbox-1", "inbox-2"}
    # finish 之后不再产生事件：回执说 inbox_closed，账本长度不变。
    receipt = inbox.send(user_message("c", source="steer"))
    assert not receipt.accepted and receipt.reason == "inbox_closed" and receipt.message_id == ""
    assert len(ledger.events) == 4
    # 修复轮重开：又能收，编号接着排。
    inbox.reopen()
    receipt = inbox.send(user_message("c", source="steer"))
    assert receipt.accepted and receipt.message_id == "inbox-3"


def test_keep_on_cancel_leaves_messages_in_the_box_and_the_log_undecided() -> None:
    ledger = _Ledger()
    inbox = Inbox(ledger)
    inbox.send(user_message("a", source="steer"))
    inbox.keep_on_cancel = True

    assert inbox.discard_all(reason="cancelled") == 0
    assert inbox.closed and inbox.pending() == 1
    assert ledger.kinds() == ["inbox_inserted"]
    # 不是取消原因时照常清。
    inbox.reopen()
    assert inbox.discard_all(reason="episode_finished") == 1
    assert ledger.kinds()[-1] == "inbox_discarded"


def test_validation_rejects_non_user_roles_unknown_targets_and_reasons() -> None:
    ledger = _Ledger()
    inbox = Inbox(ledger)
    with pytest.raises(ValueError, match="user"):
        inbox.send(assistant_message(ModelTurn("x", (), "scripted", "")))
    with pytest.raises(ValueError, match="队列"):
        inbox.send(user_message("a"), target="later")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="丢弃原因"):
        inbox.discard_all(reason="whatever")  # type: ignore[arg-type]
    assert ledger.events == []
    assert INBOX_TARGETS == {"next_turn", "next_step"}
    assert INBOX_DISCARD_REASONS == {"rejected_by_harness", "cancelled", "episode_finished"}


def test_derivation_refuses_a_claim_without_its_insert() -> None:
    orphan = [EpisodeEvent(1, "inbox_claimed", {"message_id": "inbox-9", "target": "next_step"})]
    with pytest.raises(DerivationUnavailable, match="inbox-9"):
        derive_messages(orphan)


def test_concurrent_senders_get_unique_ids_and_nothing_is_lost() -> None:
    ledger = _Ledger()
    inbox = Inbox(ledger)
    receipts: list[str] = []
    lock = threading.Lock()

    def worker(prefix: str) -> None:
        for index in range(25):
            receipt = inbox.send(user_message(f"{prefix}-{index}", source="steer"))
            with lock:
                receipts.append(receipt.message_id)

    threads = [threading.Thread(target=worker, args=(f"t{n}",)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(receipts) == 100 == len(set(receipts))
    assert sorted(int(r.split("-")[1]) for r in receipts) == list(range(1, 101))
    assert ledger.kinds().count("inbox_inserted") == 100
    claimed = inbox.claim("next_step")
    assert len(claimed) == 100 and inbox.pending() == 0
    assert len(to_provider(derive_messages(ledger.events))) == 100
