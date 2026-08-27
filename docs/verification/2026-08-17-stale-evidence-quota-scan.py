#!/usr/bin/env python3
"""只读重扫：top-8 截断对 superseded 提醒的封杀面。

不改 intelligence/。数字进
`docs/superpowers/specs/2026-08-17-stale-evidence-quota-decision.md`。

用法：先有 `KNOWLEDGE_WIKI`（workbench 启动器会 export），再：

    PYTHONPATH=<仓根> python docs/verification/2026-08-17-stale-evidence-quota-scan.py

解释器要用仓内 workbench venv，不要用宿主 python3。
"""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

from intelligence.adapters.knowledge import (
    KnowledgeAdapter,
    _evidence_key,
    evidence_status,
)

LIMITS = (8, 12, 16, 24, 50)


def _items(wiki: str) -> list[dict[str, Any]]:
    raw = json.load(open(os.path.join(wiki, "relations/evidence_index.json")))
    if isinstance(raw, list):
        return [i for i in raw if isinstance(i, dict)]
    return [i for i in (raw.get("items") or []) if isinstance(i, dict)]


def _line_chars(item: dict[str, Any]) -> tuple[int, int]:
    mark = " ⚠️已被新证据取代" if evidence_status(item) == "superseded" else ""
    line = (
        f"{item.get('target')}：{str(item.get('evidence') or '')[:80]}"
        f"（{item.get('source')}, {item.get('source_date') or '无日期'}, "
        f"质量 {item.get('confidence') or '?'}{mark}） [R]"
    )
    replacement = str(item.get("superseded_by") or item.get("status_note") or "").strip()
    suffix = f"，新证据：{replacement}" if replacement else ""
    note = (
        f"{item.get('target')} 该条证据已被取代{suffix}，只能作历史参照，不能当作当前事实 [R]"
        if evidence_status(item) == "superseded"
        else ""
    )
    return len(line), len(note)


def _pointer(item: dict[str, Any]) -> bool:
    return bool(str(item.get("superseded_by") or item.get("status_note") or "").strip())


