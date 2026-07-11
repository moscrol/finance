#!/usr/bin/env python3
"""双盲同题答卷工装：输入冻结清单 + 机器可读答卷校验 + 跨期自动聚合。

对应 docs/learning/dual-blind-forecast-template.md 的三个改进点：

1. ``manifest``：答卷前先生成输入清单（DuckDB 截止日、材料文件 sha256、
   知识库 commit id），写入台账目录 ``<date>.manifest.json``。两份答卷
   必须引用同一份清单的 ``manifest_sha``，保证冻结输入一致（控制变量）。
2. ``validate``：校验机器可读答卷 ``<date>.answer.<agent>[.<source>].json``
   （source 可选，取 duckdb/briefing/sellside，同日同 agent 可按流各落一份）
   的必填字段与 manifest 一致性；答卷 markdown 照旧给人读，JSON 给机器算。
3. ``aggregate``：跨期聚合所有答卷 + 回检数据，按 agent 输出标的池
   T+1/T+3 均值、跑赢比例、阈值命中率等长期统计（单期噪声大，看聚合）。
4. ``verdict``：盘后验证结果的唯一机器可读落点 ``<date>.verdict.json``。
   逐假设 {id, agent, verdict: hit/miss/partial/unverifiable, actual, evidence_ref}，
   假设 id 必须引用对应答卷的假设 id（答卷可选 ``hypotheses`` 字段；未声明时
   从 thresholds/picks 派生：market / direction / falsify / target:<code>）。
   落盘后同时把回检表渲染进当日 ``<date>.md`` 的自动生成标记区（md 不存在时跳过并提示）。
5. ``index``：从 manifest/answer/verdict 扫描生成状态总表，写入 ``index.md``
   的自动生成标记区（人写的导航区不动）。加 ``--html`` 同时生成
   ``index.html`` 总入口：每日展开各 agent 的先验假设（主判断 + 市场/方向/证伪
   阈值 + 标的池），有 verdict 时逐假设标注 hit/miss，日期链接跳单日详情页。

用法::

    python3 scripts/dual_blind_forecast.py manifest --date 2026-07-03 \
        --perspective 2026-07-02 --material 复盘材料.md --material 卖方.md
    python3 scripts/dual_blind_forecast.py validate \
        docs/learning/forecast-review-ledger/2026-07-03.answer.codex.json
    python3 scripts/dual_blind_forecast.py aggregate [--json]
    python3 scripts/dual_blind_forecast.py verdict 草稿.json   # 校验后落盘 <date>.verdict.json
    python3 scripts/dual_blind_forecast.py index [--html]     # 重建 index.md 状态总表（--html 另出 index.html 总入口）

只读 DuckDB / 材料文件；不联网。找不到 DuckDB 时 manifest 相应字段留空并 WARN。
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LEDGER_DIR = REPO / "docs" / "learning" / "forecast-review-ledger"
DB_PATH = REPO / "db" / "market_feature_store.duckdb"

ALLOWED_AGENTS = {"codex", "claude", "devin"}
# 三流分账：盘面(duckdb, T+1) / 晨汇事件(briefing, 当日/T+1) / 晚间卖方(sellside, T+3/T+5)
# 验证窗口与评判标准不同，聚合必须分流统计，混池算胜率会互相污染。
# 问句模板见 docs/learning/forecast-question-templates.md
ALLOWED_SOURCES = {"duckdb", "briefing", "sellside"}
DEFAULT_SOURCE = "duckdb"
LATEST_ANSWER_SCHEMA = "1.1"
ALLOWED_ANSWER_SCHEMAS = {"1.0", LATEST_ANSWER_SCHEMA}
REQUIRED_ANSWER_FIELDS = (
    "schema_version",
    "date",
    "agent",
    "manifest_sha",
    "stage",
    "main_judgment",
    "direction_ranking",
    "picks",
    "thresholds",
)
REQUIRED_PICK_FIELDS = ("code", "name", "strategy", "reason")
REQUIRED_THRESHOLD_FIELDS = ("market", "direction", "targets", "falsify")
V11_REQUIRED_FIELDS = (
    "evidence_catalog",
    "stage_features",
    "threshold_provenance",
    "hypotheses",
)
ALLOWED_EVIDENCE_LEVELS = {"L1", "L2", "L3", "L4"}
ALLOWED_EVIDENCE_DIRECTIONS = {"support", "counter", "neutral"}
ALLOWED_THRESHOLD_ORIGINS = {"fixed_rule", "backtest", "mechanical", "heuristic"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_HYPOTHESIS_CATEGORIES = {"market", "direction", "target", "falsify"}
VERDICT_VALUES = {"hit", "miss", "partial", "unverifiable"}
VERDICT_LABELS = {"hit": "✅ hit", "miss": "❌ miss", "partial": "⚠️ partial", "unverifiable": "❓ unverifiable"}
REQUIRED_VERDICT_FIELDS = ("id", "agent", "verdict")
VERDICT_STREAMS = {"盘面", "晨汇", "卖方"}
VERDICT_HORIZONS = {"T+1", "T+3", "T+5"}
STREAM_TO_SOURCE = {"盘面": "duckdb", "晨汇": "briefing", "卖方": "sellside"}
INDEX_BEGIN = "<!-- BEGIN AUTO dual-blind-status 本表由 dual_blind_forecast.py index 生成，勿手改 -->"
INDEX_END = "<!-- END AUTO dual-blind-status -->"
VERDICT_BEGIN = "<!-- BEGIN AUTO dual-blind-verdict 本表由 dual_blind_forecast.py verdict 渲染，勿手改 -->"
VERDICT_END = "<!-- END AUTO dual-blind-verdict -->"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _duckdb_max_trade_date(db_path: Path) -> str | None:
    if not db_path.exists():
        return None
    try:
        import duckdb  # noqa: PLC0415 允许可选依赖延迟导入

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            row = None
            for table in ("fact_market_daily", "daily_market"):
                try:
                    row = con.execute(f"SELECT max(trade_date) FROM {table}").fetchone()
                    if row and row[0] is not None:
                        break
                except Exception:
                    row = None
        finally:
            con.close()
        return str(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def _kb_commit(kb_root: Path | None) -> str | None:
    if kb_root is None or not kb_root.exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(kb_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def manifest_path_for(date: str, ledger_dir: Path = LEDGER_DIR) -> Path:
    return ledger_dir / f"{date}.manifest.json"


def cmd_manifest(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    ledger_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    materials: list[dict[str, str]] = []
    for raw in args.material or []:
        path = Path(raw).expanduser()
        if not path.exists():
            print(f"ERROR: 材料文件不存在：{path}", file=sys.stderr)
            return 2
        materials.append({"path": str(path), "sha256": _sha256(path)})

    db_path = Path(args.db).expanduser() if args.db else DB_PATH
    duckdb_cutoff = _duckdb_max_trade_date(db_path)
    if duckdb_cutoff is None:
        warnings.append(f"DuckDB 不可读（{db_path}），duckdb_cutoff 留空——答卷前请人工确认数据截止日")

    kb_root = Path(args.kb_root).expanduser() if args.kb_root else None
    kb_commit = _kb_commit(kb_root)
    if kb_root and kb_commit is None:
        warnings.append(f"知识库 commit 不可读（{kb_root}）")

    body = {
        "schema_version": "1.0",
        "date": args.date,
        "perspective_date": args.perspective,
        "duckdb_path": str(db_path),
        "duckdb_cutoff": duckdb_cutoff,
        "kb_root": str(kb_root) if kb_root else None,
        "kb_commit": kb_commit,
        "materials": materials,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "warnings": warnings,
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True)
    body["manifest_sha"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    out_path = manifest_path_for(args.date, ledger_dir)
    out_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for warn in warnings:
        print(f"WARN: {warn}", file=sys.stderr)
    print(f"manifest_sha: {body['manifest_sha']}")
    print(f"written: {out_path}")
    return 0


def validate_answer(answer_path: Path, *, ledger_dir: Path = LEDGER_DIR) -> list[str]:
    """返回错误列表；空列表 = 通过。"""
    errors: list[str] = []
    try:
        answer = json.loads(answer_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"JSON 解析失败：{exc}"]

    for field in REQUIRED_ANSWER_FIELDS:
        if not answer.get(field):
            errors.append(f"缺必填字段 {field}")
    if errors:
        return errors
    schema_version = str(answer.get("schema_version") or "")
    if schema_version not in ALLOWED_ANSWER_SCHEMAS:
        errors.append(
            f"schema_version 应为 {sorted(ALLOWED_ANSWER_SCHEMAS)} 之一，实际 {schema_version}"
        )

    if str(answer["agent"]).lower() not in ALLOWED_AGENTS:
        errors.append(f"agent 应为 {sorted(ALLOWED_AGENTS)} 之一，实际 {answer['agent']}")

    source = str(answer.get("source") or DEFAULT_SOURCE).lower()
    if source not in ALLOWED_SOURCES:
        errors.append(f"source 应为 {sorted(ALLOWED_SOURCES)} 之一，实际 {answer.get('source')}")

    if ".answer." in answer_path.name:
        fname_agent, fname_source = parse_answer_filename(answer_path.name)
        if fname_agent != str(answer["agent"]).lower():
            errors.append(f"文件名 agent={fname_agent} 与答卷 agent={answer['agent']} 不一致")
        if fname_source is not None and fname_source != source:
            errors.append(f"文件名 source={fname_source} 与答卷 source={source} 不一致")

    picks = answer.get("picks") or []
    if not isinstance(picks, list) or not picks:
        errors.append("picks 应为非空列表")
    else:
        for i, pick in enumerate(picks):
            for field in REQUIRED_PICK_FIELDS:
                if not pick.get(field):
                    errors.append(f"picks[{i}] 缺字段 {field}")

    thresholds = answer.get("thresholds") or {}
    for field in REQUIRED_THRESHOLD_FIELDS:
        if not thresholds.get(field):
            errors.append(f"thresholds 缺字段 {field}（验证条件必须可证伪）")

    mpath = manifest_path_for(str(answer["date"]), ledger_dir)
    if not mpath.exists():
        errors.append(f"找不到输入清单 {mpath.name}——答卷前先跑 manifest 子命令")
    else:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        if answer["manifest_sha"] != manifest.get("manifest_sha"):
            errors.append(
                f"manifest_sha 不一致：答卷 {answer['manifest_sha']} vs 清单 {manifest.get('manifest_sha')}"
                "——输入未冻结或引用了旧清单"
            )
        if schema_version == LATEST_ANSWER_SCHEMA:
            errors.extend(
                _validate_v11_answer(
                    answer,
                    cutoff=str(manifest.get("perspective_date") or ""),
                )
            )
    return errors


def _date_not_after(value: Any, cutoff: str) -> bool:
    raw = str(value or "")[:10]
    return bool(raw and cutoff and raw <= cutoff[:10])


def _nonempty_refs(value: Any) -> bool:
    return isinstance(value, list) and bool([x for x in value if str(x).strip()])


def _validate_v11_answer(answer: dict[str, Any], *, cutoff: str) -> list[str]:
    errors: list[str] = []
    for field in V11_REQUIRED_FIELDS:
        if not answer.get(field):
            errors.append(f"schema 1.1 缺字段 {field}")

    catalog = answer.get("evidence_catalog")
    if isinstance(catalog, dict) and catalog:
        for evidence_id, evidence in catalog.items():
            if not isinstance(evidence, dict):
                errors.append(f"evidence_catalog.{evidence_id} 应为对象")
                continue
            for field in ("level", "source", "source_time", "direction"):
                if not evidence.get(field):
                    errors.append(f"evidence_catalog.{evidence_id} 缺字段 {field}")
            if str(evidence.get("level") or "") not in ALLOWED_EVIDENCE_LEVELS:
                errors.append(
                    f"evidence_catalog.{evidence_id}.level 应为 "
                    f"{sorted(ALLOWED_EVIDENCE_LEVELS)} 之一"
                )
            if str(evidence.get("direction") or "") not in ALLOWED_EVIDENCE_DIRECTIONS:
                errors.append(
                    f"evidence_catalog.{evidence_id}.direction 应为 "
                    f"{sorted(ALLOWED_EVIDENCE_DIRECTIONS)} 之一"
                )
            if evidence.get("source_time") and cutoff and not _date_not_after(
                evidence["source_time"], cutoff
            ):
                errors.append(
                    f"evidence_catalog.{evidence_id}.source_time={evidence['source_time']} "
                    f"晚于输入截止 {cutoff}"
                )
    elif catalog is not None:
        errors.append("evidence_catalog 应为非空对象")
    catalog_ids = set(catalog) if isinstance(catalog, dict) else set()

    def check_refs(path: str, refs: Any) -> None:
        if not _nonempty_refs(refs):
            errors.append(f"{path} 应为非空列表")
            return
        unknown = sorted({str(ref) for ref in refs} - catalog_ids)
        if unknown:
            errors.append(f"{path} 引用了不存在的 evidence id：{unknown}")

    stage = answer.get("stage_features")
    if isinstance(stage, dict):
        for field in ("rule_id", "as_of", "metrics", "evidence_refs"):
            if not stage.get(field):
                errors.append(f"stage_features 缺字段 {field}")
        metrics = stage.get("metrics")
        if not isinstance(metrics, dict) or not metrics:
            errors.append("stage_features.metrics 应为非空对象，阶段标签必须绑定确定性特征")
        else:
            for metric_name, metric in metrics.items():
                if not isinstance(metric, dict) or "value" not in metric or not metric.get(
                    "evidence_ref"
                ):
                    errors.append(
                        f"stage_features.metrics.{metric_name} 应含 value/evidence_ref"
                    )
                    continue
                evidence_ref = str(metric["evidence_ref"])
                if evidence_ref not in catalog_ids:
                    errors.append(
                        f"stage_features.metrics.{metric_name}.evidence_ref "
                        f"引用不存在的 evidence id：{evidence_ref}"
                    )
                    continue
                evidence = catalog[evidence_ref]
                if not isinstance(evidence, dict):
                    continue
                if evidence.get("field") and str(evidence["field"]) != str(metric_name):
                    errors.append(
                        f"stage_features.metrics.{metric_name} 与证据字段 "
                        f"{evidence['field']} 不一致"
                    )
                if "value" in evidence and evidence["value"] != metric["value"]:
                    errors.append(
                        f"stage_features.metrics.{metric_name} 数值 {metric['value']} "
                        f"与证据 {evidence_ref} 的 {evidence['value']} 不一致"
                    )
        check_refs("stage_features.evidence_refs", stage.get("evidence_refs"))
        if stage.get("as_of") and cutoff and not _date_not_after(stage["as_of"], cutoff):
            errors.append(
                f"stage_features.as_of={stage['as_of']} 晚于输入截止 {cutoff}"
            )
    elif stage is not None:
        errors.append("stage_features 应为对象")

    provenance = answer.get("threshold_provenance")
    if isinstance(provenance, dict):
        for field in REQUIRED_THRESHOLD_FIELDS:
            item = provenance.get(field)
            if not isinstance(item, dict):
                errors.append(f"threshold_provenance.{field} 应为对象")
                continue
            origin = str(item.get("origin") or "")
            if origin not in ALLOWED_THRESHOLD_ORIGINS:
                errors.append(
                    f"threshold_provenance.{field}.origin 应为 "
                    f"{sorted(ALLOWED_THRESHOLD_ORIGINS)} 之一"
                )
            if not item.get("evidence_ref"):
                errors.append(f"threshold_provenance.{field} 缺 evidence_ref")
            elif str(item["evidence_ref"]) not in catalog_ids:
                errors.append(
                    f"threshold_provenance.{field}.evidence_ref 引用不存在的 evidence id："
                    f"{item['evidence_ref']}"
                )
            if not item.get("as_of"):
                errors.append(f"threshold_provenance.{field} 缺 as_of")
            elif cutoff and not _date_not_after(item["as_of"], cutoff):
                errors.append(
                    f"threshold_provenance.{field}.as_of={item['as_of']} 晚于输入截止 {cutoff}"
                )
    elif provenance is not None:
        errors.append("threshold_provenance 应为对象")

    for i, pick in enumerate(answer.get("picks") or []):
        check_refs(f"picks[{i}].evidence_refs", pick.get("evidence_refs"))
        if not pick.get("evidence_as_of"):
            errors.append(f"picks[{i}] 缺 evidence_as_of")
        elif cutoff and not _date_not_after(pick["evidence_as_of"], cutoff):
            errors.append(
                f"picks[{i}].evidence_as_of={pick['evidence_as_of']} 晚于输入截止 {cutoff}"
            )

    hypotheses = answer.get("hypotheses")
    if isinstance(hypotheses, list) and hypotheses:
        seen_ids: set[str] = set()
        for i, hypothesis in enumerate(hypotheses):
            if not isinstance(hypothesis, dict):
                errors.append(f"hypotheses[{i}] 应为对象")
                continue
            for field in (
                "id",
                "category",
                "claim",
                "horizon",
                "confidence",
                "confidence_probability",
                "evidence_refs",
                "evidence_as_of",
                "falsify_when",
            ):
                if not hypothesis.get(field):
                    errors.append(f"hypotheses[{i}] 缺字段 {field}")
            hypothesis_id = str(hypothesis.get("id") or "")
            if hypothesis_id in seen_ids:
                errors.append(f"hypotheses[{i}].id 重复：{hypothesis_id}")
            seen_ids.add(hypothesis_id)
            if str(hypothesis.get("category") or "") not in ALLOWED_HYPOTHESIS_CATEGORIES:
                errors.append(
                    f"hypotheses[{i}].category 应为 "
                    f"{sorted(ALLOWED_HYPOTHESIS_CATEGORIES)} 之一"
                )
            if str(hypothesis.get("confidence") or "") not in ALLOWED_CONFIDENCE:
                errors.append(
                    f"hypotheses[{i}].confidence 应为 {sorted(ALLOWED_CONFIDENCE)} 之一"
                )
            probability = hypothesis.get("confidence_probability")
            if not isinstance(probability, (int, float)) or isinstance(probability, bool):
                errors.append(f"hypotheses[{i}].confidence_probability 应为 0~1 数字")
            elif not 0 <= float(probability) <= 1:
                errors.append(f"hypotheses[{i}].confidence_probability 应在 0~1 之间")
            if str(hypothesis.get("horizon") or "") not in VERDICT_HORIZONS:
                errors.append(
                    f"hypotheses[{i}].horizon 应为 {sorted(VERDICT_HORIZONS)} 之一"
                )
            check_refs(
                f"hypotheses[{i}].evidence_refs",
                hypothesis.get("evidence_refs"),
            )
            if hypothesis.get("evidence_as_of") and cutoff and not _date_not_after(
                hypothesis["evidence_as_of"], cutoff
            ):
                errors.append(
                    f"hypotheses[{i}].evidence_as_of={hypothesis['evidence_as_of']} "
                    f"晚于输入截止 {cutoff}"
                )
    elif hypotheses is not None:
        errors.append("hypotheses 应为非空列表")
    return errors


def hypothesis_ids(answer: dict[str, Any]) -> set[str]:
    """答卷的合法假设 id 集合：优先用显式 hypotheses，否则从 thresholds/picks 派生。"""
    explicit = {str(h.get("id")) for h in answer.get("hypotheses") or [] if h.get("id")}
    if explicit:
        return explicit
    ids = {"market", "direction", "falsify"}
    for pick in answer.get("picks") or []:
        if pick.get("code"):
            ids.add(f"target:{pick['code']}")
    return ids


def parse_answer_filename(name: str) -> tuple[str, str | None]:
    """解析 ``<date>.answer.<agent>[.<source>].json`` -> (agent, source|None)。"""
    suffix = name.split(".answer.", 1)[1].rsplit(".json", 1)[0].lower()
    if "." in suffix:
        agent, source = suffix.split(".", 1)
        return agent, source
    return suffix, None


def answer_paths_for(date: str, ledger_dir: Path = LEDGER_DIR) -> dict[str, Path]:
    """key 为文件名后缀 ``agent`` 或 ``agent.source``（同日同 agent 多流并存）。"""
    out: dict[str, Path] = {}
    for path in sorted(ledger_dir.glob(f"{date}.answer.*.json")):
        key = path.name.split(".answer.", 1)[1].rsplit(".json", 1)[0].lower()
        out[key] = path
    return out


def verdict_path_for(date: str, ledger_dir: Path = LEDGER_DIR) -> Path:
    return ledger_dir / f"{date}.verdict.json"


def validate_verdict(draft: dict[str, Any], *, ledger_dir: Path = LEDGER_DIR) -> list[str]:
    """返回错误列表；空列表 = 通过。"""
    errors: list[str] = []
    date = str(draft.get("date") or "")
    if not date:
        return ["缺必填字段 date"]
    verdicts = draft.get("verdicts")
    if not isinstance(verdicts, list) or not verdicts:
        return ["verdicts 应为非空列表"]

    answers = answer_paths_for(date, ledger_dir)
    ids_by_agent: dict[str, set[str]] = {}
    ids_by_agent_source: dict[tuple[str, str], set[str]] = {}
    sources_by_agent: dict[str, set[str]] = {}
    for key, path in answers.items():
        try:
            answer = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"答卷 {path.name} 不可读：{exc}")
            continue
        agent = str(answer.get("agent") or key.split(".", 1)[0]).lower()
        source = str(answer.get("source") or DEFAULT_SOURCE).lower()
        answer_ids = hypothesis_ids(answer)
        ids_by_agent.setdefault(agent, set()).update(answer_ids)
        ids_by_agent_source.setdefault((agent, source), set()).update(answer_ids)
        sources_by_agent.setdefault(agent, set()).add(source)

    for i, entry in enumerate(verdicts):
        for field in REQUIRED_VERDICT_FIELDS:
            if not entry.get(field):
                errors.append(f"verdicts[{i}] 缺字段 {field}")
                continue
        agent = str(entry.get("agent") or "").lower()
        if agent and agent not in ids_by_agent:
            errors.append(
                f"verdicts[{i}] agent={agent} 无对应答卷 {date}.answer.{agent}[.<source>].json——先有答卷再有验证"
            )
        elif agent and entry.get("id"):
            available_sources = sources_by_agent.get(agent, set())
            if len(available_sources) > 1 and not entry.get("source") and not entry.get(
                "stream"
            ):
                errors.append(
                    f"verdicts[{i}] {agent} 同日有多流答卷，必须填 source 或 stream"
                )
            source = _verdict_source(entry, available_sources=available_sources)
            source_ids = ids_by_agent_source.get((agent, source))
            if source_ids is None:
                errors.append(
                    f"verdicts[{i}] source={source} 无对应答卷 "
                    f"{date}.answer.{agent}.{source}.json"
                )
            elif str(entry["id"]) not in source_ids:
                errors.append(
                    f"verdicts[{i}] id={entry['id']} 不在 {agent}/{source} "
                    f"答卷假设集 {sorted(source_ids)} 内"
                )
        if entry.get("verdict") and str(entry["verdict"]) not in VERDICT_VALUES:
            errors.append(f"verdicts[{i}] verdict 应为 {sorted(VERDICT_VALUES)} 之一，实际 {entry['verdict']}")
        if str(entry.get("verdict")) in {"hit", "miss", "partial"} and not entry.get("actual"):
            errors.append(f"verdicts[{i}] 已裁定 {entry.get('verdict')} 必须填 actual（实际值/实际情况）")
        if entry.get("stream") and str(entry["stream"]) not in VERDICT_STREAMS:
            errors.append(f"verdicts[{i}] stream 应为 {sorted(VERDICT_STREAMS)} 之一，实际 {entry['stream']}")
        if entry.get("horizon") and str(entry["horizon"]) not in VERDICT_HORIZONS:
            errors.append(f"verdicts[{i}] horizon 应为 {sorted(VERDICT_HORIZONS)} 之一，实际 {entry['horizon']}")
    return errors


def cmd_verdict(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    draft_path = Path(args.draft).expanduser()
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: 草稿 JSON 解析失败：{exc}", file=sys.stderr)
        return 2
    errors = validate_verdict(draft, ledger_dir=ledger_dir)
    if errors:
        for err in errors:
            print(f"ERROR {draft_path.name}: {err}")
        return 1
    body = {
        "schema_version": draft.get("schema_version") or "1.0",
        "date": draft["date"],
        "verdicts": draft["verdicts"],
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    out_path = verdict_path_for(str(draft["date"]), ledger_dir)
    out_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK    written: {out_path}")
    md_path = render_verdict_md(body, ledger_dir=ledger_dir)
    if md_path is None:
        print(f"WARN: 当日台账 {draft['date']}.md 不存在，回检表未渲染", file=sys.stderr)
    else:
        print(f"OK    rendered: {md_path}")
    return 0


def build_verdict_table(verdict: dict[str, Any]) -> str:
    lines = [
        "| 假设 id | agent | 流 | 时点 | 判定 | 实际 | 归因 | 证据 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for entry in verdict.get("verdicts") or []:
        label = VERDICT_LABELS.get(str(entry.get("verdict") or ""), str(entry.get("verdict") or "—"))
        lines.append(
            f"| {entry.get('id') or '—'} | {entry.get('agent') or '—'} | {entry.get('stream') or '盘面'} "
            f"| {entry.get('horizon') or 'T+1'} | {label} | {entry.get('actual') or '—'} "
            f"| {entry.get('failure_mode') or '—'} | {entry.get('evidence_ref') or '—'} |"
        )
    stats = _verdict_stats(verdict)
    summary = []
    for agent, bucket in sorted(stats.items()):
        judged = bucket["hit"] + bucket["miss"] + bucket["partial"]
        summary.append(f"{agent} {bucket['hit']}/{judged}" if judged else f"{agent} 0/0")
    lines += ["", f"> 命中率（hit/已裁定）：{'，'.join(summary) if summary else '—'}"]
    return "\n".join(lines)


def render_verdict_md(verdict: dict[str, Any], *, ledger_dir: Path = LEDGER_DIR) -> Path | None:
    """把 verdict 回检表写进当日 <date>.md 的自动生成标记区；md 不存在返回 None。"""
    md_path = ledger_dir / f"{verdict['date']}.md"
    if not md_path.exists():
        return None
    block = (
        f"{VERDICT_BEGIN}\n\n### 盘后验证回检表（脚本渲染，来源 {verdict['date']}.verdict.json）\n\n"
        f"{build_verdict_table(verdict)}\n\n{VERDICT_END}"
    )
    text = md_path.read_text(encoding="utf-8")
    if VERDICT_BEGIN in text and VERDICT_END in text:
        head, rest = text.split(VERDICT_BEGIN, 1)
        _, tail = rest.split(VERDICT_END, 1)
        text = head + block + tail
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    md_path.write_text(text, encoding="utf-8")
    return md_path


def _verdict_stats(verdict: dict[str, Any]) -> dict[str, dict[str, int]]:
    """按 agent 统计 hit/miss/partial/unverifiable 个数。"""
    stats: dict[str, dict[str, int]] = {}
    for entry in verdict.get("verdicts") or []:
        agent = str(entry.get("agent") or "unknown").lower()
        bucket = stats.setdefault(agent, {v: 0 for v in sorted(VERDICT_VALUES)})
        value = str(entry.get("verdict") or "")
        if value in bucket:
            bucket[value] += 1
    return stats


def build_index_table(ledger_dir: Path = LEDGER_DIR) -> str:
    dates: set[str] = set()
    for pattern in ("*.manifest.json", "*.answer.*.json", "*.verdict.json"):
        for path in ledger_dir.glob(pattern):
            dates.add(path.name.split(".", 1)[0])
    lines = [
        "| 研判日 | manifest | 答卷 | 答卷校验 | 验证 | 命中率（hit/已裁定） |",
        "|---|---|---|---|---|---|",
    ]
    for date in sorted(dates, reverse=True):
        has_manifest = "✅" if manifest_path_for(date, ledger_dir).exists() else "—"
        answers = answer_paths_for(date, ledger_dir)
        answer_cell = ", ".join(sorted(answers)) if answers else "—"
        checks = []
        for agent, path in sorted(answers.items()):
            checks.append(f"{agent}:{'✅' if not validate_answer(path, ledger_dir=ledger_dir) else '❌'}")
        check_cell = " ".join(checks) if checks else "—"
        vpath = verdict_path_for(date, ledger_dir)
        if vpath.exists():
            try:
                stats = _verdict_stats(json.loads(vpath.read_text(encoding="utf-8")))
                rates = []
                for agent, bucket in sorted(stats.items()):
                    judged = bucket["hit"] + bucket["miss"] + bucket["partial"]
                    rate = f"{bucket['hit']}/{judged}" if judged else "0/0"
                    rates.append(f"{agent}:{rate}")
                verdict_cell, rate_cell = "✅", " ".join(rates) if rates else "—"
            except Exception:
                verdict_cell, rate_cell = "❌不可读", "—"
        else:
            verdict_cell, rate_cell = "—", "—"
        lines.append(f"| {date} | {has_manifest} | {answer_cell} | {check_cell} | {verdict_cell} | {rate_cell} |")
    if len(lines) == 2:
        lines.append("| （暂无机器可读台账文件） | — | — | — | — | — |")
    return "\n".join(lines)


def _ledger_dates(ledger_dir: Path) -> list[str]:
    dates: set[str] = set()
    for pattern in ("*.manifest.json", "*.answer.*.json", "*.verdict.json"):
        for path in ledger_dir.glob(pattern):
            dates.add(path.name.split(".", 1)[0])
    return sorted(dates, reverse=True)


def _verdicts_by_key(verdict: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(e.get("agent") or "").lower(), str(e.get("id") or "")): e
        for e in verdict.get("verdicts") or []
    }


def _html_hypothesis_rows(answer: dict[str, Any], agent: str, vmap: dict[tuple[str, str], dict[str, Any]]) -> str:
    esc = html_mod.escape
    thresholds = answer.get("thresholds") or {}
    rows: list[tuple[str, str]] = [
        ("market", str(thresholds.get("market") or "—")),
        ("direction", str(thresholds.get("direction") or "—")),
        ("falsify", str(thresholds.get("falsify") or "—")),
    ]
    for pick in answer.get("picks") or []:
        if pick.get("code"):
            rows.append((f"target:{pick['code']}", f"{pick.get('name') or ''} {pick.get('reason') or ''}".strip() or "—"))
    cells = []
    for hid, text in rows:
        entry = vmap.get((agent, hid))
        if entry:
            value = str(entry.get("verdict") or "")
            label = f'<span class="v v-{esc(value)}">{esc(VERDICT_LABELS.get(value, value))}</span>'
            actual = f'<div class="actual">实际：{esc(str(entry.get("actual") or "—"))}</div>'
        else:
            label, actual = '<span class="v v-pending">待验证</span>', ""
        cells.append(
            f'<tr><td class="hid">{esc(hid)}</td><td>{esc(text)}{actual}</td><td>{label}</td></tr>'
        )
    return "".join(cells)


def build_index_html(ledger_dir: Path = LEDGER_DIR) -> str:
    esc = html_mod.escape
    sections: list[str] = []
    for date in _ledger_dates(ledger_dir):
        vpath = verdict_path_for(date, ledger_dir)
        vmap: dict[tuple[str, str], dict[str, Any]] = {}
        if vpath.exists():
            try:
                vmap = _verdicts_by_key(json.loads(vpath.read_text(encoding="utf-8")))
            except Exception:
                vmap = {}
        cards: list[str] = []
        for key, apath in sorted(answer_paths_for(date, ledger_dir).items()):
            try:
                answer = json.loads(apath.read_text(encoding="utf-8"))
            except Exception:
                cards.append(f'<div class="card"><h3>{esc(key)}</h3><p class="muted">答卷不可读</p></div>')
                continue
            agent = str(answer.get("agent") or key.split(".", 1)[0]).lower()
            title = key.replace(".", " · ")
            cards.append(
                f'<div class="card"><h3>{esc(title)}</h3>'
                f'<p class="judgment">{esc(str(answer.get("main_judgment") or "—"))}</p>'
                f'<table><thead><tr><th>假设</th><th>内容</th><th>验证</th></tr></thead>'
                f'<tbody>{_html_hypothesis_rows(answer, agent, vmap)}</tbody></table></div>'
            )
        if not cards:
            cards.append('<p class="muted">当日无机器可读答卷</p>')
        md_link = f'<a href="{esc(date)}.md">md</a>'
        html_link = f' · <a href="{esc(date)}.html">并排页</a>' if (ledger_dir / f"{date}.html").exists() else ""
        md_path = ledger_dir / f"{date}.md"
        raw_block = ""
        if md_path.exists():
            raw_block = (
                f'<details class="raw"><summary>当日原文（{esc(date)}.md，点开展开）</summary>'
                f'<pre>{esc(md_path.read_text(encoding="utf-8"))}</pre></details>'
            )
        sections.append(
            f'<section><h2>{esc(date)} <small>{md_link}{html_link}</small></h2>'
            f'<div class="cards">{"".join(cards)}</div>{raw_block}</section>'
        )
    body = "\n".join(sections) or '<p class="muted">暂无机器可读台账文件（answer/verdict JSON）。</p>'
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>双盲复盘台账总入口</title>
<style>
  :root {{ --bg:#f7f8fa; --text:#1f2933; --muted:#64748b; --line:#d9dee7; --panel:#ffffff;
           --good:#0f8b5f; --bad:#c2410c; --warn:#a16207; --blue:#2563eb; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); line-height:1.55;
          font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  header {{ background:#111827; color:#fff; padding:24px 32px; }}
  header h1 {{ margin:0; font-size:24px; }}
  header p {{ margin:6px 0 0; color:#cbd5e1; font-size:13px; }}
  main {{ max-width:1100px; margin:0 auto; padding:24px 32px 64px; }}
  section {{ margin-bottom:32px; }}
  h2 {{ border-bottom:1px solid var(--line); padding-bottom:6px; }}
  h2 small {{ font-size:13px; font-weight:400; margin-left:8px; }}
  .cards {{ display:flex; gap:16px; flex-wrap:wrap; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px;
           padding:16px; flex:1 1 480px; }}
  .card h3 {{ margin:0 0 8px; text-transform:capitalize; }}
  .judgment {{ font-weight:600; }}
  table {{ border-collapse:collapse; width:100%; font-size:13px; }}
  th,td {{ border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }}
  .hid {{ white-space:nowrap; font-family:ui-monospace,monospace; }}
  .actual {{ color:var(--muted); font-size:12px; margin-top:4px; }}
  .muted {{ color:var(--muted); }}
  .v {{ white-space:nowrap; }}
  .v-hit {{ color:var(--good); }} .v-miss {{ color:var(--bad); }}
  .v-partial {{ color:var(--warn); }} .v-unverifiable,.v-pending {{ color:var(--muted); }}
  details.raw {{ margin-top:12px; background:var(--panel); border:1px solid var(--line);
                 border-radius:8px; padding:8px 12px; }}
  details.raw summary {{ cursor:pointer; color:var(--blue); font-size:13px; }}
  details.raw pre {{ white-space:pre-wrap; word-break:break-word; font-size:12px;
                     max-height:70vh; overflow:auto; }}
</style>
</head>
<body>
<header><h1>双盲复盘台账总入口</h1>
<p>每日各 agent 先验假设（主判断 + 市场/方向/证伪阈值 + 标的池）与盘后验证。由 dual_blind_forecast.py index --html 生成于 {esc(generated)}，勿手改。</p></header>
<main>{body}</main>
</body>
</html>
"""


