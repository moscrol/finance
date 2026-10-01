#!/usr/bin/env python3
"""数值条件门禁重放 A/B：用存证 run 的真实草稿 + 真实证据，在两份代码上各跑一遍核验器。

``date_mask_ab.py`` 只扫答卷文本，只能回答「哪些 token 新进入审计」；证据侧的放宽（单位写在
字段名里的证据值，2026-10-01 commit 15）会让待核**消失**，要证明消失的全是正确复述，必须把
证据和草稿一起喂给门禁。本脚本从 ``continuous-episode.json`` 按类型注解还原
``VerifiedEpisodeOutcome``（structural_verifier + contract），调用
``_novel_numeric_condition_tokens``，逐句输出被挂待核的数量 token。

用法（两份代码各跑一次，再比较）::

    python scripts/numeric_gate_replay_ab.py run  --runs-dir RUNS --code-root MAIN_CHECKOUT --out /tmp/a.jsonl
    python scripts/numeric_gate_replay_ab.py run  --runs-dir RUNS --code-root BRANCH_CHECKOUT --out /tmp/b.jsonl
    python scripts/numeric_gate_replay_ab.py diff /tmp/a.jsonl /tmp/b.jsonl

``diff`` 逐句列出「只在 A 挂 / 只在 B 挂」的 token 及句子原文和该句绑定证据里出现的同数字
片段，供人工判定：消失的应是正确复述，新增的应是自拟阈值。还原失败的 run 计数并列出原因，
不静默跳过。
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import json
import re
import sys
import types
import typing
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any


def _build(tp: Any, value: Any) -> Any:  # noqa: C901 - 一个类型分派表
    if value is None:
        return None
    if tp is Any or tp is object:
        return value
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin in (typing.Union, types.UnionType):
        errors = []
        for arg in args:
            if arg is type(None):
                continue
            try:
                return _build(arg, value)
            except Exception as exc:  # noqa: BLE001 - 依次尝试联合类型分支
                errors.append(exc)
        raise TypeError(f"no union branch of {tp} fits {type(value).__name__}: {errors[:2]}")
    if origin is typing.Literal:
        return value
    if origin in (tuple,):
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_build(args[0], item) for item in value)
        if not args:
            return tuple(value)
        return tuple(_build(arg, item) for arg, item in zip(args, value, strict=False))
    if origin in (list, typing.Sequence, __import__("collections.abc").abc.Sequence):
        return [_build(args[0] if args else Any, item) for item in value]
    if origin in (frozenset, set):
        built = (_build(args[0] if args else Any, item) for item in value)
        return frozenset(built) if origin is frozenset else set(built)
    if origin in (dict, typing.Mapping, __import__("collections.abc").abc.Mapping):
        kt, vt = args if args else (Any, Any)
        return {_build(kt, k): _build(vt, v) for k, v in value.items()}
    if isinstance(tp, type):
        if dataclasses.is_dataclass(tp):
            if not isinstance(value, dict):
                raise TypeError(f"{tp.__name__} expects object, got {type(value).__name__}")
            hints = typing.get_type_hints(tp)
            kwargs = {
                field.name: _build(hints.get(field.name, Any), value[field.name])
                for field in dataclasses.fields(tp)
                if field.init and field.name in value
            }
            return tp(**kwargs)
        if issubclass(tp, enum.Enum):
            return tp(value)
        if tp is Decimal:
            return Decimal(str(value))
        if tp is float and isinstance(value, (int, float)):
            return float(value)
        if tp in (str, int, bool) and not isinstance(value, tp):
            raise TypeError(f"expected {tp.__name__}, got {type(value).__name__}")
        return value
    return value


def _load_verifier(code_root: Path):
    sys.path.insert(0, str(code_root.resolve()))
    from intelligence.services import episode_semantic_verifier as esv  # noqa: PLC0415
    from intelligence.services.episode_verifier import VerifiedEpisodeOutcome  # noqa: PLC0415

    loaded = Path(esv.__file__).resolve()
    if code_root.resolve() not in loaded.parents:
        raise SystemExit(f"verifier imported from {loaded}, not from --code-root {code_root}")
    return esv, VerifiedEpisodeOutcome


def _restore(payload: dict[str, Any], verified_cls: Any) -> Any:
    structural = dict(payload["structural_verifier"])
    structural["contract"] = payload.get("contract")
    return _build(verified_cls, structural)


def cmd_run(args: argparse.Namespace) -> int:
    esv, verified_cls = _load_verifier(Path(args.code_root))
    paths = sorted(Path(args.runs_dir).expanduser().rglob("continuous-episode.json"))
    restored = failed = flagged_runs = 0
    reasons: Counter[str] = Counter()
    with open(args.out, "w", encoding="utf-8") as out:
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if "structural_verifier" not in payload:
                    raise KeyError("structural_verifier")
                verified = _restore(payload, verified_cls)
                sentences = esv._numbered_sentences(verified.outcome.draft)
                tokens = esv._novel_numeric_condition_tokens(sentences, verified)
            except Exception as exc:  # noqa: BLE001 - 还原失败逐类计数，不中断
                failed += 1
                reasons[f"{type(exc).__name__}: {str(exc)[:90]}"] += 1
                continue
            restored += 1
            by_index = {int(s["index"]): str(s["text"]) for s in sentences}
            if tokens:
                flagged_runs += 1
            out.write(
                json.dumps(
                    {
                        "run": str(path.parent),
                        "flagged": {
                            str(index): {"sentence": by_index.get(int(index), ""), "tokens": sorted(map(str, toks))}
                            for index, toks in sorted(tokens.items())
                        },
                        "evidence": [item.detail for item in verified.outcome.evidence][:200],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"code-root={args.code_root} runs={len(paths)} restored={restored} failed={failed} runs_with_flags={flagged_runs}")
    for reason, count in reasons.most_common(8):
        print(f"  restore-failure x{count}: {reason}")
    return 0 if restored else 1


def _evidence_snippets(evidence: list[str], token: str) -> list[str]:
    digits = re.findall(r"\d+(?:\.\d+)?", token)
    if not digits:
        return []
    key = digits[0]
    hits = []
    for detail in evidence:
        for part in re.split(r"[；;\n]", detail):
            if key in part:
                hits.append(part.strip()[:80])
    return hits[:4]


def cmd_diff(args: argparse.Namespace) -> int:
    def load(path: str) -> dict[str, dict[str, Any]]:
        rows = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            rows[row["run"].split("/runs/")[-1]] = row
        return rows

    a, b = load(args.a), load(args.b)
    common = sorted(set(a) & set(b))
    gone: list[tuple[str, str, str, list[str]]] = []
    new: list[tuple[str, str, str, list[str]]] = []
    for run in common:
        fa, fb = a[run]["flagged"], b[run]["flagged"]
        for index in sorted(set(fa) | set(fb), key=int):
            ta = set(fa.get(index, {}).get("tokens", ()))
            tb = set(fb.get(index, {}).get("tokens", ()))
            sentence = (fa.get(index) or fb.get(index))["sentence"]
            for token in sorted(ta - tb):
                gone.append((run, token, sentence, _evidence_snippets(b[run]["evidence"], token)))
            for token in sorted(tb - ta):
                new.append((run, token, sentence, _evidence_snippets(b[run]["evidence"], token)))
    count_a = sum(len(v["tokens"]) for r in common for v in a[r]["flagged"].values())
    count_b = sum(len(v["tokens"]) for r in common for v in b[r]["flagged"].values())
    print(f"common runs={len(common)} (only A={len(set(a) - set(b))}, only B={len(set(b) - set(a))})")
    print(f"flagged tokens: A={count_a} B={count_b}  disappeared={len(gone)} appeared={len(new)}")
    for title, rows in (("== 只在 A 挂（B 放行）——应全是正确复述", gone), ("== 只在 B 挂（A 放行）——应全是自拟阈值", new)):
        print(title)
        for run, token, sentence, snippets in rows[: args.limit]:
            print(f"  [{token}] {sentence[:140]}")
            print(f"      run={run}")
            for snippet in snippets:
                print(f"      证据: {snippet}")
        if len(rows) > args.limit:
            print(f"  ... {len(rows) - args.limit} more")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--runs-dir", required=True)
    run.add_argument("--code-root", default=str(Path(__file__).resolve().parents[1]))
    run.add_argument("--out", required=True)
    diff = sub.add_parser("diff")
    diff.add_argument("a")
    diff.add_argument("b")
    diff.add_argument("--limit", type=int, default=60)
    args = parser.parse_args(argv)
    return cmd_run(args) if args.cmd == "run" else cmd_diff(args)


if __name__ == "__main__":
    raise SystemExit(main())
