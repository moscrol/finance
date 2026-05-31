#!/usr/bin/env python3
"""
Disclosure Archive — Auto Evidence Gap Backfill。

从知识库自动发现证据缺口，生成 evidence-gap-queue.json，
或对已完成的归档批次进行收尾（batch summary + review queue + check）。

用法:
  # Step 1: 生成证据缺口队列
  python3 auto_gap_backfill.py --mode gap-queue

  # Step 1b: 限制输出条数
  python3 auto_gap_backfill.py --mode gap-queue --limit 20

  # Step 4: 归档完成后收尾
  python3 auto_gap_backfill.py --mode finalize --batch-id batch-20260527-0003
"""
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAULT = Path.home() / "Desktop" / "c c" / "知识库" / "wiki"
DEFAULT_DISCLOSURES_DIR = DEFAULT_VAULT / "raw" / "disclosures"
TZ = timezone(timedelta(hours=8))

# ── A股过滤 ──
A_SHARE_PREFIXES = ("000", "002", "003", "300", "301", "600", "601", "603", "605", "688")

# ── Gap 状态枚举与冷却期 ──
GAP_STATUS_ENUMS = {
    "pending": "待处理，可被 auto-gap-backfill 选择",
    "selected": "已被某批次选中，正在处理中",
    "archived": "已归档，从活跃队列移除",
    "skipped_no_accessible_source": "跳过：无可访问来源（冷却 30 天）",
    "deferred_no_stronger_evidence": "延后：未找到更强证据（冷却 90 天）",
    "deferred_weak_or_indirect_only": "延后：仅有弱/间接证据（冷却 90 天）",
    "deferred_role_too_generic": "延后：role 描述过于泛化（冷却 60 天）",
    "deferred_concept_boundary_unclear": "延后：概念边界不清（冷却 60 天）",
    "failed_runtime_error": "失败：运行时错误（冷却 7 天）",
}

DEFAULT_COOLDOWN_PERIODS = {
    "skipped_no_accessible_source": 30,
    "deferred_no_stronger_evidence": 90,
    "deferred_weak_or_indirect_only": 90,
    "deferred_role_too_generic": 60,
    "deferred_concept_boundary_unclear": 60,
    "failed_runtime_error": 7,
}

ACTIVE_STATUSES = {"pending", "selected"}


def is_a_share(code: str) -> bool:
    """判断是否为 A 股（6 位数字，符合 A 股代码前缀）。"""
    if not code or not isinstance(code, str):
        return False
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        return False
    return code.startswith(A_SHARE_PREFIXES)


# ── P0 — 已有低质量证据需升级 ──
LOW_QUALITY_UPDATE_TYPES = {"graph_only", "weak_signal", "review_candidate"}
LOW_QUALITY_EVIDENCE_LAYERS = {"L1", "L3", "L4"}

# ── P3 — 间接匹配类型，缺直接证据 ──
INDIRECT_MATCH_TYPES = {"adjacent_substitute", "upstream_component", "inferred_only", "negative"}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARN] 无法加载 {path}: {e}", file=sys.stderr)
        return {}


def load_manifest(disclosures_dir: Path) -> list:
    manifest_path = disclosures_dir / "manifest.jsonl"
    if not manifest_path.exists():
        return []
    records = []
    with manifest_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"[WARN] manifest 第 {i} 行解析失败", file=sys.stderr)
    return records


def build_manifest_index(manifest: list) -> dict:
    """构建 (company, canonical_concept) → records 的索引。"""
    idx = defaultdict(list)
    for r in manifest:
        key = (r.get("company", ""), r.get("canonical_concept", ""))
        idx[key].append(r)
    return dict(idx)


def build_exposure_index(entity_exposures: dict) -> dict:
    """构建 (company, concept) → edge 的索引。"""
    idx = {}
    entities = entity_exposures.get("entities", {})
    for entity_name, entity_data in entities.items():
        codes = entity_data.get("codes", [])
        concepts = entity_data.get("concepts", {})
        for concept_name, edge in concepts.items():
            idx[(entity_name, concept_name)] = {
                "entity_name": entity_name,
                "concept": concept_name,
                "codes": codes,  # 从父实体继承股票代码
                **edge,
            }
    return idx


