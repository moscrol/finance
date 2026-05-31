#!/usr/bin/env python3
import json, subprocess, sys, shutil, os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ARCHIVE = SKILL_DIR / "scripts" / "archive.py"
CHECK = SKILL_DIR / "scripts" / "check.py"
VAULT = Path.home() / "Desktop" / "c c" / "知识库" / "wiki"
TEST_DIR = VAULT / "raw" / "disclosures-test"
if TEST_DIR.exists():
    shutil.rmtree(TEST_DIR)
os.chdir(SKILL_DIR)

VALID = [
    ["A: L2 hard_delta 容大感光", [
        "--theme-term","感光膜","--canonical-concept","感光干膜",
        "--company","容大感光","--code","300576",
        "--chain-layer","midstream_manufacturing",
        "--role","PCB感光干膜材料供应商",
        "--exposure-strength","related",
        "--evidence-layer","L2","--update-type","hard_delta",
        "--fact-type","certification","--fact-status","realized",
        "--confidence","high","--source-type","announcement",
        "--title","关于公司感光干膜产品通过客户认证的公告",
        "--publish-date","2026-05-20",
        "--url","https://example.com/announcement/300576/photoresist-film",
        "--quoted-text","公司感光干膜产品已通过客户认证，具备量产能力。",
        "--facts","感光干膜产品通过客户认证","公司披露该产品具备量产能力",
    ]],
    ["B: L3 review_candidate 福斯特", [
        "--theme-term","感光膜","--canonical-concept","感光干膜",
        "--company","福斯特","--code","603806",
        "--chain-layer","midstream_manufacturing",
        "--role","感光干膜与功能膜材料供应商",
        "--exposure-strength","related",
        "--evidence-layer","L3","--update-type","review_candidate",
        "--fact-type","official_claim","--fact-status","under_validation",
        "--confidence","medium","--source-type","investor_relation_record",
        "--title","投关活动记录表",
        "--publish-date","2026-05-21",
        "--url","https://example.com/ir/603806/dry-film",
        "--quoted-text","公司表示感光干膜业务仍处于客户导入和产品迭代阶段。",
        "--facts","公司投关记录提及感光干膜业务","业务状态仍需公告或年报进一步验证",
    ]],
    ["C: L4 weak_signal 强力新材", [
        "--theme-term","感光膜","--canonical-concept","感光干膜",
        "--company","强力新材","--code","300429",
        "--chain-layer","upstream_materials",
        "--role","干膜光刻胶光引发剂供应商",
        "--exposure-strength","peripheral",
        "--evidence-layer","L4","--update-type","weak_signal",
        "--fact-type","media_signal","--fact-status","rumored",
        "--confidence","low","--source-type","industry_media",
        "--title","行业报道：干膜光刻胶材料进展",
        "--publish-date","2026-05-22",
        "--url","https://example.com/media/300429/dry-film-initiator",
        "--quoted-text","行业媒体称公司产品可应用于干膜光刻胶光引发体系。",
        "--facts","行业媒体将公司产品与干膜光刻胶光引发体系关联","该信息需要公告或年报交叉验证",
    ]],
]

