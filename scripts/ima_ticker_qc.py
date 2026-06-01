#!/usr/bin/env python3
"""通用 ticker-QC：对所有题材 pool items 逐条比对 IMA↔库(+concept_graph)。
- 自动改明显的 IMA 错号（IMA 码被别家占用 / 被 KB+CG 共同否定）
- 双向冲突或疑似库错 → 打 flag 待人工裁定
- 输出修正后的 pool items + 一张待复核清单(JSON + 终端表)
只读源数据，不写知识库。
"""
import json, os, re, glob, collections, sys

REL = os.path.expanduser("~/Desktop/c c/知识库/wiki/relations")
IN = sys.argv[1] if len(sys.argv) > 1 else "/tmp/imabatch"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/imabatch_qc"
os.makedirs(OUT, exist_ok=True)

ee = json.load(open(f"{REL}/entity_exposures.json", encoding="utf-8"))["entities"]
kb = {}                       # name -> code
rev = collections.defaultdict(set)   # code -> {names}  (KB)
for nm, e in ee.items():
    c = e.get("codes") or []
    if c:
        kb[nm] = str(c[0]); rev[str(c[0])].add(nm)
cg = collections.defaultdict(set)    # name -> {codes}  (concept_graph)
for cpt in json.load(open(f"{REL}/concept_graph.json", encoding="utf-8")).get("concepts", {}).values():
    for co in cpt.get("companies", []) or []:
        n, code = co.get("name"), str(co.get("code") or "")
        if n and re.fullmatch(r"\d{6}", code):
            cg[n].add(code)

def adjudicate(name, t_ima):
    """return (action, new_ticker, reason). action: ok|autofix|flag_ima|flag_kb|flag_unknown"""
    t_kb = kb.get(name)
    if not t_kb:
        return ("not_in_kb", t_ima, "库未覆盖（扩库候选）")
    if t_ima == t_kb:
        return ("ok", t_ima, "")
    cgset = cg.get(name, set())
    owners_ima = rev.get(t_ima, set()) - {name}     # IMA 码被库里别家占用
    if cgset:
        if t_ima in cgset and t_kb not in cgset:
            return ("flag_kb", t_ima, f"IMA+concept_graph 一致={t_ima}，库孤证={t_kb}，疑库错")
        if t_kb in cgset:
            if owners_ima:
                return ("autofix", t_kb, f"IMA码{t_ima}属[{','.join(sorted(owners_ima))}]+库/CG一致，确定IMA错")
            return ("autofix_verify", t_kb, f"库+CG一致={t_kb}，IMA={t_ima}（需抽验，防库源同错）")
        return ("flag_conflict", t_ima, f"三方不一致 IMA={t_ima}/库={t_kb}/CG={sorted(cgset)}")
    if owners_ima:
        return ("autofix", t_kb, f"IMA码{t_ima}属于[{','.join(sorted(owners_ima))}]，IMA错→改库码{t_kb}")
    return ("flag_ima", t_kb, f"双向冲突无佐证 IMA={t_ima}/库={t_kb}")

review = []           # 真冲突: autofix/flag_kb/flag_ima/flag_conflict
not_in_kb = []        # 库未覆盖 (扩库候选)
stats = collections.Counter()
seen, nk_seen = set(), set()
for f in sorted(glob.glob(os.path.join(IN, "*.theme_information_items.jsonl"))):
    theme = os.path.basename(f).split(".theme_info")[0]
    rows = [json.loads(l) for l in open(f, encoding="utf-8")]
    for r in rows:
        nm = r.get("entity_name"); tk = str(r.get("ticker", "") or "")
        if not nm or not re.fullmatch(r"\d{6}", tk):
            continue
        act, new, reason = adjudicate(nm, tk)
        if act == "ok":
            continue
        if act == "not_in_kb":
            stats["not_in_kb"] += 1
            if (theme, nm) not in nk_seen:
                nk_seen.add((theme, nm))
                not_in_kb.append({"theme": theme, "entity": nm, "ima_ticker": tk})
            continue
        r.setdefault("flags", [])
        if act in ("autofix", "autofix_verify"):
            r["ticker"] = new; r["ticker_original"] = tk
            r["flags"].append("ticker_autofixed" if act == "autofix" else "ticker_autofix_verify")
            stats[act] += 1
        else:
            r["flags"].append(f"ticker_{act}")
            stats[act] += 1
        if (theme, nm, tk) not in seen:
            seen.add((theme, nm, tk))
            review.append({"theme": theme, "entity": nm, "ima_ticker": tk,
                           "kb_ticker": kb.get(nm, ""), "cg_ticker": sorted(cg.get(nm, set())),
                           "action": act, "suggested": new, "reason": reason})
    with open(os.path.join(OUT, os.path.basename(f)), "w", encoding="utf-8") as o:
        for r in rows:
            o.write(json.dumps(r, ensure_ascii=False) + "\n")

json.dump({"stats": dict(stats), "review": review, "not_in_kb": not_in_kb},
          open(os.path.join(OUT, "ticker_review_queue.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"统计: {dict(stats)}  (修正后 items -> {OUT})")
print(f"库未覆盖公司(扩库候选): {len(not_in_kb)} 家\n")
print("=== 待复核清单（真 ticker 冲突）===")
print(f"{'题材':<12}{'公司':<8}{'IMA':<8}{'库':<8}{'CG':<9}{'处理':<14}原因")
print("-" * 90)
for x in sorted(review, key=lambda r: r["action"]):
    print(f"{x['theme'][:10]:<12}{x['entity'][:7]:<8}{x['ima_ticker']:<8}{x['kb_ticker']:<8}{(','.join(x['cg_ticker']) or '-'):<9}{x['action']:<14}{x['reason']}")
print(f"\n待复核清单 + 扩库候选 -> {OUT}/ticker_review_queue.json")
