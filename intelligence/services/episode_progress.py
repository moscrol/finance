"""Project private Episode events into replayable user-facing progress.

The Episode ledger contains model messages, queries, tool identities, hashes,
and provider diagnostics.  None of those values may cross the public Run/SSE
seam.  This module is the single projection and persistence owner for live
continuous-runtime progress.

The tool **name** is a narrow, deliberate exception -- and not really an
exception to the rule above.  It is used only as an *enum key* into
``_TOOL_LABELS``, a table we own; what crosses the seam is our hard-coded
Chinese label, never the payload value.  A name we do not recognise falls back
to the generic sentence, so an unregistered tool degrades the wording instead
of leaking its identity.

--------------------------------------------------------------------------
Why this lives in services (D5)
--------------------------------------------------------------------------

No runtime imports: the projector is a pure kind→milestone map, and the
publisher only talks to ``RunStore`` (already services).  It is a **different
contract** from ``episode_projection`` (the artifact ``events`` array).
Unknown kinds return ``None`` — the UI stays silent — unlike the artifact
boundary, which keeps the event and flags ``unregistered_kinds``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import re
from threading import RLock

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.run_store import RunStore


_PROGRESS_STATUSES = frozenset({"running", "completed", "failed"})
_PROGRESS_STAGES = frozenset(
    {"understanding", "planning", "research", "repair", "verification", "finalizing"}
)
_SAFE_KEY = re.compile(r"^[a-z][a-z0-9_-]*(?::[a-z0-9_-]+)*$")


@dataclass(frozen=True)
class EpisodeProgress:
    """One public milestone with no model- or provider-controlled prose."""

    key: str
    stage: str
    message: str
    status: str

    def __post_init__(self) -> None:
        key = str(self.key or "").strip().lower()
        stage = str(self.stage or "").strip().lower()
        message = str(self.message or "").strip()
        status = str(self.status or "").strip().lower()
        if not _SAFE_KEY.fullmatch(key):
            raise ValueError("progress key must be a safe non-empty identity")
        if stage not in _PROGRESS_STAGES:
            raise ValueError("unsupported progress stage")
        if not message:
            raise ValueError("progress message must be non-empty")
        if status not in _PROGRESS_STATUSES:
            raise ValueError("unsupported progress status")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "status", status)

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "stage": self.stage,
            "message": self.message,
            "status": self.status,
        }


_EVENT_PROJECTIONS: dict[str, tuple[str, str, str]] = {
    "plan": ("planning", "已形成研究计划。", "completed"),
    "mode_decision": ("planning", "已按任务复杂度确认研究深度。", "completed"),
    "tool_request": ("research", "正在核对计划所需资料。", "running"),
    "tool_result": ("research", "查询已结束，未确认取得可用资料。", "completed"),
    "tool_error": ("research", "一项资料未取得，正在调整研究路径。", "completed"),
    "branch_started": ("research", "已启动并行的只读补充研究。", "running"),
    "branch_completed": ("research", "一项补充研究已返回证据。", "completed"),
    "branch_failed": ("research", "一项补充研究未取得结果，主研究继续。", "completed"),
    "repair_goal": ("repair", "核验发现关键缺口，正在定向补证。", "running"),
    "finalization": ("finalizing", "证据收集完成，正在组织回答。", "running"),
    "finalization_recovery_started": (
        "finalizing",
        "正在基于已取得证据恢复最终回答。",
        "running",
    ),
    "finish": ("finalizing", "研究回答已形成，正在完成最终核验。", "completed"),
    "persistence_failed": ("finalizing", "研究恢复记录保存失败，本轮已停止。", "failed"),
}

# 公开词表：UI 进度覆盖的 kind。是车道表的精选子集，不是第二套分类。
PROGRESS_EVENT_KINDS = frozenset(_EVENT_PROJECTIONS) | {"tool_menu"}

# 工具名 → 面向用户的中文标签。键必须是
# ``research_tool_registry._DEFAULT_TOOL_METADATA`` 的子集，由
# ``test_episode_progress`` 里的一致性测试锁住：新增工具忘了登记会变红。
#
# 为什么这样安全：跨 seam 的是**这张表的值**（我们写死的中文），payload 里的
# 工具名只当查表的键用。查不到就退回通用句 —— 认不出来就 fail closed。
_TOOL_LABELS: dict[str, str] = {
    "finance_query": "本地结构化行情",
    "evidence_search": "知识证据",
    "kb_search": "知识库",
    "web_search": "公开网页",
    "web_fetch": "网页正文",
    "sub_research": "子研究分支",
    "derived_calculation": "沙箱派生计算",
    "news_search": "财经新闻",
    "graph_lookup": "题材图谱",
    "evidence_lookup": "证据原文",
    "memory_lookup": "历史对话记录",
    "l3_lookup": "订单与量产证据",
    "market_data": "盘面快照",
    "financial_data": "财务数据",
    "capital_data": "两融/大宗/解禁数据",
    "mainline_context": "主线结构",
    # 历史发现研究三件（2026-09-09）：没有标签的工具进度会静默退回通用句。
    "history_query": "历史行情重建与样本比较",
    "read_history_result": "历史研究原件",
    "save_history_research": "研究假设草稿",
}


def public_tool_label(name: str) -> str | None:
    """A public label for a known tool, never a provider-supplied fallback."""
    return _TOOL_LABELS.get(name)


# 三个 kind 的工具名落在不同键上：``tool_request`` 来自 ``call.to_dict()``
# （``name``），``tool_result`` / ``tool_error`` 来自网关 payload（``tool``）。
# 两个键都试，别赌某一个运行时的写法。
_TOOL_NAME_KEYS = ("name", "tool")
_TOOL_EVENT_TEMPLATES: dict[str, str] = {
    "tool_request": "正在查{label}。",
    "tool_result": "已取得{label}。",
    "tool_result_without_evidence": "{label}查询已结束，未确认取得可用记录。",
    "tool_error": "{label}未取到，正在调整研究路径。",
}


# 固定进度句的闭集；动态菜单由 is_public_progress_message 用同一标签表校验。
#
# 为什么要把它导出去：``api.app._public_trace_step`` 会**丢掉** step 的
# output_summary、按 stage 重新合成一句话——它必须这么防，因为 trace 步骤还有
# 别的生产者，那些 output_summary 可能带模型措辞。于是本模块辛苦区分出来的
# 「正在查盘面快照。」在跨 seam 时又被拍回「已完成一项证据核对。」。
#
# 2026-08-23 live 实测（:8801 三轮）就是这么发现的：单测全绿、拿历史 payload
# 回放也全绿，UI 上一个工具标签都没出现——**上游写了、下游不读**。
#
# 放行判据用「这句是不是我们自己生成的」而不是「这个 step 来自哪里」：后者要靠
# step_id 前缀猜，前者用同一份固定句/标签表的封闭语法校验，不放行任意前缀文本。
def public_progress_messages() -> frozenset[str]:
    """Fixed progress sentences; menu combinations use the label grammar below."""

    fixed = {message for _stage, message, _status in _EVENT_PROJECTIONS.values()}
    labelled = {
        template.format(label=label)
        for template in _TOOL_EVENT_TEMPLATES.values()
        for label in _TOOL_LABELS.values()
    }
    return frozenset(fixed | labelled)


_MENU_PREFIX = "此步模型可调用工具："
_MENU_SUFFIX = "。授权不代表已调用或服务可用。"
_MENU_EMPTY = "此步未开放可调用工具。"
_MENU_UNKNOWN = "此步工具菜单未记录；不能推断可调用范围。"
_MENU_UNRECOGNIZED = "未识别工具（不展示名称）"


def _tool_menu_message(visible: object) -> str:
    """只读实际菜单，不从 allowed_capabilities / 凭证存在推测服务可用。"""

    # EpisodeEvent 冻结后 list 是 tuple；缺字段/畸形不等于明确空菜单。
    if not isinstance(visible, (list, tuple)) or any(
        not isinstance(name, str) or not name for name in visible
    ):
        return _MENU_UNKNOWN
    if not visible:
        return _MENU_EMPTY
    labels = list(dict.fromkeys(
        _TOOL_LABELS.get(name, _MENU_UNRECOGNIZED) for name in visible
    ))
    return _MENU_PREFIX + "、".join(labels) + _MENU_SUFFIX


def is_public_progress_message(message: str) -> bool:
    """公开边界的闭集校验；动态菜单只许由既有中文枚举标签组成。

    不按前缀放行自由文本，不枚举工具子集的所有排列（指数空间），也不新建工具表。
    """

    if message in public_progress_messages() or message in {_MENU_EMPTY, _MENU_UNKNOWN}:
        return True
    if not message.startswith(_MENU_PREFIX) or not message.endswith(_MENU_SUFFIX):
        return False
    labels = message[len(_MENU_PREFIX):-len(_MENU_SUFFIX)].split("、")
    allowed = set(_TOOL_LABELS.values()) | {_MENU_UNRECOGNIZED}
    return bool(labels) and len(labels) == len(set(labels)) and set(labels) <= allowed


def _tool_label(payload: object) -> str | None:
    """Resolve a payload's tool name against our own closed label table."""

    if not hasattr(payload, "get"):
        return None
    for key in _TOOL_NAME_KEYS:
        name = payload.get(key)
        if isinstance(name, str) and name in _TOOL_LABELS:
            return _TOOL_LABELS[name]
    return None


