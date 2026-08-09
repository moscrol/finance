#!/usr/bin/env python3
"""Measure relay latency, stability and token-limit behaviour at episode scale.

Why this is separate from ``run_agent_runtime_benchmark.py``: that one runs
whole finance cases through an ``AgentRuntime``, so its latency number mixes
provider time with planning, tool calls and verification.  When an episode
times out you first need to know whether the *provider* is the slow part.
This probe answers only that, one HTTP call at a time.

Three things it exists to keep honest, each learned the expensive way on
2026-08-09 (see docs/verification/2026-08-09-episode-seam-ladder-live.md §5):

1. **User-Agent.**  ``urllib`` defaults to ``Python-urllib/<ver>`` and the
   relay rejects it with HTTP 502 "Upstream access forbidden".  That reads
   like an upstream outage, and curl keeps working, so it is very easy to
   report as "the gateway is unstable".  The first version of this probe
   recorded 24/24 provider failures that were entirely its own.  Production
   sets ``finance-workbench/1.0`` (``llm_refine.py:52``); so does this.
2. **Output tokens, not input tokens, drive latency.**  A 15K-character
   prompt answered in one sentence returns in ~4s; the same prompt asked for
   a detailed analysis takes 26-91s.  Probing with a short answer only will
   tell you the relay is fast and leave the timeout unexplained.
3. **The relay ignores ``max_tokens`` and ``max_completion_tokens``.**
   Requesting 10 returns hundreds with ``finish_reason=stop``.  Generation
   time therefore cannot be bounded by a parameter, only by the prompt.

Usage (needs the production env, e.g. the exports in
``~/.local/bin/start-finance-workbench``)::

    .venv-workbench/bin/python scripts/probe_provider_latency.py \\
        --models gpt-5.6-terra,gpt-5.6-sol --samples 10
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request

# Must match production.  See module docstring, reason 1.
USER_AGENT = os.environ.get("LLM_USER_AGENT", "finance-workbench/1.0")

SHORT_INSTRUCTION = "用一句话说明上面最后一行的成交额。"
LONG_INSTRUCTION = "请据此写一份尽可能详尽的市场结构分析。"

_ROW = (
    "交易日 2026-08-{day:02d}｜上证收盘 {close:.2f}｜涨家数 {adv}｜涨停 {lim}｜"
    "成交额 {amt:.2f} 亿｜板块边际量 {diff:.1f}%\n"
)


def build_prompt(target_chars: int) -> str:
    """Pad with rows shaped like the structured snapshots an episode carries."""

    chunks: list[str] = []
    size = 0
    day = 3
    while size < target_chars:
        text = _ROW.format(
            day=(day % 28) + 1,
            close=3800 + (day * 7.31) % 200,
            adv=2500 + (day * 137) % 2200,
            lim=60 + (day * 13) % 90,
            amt=19000 + (day * 311) % 9000,
            diff=(day * 3.7) % 40,
        )
        chunks.append(text)
        size += len(text)
        day += 1
    return "".join(chunks)


def one_call(
    base: str,
    key: str,
    model: str,
    prompt: str,
    *,
    timeout: float,
) -> dict[str, object]:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "seconds": round(time.monotonic() - started, 2),
            "error": f"HTTP {exc.code}",
            "detail": exc.read()[:200].decode("utf-8", "replace"),
        }
    except Exception as exc:  # noqa: BLE001 — every failure is a data point
        return {
            "ok": False,
            "seconds": round(time.monotonic() - started, 2),
            "error": type(exc).__name__,
            "detail": str(exc)[:200],
        }
    usage = payload.get("usage") or {}
    choice = (payload.get("choices") or [{}])[0]
    return {
        "ok": True,
        "seconds": round(time.monotonic() - started, 2),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "finish_reason": choice.get("finish_reason"),
    }


def summarize(label: str, rows: list[dict[str, object]]) -> None:
    if not rows:
        print(f"{label:34}   ——  未采样")
        return
    good = [float(row["seconds"]) for row in rows if row["ok"]]
    if not good:
        print(f"{label:34} {0:>3}/{len(rows):<3}  —— 全部失败")
    else:
        ordered = sorted(good)
        p90 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))]
        out_tokens = [
            int(row["completion_tokens"])
            for row in rows
            if row["ok"] and row["completion_tokens"]
        ]
        # Normalise by output length: comparing raw seconds across models is
        # what produced the unreliable 2-3 sample ranking this probe replaces.
        #
        # Only meaningful once generation dominates.  On a 21-token answer the
        # fixed round-trip overhead swamps it and the quotient reads "2 tok/s",
        # which looks like a catastrophically slow relay and is not a rate at
        # all.  Below the floor, print nothing rather than a misleading number.
        rate = ""
        total_tokens = sum(out_tokens)
        if out_tokens and total_tokens >= 200 * len(out_tokens):
            total_seconds = sum(good[: len(out_tokens)])
            if total_seconds > 0:
                rate = f"  ≈{total_tokens / total_seconds:.0f} tok/s"
        print(
            f"{label:34} {len(good):>3}/{len(rows):<3}  "
            f"p50={statistics.median(ordered):6.1f}s  p90={p90:6.1f}s  "
            f"max={max(good):6.1f}s{rate}"
        )
    for row in rows:
        if not row["ok"]:
            print(f"{'':34}   ✗ {row['error']}: {str(row.get('detail'))[:80]}")


def check_token_limit(base: str, key: str, model: str) -> None:
    """A limit that is silently ignored is worse than one that errors."""

    print("\n—— token 上限是否生效 ——")
    for field in ("max_tokens", "max_completion_tokens"):
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "user", "content": "请用三百字详细介绍A股的涨跌停制度。"}
                ],
                field: 10,
            }
        ).encode()
        request = urllib.request.Request(
            f"{base}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read())
        except Exception as exc:  # noqa: BLE001
            print(f"  {field}=10 → {type(exc).__name__}: {exc}")
            continue
        usage = payload.get("usage") or {}
        choice = (payload.get("choices") or [{}])[0]
        got = usage.get("completion_tokens")
        reason = choice.get("finish_reason")
        verdict = "生效" if reason == "length" else "**被忽略**"
        print(
            f"  {field}=10 → completion_tokens={got}  "
            f"finish_reason={reason}  {verdict}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="gpt-5.6-terra")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--long-samples", type=int, default=3)
    parser.add_argument("--prompt-chars", type=int, default=15000)
    parser.add_argument("--timeout", type=float, default=200.0)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY", "")
    if not base or not key:
        print("需要生产 env：LLM_BASE_URL 与 OPENAI_API_KEY")
        return 2

    padding = build_prompt(args.prompt_chars)
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    print(f"prompt chars={len(padding)}  UA={USER_AGENT}  base={base}")

    collected: dict[str, dict[str, list[dict[str, object]]]] = {}
    for model in models:
        collected[model] = {}
        for kind, instruction, count in (
            ("短输出", SHORT_INSTRUCTION, args.samples),
            ("长输出", LONG_INSTRUCTION, args.long_samples),
        ):
            rows: list[dict[str, object]] = []
            for index in range(count):
                row = one_call(
                    base,
                    key,
                    model,
                    f"{padding}\n\n{instruction}",
                    timeout=args.timeout,
                )
                rows.append(row)
                mark = "." if row["ok"] else "X"
                print(
                    f"{model} {kind} [{index + 1}/{count}] {mark} "
                    f"{row['seconds']}s tok={row.get('completion_tokens')}",
                    flush=True,
                )
            collected[model][kind] = rows

    print("\n" + "=" * 78)
    for model, kinds in collected.items():
        for kind, rows in kinds.items():
            summarize(f"{model} / {kind}", rows)
    check_token_limit(base, key, models[0])

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "prompt_chars": len(padding),
                    "user_agent": USER_AGENT,
                    "base_url": base,
                    "results": collected,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nraw → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
