"""The real author boundary keeps one format across native episode stages."""

from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.finish_authoring import finish_author_contract, saved_finish_format
from intelligence.services.episode_messages import derive_messages, to_provider
from intelligence.services.episode_restore import RestoreUnavailable
from intelligence.services.episode_store import MemoryEpisodeStore, EpisodeState
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.owned_result_support import frame_context
from intelligence.tests.test_owned_results_runtime import _Model, _registry, _repair_goal
from intelligence.services.agent_runtime import EpisodeEvent, ModelTurn
from intelligence.tests.owned_result_support import finish_payload


class BoundaryStop(BaseException):
    pass


def test_real_continuous_opening_delivers_one_author_format():
    captured = []

    class BoundaryModel:
        def complete(self, *, messages, **_kwargs):
            captured.extend(messages)
            raise BoundaryStop()

    frame, context = frame_context()
    with pytest.raises(BoundaryStop):
        ContinuousAgentEpisode(BoundaryModel()).run(
            task_frame=frame, context=context, registry=ResearchToolRegistry(()),
        )
    system = captured[0]["content"]
    payload = json.loads(captured[1]["content"])
    assert payload.get("finish_format") == finish_author_contract(context).prompt_payload()
    assert '"draft":"自然语言回答"' not in system
    assert "未提供 finish_format 时使用下面的旧格式" not in system
    assert "最终正文" in system


@pytest.mark.parametrize("stage", ["invalid", "repair", "finalizer"])
def test_real_continuous_revision_and_finalizer_repeat_the_opening_format(stage):
    class Model(_Model):
        def complete(self, *, messages, **kwargs):
            if self.calls < 2 or (stage == "repair" and self.calls == 2):
                return super().complete(messages=messages, **kwargs)
            self.calls += 1
            self.seen.append(json.loads(json.dumps(messages)))
            if stage == "finalizer" and self.calls <= 4:
                return ModelTurn("", (), error="provider_error")
            if self.calls == 3:
                return ModelTurn("完整正文尚未装入 JSON。", ())
            return ModelTurn(json.dumps(finish_payload(draft="同日主线量价资格已核对。")), ())

    frame, context = frame_context(task_id=f"author-{stage}")
    model, states = Model(), []
    episode = ContinuousAgentEpisode(model)
    outcome = episode.run(task_frame=frame, context=context, registry=_registry(model.source), _continuation_sink=states)
    if stage == "repair":
        outcome = episode.resume(states[0], outcome, replace(_repair_goal(context), unsupported_claims=("待复核的原句。",)))
    assert outcome.status == "completed"
    expected = json.loads(model.seen[0][1]["content"])["finish_format"]
    actual_user = model.seen[-1][-1]["content"]
    if stage == "repair":
        assert json.loads(actual_user)["finish_format"] == expected
        assert "完整 draft" not in actual_user
    elif stage == "finalizer":
        assert json.loads(actual_user)["finish_format"] == expected
        assert '"draft":"自然语言回答"' not in model.seen[-1][0]["content"]
    else:
        assert json.loads(actual_user.rsplit("\n", 1)[-1])["finish_format"] == expected
    tool = next(message for message in model.seen[2] if message["role"] == "tool")
    instruction = json.loads(tool["content"])["owned_results"]["instruction"]
    assert "finish_format" in instruction and "draft为空" not in instruction
    assert outcome.events[-1].payload.get("owned_answer") is None