def cmd_index(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    index_path = ledger_dir / "index.md"
    block = f"{INDEX_BEGIN}\n\n## 机检状态总表（脚本生成）\n\n{build_index_table(ledger_dir)}\n\n{INDEX_END}"
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8")
        if INDEX_BEGIN in text and INDEX_END in text:
            head, rest = text.split(INDEX_BEGIN, 1)
            _, tail = rest.split(INDEX_END, 1)
            text = head + block + tail
        else:
            text = text.rstrip("\n") + "\n\n" + block + "\n"
    else:
        text = "# 复盘推演回检台账\n\n" + block + "\n"
    index_path.write_text(text, encoding="utf-8")
    print(f"written: {index_path}")
    if getattr(args, "html", False):
        html_path = ledger_dir / "index.html"
        html_path.write_text(build_index_html(ledger_dir), encoding="utf-8")
        print(f"written: {html_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    failed = False
    for raw in args.answers:
        path = Path(raw).expanduser()
        errors = validate_answer(path, ledger_dir=ledger_dir)
        if errors:
            failed = True
            for err in errors:
                print(f"ERROR {path.name}: {err}")
        else:
            print(f"OK    {path.name}")
    return 1 if failed else 0


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _hypothesis_category(hypothesis_id: str) -> str:
    if hypothesis_id.startswith("target:"):
        return "target"
    if hypothesis_id in ALLOWED_HYPOTHESIS_CATEGORIES:
        return hypothesis_id
    return "unknown"


def _verdict_source(
    entry: dict[str, Any],
    *,
    available_sources: set[str],
) -> str:
    explicit = str(entry.get("source") or "").lower()
    if explicit in ALLOWED_SOURCES:
        return explicit
    if entry.get("stream"):
        return STREAM_TO_SOURCE.get(str(entry["stream"]), DEFAULT_SOURCE)
    if len(available_sources) == 1:
        return next(iter(available_sources))
    return DEFAULT_SOURCE


def _calibration_metrics(samples: list[tuple[float, int]]) -> dict[str, Any]:
    if not samples:
        return {
            "n": 0,
            "auc": None,
            "brier": None,
            "ece_5bin": None,
            "decision_eligible": False,
            "reason": "没有同时包含概率与 hit/miss 裁定的样本",
        }
    positives = [score for score, label in samples if label == 1]
    negatives = [score for score, label in samples if label == 0]
    auc: float | None = None
    if positives and negatives:
        wins = sum(
            1.0 if positive > negative else 0.5 if positive == negative else 0.0
            for positive in positives
            for negative in negatives
        )
        auc = round(wins / (len(positives) * len(negatives)), 4)
    brier = round(
        sum((score - label) ** 2 for score, label in samples) / len(samples),
        4,
    )
    weighted_error = 0.0
    for bin_index in range(5):
        lower = bin_index / 5
        upper = (bin_index + 1) / 5
        bucket = []
        for score, label in samples:
            in_bucket = lower <= score <= upper if bin_index == 4 else lower <= score < upper
            if in_bucket:
                bucket.append((score, label))
        if not bucket:
            continue
        mean_score = sum(score for score, _ in bucket) / len(bucket)
        hit_rate = sum(label for _, label in bucket) / len(bucket)
        weighted_error += len(bucket) / len(samples) * abs(mean_score - hit_rate)
    return {
        "n": len(samples),
        "auc": auc,
        "brier": brier,
        "ece_5bin": round(weighted_error, 4),
        "decision_eligible": False,
        "reason": "指标只做观测；需预注册最小样本和样本外验收阈值后才能升级硬闸门",
    }


def aggregate(ledger_dir: Path = LEDGER_DIR) -> dict[str, Any]:
    """聚合答卷与裁定，严格按 agent/source/category/confidence 分账。"""
    per_agent: dict[tuple[str, str], dict[str, Any]] = {}
    answer_sources: dict[tuple[str, str], set[str]] = {}
    hypothesis_meta: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for answer_path in sorted(ledger_dir.glob("*.answer.*.json")):
        try:
            answer = json.loads(answer_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        agent = str(answer.get("agent") or "unknown").lower()
        source = str(answer.get("source") or DEFAULT_SOURCE).lower()
        answer_date = str(answer.get("date") or "")
        answer_sources.setdefault((answer_date, agent), set()).add(source)
        for hypothesis in answer.get("hypotheses") or []:
            if not isinstance(hypothesis, dict) or not hypothesis.get("id"):
                continue
            hypothesis_id = str(hypothesis["id"])
            hypothesis_meta[(answer_date, agent, source, hypothesis_id)] = {
                "category": str(
                    hypothesis.get("category") or _hypothesis_category(hypothesis_id)
                ),
                "confidence": str(hypothesis.get("confidence") or "unknown"),
                "confidence_probability": str(
                    hypothesis.get("confidence_probability")
                    if hypothesis.get("confidence_probability") is not None
                    else ""
                ),
            }
        stat = per_agent.setdefault(
            (agent, source),
            {
                "answers": 0,
                "rechecked": 0,
                "pick_returns_t1": [],
                "pick_returns_t3": [],
                "beat_benchmark_t3": 0,
                "market_threshold_hits": 0,
                "market_threshold_checked": 0,
                "dates": [],
            },
        )
        stat["answers"] += 1
        stat["dates"].append(str(answer.get("date")))
        recheck = answer.get("recheck") or {}
        if not recheck:
            continue
        stat["rechecked"] += 1
        for key, bucket in (("pick_returns_t1", "pick_returns_t1"), ("pick_returns_t3", "pick_returns_t3")):
            values = recheck.get(key) or []
            stat[bucket].extend(float(v) for v in values)
        if recheck.get("beat_benchmark_t3"):
            stat["beat_benchmark_t3"] += 1
        if "market_threshold_hit" in recheck:
            stat["market_threshold_checked"] += 1
            if recheck["market_threshold_hit"]:
                stat["market_threshold_hits"] += 1

    verdict_stats: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    category_stats: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    confidence_stats: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    calibration_samples: dict[tuple[str, str], list[tuple[float, int]]] = {}
    failure_modes: dict[tuple[str, str], dict[str, int]] = {}
    for vpath in sorted(ledger_dir.glob("*.verdict.json")):
        try:
            verdict = json.loads(vpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        verdict_date = str(verdict.get("date") or "")
        for entry in verdict.get("verdicts") or []:
            agent = str(entry.get("agent") or "unknown").lower()
            source = _verdict_source(
                entry,
                available_sources=answer_sources.get((verdict_date, agent), set()),
            )
            agent_source = (agent, source)
            key = f"{entry.get('stream') or '盘面'}/{entry.get('horizon') or 'T+1'}"
            bucket = verdict_stats.setdefault(agent_source, {}).setdefault(
                key, {v: 0 for v in sorted(VERDICT_VALUES)}
            )
            value = str(entry.get("verdict") or "")
            if value in bucket:
                bucket[value] += 1
            hypothesis_id = str(entry.get("id") or "")
            meta = hypothesis_meta.get(
                (verdict_date, agent, source, hypothesis_id),
                {},
            )
            category = str(
                entry.get("category")
                or meta.get("category")
                or _hypothesis_category(hypothesis_id)
            )
            category_bucket = category_stats.setdefault(agent_source, {}).setdefault(
                category, {v: 0 for v in sorted(VERDICT_VALUES)}
            )
            if value in category_bucket:
                category_bucket[value] += 1
            confidence = str(entry.get("confidence") or meta.get("confidence") or "unknown")
            confidence_bucket = confidence_stats.setdefault(agent_source, {}).setdefault(
                confidence, {v: 0 for v in sorted(VERDICT_VALUES)}
            )
            if value in confidence_bucket:
                confidence_bucket[value] += 1
            probability_raw = entry.get(
                "confidence_probability",
                meta.get("confidence_probability"),
            )
            if value in {"hit", "miss"}:
                try:
                    probability = float(probability_raw)
                except (TypeError, ValueError):
                    probability = -1.0
                if 0 <= probability <= 1:
                    calibration_samples.setdefault(agent_source, []).append(
                        (probability, 1 if value == "hit" else 0)
                    )
            if entry.get("failure_mode"):
                fm = failure_modes.setdefault(agent_source, {})
                fm[str(entry["failure_mode"])] = fm.get(str(entry["failure_mode"]), 0) + 1

    agents: dict[str, Any] = {}
    for (agent, source), stat in sorted(per_agent.items()):
        checked = stat["market_threshold_checked"]
        agents[f"{agent}/{source}"] = {
            "agent": agent,
            "source": source,
            "answers": stat["answers"],
            "rechecked": stat["rechecked"],
            "dates": stat["dates"],
            "avg_pick_return_t1": _mean(stat["pick_returns_t1"]),
            "avg_pick_return_t3": _mean(stat["pick_returns_t3"]),
            "beat_benchmark_t3": stat["beat_benchmark_t3"],
            "market_threshold_hit_rate": (
                round(stat["market_threshold_hits"] / checked, 4) if checked else None
            ),
            "verdicts_by_stream_horizon": verdict_stats.get((agent, source), {}),
            "verdicts_by_category": category_stats.get((agent, source), {}),
            "verdicts_by_confidence": confidence_stats.get((agent, source), {}),
            "calibration_metrics": _calibration_metrics(
                calibration_samples.get((agent, source), [])
            ),
            "failure_modes": failure_modes.get((agent, source), {}),
        }
    for agent, source in sorted(set(verdict_stats) - set(per_agent)):
        key = f"{agent}/{source}"
        agents[key] = {
            "agent": agent,
            "source": source,
            "answers": 0,
            "rechecked": 0,
            "dates": [],
            "avg_pick_return_t1": None,
            "avg_pick_return_t3": None,
            "beat_benchmark_t3": 0,
            "market_threshold_hit_rate": None,
            "verdicts_by_stream_horizon": verdict_stats[(agent, source)],
            "verdicts_by_category": category_stats.get((agent, source), {}),
            "verdicts_by_confidence": confidence_stats.get((agent, source), {}),
            "calibration_metrics": _calibration_metrics(
                calibration_samples.get((agent, source), [])
            ),
            "failure_modes": failure_modes.get((agent, source), {}),
        }
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ledger_dir": str(ledger_dir),
        "agents": agents,
        "notes": [
            "分流分账：同一 agent 的 duckdb/briefing/sellside 三流分开统计，验证窗口不同不可混池。",
            "分类分账：市场、方向、标的、证伪分别统计，禁止用总分掩盖方向或标的选择偏弱。",
            "信心分桶仅用于校准观察；样本不足或高/中/低命中率不单调时，不得升级为评分或硬闸门。",
            "单期噪声大：answers < 10 的 agent 统计只作参考，不下结论。",
            "recheck 块由回检人/脚本按统一指标回填：pick_returns_t1/t3（标的池各标的收益%）、",
            "beat_benchmark_t3（标的池 T+3 是否跑赢基准）、market_threshold_hit（§5 市场阈值是否命中）。",
        ],
    }


def _render_aggregate_md(report: dict[str, Any]) -> str:
    lines = [
        "# 双盲答卷跨期聚合",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "| agent | 流 | 答卷数 | 已回检 | T+1 标的均值% | T+3 标的均值% | T+3 跑赢次数 | 市场阈值命中率 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, stat in report["agents"].items():
        lines.append(
            f"| {stat.get('agent', key)} | {stat.get('source', '-')} | {stat['answers']} | {stat['rechecked']} | "
            f"{stat['avg_pick_return_t1'] if stat['avg_pick_return_t1'] is not None else '-'} | "
            f"{stat['avg_pick_return_t3'] if stat['avg_pick_return_t3'] is not None else '-'} | "
            f"{stat['beat_benchmark_t3']} | "
            f"{stat['market_threshold_hit_rate'] if stat['market_threshold_hit_rate'] is not None else '-'} |"
        )
    verdict_rows = []
    for agent, stat in report["agents"].items():
        for key, bucket in sorted((stat.get("verdicts_by_stream_horizon") or {}).items()):
            judged = bucket["hit"] + bucket["miss"] + bucket["partial"]
            stream, horizon = key.split("/", 1)
            verdict_rows.append(
                f"| {agent} | {stream} | {horizon} | {bucket['hit']} | {bucket['miss']} "
                f"| {bucket['partial']} | {bucket['unverifiable']} | "
                f"{round(bucket['hit'] / judged, 4) if judged else '-'} |"
            )
    if verdict_rows:
        lines += [
            "",
            "## 盘后验证按流×时点",
            "",
            "| agent | 流 | 时点 | hit | miss | partial | unverifiable | 命中率 |",
            "|---|---|---|---:|---:|---:|---:|---:|",
            *verdict_rows,
        ]
        for title, field in (
            ("按判断类别", "verdicts_by_category"),
            ("按信心档", "verdicts_by_confidence"),
        ):
            rows = []
            for agent, stat in report["agents"].items():
                for group, bucket in sorted((stat.get(field) or {}).items()):
                    judged = bucket["hit"] + bucket["miss"] + bucket["partial"]
                    rows.append(
                        f"| {agent} | {group} | {bucket['hit']} | {bucket['miss']} "
                        f"| {bucket['partial']} | {bucket['unverifiable']} | "
                        f"{round(bucket['hit'] / judged, 4) if judged else '-'} |"
                    )
            if rows:
                lines += [
                    "",
                    f"## {title}",
                    "",
                    "| agent/流 | 分组 | hit | miss | partial | unverifiable | 命中率 |",
                    "|---|---|---:|---:|---:|---:|---:|",
                    *rows,
                ]
        calibration_rows = []
        for agent, stat in report["agents"].items():
            metrics = stat.get("calibration_metrics") or {}
            calibration_rows.append(
                f"| {agent} | {metrics.get('n', 0)} | "
                f"{metrics.get('auc') if metrics.get('auc') is not None else '-'} | "
                f"{metrics.get('brier') if metrics.get('brier') is not None else '-'} | "
                f"{metrics.get('ece_5bin') if metrics.get('ece_5bin') is not None else '-'} | "
                f"{'是' if metrics.get('decision_eligible') else '否'} |"
            )
        if calibration_rows:
            lines += [
                "",
                "## 概率校准观察",
                "",
                "| agent/流 | 已决样本 | AUC | Brier | ECE(5 bins) | 可进入硬闸门 |",
                "|---|---:|---:|---:|---:|---|",
                *calibration_rows,
                "",
                "> 校准指标当前只做观测；升级条件必须预注册，不能看完结果后临时改门槛。",
            ]
        fm_lines = []
        for agent, stat in report["agents"].items():
            fms = stat.get("failure_modes") or {}
            if fms:
                fm_lines.append(f"- {agent}：" + "，".join(f"{k}×{v}" for k, v in sorted(fms.items(), key=lambda kv: -kv[1])))
        if fm_lines:
            lines += ["", "### miss/partial 归因分布", "", *fm_lines]
    lines += ["", "> " + " ".join(report["notes"])]
    return "\n".join(lines) + "\n"


BENCHMARK = "sh000001"  # 统一基准：上证指数（fact_market_daily.sh_index_close），写进 recheck 块保证跨期可比


def _recheck_from_duckdb(answer: dict[str, Any], manifest: dict[str, Any], db_path: Path) -> tuple[dict[str, Any], list[str]]:
    """从 DuckDB 自动回填数值类指标；返回 (recheck 块增量, 警告列表)。

    只填机器能算的：pick_returns_t1/t3、benchmark_return_t3、beat_benchmark_t3。
    market_threshold_hit 是自然语言阈值，仍由人判定回填。
    """
    import duckdb  # noqa: PLC0415 可选依赖延迟导入

    warnings: list[str] = []
    perspective = str(manifest.get("perspective_date") or "")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        dates = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT trade_date FROM fact_stock_daily WHERE trade_date > ? ORDER BY trade_date LIMIT 3",
            [perspective],
        ).fetchall()]
        if not dates:
            return {}, [f"DuckDB 里没有 {perspective} 之后的交易日，无法回检"]
        t1 = dates[0]
        t3 = dates[2] if len(dates) >= 3 else None
        if t3 is None:
            warnings.append(f"T+3 数据未到（目前只到 {dates[-1]}），只回填 T+1")

        def _close(code: str, day: str) -> float | None:
            row = con.execute(
                "SELECT close FROM fact_stock_daily WHERE trade_date = ? AND split_part(stock_ts_code, '.', 1) = ? LIMIT 1",
                [day, code],
            ).fetchone()
            return float(row[0]) if row and row[0] is not None else None

        def _pct_chg(code: str, day: str) -> float | None:
            row = con.execute(
                "SELECT pct_chg FROM fact_stock_daily WHERE trade_date = ? AND split_part(stock_ts_code, '.', 1) = ? LIMIT 1",
                [day, code],
            ).fetchone()
            return float(row[0]) if row and row[0] is not None else None

        returns_t1: list[float] = []
        returns_t3: list[float] = []
        for pick in answer.get("picks") or []:
            code = str(pick.get("code") or "")
            r1 = _pct_chg(code, t1)
            if r1 is None:
                warnings.append(f"{code} 在 {t1} 无行情，T+1 缺失")
            else:
                returns_t1.append(round(r1, 4))
            if t3:
                c3 = _close(code, t3)
                pre = con.execute(
                    "SELECT pre_close FROM fact_stock_daily WHERE trade_date = ? AND split_part(stock_ts_code, '.', 1) = ? LIMIT 1",
                    [t1, code],
                ).fetchone()
                base = float(pre[0]) if pre and pre[0] is not None else None
                if base and c3:
                    returns_t3.append(round((c3 / base - 1) * 100, 4))
                else:
                    warnings.append(f"{code} T+3 收盘缺失")

        bench_t3 = None
        if t3:
            rows = con.execute(
                "SELECT trade_date, sh_index_close FROM fact_market_daily WHERE trade_date IN (?, ?) ORDER BY trade_date",
                [perspective, t3],
            ).fetchall()
            if len(rows) == 2 and rows[0][1] and rows[1][1]:
                bench_t3 = round((float(rows[1][1]) / float(rows[0][1]) - 1) * 100, 4)
            else:
                warnings.append("基准指数收盘缺失，beat_benchmark_t3 留空")

        block: dict[str, Any] = {
            "benchmark": BENCHMARK,
            "recheck_t1_date": t1,
            "recheck_t3_date": t3,
            "pick_returns_t1": returns_t1,
            "pick_returns_t3": returns_t3,
            "benchmark_return_t3": bench_t3,
            "recheck_generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        if bench_t3 is not None and returns_t3:
            block["beat_benchmark_t3"] = (sum(returns_t3) / len(returns_t3)) > bench_t3
        return block, warnings
    finally:
        con.close()


def cmd_recheck(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    db_path = Path(args.db).expanduser() if args.db else DB_PATH
    if not db_path.exists():
        print(f"ERROR: DuckDB 不存在：{db_path}（在有库的机器上跑，或 --db 指定）", file=sys.stderr)
        return 2
    failed = False
    for raw in args.answers:
        path = Path(raw).expanduser()
        answer = json.loads(path.read_text(encoding="utf-8"))
        mpath = manifest_path_for(str(answer.get("date")), ledger_dir)
        if not mpath.exists():
            print(f"ERROR {path.name}: 找不到 manifest {mpath.name}", file=sys.stderr)
            failed = True
            continue
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        block, warnings = _recheck_from_duckdb(answer, manifest, db_path)
        for warn in warnings:
            print(f"WARN {path.name}: {warn}", file=sys.stderr)
        if not block:
            failed = True
            continue
        recheck = dict(answer.get("recheck") or {})
        recheck.update(block)  # 只覆盖机器字段，保留人工回填（如 market_threshold_hit）
        answer["recheck"] = recheck
        path.write_text(json.dumps(answer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK    {path.name}: T+1={block['recheck_t1_date']} T+3={block['recheck_t3_date']} "
              f"picks_t1={len(block['pick_returns_t1'])} picks_t3={len(block['pick_returns_t3'])}")
    return 1 if failed else 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    report = aggregate(Path(args.ledger_dir).expanduser())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_render_aggregate_md(report), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger-dir", default=str(LEDGER_DIR), help="台账目录；默认 docs/learning/forecast-review-ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    p_manifest = sub.add_parser("manifest", help="答卷前生成输入冻结清单 <date>.manifest.json")
    p_manifest.add_argument("--date", required=True, help="研判日 YYYY-MM-DD（前瞻的目标日）")
    p_manifest.add_argument("--perspective", required=True, help="观察视角日 YYYY-MM-DD（站在哪天盘后）")
    p_manifest.add_argument("--material", action="append", default=[], help="冻结的复盘材料文件，可重复")
    p_manifest.add_argument("--db", default=None, help="DuckDB 路径；默认 db/market_feature_store.duckdb")
    p_manifest.add_argument("--kb-root", default=None, help="知识库仓根目录（记录其 HEAD commit）")
    p_manifest.set_defaults(func=cmd_manifest)

    p_validate = sub.add_parser("validate", help="校验机器可读答卷 <date>.answer.<agent>.json")
    p_validate.add_argument("answers", nargs="+", help="答卷 JSON 路径，可多个")
    p_validate.set_defaults(func=cmd_validate)

    p_aggregate = sub.add_parser("aggregate", help="跨期聚合所有答卷+回检，按 agent 出长期统计")
    p_aggregate.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown 表")
    p_aggregate.set_defaults(func=cmd_aggregate)

    p_recheck = sub.add_parser("recheck", help="从 DuckDB 自动回填答卷的数值类 recheck 指标（基准上证指数）")
    p_recheck.add_argument("answers", nargs="+", help="答卷 JSON 路径，可多个；就地更新 recheck 块")
    p_recheck.add_argument("--db", default=None, help="DuckDB 路径；默认 db/market_feature_store.duckdb")
    p_recheck.set_defaults(func=cmd_recheck)

    p_verdict = sub.add_parser("verdict", help="校验验证草稿并落盘 <date>.verdict.json（盘后验证唯一写入口）")
    p_verdict.add_argument("draft", help="验证草稿 JSON：{date, verdicts:[{id, agent, verdict, actual, evidence_ref}]}")
    p_verdict.set_defaults(func=cmd_verdict)

    p_index = sub.add_parser("index", help="扫描台账目录，重建 index.md 的机检状态总表区块")
    p_index.add_argument("--html", action="store_true", help="同时生成 index.html 总入口（每日各 agent 先验假设 + 验证标注）")
    p_index.set_defaults(func=cmd_index)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
