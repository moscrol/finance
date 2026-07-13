from __future__ import annotations

import json
import hashlib
import re
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, TimeoutError as FuturesTimeoutError
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from threading import BoundedSemaphore, RLock, Thread

from intelligence.api.structured_reports import (
    ask_result_modules,
    complete_report,
    new_structured_report,
    render_daily_review_answer,
    upsert_report_module,
)
from intelligence.services import run_store as rs
from intelligence.services.ask import (
    AskOptions,
    AskResult,
    Citation,
    answer_query,
    render_conversation_answer,
    synthesize_existing_answer_spec,
)
from intelligence.services.answer_orchestrator import (
    QUESTION_MARKET_REVIEW,
    plan_answer_question,
)
from intelligence.services.conversation_store import (
    Conversation,
    ConversationStore,
    Message,
)
from intelligence.services.execution_budget import ExecutionBudget
from intelligence.services.llm_refine import LLMStreamCancelled
from intelligence.services import perspective_lab
from intelligence.services.query_understanding import understand_query
from intelligence.services.run_store import (
    Artifact,
    ArtifactPayload,
    RunStore,
    redact,
)
from intelligence.services.runtime_inputs import (
    RuntimeResearchInputs,
    probe_market_inputs,
)
from intelligence import userspace
from intelligence.workbench_skills.contracts import (
    SkillExecutionContext,
    SkillOutput,
)
from intelligence.workbench_skills.registry import (
    SkillRegistry,
    builtin_skill_registry,
)
from intelligence.workbench_skills.router import (
    SkillMode,
    SkillRouteResult,
    route_skills,
)

RECENT_MESSAGE_LIMIT = 6
SUMMARY_CHAR_LIMIT = 2400
FINALIZATION_RESERVE_SECONDS = 5.0
SYNTHESIS_RESERVE_SECONDS = 20.0
SKILL_RESERVE_SECONDS = 25.0
_SKILL_WORKER_SLOTS = BoundedSemaphore(8)
RUNTIME_PROBE_TIMEOUT_SECONDS = 0.1
RUNTIME_PROBE_CACHE_TTL_SECONDS = 30.0
RUNTIME_PROBE_LEASE_SECONDS = 1.0
RUNTIME_PROBE_MAX_WORKERS = 4
_RUNTIME_PROBE_LOCK = RLock()
_RUNTIME_PROBE_SLOTS = BoundedSemaphore(RUNTIME_PROBE_MAX_WORKERS)
_RUNTIME_PROBE_GENERATION = 0


@dataclass(frozen=True)
class _RuntimeFileFingerprint:
    canonical_path: str
    exists: bool
    device: int | None
    inode: int | None
    mtime_ns: int | None
    size: int | None


@dataclass(frozen=True)
class _RuntimeDatabaseFingerprint:
    database: _RuntimeFileFingerprint
    wal: _RuntimeFileFingerprint


@dataclass(frozen=True)
class _RuntimeProbeCacheEntry:
    cutoff: str
    fingerprint: _RuntimeDatabaseFingerprint
    expires_at: float


@dataclass(frozen=True)
class _RuntimeProbeInflight:
    future: Future[str | None]
    fingerprint: _RuntimeDatabaseFingerprint | None
    started_at: float
    generation: int


_RUNTIME_PROBE_CACHE: dict[str, _RuntimeProbeCacheEntry] = {}
_RUNTIME_PROBE_INFLIGHT: dict[str, _RuntimeProbeInflight] = {}
_FOLLOW_UP_REFERENCE_PATTERN = re.compile(
    r"(?:^|[，。！？?!；;\s])(?:那|它|其|该公司|这个公司|上述|前述|前面)"
)
_INTERNAL_CITATION_PATTERN = re.compile(
    r"\[(?:D|P|L|G|R|S|W)\d+\]"
)
_INTERNAL_CODE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])[DPGRSW]\d+(?![A-Za-z0-9_])"
)
_EVIDENCE_LAYER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])L([1-4])(?:\s*级(?:别)?)?(?![A-Za-z0-9_])"
)


def _runtime_probe_key(inputs: RuntimeResearchInputs) -> str:
    return "|".join(
        (
            str(inputs.market_db_path),
            str(inputs.exports_dir),
            str(inputs.market_snapshot_dir),
        )
    )


def _runtime_file_fingerprint(path: Path) -> _RuntimeFileFingerprint | None:
    try:
        canonical = path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    try:
        stat = canonical.stat()
    except FileNotFoundError:
        return _RuntimeFileFingerprint(
            canonical_path=str(canonical),
            exists=False,
            device=None,
            inode=None,
            mtime_ns=None,
            size=None,
        )
    except OSError:
        return None
    return _RuntimeFileFingerprint(
        canonical_path=str(canonical),
        exists=True,
        device=stat.st_dev,
        inode=stat.st_ino,
        mtime_ns=stat.st_mtime_ns,
        size=stat.st_size,
    )


def _runtime_db_fingerprint(path: Path) -> _RuntimeDatabaseFingerprint | None:
    database = _runtime_file_fingerprint(path)
    if database is None or not database.exists:
        return None
    wal = _runtime_file_fingerprint(Path(f"{path}.wal"))
    if wal is None:
        return None
    return _RuntimeDatabaseFingerprint(database=database, wal=wal)


def _prune_runtime_probe_state(now: float) -> None:
    for key, cached in tuple(_RUNTIME_PROBE_CACHE.items()):
        if cached.expires_at <= now:
            _RUNTIME_PROBE_CACHE.pop(key, None)
    for key, inflight in tuple(_RUNTIME_PROBE_INFLIGHT.items()):
        if now - inflight.started_at >= RUNTIME_PROBE_LEASE_SECONDS:
            current = _RUNTIME_PROBE_INFLIGHT.get(key)
            if current is inflight:
                _RUNTIME_PROBE_INFLIGHT.pop(key, None)