def project_episode_progress(event: EpisodeEvent) -> EpisodeProgress | None:
    """Return a fixed public projection of one event.

    只有工具名 / tool_menu.visible 作为中文标签枚举键；授权、调用、取回资料分别
    展示。configure 在 episode 工具装配前产生，不能拿它冒充实际可调用菜单。
    """

    if event.kind == "tool_menu":
        return EpisodeProgress(
            key=f"episode:{event.sequence}:tool_menu",
            stage="planning",
            message=_tool_menu_message(event.payload.get("visible")),
            status="completed",
        )
    projection_kind = event.kind
    if event.kind == "branch_failed" and (
        event.payload.get("persistence") == "failed"
        or event.payload.get("error") == "storage_failed"
        or event.payload.get("reason") == "storage_failed"
    ):
        # This is not an isolated missing source: the whole tree is fenced.
        projection_kind = "persistence_failed"
    projection = _EVENT_PROJECTIONS.get(projection_kind)
    if projection is None:
        return None
    stage, message, status = projection
    template = _TOOL_EVENT_TEMPLATES.get(event.kind)
    if event.kind == "tool_result":
        # ok=True 仅说明调用返回，不表示有业务数据；旧事件缺 evidence 也不能猜成功。
        evidence = event.payload.get("evidence")
        if not isinstance(evidence, (tuple, list)) or not evidence or event.payload.get("ok") is False:
            template = _TOOL_EVENT_TEMPLATES["tool_result_without_evidence"]
    if template is not None:
        label = _tool_label(event.payload)
        if label is not None:
            message = template.format(label=label)
    return EpisodeProgress(
        key=f"episode:{event.sequence}:{event.kind}",
        stage=stage,
        message=message,
        status=status,
    )


