#!/usr/bin/env python3
"""零凭证离线 selftest：验证 `intelligence.ask` 的 W 源（知识库 hybrid 向量召回）接线。

本测试**不联网、不读飞书/iFinD/DuckDB、不下 BGE-m3 权重**：在临时目录里伪造一个
最小知识库仓（`scripts/rag_index.py` stub + `wiki/synthesis/*.md` 候选页 + 空
`.rag_index/` 目录），用 stub 模拟真实 `rag_index.py query --json` 的 PageHit 输出
契约，然后：

  1. 直接调 ``kb_rag.retrieve`` —— 验证 subprocess 调用、JSON 解析、按相对
     file_path 读候选页正文（剥 YAML frontmatter）生成 excerpt；
  2. 跑完整 ``answer_query`` —— 验证证据链多出「图谱·语义召回(wiki 向量)」块、
     生成 ``[W#]`` 编号、found_wiki=True，且与 S/G/R 三路并存；
  3. 「存在才接」降级：脚本缺失 / 索引缺失 / 子进程非零退出 / 输出非 JSON 四种情况
     都静默跳过 W，保持 S/G/R 行为不变并记录 warning；
  4. ``--no-wiki-rag`` 关闭：即便 stub 可用也不产生 W 引用。

用法：python3 intelligence/services/kb_rag_selftest.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from intelligence.services import kb_rag  # noqa: E402
from intelligence.services.ask import SUBHEAD, AskOptions, answer_query, render_answer  # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, ok: bool, extra: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}" + (f" — {extra}" if extra else ""))


STUB = '''#!/usr/bin/env python3
import os, sys, json
mode = os.environ.get("KB_RAG_STUB_MODE", "ok")
if mode == "fail":
    sys.stderr.write("stub: simulated query failure\\n")
    sys.exit(2)
if mode == "garbage":
    sys.stdout.write("<<not json at all>>")
    sys.exit(0)
hits = [
    {"page_id": "page_a", "file_path": "wiki/synthesis/page_a.md",
     "title": "页A·钨供给瓶颈", "score": 0.812345, "best_chunk_id": "page_a#0",
     "section": "供需", "content_hash": "hash-a",
     "index_built_at": "2026-07-10T12:00:00+00:00",
     "index_source_revision": "abc123", "index_freshness": "fresh",
     "via_neighbor": False, "snippet": "snippet-A-fallback",
     "evidence_text": "匹配块：钨精矿供给出现瓶颈，江钨等龙头受益。"},
    {"page_id": "page_b", "file_path": "wiki/synthesis/page_b.md",
     "title": "页B·海绵钛", "score": 0.501234, "best_chunk_id": "page_b#0",
     "via_neighbor": True, "snippet": "snippet-B-fallback",
     "evidence_text": "匹配块：海绵钛价格企稳。"},
]
print(json.dumps(hits, ensure_ascii=False, indent=2))
'''

# Echo stub: 把子进程看到的 RAG_INDEX_DIR 回显到命中页 title，用于验证 index_dir 路由。
STUB_ECHO = '''#!/usr/bin/env python3
import os, sys, json
idx = os.environ.get("RAG_INDEX_DIR", "<none>")
hits = [{"page_id": "page_a", "file_path": "wiki/synthesis/page_a.md",
         "title": "IDX=" + idx, "score": 0.9, "best_chunk_id": "page_a#0",
         "via_neighbor": False, "snippet": "s", "evidence_text": "matched"}]
print(json.dumps(hits, ensure_ascii=False))
'''

PAGE_A = """---
title: 页A·钨供给瓶颈
type: synthesis
---
钨精矿供给出现瓶颈，江钨等龙头受益。这是正文第一段，应被 W 源读取为 excerpt。
"""

PAGE_B = """---
title: 页B·海绵钛
type: synthesis
---
海绵钛价格企稳，宝钛股份产能爬坡。W 源应读到此正文而非 frontmatter。
"""


def _build_kb(root: Path, *, with_script: bool, with_index: bool) -> Path:
    """伪造最小知识库仓，返回 wiki 根目录 (= FW 的 --kb-wiki)。"""
    wiki = root / "wiki"
    (wiki / "synthesis").mkdir(parents=True, exist_ok=True)
    (wiki / "synthesis" / "page_a.md").write_text(PAGE_A, encoding="utf-8")
    (wiki / "synthesis" / "page_b.md").write_text(PAGE_B, encoding="utf-8")
    if with_script:
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / "rag_index.py").write_text(STUB, encoding="utf-8")
    if with_index:
        (root / ".rag_index").mkdir(parents=True, exist_ok=True)
        (root / ".rag_index" / "store.json").write_text("{}", encoding="utf-8")
    return wiki


def _set_env(**kw: str | None) -> None:
    for key, val in kw.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _ask(wiki: Path, *, use_wiki_rag: bool = True):
    return answer_query(
        AskOptions(
            query="钨 供给 瓶颈",
            exports_dir=str(wiki.parent / "__no_exports__"),  # force S miss
            kb_wiki=str(wiki),
            use_modules=False,
            use_wiki_rag=use_wiki_rag,
            wiki_rag_k=3,
        )
    )


def _wiki_chain_lines(result) -> list[str]:
    """Collect the lines under the '图谱·语义召回(wiki 向量)' subhead of 证据链."""
    out: list[str] = []
    grab = False
    for line in result.sections.get("证据链", []):
        if line.startswith(SUBHEAD):
            grab = "语义召回(wiki" in line
            continue
        if grab:
            out.append(line)
    return out


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # ---------- Scenario 1: happy path (script + index + valid stub) ----------
        kb1 = base / "kb_ok"
        wiki1 = _build_kb(kb1, with_script=True, with_index=True)
        _set_env(RAG_INDEX_DIR=str(kb1 / ".rag_index"), KB_RAG_STUB_MODE="ok")

        wr = kb_rag.retrieve("钨 供给 瓶颈", str(wiki1), k=3, mode="hybrid", timeout=30)
        check("retrieve: ok=True with 2 hits", wr.ok and len(wr.hits) == 2, repr(wr.warning))
        if wr.hits:
            h0 = wr.hits[0]
            check("retrieve: file_path relative + title parsed",
                  h0.file_path == "wiki/synthesis/page_a.md" and "钨供给瓶颈" in h0.title, repr(h0))
            check("retrieve: excerpt comes from the exact matched chunk",
                  h0.excerpt.startswith("匹配块：钨精矿供给出现瓶颈") and "正文第一段" not in h0.excerpt,
                  repr(h0.excerpt))
            check("retrieve: chunk identity + index snapshot preserved",
                  h0.best_chunk_id == "page_a#0" and h0.section == "供需"
                  and h0.index_source_revision == "abc123", repr(h0))
            check("retrieve: via_neighbor flag preserved (hit B)", wr.hits[1].via_neighbor is True)

        r1 = _ask(wiki1)
        wtags = [c for c in r1.citations if c.tag.startswith("W")]
        check("ask: found_wiki=True", r1.found_wiki is True)
        check("ask: 2 [W#] citations", len(wtags) == 2, f"{[c.tag for c in wtags]}")
        wlines = _wiki_chain_lines(r1)
        check("ask: 证据链 has wiki block with excerpt + [W1]",
              any("钨精矿供给出现瓶颈" in ln and "[W1]" in ln for ln in wlines), repr(wlines))
        src_join = "\n".join(r1.sections.get("引用来源", []))
        check("ask: 引用来源 cites the candidate page path",
              "[W1]" in src_join and "wiki/synthesis/page_a.md" in src_join, src_join)
        rendered = render_answer(r1)
        check("render: contains wiki·语义召回 subhead", "语义召回(wiki 向量)" in rendered)
        check("ask: S/G/R subheads still present (W coexists)",
              "盘面" in rendered and "图谱·概念" in rendered and "证据" in rendered)

        # ---------- Scenario 2: degrade — rag_index.py missing ----------
        kb2 = base / "kb_noscript"
        wiki2 = _build_kb(kb2, with_script=False, with_index=True)
        _set_env(RAG_INDEX_DIR=str(kb2 / ".rag_index"), KB_RAG_STUB_MODE="ok")
        wr2 = kb_rag.retrieve("x", str(wiki2), timeout=30)
        check("degrade(script missing): ok=False + warning", (not wr2.ok) and "找不到" in wr2.warning, repr(wr2.warning))
        r2 = _ask(wiki2)
        check("degrade(script missing): no W citations, found_wiki=False",
              r2.found_wiki is False and not any(c.tag.startswith("W") for c in r2.citations))
        check("degrade(script missing): warning recorded on result",
              any("wiki-rag" in w for w in r2.warnings), repr(r2.warnings))

        # ---------- Scenario 3: degrade — index missing ----------
        kb3 = base / "kb_noindex"
        wiki3 = _build_kb(kb3, with_script=True, with_index=False)
        _set_env(RAG_INDEX_DIR=str(kb3 / ".rag_index_absent"), KB_RAG_STUB_MODE="ok")
        wr3 = kb_rag.retrieve("x", str(wiki3), timeout=30)
        check("degrade(index missing): ok=False + 索引 warning",
              (not wr3.ok) and "索引" in wr3.warning, repr(wr3.warning))

        # ---------- Scenario 4: degrade — subprocess non-zero exit ----------
        _set_env(RAG_INDEX_DIR=str(kb1 / ".rag_index"), KB_RAG_STUB_MODE="fail")
        wr4 = kb_rag.retrieve("x", str(wiki1), timeout=30)
        check("degrade(exit!=0): ok=False + 退出码 warning",
              (not wr4.ok) and "退出码" in wr4.warning, repr(wr4.warning))

        # ---------- Scenario 5: degrade — non-JSON stdout ----------
        _set_env(RAG_INDEX_DIR=str(kb1 / ".rag_index"), KB_RAG_STUB_MODE="garbage")
        wr5 = kb_rag.retrieve("x", str(wiki1), timeout=30)
        check("degrade(bad json): ok=False + 非 JSON warning",
              (not wr5.ok) and "JSON" in wr5.warning, repr(wr5.warning))

        # ---------- Scenario 6: --no-wiki-rag disables W even when stub is valid ----------
        _set_env(RAG_INDEX_DIR=str(kb1 / ".rag_index"), KB_RAG_STUB_MODE="ok")
        r6 = _ask(wiki1, use_wiki_rag=False)
        check("disabled(--no-wiki-rag): no W citations, found_wiki=False",
              r6.found_wiki is False and not any(c.tag.startswith("W") for c in r6.citations))
        check("disabled(--no-wiki-rag): no wiki-rag warning emitted",
              not any("wiki-rag" in w for w in r6.warnings), repr(r6.warnings))

        # ---------- Scenario 7: index_dir 路由（双索引）+ 缺失回退 ----------
        kb7 = base / "kb_dual"
        wiki7 = _build_kb(kb7, with_script=False, with_index=True)
        (kb7 / "scripts").mkdir(parents=True, exist_ok=True)
        (kb7 / "scripts" / "rag_index.py").write_text(STUB_ECHO, encoding="utf-8")
        (kb7 / ".rag_index_full").mkdir(parents=True, exist_ok=True)
        (kb7 / ".rag_index_full" / "store.json").write_text("{}", encoding="utf-8")
        _set_env(RAG_INDEX_DIR=str(kb7 / ".rag_index"), KB_RAG_STUB_MODE="ok")

        wr7 = kb_rag.retrieve("x", str(wiki7), index_dir=".rag_index_full", timeout=30)
        check("index_dir(full): chosen index ends with .rag_index_full",
              wr7.ok and wr7.index_dir.endswith(".rag_index_full"), repr(wr7.index_dir))
        check("index_dir(full): subprocess RAG_INDEX_DIR routed to full",
              bool(wr7.hits) and wr7.hits[0].title.endswith(".rag_index_full"),
              repr(wr7.hits[0].title if wr7.hits else None))

        wr7d = kb_rag.retrieve("x", str(wiki7), timeout=30)
        check("index_dir(default None): 逐字节 → .rag_index, 无 warning",
              wr7d.ok and wr7d.index_dir.endswith(".rag_index")
              and not wr7d.index_dir.endswith(".rag_index_full") and wr7d.warning == "",
              repr((wr7d.index_dir, wr7d.warning)))

        wr7m = kb_rag.retrieve("x", str(wiki7), index_dir=".rag_index_missing", timeout=30)
        check("index_dir(missing): 回退默认 .rag_index + 回退 warning",
              wr7m.ok and wr7m.index_dir.endswith(".rag_index") and "\u56de\u9000" in wr7m.warning,
              repr((wr7m.index_dir, wr7m.warning)))

        # ---------- Scenario 8: 模式名/别名解析 + 自然语言触发词 + CLI 解析 ----------
        check("mode: structured 别名",
              all(kb_rag.normalize_kb_mode(x) == "structured"
                  for x in ["structured", "fast", "\u7ed3\u6784", "\u7ed3\u6784\u7248", "\u901f\u67e5", "STRUCTURED"]))
        check("mode: full 别名",
              all(kb_rag.normalize_kb_mode(x) == "full"
                  for x in ["full", "deep", "\u5168\u6587", "\u5168\u6587\u7248", "\u6df1\u5ea6"]))
        check("mode: 未知 → None",
              kb_rag.normalize_kb_mode("\u94f6\u6cb3") is None and kb_rag.normalize_kb_mode(None) is None)
        check("mode: profile structured=(None,hybrid)",
              kb_rag.kb_mode_profile("structured") == (None, "hybrid")
              and kb_rag.kb_mode_profile(None) == (None, "hybrid"))
        check("mode: profile full=(.rag_index_full,rerank)",
              kb_rag.kb_mode_profile("full") == (kb_rag.FULL_INDEX_DIRNAME, "rerank"))
        check("trigger: \u6df1\u6316/\u770b\u539f\u6587 → full",
              kb_rag.detect_kb_mode("\u5e2e\u6211\u6df1\u6316\u8fd9\u5bb6\u516c\u53f8") == "full"
              and kb_rag.detect_kb_mode("\u770b\u539f\u6587") == "full")
        check("trigger: \u5feb\u901f → structured（\u663e\u5f0f\u4f18\u5148）",
              kb_rag.detect_kb_mode("\u5feb\u901f\u770b\u770b") == "structured"
              and kb_rag.detect_kb_mode("\u5feb\u901f\u6df1\u6316") == "structured")
        check("trigger: \u65e0\u89e6\u53d1\u8bcd → None",
              kb_rag.detect_kb_mode("\u6db2\u51b7\u670d\u52a1\u5668") is None)

        from intelligence.cli import _resolve_kb_mode  # noqa: E402
        check("cli: 默认 → (hybrid,None,'')",
              _resolve_kb_mode("\u6db2\u51b7", None, "hybrid") == ("hybrid", None, ""))
        check("cli: --kb-mode full → (rerank,.rag_index_full,'')",
              _resolve_kb_mode("\u6db2\u51b7", "full", "hybrid") == ("rerank", kb_rag.FULL_INDEX_DIRNAME, ""))
        check("cli: NL \u6df1\u6316 → full",
              _resolve_kb_mode("\u6df1\u6316\u6db2\u51b7", None, "hybrid") == ("rerank", kb_rag.FULL_INDEX_DIRNAME, ""))
        check("cli: --wiki-rag-mode \u663e\u5f0f\u8986\u76d6",
              _resolve_kb_mode("\u6db2\u51b7", None, "dense") == ("dense", None, ""))
        _rm, _idx, _err = _resolve_kb_mode("\u6db2\u51b7", "\u94f6\u6cb3", "hybrid")
        check("cli: \u975e\u6cd5 --kb-mode → error", _err != "" and _idx is None)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