def build_concept_graph_crossref(concept_graph: dict, exposure_index: dict) -> dict:
    """构建 concept → exposed_entities 的反向索引（仅 concept_graph 中存在的概念）。"""
    ref = defaultdict(list)
    graph_concepts = set(concept_graph.get("concepts", {}).keys())
    for (company, concept), edge in exposure_index.items():
        if concept in graph_concepts:
            ref[concept].append({**edge, "company": company})
    return dict(ref)


# ═══════════════════════════════════════════════════════════════════
#  Gap Detection
# ═══════════════════════════════════════════════════════════════════

def detect_p0_upgrade_gaps(manifest: list, exposure_index: dict, manifest_index: dict) -> list:
    """P0: manifest 中已有低质量记录，可以升级为更高质量证据。"""
    gaps = []
    seen = set()

    for r in manifest:
        ut = r.get("update_type", "")
        el = r.get("evidence_layer", "")
        cmt = r.get("concept_match_type", "")
        company = r.get("company", "")
        concept = r.get("canonical_concept", "")

        is_low_quality = ut in LOW_QUALITY_UPDATE_TYPES or el in LOW_QUALITY_EVIDENCE_LAYERS
        if not is_low_quality:
            continue

        key = (company, concept)
        if key in seen:
            continue
        seen.add(key)

        # 查 entity_exposures 获取当前 strength/role
        exp_edge = exposure_index.get(key, {})
        current_strength = exp_edge.get("strength", r.get("exposure_strength", "related"))

        # 判断 gap_type
        if cmt in INDIRECT_MATCH_TYPES:
            gap_type = "archived_adjacent_needs_direct"
            missing = f"当前仅有间接/推断证据（{cmt}），需补充 primary_official 直接证据"
        else:
            gap_type = "weak_entity_exposure"
            missing = f"当前证据质量不足（{el}/{ut}），需升级为 L2 baseline/hard_delta"

        gaps.append({
            "gap_type": gap_type,
            "priority": "P0",
            "canonical_concept": concept,
            "theme_term": r.get("theme_term", concept),
            "company": company,
            "code": r.get("code", ""),
            "current_evidence_layer": el,
            "current_update_type": ut,
            "current_source_type": r.get("source_type", ""),
            "current_strength": current_strength,
            "concept_match_type": cmt,
            "missing_reason": missing,
            "suggested_query_terms": _build_query_terms(r),
            "suggested_source_types": _suggest_sources(r),
            "expected_chain_layer": r.get("chain_layer", ""),
            "expected_role": r.get("role", ""),
            "uncertainty": "需查找更高质量的一手来源",
            "recommended_archive_limit": 1,
        })

    return gaps


