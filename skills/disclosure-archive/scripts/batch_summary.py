#!/usr/bin/env python3
"""
Disclosure Archive — 批次摘要生成。

从 manifest.jsonl 中筛选指定 batch_id 的记录，输出 JSON 摘要到 batches/。
自动调用 check.py 并将结果纳入摘要。
"""
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAULT = Path.home() / "Desktop" / "c c" / "知识库" / "wiki"
DEFAULT_DISCLOSURES_DIR = DEFAULT_VAULT / "raw" / "disclosures"
TZ = timezone(timedelta(hours=8))

# 与 check.py/archive.py 保持一致的禁止 role 模式
FORBIDDEN_ROLE_PATTERNS = [
    r"相关公司", r"相关企业",
    r"产业链参与", r"产业链(?:上|中|下)游[的]?(?:公司|企业|厂商)?$",
    r"中游制造及提供商",
    r"参与者$",
    r"相关(?:上市)?公司",
    r"^(?:公司|企业|厂商|供应商|制造商|生产商)$",
    r"受益标的",
    r"布局企业",
    r"龙头",
    r"领先企业",
    r"先行者",
    r"重要玩家",
    r"平台型公司",
    r"生态伙伴",
    r"具备相关能力",
    r"涉足",
    r"相关业务布局",
    r"芯片/核心器件",
    r"核心器件",
    r"^上游材料企业$",
    r"^中游制造商$",
    r"^下游应用企业$",
    r"^芯片公司$",
    r"^材料公司$",
    r"^设备公司$",
]


def load_manifest(disclosures_dir: Path) -> list:
    manifest_path = disclosures_dir / "manifest.jsonl"
    if not manifest_path.exists():
        print(f"[ERR] manifest.jsonl 不存在: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    records = []
    with manifest_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] manifest 第 {i} 行解析失败: {e}", file=sys.stderr)
    return records


def run_check(disclosures_dir: Path) -> dict:
    check_script = SKILL_DIR / "scripts" / "check.py"
    try:
        result = subprocess.run(
            [sys.executable, str(check_script),
             "--disclosures-dir", str(disclosures_dir)],
            capture_output=True, text=True, timeout=30,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "status": "PASS" if result.returncode == 0 else "FAIL",
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "check.py timed out", "status": "TIMEOUT"}
    except FileNotFoundError:
        return {"exit_code": -1, "stdout": "", "stderr": "check.py not found", "status": "ERROR"}


