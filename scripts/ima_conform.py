#!/usr/bin/env python3
"""把旧 schema 的 IMA 抽取 md 升级到官方 raw-IMA 契约 (parse_ima_theme_markdown.py)。

只读输入，产出 <name>.conformed.md + <name>.conform-report.md。
变更：补 ticker_check_status + theme_layer；evidence_level hard_fact->review_candidate
      (raw IMA 禁 hard_fact)；ticker 对知识库交叉校正；风险来源强制 needs_review。
不写知识库。
"""
import json, os, re, sys, collections

REL = os.path.expanduser("~/Desktop/c c/知识库/wiki/relations")
RISK_SRC = {"自媒体专栏", "行业研报/自媒体", "研报及自媒体专栏", "用户提示词"}

kb = {}
for nm, ent in json.load(open(os.path.join(REL, "entity_exposures.json"), encoding="utf-8"))["entities"].items():
    codes = ent.get("codes") or []
    if codes:
        kb[nm] = str(codes[0])

def extract_jsonl(text):
    recs = []
    for b in re.findall(r"```jsonl\n(.*?)```", text, re.S):
        for ln in b.splitlines():
            ln = ln.strip()
            if ln.startswith("{") and ln.endswith("}"):
                recs.append(json.loads(ln))
    if not recs:  # fallback: any { } line
        for ln in text.splitlines():
            ln = ln.strip()
            if ln.startswith("{") and ln.endswith("}"):
                recs.append(json.loads(ln))
    return recs

def theme_from_title(text, fallback):
    for ln in text.splitlines():
        if ln.startswith("# "):
            t = re.sub(r"^[🎯\s]+", "", ln.lstrip("#").strip())
            t = re.sub(r"(?:_)?题材雷达数据抽取(报告)?.*$", "", t).strip()
            return t or fallback
    return fallback

def conform(rec, log):
    name = rec.get("entity_name", "")
    tk = str(rec.get("ticker", "")).strip()
    # ticker cross-check / correct
    kb_code = kb.get(name)
    if re.fullmatch(r"\d{6}", tk):
        if kb_code and kb_code != tk:
            log["ticker_fixed"].append(f"{name} {tk}->{kb_code}")
            tk = kb_code; status = "corrected"
        elif kb_code == tk:
            status = "verified"
        else:
            status = "unverified"
    elif "拟上市" in tk:
        status = "prelisting"
    elif tk == "":
        status = "non_company"
    else:
        status = "unverified"
    rec["ticker"] = tk
    rec["ticker_check_status"] = status
    # theme_layer
    ev = rec.get("evidence_level", "")
    sug = rec.get("suggested_use", "")
    if tk == "":
        layer = "context"
    elif ev == "exposure_only" or sug == "watchlist_only":
        layer = "adjacent"
    elif rec.get("confidence") == "high":
        layer = "core"
    else:
        layer = "strong_support"
    rec["theme_layer"] = layer
    log["theme_layer"][layer] += 1
    # evidence_level: hard_fact 非法 -> review_candidate
    if ev == "hard_fact":
        rec["evidence_level"] = "review_candidate"
        rec["needs_review"] = True
        log["hard_fact_downgraded"].append(name)
    # risky source 强制复核
    if rec.get("source_type") in RISK_SRC and rec.get("needs_review") is False:
        rec["needs_review"] = True
        log["risky_forced_review"].append(name)
    log["ticker_status"][status] += 1
    return rec

def main():
    src = os.path.expanduser(sys.argv[1])
    text = open(src, encoding="utf-8").read()
    recs = extract_jsonl(text)
    theme = theme_from_title(text, recs[0].get("theme", "") if recs else "")
    log = {"ticker_fixed": [], "hard_fact_downgraded": [], "risky_forced_review": [],
           "ticker_status": collections.Counter(), "theme_layer": collections.Counter()}
    out = [conform(r, log) for r in recs]
    base = os.path.splitext(src)[0]
    outmd = base + ".conformed.md"
    with open(outmd, "w", encoding="utf-8") as f:
        f.write(f"# {theme}题材雷达数据抽取\n\n")
        f.write("> conformed to official raw-IMA contract (ima_conform.py). read-only derived.\n\n")
        f.write("```jsonl\n")
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.write("```\n")
    rep = base + ".conform-report.md"
    with open(rep, "w", encoding="utf-8") as f:
        f.write(f"# IMA conform 报告: {os.path.basename(src)}\n\n")
        f.write(f"- theme: {theme}\n- records: {len(out)}\n")
        f.write(f"- ticker_check_status: {dict(log['ticker_status'])}\n")
        f.write(f"- theme_layer: {dict(log['theme_layer'])}\n")
        f.write(f"- ticker 校正({len(log['ticker_fixed'])}): {log['ticker_fixed']}\n")
        f.write(f"- hard_fact→review_candidate({len(log['hard_fact_downgraded'])}): {log['hard_fact_downgraded']}\n")
        f.write(f"- 风险来源强制复核({len(log['risky_forced_review'])}): {log['risky_forced_review']}\n")
    print(f"[OK] conformed -> {outmd}")
    print(f"[OK] report    -> {rep}")
    print(f"ticker_fixed: {log['ticker_fixed']}")
    print(f"hard_fact_downgraded: {len(log['hard_fact_downgraded'])}  theme_layer: {dict(log['theme_layer'])}")

if __name__ == "__main__":
    main()