def detect_p1_stub_gaps(concept_graph: dict, concept_graph_crossref: dict,
                         manifest_index: dict, exposure_index: dict) -> list:
    """P1: concept_graph 中 low confidence + empty companies 的概念。"""
    gaps = []
    seen = set()
    concepts = concept_graph.get("concepts", {})
    manifest_key_set = set(manifest_index.keys())

    # 按 inbound links 数排序（越多概念引用此概念，越值得补）
    inbound_counts = defaultdict(int)
    for name, node in concepts.items():
        for rel in node.get("related_concepts", []):
            if isinstance(rel, dict):
                inbound_counts[rel.get("name", "")] += 1

    candidates = []
    for name, node in concepts.items():
        if node.get("confidence") != "low":
            continue

        exposed_entities = concept_graph_crossref.get(name, [])
        if not exposed_entities:
            continue  # 无实体暴露于该概念，跳过

        # 过滤已有记录的 entities
        fresh_entities = [e for e in exposed_entities
                          if (e["company"], name) not in manifest_key_set]
        if not fresh_entities:
            continue

        candidates.append((name, node, fresh_entities, inbound_counts.get(name, 0)))

    # 按 inbound 降序排列
    candidates.sort(key=lambda x: -x[3])

    for concept_name, node, fresh_entities, inbound_count in candidates:
        if len(gaps) >= 100:
            break

        for entity in fresh_entities[:5]:
            key = (entity["company"], concept_name)
            if key in seen:
                continue
            seen.add(key)

            # 推断 theme_term (canonical_concept 的简体中文别名)
            theme_term = concept_name

            gaps.append({
                "gap_type": "concept_stub_missing_evidence",
                "priority": "P1",
                "canonical_concept": concept_name,
                "theme_term": theme_term,
                "company": entity["company"],
                "code": _extract_code(entity, exposure_index),
                "current_evidence_layer": "none",
                "current_update_type": "none",
                "current_source_type": "none",
                "current_strength": entity.get("strength", "related"),
                "concept_match_type": "none",
                "missing_reason": (
                    f'概念 "{concept_name}" 在 concept_graph 中 confidence=low，'
                    f'{inbound_count} 个关联概念，inbound_links={inbound_count}'
                ),
                "suggested_query_terms": _build_generic_terms(entity["company"], concept_name),
                "suggested_source_types": ["official_website_product", "annual_report", "announcement", "interactive_e"],
                "expected_chain_layer": _infer_chain_layer(entity, node),
                "expected_role": entity.get("role", ""),
                "uncertainty": "该概念在知识图谱中为低置信度，需验证公司与概念的关联强度",
                "recommended_archive_limit": 1,
            })

    return gaps


def detect_p2_empty_radar_gaps(concept_graph: dict, exposure_index: dict,
                                manifest_index: dict) -> list:
    """P2: entity_exposures 中有暴露但概念在 graph 中公司数≤2，无归档。"""
    gaps = []
    seen = set()
    manifest_key_set = set(manifest_index.keys())
    concepts = concept_graph.get("concepts", {})

    # 找出公司数≤2的概念（排除已有很多公司的成熟概念）
    concepts_few_companies = {
        name for name, node in concepts.items()
        if len(node.get("companies", [])) <= 2
    }

    for (company, concept), edge in exposure_index.items():
        if concept not in concepts_few_companies:
            continue
        if (company, concept) in manifest_key_set:
            continue

        key = (company, concept)
        if key in seen:
            continue
        seen.add(key)

        node = concepts.get(concept, {})

        if len(gaps) >= 100:
            break

        gaps.append({
            "gap_type": "radar_empty_frame",
            "priority": "P2",
            "canonical_concept": concept,
            "theme_term": concept,
            "company": company,
            "code": _extract_code(edge, exposure_index),
            "current_evidence_layer": "none",
            "current_update_type": "none",
            "current_source_type": "none",
            "current_strength": edge.get("strength", "related"),
            "concept_match_type": "none",
            "missing_reason": (
                f'entity_exposures 中 {company} 暴露于 "{concept}"，'
                f'但 concept_graph 中该概念仅有 {len(node.get("companies", []))} 家公司，且无披露归档'
            ),
            "suggested_query_terms": _build_generic_terms(company, concept),
            "suggested_source_types": ["official_website_product", "interactive_e", "annual_report"],
            "expected_chain_layer": _infer_chain_layer(edge, node),
            "expected_role": edge.get("role", ""),
            "uncertainty": "需验证公司是否真正涉及该概念的核心业务",
            "recommended_archive_limit": 1,
        })

    return gaps


