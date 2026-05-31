#!/usr/bin/env python3
"""
Disclosure Archive — 归档单条公司披露证据到 wiki/raw/disclosures/。

用法:
  python3 archive.py \\
    --theme-term "感光膜" \\
    --canonical-concept "感光干膜" \\
    --company "容大感光" \\
    --code "300576" \\
    --chain-layer midstream_manufacturing \\
    --role "PCB干膜光刻胶供应商" \\
    --exposure-strength related \\
    --evidence-layer L2 \\
    --update-type hard_delta \\
    --fact-type product_capability \\
    --fact-status realized \\
    --confidence high \\
    --source-type announcement \\
    --title "关于公司感光干膜产品通过客户认证的公告" \\
    --publish-date 2026-05-20 \\
    --url "https://example.com" \\
    --quoted-text "公司感光干膜产品已通过XX客户认证，具备量产能力。" \\
    --facts "事实1" "事实2"

注意: 本脚本只负责归档，不修改 wiki/entities, wiki/concepts, wiki/relations。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 路径 ──────────────────────────────────────────
SKILL_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SKILL_DIR.parent
DEFAULT_VAULT = Path.home() / "Desktop" / "c c" / "知识库" / "wiki"
DEFAULT_DISCLOSURES_DIR = DEFAULT_VAULT / "raw" / "disclosures"

TZ = timezone(timedelta(hours=8))

# ── 合法值集合 ────────────────────────────────────
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

# 媒体转载域名列表（用于 source_origin 判断）
MEDIA_REPRINT_DOMAINS = {
    "stockstar.com", "zqrb.cn", "eastmoney.com", "10jqka.com",
    "hexun.com", "cls.cn", "163.com", "sina.com.cn", "sohu.com",
    " finance.sina", "finance.qq", "caixin.com", "21jingji.com",
    "yicai.com", "wallstreetcn.com", "jrj.com.cn",
}

# source_type → 允许的 evidence_layer
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
    "other":                     {"L1", "L2", "L3", "L4"},  # 通配
}

# 禁止用作 role 的泛词
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

# 低确定性关键词
LOW_CERTAINTY_KEYWORDS = [
    "拟投资", "规划", "框架协议", "战略合作",
    "可应用于", "正在布局", "关注相关技术",
]


def slugify(text: str) -> str:
    """生成文件名友好的 slug。"""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text.strip())
    return text[:80]


def validate_role(role: str) -> list:
    """检查 role 是否包含禁止的泛词，返回错误列表（仅报告第一个匹配）。"""
    errors = []
    for pattern in FORBIDDEN_ROLE_PATTERNS:
        if re.search(pattern, role):
            errors.append(f"role 含禁止泛词（匹配 '{pattern}'）: '{role}'。必须使用具体角色描述，如 'PCB干膜光刻胶供应商'。")
            break
    return errors


def validate_fields(args: argparse.Namespace) -> list:
    """校验所有字段，返回错误列表。"""
    errors = []

    # ── 必填字段 ──
    required = [
        "theme_term", "canonical_concept", "company", "code",
        "chain_layer", "role", "exposure_strength", "evidence_layer",
        "update_type", "fact_type", "fact_status", "confidence",
        "source_type", "title", "publish_date", "url", "quoted_text",
    ]
    for field in required:
        val = getattr(args, field, None)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            errors.append(f"缺少必填字段: --{field.replace('_', '-')}")

    if errors:
        return errors  # 先返回缺字段，避免后面空值报错

    # ── 新字段枚举值校验 ──
    so = args.source_origin
    cmt = args.concept_match_type
    ep = args.evidence_polarity
    ts = args.time_scope
    ft = args.fact_traceability

    if so and so not in VALID_SOURCE_ORIGINS:
        errors.append(f"source_origin 非法值: {so}")
    if cmt and cmt not in VALID_CONCEPT_MATCH_TYPES:
        errors.append(f"concept_match_type 非法值: {cmt}")
    if ep and ep not in VALID_EVIDENCE_POLARITIES:
        errors.append(f"evidence_polarity 非法值: {ep}")
    if ts and ts not in VALID_TIME_SCOPES:
        errors.append(f"time_scope 非法值: {ts}")
    if ft and ft not in VALID_FACT_TRACEABILITIES:
        errors.append(f"fact_traceability 非法值: {ft}")

    # ── Hard Rules ──

    ut = args.update_type
    el = args.evidence_layer
    st = args.source_type
    is_baseline_or_hard = ut in ("baseline", "hard_delta")

    # Rule 1: source_origin != primary_official → 限制
    if so and so != "primary_official":
        if st in ("annual_report", "prospectus", "announcement") and not args.raw_path:
            errors.append(
                f"source_origin='{so}' 时 source_type='{st}' 必须提供 raw_path"
                f"（当前来源非官方原始文件）"
            )
        if is_baseline_or_hard:
            errors.append(
                f"source_origin='{so}' 不得用于 {ut}"
                f"（source_origin 必须为 primary_official）"
            )

    # Rule 2: concept_match_type 限制
    if cmt in ("inferred_only", "adjacent_substitute", "negative") and is_baseline_or_hard:
        errors.append(
            f"concept_match_type='{cmt}' 不得用于 {ut}"
        )

    # Rule 3: evidence_polarity 限制
    if ep in ("adjacent", "negative", "historical") and is_baseline_or_hard:
        errors.append(
            f"evidence_polarity='{ep}' 不得用于 {ut}"
        )

    # Rule 4: time_scope 限制
    if ts in ("historical", "exited", "planned") and is_baseline_or_hard:
        errors.append(
            f"time_scope='{ts}' 不得用于 {ut}"
        )

    # Rule 5: fact_traceability 限制（只对 baseline/hard_delta 强制）
    if ft and ft != "all_facts_supported" and ut in ("baseline", "hard_delta"):
        errors.append(
            f"fact_traceability='{ft}' 时不得标 {ut}，或必须降级为 review_candidate"
        )

    # Rule 8: URL 域名检测 → source_origin 提示
    if so == "primary_official" and args.url:
        from urllib.parse import urlparse
        try:
            domain = urlparse(args.url).netloc.lower()
            for media_domain in MEDIA_REPRINT_DOMAINS:
                if media_domain in domain:
                    if not args.raw_path:
                        errors.append(
                            f"URL 域名 '{domain}' 为媒体转载平台（{media_domain}），"
                            f"source_origin 不应为 primary_official"
                            f"（无 raw_path 时无法独立验证来源真实性）"
                        )
                    break
        except Exception:
            pass

    # Rule 9: 产品页无发布日期
    if "product" in st and args.publish_date == datetime.now(TZ).strftime("%Y-%m-%d"):
        if not args.uncertainty or "发布日期" not in args.uncertainty:
            errors.append(
                f"产品页（{st}）publish_date 使用抓取日期时，"
                f"必须在 uncertainty 中标注"
            )

    # ── 枚举值校验 ──
    if args.chain_layer not in VALID_CHAIN_LAYERS:
        errors.append(f"chain_layer 非法值: {args.chain_layer}，合法值: {sorted(VALID_CHAIN_LAYERS)}")
    if args.exposure_strength not in VALID_EXPOSURE_STRENGTHS:
        errors.append(f"exposure_strength 非法值: {args.exposure_strength}")
    if args.evidence_layer not in VALID_EVIDENCE_LAYERS:
        errors.append(f"evidence_layer 非法值: {args.evidence_layer}")
    if args.update_type not in VALID_UPDATE_TYPES:
        errors.append(f"update_type 非法值: {args.update_type}")
    if args.fact_type not in VALID_FACT_TYPES:
        errors.append(f"fact_type 非法值: {args.fact_type}")
    if args.fact_status not in VALID_FACT_STATUSES:
        errors.append(f"fact_status 非法值: {args.fact_status}")
    if args.confidence not in VALID_CONFIDENCE:
        errors.append(f"confidence 非法值: {args.confidence}")
    if args.source_type not in VALID_SOURCE_TYPES:
        errors.append(f"source_type 非法值: {args.source_type}")
    if args.suggested_next_action not in VALID_NEXT_ACTIONS:
        errors.append(f"suggested_next_action 非法值: {args.suggested_next_action}")

    # ── Role 泛词检查（阻断）──
    errors.extend(validate_role(args.role))

    # ── Facts 非空检查 ──
    if args.update_type != "reject" and (not args.facts or len(args.facts) == 0):
        errors.append("--facts 必须至少提供一条可验证事实（除非 update_type=reject）")

    # ── publish_date 格式 ──
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", args.publish_date):
        errors.append(f"publish_date 格式错误: '{args.publish_date}'，应为 YYYY-MM-DD")
    else:
        try:
            datetime.strptime(args.publish_date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"publish_date 不是合法日期: '{args.publish_date}'")

    # ── URL 校验 ──
    if args.raw_path:
        # 有本地文件时 url 可选
        pass
    elif not args.url.startswith("http://") and not args.url.startswith("https://"):
        errors.append(f"url 必须以 http:// 或 https:// 开头（当前: '{args.url}'）")
    elif args.url.startswith("http://"):
        errors.append(f"url 必须使用 HTTPS: '{args.url}'")

    # ── source_type ↔ evidence_layer 一致性 ──
    allowed_layers = SOURCE_LAYER_MAP.get(args.source_type, set())
    if allowed_layers and args.evidence_layer not in allowed_layers:
        errors.append(
            f"source_type='{args.source_type}' 不允许 evidence_layer={args.evidence_layer}"
            f"，允许值: {sorted(allowed_layers)}"
        )

    # ── L4 不允许 baseline/hard_delta ──
    if args.evidence_layer == "L4" and args.update_type in ("baseline", "hard_delta"):
        errors.append(f"evidence_layer=L4 不允许 update_type='{args.update_type}'（L4 来源不能作为 baseline/hard_delta）")

    # ── graph_only / exposure_only 冲突 ──
    if args.graph_only and args.update_type in ("baseline", "hard_delta"):
        errors.append(f"graph_only=true 不能与 update_type='{args.update_type}' 共存（graph_only 的证据不足以写入 baseline/hard_delta）")
    if args.exposure_only and args.update_type in ("baseline", "hard_delta"):
        errors.append(f"exposure_only=true 不能与 update_type='{args.update_type}' 共存（exposure_only 的证据不足以写入 baseline/hard_delta）")

    # ── exposure_strength=core 必须 L2 ──
    if args.exposure_strength == "core" and args.evidence_layer != "L2":
        errors.append(f"exposure_strength=core 必须对应 evidence_layer=L2，当前={args.evidence_layer}")

    # ── update_type=baseline/hard_delta 必须 L2 ──
    if args.update_type in ("baseline", "hard_delta") and args.evidence_layer != "L2":
        errors.append(f"update_type='{args.update_type}' 必须对应 evidence_layer=L2，当前={args.evidence_layer}")

    # ── 低确定性关键词检查 ──
    if args.quoted_text:
        for kw in LOW_CERTAINTY_KEYWORDS:
            if kw in args.quoted_text and args.fact_status not in ("planned", "framework", "rumored"):
                errors.append(
                    f"引文含低确定性关键词 '{kw}'，但 fact_status='{args.fact_status}'"
                    f"，应为 planned/framework/rumored"
                )
                break

    return errors


def generate_archive_id(disclosures_dir: Path) -> str:
    """生成 archive_id: disc-YYYYMMDD-NNNN"""
    today = datetime.now(TZ).strftime("%Y%m%d")
    manifest_path = disclosures_dir / "manifest.jsonl"
    seq = 0
    if manifest_path.exists():
        try:
            for line in manifest_path.read_text().strip().splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                aid = entry.get("archive_id", "")
                if aid.startswith(f"disc-{today}"):
                    n = int(aid.split("-")[-1])
                    seq = max(seq, n)
        except (json.JSONDecodeError, OSError, IndexError, ValueError):
            pass
    return f"disc-{today}-{seq + 1:04d}"


def build_yaml_value(key: str, value) -> str:
    """将 Python 值转成 YAML frontmatter 行内值。"""
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "null"
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    # string — 用双引号包裹（中文/特殊字符安全）
    return json.dumps(str(value), ensure_ascii=False)


def build_markdown_frontmatter(data: dict) -> str:
    """生成 YAML frontmatter。"""
    # 定义字段顺序
    keys = [
        "archive_id", "batch_id", "theme_term", "canonical_concept", "aliases",
        "company", "code", "chain_layer", "role",
        "exposure_strength", "evidence_layer", "update_type",
        "fact_type", "fact_status", "graph_only", "exposure_only",
        "confidence", "source_type",
        "title", "publish_date", "fetched_at", "url",
        "quoted_text", "extracted_facts",
        "uncertainty", "raw_path",
        "ingest_status", "review_status", "not_applied",
        "applied_payload", "review_notes",
        "source_origin", "concept_match_type",
        "evidence_polarity", "time_scope", "fact_traceability",
        "duplicate_of", "suggested_next_action",
    ]
    lines = ["---"]
    for k in keys:
        if k in data:
            lines.append(f"{k}: {build_yaml_value(k, data[k])}")
    lines.append("---")
    return "\n".join(lines)


def build_markdown_body(data: dict) -> str:
    """生成 Markdown 正文。"""
    facts = data.get("extracted_facts", [])
    quoted = data.get("quoted_text", "")
    uncertainty = data.get("uncertainty", "")
    suggested = data.get("suggested_next_action", "")
    is_reject = data.get("update_type") == "reject"

    body = f"""# {data['title']}

