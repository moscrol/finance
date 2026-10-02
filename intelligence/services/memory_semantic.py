"""用户记忆的语义召回——默认关闭，开了也能随时退回关键词召回。

背景：2026-08-05 用户拍定方向「用语义检索，不用关键词匹配」
（``docs/handoffs/2026-08-05b-user-memory-semantic-recall.md``）。08-15 基线
user_memory hit@5 = 7/15，漏召回多是「整句当检索词」「标签为空」「换了说法」
（``docs/verification/2026-08-15-recall-baseline.md``）。

开关（环境变量，进程级）：

- ``FINANCE_MEMORY_RECALL_MODE``：``keyword``（默认，召回逐字节不变）/ ``semantic``（只按
  向量相似度）/ ``hybrid``（先放关键词命中——标签命中精度高——空位用语义命中补齐）。
- ``FINANCE_MEMORY_EMBED_MODEL``：向量从哪来。
  - 本地 sentence-transformers 模型目录，或本机 HF 缓存里已有的模型名（如 ``BAAI/bge-m3``、
    ``BAAI/bge-small-zh-v1.5``）。一律 ``local_files_only``，**不联网、不调云端**（agent 工具
    红线）。需要本机装了 ``sentence-transformers``；没装就降级，不报错。
  - ``builtin:char-bigram``：零依赖的「字符二元组」向量。**它不是语义**，是更强的字面基线，
    给评测当对照组：语义模型要比它好出足够多，才值得背模型加载成本。
- ``FINANCE_MEMORY_SEMANTIC_MIN_SIM``：相似度下限，低于它不召回——宁缺毋滥，和关键词召回
  「0 分不召回」同一纪律。不设时按 embedder 自己的默认：语义模型 0.5，字符二元组 0.2（二元组
  的余弦天然偏低：相关 0.25–0.8、无关 0–0.08）。阈值随模型不同，须用评测扫一遍再定。

隐私与降级（handoff §2 硬约束）：

- 向量缓存只存「正文 sha256 → 向量」，**不存正文**；正文改了哈希就变，自然失效。放在仓库和
  记忆库**之外**的缓存目录：``FINANCE_MEMORY_VECTOR_CACHE_DIR``（默认 ``~/.cache/finance-memory-vectors``），
  按台账绝对路径的哈希分用户子目录。不放台账旁边，是因为真台账在自动同步的 agent-memory 记忆库里，
  放旁边就会被同步进 git（handoff：不要进 git）。设成 ``off`` 关缓存；目录写不进去也只是不缓存。
- 模型缺失、依赖没装、加载或编码失败：退回关键词召回，``telemetry`` 记原因，日志只写原因
  和条数、不写正文。不会因为语义那条路不通而静默返回空。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

MODE_ENV = "FINANCE_MEMORY_RECALL_MODE"
MODEL_ENV = "FINANCE_MEMORY_EMBED_MODEL"
MIN_SIM_ENV = "FINANCE_MEMORY_SEMANTIC_MIN_SIM"
MODES = ("keyword", "semantic", "hybrid")
DEFAULT_MODE = "keyword"
DEFAULT_MIN_SIMILARITY = 0.5
BUILTIN_BIGRAM = "builtin:char-bigram"
CACHE_DIR_ENV = "FINANCE_MEMORY_VECTOR_CACHE_DIR"
CACHE_OFF_VALUES = frozenset({"off", "0", "false", "none"})
CACHE_VERSION = 1


class Embedder(Protocol):
    name: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """返回与 texts 等长、L2 归一化的向量。"""


class EmbedderUnavailable(Exception):
    """语义那条路走不通（未配置 / 依赖缺失）：调用方退回关键词召回。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def recall_mode(env: Mapping[str, str] | None = None) -> str:
    raw = str((os.environ if env is None else env).get(MODE_ENV) or "").strip().lower()
    if not raw:
        return DEFAULT_MODE
    if raw not in MODES:
        logger.warning("%s=%r 不是 %s 之一，按 keyword 处理", MODE_ENV, raw, "/".join(MODES))
        return DEFAULT_MODE
    return raw