def main() -> None:
    wiki = os.environ.get("KNOWLEDGE_WIKI")
    if not wiki:
        raise SystemExit("KNOWLEDGE_WIKI is required")
    ka = KnowledgeAdapter(wiki)
    items = _items(wiki)
    print("wiki", wiki)
    print("n_items", len(items))
    print("file_status", dict(Counter(evidence_status(i) for i in items)))

    file_hosts = sorted(
        {i.get("target") for i in items if evidence_status(i) == "superseded"}
    )
    print("file_superseded_hosts", len(file_hosts), file_hosts)

    overlay = json.load(open(os.path.join(wiki, "relations/invalidation_links.json")))
    links = overlay.get("links") or []
    print(
        "overlay_links",
        len(links),
        dict(Counter(str(link.get("strength")) for link in links)),
    )
    idx = ka._invalidation_overlay_index()
    print("overlay_index_keys", len(idx), dict(Counter(v.get("strength") for v in idx.values())))
    matched_hosts: set[str] = set()
    matched_soft = matched_hard = 0
    for item in items:
        link = idx.get(_evidence_key(item))
        if not link:
            continue
        matched_hosts.add(str(item.get("target") or ""))
        if link.get("strength") == "hard":
            matched_hard += 1
        else:
            matched_soft += 1
    print("overlay_matched_soft", matched_soft, "hard", matched_hard, "hosts", sorted(matched_hosts))

    adapter_hosts: list[str] = []
    for target in sorted(set(file_hosts) | matched_hosts):
        full = ka.get_evidence(target, limit=10_000).get("items") or []
        n_sup = sum(1 for it in full if evidence_status(it) == "superseded")
        if n_sup:
            adapter_hosts.append(str(target))
    print("adapter_superseded_hosts", len(adapter_hosts), adapter_hosts)

    print("\n=== curve (adapter-visible superseded) ===")
    print("host\tn\tact\tsup\tfirst_rank\tneed_limit\t" + "\t".join(f"in{lim}" for lim in LIMITS))
    for target in adapter_hosts:
        full = ka.get_evidence(target, limit=10_000).get("items") or []
        n_act = sum(1 for it in full if evidence_status(it) != "superseded")
        n_sup = sum(1 for it in full if evidence_status(it) == "superseded")
        first = next(
            (i for i, it in enumerate(full, 1) if evidence_status(it) == "superseded"),
            None,
        )
        ins = [
            str(sum(1 for it in full[:lim] if evidence_status(it) == "superseded"))
            for lim in LIMITS
        ]
        print(
            f"{target}\t{len(full)}\t{n_act}\t{n_sup}\t{first}\t{n_act + 1}\t"
            + "\t".join(ins)
        )

    print("\n=== coverage ===")
    total_edges = 0
    host_hits = {lim: 0 for lim in LIMITS}
    edge_hits = {lim: 0 for lim in LIMITS}
    for target in adapter_hosts:
        full = ka.get_evidence(target, limit=10_000).get("items") or []
        stales = [it for it in full if evidence_status(it) == "superseded"]
        total_edges += len(stales)
        for lim in LIMITS:
            n = sum(1 for it in full[:lim] if evidence_status(it) == "superseded")
            edge_hits[lim] += n
            if n:
                host_hits[lim] += 1
    n_hosts = len(adapter_hosts)
    for lim in LIMITS:
        print(
            f"limit={lim} hosts {host_hits[lim]}/{n_hosts} "
            f"edges {edge_hits[lim]}/{total_edges}"
        )
    print(f"quota<=1 hosts {n_hosts}/{n_hosts} edges {n_hosts}/{total_edges} (1/host)")

    print("\n=== quota squeeze (file-status hosts, pointer-first) ===")
    for target in file_hosts:
        full = ka.get_evidence(target, limit=10_000).get("items") or []
        actives = [it for it in full if evidence_status(it) != "superseded"]
        stales = [it for it in full if evidence_status(it) == "superseded"]
        stales.sort(key=lambda it: (0 if _pointer(it) else 1))
        squeezed = len(actives) >= 8
        dropped = actives[7] if squeezed else None
        kept = stales[0]
        print(
            json.dumps(
                {
                    "host": target,
                    "n_active": len(actives),
                    "n_stale": len(stales),
                    "in8": sum(1 for it in full[:8] if evidence_status(it) == "superseded"),
                    "squeezed": squeezed,
                    "dropped_active": None
                    if dropped is None
                    else {
                        "source_date": dropped.get("source_date"),
                        "source": dropped.get("source"),
                        "evidence": str(dropped.get("evidence") or "")[:120],
                    },
                    "kept_stale": {
                        "source_date": kept.get("source_date"),
                        "source": kept.get("source"),
                        "evidence": str(kept.get("evidence") or "")[:120],
                        "has_pointer": _pointer(kept),
                    },
                },
                ensure_ascii=False,
            )
        )

    print("\n=== char cost (file-status hosts) ===")
    active_c: list[int] = []
    stale_c: list[int] = []
    note_c: list[int] = []
    for target in file_hosts:
        for it in ka.get_evidence(target, limit=10_000).get("items") or []:
            lc, nc = _line_chars(it)
            if evidence_status(it) == "superseded":
                stale_c.append(lc)
                note_c.append(nc)
            else:
                active_c.append(lc)

    def _stats(name: str, xs: list[int]) -> None:
        xs = sorted(xs)
        print(
            f"{name} n={len(xs)} min={xs[0]} p50={xs[len(xs)//2]} "
            f"mean={sum(xs)/len(xs):.1f} max={xs[-1]}"
        )

    _stats("active_line", active_c)
    _stats("stale_line", stale_c)
    _stats("stale_note", note_c)

    sizes = Counter(i.get("target") for i in items)
    n_hosts_all = len(sizes)
    grow = sum(1 for n in sizes.values() if n > 8)
    extra12 = sum(max(0, min(n, 12) - 8) for n in sizes.values())
    extra24 = sum(max(0, min(n, 24) - 8) for n in sizes.values())
    extra50 = sum(max(0, min(n, 50) - 8) for n in sizes.values())
    print("\n=== global lift extras (all evidence_index hosts) ===")
    print("hosts", n_hosts_all, "would_grow", grow)
    print("mean_extra_items 8->12", extra12 / n_hosts_all)
    print("mean_extra_items 8->24", extra24 / n_hosts_all)
    print("mean_extra_items 8->50", extra50 / n_hosts_all)


if __name__ == "__main__":
    main()