## 原始来源
- 题材：{data['theme_term']}
- 规范概念：{data['canonical_concept']}
- 公司：{data['company']}（{data['code']}）
- 产业链层：{data['chain_layer']}
- 公司角色：{data['role']}
- 来源类型：{data['source_type']}
- URL：{data['url']}
- 发布日期：{data['publish_date']}
- 抓取时间：{data['fetched_at']}

## 可验证事实
"""
    if facts:
        for fact in facts:
            body += f"- {fact}\n"
    else:
        body += "（无 — update_type=reject）\n"

    body += f"""
## 原文摘录
> {quoted}

## 主题关联
- 题材：{data['theme_term']}
- 规范概念：{data['canonical_concept']}
- 产业链位置：{data['chain_layer']}
- 公司角色：{data['role']}
- 暴露强度：{data['exposure_strength']}
- 证据分层：{data['evidence_layer']}
- 证据类型：{data['update_type']}

## 证据质量
- graph_only：{str(data.get('graph_only', False)).lower()}
- exposure_only：{str(data.get('exposure_only', False)).lower()}
- 确定性标注：{data['fact_status']}
"""
    if uncertainty:
        body += f"- 不确定性说明：{uncertainty}\n"

    if is_reject:
        body += "\n## 拒绝原因\n（此条标记为 reject，不进入后续入库流程。）\n"
    else:
        body += f"""