def detect_p3_indirect_needs_direct(manifest: list, manifest_index: dict) -> list:
    """P3: 已有间接证据（adjacent/upstream/inferred），但缺 direct_alias 直接证据。"""
    gaps = []
    seen = set()

    for r in manifest:
        cmt = r.get("concept_match_type", "")
        if cmt not in INDIRECT_MATCH_TYPES:
            continue

        company = r.get("company", "")
        concept = r.get("canonical_concept", "")

        # 检查是否已有 direct_alias 记录
        existing = manifest_index.get((company, concept), [])
        has_direct = any(e.get("concept_match_type") == "direct_alias" for e in existing)
        if has_direct:
            continue

        key = (company, concept)
        if key in seen:
            continue
        seen.add(key)

        gaps.append({
            "gap_type": "archived_adjacent_needs_direct",
            "priority": "P3",
            "canonical_concept": concept,
            "theme_term": r.get("theme_term", concept),
            "company": company,
            "code": r.get("code", ""),
            "current_evidence_layer": r.get("evidence_layer", ""),
            "current_update_type": r.get("update_type", ""),
            "current_source_type": r.get("source_type", ""),
            "current_strength": r.get("exposure_strength", "related"),
            "concept_match_type": cmt,
            "missing_reason": (
                f"仅有 {cmt} 类型证据，缺少 direct_alias 或 primary_official 直接证据"
            ),
            "suggested_query_terms": _build_query_terms(r),
            "suggested_source_types": _suggest_sources(r),
            "expected_chain_layer": r.get("chain_layer", ""),
            "expected_role": r.get("role", ""),
            "uncertainty": "需确认公司与概念的直接关联",
            "recommended_archive_limit": 1,
        })

    return gaps


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════

def _extract_code(entity_data: dict, exposure_index: dict) -> str:
    """从 entity_exposures 数据中提取股票代码。"""
    codes = entity_data.get("codes", [])
    if codes:
        return codes[0]
    # fallback: 从 exposure_index 中查找
    for (company, concept), edge in exposure_index.items():
        if company == entity_data.get("company", ""):
            c = edge.get("codes", edge.get("code", ""))
            if isinstance(c, list) and c:
                return c[0]
            if isinstance(c, str) and c:
                return c
    return ""


def _build_query_terms(record: dict) -> list:
    """从已有记录生成建议搜索词。"""
    terms = []
    company = record.get("company", "")
    concept = record.get("canonical_concept", "")
    if company and concept:
        terms.append(f"{company} {concept}")
    if record.get("role"):
        terms.append(f"{company} {record['role']}")
    sour = record.get("source_type", "")
    if sour in ("annual_report",):
        terms.append(f"{company} 年报 {concept}")
    elif sour in ("interactive_e", "sse_e_interaction",):
        terms.append(f"{company} {concept} 互动易")
    return terms


def _suggest_sources(record: dict) -> list:
    """根据当前证据质量推荐合适的来源类型。"""
    el = record.get("evidence_layer", "")
    if el in ("L4",):
        return ["official_website_product", "annual_report", "announcement"]
    elif el in ("L3",):
        return ["annual_report", "announcement", "official_website_product"]
    elif el in ("L1",):
        return ["official_website_product", "interactive_e", "annual_report"]
    return ["official_website_product", "interactive_e", "annual_report"]


def _build_generic_terms(company: str, concept: str) -> list:
    return [
        f"{company} {concept}",
        f"{company} {concept} 业务",
        f"{company} 年报 {concept}",
    ]


def _infer_chain_layer(edge: dict, node: dict) -> str:
    """从 concept_graph 的 supply_chain 推断 chain_layer。"""
    sc = node.get("supply_chain", {})
    if sc:
        # 取第一个有值的 layer
        for layer in ("upstream_materials", "midstream_manufacturing",
                       "downstream_application", "ecosystem"):
            if sc.get(layer):
                return layer
    return ""


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════

def load_gap_queue(disclosures_dir: Path) -> dict:
    """加载现有 evidence-gap-queue.json。"""
    gap_queue_path = disclosures_dir / "evidence-gap-queue.json"
    if not gap_queue_path.exists():
        return {"gaps": []}
    try:
        return json.loads(gap_queue_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] 无法加载 gap queue: {e}", file=sys.stderr)
        return {"gaps": []}