def _valid_runtime_cutoff(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return value if parsed.isoformat() == value else None


def _runtime_cutoff_with_timeout(inputs: RuntimeResearchInputs) -> str | None:
    global _RUNTIME_PROBE_GENERATION

    key = _runtime_probe_key(inputs)
    now = time.monotonic()
    fingerprint = _runtime_db_fingerprint(inputs.market_db_path)
    start_worker = False
    probe_slots: BoundedSemaphore | None = None
    with _RUNTIME_PROBE_LOCK:
        _prune_runtime_probe_state(now)
        cached = _RUNTIME_PROBE_CACHE.get(key)
        if cached is not None:
            if fingerprint is not None and cached.fingerprint == fingerprint:
                return cached.cutoff
            _RUNTIME_PROBE_CACHE.pop(key, None)
        inflight = _RUNTIME_PROBE_INFLIGHT.get(key)
        if inflight is not None and inflight.fingerprint != fingerprint:
            _RUNTIME_PROBE_INFLIGHT.pop(key, None)
            inflight = None
        if inflight is None:
            probe_slots = _RUNTIME_PROBE_SLOTS
            if not probe_slots.acquire(blocking=False):
                return None
            _RUNTIME_PROBE_GENERATION += 1
            inflight = _RuntimeProbeInflight(
                future=Future(),
                fingerprint=fingerprint,
                started_at=now,
                generation=_RUNTIME_PROBE_GENERATION,
            )
            _RUNTIME_PROBE_INFLIGHT[key] = inflight
            start_worker = True

    if start_worker:
        assert probe_slots is not None

        def probe_once() -> None:
            effective_cutoff: str | None = None
            try:
                try:
                    cutoff = _valid_runtime_cutoff(
                        probe_market_inputs(inputs).duckdb_cutoff
                    )
                except Exception:  # Optional external input boundary.
                    cutoff = None
                completed_fingerprint = _runtime_db_fingerprint(
                    inputs.market_db_path
                )
                if (
                    cutoff is not None
                    and inflight.fingerprint is not None
                    and completed_fingerprint == inflight.fingerprint
                ):
                    effective_cutoff = cutoff
                with _RUNTIME_PROBE_LOCK:
                    current = _RUNTIME_PROBE_INFLIGHT.get(key)
                    if (
                        effective_cutoff is not None
                        and current is not None
                        and current.generation == inflight.generation
                    ):
                        _RUNTIME_PROBE_CACHE[key] = _RuntimeProbeCacheEntry(
                            cutoff=effective_cutoff,
                            fingerprint=inflight.fingerprint,
                            expires_at=(
                                time.monotonic()
                                + RUNTIME_PROBE_CACHE_TTL_SECONDS
                            ),
                        )
            finally:
                with _RUNTIME_PROBE_LOCK:
                    current = _RUNTIME_PROBE_INFLIGHT.get(key)
                    if (
                        current is not None
                        and current.generation == inflight.generation
                    ):
                        _RUNTIME_PROBE_INFLIGHT.pop(key, None)
                probe_slots.release()
                inflight.future.set_result(effective_cutoff)

        worker = Thread(
            target=probe_once,
            name="workbench-runtime-probe",
            daemon=True,
        )
        try:
            worker.start()
        except RuntimeError:
            with _RUNTIME_PROBE_LOCK:
                current = _RUNTIME_PROBE_INFLIGHT.get(key)
                if (
                    current is not None
                    and current.generation == inflight.generation
                ):
                    _RUNTIME_PROBE_INFLIGHT.pop(key, None)
            probe_slots.release()
            inflight.future.set_result(None)
            return None

    try:
        return inflight.future.result(timeout=RUNTIME_PROBE_TIMEOUT_SECONDS)
    except FuturesTimeoutError:
        return None
_INTERNAL_TIER_TOKEN_PATTERN = re.compile(
    r"(?:high/)?L[1-4](?:_L[1-4])+(?:_[A-Za-z0-9]+)*",
    re.IGNORECASE,
)
_EVIDENCE_LAYER_SUMMARY_PATTERN = re.compile(
    r"(?:整体)?证据层分布为\s*"
    r"L[1-4](?:\s*[×x*]\s*\d+)?"
    r"(?:\s*[、,，]\s*L[1-4](?:\s*[×x*]\s*\d+)?)*"
    r"\s*[，,]?\s*"
)


def _turn_work_seconds(answer_deadline_seconds: float) -> float:
    return max(
        1.0,
        answer_deadline_seconds - FINALIZATION_RESERVE_SECONDS,
    )


class _SkillRunStoreGuard:
    """Minimal artifact-only capability for background skills.

    Deliberately do not proxy arbitrary RunStore methods: a late skill may stage
    one artifact, but it cannot mutate provenance, steps, degrades, or run state.
    """

    def __init__(self, store: RunStore, stopped: Callable[[], bool]) -> None:
        self._store = store
        self._cancelled = stopped
        self._stopped = False
        self._lock = RLock()
        self._run_id: str | None = None
        self._staged: dict[str, ArtifactPayload] = {}

    def add_artifact(
        self,
        run_id: str,
        filename: str,
        content: str | bytes,
        *,
        renderer: str,
        title: str,
    ) -> Artifact:
        with self._lock:
            if self._stopped or self._cancelled():
                return self._discarded_artifact(filename, renderer, title)
            if self._run_id is not None and self._run_id != run_id:
                raise ValueError("skill artifact staging supports one run")
            self._run_id = run_id
            data = content.encode("utf-8") if isinstance(content, str) else content
            artifact = Artifact(
                artifact_id=f"artifact_{filename.replace('.', '_')}",
                path=filename,
                renderer=renderer,
                title=title,
                sha256=hashlib.sha256(data).hexdigest(),
                bytes=len(data),
            )
            self._staged[filename] = ArtifactPayload(
                filename,
                content,
                renderer,
                title,
            )
            return artifact

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            self._staged.clear()

    def commit(self) -> bool:
        with self._lock:
            if self._stopped or self._cancelled():
                self._staged.clear()
                return False
            run_id = self._run_id
            payloads = tuple(self._staged.values())
            self._staged.clear()
            self._stopped = True
        if run_id is None:
            return True
        return self._store.add_artifacts_if_active(run_id, payloads) is not None

    @staticmethod
    def _discarded_artifact(filename: str, renderer: str, title: str) -> Artifact:
        return Artifact(
            artifact_id=f"discarded_{filename.replace('.', '_')}",
            path=filename,
            renderer=renderer,
            title=title,
            sha256="",
            bytes=0,
            previewable=False,
            downloadable=False,
        )


def _start_skill_worker(
    future: Future[SkillOutput],
    execute: Callable[[], SkillOutput],
    *,
    name: str,
) -> None:
    def run() -> None:
        try:
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(execute())
            except BaseException as exc:  # noqa: BLE001
                future.set_exception(exc)
        finally:
            _SKILL_WORKER_SLOTS.release()

    Thread(target=run, name=name, daemon=True).start()
_INTERNAL_FIELD_PATTERN = re.compile(
    r'"?(?:candidate_tier|priority_score|cycle_status|warnings?)"?'
    r'\s*[:=]\s*(?:"[^"]*"|[^,，}\]\n]+)[,，]?',
    re.IGNORECASE,
)
_JSON_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*[\[{].*?[\]}]\s*```",
    re.IGNORECASE | re.DOTALL,
)
_HUMAN_READABLE_REPLACEMENTS = (
    (
        "knowledge-base · wiki/relations/entity_exposures.json",
        "本地知识库 · 公司题材关联",
    ),
    (
        "knowledge-base · wiki/relations/evidence_index.json",
        "本地知识库 · 公司证据索引",
    ),
    ("knowledge-base · wiki/relations/", "本地知识库 · "),
    ("daily-agent", "每日复盘流程"),
    ("Daily Review 确定性投影数据", "本地复盘数据"),
    ("Daily Review", "本地复盘"),
    ("本地复盘确定性投影数据", "本地复盘数据"),
    ("本地复盘确定性投影", "本地复盘数据"),
    ('并被系统标注为"沸点"', '，盘面状态达到"沸点"'),
    ("系统统一标注为", "盘面表现为"),
    ("盘面 L4 信号", "盘面信号"),
    ("盘面L4信号", "盘面信号"),
    ("L4 信号", "盘面信号"),
    ("L4信号", "盘面信号"),
    ("L3 硬证据", "公告等硬证据"),
    ("L3硬证据", "公告等硬证据"),
    ("RAG检索的wiki向量源降级未接入", "知识库资料没有提供可用补充"),
    ("RAG 检索的 wiki 向量源降级未接入", "知识库资料没有提供可用补充"),
    ("replay 发酵信号也未匹配到任何主题", "历史发酵信号也未提供可用信息"),
    ("replay 发酵信号", "历史发酵信号"),
    ("模块 replay", "历史信号回检"),
    ("replay", "历史信号回检"),
    ("wiki 向量检索无可用命中", "知识库没有提供可用补充"),
    ("wiki 向量检索", "知识库检索"),
    ("wiki向量源", "知识库资料"),
    ("wiki 向量源", "知识库资料"),
    ("wiki-rag", "知识库检索"),
    ("图谱命中的", "知识图谱关联到的"),
    ("图谱命中", "知识图谱关联"),
    ("graph_only低置信关联", "低置信关联"),
    ("graph_only/低置信暴露", "低置信关联"),
    ("graph_only", "低置信关联"),
    ("DuckDB 同题材强势替代队列为空", "本地盘面数据没有提供同题材强势替代方向"),
    ("snapshot/export", "历史盘面快照"),
    ("capacity_industry", "成交容量居前"),
    ("market_context", "市场环境"),
    ("knowledge_evidence", "知识库候选资料"),
    ("exposure_only", "仅有概念关联"),
    ("L1_L3_candidate", "候选资料，需公告或年报确认"),
    ("DuckDB", "本地市场数据"),
    ("命中主题=", "相关主题："),
    ("命中主要来自", "现有信息主要来自"),
    ("cycle_status", "阶段状态"),
    ("candidate_tier", "候选分层"),
    ("priority_score", "优先级"),
    ("diff_ratio", "成交边际变化"),
    ("模块路由", "分析路径"),
    ("deep-dive", "产业链研究"),
    ("disclosure-archive → apply", "官方公告与年报"),
    ("图谱·语义召回(知识库向量)", "知识库补充"),
    ("图谱·语义召回(wiki 向量)", "知识库补充"),
    ("检索可观测", "资料覆盖情况"),
    ("输出质检", "回答质量检查"),
    ("theme-radar", "题材盘面快照"),
    ("double_red", "涨幅与边际量同步增强"),
    ("new_high_cluster", "新高个股聚集"),
    ("new_high_direction", "新高方向确认"),
    ("limit_advance_cluster", "连板晋级聚集"),
    ("limit_heat", "涨停热度"),
    ("super_capacity", "超大容量"),
    ("long_tail", "长尾观察"),
    ("score_detail.", "盘面信号."),
    ("medium/", "中置信/"),
    ("low/", "低置信/"),
    ("high/", "高置信/"),
    (
        "Temporal Facts 层尚未接入：以上证据仅按 source_date 标注新鲜度；"
        "正式版应把会过期/被证伪的事实建成带 status(active/superseded/invalidated) 的时序边",
        "时效边界：以上证据仅按来源日期标注，使用前需复核是否仍然有效。",
    ),
    ("rerank", "检索重排"),
    ("RAG 遥测", "检索诊断"),
    ("RAG", "知识库检索"),
    ("wiki", "知识库"),
    ("降权", "降低可信度"),
)
_EVIDENCE_LAYER_REPLACEMENTS = {
    "1": "行业资料",
    "2": "公司基础资料",
    "3": "公告等硬证据",
    "4": "盘面信号",
}
_CREDENTIAL_IDENTIFIER_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\b"
)
_LOCAL_PATH_PATTERN = re.compile(r"/(?:Users|home)/|[A-Za-z]:\\")
_INTERNAL_ERROR_PATTERN = re.compile(
    r"Traceback|File \".+\", line \d+|"
    r"\b[A-Za-z_][\w.]+(?:Error|Exception)\b"
)
_INTERNAL_RETRIEVAL_DIAGNOSTIC_PATTERN = re.compile(
    r"Fetching\s+\d+\s+files:|Loading weights:|"
    r"检索方式=hybrid|BM25|BGE-m3|RRF|"
    r"\bchunk(?:_id)?=|\bhash=|\bindex=|\bk=\d+|耗时=\d+ms|状态=empty|"
    r"[DMVW]\s*源|命中来源分布|检索质量裁定|公告等硬证据覆盖|"
    r"--mode\b|\b\w+\.py\b",
    re.IGNORECASE,
)
_PUBLIC_REPORT_REPLACEMENTS = (
    ("research_1_summary", "结论"),
    ("research_2_evidence", "证据链"),
    ("research_3_risks", "分歧反证"),
    ("research_4_actions", "后续验证点"),
    ("research_5_telemetry", "资料覆盖情况"),
    ("research_6_review", "回答质量检查"),
    ("research_7_implications", "交易含义"),
    ("research_8_sources", "引用来源"),
    (
        "llm_unavailable_template_answer",
        "自然语言综合暂时不可用；已保留可核验数据与结构化产物。",
    ),
    ("answer-orchestrator", "问题理解"),
    ("ask_retrieval_pipeline", "研究检索流程"),
    ("deterministic_projection", "确定性数据整理"),
    ("deterministic_duckdb_query", "本地数据查询"),
    ("retrieved_evidence", "已检索证据"),
    ("canonical", "原始来源"),
    ("disclosure-archive → apply", "官方公告与年报"),
    ("图谱·语义召回(知识库向量)", "知识库补充"),
    ("图谱·语义召回(wiki 向量)", "知识库补充"),
    (
        "模块·deep-dive（产业维 · radar.py --mode deep-dive 题材深拆）",
        "产业链研究",
    ),
    ("模块·deep-dive", "产业链研究"),
    ("[deep-dive]", ""),
    (
        "Temporal Facts 层尚未接入：以上证据仅按 source_date 标注新鲜度；"
        "正式版应把会过期/被证伪的事实建成带 status(active/superseded/invalidated) 的时序边",
        "时效边界：以上证据仅按来源日期标注，使用前需复核是否仍然有效。",
    ),
)


@dataclass(frozen=True)
class ConversationContext:
    summary: str
    recent_messages: tuple[Message, ...]

    def to_prompt_block(self) -> str:
        recent = "\n".join(
            f"{message.role}: {message.content}" for message in self.recent_messages
        )
        return (
            "## 较早消息摘要\n"
            f"{self.summary or '（无较早消息）'}\n\n"
            "## 最近消息原文\n"
            f"{recent or '（无历史消息）'}"
        )


@dataclass(frozen=True)
class TurnResult:
    status: str
    content: str
    selected_skill_ids: tuple[str, ...]
    invoked_skill_ids: tuple[str, ...]


def _skill_owner_result(query: str, output: SkillOutput) -> AskResult:
    contract = output.answer_contract
    if contract is None:
        raise ValueError("skill owner output requires an answer contract")
    citations = [
        Citation(
            tag=f"K{index}",
            source=str(
                citation.get("title")
                or citation.get("source")
                or output.skill_id
            ),
            detail=str(citation.get("source") or ""),
        )
        for index, citation in enumerate(output.citations, start=1)
    ]
    return AskResult(
        query=query,
        trade_date=output.as_of,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        found_graph=bool(contract.answer_spec.verified_facts),
        question_plan=plan_answer_question(
            query,
            question_type_override=contract.question_type,
        ),
        citations=citations,
        answer_spec=contract.answer_spec,
    )


def _summarize_messages(messages: Sequence[Message]) -> str:
    text = "\n".join(f"{message.role}: {message.content}" for message in messages)
    if len(text) <= SUMMARY_CHAR_LIMIT:
        return text
    return "…" + text[-(SUMMARY_CHAR_LIMIT - 1) :]


def _redact_object(value: object) -> object:
    if isinstance(value, str):
        return sanitize_user_visible_artifact_text(value)
    if isinstance(value, list):
        return [_redact_object(item) for item in value]
    if isinstance(value, dict):
        return {
            redact(str(key)): _redact_object(item)
            for key, item in value.items()
        }
    return value


def _sanitize_citation_list(
    citations: list[dict[str, object]],
) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for citation in citations:
        item = dict(citation)
        for key in ("source", "detail", "label", "title"):
            value = item.get(key)
            if isinstance(value, str):
                item[key] = sanitize_user_visible_artifact_text(value)
        sanitized.append(item)
    return sanitized


def sanitize_user_visible_artifact_text(text: str) -> str:
    cleaned = redact(text)
    if re.search(r"未配置 LLM key", cleaned, re.IGNORECASE):
        return "自然语言综合暂时不可用；已保留可核验数据与结构化产物。"
    if re.search(r"HF_TOKEN|Hugging\s*Face", cleaned, re.IGNORECASE):
        return "外部语义检索当前不可用或受限，未使用其结果。"
    if _INTERNAL_RETRIEVAL_DIAGNOSTIC_PATTERN.search(cleaned):
        return "外部语义检索当前不可用或受限，未使用其结果。"
    if _LOCAL_PATH_PATTERN.search(cleaned):
        return "本地研究数据（路径已隐藏）。"
    if _INTERNAL_ERROR_PATTERN.search(cleaned):
        return "研究过程中出现内部错误；相关结果未纳入结论。"
    cleaned = sanitize_conversation_answer(cleaned)
    cleaned = _CREDENTIAL_IDENTIFIER_PATTERN.sub("模型服务凭据", cleaned)
    for internal, readable in _PUBLIC_REPORT_REPLACEMENTS:
        cleaned = cleaned.replace(internal, readable)
    return cleaned


def sanitize_conversation_answer(text: str) -> str:
    cleaned = _JSON_BLOCK_PATTERN.sub("", text)
    cleaned = re.sub(
        r"(?m)^.*(?:Fetching\s+\d+\s+files:|Loading weights:|"
        r"检索方式=hybrid|BM25|BGE-m3|RRF|"
        r"\bchunk(?:_id)?=|\bhash=|\bindex=|\bk=\d+|"
        r"耗时=\d+ms|状态=empty|[DMVW]\s*源|命中来源分布|"
        r"检索质量裁定|公告等硬证据覆盖|--mode\b|\b\w+\.py\b).*$",
        "外部语义检索当前不可用或受限，未使用其结果。",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = _INTERNAL_FIELD_PATTERN.sub("", cleaned)
    cleaned = _EVIDENCE_LAYER_SUMMARY_PATTERN.sub("", cleaned)
    cleaned = _INTERNAL_CITATION_PATTERN.sub("", cleaned)
    cleaned = re.sub(
        r"\bMarketAdapter\.get_[A-Za-z0-9_]+\b",
        "本地盘面数据",
        cleaned,
    )
    for internal, readable in _HUMAN_READABLE_REPLACEMENTS:
        cleaned = cleaned.replace(internal, readable)
    cleaned = re.sub(
        r"\b(?:True|False)\b",
        lambda match: "是" if match.group(0) == "True" else "否",
        cleaned,
    )
    cleaned = _INTERNAL_TIER_TOKEN_PATTERN.sub("较高置信候选", cleaned)
    cleaned = _EVIDENCE_LAYER_PATTERN.sub(
        lambda match: _EVIDENCE_LAYER_REPLACEMENTS[match.group(1)],
        cleaned,
    )
    cleaned = re.sub(
        r"公告等硬证据(?:\s*(?:的\s*)?(?:硬)?证据)+",
        "公告等硬证据",
        cleaned,
    )
    cleaned = re.sub(r"行业资料(?:\s*行业资料)+", "行业资料", cleaned)
    cleaned = re.sub(
        r"公司基础资料(?:\s*(?:公司)?基础资料)+", "公司基础资料", cleaned
    )
    cleaned = re.sub(r"盘面信号(?:\s*盘面信号)+", "盘面信号", cleaned)
    cleaned = re.sub(r"盘面\s*盘面信号", "盘面信号", cleaned)
    cleaned = re.sub(r"公告等硬证据\s*(?=(?:公告|订单|认证|量产|客户验证))", "", cleaned)
    cleaned = re.sub(
        r"(?<![A-Za-z])local(?![A-Za-z])", "本地", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"本地\s*本地", "本地", cleaned)
    cleaned = re.sub(r"本地复盘\s*确定性投影(?:数据)?", "本地复盘数据", cleaned)
    cleaned = cleaned.replace("知识知识图谱", "知识图谱")
    cleaned = cleaned.replace("确定性投影", "数据")
    cleaned = re.sub(r"本地复盘数据(?:\s*数据)+", "本地复盘数据", cleaned)
    cleaned = re.sub(r"\bnormal\b", "常规容量", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"质量\s+medium\b", "质量中等", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"质量\s+high\b", "质量较高", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"质量\s+low\b", "质量较低", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\btarget=([^\s]+)\s+source=",
        r"对象=\1；来源=",
        cleaned,
    )
    cleaned = cleaned.replace("[[", "").replace("]]", "")
    cleaned = _INTERNAL_CODE_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", cleaned)
    cleaned = re.sub(r" +([，。；：、])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_conversation_context(
    conversation: Conversation,
    messages: Sequence[Message],
    *,
    current_run_id: str,
) -> ConversationContext:
    history = [
        message
        for message in messages
        if message.run_id != current_run_id
        and message.status == "completed"
        and message.role in {"user", "assistant"}
        and message.content.strip()
    ]
    recent = tuple(history[-RECENT_MESSAGE_LIMIT:])
    older = history[:-RECENT_MESSAGE_LIMIT]
    summary = _summarize_messages(older) if older else conversation.summary
    return ConversationContext(summary=summary, recent_messages=recent)


def contextualize_follow_up_query(
    query: str,
    context: ConversationContext,
) -> str:
    cleaned = query.strip()
    if not _FOLLOW_UP_REFERENCE_PATTERN.search(cleaned):
        return cleaned
    previous_user = next(
        (
            message.content.strip()
            for message in reversed(context.recent_messages)
            if message.role == "user" and message.content.strip()
        ),
        "",
    )
    if not previous_user:
        return cleaned
    return f"{previous_user}\n追问：{cleaned}"


class _ProgressProducer:
    def __init__(self, emitter: _TurnProgressEmitter, producer_id: str) -> None:
        self._emitter = emitter
        self.producer_id = producer_id

    def __call__(self, stage: str, status: str) -> None:
        self._emitter.emit(self.producer_id, stage, status)

    def revoke(self) -> None:
        self._emitter.revoke(self.producer_id)


class _TurnProgressEmitter:
    """Best-effort stage stream with isolated, revocable producers."""

    def __init__(
        self,
        *,
        can_emit: Callable[[], bool],
        emit_event: Callable[[str, str, int], None],
    ) -> None:
        self._can_emit = can_emit
        self._emit_event = emit_event
        self._lock = RLock()
        self._active = True
        self._sequence = 0
        self._producers: set[str] = set()
        self._running: set[tuple[str, str]] = set()

    def producer(self, producer_id: str) -> _ProgressProducer:
        with self._lock:
            if self._active:
                self._producers.add(producer_id)
        return _ProgressProducer(self, producer_id)

    def emit(self, producer_id: str, stage: str, status: str) -> None:
        with self._lock:
            self._emit_locked(producer_id, stage, status)

    def revoke(self, producer_id: str) -> None:
        with self._lock:
            if producer_id not in self._producers:
                return
            stages = sorted(
                stage
                for current_producer, stage in self._running
                if current_producer == producer_id
            )
            for stage in stages:
                self._emit_locked(producer_id, stage, "degraded")
            self._producers.discard(producer_id)
            self._running = {
                item for item in self._running if item[0] != producer_id
            }

    def close(self) -> None:
        with self._lock:
            for producer_id in sorted(self._producers):
                self.revoke(producer_id)
            self._active = False
            self._producers.clear()
            self._running.clear()

    def _emit_locked(self, producer_id: str, stage: str, status: str) -> None:
        if not self._active or producer_id not in self._producers:
            return
        try:
            allowed = self._can_emit()
        except Exception:
            allowed = False
        if not allowed:
            self._disable_locked()
            return
        key = (producer_id, stage)
        if status == "running":
            self._running.add(key)
        else:
            self._running.discard(key)
        self._sequence += 1
        try:
            self._emit_event(stage, status, self._sequence)
        except Exception:
            self._disable_locked()

    def _disable_locked(self) -> None:
        self._active = False
        self._producers.clear()
        self._running.clear()


class TurnOrchestrator:
    def __init__(
        self,
        *,
        repo_root: Path,
        conversation_store: ConversationStore,
        run_store: RunStore,
        runtime_inputs: RuntimeResearchInputs | None = None,
        answer_query_fn: Callable[[AskOptions], AskResult] | None = None,
        route_skills_fn: Callable[..., SkillRouteResult] | None = None,
        skill_registry: SkillRegistry | None = None,
        llm_configured: bool = False,
        llm_model: str | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        cancellation_reason: Callable[[], str | None] | None = None,
        claim_terminal: Callable[[], bool] | None = None,
        event_id_prefix: str = "",
        answer_deadline_seconds: float = 60.0,
        budget_factory: Callable[[], ExecutionBudget] | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.runtime_inputs = runtime_inputs or RuntimeResearchInputs.from_roots(
            code_root=repo_root,
            data_root=repo_root,
            users_root=repo_root / "intelligence" / "users",
            knowledge_wiki=repo_root / "wiki",
            vector_index_dir=repo_root / ".rag_index",
        )
        self.conversation_store = conversation_store
        self.run_store = run_store
        self.answer_query = answer_query_fn or answer_query
        self.route_skills = route_skills_fn or route_skills
        self.skill_registry = skill_registry or builtin_skill_registry()
        self.llm_configured = llm_configured
        self.llm_model = llm_model
        self.is_cancelled = is_cancelled or (lambda: False)
        self.cancellation_reason = cancellation_reason or (lambda: None)
        self.claim_terminal = claim_terminal or (lambda: True)
        self.event_id_prefix = event_id_prefix
        self.answer_deadline_seconds = answer_deadline_seconds
        self.budget_factory = budget_factory

    def run_turn(
        self,
        *,
        conversation_id: str,
        run_id: str,
        assistant_message_id: str,
        query: str,
        skill_mode: SkillMode,
        selected_skill_ids: Sequence[str],
        perspective_mode: str = perspective_lab.PERSPECTIVE_MODE_NEUTRAL,
        selected_perspective_ids: Sequence[str] = (),
    ) -> TurnResult:
        turn_started = time.monotonic()
        execution_budget = (
            self.budget_factory()
            if self.budget_factory is not None
            else ExecutionBudget.start(
                _turn_work_seconds(self.answer_deadline_seconds)
            )
        )
        report = new_structured_report(
            run_id=run_id,
            question=query,
            task_type="ask",
            llm_configured=self.llm_configured,
        )
        selected: list[str] = []
        manual_selected = list(dict.fromkeys(selected_skill_ids))
        invoked: list[str] = []
        warnings: list[str] = []
        citations: list[dict[str, object]] = []
        text_chunks: list[str] = []
        skill_outputs: list[SkillOutput] = []
        skill_timed_out = False

        def can_emit_progress() -> bool:
            if self.is_cancelled():
                return False
            try:
                run = self.run_store.load_run(run_id)
            except (OSError, ValueError):
                return False
            return run.status == rs.STATUS_RUNNING

        def append_progress_event(stage: str, status: str, sequence: int) -> None:
            self._emit(
                run_id,
                assistant_message_id,
                f"stage:{stage}:{sequence:02d}",
                "stage.progress",
                {
                    "stage": stage,
                    "status": status,
                    "elapsed_ms": self._elapsed_ms(turn_started),
                },
                conversation_id,
            )

        turn_progress = _TurnProgressEmitter(
            can_emit=can_emit_progress,
            emit_event=append_progress_event,
        )

        self._emit(
            run_id,
            assistant_message_id,
            "message:start",
            "message.start",
            {"status": "running"},
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "report:start",
            "report.start",
            {"report": report},
            conversation_id,
        )
        runtime_cutoff = _runtime_cutoff_with_timeout(self.runtime_inputs)
        if runtime_cutoff is not None:
            try:
                self.run_store.update_provenance(
                    run_id,
                    duckdb_cutoff=runtime_cutoff,
                )
            except (OSError, ValueError):
                pass
        try:
            conversation = self.conversation_store.load_conversation(conversation_id)
            context = build_conversation_context(
                conversation,
                self.conversation_store.load_messages(conversation_id),
                current_run_id=run_id,
            )
            self.conversation_store.update_summary_text(
                conversation_id, context.summary
            )
            contextual_query = contextualize_follow_up_query(query, context)
            primary_question_plan = plan_answer_question(contextual_query)
            primary_question_type = primary_question_plan.question_type
            understanding_progress = turn_progress.producer("turn:understanding")
            understanding_progress("understanding", "running")
            try:
                routing_envelope = understand_query(contextual_query)
                route_started = time.monotonic()
                route = self.route_skills(
                    contextual_query,
                    "ask",
                    skill_mode,
                    selected_skill_ids,
                    registry=self.skill_registry.definitions,
                    query_envelope=routing_envelope,
                    primary_question_type=primary_question_type,
                    llm_timeout=execution_budget.child_timeout(5, reserve=50),
                    execution_budget=execution_budget,
                )
            except Exception:
                understanding_progress("understanding", "degraded")
                understanding_progress.revoke()
                raise
            selected = [selection.skill_id for selection in route.selections]
            understanding_progress("understanding", "completed")
            understanding_progress.revoke()
            self._trace(
                run_id,
                assistant_message_id,
                conversation_id,
                "route",
                "route_skills",
                {
                    "selected": [
                        {
                            "skill_id": selection.skill_id,
                            "source": selection.selection_source,
                            "reason": selection.reason,
                        }
                        for selection in route.selections
                    ],
                    "fallback_to_ask": route.fallback_to_ask,
                    "base_finance_fallback": route.base_finance_fallback,
                    "query_envelope": routing_envelope.to_dict(),
                    "elapsed_ms": self._elapsed_ms(route_started),
                },
            )
            self._check_cancelled()

            for selection_index, selection in enumerate(route.selections, start=1):
                self._check_cancelled()
                skill_id = selection.skill_id
                skill_timeout = execution_budget.child_timeout(
                    self.skill_registry.definitions[skill_id].timeout_seconds,
                    reserve=SKILL_RESERVE_SECONDS,
                )
                if skill_timeout <= 0:
                    warning = f"Skill {skill_id} 因时间预算不足已跳过"
                    warnings.append(warning)
                    self.run_store.add_degrade(run_id, warning)
                    module = self._skill_warning_module(skill_id, warning)
                    self._emit_module(
                        run_id,
                        assistant_message_id,
                        conversation_id,
                        report,
                        module,
                        f"skill:{skill_id}:warning",
                    )
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"skill:{skill_id}:result",
                        "skill.result",
                        {
                            "skill_id": skill_id,
                            "status": "degraded",
                            "warnings": [warning],
                            "elapsed_ms": 0,
                            "task_may_continue": False,
                        },
                        conversation_id,
                    )
                    continue
                if not _SKILL_WORKER_SLOTS.acquire(blocking=False):
                    warning = f"Skill {skill_id} 因并发容量不足已跳过"
                    warnings.append(warning)
                    self.run_store.add_degrade(run_id, warning)
                    module = self._skill_warning_module(skill_id, warning)
                    self._emit_module(
                        run_id,
                        assistant_message_id,
                        conversation_id,
                        report,
                        module,
                        f"skill:{skill_id}:warning",
                    )
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"skill:{skill_id}:result",
                        "skill.result",
                        {
                            "skill_id": skill_id,
                            "status": "degraded",
                            "warnings": [warning],
                            "elapsed_ms": 0,
                            "task_may_continue": False,
                        },
                        conversation_id,
                    )
                    continue
                skill_progress = turn_progress.producer(
                    f"skill:{selection_index}:{skill_id}"
                )
                future: Future[SkillOutput] = Future()
                guarded_run_store = _SkillRunStoreGuard(
                    self.run_store,
                    self.is_cancelled,
                )
                worker_started = False
                skill_started = time.monotonic()
                try:
                    invoked.append(skill_id)
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"skill:{skill_id}:start",
                        "skill.start",
                        {
                            "skill_id": skill_id,
                            "selection_source": selection.selection_source,
                            "reason": selection.reason,
                        },
                        conversation_id,
                    )
                    skill_context = SkillExecutionContext(
                        query=contextual_query,
                        task_type="ask",
                        user_id=self.run_store.user_id,
                        run_id=run_id,
                        conversation_id=conversation_id,
                        repo_root=self.repo_root,
                        run_store=guarded_run_store,  # type: ignore[arg-type]
                        runtime_inputs=self.runtime_inputs,
                        conversation_context=context.to_prompt_block(),
                        execution_budget=execution_budget,
                        progress_callback=skill_progress,
                    )
                    _start_skill_worker(
                        future,
                        lambda: self.skill_registry.executors[skill_id].execute(
                            skill_context
                        ),
                        name=f"workbench-{skill_id}",
                    )
                    worker_started = True
                    output = future.result(timeout=skill_timeout)
                except Exception as exc:  # noqa: BLE001
                    skill_progress.revoke()
                    if isinstance(exc, FuturesTimeoutError) and future is not None:
                        skill_timed_out = True
                        future.cancel()
                    warning = (
                        f"Skill {skill_id} 执行超时"
                        if isinstance(exc, FuturesTimeoutError)
                        else f"Skill {skill_id} 执行失败（{type(exc).__name__}）"
                    )
                    warnings.append(warning)
                    self.run_store.add_degrade(run_id, warning)
                    module = self._skill_warning_module(skill_id, warning)
                    self._emit_module(
                        run_id,
                        assistant_message_id,
                        conversation_id,
                        report,
                        module,
                        f"skill:{skill_id}:warning",
                    )
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"skill:{skill_id}:result",
                        "skill.result",
                        {
                            "skill_id": skill_id,
                            "status": "degraded",
                            "warnings": [warning],
                            "elapsed_ms": self._elapsed_ms(skill_started),
                            "task_may_continue": (
                                isinstance(exc, FuturesTimeoutError)
                                and future is not None
                                and not future.done()
                            ),
                        },
                        conversation_id,
                    )
                else:
                    if guarded_run_store.commit():
                        skill_outputs.append(output)
                        warnings.extend(output.warnings)
                        citations.extend(output.citations)
                        for warning in output.warnings:
                            self.run_store.add_degrade(run_id, warning)
                        for index, module in enumerate(output.modules, start=1):
                            self._emit_module(
                                run_id,
                                assistant_message_id,
                                conversation_id,
                                report,
                                module,
                                f"skill:{skill_id}:module:{index}",
                            )
                        self._emit(
                            run_id,
                            assistant_message_id,
                            f"skill:{skill_id}:result",
                            "skill.result",
                            {
                                "skill_id": skill_id,
                                "status": (
                                    "degraded" if output.warnings else "completed"
                                ),
                                "output": asdict(output),
                                "elapsed_ms": self._elapsed_ms(skill_started),
                                "task_may_continue": False,
                            },
                            conversation_id,
                        )
                    else:
                        self._check_cancelled()
                finally:
                    skill_progress.revoke()
                    guarded_run_store.stop()
                    future.cancel()
                    if not worker_started:
                        _SKILL_WORKER_SLOTS.release()
                self._check_cancelled()

            def emit_text_delta(delta: str) -> None:
                self._check_cancelled()
                text_chunks.append(delta)
                self._emit(
                    run_id,
                    assistant_message_id,
                    f"text:{len(text_chunks):06d}",
                    "text.delta",
                    {"delta": delta},
                    conversation_id,
                )

            compose_started = time.monotonic()
            owner_output = next(
                (
                    output
                    for output in skill_outputs
                    if output.answer_contract is not None
                    and output.answer_contract.question_type
                    == primary_question_type
                ),
                None,
            )
            daily_review_output = next(
                (
                    output
                    for output in skill_outputs
                    if output.skill_id == "daily-review"
                ),
                None,
            )
            market_review_requested = primary_question_type == QUESTION_MARKET_REVIEW
            if owner_output is not None:
                result = _skill_owner_result(query, owner_output)
                owner_synthesis_allowance = execution_budget.child_timeout(
                    SYNTHESIS_RESERVE_SECONDS,
                    reserve=FINALIZATION_RESERVE_SECONDS,
                )
                if owner_synthesis_allowance < 4.0:
                    result.llm_fallback_reason = "budget_exhausted"
                else:
                    synthesize_existing_answer_spec(
                        AskOptions(
                            query=contextual_query,
                            user=self.run_store.user_id,
                            compose=True,
                            synthesize=True,
                            use_modules=False,
                            use_wiki_rag=False,
                            compose_self_review=False,
                            compose_revise_on_warn=False,
                            conversation_context=context.to_prompt_block(),
                            perspective_mode=perspective_mode,
                            perspective_ids=tuple(selected_perspective_ids),
                            stream_text_delta=emit_text_delta,
                            stream_cancel_check=self.is_cancelled,
                            execution_budget=execution_budget,
                            llm_model=self.llm_model,
                            llm_timeout=max(
                                1,
                                int(owner_synthesis_allowance),
                            ),
                            llm_finalization_reserve=(
                                FINALIZATION_RESERVE_SECONDS
                            ),
                        ),
                        result,
                    )
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "compose",
                    "skill_answer_owner",
                    {
                        "skill_id": owner_output.skill_id,
                        "retrieval_plan": list(
                            owner_output.answer_contract.retrieval_plan
                        ),
                        "output_contract": list(
                            owner_output.answer_contract.output_contract
                        ),
                    },
                )
            else:
                synthesis_allowance = execution_budget.child_timeout(
                    SYNTHESIS_RESERVE_SECONDS,
                    reserve=FINALIZATION_RESERVE_SECONDS,
                )
                budget_degraded = synthesis_allowance < 4.0
                if budget_degraded:
                    budget_warning = "workbench_time_budget_exhausted_template_answer"
                    warnings.append(budget_warning)
                    self.run_store.add_degrade(run_id, budget_warning)
                per_call_timeout = (
                    max(1, int(synthesis_allowance))
                    if not budget_degraded
                    else 1
                )
                cheap_skill_timeout_fallback = skill_timed_out
                base_progress = turn_progress.producer("turn:base")
                try:
                    result = self.answer_query(
                        AskOptions(
                            query=contextual_query,
                            date=(
                                daily_review_output.as_of
                                if daily_review_output is not None
                                and market_review_requested
                                else None
                            ),
                            user=self.run_store.user_id,
                            compose=not budget_degraded,
                            synthesize=not budget_degraded,
                            use_modules=(
                                not budget_degraded
                                and not cheap_skill_timeout_fallback
                            ),
                            use_wiki_rag=(
                                not budget_degraded
                                and not cheap_skill_timeout_fallback
                            ),
                            compose_self_review=False,
                            compose_revise_on_warn=False,
                            market_db_path=self.runtime_inputs.market_db_path,
                            exports_dir=self.runtime_inputs.exports_dir,
                            kb_wiki=self.runtime_inputs.knowledge_wiki,
                            wiki_rag_index_dir=self.runtime_inputs.vector_index_dir,
                            conversation_context=context.to_prompt_block(),
                            supplemental_evidence=self._skill_evidence(skill_outputs),
                            include_memory_block=(
                                not cheap_skill_timeout_fallback
                            ),
                            include_recall_block=(
                                not cheap_skill_timeout_fallback
                            ),
                            perspective_mode=perspective_mode,
                            perspective_ids=tuple(selected_perspective_ids),
                            stream_text_delta=emit_text_delta,
                            stream_cancel_check=self.is_cancelled,
                            execution_budget=execution_budget,
                            progress_callback=base_progress,
                            llm_timeout=per_call_timeout,
                            llm_finalization_reserve=(
                                FINALIZATION_RESERVE_SECONDS
                            ),
                        )
                    )
                finally:
                    base_progress.revoke()
                if budget_degraded and result.llm_fallback_reason is None:
                    result.llm_fallback_reason = "budget_exhausted"
            self._check_cancelled()
            is_market_review = (
                owner_output is None
                and daily_review_output is not None
                and market_review_requested
            )
            if (
                is_market_review
                and daily_review_output is not None
                and result.trade_date is None
            ):
                result.trade_date = daily_review_output.as_of
            self._record_retrieval(
                run_id,
                assistant_message_id,
                conversation_id,
                result,
                elapsed_ms=self._elapsed_ms(compose_started),
            )
            self.run_store.update_provenance(run_id, source_date=result.trade_date)
            warnings.extend(result.warnings)
            for warning in result.warnings:
                self.run_store.add_degrade(run_id, warning)
            citations.extend(
                {
                    "tag": citation.tag,
                    "source": citation.source,
                    "detail": citation.detail,
                }
                for citation in result.citations
            )
            citations = _sanitize_citation_list(citations)
            for index, module in enumerate(ask_result_modules(result), start=1):
                self._emit_module(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    report,
                    module,
                    f"ask:module:{index}",
                )
            for index, citation in enumerate(citations, start=1):
                self._emit(
                    run_id,
                    assistant_message_id,
                    f"citation:{index:04d}",
                    "citation.ready",
                    {"citation": citation},
                    conversation_id,
                )

            answer_text = render_conversation_answer(result)
            if (
                result.synthesis is None
                and is_market_review
                and daily_review_output is not None
            ):
                answer_text = render_daily_review_answer(
                    date_text=daily_review_output.as_of,
                    modules=daily_review_output.modules,
                    warnings=daily_review_output.warnings,
                )
            if result.synthesis is None and text_chunks:
                answer_text = "".join(text_chunks)
            answer_text = sanitize_conversation_answer(answer_text)
            if not text_chunks:
                emit_text_delta(answer_text)
            perspective_header = perspective_lab.runtime_answer_header(
                userspace.user_space(self.run_store.user_id),
                mode=perspective_mode,
                perspective_ids=tuple(selected_perspective_ids),
            )
            fallback_notice = (
                perspective_lab.runtime_fallback_notice(perspective_mode)
                if result.synthesis is None
                and owner_output is None
                and not is_market_review
                else ""
            )
            answer_prefix = "\n\n".join(
                block for block in (perspective_header, fallback_notice) if block
            )
            answer_text = f"{answer_prefix}\n\n{answer_text}"
            if (
                result.synthesis is None
                and owner_output is None
                and not is_market_review
            ):
                fallback = "llm_unavailable_template_answer"
                warnings.append(fallback)
                self.run_store.add_degrade(run_id, fallback)

            turn_progress.close()
            complete_report(
                report,
                as_of=result.trade_date,
                warnings=warnings,
                llm_provider=result.llm_provider,
                llm_model=self.llm_model if result.llm_provider else None,
                llm_configured=self.llm_configured,
                llm_attempted=result.llm_attempted,
                llm_fallback_reason=result.llm_fallback_reason,
            )
            public_report = _redact_object(report)
            if isinstance(public_report, dict):
                report = public_report
            self._check_cancelled()
            if not self.claim_terminal():
                return self._terminal_state_result(run_id, selected, invoked)
            finished = self.run_store.finish_run_with_artifacts(
                run_id,
                rs.STATUS_COMPLETED,
                (
                    ArtifactPayload(
                        "answer.md",
                        redact(answer_text),
                        "markdown",
                        redact(f"对话回答：{query[:24]}"),
                    ),
                    ArtifactPayload(
                        "report.json",
                        json.dumps(report, ensure_ascii=False, indent=2),
                        "structured_report",
                        "结构化对话报告",
                    ),
                ),
            )
            if finished.status != rs.STATUS_COMPLETED:
                return self._terminal_state_result(run_id, selected, invoked)
            assistant = self.conversation_store.revise_message(
                conversation_id,
                assistant_message_id,
                content=answer_text,
                status="completed",
                selected_skill_ids=manual_selected,
                invoked_skill_ids=invoked,
                citations=citations,
                degrades=warnings,
            )
            self._emit(
                run_id,
                assistant_message_id,
                "report:complete",
                "report.complete",
                {"report": report},
                conversation_id,
            )
            self._emit(
                run_id,
                assistant_message_id,
                "message:complete",
                "message.complete",
                {"message": asdict(assistant)},
                conversation_id,
            )
            return TurnResult(
                status=rs.STATUS_COMPLETED,
                content=assistant.content,
                selected_skill_ids=tuple(selected),
                invoked_skill_ids=tuple(invoked),
            )
        except LLMStreamCancelled:
            turn_progress.close()
            if self.cancellation_reason() == "executor_timeout":
                return self._fail(
                    conversation_id,
                    run_id,
                    assistant_message_id,
                    report,
                    selected,
                    manual_selected,
                    invoked,
                    warnings,
                    citations,
                    text_chunks,
                    TimeoutError("executor_timeout"),
                )
            return self._cancel(
                conversation_id,
                run_id,
                assistant_message_id,
                report,
                selected,
                manual_selected,
                invoked,
                warnings,
                citations,
                text_chunks,
            )
        except Exception as exc:  # noqa: BLE001
            turn_progress.close()
            return self._fail(
                conversation_id,
                run_id,
                assistant_message_id,
                report,
                selected,
                manual_selected,
                invoked,
                warnings,
                citations,
                text_chunks,
                exc,
            )

    def _emit(
        self,
        run_id: str,
        message_id: str,
        event_id: str,
        event_type: str,
        payload: dict[str, object],
        conversation_id: str,
    ) -> None:
        self.run_store.append_stream_event(
            run_id,
            event_id=f"{self.event_id_prefix}{event_id}",
            event_type=event_type,
            payload=payload,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    def _check_cancelled(self) -> None:
        if self.is_cancelled():
            raise LLMStreamCancelled()

    def _emit_module(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        report: dict,
        module: dict,
        event_id: str,
    ) -> None:
        public_module = _redact_object(module)
        if not isinstance(public_module, dict):
            return
        upsert_report_module(report, public_module)
        self._emit(
            run_id,
            message_id,
            event_id,
            "report.module",
            {"module": public_module},
            conversation_id,
        )

    def _trace(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        step_id: str,
        name: str,
        output: dict[str, object],
        *,
        retrieval: dict[str, object] | None = None,
    ) -> None:
        step = self.run_store.append_step(
            run_id,
            step_id=step_id,
            name=name,
            status="completed",
            output_summary=json.dumps(output, ensure_ascii=False),
            retrieval=retrieval,
        )
        self._emit(
            run_id,
            message_id,
            f"trace:{step_id}",
            "trace.step",
            {"step": step},
            conversation_id,
        )

    def _record_retrieval(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        result: AskResult,
        *,
        elapsed_ms: int,
    ) -> None:
        wiki_telemetry = result.wiki_rag_telemetry
        citation_counts: dict[str, int] = {}
        citation_records: list[dict[str, str]] = []
        for citation in result.citations:
            prefix = citation.tag[:1]
            if prefix:
                citation_counts[prefix] = citation_counts.get(prefix, 0) + 1
            citation_records.append(
                {
                    "tag": citation.tag,
                    "source": citation.source,
                    "detail": citation.detail,
                }
            )
        self._trace(
            run_id,
            message_id,
            conversation_id,
            "retrieve",
            "ask_retrieve_compose",
            {
                "trade_date": result.trade_date,
                "matched_theme": result.matched_theme,
                "citation_count": len(result.citations),
                "elapsed_ms": elapsed_ms,
                "wiki_rag": (
                    {
                        "status": wiki_telemetry.status,
                        "hit_count": wiki_telemetry.hit_count,
                        "latency_ms": wiki_telemetry.latency_ms,
                    }
                    if wiki_telemetry is not None
                    else None
                ),
                "closed_loop_retrieval": (
                    result.closed_loop_retrieval.inspector_dict()
                    if result.closed_loop_retrieval is not None
                    else None
                ),
            },
            retrieval={
                "citations": citation_records,
                "citation_counts": citation_counts,
            },
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((time.monotonic() - started) * 1000))

    def _cancel(
        self,
        conversation_id: str,
        run_id: str,
        message_id: str,
        report: dict,
        selected: list[str],
        manual_selected: list[str],
        invoked: list[str],
        warnings: list[str],
        citations: list[dict[str, object]],
        text_chunks: list[str],
    ) -> TurnResult:
        if not self.claim_terminal():
            return self._terminal_state_result(run_id, selected, invoked)
        warning = "用户已取消本轮执行"
        if warning not in warnings:
            warnings.append(warning)
        self.run_store.add_degrade(run_id, warning)
        report["status"] = rs.STATUS_CANCELLED
        report["warnings"] = list(dict.fromkeys(warnings))
        content = "".join(text_chunks)
        finished = self.run_store.finish_run_with_artifacts(
            run_id,
            rs.STATUS_CANCELLED,
            (
                ArtifactPayload(
                    "report.json",
                    json.dumps(_redact_object(report), ensure_ascii=False, indent=2),
                    "structured_report",
                    "已取消的结构化对话报告",
                ),
            ),
        )
        if finished.status != rs.STATUS_CANCELLED:
            return self._terminal_state_result(run_id, selected, invoked)
        assistant = self.conversation_store.revise_message(
            conversation_id,
            message_id,
            content=content,
            status=rs.STATUS_CANCELLED,
            selected_skill_ids=manual_selected,
            invoked_skill_ids=invoked,
            citations=citations,
            degrades=warnings,
        )
        self._emit(
            run_id,
            message_id,
            "message:cancelled",
            "message.error",
            {"status": rs.STATUS_CANCELLED, "message": asdict(assistant)},
            conversation_id,
        )
        return TurnResult(
            status=rs.STATUS_CANCELLED,
            content=assistant.content,
            selected_skill_ids=tuple(selected),
            invoked_skill_ids=tuple(invoked),
        )

    def _fail(
        self,
        conversation_id: str,
        run_id: str,
        message_id: str,
        report: dict,
        selected: list[str],
        manual_selected: list[str],
        invoked: list[str],
        warnings: list[str],
        citations: list[dict[str, object]],
        text_chunks: list[str],
        error: Exception,
    ) -> TurnResult:
        if not self.claim_terminal():
            return self._terminal_state_result(run_id, selected, invoked)
        warning = f"本轮执行失败（{type(error).__name__}）"
        warnings.append(warning)
        report["status"] = rs.STATUS_FAILED
        report["warnings"] = list(dict.fromkeys(warnings))
        content = "".join(text_chunks)
        finished = self.run_store.finish_run(
            run_id,
            rs.STATUS_FAILED,
            error=warning,
        )
        if finished.status != rs.STATUS_FAILED:
            return self._terminal_state_result(run_id, selected, invoked)
        assistant = self.conversation_store.revise_message(
            conversation_id,
            message_id,
            content=content,
            status=rs.STATUS_FAILED,
            selected_skill_ids=manual_selected,
            invoked_skill_ids=invoked,
            citations=citations,
            degrades=warnings,
        )
        self._emit(
            run_id,
            message_id,
            "report:error",
            "report.error",
            {"report": report},
            conversation_id,
        )
        self._emit(
            run_id,
            message_id,
            "message:error",
            "message.error",
            {"status": rs.STATUS_FAILED, "message": asdict(assistant)},
            conversation_id,
        )
        return TurnResult(
            status=rs.STATUS_FAILED,
            content=assistant.content,
            selected_skill_ids=tuple(selected),
            invoked_skill_ids=tuple(invoked),
        )

    def _terminal_state_result(
        self,
        run_id: str,
        selected: Sequence[str],
        invoked: Sequence[str],
    ) -> TurnResult:
        run = self.run_store.load_run(run_id)
        return TurnResult(
            status=run.status,
            content="",
            selected_skill_ids=tuple(selected),
            invoked_skill_ids=tuple(invoked),
        )

    @staticmethod
    def _skill_evidence(outputs: Sequence[SkillOutput]) -> str:
        if not outputs:
            return ""
        lines: list[str] = []
        for output in outputs:
            as_of = f"（截至 {output.as_of}）" if output.as_of else ""
            lines.append(f"### {output.skill_id}{as_of}")
            for module in output.modules:
                title = module.get("title")
                if isinstance(title, str) and title.strip():
                    lines.append(f"- {title.strip()}")
                summary = module.get("summary")
                if isinstance(summary, str) and summary.strip():
                    lines.append(f"  - 摘要：{summary.strip()}")
                content = module.get("content")
                if isinstance(content, str) and content.strip():
                    lines.append(f"  - 正文：{content.strip()}")
                metrics = module.get("metrics")
                if isinstance(metrics, list):
                    metric_bits: list[str] = []
                    for metric in metrics:
                        if not isinstance(metric, dict):
                            continue
                        label = metric.get("label")
                        value = metric.get("value")
                        if isinstance(label, str) and value is not None:
                            metric_bits.append(f"{label}={value}")
                    if metric_bits:
                        lines.append("  - 指标：" + "；".join(metric_bits))
                items = module.get("items")
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        title = item.get("title")
                        summary = item.get("summary")
                        if not isinstance(summary, str) or not summary.strip():
                            continue
                        prefix = (
                            f"{title.strip()}："
                            if isinstance(title, str) and title.strip()
                            else ""
                        )
                        lines.append(f"  - {prefix}{summary.strip()}")
            if output.warnings:
                lines.append(
                    "- 数据质量提示：" + "；".join(output.warnings[:3])
                )
        return "\n".join(lines)

    @staticmethod
    def _skill_warning_module(skill_id: str, warning: str) -> dict[str, object]:
        return {
            "module_id": f"skill_{skill_id}_warning",
            "title": f"{skill_id} 降级",
            "kind": "warning",
            "status": "degraded",
            "summary": warning,
            "content": None,
            "metrics": [],
            "items": [],
            "table": None,
            "warnings": [warning],
            "provenance": {
                "source": skill_id,
                "as_of": None,
                "generated_by": "turn_orchestrator",
            },
        }