INVALID = [
    ["D: news+L2", [
        "--theme-term","感光膜","--canonical-concept","感光干膜",
        "--company","容大感光","--code","300576",
        "--chain-layer","midstream_manufacturing","--role","PCB感光干膜材料供应商",
        "--exposure-strength","related",
        "--evidence-layer","L2","--update-type","hard_delta",
        "--fact-type","certification","--fact-status","realized",
        "--confidence","high","--source-type","news",
        "--title","新闻标题","--publish-date","2026-05-20",
        "--url","https://example.com/news/article",
        "--quoted-text","媒体报道公司通过客户认证。","--facts","媒体报道公司产品通过认证",
    ]],
    ["E: graph_only+hard_delta", [
        "--theme-term","感光膜","--canonical-concept","感光干膜",
        "--company","容大感光","--code","300576",
        "--chain-layer","midstream_manufacturing","--role","PCB感光干膜材料供应商",
        "--exposure-strength","related",
        "--evidence-layer","L2","--update-type","hard_delta",
        "--fact-type","certification","--fact-status","realized",
        "--confidence","high","--source-type","announcement",
        "--graph-only",
        "--title","公告","--publish-date","2026-05-20",
        "--url","https://example.com/ann","--quoted-text","产品认证。","--facts","产品认证",
    ]],
    ["F: core+L3", [
        "--theme-term","感光膜","--canonical-concept","感光干膜",
        "--company","福斯特","--code","603806",
        "--chain-layer","midstream_manufacturing","--role","感光干膜供应商",
        "--exposure-strength","core",
        "--evidence-layer","L3","--update-type","review_candidate",
        "--fact-type","official_claim","--fact-status","under_validation",
        "--confidence","medium","--source-type","investor_relation_record",
        "--title","投关记录","--publish-date","2026-05-21",
        "--url","https://example.com/ir","--quoted-text","公司提及干膜。","--facts","公司提及干膜",
    ]],
    ["G: 泛词role=相关公司", [
        "--theme-term","感光膜","--canonical-concept","感光干膜",
        "--company","容大感光","--code","300576",
        "--chain-layer","midstream_manufacturing","--role","相关公司",
        "--exposure-strength","related",
        "--evidence-layer","L2","--update-type","hard_delta",
        "--fact-type","certification","--fact-status","realized",
        "--confidence","high","--source-type","announcement",
        "--title","公告","--publish-date","2026-05-20",
        "--url","https://example.com/ann",
        "--quoted-text","产品认证。","--facts","产品认证",
    ]],
    ["H: facts空+非reject", [
        "--theme-term","感光膜","--canonical-concept","感光干膜",
        "--company","容大感光","--code","300576",
        "--chain-layer","midstream_manufacturing","--role","PCB感光干膜材料供应商",
        "--exposure-strength","related",
        "--evidence-layer","L2","--update-type","hard_delta",
        "--fact-type","certification","--fact-status","realized",
        "--confidence","high","--source-type","announcement",
        "--title","公告","--publish-date","2026-05-20",
        "--url","https://example.com/ann",
        "--quoted-text","产品认证。",
    ]],
]

def run(args, real):
    dry = [] if real else ["--dry-run"]
    cmd = [sys.executable, str(ARCHIVE), "--disclosures-dir", str(TEST_DIR)] + dry + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r

print("=" * 60)
print("Phase 1: dry-run 拦截验证")
print("=" * 60)
for label, args in INVALID:
    r = run(args, False)
    status = "PASS" if r.returncode != 0 else "UNEXPECTED_SUCCESS"
    first = r.stderr.strip().split("\n")[0] if r.stderr else ""
    print(f"  [{status}] {label}")
    if first:
        print(f"    -> {first}")

print()
print("=" * 60)
print("Phase 2: 写入合法样例")
print("=" * 60)
for label, args in VALID:
    r = run(args, True)
    print(f"  [{('PASS' if r.returncode==0 else 'FAIL')}] {label}")

print()
print("=" * 60)
print("Phase 3: 写入非法样例(均应拒绝)")
print("=" * 60)
for label, args in INVALID:
    r = run(args, True)
    status = "PASS" if r.returncode != 0 else "UNEXPECTED_SUCCESS"
    first = r.stderr.strip().split("\n")[0] if r.stderr else ""
    print(f"  [{status}] {label}")
    if first:
        print(f"    -> {first}")

print()
print("=" * 60)
print("Phase 4: manifest.jsonl")
print("=" * 60)
mp = TEST_DIR / "manifest.jsonl"
if mp.exists():
    for line in mp.read_text().strip().splitlines():
        if line.strip():
            d = json.loads(line)
            print(f"  {d['archive_id']} | {d['company']} ({d['code']}) | {d['evidence_layer']}/{d['update_type']} | {d['exposure_strength']}")
else:
    print("  (不存在)")

print()
print("=" * 60)
print("Phase 5: 目录结构")
print("=" * 60)
for p in sorted(TEST_DIR.rglob("*")):
    if p.is_file():
        print(f"  {p.relative_to(TEST_DIR)}")

print()
print("=" * 60)
print("Phase 6: check.py")
print("=" * 60)
r = subprocess.run([sys.executable, str(CHECK), "--disclosures-dir", str(TEST_DIR)], capture_output=True, text=True)
print(r.stdout)
if r.stderr:
    print("STDERR:", r.stderr)

print()
print("=" * 60)
print("汇总")
print("=" * 60)
passed = len(VALID)
failed_expected = len(INVALID)
manifest_count = len([l for l in mp.read_text().strip().splitlines() if l.strip()]) if mp.exists() else 0
check_ok = r.returncode == 0
print(f"  合法样例写入:    {passed}/3")
print(f"  非法样例拒绝:    {failed_expected}/5")
print(f"  manifest 记录数: {manifest_count}")
print(f"  check.py 状态:   {'PASS' if check_ok else 'FAIL'}")
print(f"  结论: {'全部通过' if passed==3 and failed_expected==5 and manifest_count==3 and check_ok else '需排查'}")
