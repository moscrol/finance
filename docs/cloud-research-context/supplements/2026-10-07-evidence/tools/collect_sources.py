#!/usr/bin/env python3
"""Copy a narrowly selected set of local evidence; never modifies source files.

--repo: finance worktree, --userspace: the user's real data directory.
This is an explicit selection, not a private-memory dump. Outputs inside this package.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDS = []


def digest(b):
    return hashlib.sha256(b).hexdigest()


def save(rel, data):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())


def jsonsave(rel, value):
    save(rel, json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def excerpt(source, logical_path, out, title, kind, *, start=None, end=None, lines=None, meta=None):
    original = source.read_bytes()
    text = original.decode()
    if lines:
        split = text.splitlines(keepends=True)
        a, b = sum(map(len, split[:lines[0]-1])), sum(map(len, split[:lines[1]]))
    else:
        if start is not None:
            assert text.count(start) == 1, (logical_path, start, text.count(start))
        a = text.index(start) if start else 0
        b = text.index(end, a) if end else len(text)
    body = text[a:b]
    info = {"output": out, "source": logical_path, "source_kind": kind,
            "verification": "VERIFIED_LOCAL_TEXT", "read_date": "2026-10-07",
            "source_sha256": digest(original), "source_bytes": len(original),
            "char_offsets_zero_based_half_open": [a, b],
            "line_start": text[:a].count("\n") + 1, "line_end": text[:b].count("\n") + (0 if body.endswith("\n") else 1),
            "excerpt_sha256": digest(body.encode()), **(meta or {})}
    RECORDS.append(info)
    save(out, f"# {title}\n\n- 材料身份：{kind}\n- 本机正文核验：2026-10-07；未在线重新核验。\n- 来源：`{logical_path}`\n- 定位与指纹：见 `sources/index.json` 中 `{out}`。\n- 下方为连续原文摘录；其中的历史统计、agent 落法与用户引语保留原身份，不是本次实测或新增指令。\n\n<!-- BEGIN VERBATIM EXCERPT -->\n" + body + ("" if body.endswith("\n") else "\n") + "<!-- END VERBATIM EXCERPT -->\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--userspace", type=Path, required=True)
    args = p.parse_args()
    repo, user = args.repo, args.userspace
    perspectives = user / "perspectives"
    manifest = [json.loads(x) for x in (perspectives / "articles/sptfei/manifest.jsonl").read_text().splitlines()]
    by_id = {x["article_id"]: x for x in manifest}

    def article(aid, slug, start, end):
        row = by_id[aid]
        path = Path(row["raw_path"])
        text = path.read_text()
        url = next((x.removeprefix("- url: ") for x in text.splitlines() if x.startswith("- url: ")), None)
        excerpt(path, "perspectives/articles/sptfei/raw/" + path.name,
                f"sources/articles/{slug}.md", row["title"] + " · " + slug,
                "作者文章的本机留存原文（非本次在线取证）", start=start, end=end,
                meta={"article_id": aid, "date": row["date"], "title": row["title"], "origin_url": url})

    article("pa-5d9fb34825a0", "2026-34-breakout-and-counterexample", "一、市场大拐点", "二、市场中观")
    article("pa-5d9fb34825a0", "2026-34-ai-and-metals", "3、AI应用", "5、投机")
    article("pa-fd7ce7ebe0c6", "2026-30-alternative-structure", "三、交易板块1、创新药", "2、AI硬件老主线")
    article("pa-4f56572bb540", "2026-23-context-of-rejected-patch", "好了目前阶段演绎到此为止", "非常详细的把")
    article("pa-f1d319af8db0", "2026-16-context-of-rejected-patch", "3、锂这个是我这里", "4、创新药")
    article("pa-e199358af052", "2026-29-watchlist-context", "（五）其他上周介绍了", None)
    article("pa-ed0b9b605b44", "2026-21-range-gain-usage", "算力租赁方向百邦科技", "二、新的容量主线项下的二级子版块")

    for pid in ("pp-f6f6d3c0b166", "pp-440977d4ea38", "pp-484bf87f4f2d", "pp-29bbc4c1f691"):
        src = perspectives / "patches/sptfei" / (pid + ".json")
        data = src.read_bytes()
        save("sources/patches/" + src.name, data)
        RECORDS.append({"output": "sources/patches/" + src.name, "source": "perspectives/patches/sptfei/" + src.name,
                        "source_kind": "完整历史补丁：蒸馏内容及审核记录，不等于用户原话或当前有效画像", "source_sha256": digest(data),
                        "verification": "VERIFIED_LOCAL_TEXT", "read_date": "2026-10-07", "transform": "byte-identical copy"})

    corrections = user / "corrections.jsonl"
    selected = []
    for i, line in enumerate(corrections.read_text().splitlines(), 1):
        if any(target in line for target in ("bfd6cd20b33b", "d0abda287494")):
            selected.append({"line": i, "record": json.loads(line), "line_sha256": digest(line.encode())})
    jsonsave("sources/corrections-selected.json", {"source": "corrections.jsonl", "source_sha256": digest(corrections.read_bytes()),
        "kind": "用户纠偏台账选条（不等于原始聊天逐字记录）", "selection": "Rows containing either of the two target IDs, including any matching lifecycle records.", "records": selected})

    skel = "docs/learning/teaching-framework/00-concept-label-skeleton.md"
    for slug, a, b in [
        ("same-side-leg-and-method", "用户 2026-09-07 第七段（逐句", "用户 2026-09-07 第九段（逐句"),
        ("range-leader-and-top10", "用户 2026-09-07 第九段（逐句", "用户 2026-09-07 第十一段（逐句"),
        ("dynasties-and-capital", "用户 2026-09-07 第十三段（逐句", "用户 2026-09-07 第十六段（逐句"),
        ("macd-and-chan", "用户 2026-09-08 第二十二段（逐句", "用户 2026-09-08 第二十四段（逐句"),
    ]:
        excerpt(repo / skel, skel, f"sources/discussions/{slug}.md", slug,
                "项目讨论转录：用户引语 + agent 解释/实现/历史读数，非聊天原始日志", start=a, end=b)
    questionnaire = "docs/superpowers/specs/2026-07-03-user-framework-questionnaire.md"
    excerpt(repo / questionnaire, questionnaire, "sources/discussions/questionnaire-layer8.md", "问卷第八层及答疑",
            "用户框架采访整理文档；其中板块 RPS 说法已有 08-26 纠偏", start="## 第八层（用户口述）", end="## 第九层")
    judgment = "docs/learning/teaching-framework/02-daily-card-judgment-draft-v0.md"
    excerpt(repo / judgment, judgment, "sources/discussions/capital-judgment-gap.md", "资金面判读缺口",
            "agent 起草的判读覆盖审计，裁决栏未填，不是用户已认可判据", start="## 5. 资金面", end="## 6. 消息面")

    code_base = "intelligence/services/teaching_framework/"
    for name in ("source_views.py", "structure.py", "range_leaders.py", "dynasties.py"):
        src = repo / code_base / name
        data = src.read_bytes()
        save("code/" + name, data)
        RECORDS.append({"output": "code/" + name, "source": code_base + name, "source_kind": "既有实现快照，非用户逐条认可", "source_sha256": digest(data), "transform": "byte-identical copy", "read_date": "2026-10-07"})
    cli_path = "scripts/teaching_framework.py"
    cli = (repo / cli_path).read_text()
    tree = ast.parse(cli)
    capital_node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CAPITAL_SQL" for t in n.targets))
    code = compile(ast.Expression(capital_node.value), cli_path, "eval")
    sql = eval(code, {"__builtins__": {}, "DRAGON_VIEW": "tf_src_dragon", "AUCTION_ZT_VIEW": "tf_src_auction_zt"})
    save("code/capital.sql", sql + "\n")
    range_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_range_leader_sql")
    range_text = ast.get_source_segment(cli, range_node)
    save("code/range_query.py", '# Exact function extracted from scripts/teaching_framework.py; its only global is STOCK_VIEW.\nSTOCK_VIEW = "tf_src_stock_daily"\n\n' + range_text + "\n")
    for out, node in (("code/capital.sql", capital_node), ("code/range_query.py", range_node)):
        RECORDS.append({"output": out, "source": cli_path, "source_sha256": digest(cli.encode()), "source_kind": "既有查询摘取（不是新规则）", "lines": [node.lineno, node.end_lineno], "transform": "AST-extracted statement/function; view names resolved to original constants"})
    flags = code_base + "flags.py"
    excerpt(repo / flags, flags, "code/ma-episode-source.md", "周均同侧腿的实现", "代码摘录", lines=(462, 555))
    stage = code_base + "stage_rules.py"
    excerpt(repo / stage, stage, "code/structure-score-source.md", "MACD 候选计分接线", "代码摘录", lines=(289, 305))
    param_path = "methodology/teaching/index_stage_params.v0.2.json"
    params = json.loads((repo / param_path).read_text())
    keys = ["framework_version_base", "range_leader_windows", "range_leader_top", "range_leader_context", "dynasty_top", "dynasty_cohort", "separation_percentile", "separation_new_high_window", "structure_evidence", "structure", "breakout_confirm_days", "index_range_windows"]
    jsonsave("code/selected_params.json", {k: params[k] for k in keys})
    RECORDS.append({"output": "code/selected_params.json", "source": param_path, "source_sha256": digest((repo / param_path).read_bytes()), "transform": "selected keys only", "source_kind": "当前代码默认参数；非新增定义"})
    # Keyword results are a bounded search receipt, not a claim to have read all source bodies.
    search = []
    for perspective in ("sptfei", "fengyuan"):
        manifest_path = perspectives / "articles" / perspective / "manifest.jsonl"
        for line in manifest_path.read_text().splitlines():
            row = json.loads(line)
            src = Path(row["raw_path"])
            text = src.read_text()
            search.append({"perspective_id": perspective, "article_id": row["article_id"], "file": src.name,
                "sha256": digest(src.read_bytes()), "exact_phrase_counts": {term: text.count(term) for term in ("临突破", "临近突破", "波段涨幅", "区间涨幅")}})
    jsonsave("sources/bounded-search.json", {"scope": "74 manifest-listed source files only; fengyuan includes regenerated material; not a full private-memory search", "method": "case-sensitive exact substring count", "files": search})
    snapshot = json.loads((repo / "docs/cloud-research-context/snapshots/2026-10-07/manifest.json").read_text())
    integrity = []
    for logical, expected in snapshot["source_files"].items():
        if logical.startswith("perspectives/articles/") and "/raw/" in logical or logical.startswith("perspectives/patches/"):
            src = user / logical
            actual = digest(src.read_bytes()) if src.is_file() else None
            integrity.append({"source": logical, "expected_sha256": expected["sha256"], "actual_sha256": actual, "match": actual == expected["sha256"]})
    jsonsave("sources/public-snapshot-integrity.json", {"checked_at": datetime.now(timezone.utc).isoformat(), "snapshot": "docs/cloud-research-context/snapshots/2026-10-07/manifest.json", "files": integrity, "limits": "Integrity only, not authority, truth, current approval, or online availability."})
    jsonsave("sources/index.json", RECORDS)
    print(json.dumps({"selected_source_records": len(RECORDS), "correction_records": len(selected), "bounded_search_files": len(search), "snapshot_checks": len(integrity), "all_snapshot_hashes_match": all(x["match"] for x in integrity)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