def min_similarity(env: Mapping[str, str] | None = None) -> float | None:
    """环境变量里的相似度下限；没设或不合法返回 None（交给 embedder 自己的默认）。"""

    raw = str((os.environ if env is None else env).get(MIN_SIM_ENV) or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        logger.warning("%s=%r 不是数，按 embedder 默认", MIN_SIM_ENV, raw)
        return None
    return value if math.isfinite(value) else None


def _normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0 or not math.isfinite(norm):
        return [0.0] * len(vector)
    return [x / norm for x in vector]


class CharBigramEmbedder:
    """零依赖的字符二元组向量：中文不分词也能按局部字面重合打分。**不是语义模型**。

    「盘前复盘推演怎么做」与「日度复盘推演」共享「复盘」「盘推」「推演」，整句当一个检索词时
    子串匹配打不到的，这里打得到；但「Chrome 没开远程调试」与「IPv6/UUID」这种只在意思上
    相关的，它照样打不到——那是语义模型要证明自己的地方。
    """

    name = BUILTIN_BIGRAM
    dim = 2048
    default_threshold = 0.2

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            chars = [c for c in str(text or "").lower() if not c.isspace()]
            grams = ["".join(chars[i:i + 2]) for i in range(len(chars) - 1)] or chars
            vector = [0.0] * self.dim
            for gram in grams:
                digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
                vector[int.from_bytes(digest, "big") % self.dim] += 1.0
            vectors.append(_normalize(vector))
        return vectors


class SentenceTransformerEmbedder:
    """本地 sentence-transformers 模型。首次 embed 时加载，进程内只加载一次；全程离线。"""

    def __init__(self, model: str) -> None:
        self.model = model
        self.name = f"sentence-transformers:{model}"
        self.default_threshold = DEFAULT_MIN_SIMILARITY
        self._encoder: Any = None

    def _load(self) -> Any:
        if self._encoder is None:
            # 双保险不联网：HF 两个离线开关 + local_files_only（老版本不认这个参数就只靠开关）。
            for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
                os.environ.setdefault(key, "1")
            from sentence_transformers import SentenceTransformer

            try:
                self._encoder = SentenceTransformer(self.model, local_files_only=True)
            except TypeError:
                self._encoder = SentenceTransformer(self.model)
        return self._encoder

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        encoder = self._load()
        rows = encoder.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return [_normalize([float(x) for x in row]) for row in rows]


_EMBEDDERS: dict[str, Embedder] = {}


def resolve_embedder(env: Mapping[str, str] | None = None) -> Embedder:
    """按 ``FINANCE_MEMORY_EMBED_MODEL`` 给出本地 embedder；走不通抛 EmbedderUnavailable。"""

    model = str((os.environ if env is None else env).get(MODEL_ENV) or "").strip()
    if not model:
        raise EmbedderUnavailable("embed_model_unset")
    cached = _EMBEDDERS.get(model)
    if cached is not None:
        return cached
    if model == BUILTIN_BIGRAM:
        embedder: Embedder = CharBigramEmbedder()
    else:
        import importlib.util

        if importlib.util.find_spec("sentence_transformers") is None:
            raise EmbedderUnavailable("sentence_transformers_missing")
        embedder = SentenceTransformerEmbedder(model)
    _EMBEDDERS[model] = embedder
    return embedder


def record_text(record: Mapping[str, Any], text_keys: Sequence[str], tag_keys: Sequence[str]) -> str:
    """一条台账记录参与向量化的文本：标签在前，正文在后。"""

    tags = [str(t).strip() for key in tag_keys for t in (record.get(key) or []) if str(t).strip()]
    texts = [str(record.get(key) or "").strip() for key in text_keys]
    return "；".join([*tags, *(t for t in texts if t)])


def query_text(query: str, theme: str | None = None, entity: str | None = None) -> str:
    return "；".join(part.strip() for part in (query, theme or "", entity or "") if part and part.strip())


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_root(env: Mapping[str, str] | None = None) -> Path | None:
    """向量缓存根目录；``off`` 等值返回 None（不缓存）。"""

    raw = str((os.environ if env is None else env).get(CACHE_DIR_ENV) or "").strip()
    if raw.lower() in CACHE_OFF_VALUES:
        return None
    if not raw:
        return Path.home() / ".cache" / "finance-memory-vectors"
    root = Path(raw).expanduser()
    # 相对路径会落进当前工作目录（多半是仓库根），按配错处理：不缓存。
    return root if root.is_absolute() else None


def cache_path_for(ledger_path: Path, embedder_name: str, root: Path | None = None) -> Path | None:
    """``<缓存根>/<台账绝对路径哈希>/<台账名>.<模型哈希>.json``；缓存关了返回 None。"""

    base = cache_root() if root is None else root
    if base is None:
        return None
    ledger_digest = hashlib.sha256(str(ledger_path.expanduser().resolve()).encode("utf-8")).hexdigest()[:16]
    model_digest = hashlib.sha256(embedder_name.encode("utf-8")).hexdigest()[:12]
    return base / ledger_digest / f"{ledger_path.stem}.{model_digest}.json"


class VectorCache:
    """「正文哈希 → 向量」的 JSON 缓存；不存正文。读坏了从空开始，写不进去就不缓存。"""

    def __init__(self, path: Path | None, embedder_name: str) -> None:
        self.path = path
        self.embedder_name = embedder_name
        self.status = "disabled" if path is None else "cold"
        self._vectors: dict[str, list[float]] = {}
        self._dirty = False
        if path is not None and path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("version") == CACHE_VERSION and payload.get("embedder") == embedder_name:
                    self._vectors = {
                        str(k): [float(x) for x in v]
                        for k, v in (payload.get("vectors") or {}).items()
                    }
                    self.status = "warm"
                else:
                    self.status = "reset_mismatch"
            except (OSError, ValueError, TypeError, AttributeError):
                self.status = "reset_unreadable"

    def get(self, digest: str) -> list[float] | None:
        return self._vectors.get(digest)

    def put(self, digest: str, vector: list[float]) -> None:
        self._vectors[digest] = vector
        self._dirty = True

    def retain(self, digests: set[str]) -> None:
        """只留当前台账里还在的记录，删掉的条目不在缓存里滞留。"""

        stale = set(self._vectors) - digests
        for key in stale:
            del self._vectors[key]
        self._dirty = self._dirty or bool(stale)

    def save(self) -> None:
        if self.path is None or not self._dirty:
            return
        payload = {
            "version": CACHE_VERSION,
            "embedder": self.embedder_name,
            "vectors": {k: [round(x, 6) for x in v] for k, v in sorted(self._vectors.items())},
        }
        tmp = self.path.with_name(self.path.name + f".tmp-{os.getpid()}")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.path)
            self._dirty = False
        except OSError:
            self.status = "unwritable"
            try:
                tmp.unlink()
            except OSError:
                pass