def test_actual_codex_schema_file_selects_the_context_author_contract():
    from intelligence.runtime.codex_headless_runtime import CodexHeadlessRuntime

    frame, context = frame_context()
    schemas = []

    def capture(command):
        schemas.append(json.loads((command.cwd / "episode-finish.schema.json").read_text()))
        raise BoundaryStop()

    with pytest.raises(BoundaryStop):
        CodexHeadlessRuntime(command_runner=capture).run(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    assert schemas == [finish_author_contract(context).schema_payload()]


@pytest.mark.parametrize("legacy_draft", [False, True])
def test_real_free_only_and_legacy_body_reach_semantic_public_without_owned_receipt(monkeypatch, legacy_draft):
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, recheck_owned_public_delivery
    from intelligence.services.episode_verifier import verify_episode_outcome

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    text = "已取得同日板块观察，后续分析仍需核验。"

    class FreeModel(_Model):
        def complete(self, **kwargs):
            if self.calls < 2:
                return super().complete(**kwargs)
            self.calls += 1
            wire = finish_payload(draft=text) if legacy_draft else finish_payload([text])
            return ModelTurn(json.dumps(wire), ())

    frame, context = frame_context(task_id=f"free-only-{legacy_draft}")
    model = FreeModel()
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=_registry(model.source))
    assert outcome.status == "completed" and outcome.draft == text
    assert outcome.events[-1].payload.get("owned_answer") is None
    verified = verify_episode_outcome(context.contract, outcome)
    semantic = SemanticEpisodeVerifier().verify(frame=frame, structurally_verified=verified, context=context, deadline=context.deadline)
    public = recheck_owned_public_delivery(semantic, context=context, projected=semantic.public_answer)
    assert public.owned_coverage is None and public.verified._owned_answer is None
    assert "owned_coverage" not in public.to_dict()


def _legacy_archive():
    return json.loads((Path(__file__).parent / "fixtures/episode_opening_legacy_20261008.json").read_text())


