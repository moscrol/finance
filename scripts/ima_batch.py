#!/usr/bin/env python3
"""批量扫描 ima/ 下所有 IMA MD：格式、parse_ima 合规、pool 产出、ticker 对库校验。只读。"""
import json, os, re, subprocess, sys, glob

PIPE = "/tmp/imapipe"
IMA = os.path.expanduser("~/Desktop/c c/ima")
OUT = "/tmp/imabatch"
REL = os.path.expanduser("~/Desktop/c c/知识库/wiki/relations")
os.makedirs(OUT, exist_ok=True)

kb = {}
for nm, ent in json.load(open(os.path.join(REL, "entity_exposures.json"), encoding="utf-8"))["entities"].items():
    c = ent.get("codes") or []
    if c:
        kb[nm] = str(c[0])

def jsonl_recs(text):
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("{") and ln.endswith("}"):
            try: out.append(json.loads(ln))
            except Exception: pass
    return out

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

files = sorted(f for f in glob.glob(os.path.join(IMA, "*.md"))
               if not f.endswith((".conformed.md", ".conform-report.md")))
print(f"{'题材':<22}{'格式':<14}{'pool':>5} {'记录类型(主)':<26}{'parse问题':<10}{'ticker错':<8}")
print("-" * 96)
problems = []
for f in files:
    base = os.path.basename(f)
    stem = os.path.splitext(base)[0]
    text = open(f, encoding="utf-8").read()
    recs = jsonl_recs(text)
    # 格式判定
    if not recs:
        fmt = "DeepDive散文"
    else:
        ok = all(("ticker_check_status" in r and "theme_layer" in r) for r in recs)
        hf = any(r.get("evidence_level") == "hard_fact" for r in recs)
        fmt = "JSONL合规" if (ok and not hf) else "JSONL旧需conform"
    # build_pool
    r = run(["python3", f"{PIPE}/build_theme_information_pool.py", f, "--out-dir", OUT])
    try:
        s = json.load(open(os.path.join(OUT, f"{stem}.summary.json"), encoding="utf-8"))
        n = s.get("item_count", 0); theme = s.get("theme", stem)
        rt = s.get("items_by_record_type", {})
        rtmain = ",".join(f"{k.replace('deep_dive_','').replace('jsonl_appendix','jsonl')}:{v}" for k, v in list(rt.items())[:3])
    except Exception:
        n, theme, rtmain = "ERR", stem, str(r.stderr[:30])
    # parse_ima 问题数
    pr = run(["python3", f"{PIPE}/parse_ima_theme_markdown.py", f])
    pi = "-"
    if recs:
        try:
            d = json.loads(pr.stdout); pi = d.get("validation_issue_count", "?")
        except Exception:
            pi = "无JSONL"
    # ticker 对库校验
    mism = []
    for rec in recs:
        nm = rec.get("entity_name"); tk = str(rec.get("ticker", ""))
        if re.fullmatch(r"\d{6}", tk) and kb.get(nm) and kb[nm] != tk:
            mism.append(f"{nm}:{tk}->{kb[nm]}")
    tkn = str(len(mism)) if mism else "0"
    print(f"{theme:<22}{fmt:<14}{str(n):>5} {rtmain:<26}{str(pi):<10}{tkn:<8}")
    if mism: problems.append((theme, "ticker", mism))
    if fmt == "JSONL旧需conform": problems.append((theme, "需conform", ""))
print("\n=== ticker 错误明细 ===")
for t, k, m in problems:
    if k == "ticker": print(f"  {t}: {m}")
print("=== 需 conform 的旧 schema ===")
print("  " + ", ".join(t for t, k, _ in problems if k == "需conform") or "  (无)")