def compute_batch_quality_score(records: list, check_result: dict,
                                skipped_count: int) -> tuple:
    """评估批次质量，返回 (batch_quality_score, blocking_issues, warnings)。

    PASS_STRONG: 检查通过，所有记录 source_origin=primary_official，无任何警告
    PASS_WITH_WARNINGS: 检查通过，仅有可容忍的小问题
    NEEDS_FIX: 检查通过但存在可恢复问题（不良 source_origin、禁止 role 模式等）
    FAIL: check.py 失败或存在阻塞性问题
    """
    blocking_issues = []
    warnings = []

    if not records:
        return "FAIL", ["批次无归档记录"], []

    # 逐条检查
    for r in records:
        aid = r.get("archive_id", "?")
        so = r.get("source_origin", "")
        ut = r.get("update_type", "")
        st = r.get("source_type", "")
        el = r.get("evidence_layer", "")
        cmt = r.get("concept_match_type", "")
        ep = r.get("evidence_polarity", "")
        ts = r.get("time_scope", "")
        ft = r.get("fact_traceability", "")
        role = r.get("role", "")
        raw_path = r.get("raw_path", "")
        url = r.get("url", "")

        # ── 阻塞性问题 ──

        # source_origin 非 primary_official + baseline/hard_delta
        if so != "primary_official" and ut in ("baseline", "hard_delta"):
            blocking_issues.append(
                f"[{aid}] source_origin='{so}' 但 update_type='{ut}'"
                f"（必须为 primary_official）"
            )

        # concept_match_type 不当
        if cmt in ("inferred_only", "adjacent_substitute", "negative") and ut in ("baseline", "hard_delta"):
            blocking_issues.append(
                f"[{aid}] concept_match_type='{cmt}' 不得用于 {ut}"
            )

        # evidence_polarity 不当
        if ep in ("adjacent", "negative", "historical") and ut in ("baseline", "hard_delta"):
            blocking_issues.append(
                f"[{aid}] evidence_polarity='{ep}' 不得用于 {ut}"
            )

        # time_scope 不当
        if ts in ("historical", "exited", "planned") and ut in ("baseline", "hard_delta"):
            blocking_issues.append(
                f"[{aid}] time_scope='{ts}' 不得用于 {ut}"
            )

        # fact_traceability 不足
        if ft and ft != "all_facts_supported" and ut in ("baseline", "hard_delta"):
            blocking_issues.append(
                f"[{aid}] fact_traceability='{ft}' 时不得标 {ut}"
            )

        # L4 + baseline/hard_delta
        if el == "L4" and ut in ("baseline", "hard_delta"):
            blocking_issues.append(
                f"[{aid}] evidence_layer=L4 不允许 update_type='{ut}'"
            )

        # graph_only/exposure_only + baseline/hard_delta
        if r.get("graph_only") and ut in ("baseline", "hard_delta"):
            blocking_issues.append(f"[{aid}] graph_only=true 不能与 update_type='{ut}' 共存")
        if r.get("exposure_only") and ut in ("baseline", "hard_delta"):
            blocking_issues.append(f"[{aid}] exposure_only=true 不能与 update_type='{ut}' 共存")

        # core 必须 L2
        if r.get("exposure_strength") == "core" and el != "L2":
            blocking_issues.append(
                f"[{aid}] exposure_strength=core 必须 L2，当前={el}"
            )

        # role 禁止泛词
        for pattern in FORBIDDEN_ROLE_PATTERNS:
            if re.search(pattern, role):
                blocking_issues.append(
                    f"[{aid}] role 含禁止泛词（匹配 '{pattern}'）: '{role}'"
                )
                break

        # source_type ↔ evidence_layer 不一致
        _source_layer_map = {
            "announcement": {"L2"}, "annual_report": {"L2"},
            "semiannual_report": {"L2"}, "quarterly_report": {"L2"},
            "prospectus": {"L2"}, "offering_circular": {"L2"},
            "exchange_inquiry_reply": {"L2"},
            "official_website_product": {"L2"},
            "official_website_news": {"L2", "L3"},
            "investor_relation_record": {"L3"},
            "interactive_e": {"L3"}, "sse_e_interaction": {"L3"},
            "official_wechat": {"L4"},
            "authoritative_media": {"L4"}, "news": {"L4"},
            "industry_media": {"L4"}, "forwarded_content": {"L4"},
            "other": {"L1", "L2", "L3", "L4"},
        }
        allowed = _source_layer_map.get(st, set())
        if st and el and allowed and el not in allowed:
            blocking_issues.append(
                f"[{aid}] source_type='{st}' 不允许 evidence_layer={el}"
            )

        # ── 警告（不阻塞）──

        # primary_official + 媒体域名 URL 但有 raw_path
        if so == "primary_official" and url and raw_path:
            from urllib.parse import urlparse
            try:
                domain = urlparse(url).netloc.lower()
                media_domains = {
                    "stockstar.com", "zqrb.cn", "eastmoney.com", "10jqka.com",
                    "hexun.com", "cls.cn", "163.com", "sina.com.cn", "sohu.com",
                    "finance.sina", "finance.qq", "caixin.com", "21jingji.com",
                    "yicai.com", "wallstreetcn.com", "jrj.com.cn",
                }
                for md in media_domains:
                    if md in domain:
                        warnings.append(
                            f"[{aid}] URL 为媒体转载平台（{domain}），"
                            f"虽有 raw_path 验证，建议优先使用官方原始 URL"
                        )
                        break
            except Exception:
                pass

        # 产品页 publish_date 使用抓取日期
        if "product" in st:
            pub_date = r.get("publish_date", "")
            fetched = r.get("fetched_at", "")
            if pub_date and fetched and pub_date == fetched[:10]:
                uncertainty = r.get("uncertainty", "")
                if not uncertainty or "发布日期" not in uncertainty:
                    warnings.append(
                        f"[{aid}] 产品页 publish_date 使用抓取日期，"
                        f"但 uncertainty 未标注"
                    )

        # source_origin 非 primary_official（非 baseline/hard_delta 时仅警告）
        if so not in ("primary_official", "") and ut not in ("baseline", "hard_delta"):
            warnings.append(
                f"[{aid}] source_origin='{so}'，建议优先使用 primary_official"
            )

    # ── 综合判定 ──

    if check_result and check_result.get("status") == "FAIL":
        return "FAIL", blocking_issues, warnings

    if blocking_issues:
        return "NEEDS_FIX", blocking_issues, warnings

    if warnings:
        return "PASS_WITH_WARNINGS", blocking_issues, warnings

    # 额外检查：所有记录是否均为 primary_official
    all_primary = all(
        r.get("source_origin") == "primary_official" for r in records
    )
    if not all_primary:
        non_primary = [
            r.get("archive_id") for r in records
            if r.get("source_origin") != "primary_official"
        ]
        warnings.append(
            f"部分记录 source_origin 非 primary_official: {non_primary}"
        )
        return "PASS_WITH_WARNINGS", [], warnings

    return "PASS_STRONG", [], []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成 disclosure archive 批次摘要")
    parser.add_argument("--batch-id", required=True, help="批次 ID，如 batch-20260527-0002")
    parser.add_argument("--disclosures-dir", default=str(DEFAULT_DISCLOSURES_DIR))
    parser.add_argument("--skip-check", action="store_true",
                        help="跳过 check.py 调用（节省时间）")
    parser.add_argument("--skipped-count", type=int, default=0,
                        help="本批次跳过的记录数")
    parser.add_argument("--failed-count", type=int, default=0,
                        help="本批次失败/出错的记录数")
    parser.add_argument("--skipped-reasons", nargs="*", default=[],
                        help="跳过原因列表（每条一句）")
    args = parser.parse_args()

    bid = args.batch_id
    disclosures_dir = Path(args.disclosures_dir)
    batches_dir = disclosures_dir / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    all_records = load_manifest(disclosures_dir)
    batch_records = [r for r in all_records if r.get("batch_id") == bid]

    if not batch_records:
        print(f"[ERR] 在 manifest 中未找到 batch_id='{bid}' 的记录", file=sys.stderr)
        sys.exit(1)

    # ── 统计 ──
    theme_terms = sorted(set(r.get("theme_term", "") for r in batch_records))
    concepts = sorted(set(r.get("canonical_concept", "") for r in batch_records))
    aliases_set = set()
    for r in batch_records:
        a = r.get("aliases") or []
        if isinstance(a, list):
            aliases_set.update(a)
    aliases_sorted = sorted(aliases_set)
    companies = sorted(set(r.get("company", "") for r in batch_records))
    codes = sorted(set(r.get("code", "") for r in batch_records))
    layer_counter = Counter(r.get("evidence_layer") for r in batch_records)
    update_counter = Counter(r.get("update_type") for r in batch_records)
    source_counter = Counter(r.get("source_type") for r in batch_records)
    exposure_counter = Counter(r.get("exposure_strength") for r in batch_records)
    chain_counter = Counter(r.get("chain_layer") for r in batch_records)
    graph_only_count = sum(1 for r in batch_records if r.get("graph_only"))
    exposure_only_count = sum(1 for r in batch_records if r.get("exposure_only"))
    not_applied = all(r.get("not_applied") for r in batch_records if "not_applied" in r)

    # ── 记录摘要 ──
    record_summaries = []
    for r in batch_records:
        record_summaries.append({
            "archive_id": r.get("archive_id"),
            "company": r.get("company"),
            "code": r.get("code"),
            "chain_layer": r.get("chain_layer"),
            "role": r.get("role"),
            "evidence_layer": r.get("evidence_layer"),
            "update_type": r.get("update_type"),
            "exposure_strength": r.get("exposure_strength"),
            "source_type": r.get("source_type"),
            "source_origin": r.get("source_origin"),
            "concept_match_type": r.get("concept_match_type"),
            "evidence_polarity": r.get("evidence_polarity"),
            "time_scope": r.get("time_scope"),
            "fact_traceability": r.get("fact_traceability"),
            "title": r.get("title"),
            "url": r.get("url"),
        })

    # ── check.py ──
    check_result = None if args.skip_check else run_check(disclosures_dir)

    # ── next_review_suggestion ──
    if update_counter.get("hard_delta", 0) > 0:
        review_suggestion = "建议优先审核 hard_delta 条目"
    elif update_counter.get("review_candidate", 0) > 0:
        review_suggestion = "建议审核 review_candidate 条目"
    elif update_counter.get("baseline", 0) > 0:
        review_suggestion = "建议确认 baseline 是否需要补充"
    else:
        review_suggestion = "建议评估是否需补充更高质量证据"

    # ── 批次质量评分 ──
    quality_score, blocking_issues, quality_warnings = compute_batch_quality_score(
        batch_records, check_result, args.skipped_count
    )

    # ── 组装摘要 ──
    summary = {
        "batch_id": bid,
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "theme_term": ", ".join(theme_terms),
        "canonical_concept": ", ".join(concepts),
        "aliases": aliases_sorted,
        "archived_count": len(batch_records),
        "skipped_count": args.skipped_count,
        "failed_count": args.failed_count,
        "companies": companies,
        "codes": codes,
        "by_evidence_layer": dict(layer_counter),
        "by_update_type": dict(update_counter),
        "by_source_type": dict(source_counter),
        "by_exposure_strength": dict(exposure_counter),
        "by_chain_layer": dict(chain_counter),
        "graph_only_count": graph_only_count,
        "exposure_only_count": exposure_only_count,
        "not_applied": not_applied,
        "skipped_reasons": args.skipped_reasons,
        "records": record_summaries,
        "check_status": check_result["status"] if check_result else "SKIPPED",
        "batch_quality_score": quality_score,
        "blocking_issues": blocking_issues,
        "warnings": quality_warnings,
        "next_review_suggestion": review_suggestion,
        "safety_statement": (
            "本批次仅归档至 wiki/raw/disclosures/，"
            "未修改 entities/concepts/relations，未运行 writer。"
        ),
    }

    if check_result and check_result["stderr"]:
        summary["check_stderr"] = check_result["stderr"]

    output_path = batches_dir / f"{bid}.json"
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] 批次摘要写入: {output_path}")
    print(f"     记录数: {len(batch_records)}, 公司: {len(companies)}, "
          f"检查: {summary['check_status']}, 质量: {quality_score}")

    if check_result and check_result["exit_code"] != 0 and not args.skip_check:
        print(f"[WARN] check.py 返回非零退出码: {check_result['exit_code']}", file=sys.stderr)
        if check_result["stderr"]:
            print(check_result["stderr"], file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