def rank_by_similarity(
    records: Sequence[Mapping[str, Any]],
    query: str,
    *,
    text_keys: Sequence[str],
    tag_keys: Sequence[str],
    embedder: Embedder,
    cache: VectorCache,
    threshold: float,
) -> list[tuple[float, Mapping[str, Any]]]:
    """按余弦相似度降序（同分按 ts 新者在前）；低于阈值的不要。"""

    texts = [record_text(rec, text_keys, tag_keys) for rec in records]
    if not any(texts):
        # 空台账（生产里 judgments.jsonl 就不存在）：不算问句向量，也就不为它加载模型。
        return []
    digests = [_digest(text) for text in texts]
    missing = sorted({d for d, t in zip(digests, texts) if t and cache.get(d) is None})
    if missing:
        by_digest = {d: t for d, t in zip(digests, texts)}
        for digest, vector in zip(missing, embedder.embed([by_digest[d] for d in missing])):
            cache.put(digest, vector)
    cache.retain(set(digests))
    cache.save()
    (query_vector,) = embedder.embed([query])
    ranked: list[tuple[float, Mapping[str, Any]]] = []
    for rec, text, digest in zip(records, texts, digests):
        vector = cache.get(digest) if text else None
        if vector is None:
            continue
        score = sum(a * b for a, b in zip(query_vector, vector))
        if score >= threshold:
            ranked.append((score, rec))
    ranked.sort(key=lambda item: (item[0], str(item[1].get("ts") or "")), reverse=True)
    return ranked


