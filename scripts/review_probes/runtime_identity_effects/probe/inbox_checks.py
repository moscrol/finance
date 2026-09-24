"""K3 写手补测：Inbox / inbox-spool（工单 C6 片段）独立核对。

只测 ``intelligence/services/episode_inbox.py`` 的投递槽语义，全部合成输入 + tmp_path：

- C1 保存 insert 失败：不删 spool 文件、不 claim、磁盘原件字节保持（两种故障形状）。
- C2 正常落账才删文件；claim 只有一次；正文经 ``derive_messages`` 逐字匹配。
- C3 关箱后 late spool 保留、不写账；reopen 后可补吞。
- C4 崩溃窗口（insert 已落、unlink 失败）：at-least-once，靠 spool_id 对账，
  本文件明确**不许**断言 exactly-once。
- C5 损坏 JSON 隔离成 .invalid、原件字节留档、不从撕裂字节凭空造消息。

账本是最小 ``RecordingLedger``：逐条记真实 ``EpisodeEvent``，故障标志只在 ``add``
里置位（模拟 ``ContinuousAgentEpisode.add`` 对 store 失败的 latch：置标志、吞 OSError、
返回 None），``persistence_failed`` 就是读这个标志——不是 mock 返回值。

影子变异：``K3_INBOX_SHADOW=1`` 时，把候选 ``episode_inbox.py`` 源码读出，**仅**精确撤掉
``ingest_spool`` 中 ``storage_failed`` 保留文件的保护（``{"inbox_closed", "storage_failed"}``
→ ``{"inbox_closed"}``），模块先登记 ``sys.modules`` 再 exec。预期：只有 C1 红，其余仍绿。
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_messages import (
    derive_messages,
    sha256_text,
    user_message,
)

CANDIDATE_ROOT = Path(os.environ["PYTHONPATH"].split(os.pathsep)[0])
_SHADOW_NAME = "k3_shadow_episode_inbox"
# 变异定位锚点：必须在候选源码里恰好出现一次，否则拒绝构造 shadow（不许静默错杀）。
_SHADOW_ANCHOR = 'if receipt.reason in {"inbox_closed", "storage_failed"}:'
_SHADOW_REVERTED = 'if receipt.reason in {"inbox_closed"}:'


def _load_shadow_module():
    """加载候选 inbox 的影子副本，仅撤掉 storage_failed 的保留文件保护。"""
    source_path = CANDIDATE_ROOT / "intelligence" / "services" / "episode_inbox.py"
    source = source_path.read_text(encoding="utf-8")
    assert source.count(_SHADOW_ANCHOR) == 1, "影子变异锚点不唯一，拒绝构造"
    mutated = source.replace(_SHADOW_ANCHOR, _SHADOW_REVERTED)
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader(_SHADOW_NAME, loader=None)
    )
    module.__file__ = str(source_path)
    sys.modules[_SHADOW_NAME] = module  # 先登记 sys.modules，再 exec（dataclass 解析需要）
    exec(compile(mutated, str(source_path), "exec"), module.__dict__)
    return module


@pytest.fixture(scope="module")
def inbox_mod():
    """基线轮用候选真模块；shadow 轮（K3_INBOX_SHADOW=1）用精确变异副本。"""
    if os.environ.get("K3_INBOX_SHADOW") == "1":
        return _load_shadow_module()
    return importlib.import_module("intelligence.services.episode_inbox")


class RecordingLedger:
    """最小 durable 账本：成功的写入落成 ``EpisodeEvent``。

    故障只在 ``add`` 里发生并置 ``self.failed`` latch（与真实 episode 的
    ``store_failures`` 同形）；失败写入不进 ``events``，返回 None，不抛给调用方。
    """

    def __init__(self) -> None:
        self.events: list[EpisodeEvent] = []
        self.attempts: list[str] = []  # 含失败尝试，供「试没试过写」对账
        self.failed = False
        self._fail_on: dict[str, int] = {}

    def fail_next(self, kind: str, times: int = 1) -> None:
        self._fail_on[kind] = self._fail_on.get(kind, 0) + times

    def is_failed(self) -> bool:
        return self.failed

    def add(self, kind: str, payload: dict[str, object]):
        self.attempts.append(kind)
        if self.failed or self._fail_on.get(kind, 0) > 0:
            if not self.failed:
                self._fail_on[kind] -= 1
            self.failed = True  # 故障标志在 add 时设置
            return None
        event = EpisodeEvent(len(self.events) + 1, kind, dict(payload))
        self.events.append(event)
        return event

    def kinds(self, kind: str) -> list[EpisodeEvent]:
        return [e for e in self.events if e.kind == kind]


def _make_inbox(inbox_mod, ledger: RecordingLedger, tmp_path: Path):
    spool = tmp_path / inbox_mod.INBOX_SPOOL_DIRNAME
    inbox = inbox_mod.Inbox(ledger, spool=spool, persistence_failed=ledger.is_failed)
    return inbox, spool


def _join(events: list[EpisodeEvent]) -> str:
    return json.dumps([e.to_dict() for e in events], ensure_ascii=False)


# ── C1：保存 insert 失败不删文件、不 claim、字节保持 ────────────────────────────


@pytest.mark.parametrize(
    "failure_shape",
    ["deferred_short_circuit", "mid_insert_write"],
    ids=["deferred_short_circuit", "mid_insert_write"],
)
def test_c1_failed_insert_keeps_spool_file_and_blocks_claim(inbox_mod, tmp_path, failure_shape):
    ledger = RecordingLedger()
    inbox, spool = _make_inbox(inbox_mod, ledger, tmp_path)
    # 先有一条 durable 在途消息，证明失败前通道是好的。
    first = inbox.send(user_message("在途消息", source="probe"), target="next_step")
    assert first.accepted
    ledger.fail_next("inbox_inserted")  # 故障在下一次 add 时置位
    if failure_shape == "deferred_short_circuit":
        # 形状 A：故障已被前一次直接投递踩爆（经 add 置位），spool 条的 send 在入口短路。
        tripped = inbox.send(user_message("直接投递", source="probe"), target="next_step")
        assert not tripped.accepted and tripped.reason == "storage_failed"
    # 形状 B（mid_insert_write）：spool 条自己的 inbox_inserted add 炸掉。
    path = inbox_mod.write_spool_record(
        spool, inbox_mod.SpoolRecord("sp-fail", "保存失败期间的话")
    )
    original_bytes = path.read_bytes()

    assert inbox.ingest_spool() == 0, "insert 没落账就不许销毁运输副本"
    assert path.exists(), "保存失败时必须保留 spool 文件"
    assert path.read_bytes() == original_bytes, "磁盘原件字节必须保持"

    inserted = ledger.kinds("inbox_inserted")
    assert len(inserted) == 1 and inserted[0].payload["content"] == "在途消息"
    assert not any(e.payload.get("spool_id") == "sp-fail" for e in inserted), \
        "失败的消息不许出现 inbox_inserted 事实"

    # 失败期间不 claim：一条 claim 事实都不许落，在途消息留在箱里。
    assert inbox.claim("next_step") == []
    assert ledger.kinds("inbox_claimed") == []
    assert inbox.pending("next_step") == 1, "在途消息仍在箱内，等待存储恢复"
    # 再次吞槽仍不许销毁文件。
    assert inbox.ingest_spool() == 0 and path.exists()


# ── C2：正常落账才删文件；claim 只有一次；derive_messages 正文匹配 ───────────────


def test_c2_durable_insert_then_unlink_single_claim_derives(inbox_mod, tmp_path):
    ledger = RecordingLedger()
    inbox, spool = _make_inbox(inbox_mod, ledger, tmp_path)
    p_step = inbox_mod.write_spool_record(
        spool, inbox_mod.SpoolRecord("sp-a", "第一句补充", target="next_step")
    )
    p_turn = inbox_mod.write_spool_record(
        spool, inbox_mod.SpoolRecord("sp-b", "第二句补充", target="next_turn", source="cli")
    )

    assert inbox.ingest_spool() == 2
    assert not p_step.exists() and not p_turn.exists(), "落账成功后才删文件"
    assert sorted(spool.glob(f"*{inbox_mod.INBOX_SPOOL_SUFFIX}")) == []
    assert [e.kind for e in ledger.events] == ["inbox_inserted", "inbox_inserted"]
    linked = {e.payload["message_id"]: e.payload.get("spool_id") for e in ledger.events}
    assert linked == {"inbox-1": "sp-a", "inbox-2": "sp-b"}
    assert ledger.events[0].payload["content_sha256"] == sha256_text("第一句补充")

    # 文件已删，重复吞槽不得产生任何新事实（不重复 inserted）。
    assert inbox.ingest_spool() == 0
    assert len(ledger.events) == 2

    claimed_step = inbox.claim("next_step")
    assert [m.content for m in claimed_step] == ["第一句补充"]
    assert inbox.claim("next_step") == [], "claim 只有一次：再认领必须为空"
    claimed_turn = inbox.claim("next_turn")
    assert [m.content for m in claimed_turn] == ["第二句补充"]

    claimed_events = ledger.kinds("inbox_claimed")
    assert [e.payload["message_id"] for e in claimed_events] == ["inbox-1", "inbox-2"]
    # 正文经 derive_messages 从事件流派生、与投递内容逐字匹配。
    derived = derive_messages(ledger.events)
    assert [m.content for m in derived] == ["第一句补充", "第二句补充"]
    assert all(m.role == "user" for m in derived)


# ── C3：关箱后 late spool 保留、不写账 ─────────────────────────────────────────


def test_c3_late_spool_after_close_kept_and_not_written(inbox_mod, tmp_path):
    ledger = RecordingLedger()
    inbox, spool = _make_inbox(inbox_mod, ledger, tmp_path)
    assert inbox.discard_all(reason="episode_finished") == 0
    assert inbox.closed

    late = inbox_mod.write_spool_record(
        spool, inbox_mod.SpoolRecord("sp-late", "收口后到的话")
    )
    original_bytes = late.read_bytes()
    n_events = len(ledger.events)

    assert inbox.ingest_spool() == 0, "关箱不吞"
    assert inbox.pending() == 0
    assert late.exists() and late.read_bytes() == original_bytes, "关箱后运输副本保留"
    assert len(ledger.events) == n_events == 0, "关箱后一条事实都不许写"

    receipt = inbox.send(user_message("进程内迟到", source="probe"), target="next_step")
    assert not receipt.accepted and receipt.reason == "inbox_closed"
    assert not ledger.events, "inbox_closed 回执不落账"

    inbox.reopen()
    assert inbox.ingest_spool() == 1, "reopen 后迟到的运输副本必须补吞，不丢话"
    assert not late.exists()
    inserted = ledger.kinds("inbox_inserted")
    assert len(inserted) == 1
    assert inserted[0].payload.get("spool_id") == "sp-late"
    assert inserted[0].payload["content"] == "收口后到的话"
    assert inserted[0].payload["content_sha256"] == sha256_text("收口后到的话")


# ── C4：崩溃窗口 at-least-once，靠 spool_id 对账 ────────────────────────────────


def test_c4_crash_window_is_at_least_once_reconciled_by_spool_id(inbox_mod, tmp_path):
    ledger = RecordingLedger()
    inbox, spool = _make_inbox(inbox_mod, ledger, tmp_path)
    content = "崩溃窗口消息"
    path = inbox_mod.write_spool_record(spool, inbox_mod.SpoolRecord("sp-crash", content))

    # insert 落账后、unlink 前制造真实崩溃窗口：目录去写权限 → unlink 必然 EACCES。
    os.chmod(spool, 0o555)
    try:
        with pytest.raises(OSError):
            inbox.ingest_spool()
    finally:
        os.chmod(spool, 0o755)

    inserted_before = [
        e for e in ledger.kinds("inbox_inserted") if e.payload.get("spool_id") == "sp-crash"
    ]
    assert len(inserted_before) == 1, "崩溃窗口内 inserted 已 durable"
    assert path.exists(), "unlink 失败，运输副本还在 → 重吞不可避免"

    # 恢复后重吞：同 spool_id 第二条 inserted，at-least-once 在账上可见、可对账。
    assert inbox.ingest_spool() == 1 and not path.exists()
    inserted = [
        e for e in ledger.kinds("inbox_inserted") if e.payload.get("spool_id") == "sp-crash"
    ]
    assert len(inserted) == 2, \
        "at-least-once：不许冒称 exactly-once（此断言写死重吞产生第二条 inserted 的形状）"
    assert {e.payload["content_sha256"] for e in inserted} == {sha256_text(content)}
    assert {e.payload["message_id"] for e in inserted} == {"inbox-1", "inbox-2"}

    # 重复送达对模型可见，不得被吞没：claim 出两条、派生出两条同正文消息。
    claimed = inbox.claim("next_step")
    assert [m.content for m in claimed] == [content, content]
    derived = derive_messages(ledger.events)
    assert [m.content for m in derived] == [content, content]
    claimed_ids = [e.payload["message_id"] for e in ledger.kinds("inbox_claimed")]
    assert len(claimed_ids) == len(set(claimed_ids)) == 2


# ── C5：损坏 JSON 隔离，不凭空造消息 ───────────────────────────────────────────


def test_c5_corrupt_spool_quarantined_without_fabricating(inbox_mod, tmp_path):
    ledger = RecordingLedger()
    inbox, spool = _make_inbox(inbox_mod, ledger, tmp_path)
    spool.mkdir(parents=True, exist_ok=True)
    # 撕裂 JSON：UTF-8 合法、JSON 不完整（文件名排到最前，先被处理）。
    torn = spool / f"00000000000000000001-torn{inbox_mod.INBOX_SPOOL_SUFFIX}"
    torn_bytes = '{"spool_id": "x", "content": "被截断的话'.encode("utf-8")
    torn.write_bytes(torn_bytes)
    # JSON 合法但形状不全（缺 content）。
    shapeless = spool / f"00000000000000000002-shape{inbox_mod.INBOX_SPOOL_SUFFIX}"
    shapeless.write_text(json.dumps({"spool_id": "y"}), encoding="utf-8")
    shapeless_bytes = shapeless.read_bytes()  # 先快照原件字节，再吞槽
    good = inbox_mod.write_spool_record(
        spool, inbox_mod.SpoolRecord("sp-good", "完好的话")
    )

    assert inbox.ingest_spool() == 1, "只吞完好的那一条"
    for bad, kept in ((torn, torn_bytes), (shapeless, shapeless_bytes)):
        quarantined = spool / (bad.name + ".invalid")
        assert not bad.exists() and quarantined.exists(), "坏文件改名隔离"
        assert quarantined.read_bytes() == kept, "隔离保留原件字节供人查"
    assert not good.exists(), "完好那条落账后才删"

    inserted = ledger.kinds("inbox_inserted")
    assert len(inserted) == 1 and inserted[0].payload["content"] == "完好的话"
    stream = _join(ledger.events)
    assert "被截断的话" not in stream, "不许从撕裂字节凭空造消息进账"
    assert "torn" not in stream and "shape" not in stream

    claimed = inbox.claim("next_step")
    assert [m.content for m in claimed] == ["完好的话"]
    derived = derive_messages(ledger.events)
    assert [m.content for m in derived] == ["完好的话"]

    # .invalid 不会再被当槽文件处理。
    assert inbox.ingest_spool() == 0
    assert (spool / (torn.name + ".invalid")).exists()
