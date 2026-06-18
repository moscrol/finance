"""可证伪点台账 + 判断打分 + 二阶推演校准 (checkpoints / verdicts / calibration)。

B 方案（``judgments.jsonl``）让 foresight 站在你旧判断上往前推；C 方案再往前一步：
把判断里**可证伪的那一刀**单独登记成带「到期日 + 类别 + 机检规格」的检查点，到期拉
盘面/知识库数据核对当初判断的对错，给判断打分，再**反过来校准「你哪类二阶推演靠谱」**，
把这份胜率回注 foresight 发问——让它信任你历史靠谱的推演类、主动质疑你常落空的那类。

两个 append-only 台账（每行一条 JSON，均 gitignore、按用户隔离）：

- ``checkpoints.jsonl``  登记的可证伪点：
    - ``id``                 稳定 id（注册日 + 短哈希），verdict 凭它回链；
    - ``claim``              可证伪陈述（必填）；
    - ``due``                到期回检日 YYYY-MM-DD（必填）；
    - ``category``           二阶推演类型（校准聚合维度，如「估值切换」「产能时点」）；
    - ``themes`` / ``stocks``关联题材 / 个股；
    - ``metric``             可选机检规格（无则人工判定）：
        - ``stock_return``   个股区间涨幅，对比 ``op``/``target``（``window_days`` 窗口）→ 盘面 resolver；
        - ``kb_evidence``    注册后是否出现新证据（``target`` 主题/公司，``target`` 条数阈值）→ 知识库 resolver；
        - ``manual``         人工判定；
    - ``source_judgment_ts`` 反链 B 的核心判断（可选）；
    - ``session_id``         来源会话（可选）。
- ``verdicts.jsonl``    回检打分：``id`` / ``verdict``(hit|miss|partial|unverifiable) /
    ``score``(1|0|0.5|None) / ``observed`` / ``data_source`` / ``reason`` / ``auto`` / ``checked_at``。

``unverifiable``（如本机无 DuckDB、数据未到）是**非终态**：不计入胜率、下次仍进到期队列，
等数据齐了再判。终态（hit/miss/partial）才进 ``calibrate`` 聚合。

本模块只用标准库，不依赖 duckdb / 联网，可离线运行、可独立单测；真正拉数的 resolver
在 ``checkpoint_resolvers`` 里且**优雅降级**（缺数→unverifiable，绝不编造）。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timezone
from pathlib import Path
from typing import Any

# verdict → 分数。unverifiable 记 None（不计入胜率）。
VERDICTS = ("hit", "partial", "miss", "unverifiable")
TERMINAL_VERDICTS = ("hit", "partial", "miss")
SCORE_MAP: dict[str, float | None] = {"hit": 1.0, "partial": 0.5, "miss": 0.0, "unverifiable": None}

METRIC_TYPES = ("stock_return", "kb_evidence", "manual")
NUMERIC_METRIC_TYPES = ("stock_return", "kb_evidence")
VALID_OPS = (">=", ">", "<=", "<", "==")

DEFAULT_WINDOW_DAYS = 60
DEFAULT_CALIBRATION_MIN_N = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> str:
    return date_cls.today().isoformat()


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _clean_terms(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        key = _norm(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _parse_date(value: Any) -> str:
    """把 ``value`` 规整成 ``YYYY-MM-DD``；非法日期抛 ``ValueError``。"""
    s = str(value or "").strip()
    if not s:
        raise ValueError("到期日 due 不能为空")
    try:
        return date_cls.fromisoformat(s[:10]).isoformat()
    except ValueError as exc:
        raise ValueError(f"非法到期日 due={value!r}（需 YYYY-MM-DD）") from exc


def normalize_metric(metric: dict[str, Any] | None) -> dict[str, Any] | None:
    """校验并规整机检规格；``None`` / 空 → ``None``（走人工判定）。"""
    if not metric:
        return None
    if not isinstance(metric, dict):
        raise ValueError("metric 必须是对象")
    mtype = str(metric.get("type") or "").strip()
    if mtype not in METRIC_TYPES:
        raise ValueError(f"非法 metric.type={mtype!r}（允许 {METRIC_TYPES}）")
    if mtype == "manual":
        return {"type": "manual"}
    out: dict[str, Any] = {"type": mtype}
    op = str(metric.get("op") or ">=").strip()
    if op not in VALID_OPS:
        raise ValueError(f"非法 metric.op={op!r}（允许 {VALID_OPS}）")
    out["op"] = op
    target = metric.get("target")
    if target is None:
        raise ValueError(f"metric.type={mtype} 需要数值阈值 target")
    try:
        out["target"] = float(target)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"非法 metric.target={target!r}（需数值）") from exc
    if mtype == "stock_return":
        out["window_days"] = int(metric.get("window_days") or DEFAULT_WINDOW_DAYS)
    if metric.get("target_name"):
        out["target_name"] = str(metric["target_name"]).strip()
    return out


def _make_id(claim: str, ts: str) -> str:
    digest = hashlib.sha1(f"{ts}|{claim}".encode("utf-8")).hexdigest()[:6]
    return f"ck-{ts[:10]}-{digest}"


def register_checkpoint(
    path: str | Path,
    *,
    claim: str,
    due: str,
    category: str | None = None,
    themes: list[str] | None = None,
    stocks: list[str] | None = None,
    metric: dict[str, Any] | None = None,
    source_judgment_ts: str | None = None,
    session_id: str | None = None,
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """登记一个可证伪点到 ``checkpoints.jsonl``，返回 ``(path, record)``。

    ``claim`` 为空或 ``due`` 非法日期时抛 ``ValueError``——可证伪点至少要有陈述与到期日。
    """
    text = str(claim or "").strip()
    if not text:
        raise ValueError("claim 不能为空：可证伪点至少要有陈述")
    due_norm = _parse_date(due)
    metric_norm = normalize_metric(metric)
    ts_norm = ts or _now().isoformat(timespec="seconds")
    record: dict[str, Any] = {
        "id": _make_id(text, ts_norm),
        "ts": ts_norm,
        "claim": text,
        "due": due_norm,
        "category": str(category).strip() if category and str(category).strip() else None,
        "themes": _clean_terms(themes),
        "stocks": _clean_terms(stocks),
    }
    if metric_norm:
        record["metric"] = metric_norm
    if source_judgment_ts and str(source_judgment_ts).strip():
        record["source_judgment_ts"] = str(source_judgment_ts).strip()
    if session_id and str(session_id).strip():
        record["session_id"] = str(session_id).strip()
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def _load_jsonl(path: str | Path, label: str) -> tuple[list[dict[str, Any]], str | None]:
    p = Path(path).expanduser()
    if not p.exists():
        return [], None
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        return [], f"{label}读取失败：{exc}"
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out, None


def load_checkpoints(path: str | Path) -> tuple[list[dict[str, Any]], str | None]:
    """读取全部可证伪点（保留出现顺序）。文件不存在时返回空列表。"""
    records, warn = _load_jsonl(path, "可证伪点台账")
    return [r for r in records if str(r.get("claim") or "").strip() and r.get("id")], warn


def load_verdicts(path: str | Path) -> tuple[list[dict[str, Any]], str | None]:
    """读取全部回检打分（保留出现顺序）。文件不存在时返回空列表。"""
    records, warn = _load_jsonl(path, "回检打分台账")
    return [r for r in records if r.get("id") and r.get("verdict") in VERDICTS], warn


def _latest_terminal_verdicts(verdicts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """每个 id 取最后一条**终态**打分（后写覆盖先写）。"""
    out: dict[str, dict[str, Any]] = {}
    for v in verdicts:
        if v.get("verdict") in TERMINAL_VERDICTS:
            out[str(v["id"])] = v
    return out


def due_checkpoints(
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    today: str | None = None,
) -> list[dict[str, Any]]:
    """到期且尚未拿到终态打分的检查点（``due <= today``）。

    ISO 日期可直接字典序比较。``unverifiable`` 非终态，仍会再次进队列等数据齐了重判。
    """
    today = today or _today()
    scored = _latest_terminal_verdicts(verdicts)
    out: list[dict[str, Any]] = []
    for c in checkpoints:
        due = str(c.get("due") or "")
        if not due or due > today:
            continue
        if str(c.get("id")) in scored:
            continue
        out.append(c)
    return out


def record_verdict(
    path: str | Path,
    *,
    id: str,
    verdict: str,
    score: float | None = None,
    observed: dict[str, Any] | None = None,
    data_source: str = "manual",
    reason: str = "",
    auto: bool = False,
    checked_at: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """把一条回检打分 append 到 ``verdicts.jsonl``，返回 ``(path, record)``。"""
    cid = str(id or "").strip()
    if not cid:
        raise ValueError("verdict 必须带 checkpoint id")
    if verdict not in VERDICTS:
        raise ValueError(f"非法 verdict={verdict!r}（允许 {VERDICTS}）")
    if score is None:
        score = SCORE_MAP[verdict]
    record: dict[str, Any] = {
        "id": cid,
        "checked_at": checked_at or _now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "score": score,
        "data_source": data_source,
        "auto": bool(auto),
    }
    if observed:
        record["observed"] = observed
    if reason and str(reason).strip():
        record["reason"] = str(reason).strip()
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


# --------------------------------------------------------------------------- #
# 校准：把已回检的判断按「二阶推演类别」聚合成胜率，定位你哪类推演靠谱/偏差。
# --------------------------------------------------------------------------- #
@dataclass
class CategoryStat:
    category: str
    n: int = 0
    hits: int = 0
    partial: int = 0
    miss: int = 0
    score_sum: float = 0.0
    samples: list[str] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        return (self.score_sum / self.n) if self.n else 0.0

    @property
    def reliability(self) -> str:
        if self.n == 0:
            return "无样本"
        r = self.hit_rate
        if r >= 0.7:
            return "靠谱"
        if r >= 0.4:
            return "参半"
        return "偏差大"


@dataclass
class Calibration:
    by_category: list[CategoryStat] = field(default_factory=list)
    scored: int = 0
    pending: int = 0
    unverifiable: int = 0

    @property
    def overall_rate(self) -> float:
        total = sum(c.score_sum for c in self.by_category)
        n = sum(c.n for c in self.by_category)
        return (total / n) if n else 0.0


def calibrate(
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    today: str | None = None,
) -> Calibration:
    """按 ``category`` 聚合终态打分→胜率；``by_category`` 按命中率升序（最该质疑的在前）。"""
    by_id = {str(c.get("id")): c for c in checkpoints if c.get("id")}
    terminal = _latest_terminal_verdicts(verdicts)
    stats: dict[str, CategoryStat] = {}
    for cid, v in terminal.items():
        ck = by_id.get(cid)
        if ck is None:
            continue
        cat = str(ck.get("category") or "未分类").strip() or "未分类"
        st = stats.setdefault(cat, CategoryStat(category=cat))
        verdict = str(v.get("verdict"))
        score = v.get("score")
        score = SCORE_MAP.get(verdict, 0.0) if score is None else float(score)
        st.n += 1
        st.score_sum += score
        if verdict == "hit":
            st.hits += 1
        elif verdict == "partial":
            st.partial += 1
        else:
            st.miss += 1
        if len(st.samples) < 3:
            st.samples.append(str(ck.get("claim") or "")[:60])
    pending = len(due_checkpoints(checkpoints, verdicts, today=today))
    unverifiable = sum(1 for v in verdicts if v.get("verdict") == "unverifiable")
    return Calibration(
        by_category=sorted(stats.values(), key=lambda s: (s.hit_rate, -s.n)),
        scored=sum(s.n for s in stats.values()),
        pending=pending,
        unverifiable=unverifiable,
    )


def render_calibration_for_prompt(cal: Calibration, min_n: int = DEFAULT_CALIBRATION_MIN_N) -> str:
    """渲染成注入 foresight 系统提示词的「胜率加权」要点（只列样本足够的类别）。"""
    lines: list[str] = []
    for st in cal.by_category:
        if st.n < min_n:
            continue
        pct = round(st.hit_rate * 100)
        if st.reliability == "靠谱":
            tail = "→ 这类判断历史靠谱，可继续信任、承接它往前推"
        elif st.reliability == "偏差大":
            tail = "→ 这类判断历史常落空，发问时主动质疑、要我拿反证"
        else:
            tail = "→ 这类判断半对半错，发问时让我同时给正反两面"
        lines.append(
            f"- {st.category}：{st.n} 中 {st.hits} 命中"
            f"（命中率 {pct}%，{st.reliability}）{tail}"
        )
    return "\n".join(lines)


def render_report(cal: Calibration) -> str:
    """CLI 人读的校准报告。"""
    lines = ["# 二阶推演校准（哪类判断靠谱）"]
    lines.append(
        f"> 已回检 {cal.scored} 条 · 待回检 {cal.pending} 条 · "
        f"暂无法判定 {cal.unverifiable} 条 · 总命中率 {round(cal.overall_rate * 100)}%"
    )
    if not cal.by_category:
        lines.append("")
        lines.append("（还没有已回检的判断。先 `checkpoint register` 登记可证伪点，到期 `checkpoint recheck`。）")
        return "\n".join(lines) + "\n"
    for st in cal.by_category:
        lines.append("")
        lines.append(
            f"## {st.category} · 命中率 {round(st.hit_rate * 100)}%（{st.reliability}）"
        )
        lines.append(f"- 样本 {st.n}：命中 {st.hits} / 半对 {st.partial} / 落空 {st.miss}")
        for s in st.samples:
            lines.append(f"- 例：{s}")
    return "\n".join(lines) + "\n"


def load_calibration(
    checkpoints_path: str | Path,
    verdicts_path: str | Path,
    *,
    today: str | None = None,
) -> tuple[Calibration, list[str]]:
    """从两个台账文件直接算出校准（给 foresight 注入与 CLI 复用）。"""
    warnings: list[str] = []
    cks, cwarn = load_checkpoints(checkpoints_path)
    if cwarn:
        warnings.append(cwarn)
    vds, vwarn = load_verdicts(verdicts_path)
    if vwarn:
        warnings.append(vwarn)
    return calibrate(cks, vds, today=today), warnings
