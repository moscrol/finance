"""单次研究全口径成本报表：写手 + 判官 token 与元/次（INDEX #23）。

Usage::

    python -m intelligence.eval.research_cost --runs-root PATH --since 7d \\
        --out-dir intelligence/eval/measurements

形状照 ``intelligence/eval/tool_hunger.py``：``--since`` / ``discover_run_dirs`` /
``write_*_report`` / 输出 ``measurements/research-cost-YYYY-MM-DD.{json,md}``。

口径（与 BP §7.3 写手侧实测同一套，判官侧是本单补上的那一列）：

- run 集合：``run.json.status == completed``（缺 run.json 时退到
  ``continuous-episode.json`` 的 ``outcome.status``）且落在 ``--since`` 之后。
- 写手侧：``continuous-episode.json`` → ``outcome.usage.{input_tokens,output_tokens}``；
  两者皆无或皆为 0 的 run 记 ``writer_unrecorded_runs``，不进任何分位数（BP 那次
  同样剔除了 17 个 usage=0 的 run）。
- 判官侧：``metrics.judge_usage.{calls,input_tokens,output_tokens,usage_source}``。
  **没有这个键的 run 是改动上线前的旧格式**，记 ``judge_unrecorded_runs``，只进写手列、
  不进判官列与合计列——旧 run 没有原始 stdout，不回填、不估。``calls == 0`` 是判官
  真的没被调用（快路径 / 判官不可用），判官 token 按 0 计入合计。
- 估算标记：``usage_source == "estimated"`` 的 run 计 ``judge_estimated_runs``，
  ``estimated_share`` = 估算 run / 判官有记账且 calls ≥ 1 的 run；> 0 时成本列标
  「含估算」——估算值不得与真实值混成一个数而不注明。
- 元/次：按 ``intelligence/eval/pricing/llm-prices.json`` 折算，写手模型取
  ``report.json.llm.model``（缺则 ``--writer-model``）。判官模型不落进产物，只能按
  ``usage_source`` 反推走的哪条路（见 ``judge_price_model``）：``cli``/``estimated``
  用 ``--judge-model``（默认 ``grok-4.6-build``，即生产 grok CLI 的实付档），``api``
  用 ``--judge-api-model``，``mixed`` 与无来源不定价。价目表无价（null 或无匹配）的
  模型不猜：对应成本列标「价目表未录」，并列出 ``unpriced_models``。
- 分位数：p90 用线性插值（numpy 默认口径）；中位同。
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from intelligence.eval.tool_hunger import discover_run_dirs, parse_since

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRICING_PATH = Path(__file__).resolve().parent / "pricing" / "llm-prices.json"
# 生产判官走 grok CLI，xAI 的计费表把它记在 `grok-4.6-build` 这个 SKU 上（探针 modelUsage 的键），
# 实付约 API list 价的 0.17；按 list 计价会把判官侧读数放大 5.9 倍。API 备胎判官请用 --judge-model grok-4.6。
DEFAULT_JUDGE_MODEL = "grok-4.6-build"
DEFAULT_WRITER_MODEL = "glm-5.2"
EPISODE_FILENAME = "continuous-episode.json"

_RUN_DIR_STAMP = re.compile(r"^run_(\d{8})_(\d{6})")


# ── 价目表 ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PriceRow:
    model_pattern: str
    input_cny_per_m: float | None
    output_cny_per_m: float | None
    cache_hit_cny_per_m: float | None
    source_url: str | None
    checked_at: str | None
    note: str = ""

    @property
    def priced(self) -> bool:
        return self.input_cny_per_m is not None and self.output_cny_per_m is not None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def load_pricing(path: Path | str = DEFAULT_PRICING_PATH) -> list[PriceRow]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("prices") if isinstance(payload, dict) else payload
    out: list[PriceRow] = []
    for item in rows or []:
        if not isinstance(item, dict) or not item.get("model_pattern"):
            continue
        out.append(
            PriceRow(
                model_pattern=str(item["model_pattern"]),
                input_cny_per_m=_optional_float(item.get("input_cny_per_m")),
                output_cny_per_m=_optional_float(item.get("output_cny_per_m")),
                cache_hit_cny_per_m=_optional_float(item.get("cache_hit_cny_per_m")),
                source_url=(str(item["source_url"]) if item.get("source_url") else None),
                checked_at=(str(item["checked_at"]) if item.get("checked_at") else None),
                note=str(item.get("note") or ""),
            )
        )
    return out


def match_price(model: str | None, rows: list[PriceRow]) -> PriceRow | None:
    """自上而下首个 fnmatch 命中（忽略大小写）；``model`` 为空返回 None。"""

    if not model:
        return None
    lowered = model.strip().lower()
    for row in rows:
        if fnmatch.fnmatchcase(lowered, row.model_pattern.lower()):
            return row
    return None


def cost_cny(
    input_tokens: int | None,
    output_tokens: int | None,
    row: PriceRow | None,
) -> float | None:
    """tokens × 单价 / 1e6；价目表无价或 token 未知返回 None（不算 0）。"""

    if row is None or not row.priced:
        return None
    if input_tokens is None and output_tokens is None:
        return None
    assert row.input_cny_per_m is not None and row.output_cny_per_m is not None
    return (
        (input_tokens or 0) * row.input_cny_per_m
        + (output_tokens or 0) * row.output_cny_per_m
    ) / 1_000_000


def judge_price_model(
    usage_source: str | None,
    *,
    judge_model: str | None,
    judge_api_model: str | None,
) -> str | None:
    """按 `judge_usage.usage_source` 决定这个 run 的判官该用哪一行价目。

    判官侧的模型名不落进产物，报表只能按 `usage_source` 反推走的是哪条路：

    - `cli` / `estimated`：grok CLI 主判官。`estimated` 估的是 token 数不是 SKU，
      仍按 CLI 那档计价（估算标记另有 `estimated_share` 承担）。
    - `api`：备胎判官，模型由 `LLM_JUDGE_FALLBACK_MODEL` 定（默认 `gpt-4o-mini`，
      与 grok 无关）——**不给 `--judge-api-model` 就不定价**，宁可少一个数也不按
      CLI 档硬算（那会把备胎的成本按 grok 折扣价记，且报表看不出异常）。
    - `mixed`：主备各服务了一部分，`judge_usage` 分不出各自 token，不定价。
    - None：一条带用量的记录都没有，无从定价。
    """

    if usage_source in ("cli", "estimated"):
        return judge_model
    if usage_source == "api":
        return judge_api_model
    return None


# ── 单个 run ───────────────────────────────────────────────────────────


@dataclass
class RunCost:
    run_id: str
    created_at: str | None
    writer_model: str | None
    writer_input: int | None
    writer_output: int | None
    judge_recorded: bool
    judge_calls: int = 0
    judge_input: int | None = None
    judge_output: int | None = None
    judge_source: str | None = None
    judge_model: str | None = None
    writer_cost: float | None = None
    judge_cost: float | None = None

    @property
    def writer_measured(self) -> bool:
        return bool(self.writer_input) or bool(self.writer_output)

    @property
    def judge_estimated(self) -> bool:
        return self.judge_source == "estimated"

    @property
    def total_input(self) -> int | None:
        if not self.judge_recorded:
            return None
        return (self.writer_input or 0) + (self.judge_input or 0)

    @property
    def total_output(self) -> int | None:
        if not self.judge_recorded:
            return None
        return (self.writer_output or 0) + (self.judge_output or 0)

    @property
    def total_cost(self) -> float | None:
        if not self.judge_recorded or self.writer_cost is None:
            return None
        if self.judge_calls == 0:
            return self.writer_cost
        if self.judge_cost is None:
            return None
        return self.writer_cost + self.judge_cost

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "writer_model": self.writer_model,
            "writer_input_tokens": self.writer_input,
            "writer_output_tokens": self.writer_output,
            "judge_recorded": self.judge_recorded,
            "judge_calls": self.judge_calls,
            "judge_input_tokens": self.judge_input,
            "judge_output_tokens": self.judge_output,
            "judge_usage_source": self.judge_source,
            "judge_model": self.judge_model,
            "writer_cost_cny": _round(self.writer_cost),
            "judge_cost_cny": _round(self.judge_cost),
            "total_cost_cny": _round(self.total_cost),
        }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _token(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _run_created_at(run_dir: Path, run_meta: dict[str, Any] | None) -> datetime | None:
    raw = (run_meta or {}).get("created_at")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = datetime.fromisoformat(raw.strip())
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
            return parsed
    match = _RUN_DIR_STAMP.match(run_dir.name)
    if match:
        try:
            return datetime.strptime(
                f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S"
            ).replace(tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError:
            return None
    return None


def _run_status(run_meta: dict[str, Any] | None, episode: dict[str, Any] | None) -> str:
    status = (run_meta or {}).get("status")
    if isinstance(status, str) and status:
        return status
    outcome = (episode or {}).get("outcome")
    if isinstance(outcome, dict) and isinstance(outcome.get("status"), str):
        return str(outcome["status"])
    return ""


def _writer_model(run_dir: Path, default: str | None) -> str | None:
    report = _read_json(run_dir / "report.json")
    llm = (report or {}).get("llm")
    if isinstance(llm, dict):
        model = llm.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    return default


def run_cost_from_dir(
    run_dir: Path,
    *,
    pricing: list[PriceRow],
    judge_model: str | None,
    writer_model_default: str | None,
    writer_price_model: str | None = None,
    judge_api_model: str | None = None,
) -> tuple[RunCost | None, str]:
    """返回 (RunCost, 分类)。分类：measured / not_completed / no_episode / writer_unrecorded。

    ``writer_price_model`` 给定时，写手 token 一律按该模型的价目折算（BP §7.3 那种
    「按 GLM-5.2 档」的 what-if），run 实际用的模型仍原样记在 ``writer_model``。
    """

    run_meta = _read_json(run_dir / "run.json")
    episode = _read_json(run_dir / EPISODE_FILENAME)
    if _run_status(run_meta, episode) != "completed":
        return None, "not_completed"
    if episode is None:
        return None, "no_episode"
    created = _run_created_at(run_dir, run_meta)
    outcome = episode.get("outcome")
    usage = outcome.get("usage") if isinstance(outcome, dict) else None
    writer_input = _token(usage.get("input_tokens")) if isinstance(usage, dict) else None
    writer_output = _token(usage.get("output_tokens")) if isinstance(usage, dict) else None
    metrics = episode.get("metrics")
    judge_usage = metrics.get("judge_usage") if isinstance(metrics, dict) else None
    judge_recorded = isinstance(judge_usage, dict)
    run = RunCost(
        run_id=str((run_meta or {}).get("run_id") or run_dir.name),
        created_at=created.isoformat(timespec="seconds") if created else None,
        writer_model=_writer_model(run_dir, writer_model_default),
        writer_input=writer_input,
        writer_output=writer_output,
        judge_recorded=judge_recorded,
    )
    if judge_recorded:
        assert isinstance(judge_usage, dict)
        calls = _token(judge_usage.get("calls"))
        run.judge_calls = calls or 0
        run.judge_input = _token(judge_usage.get("input_tokens"))
        run.judge_output = _token(judge_usage.get("output_tokens"))
        source = judge_usage.get("usage_source")
        run.judge_source = source if isinstance(source, str) and source else None
        run.judge_model = (
            judge_price_model(
                run.judge_source,
                judge_model=judge_model,
                judge_api_model=judge_api_model,
            )
            if run.judge_calls
            else None
        )
    if not run.writer_measured:
        return run, "writer_unrecorded"
    run.writer_cost = cost_cny(
        run.writer_input,
        run.writer_output,
        match_price(writer_price_model or run.writer_model, pricing),
    )
    if run.judge_recorded and run.judge_calls:
        run.judge_cost = cost_cny(
            run.judge_input, run.judge_output, match_price(run.judge_model, pricing)
        )
    return run, "measured"


# ── 聚合 ───────────────────────────────────────────────────────────────


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def percentile(values: list[float], q: float) -> float | None:
    """线性插值分位（numpy 默认 ``linear``）；空列表 None。"""

    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def distribution(
    values: list[float | int | None], *, digits: int = 2
) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"n": 0, "median": None, "mean": None, "p90": None}
    return {
        "n": len(clean),
        "median": _round(statistics.median(clean), digits),
        "mean": _round(statistics.fmean(clean), digits),
        "p90": _round(percentile(clean, 0.9), digits),
    }


def _git_revision() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    revision = completed.stdout.strip()
    return revision or None


def aggregate_research_cost(
    runs_root: Path,
    *,
    since: datetime | str | None = None,
    pricing_path: Path | str = DEFAULT_PRICING_PATH,
    judge_model: str | None = DEFAULT_JUDGE_MODEL,
    writer_model_default: str | None = DEFAULT_WRITER_MODEL,
    writer_price_model: str | None = None,
    judge_api_model: str | None = None,
) -> dict[str, Any]:
    cutoff = parse_since(since) if isinstance(since, str) else since
    pricing = load_pricing(pricing_path)
    run_dirs = discover_run_dirs(Path(runs_root))
    counts = {
        "runs_scanned": len(run_dirs),
        "runs_before_since": 0,
        "runs_not_completed": 0,
        "runs_no_episode": 0,
        "writer_unrecorded_runs": 0,
        "runs_measured": 0,
        "judge_unrecorded_runs": 0,
        "judge_recorded_runs": 0,
        "judge_no_call_runs": 0,
        "judge_estimated_runs": 0,
        "judge_mixed_source_runs": 0,
    }
    measured: list[RunCost] = []
    unpriced: dict[str, int] = {}
    for run_dir in run_dirs:
        run_meta = _read_json(run_dir / "run.json")
        created = _run_created_at(run_dir, run_meta)
        if cutoff is not None and created is not None and created < cutoff:
            counts["runs_before_since"] += 1
            continue
        run, category = run_cost_from_dir(
            run_dir,
            pricing=pricing,
            judge_model=judge_model,
            writer_model_default=writer_model_default,
            writer_price_model=writer_price_model,
            judge_api_model=judge_api_model,
        )
        if category == "not_completed":
            counts["runs_not_completed"] += 1
            continue
        if category == "no_episode":
            counts["runs_no_episode"] += 1
            continue
        if category == "writer_unrecorded" or run is None:
            counts["writer_unrecorded_runs"] += 1
            continue
        counts["runs_measured"] += 1
        measured.append(run)
        if run.writer_cost is None:
            key = writer_price_model or run.writer_model or "unknown"
            unpriced[key] = unpriced.get(key, 0) + 1
        if not run.judge_recorded:
            counts["judge_unrecorded_runs"] += 1
            continue
        counts["judge_recorded_runs"] += 1
        if run.judge_calls == 0:
            counts["judge_no_call_runs"] += 1
            continue
        if run.judge_estimated:
            counts["judge_estimated_runs"] += 1
        if run.judge_source == "mixed":
            counts["judge_mixed_source_runs"] += 1
        if run.judge_cost is None:
            # 没有价目行时别把它记成 judge_model——那会谎报「grok 未录价」，
            # 真相是这个 run 的判官压根不是走 CLI 那条路。
            key = run.judge_model or f"judge(usage_source={run.judge_source or '无'})"
            unpriced[key] = unpriced.get(key, 0) + 1

    judge_called = [run for run in measured if run.judge_recorded and run.judge_calls]
    with_judge = [run for run in measured if run.judge_recorded]
    estimated_share = (
        counts["judge_estimated_runs"] / len(judge_called) if judge_called else 0.0
    )
    stamps = sorted(run.created_at for run in measured if run.created_at)
    tokens = {
        "writer": {
            "input": distribution([run.writer_input for run in measured]),
            "output": distribution([run.writer_output for run in measured]),
        },
        "judge": {
            "input": distribution([run.judge_input for run in judge_called]),
            "output": distribution([run.judge_output for run in judge_called]),
            "calls": distribution([run.judge_calls for run in judge_called]),
        },
        "total": {
            "input": distribution([run.total_input for run in with_judge]),
            "output": distribution([run.total_output for run in with_judge]),
        },
    }
    cost = {
        "writer": distribution([run.writer_cost for run in measured], digits=4),
        "judge": distribution([run.judge_cost for run in judge_called], digits=4),
        "total": distribution([run.total_cost for run in with_judge], digits=4),
        "contains_estimated": estimated_share > 0,
    }
    priced_rows = [
        {
            "model_pattern": row.model_pattern,
            "input_cny_per_m": row.input_cny_per_m,
            "output_cny_per_m": row.output_cny_per_m,
            "cache_hit_cny_per_m": row.cache_hit_cny_per_m,
            "checked_at": row.checked_at,
            "source_url": row.source_url,
        }
        for row in pricing
    ]
    return {
        "schema": "research-cost/v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runs_root": str(Path(runs_root)),
        "since": cutoff.isoformat() if cutoff is not None else None,
        "date_range": {
            "first_run": stamps[0] if stamps else None,
            "last_run": stamps[-1] if stamps else None,
        },
        "counts": counts,
        "estimated_share": _round(estimated_share, 4),
        "tokens": tokens,
        "cost_cny_per_run": cost,
        "judge_model_assumed": judge_model,
        "judge_api_model_assumed": judge_api_model,
        "writer_model_default": writer_model_default,
        "writer_price_model": writer_price_model,
        "unpriced_models": dict(sorted(unpriced.items())),
        "pricing": {"path": str(Path(pricing_path)), "rows": priced_rows},
        "conditions": {
            "repo_root": str(REPO_ROOT),
            "interpreter": sys.executable,
            "revision": _git_revision(),
        },
        "runs": [run.to_dict() for run in measured],
    }


# ── 渲染 ───────────────────────────────────────────────────────────────


def _fmt(value: float | int | None, digits: int = 0) -> str:
    if value is None:
        return "—"
    if digits == 0:
        return f"{int(round(float(value))):,}"
    return f"{float(value):.{digits}f}"


def _dist_cells(dist: dict[str, Any], digits: int = 0) -> str:
    return (
        f"{_fmt(dist.get('median'), digits)} / "
        f"{_fmt(dist.get('mean'), digits)} / "
        f"{_fmt(dist.get('p90'), digits)}"
    )


def render_research_cost_markdown(report: dict[str, Any]) -> str:
    counts = report.get("counts") or {}
    tokens = report.get("tokens") or {}
    cost = report.get("cost_cny_per_run") or {}
    conditions = report.get("conditions") or {}
    pricing = report.get("pricing") or {}
    rows = pricing.get("rows") or []
    checked = sorted(
        {str(row.get("checked_at")) for row in rows if row.get("checked_at")}
    )
    estimated_share = float(report.get("estimated_share") or 0.0)
    cost_label = "元/次（中位 / 均值 / p90）"
    if estimated_share > 0:
        cost_label += "**（含估算）**"
    date_range = report.get("date_range") or {}
    unpriced = report.get("unpriced_models") or {}

    lines = [
        "# 单次研究全口径成本报表（写手 + 判官）",
        "",
        "## 成立条件",
        "",
        f"- 价目表：`{pricing.get('path')}`，checked_at = {', '.join(checked) or '—'}",
        (
            f"- run 数：扫描 {counts.get('runs_scanned', 0)}，完成且有写手 usage（进统计）"
            f" {counts.get('runs_measured', 0)}；判官有记账 {counts.get('judge_recorded_runs', 0)}"
            f"（其中判官未调用 {counts.get('judge_no_call_runs', 0)}），"
            f"判官未记账（旧格式）{counts.get('judge_unrecorded_runs', 0)}"
        ),
        (
            f"- 日期范围：{date_range.get('first_run') or '—'} → "
            f"{date_range.get('last_run') or '—'}；since = {report.get('since') or '全部'}"
        ),
        (
            f"- 估算记录占比（判官调用 run 中 usage_source=estimated 的比例）："
            f"{estimated_share:.1%}"
        ),
        (
            f"- 树 / 解释器 / revision：`{conditions.get('repo_root')}` / "
            f"`{conditions.get('interpreter')}` / `{conditions.get('revision') or '—'}`"
        ),
        (
            f"- 判官取价按 `usage_source` 分路（产物不落判官模型名）："
            f"`cli`/`estimated` → `{report.get('judge_model_assumed') or '—'}`，"
            f"`api` → `{report.get('judge_api_model_assumed') or '未给 --judge-api-model，不定价'}`，"
            f"`mixed` 不定价；"
            f"写手模型取 report.json.llm.model，缺则 `{report.get('writer_model_default') or '—'}`"
            + (
                f"；**写手成本按 `{report['writer_price_model']}` 价目 what-if 折算**"
                if report.get("writer_price_model")
                else ""
            )
        ),
        f"- 生成时间：{report.get('generated_at')}",
        "",
        "## 每次研究 token（中位 / 均值 / p90）",
        "",
        "| 侧 | n | input tokens | output tokens |",
        "| --- | ---: | --- | --- |",
    ]
    for label, key in (("写手", "writer"), ("判官", "judge"), ("合计", "total")):
        block = tokens.get(key) or {}
        input_dist = block.get("input") or {}
        output_dist = block.get("output") or {}
        lines.append(
            f"| {label} | {input_dist.get('n', 0)} | {_dist_cells(input_dist)} | "
            f"{_dist_cells(output_dist)} |"
        )
    judge_calls = (tokens.get("judge") or {}).get("calls") or {}
    lines.extend(
        [
            "",
            f"判官每次研究调用次数（中位 / 均值 / p90）：{_dist_cells(judge_calls, 1)}",
            "",
            "## 每次研究成本",
            "",
            f"| 侧 | n | {cost_label} |",
            "| --- | ---: | --- |",
        ]
    )
    judge_called_runs = int(counts.get("judge_recorded_runs", 0)) - int(
        counts.get("judge_no_call_runs", 0)
    )
    eligible = {
        "writer": int(counts.get("runs_measured", 0)),
        "judge": judge_called_runs,
        "total": int(counts.get("judge_recorded_runs", 0)),
    }
    for label, key in (("写手", "writer"), ("判官", "judge"), ("合计", "total")):
        dist = cost.get(key) or {}
        n = int(dist.get("n", 0))
        if n == 0 and eligible[key] > 0:
            cell = f"价目表未录（{eligible[key]} 个 run 无法折算）"
        else:
            cell = _dist_cells(dist, 4)
            if 0 < n < eligible[key]:
                cell += f"（仅 {n}/{eligible[key]} 个 run 有价）"
        lines.append(f"| {label} | {n} | {cell} |")
    if unpriced:
        lines.extend(
            [
                "",
                "价目表未录（或无匹配）的模型 → 对应 run 的成本列不计（不猜数）：",
            ]
        )
        for model, count in unpriced.items():
            lines.append(f"- `{model}`：{count} 个 run")
    if estimated_share > 0:
        lines.extend(
            [
                "",
                (
                    "⚠ 判官侧含估算记录（字符估算，不含 reasoning token 与 CLI 自带上下文）："
                    "成本列已标「含估算」，引用时须注明「判官侧为估算」。"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## 口径",
            "",
            "- 写手侧 = `outcome.usage`；判官侧 = `metrics.judge_usage`（INDEX #23 起写入）。",
            "- 合计列只含判官有记账的 run（旧格式 run 无法回填，不估）。判官未调用的 run 判官 token 按 0 计。",
            "- 分位数为线性插值；成本 = tokens × 价目表单价 / 1e6，缓存命中未单列。",
            "",
            "## 价目表",
            "",
            "| model_pattern | 输入 元/M | 输出 元/M | 缓存命中 元/M | checked_at |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row.get('model_pattern')}` | {_price(row.get('input_cny_per_m'))} | "
            f"{_price(row.get('output_cny_per_m'))} | {_price(row.get('cache_hit_cny_per_m'))} | "
            f"{row.get('checked_at') or '未核对'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _price(value: object) -> str:
    return "未录" if value is None else f"{float(value):g}"


def write_research_cost_report(
    report: dict[str, Any],
    out_dir: Path,
    *,
    stem: str | None = None,
) -> dict[str, Path]:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    name = stem or "research-cost"
    json_path = directory / f"{name}.json"
    md_path = directory / f"{name}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_research_cost_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="单次研究全口径成本报表：写手 + 判官 token 与元/次"
    )
    parser.add_argument(
        "--runs-root",
        "--runs-dir",
        dest="runs_root",
        required=True,
        help="run_* 目录的父目录，或含 */runs/run_* 的 users 根目录",
    )
    parser.add_argument(
        "--since",
        default="all",
        help="只统计此时间之后创建的 run（7d、24h、ISO 日期时间；all = 不过滤）",
    )
    parser.add_argument(
        "--out-dir",
        default="intelligence/eval/measurements",
        help="输出目录（research-cost-YYYY-MM-DD.{json,md}）",
    )
    parser.add_argument("--stem", default=None, help="输出文件名 stem")
    parser.add_argument(
        "--pricing",
        default=str(DEFAULT_PRICING_PATH),
        help="价目表 JSON（默认 intelligence/eval/pricing/llm-prices.json）",
    )
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help="CLI 主判官（usage_source=cli/estimated）的取价模型名（产物不落判官模型名）",
    )
    parser.add_argument(
        "--judge-api-model",
        default=None,
        help=(
            "备胎判官（usage_source=api）的取价模型名，取 LLM_JUDGE_FALLBACK_MODEL 的值；"
            "不给则那些 run 的判官成本不定价，并列进 unpriced_models"
        ),
    )
    parser.add_argument(
        "--writer-model",
        default=DEFAULT_WRITER_MODEL,
        help="report.json 缺 llm.model 时的写手模型名",
    )
    parser.add_argument(
        "--writer-price-model",
        default=None,
        help="what-if：写手 token 一律按此模型价目折算（如 glm-5.2，复现 BP §7.3 的算法）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    since = None if str(args.since).strip() in {"", "all"} else args.since
    report = aggregate_research_cost(
        Path(args.runs_root),
        since=since,
        pricing_path=args.pricing,
        judge_model=args.judge_model,
        writer_model_default=args.writer_model,
        writer_price_model=args.writer_price_model,
        judge_api_model=args.judge_api_model,
    )
    today = datetime.now().date().isoformat()
    stem = args.stem or f"research-cost-{today}"
    paths = write_research_cost_report(report, Path(args.out_dir), stem=stem)
    print(paths["json"])
    print(paths["md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