def test_true_legacy_restore_prefix_cannot_gain_the_current_default_author():
    from datetime import date
    from intelligence.services.research_contract import InformationCutoff
    from intelligence.tests.test_episode_protocol import _frame, _context, _registry as legacy_registry
    from intelligence.runtime.episode_finalizer import EpisodeFinalizer

    archive = _legacy_archive()
    events = tuple(EpisodeEvent(**item) for item in archive["events"])
    state = EpisodeState.from_dict(archive["state"])
    frame = _frame()
    context = replace(_context(frame), information_cutoff=InformationCutoff(date(2026, 10, 8), "runtime_default"))
    store = MemoryEpisodeStore()
    store.append(context.contract.task_id, events)
    store.put_state(context.contract.task_id, state)
    restored = ContinuousAgentEpisode.restore(context.contract.task_id, store, context=context, registry=legacy_registry(),
                                              now=datetime.fromisoformat(state.deadline_at) - timedelta(seconds=1))
    assert restored.disposition == "resumable" and restored.plan.action == "retry_model"
    captured = []

    class Capture:
        def complete(self, *, messages, **_kwargs):
            captured.extend(messages)
            return ModelTurn("{}", ())

    Capture().complete(messages=to_provider(derive_messages(restored.events)))
    assert sha256(json.dumps(captured, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest() == "a412664e7d52aedb67df336ab914a32d010464457d41be738a22362e4afa8da5"
    assert saved_finish_format(restored.events, context=context) is None
    captured.clear()
    EpisodeFinalizer(Capture()).recover(task_frame=frame, context=context, evidence=(), gaps=(), failure_reason="interrupted",
                                       finish_format=saved_finish_format(restored.events, context=context))
    assert "finish_format" not in json.loads(captured[1]["content"])
    assert '"draft":"自然语言回答"' in captured[0]["content"]


@pytest.mark.parametrize("damage", [None, "unknown", "corrupt", "other_owner", "unknown_prompt_source"])
def test_new_native_restore_rejects_unknown_or_corrupt_author_without_new_writes(damage):
    frame, context = frame_context(task_id=f"restore-author-{damage}")
    store = MemoryEpisodeStore()
    episode = ContinuousAgentEpisode(_Model(), store=store)
    drive = episode.manual_drive(task_frame=frame, context=context, registry=ResearchToolRegistry(()))
    drive.run_until("model_pending")
    drive.close()
    events, state = store.load(context.contract.task_id)
    if damage is not None:
        initial = next(event for event in events if event.kind == "prompt_assembled")
        payload = json.loads(initial.payload["user"])
        if damage == "unknown":
            payload["finish_format"]["format"] = "unknown_author"
        elif damage == "corrupt":
            payload["finish_format"]["wire_template"] = "{"
        elif damage == "other_owner":
            payload["finish_format"]["format"] = "material_claims_v1"
        raw = json.dumps(payload, ensure_ascii=False)
        replacement = replace(initial, payload={**initial.to_dict()["payload"], "user": raw, "user_sha256": sha256(raw.encode()).hexdigest()})
        if damage == "unknown_prompt_source":
            replacement = replace(replacement, payload={**replacement.to_dict()["payload"], "source": "unknown_prompt_source"})
        events = tuple(replacement if event is initial else event for event in events)
        store = MemoryEpisodeStore()
        store.append(context.contract.task_id, events)
        store.put_state(context.contract.task_id, state)
        before = store.load(context.contract.task_id)
        with pytest.raises(RestoreUnavailable, match="author"):
            ContinuousAgentEpisode.restore(context.contract.task_id, store, context=context, registry=ResearchToolRegistry(()))
        assert store.load(context.contract.task_id) == before
    else:
        restored = ContinuousAgentEpisode.restore(context.contract.task_id, store, context=context, registry=ResearchToolRegistry(()))
        expected = finish_author_contract(context).prompt_payload()
        assert saved_finish_format(restored.events, context=context) == expected
        # A later finalizer description is another model conversation, never
        # the identity of the original episode author.
        later = EpisodeEvent(len(restored.events) + 1, "prompt_assembled", {"source": "finalizer", "user": '{"finish_format":{"format":"unknown_author"}}'})
        assert saved_finish_format((*restored.events, later), context=context) == expected


def test_old_custom_steering_signature_is_called_at_the_true_recovery_boundary():
    class CustomHarness(FinanceResearchHarness):
        def steering_message(self, kind, *, detail):
            return super().steering_message(kind, detail=detail)

    class Model(_Model):
        def complete(self, **kwargs):
            if self.calls < 2:
                return super().complete(**kwargs)
            self.calls += 1
            self.seen.append(kwargs["messages"])
            if self.calls == 3:
                return ModelTurn("未包装的完整正文。", ())
            return ModelTurn(json.dumps(finish_payload(draft="同日主线观察已核对。")), ())

    frame, context = frame_context()
    model = Model()
    outcome = ContinuousAgentEpisode(model, harness=CustomHarness()).run(task_frame=frame, context=context, registry=_registry(model.source))
    assert outcome.status == "completed"
    repeated = json.loads(model.seen[-1][-1]["content"].rsplit("\n", 1)[-1])
    assert repeated["finish_format"] == finish_author_contract(context).prompt_payload()


@pytest.mark.parametrize("invalid_repair", [False, True])
def test_actual_legacy_same_process_repair_keeps_saved_author_and_carries_original_on_failure(invalid_repair):
    from datetime import date
    from intelligence.services.research_contract import InformationCutoff
    from intelligence.tests.test_episode_protocol import _frame, _context, _registry as legacy_registry

    original = to_provider(derive_messages(EpisodeEvent(**item) for item in _legacy_archive()["events"]))

    class LegacyHarness(FinanceResearchHarness):
        def assemble_prompt(self, *_args):
            return original[0]["content"], original[1]["content"]

    class Writer:
        def __init__(self):
            self.seen = []

        def complete(self, *, messages, **_kwargs):
            self.seen.append(json.loads(json.dumps(messages)))
            if invalid_repair and len(self.seen) > 1:
                return ModelTurn("invalid repair", ())
            return ModelTurn(json.dumps({
                "status": "partial", "draft": "行情尚未核验。" if len(self.seen) == 1 else "本轮仍未核验行情。",
                "gaps": ["缺行情数据"], "bindings": [{"output_id": "direct_assessment", "evidence_hashes": [],
                    "basis": "evidence", "gap": "缺行情数据"}],
            }), ())

    frame = _frame()
    context = replace(_context(frame), information_cutoff=InformationCutoff(date(2026, 10, 8), "runtime_default"))
    writer, states = Writer(), []
    episode = ContinuousAgentEpisode(writer, harness=LegacyHarness())
    first = episode.run(task_frame=frame, context=context, registry=legacy_registry(), _continuation_sink=states)
    repaired = episode.resume(states[0], first, _repair_goal(context))
    repair = next(json.loads(message["content"]) for message in writer.seen[-1] if message["role"] == "user"
                  and message["content"].startswith('{"kind": "REPAIR_GOAL"'))
    assert "finish_format" not in repair
    assert writer.seen[-1][0]["content"] == original[0]["content"]
    assert repaired.events[-1].payload.get("owned_answer") is None
    if invalid_repair:
        assert repaired.draft == first.draft and repaired.stop_reason == "invalid_repair_finish"


def test_old_material_descriptor_location_is_used_by_real_restore_and_finalizer():
    from intelligence.runtime.episode_finalizer import EpisodeFinalizer
    from intelligence.tests.test_material_answer_authoring import history_setup, compact_finish

    frame, context = history_setup()
    store, registry = MemoryEpisodeStore(), ResearchToolRegistry(())
    drive = ContinuousAgentEpisode(_Model(), store=store).manual_drive(task_frame=frame, context=context, registry=registry)
    drive.run_until("model_pending")
    drive.close()
    events, state = store.load(context.contract.task_id)
    initial = next(event for event in events if event.kind == "prompt_assembled")
    payload = json.loads(initial.payload["user"])
    expected = payload.pop("finish_format")
    assert payload["material_grounding"]["finish_format"] == expected
    raw = json.dumps(payload, ensure_ascii=False)
    original_system = to_provider(derive_messages(EpisodeEvent(**item) for item in _legacy_archive()["events"]))[0]["content"]
    archived = replace(initial, payload={**initial.to_dict()["payload"], "user": raw, "user_sha256": sha256(raw.encode()).hexdigest(),
                                         "system": original_system, "system_sha256": sha256(original_system.encode()).hexdigest()})
    old_store = MemoryEpisodeStore()
    old_store.append(context.contract.task_id, tuple(archived if event is initial else event for event in events))
    old_store.put_state(context.contract.task_id, state)
    restored = ContinuousAgentEpisode.restore(context.contract.task_id, old_store, context=context, registry=registry)
    assert restored.disposition == "resumable"
    chosen = saved_finish_format(restored.events, context=context)
    assert chosen == expected
    calls = []

    class Writer:
        def complete(self, *, messages, **_kwargs):
            calls.append(messages)
            return ModelTurn(json.dumps(compact_finish()), ())

    EpisodeFinalizer(Writer()).recover(task_frame=frame, context=context, evidence=(), gaps=(), failure_reason="interrupted", finish_format=chosen)
    finalizer = json.loads(calls[0][1]["content"])
    assert finalizer["finish_format"] == finalizer["material_grounding"]["finish_format"] == expected
    assert context.contract.allowed_capabilities == ()


@pytest.mark.parametrize("kind", ["old_signature", "kwargs", "explicit_format", "default", "internal_type_error",
                                  "positional_or_keyword", "positional_only", "varargs_named"])
def test_real_injected_finalizer_signature_is_compatible_without_retrying_internal_errors(kind):
    from intelligence.runtime.episode_finalizer import EpisodeFinalizer

    calls, requests = [], []

    class Writer:
        def complete(self, *, messages, **_kwargs):
            requests.append(messages)
            return ModelTurn(json.dumps(finish_payload(draft="同日主线观察已核对。")), ())

    class Delegate:
        def call(self, **kwargs):
            calls.append(kwargs)
            if kind == "internal_type_error":
                raise TypeError("inside finalizer implementation")
            return EpisodeFinalizer(Writer()).recover(**kwargs)

    class OldFinalizer(Delegate):
        def recover(self, *, task_frame, context, evidence, gaps, failure_reason, on_prompt=None,
                    evidence_priority=(), domain_materials=None):
            return self.call(task_frame=task_frame, context=context, evidence=evidence, gaps=gaps,
                             failure_reason=failure_reason, on_prompt=on_prompt,
                             evidence_priority=evidence_priority, domain_materials=domain_materials)

    class KwargsFinalizer(Delegate):
        def recover(self, **kwargs):
            return self.call(**kwargs)

    class ExplicitFinalizer(Delegate):
        def recover(self, *, task_frame, context, evidence, gaps, failure_reason, on_prompt=None,
                    evidence_priority=(), domain_materials=None, finish_format=None):
            return self.call(task_frame=task_frame, context=context, evidence=evidence, gaps=gaps,
                             failure_reason=failure_reason, on_prompt=on_prompt, finish_format=finish_format,
                             evidence_priority=evidence_priority, domain_materials=domain_materials)

    class PositionalKeywordFinalizer(Delegate):
        def recover(self, finish_format=None, *, task_frame, context, evidence, gaps, failure_reason, on_prompt=None,
                    evidence_priority=(), domain_materials=None):
            return self.call(task_frame=task_frame, context=context, evidence=evidence, gaps=gaps,
                             failure_reason=failure_reason, on_prompt=on_prompt, finish_format=finish_format,
                             evidence_priority=evidence_priority, domain_materials=domain_materials)

    class PositionalOnlyFinalizer(Delegate):
        def recover(self, finish_format=None, /, *, task_frame, context, evidence, gaps, failure_reason, on_prompt=None,
                    evidence_priority=(), domain_materials=None):
            assert finish_format is None
            return self.call(task_frame=task_frame, context=context, evidence=evidence, gaps=gaps,
                             failure_reason=failure_reason, on_prompt=on_prompt,
                             evidence_priority=evidence_priority, domain_materials=domain_materials)

    class VarargsFinalizer(Delegate):
        def recover(self, *finish_format, task_frame, context, evidence, gaps, failure_reason, on_prompt=None,
                    evidence_priority=(), domain_materials=None):
            assert finish_format == ()
            return self.call(task_frame=task_frame, context=context, evidence=evidence, gaps=gaps,
                             failure_reason=failure_reason, on_prompt=on_prompt,
                             evidence_priority=evidence_priority, domain_materials=domain_materials)

    class Model(_Model):
        def complete(self, **kwargs):
            if self.calls < 2:
                return super().complete(**kwargs)
            self.calls += 1
            return ModelTurn("", (), error="provider_error")

    frame, context = frame_context(task_id=f"finalizer-signature-{kind}")
    model = Model()
    implementations = {"old_signature": OldFinalizer, "kwargs": KwargsFinalizer,
                       "explicit_format": ExplicitFinalizer, "internal_type_error": ExplicitFinalizer,
                       "positional_or_keyword": PositionalKeywordFinalizer,
                       "positional_only": PositionalOnlyFinalizer, "varargs_named": VarargsFinalizer}
    finalizer = EpisodeFinalizer(Writer()) if kind == "default" else implementations[kind]()
    outcome = ContinuousAgentEpisode(model, finalizer=finalizer).run(task_frame=frame, context=context, registry=_registry(model.source))
    if kind == "internal_type_error":
        assert len(calls) == 1 and requests == []
        assert outcome.stop_reason == "finalization_recovery_failed"
        assert any(event.kind == "model_error" and event.payload.get("reason") == "finalization_recovery_exception:TypeError"
                   for event in outcome.events)
    else:
        assert outcome.stop_reason == "finalization_recovered" and len(requests) == 1
        if kind in {"old_signature", "positional_only", "varargs_named"}:
            assert len(calls) == 1 and "finish_format" not in calls[0]
        else:
            expected = finish_author_contract(context).prompt_payload()
            assert json.loads(requests[0][1]["content"])["finish_format"] == expected


@pytest.mark.parametrize("kind", ["positional_only", "positional_or_keyword", "varargs_named", "keyword_only", "kwargs"])
def test_real_steering_interface_obeys_all_five_parameter_kinds(kind):
    from intelligence.services.finish_authoring import describe_finish_format
    from intelligence.services.research_harness import steering_message_for_author

    calls = []

    class PositionalOnly(FinanceResearchHarness):
        def steering_message(self, kind, finish_format=None, /, *, detail):
            calls.append(finish_format)
            return "custom message"

    class PositionalKeyword(FinanceResearchHarness):
        def steering_message(self, kind, finish_format=None, *, detail):
            calls.append(finish_format)
            return describe_finish_format("custom message", finish_format)

    class Varargs(FinanceResearchHarness):
        def steering_message(self, kind, *finish_format, detail):
            assert finish_format == ()
            calls.append(None)
            return "custom message"

    class KeywordOnly(FinanceResearchHarness):
        def steering_message(self, kind, *, detail, finish_format=None):
            calls.append(finish_format)
            return describe_finish_format("custom message", finish_format)

    class Kwargs(FinanceResearchHarness):
        def steering_message(self, kind, **kwargs):
            calls.append(kwargs["finish_format"])
            return describe_finish_format("custom message", kwargs["finish_format"])

    implementations = {"positional_only": PositionalOnly, "positional_or_keyword": PositionalKeyword,
                       "varargs_named": Varargs, "keyword_only": KeywordOnly, "kwargs": Kwargs}
    expected = finish_author_contract(frame_context()[1]).prompt_payload()
    result = steering_message_for_author(implementations[kind](), "invalid_finish", detail="reason", finish_format=expected)
    assert calls == [None if kind in {"positional_only", "varargs_named"} else expected]
    assert json.loads(result.rsplit("\n", 1)[-1])["finish_format"] == expected


@pytest.mark.parametrize("value", [None, False, "", "missing"])
@pytest.mark.parametrize("top_present", [False, True])
def test_real_restore_distinguishes_missing_material_format_from_present_invalid_values(value, top_present):
    from intelligence.tests.test_material_answer_authoring import history_setup

    frame, context = history_setup()
    store, registry = MemoryEpisodeStore(), ResearchToolRegistry(())
    drive = ContinuousAgentEpisode(_Model(), store=store).manual_drive(task_frame=frame, context=context, registry=registry)
    drive.run_until("model_pending")
    drive.close()
    events, state = store.load(context.contract.task_id)
    assert len(events) == 5
    initial = next(event for event in events if event.kind == "prompt_assembled")
    payload = json.loads(initial.payload["user"])
    expected = payload["finish_format"]
    if not top_present:
        payload.pop("finish_format")
    if value == "missing":
        payload["material_grounding"].pop("finish_format")
    else:
        payload["material_grounding"]["finish_format"] = value
    raw = json.dumps(payload, ensure_ascii=False)
    changed = replace(initial, payload={**initial.to_dict()["payload"], "user": raw, "user_sha256": sha256(raw.encode()).hexdigest()})
    damaged = MemoryEpisodeStore()
    damaged.append(context.contract.task_id, tuple(changed if event is initial else event for event in events))
    damaged.put_state(context.contract.task_id, state)
    before = damaged.load(context.contract.task_id)
    if value == "missing":
        restored = ContinuousAgentEpisode.restore(context.contract.task_id, damaged, context=context, registry=registry)
        assert restored.disposition == "resumable"
        assert saved_finish_format(restored.events, context=context) == (expected if top_present else None)
    else:
        with pytest.raises(RestoreUnavailable, match="author"):
            ContinuousAgentEpisode.restore(context.contract.task_id, damaged, context=context, registry=registry)
        assert damaged.load(context.contract.task_id) == before