def select(
    records: list[dict[str, Any]],
    query: str,
    theme: str | None,
    entity: str | None,
    *,
    text_keys: Sequence[str],
    tag_keys: Sequence[str],
    limit: int,
    mode: str,
    keyword: list[dict[str, Any]],
    ledger_path: Path | None = None,
    telemetry: dict[str, Any] | None = None,
    embedder_factory: Callable[[], Embedder] | None = None,
    threshold: float | None = None,
) -> list[dict[str, Any]]:
    """semantic / hybrid 召回；任何一步走不通都退回 ``keyword``（调用方已算好的关键词结果）。"""

    sink = telemetry if telemetry is not None else {}
    sink.update(mode=mode, effective=mode, degraded=None)
    if mode == "keyword":
        sink["effective"] = "keyword"
        return keyword
    started = time.perf_counter()
    try:
        # 调用时才取工厂：默认值写在签名里会在定义时绑死，测试和评测就换不掉。
        embedder = (embedder_factory or resolve_embedder)()
        if threshold is None:
            threshold = min_similarity()
        if threshold is None:
            threshold = float(getattr(embedder, "default_threshold", DEFAULT_MIN_SIMILARITY))
        cache = VectorCache(
            cache_path_for(ledger_path, embedder.name) if ledger_path is not None else None,
            embedder.name,
        )
        ranked = rank_by_similarity(
            records,
            query_text(query, theme, entity),
            text_keys=text_keys,
            tag_keys=tag_keys,
            embedder=embedder,
            cache=cache,
            threshold=threshold,
        )
    except EmbedderUnavailable as exc:
        return _degrade(sink, exc.reason, keyword, len(records))
    except Exception as exc:  # noqa: BLE001 — 语义路不通不能拖垮召回
        return _degrade(sink, f"embed_failed:{type(exc).__name__}", keyword, len(records))
    semantic = [dict_record for _, dict_record in ranked]
    if mode == "semantic":
        chosen = semantic[: max(0, limit)]
    else:
        taken = {id(rec) for rec in keyword}
        chosen = (keyword + [rec for rec in semantic if id(rec) not in taken])[: max(0, limit)]
    sink.update(
        embedder=embedder.name,
        threshold=threshold,
        cache=cache.status,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        semantic_hits=len(semantic),
    )
    return chosen  # type: ignore[return-value]


_WARNED_REASONS: set[str] = set()


def _degrade(sink: dict[str, Any], reason: str, keyword: list[dict[str, Any]], pool: int) -> list[dict[str, Any]]:
    sink.update(effective="keyword", degraded=reason)
    # 只记原因和条数：台账正文是用户私有判断，不进日志。同一原因每进程只告警一次，
    # 之后降为 debug——每一问都告警会把日志淹掉；逐次信号在 telemetry 里。
    level = logging.DEBUG if reason in _WARNED_REASONS else logging.WARNING
    _WARNED_REASONS.add(reason)
    logger.log(level, "user memory semantic recall unavailable (%s); keyword fallback over %d records", reason, pool)
    return keyword
