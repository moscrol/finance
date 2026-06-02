#!/usr/bin/env python3
"""用 iFinD(问财) 对 ticker 冲突做权威裁定，覆盖 KB/CG，改写 pool items。"""
import json, os, re, subprocess, glob, time

CLI = os.path.expanduser("~/Desktop/c c/金融/.claude/skills/hithink-market-query/scripts/cli.py")
QC = "/tmp/imabatch_qc"
q = json.load(open(f"{QC}/ticker_review_queue.json", encoding="utf-8"))
names = sorted({r["entity"] for r in q["review"]})

def ifind_code(name):
    try:
        r = subprocess.run(["python3", CLI, "--query", f"{name} 股票代码"],
                           capture_output=True, text=True, timeout=40)
        d = json.loads(r.stdout)
        cand = d.get("datas", []) or []
        # 优先精确简称匹配
        for it in cand:
            if str(it.get("股票简称", "")) == name:
                return re.sub(r"\..*$", "", str(it.get("股票代码", "")))
        if cand:
            return re.sub(r"\..*$", "", str(cand[0].get("股票代码", "")))
    except Exception as e:
        return f"ERR:{e}"
    return ""

truth = {}
print(f"{'公司':<9}{'iFinD':<8}{'IMA':<8}{'库':<8}裁定")
print("-" * 60)
rmap = {r["entity"]: r for r in q["review"]}
for nm in names:
    code = ifind_code(nm); time.sleep(0.3)
    truth[nm] = code
    r = rmap[nm]; ima = r["ima_ticker"]; kb = r["kb_ticker"]
    verdict = ("=IMA" if code == ima else "=库" if code == kb else "都不符!" if re.fullmatch(r"\d{6}", code or "") else "查询失败")
    print(f"{nm[:8]:<9}{code:<8}{ima:<8}{kb:<8}{verdict}")

# 应用 iFinD 权威码到 pool items
fixed = 0
for f in glob.glob(f"{QC}/*.theme_information_items.jsonl"):
    rows = [json.loads(l) for l in open(f, encoding="utf-8")]
    for r in rows:
        nm = r.get("entity_name"); code = truth.get(nm)
        if nm in truth and re.fullmatch(r"\d{6}", code or "") and str(r.get("ticker", "")) != code:
            r.setdefault("flags", []).append("ticker_ifind_authoritative")
            r["ticker_original"] = r.get("ticker_original", r.get("ticker"))
            r["ticker"] = code; fixed += 1
    with open(f, "w", encoding="utf-8") as o:
        for r in rows:
            o.write(json.dumps(r, ensure_ascii=False) + "\n")

json.dump({"ifind_truth": truth}, open(f"{QC}/ifind_resolution.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n按 iFinD 改写 pool items: {fixed} 处 -> {QC}/ifind_resolution.json")