class RunEpisodeProgressPublisher:
    """Persist one progress event to both trace and replayable SSE exactly once."""

    def __init__(
        self,
        *,
        run_store: RunStore,
        run_id: str,
        conversation_id: str,
        message_id: str,
        is_cancelled: Callable[[], bool] | None = None,
        event_id_prefix: str = "",
    ) -> None:
        if not isinstance(run_store, RunStore):
            raise TypeError("run_store must be a RunStore")
        self._run_store = run_store
        self._run_id = str(run_id or "").strip()
        self._conversation_id = str(conversation_id or "").strip()
        self._message_id = str(message_id or "").strip()
        self._is_cancelled = is_cancelled or (lambda: False)
        self._event_id_prefix = str(event_id_prefix or "")
        if not self._run_id or not self._conversation_id or not self._message_id:
            raise ValueError("progress publisher identities must be non-empty")
        self._published: set[str] = set()
        self._lock = RLock()

    def publish(self, progress: EpisodeProgress) -> None:
        if not isinstance(progress, EpisodeProgress):
            raise TypeError("progress must be EpisodeProgress")
        with self._lock:
            if self._is_cancelled() or progress.key in self._published:
                return
            prefixed_key = f"{self._event_id_prefix}{progress.key}"
            finished_at = (
                datetime.now().astimezone().isoformat()
                if progress.status != "running"
                else None
            )
            step = self._run_store.append_step(
                self._run_id,
                step_id=f"continuous:{prefixed_key}",
                name=progress.stage,
                status=progress.status,
                output_summary=progress.message,
                finished_at=finished_at,
            )
            self._run_store.append_stream_event(
                self._run_id,
                event_id=(
                    f"{self._event_id_prefix}continuous:progress:{progress.key}"
                ),
                event_type="trace.step",
                payload={"step": step},
                conversation_id=self._conversation_id,
                message_id=self._message_id,
            )
            self._published.add(progress.key)


__all__ = [
    "EpisodeProgress",
    "PROGRESS_EVENT_KINDS",
    "RunEpisodeProgressPublisher",
    "project_episode_progress",
    "public_progress_messages",
    "public_tool_label",
    "is_public_progress_message",
]