def is_gap_active(gap: dict, now: datetime = None) -> bool:
    """判断 gap 是否处于可被选中的活跃状态。"""
    if now is None:
        now = datetime.now(TZ)
    status = gap.get("status", "pending")
    if status in ACTIVE_STATUSES:
        return True
    # 检查冷却期是否已过
    next_check = gap.get("next_check_after", "")
    if next_check:
        try:
            check_dt = datetime.fromisoformat(next_check)
            if now >= check_dt:
                return True  # 冷却期已过，可重试
        except (ValueError, TypeError):
            pass
    return False


def generate_gap_queue(vault: Path, disclosures_dir: Path, limit: int = 200,
                       include_deferred: bool = False,
                       force_gap_id: str = "") -> dict:
    """生成 evidence-gap-queue.json。

    include_deferred=True 时，包含所有冷却期已过的 deferred/skipped gaps。
    force_gap_id 指定时，强制将该 gap 设为 selected 并返回。
    """
    # 加载现有队列以获取状态信息
    existing_queue = load_gap_queue(disclosures_dir)
    existing_gaps = existing_queue.get("gaps", [])
    existing_status_map = {}
    for g in existing_gaps:
        key = (g.get("company", ""), g.get("canonical_concept", ""))
        existing_status_map[key] = {
            "status": g.get("status", "pending"),
            "status_reason": g.get("status_reason", ""),
            "status_updated_at": g.get("status_updated_at", ""),
            "next_check_after": g.get("next_check_after", ""),
            "gap_id": g.get("gap_id", ""),
        }

    # 如果指定了 force_gap_id，直接从现有队列中找
    if force_gap_id:
        forced = [g for g in existing_gaps if g.get("gap_id") == force_gap_id]
        if not forced:
            print(f"[ERR] force_gap_id='{force_gap_id}' 在现有队列中不存在", file=sys.stderr)
            sys.exit(1)
        now_iso = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
        for g in forced:
            g["status"] = "selected"
            g["status_reason"] = f"force selected via --force-gap-id at {now_iso}"
            g["status_updated_at"] = now_iso
            g.pop("next_check_after", None)
        return {
            "generated_at": now_iso,
            "total_gaps": len(forced),
            "by_priority": {},
            "summary": f"强制选择 gap: {force_gap_id}",
            "safety_statement": existing_queue.get("safety_statement", ""),
            "gaps": forced,
        }

    entity_exposures = load_json(vault / "relations" / "entity_exposures.json")
    concept_graph = load_json(vault / "relations" / "concept_graph.json")
    manifest = load_manifest(disclosures_dir)
    manifest_index = build_manifest_index(manifest)
    exposure_index = build_exposure_index(entity_exposures)
    graph_crossref = build_concept_graph_crossref(concept_graph, exposure_index)

    # 收集各优先级 gaps
    all_gaps = []
    all_gaps.extend(detect_p0_upgrade_gaps(manifest, exposure_index, manifest_index))
    all_gaps.extend(detect_p1_stub_gaps(concept_graph, graph_crossref, manifest_index, exposure_index))
    all_gaps.extend(detect_p2_empty_radar_gaps(concept_graph, exposure_index, manifest_index))
    all_gaps.extend(detect_p3_indirect_needs_direct(manifest, manifest_index))

    # ── 只保留 A 股 ──
    all_gaps = [g for g in all_gaps if is_a_share(g.get("code", ""))]

    # 排序
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    all_gaps.sort(key=lambda g: priority_order.get(g["priority"], 99))

    # 去重：同级 (company, canonical_concept) 只保留最高优先级
    seen_pairs = set()
    deduped = []
    for g in all_gaps:
        pair = (g["company"], g["canonical_concept"])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        deduped.append(g)
    all_gaps = deduped

    # 分配 gap_id（保留现有 gap_id 和状态）
    now_iso = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    new_gap_counter = 0
    for g in all_gaps:
        key = (g["company"], g["canonical_concept"])
        existing = existing_status_map.get(key, {})
        if existing and existing.get("gap_id"):
            g["gap_id"] = existing["gap_id"]
            g["status"] = existing.get("status", "pending")
            g["status_reason"] = existing.get("status_reason", "")
            g["status_updated_at"] = existing.get("status_updated_at", "")
            if existing.get("next_check_after"):
                g["next_check_after"] = existing["next_check_after"]
        else:
            new_gap_counter += 1
            g["gap_id"] = f"gap-{datetime.now(TZ).strftime('%Y%m%d')}-{new_gap_counter:04d}"
            g["status"] = "pending"
            g["status_reason"] = ""
            g["status_updated_at"] = now_iso
            g["next_check_after"] = None

    # ── 过滤非活跃 gap ──
    skipped_inactive = 0
    if not include_deferred:
        now = datetime.now(TZ)
        active_gaps = []
        for g in all_gaps:
            if is_gap_active(g, now):
                active_gaps.append(g)
            else:
                skipped_inactive += 1
        all_gaps = active_gaps

    all_gaps = all_gaps[:limit]

    summary_parts = [
        f"共发现 {len(all_gaps)} 个活跃证据缺口。"
    ]
    for p in ["P0", "P1", "P2", "P3"]:
        cnt = sum(1 for g in all_gaps if g["priority"] == p)
        if cnt:
            summary_parts.append(f"{p}: {cnt} 个")
    if skipped_inactive:
        summary_parts.append(f"（跳过 {skipped_inactive} 个冷却期未到的非活跃 gap）")

    queue = {
        "generated_at": now_iso,
        "total_gaps": len(all_gaps),
        "by_priority": {
            p: sum(1 for g in all_gaps if g["priority"] == p)
            for p in ["P0", "P1", "P2", "P3"]
        },
        "summary": "；".join(summary_parts) + "。每次选择 1 个 canonical_concept，3-5 家公司，每家公司最多 1 条证据。",
        "safety_statement": (
            "此为证据缺口发现阶段，尚未产生任何归档记录。"
            "未修改 entities/concepts/relations，未运行 writer。"
        ),
        "gaps": all_gaps,
    }

    return queue