## 后续入库建议
- 建议进入 entity-delta：{"是" if data["update_type"] == "hard_delta" and data["evidence_layer"] in ("L2", "L3") else "待审核" if data["update_type"] == "review_candidate" else "否"}
- 建议进入 baseline：{"是" if data["update_type"] == "baseline" and data["evidence_layer"] == "L2" else "待审核" if data["update_type"] == "review_candidate" else "否"}
- 建议仅作为 weak_signal：{"是" if data["update_type"] == "weak_signal" else "否"}
- 需要人工复核：{"是" if data["evidence_layer"] == "L3" else "否"}
- 后续操作：{suggested}
"""
    return body


def main():
    parser = argparse.ArgumentParser(description="归档单条公司披露证据到 wiki/raw/disclosures/")
    parser.add_argument("--theme-term", required=True)
    parser.add_argument("--canonical-concept", required=True)
    parser.add_argument("--aliases", nargs="*", default=[])
    parser.add_argument("--company", required=True)
    parser.add_argument("--code", required=True)
    parser.add_argument("--chain-layer", required=True, choices=sorted(VALID_CHAIN_LAYERS))
    parser.add_argument("--role", required=True)
    parser.add_argument("--exposure-strength", required=True, choices=sorted(VALID_EXPOSURE_STRENGTHS))
    parser.add_argument("--evidence-layer", required=True, choices=sorted(VALID_EVIDENCE_LAYERS))
    parser.add_argument("--update-type", required=True, choices=sorted(VALID_UPDATE_TYPES))
    parser.add_argument("--fact-type", required=True, choices=sorted(VALID_FACT_TYPES))
    parser.add_argument("--fact-status", required=True, choices=sorted(VALID_FACT_STATUSES))
    parser.add_argument("--graph-only", action="store_true", default=False)
    parser.add_argument("--exposure-only", action="store_true", default=False)
    parser.add_argument("--confidence", required=True, choices=sorted(VALID_CONFIDENCE))
    parser.add_argument("--source-type", required=True, choices=sorted(VALID_SOURCE_TYPES))
    parser.add_argument("--title", required=True)
    parser.add_argument("--publish-date", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--quoted-text", required=True)
    parser.add_argument("--facts", nargs="*", default=[])
    parser.add_argument("--uncertainty", default="")
    parser.add_argument("--raw-path", default="")
    parser.add_argument("--suggested-next-action", default="read_for_delta",
                        choices=sorted(VALID_NEXT_ACTIONS))
    parser.add_argument("--duplicate-of", default="")
    parser.add_argument("--batch-id", default="",
                        help="批次 ID，格式 batch-YYYYMMDD-NNNN")
    parser.add_argument("--source-origin", default="",
                        choices=sorted(VALID_SOURCE_ORIGINS),
                        help="来源原始性分类")
    parser.add_argument("--concept-match-type", default="",
                        choices=sorted(VALID_CONCEPT_MATCH_TYPES),
                        help="概念匹配类型")
    parser.add_argument("--evidence-polarity", default="",
                        choices=sorted(VALID_EVIDENCE_POLARITIES),
                        help="证据极性")
    parser.add_argument("--time-scope", default="",
                        choices=sorted(VALID_TIME_SCOPES),
                        help="时间跨度")
    parser.add_argument("--fact-traceability", default="",
                        choices=sorted(VALID_FACT_TRACEABILITIES),
                        help="事实可追溯性")
    parser.add_argument("--disclosures-dir", default=str(DEFAULT_DISCLOSURES_DIR))
    parser.add_argument("--dry-run", action="store_true", help="只校验不写入")
    args = parser.parse_args()

    # 空字符串转 None
    if args.duplicate_of == "":
        args.duplicate_of = None
    if args.uncertainty == "":
        args.uncertainty = None
    if args.batch_id == "":
        args.batch_id = None
    if args.source_origin == "":
        args.source_origin = None
    if args.concept_match_type == "":
        args.concept_match_type = None
    if args.evidence_polarity == "":
        args.evidence_polarity = None
    if args.time_scope == "":
        args.time_scope = None
    if args.fact_traceability == "":
        args.fact_traceability = None

    # ── 校验 ──
    errors = validate_fields(args)
    if errors:
        print("字段校验失败，拒绝写入:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    # ── 准备数据 ──
    disclosures_dir = Path(args.disclosures_dir)
    manifest_path = disclosures_dir / "manifest.jsonl"
    now_iso = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    archive_id = generate_archive_id(disclosures_dir)
    pub_date = args.publish_date
    date_dir_name = pub_date

    data = {
        "archive_id": archive_id,
        "batch_id": args.batch_id,
        "theme_term": args.theme_term,
        "canonical_concept": args.canonical_concept,
        "aliases": args.aliases,
        "company": args.company,
        "code": args.code,
        "chain_layer": args.chain_layer,
        "role": args.role,
        "exposure_strength": args.exposure_strength,
        "evidence_layer": args.evidence_layer,
        "update_type": args.update_type,
        "fact_type": args.fact_type,
        "fact_status": args.fact_status,
        "graph_only": args.graph_only,
        "exposure_only": args.exposure_only,
        "confidence": args.confidence,
        "source_type": args.source_type,
        "title": args.title,
        "publish_date": pub_date,
        "fetched_at": now_iso,
        "url": args.url,
        "quoted_text": args.quoted_text,
        "extracted_facts": args.facts,
        "uncertainty": args.uncertainty,
        "raw_path": args.raw_path or None,
        "ingest_status": "archived_only",
        "review_status": "unreviewed",
        "not_applied": True,
        "applied_payload": None,
        "review_notes": None,
        "source_origin": args.source_origin,
        "concept_match_type": args.concept_match_type,
        "evidence_polarity": args.evidence_polarity,
        "time_scope": args.time_scope,
        "fact_traceability": args.fact_traceability,
        "duplicate_of": args.duplicate_of,
        "suggested_next_action": args.suggested_next_action,
    }

    # ── 文件名 ──
    slug = slugify(f"{args.company}_{args.code}_{args.source_type}_{args.title}")
    filename = f"{slugify(args.theme_term)}_{slug}.md"
    date_dir = disclosures_dir / date_dir_name
    md_path = date_dir / filename

    if args.dry_run:
        print(f"[DRY RUN] 将写入: {md_path}")
        print(f"[DRY RUN] archive_id: {archive_id}")
        print(f"[DRY RUN] manifest: {manifest_path}")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    # ── 创建目录 ──
    date_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = date_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    # ── 去重检查 ──
    if manifest_path.exists():
        for line in manifest_path.read_text().strip().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if (entry.get("company") == args.company
                        and entry.get("url") == args.url
                        and entry.get("theme_term") == args.theme_term
                        and entry.get("duplicate_of") is None):
                    print(f"[SKIP] 重复归档: archive_id={entry['archive_id']}, 公司={args.company}, URL={args.url}")
                    print("       如需强制归档，确认后手动编辑 manifest 或使用 --duplicate-of")
                    return
            except json.JSONDecodeError:
                continue

    # ── 写入 Markdown ──
    frontmatter = build_markdown_frontmatter(data)
    body = build_markdown_body(data)
    md_content = frontmatter + "\n" + body + "\n"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"[OK] 写入: {md_path}")

    # ── 追加 manifest.jsonl（含 extracted_facts 摘要）──
    manifest_entry = dict(data)
    manifest_entry["markdown_path"] = str(Path(date_dir_name) / filename)
    manifest_entry["raw_asset_path"] = f"{date_dir_name}/assets/" if args.raw_path else ""

    with manifest_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(manifest_entry, ensure_ascii=False) + "\n")
    print(f"[OK] 追加 manifest: {manifest_path}")

    # ── 质量摘要 ──
    print()
    print("─" * 50)
    print(f"归档完成: {archive_id}")
    if args.batch_id:
        print(f"  批次:      {args.batch_id}")
    print(f"  题材:      {args.theme_term}")
    print(f"  概念:      {args.canonical_concept}")
    print(f"  公司:      {args.company} ({args.code})")
    print(f"  角色:      {args.role}")
    print(f"  分层:      {args.evidence_layer} / {args.update_type}")
    print(f"  暴露强度:  {args.exposure_strength}")
    print(f"  确定性:    {args.fact_status}")
    print(f"  graph_only: {args.graph_only}, exposure_only: {args.exposure_only}")
    print(f"  事实数:    {len(args.facts)}")
    print(f"  后续操作:  {args.suggested_next_action}")


if __name__ == "__main__":
    main()
