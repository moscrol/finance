#!/usr/bin/env python3
"""
Disclosure Archive — 健康检查。

检查已归档的 manifest.jsonl，验证每条记录是否仍满足当前约束规则。
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SKILL_DIR.parent
DEFAULT_VAULT = Path.home() / "Desktop" / "c c" / "知识库" / "wiki"
DEFAULT_DISCLOSURES_DIR = DEFAULT_VAULT / "raw" / "disclosures"

# ── 与 archive.py 保持一致的约束 ──

VALID_CHAIN_LAYERS = {
    "upstream_materials", "upstream_equipment",
    "midstream_manufacturing", "midstream_service",
    "downstream_application", "ecosystem",
}
VALID_EXPOSURE_STRENGTHS = {"core", "related", "peripheral", "watchlist"}
VALID_EVIDENCE_LAYERS = {"L1", "L2", "L3", "L4"}
VALID_UPDATE_TYPES = {
    "baseline", "hard_delta", "review_candidate",
    "graph_only", "weak_signal", "reject",
}
VALID_FACT_TYPES = {
    "revenue_mix", "capacity", "shipment", "product_launch",
    "certification", "customer_adoption", "contract", "tender_win",
    "mass_production", "project_construction", "product_capability",
    "official_claim", "media_signal",
}
VALID_FACT_STATUSES = {
    "realized", "disclosed", "under_validation",
    "planned", "framework", "rumored",
}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_SOURCE_TYPES = {
    "announcement", "annual_report", "semiannual_report", "quarterly_report",
    "prospectus", "offering_circular", "exchange_inquiry_reply",
    "official_website_product", "official_website_news",
    "investor_relation_record", "interactive_e", "sse_e_interaction",
    "official_wechat", "authoritative_media", "news", "industry_media",
    "forwarded_content", "other",
}
VALID_NEXT_ACTIONS = {
    "read_for_delta", "read_for_baseline", "read_for_concept",
    "mark_weak", "reject",
}
VALID_INGEST_STATUSES = {"archived_only"}

VALID_SOURCE_ORIGINS = {
    "primary_official", "official_repost",
    "media_reprint", "secondary_summary",
}
VALID_CONCEPT_MATCH_TYPES = {
    "direct_alias", "explicit_synonym", "upstream_component",
    "downstream_application", "adjacent_substitute",
    "inferred_only", "negative",
}
VALID_EVIDENCE_POLARITIES = {"positive", "adjacent", "negative", "historical"}
VALID_TIME_SCOPES = {"current", "historical", "planned", "exited", "unknown"}
VALID_FACT_TRACEABILITIES = {"all_facts_supported", "partial_support", "unsupported_claims"}

MEDIA_REPRINT_DOMAINS = {
    "stockstar.com", "zqrb.cn", "eastmoney.com", "10jqka.com",
    "hexun.com", "cls.cn", "163.com", "sina.com.cn", "sohu.com",
    "finance.sina", "finance.qq", "caixin.com", "21jingji.com",
    "yicai.com", "wallstreetcn.com", "jrj.com.cn",
}

SOURCE_LAYER_MAP = {
    "announcement":              {"L2"},
    "annual_report":             {"L2"},
    "semiannual_report":         {"L2"},
    "quarterly_report":          {"L2"},
    "prospectus":                {"L2"},
    "offering_circular":         {"L2"},
    "exchange_inquiry_reply":    {"L2"},
    "official_website_product":  {"L2"},
    "official_website_news":     {"L2", "L3"},
    "investor_relation_record":  {"L3"},
    "interactive_e":             {"L3"},
    "sse_e_interaction":         {"L3"},
    "official_wechat":           {"L4"},
    "authoritative_media":       {"L4"},
    "news":                      {"L4"},
    "industry_media":            {"L4"},
    "forwarded_content":         {"L4"},
    "other":                     {"L1", "L2", "L3", "L4"},
}

FORBIDDEN_ROLE_PATTERNS = [
    # 原有泛词
    r"相关公司", r"相关企业",
    r"产业链参与", r"产业链(?:上|中|下)游[的]?(?:公司|企业|厂商)?$",
    r"中游制造及提供商",
    r"参与者$",
    r"相关(?:上市)?公司",
    r"^(?:公司|企业|厂商|供应商|制造商|生产商)$",
    # 新增：营销/炒作泛词
    r"受益标的",
    r"布局企业",
    r"龙头",
    r"领先企业",
    r"先行者",
    r"重要玩家",
    r"平台型公司",
    r"生态伙伴",
    # 新增：模糊能力/涉足描述
    r"具备相关能力",
    r"涉足",
    r"相关业务布局",
    # 新增：将公司描述为"器件/组件"而非角色
    r"芯片/核心器件",
    r"核心器件",
    # 新增：裸产业链位置（无具体产品/业务）
    r"^上游材料企业$",
    r"^中游制造商$",
    r"^下游应用企业$",
    # 新增：裸行业公司（无具体业务）
    r"^芯片公司$",
    r"^材料公司$",
    r"^设备公司$",
]

LOW_CERTAINTY_KEYWORDS = [
    "拟投资", "规划", "框架协议", "战略合作",
    "可应用于", "正在布局", "关注相关技术",
]

REQUIRED_FIELDS = [
    "archive_id", "theme_term", "canonical_concept", "company", "code",
    "chain_layer", "role", "exposure_strength", "evidence_layer",
    "update_type", "fact_type", "fact_status", "confidence",
    "source_type", "title", "publish_date", "fetched_at",
    "url", "quoted_text", "ingest_status", "review_status",
    "suggested_next_action",
]


def check_record(rec: dict, index: int) -> list:
    """对单条记录执行全部约束检查，返回错误列表。"""
    errors = []
    aid = rec.get("archive_id", f"#L{index}")
    prefix = f"[{aid}]"

    def err(msg):
        errors.append(f"{prefix} {msg}")

    # ── 必填字段 ──
    for field in REQUIRED_FIELDS:
        val = rec.get(field)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            err(f"缺少必填字段: {field}")

    # ── 枚举值 ──
    field_checks = [
        ("chain_layer", VALID_CHAIN_LAYERS),
        ("exposure_strength", VALID_EXPOSURE_STRENGTHS),
        ("evidence_layer", VALID_EVIDENCE_LAYERS),
        ("update_type", VALID_UPDATE_TYPES),
        ("fact_type", VALID_FACT_TYPES),
        ("fact_status", VALID_FACT_STATUSES),
        ("confidence", VALID_CONFIDENCE),
        ("source_type", VALID_SOURCE_TYPES),
        ("ingest_status", VALID_INGEST_STATUSES),
        ("review_status", {"unreviewed", "reviewed", "approved", "rejected", "duplicate", "needs_edit"}),
        ("suggested_next_action", VALID_NEXT_ACTIONS),
        ("source_origin", VALID_SOURCE_ORIGINS),
        ("concept_match_type", VALID_CONCEPT_MATCH_TYPES),
        ("evidence_polarity", VALID_EVIDENCE_POLARITIES),
        ("time_scope", VALID_TIME_SCOPES),
        ("fact_traceability", VALID_FACT_TRACEABILITIES),
    ]
    for field, valid_set in field_checks:
        val = rec.get(field)
        if val and val not in valid_set:
            err(f"{field} 非法值: '{val}'")

    # ── not_applied 必须为 true ──
    na = rec.get("not_applied")
    if na is None or na is False or na == "false":
        err(f"not_applied 必须为 true（当前: {na}）")

    # ── publish_date 格式 ──
    pd = rec.get("publish_date", "")
    if pd and not re.match(r"^\d{4}-\d{2}-\d{2}$", pd):
        err(f"publish_date 格式错误: '{pd}'")
    elif pd:
        try:
            datetime.strptime(pd, "%Y-%m-%d")
        except ValueError:
            err(f"publish_date 不是合法日期: '{pd}'")

    # ── fetched_at 格式 ──
    fa = rec.get("fetched_at", "")
    if fa and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$", fa):
        err(f"fetched_at 格式异常: '{fa}'")

    # ── URL 校验（有 raw_path 时豁免）──
    url = rec.get("url", "")
    raw_path = rec.get("raw_path", "")
    if url and not raw_path:
        if not url.startswith("https://"):
            if url.startswith("http://"):
                err(f"url 必须使用 HTTPS: '{url}'")
            else:
                err(f"url 必须以 https:// 开头: '{url}'")

    # ── source_type ↔ evidence_layer ──
    st = rec.get("source_type", "")
    el = rec.get("evidence_layer", "")
    allowed = SOURCE_LAYER_MAP.get(st, set())
    if st and el and allowed and el not in allowed:
        err(f"source_type='{st}' 不允许 evidence_layer={el}，允许值: {sorted(allowed)}")

    # ── L4 不允许 baseline/hard_delta ──
    ut = rec.get("update_type", "")
    if el == "L4" and ut in ("baseline", "hard_delta"):
        err(f"evidence_layer=L4 不允许 update_type='{ut}'")

    # ── Hard Rule 1: source_origin != primary_official 限制 ──
    so = rec.get("source_origin")
    st = rec.get("source_type", "")
    raw_path = rec.get("raw_path", "")
    is_baseline_or_hard = ut in ("baseline", "hard_delta")
    if so and so != "primary_official":
        if st in ("annual_report", "prospectus", "announcement") and not raw_path:
            err(f"source_origin='{so}' 时 source_type='{st}' 必须提供 raw_path（当前来源非官方原始文件）")
        if is_baseline_or_hard:
            err(f"source_origin='{so}' 不得用于 {ut}（source_origin 必须为 primary_official）")

    # ── Hard Rule 2: concept_match_type 限制 ──
    cmt = rec.get("concept_match_type")
    if cmt in ("inferred_only", "adjacent_substitute", "negative") and is_baseline_or_hard:
        err(f"concept_match_type='{cmt}' 不得用于 {ut}")

    # ── Hard Rule 3: evidence_polarity 限制 ──
    ep = rec.get("evidence_polarity")
    if ep in ("adjacent", "negative", "historical") and is_baseline_or_hard:
        err(f"evidence_polarity='{ep}' 不得用于 {ut}")

    # ── Hard Rule 4: time_scope 限制 ──
    ts = rec.get("time_scope")
    if ts in ("historical", "exited", "planned") and is_baseline_or_hard:
        err(f"time_scope='{ts}' 不得用于 {ut}")

    # ── Hard Rule 5: fact_traceability 限制（只对 baseline/hard_delta 强制）──
    ft = rec.get("fact_traceability")
    if ft and ft != "all_facts_supported" and ut in ("baseline", "hard_delta"):
        err(f"fact_traceability='{ft}' 时不得标 {ut}，或必须降级为 review_candidate")

    # ── Hard Rule 8: URL 域名检测 ──
    if so == "primary_official" and url:
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc.lower()
            for media_domain in MEDIA_REPRINT_DOMAINS:
                if media_domain in domain:
                    if not raw_path:
                        err(f"URL 域名 '{domain}' 为媒体转载平台（{media_domain}），source_origin 不应为 primary_official"
                            f"（无 raw_path 时无法独立验证来源真实性）")
                    break
        except Exception:
            pass

    # ── Hard Rule 9: 产品页无发布日期 ──
    if "product" in st and pd and fa:
        pub_date_str = pd
        today_str = fa[:10]
        if pub_date_str == today_str:
            uncertainty = rec.get("uncertainty", "")
            if not uncertainty or "发布日期" not in uncertainty:
                err(f"产品页（{st}）publish_date 使用抓取日期，但 uncertainty 未标注")

    # ── source_type=other 不允许 baseline/hard_delta ──
    if st == "other" and ut in ("baseline", "hard_delta"):
        err(f"source_type='other' 不能与 update_type='{ut}' 共存（other 来源不确定，不得用作 baseline/hard_delta）")

    # ── graph_only / exposure_only 冲突 ──
    go = rec.get("graph_only", False)
    eo = rec.get("exposure_only", False)
    if go and ut in ("baseline", "hard_delta"):
        err(f"graph_only=true 不能与 update_type='{ut}' 共存")
    if eo and ut in ("baseline", "hard_delta"):
        err(f"exposure_only=true 不能与 update_type='{ut}' 共存")

    # ── core 必须 L2 ──
    es = rec.get("exposure_strength", "")
    if es == "core" and el != "L2":
        err(f"exposure_strength=core 必须对应 evidence_layer=L2，当前={el}")

    # ── baseline/hard_delta 必须 L2 ──
    if ut in ("baseline", "hard_delta") and el != "L2":
        err(f"update_type='{ut}' 必须对应 evidence_layer=L2，当前={el}")

    # ── role 泛词 ──
    role = rec.get("role", "")
    for pattern in FORBIDDEN_ROLE_PATTERNS:
        if re.search(pattern, role):
            err(f"role 含禁止泛词（匹配 '{pattern}'）: '{role}'")
            break

    # ── facts 非空（除非 reject） ──
    facts = rec.get("extracted_facts", [])
    if ut != "reject" and (not facts or (isinstance(facts, list) and len(facts) == 0)):
        err("extracted_facts 为空且 update_type 不是 reject")

    # ── 低确定性关键词检查 ──
    quoted = rec.get("quoted_text", "")
    fs = rec.get("fact_status", "")
    if quoted:
        for kw in LOW_CERTAINTY_KEYWORDS:
            if kw in quoted and fs not in ("planned", "framework", "rumored"):
                err(f"引文含低确定性关键词 '{kw}' 但 fact_status='{fs}'")
                break

    return errors


def check_directory(disclosures_dir: Path) -> list:
    """检查目录是否可达。"""
    issues = []
    try:
        disclosures_dir.mkdir(parents=True, exist_ok=True)
        test_file = disclosures_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        print(f"[OK]  目录可达且可写: {disclosures_dir}")
    except (OSError, PermissionError) as e:
        issues.append(f"目录不可写: {e}")
        print(f"[ERR] 目录问题: {e}")
    return issues


def check_manifest(disclosures_dir: Path) -> tuple:
    """加载 manifest.jsonl，返回 (issues, records)。"""
    issues = []
    manifest_path = disclosures_dir / "manifest.jsonl"
    if not manifest_path.exists():
        print(f"[WARN] manifest.jsonl 不存在（首次使用会自动创建）: {manifest_path}")
        return issues, []

    records = []
    with manifest_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                issues.append(f"manifest.jsonl 第 {i} 行解析失败: {e}")

    print(f"[OK]  manifest.jsonl: {len(records)} 条记录")
    return issues, records


def print_stats(records: list):
    """打印分布统计。"""
    if not records:
        print()
        print("─" * 50)
        print("统计: 无记录")
        return

    layer_counter = Counter(r.get("evidence_layer") for r in records)
    update_counter = Counter(r.get("update_type") for r in records)
    exposure_counter = Counter(r.get("exposure_strength") for r in records)
    chain_counter = Counter(r.get("chain_layer") for r in records)
    source_counter = Counter(r.get("source_type") for r in records)
    graph_only_count = sum(1 for r in records if r.get("graph_only"))
    exposure_only_count = sum(1 for r in records if r.get("exposure_only"))
    by_status = Counter(r.get("ingest_status") for r in records)

    print()
    print("─" * 50)
    print(f"归档统计 ({len(records)} 条)")
    print()
    print(f"  ingest_status:     {dict(by_status)}")
    print(f"  evidence_layer:    {dict(layer_counter)}")
    print(f"  update_type:       {dict(update_counter)}")
    print(f"  exposure_strength: {dict(exposure_counter)}")
    print(f"  chain_layer:       {dict(chain_counter)}")
    print(f"  source_type:       {dict(source_counter)}")
    print(f"  graph_only:        {graph_only_count}")
    print(f"  exposure_only:     {exposure_only_count}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="检查 disclosure archive 归档健康状态")
    parser.add_argument("--disclosures-dir", default=str(DEFAULT_DISCLOSURES_DIR))
    args = parser.parse_args()

    disclosures_dir = Path(args.disclosures_dir)

    print("=" * 50)
    print("Disclosure Archive — 健康检查")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"目录:     {disclosures_dir}")
    print("=" * 50)
    print()

    # 1. 目录
    dir_issues = check_directory(disclosures_dir)

    # 2. manifest
    manifest_issues, records = check_manifest(disclosures_dir)

    all_issues = dir_issues + manifest_issues

    # 3. 逐条检查
    record_issues = []
    for i, rec in enumerate(records):
        record_issues.extend(check_record(rec, i + 1))

    if record_issues:
        print(f"\n[ERR] 约束违反: {len(record_issues)} 个问题")
        for issue in record_issues:
            print(f"  - {issue}")
    else:
        print(f"[OK]  约束检查: 全部 {len(records)} 条记录通过")

    all_issues.extend(record_issues)

    # 4. 分布统计
    print_stats(records)

    print()
    print("─" * 50)
    if all_issues:
        print(f"总计 {len(all_issues)} 个问题。")
        sys.exit(1)
    else:
        print("全部检查通过。")
        sys.exit(0)


if __name__ == "__main__":
    main()