def run_finalize(batch_id: str, disclosures_dir: Path, vault: Path):
    """Wrap-up after archiving: batch_summary + review_queue + check + auto summary."""
    batches_dir = disclosures_dir / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    # 1. batch_summary
    print(f"[1/5] 生成批次摘要: {batch_id}")
    subprocess.run([
        sys.executable, str(SKILL_DIR / "scripts" / "batch_summary.py"),
        "--batch-id", batch_id,
        "--disclosures-dir", str(disclosures_dir),
        "--skip-check",
    ], check=False)

    # 2. review_queue — infer canonical_concept from manifest
    manifest = load_manifest(disclosures_dir)
    batch_concepts = sorted(set(
        r.get("canonical_concept", "") for r in manifest
        if r.get("batch_id") == batch_id
    ))
    for concept in batch_concepts:
        if concept:
            print(f"[2/5] 生成 review queue: {concept}")
            subprocess.run([
                sys.executable, str(SKILL_DIR / "scripts" / "review_queue.py"),
                "--canonical-concept", concept,
                "--disclosures-dir", str(disclosures_dir),
            ], check=False)

    # 3. check.py
    print("[3/5] 运行 check.py")
    check_result = subprocess.run([
        sys.executable, str(SKILL_DIR / "scripts" / "check.py"),
        "--disclosures-dir", str(disclosures_dir),
    ], capture_output=True, text=True, check=False)

    check_status = "PASS" if check_result.returncode == 0 else "FAIL"

    # 4. assemble auto-backfill summary
    print("[4/5] 生成 auto-backfill summary")
    batch_file = batches_dir / f"{batch_id}.json"
    batch_data = {}
    if batch_file.exists():
        batch_data = json.loads(batch_file.read_text(encoding="utf-8"))

    summary = {
        "backfill_id": f"auto-{batch_id}",
        "batch_id": batch_id,
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "selected_concepts": batch_data.get("canonical_concept", ""),
        "selected_companies": batch_data.get("companies", []),
        "archived_count": batch_data.get("archived_count", 0),
        "by_evidence_layer": batch_data.get("by_evidence_layer", {}),
        "by_update_type": batch_data.get("by_update_type", {}),
        "by_source_type": batch_data.get("by_source_type", {}),
        "check_status": check_status,
        "safety_statement": (
            "本批次仅归档至 wiki/raw/disclosures/，"
            "未修改 entities/concepts/relations，未运行 writer。"
        ),
        "next_review_suggestion": batch_data.get("next_review_suggestion", "建议在 review queue 中审核本批次归档"),
    }

    output = batches_dir / f"auto-backfill-{batch_id}.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] auto-backfill summary: {output}")

    # 5. report
    print()
    print(f"[5/5] ======== Auto Gap Backfill 完成 ========")
    print(f"  batch_id:        {batch_id}")
    print(f"  concepts:        {', '.join(batch_concepts)}")
    print(f"  companies:       {len(summary['selected_companies'])}")
    print(f"  archived:        {summary['archived_count']}")
    print(f"  evidence layers: {summary['by_evidence_layer']}")
    print(f"  update types:    {summary['by_update_type']}")
    print(f"  check:           {check_status}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto Evidence Gap Backfill")
    parser.add_argument("--mode", choices=["gap-queue", "finalize"],
                        default="gap-queue",
                        help="gap-queue: 生成证据缺口队列；finalize: 归档完成后收尾")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT),
                        help="知识库根目录")
    parser.add_argument("--disclosures-dir", default=str(DEFAULT_DISCLOSURES_DIR))
    parser.add_argument("--limit", type=int, default=200,
                        help="gap-queue 模式：最大输出条数")
    parser.add_argument("--batch-id", default="",
                        help="finalize 模式：批次 ID")
    parser.add_argument("--output", default="",
                        help="gap-queue 模式：输出文件路径（默认 evidence-gap-queue.json）")
    parser.add_argument("--include-deferred", action="store_true",
                        help="gap-queue 模式：包含冷却期已过的 deferred/skipped gaps")
    parser.add_argument("--force-gap-id", default="",
                        help="gap-queue 模式：强制选择指定 gap_id，忽略冷却期")
    args = parser.parse_args()

    vault = Path(args.vault)
    disclosures_dir = Path(args.disclosures_dir)

    if args.mode == "gap-queue":
        print("=" * 50)
        print("Auto Gap Backfill — 证据缺口发现")
        print(f"时间: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}")
        print(f"知识库: {vault}")
        print(f"归档目录: {disclosures_dir}")
        print("=" * 50)
        print()

        queue = generate_gap_queue(vault, disclosures_dir, args.limit,
                                   include_deferred=args.include_deferred,
                                   force_gap_id=args.force_gap_id)

        output_path = Path(args.output) if args.output else (
            disclosures_dir / "evidence-gap-queue.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        print(f"[OK] 证据缺口队列写入: {output_path}")
        print(f"     总缺口: {queue['total_gaps']}")
        print(f"     优先级分布: {queue['by_priority']}")
        print()
        print("前 10 项:")
        for g in queue["gaps"][:10]:
            print(f"  {g['gap_id']} [{g['priority']}] {g['gap_type']}")
            print(f"    {g['company']} → {g['canonical_concept']}")
            print(f"    当前: {g['current_evidence_layer']}/{g['current_update_type']}")
            print(f"    原因: {g['missing_reason'][:80]}...")

    elif args.mode == "finalize":
        if not args.batch_id:
            print("[ERR] finalize 模式需要 --batch-id", file=sys.stderr)
            sys.exit(1)
        run_finalize(args.batch_id, disclosures_dir, vault)


if __name__ == "__main__":
    main()
