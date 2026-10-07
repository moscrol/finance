#!/usr/bin/env python3
"""从画像投影允许字段，生成待人工审阅的框架候选；不自动发布或保证正文脱敏。

    python3 scripts/export_perspective_framework.py --perspective example --user me
    python3 scripts/export_perspective_framework.py --perspective example --user me --out /tmp/framework.json

## 为什么需要这个

``intelligence/users/<user>/perspectives/`` 被 ``.gitignore:114`` 排除，
``perspective_lab`` 的文档头写明原因是「版权 + 隐私边界」：``articles/<id>/raw/``
存的是第三方文章原文，画像本身也可能夹带 360 字的 ``excerpt`` 片段与带日期的
``contradictions``（单次观察，近似私人复盘记录）。

但「不能整个推上去」不等于「不能分享」。真正该分享的是**蒸馏后的框架**——
market_lenses / risk_triggers / reasoning_patterns / falsification_style 这些
可迁移的分析结构，恰恰是 perspective_lab 设计里「学框架不学口癖」的那一半。
框架字段也可能复述来源或包含个人信息；字段属于框架不等于获得披露权利。

## 为什么是白名单不是黑名单

黑名单（「去掉 raw、去掉 excerpt」）在这件事上是错的形状：画像 schema 以后
新增任何字段，默认都会**漏出去**，而且漏的时候没有任何提示。脱敏工具只会往
一个方向出错，而那个方向是不可撤销的——推上公开仓的东西，删了也还在 git 历史里。

所以只放行显式列出的顶层和子字段，其余丢弃并在报告里点名。
这不是自动发布许可：允许字段的散文仍可能含隐私或来源原文，披露前必须人工审阅。
运行时画像路径统一走 userspace（支持 FORESIGHT_USERS_DIR），不读冻结旧根。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# 放行名单：perspective_lab 设计里「可迁移的分析结构」那一组。
# 每一项都要能回答「它是框架还是来源」——是框架才进。
ALLOW = {
    "display_name": "视角名",
    "type": "视角类型",
    "market_lenses": "镜头：看市场的维度与权重",
    "opportunity_preferences": "机会偏好",
    "risk_triggers": "风险触发条件",
    "evidence_hierarchy": "证据层级排序",
    "reasoning_patterns": "推理模式（名 + 规则）",
    "anti_patterns": "反模式：明确不做什么",
    "falsification_style": "证伪风格：怎么给失效条件",
    "honest_boundaries": "诚实边界：该视角不适用于哪些领域",
}

# 显式拒绝名单，只为了**解释原因**；真正的门是上面的白名单。
# 列在这里是为了让人看到「这些我是故意不导的」，而不是「这些我忘了」。
DENY_REASON = {
    "contradictions": "带日期的单次观察，形状接近私人复盘记录，不是可迁移框架",
    "sources": "含 allowed_sources 等来源配置，指向本地文章台账",
    "confidence": "含 article_count 等样本元信息；用 --with-confidence 可单独带上",
    "voice_guidance": "语气指引。设计明写「学框架不学口癖」，分享框架时不需要它",
    "schema_version": "内部字段",
    "id": "内部字段",
    "created_at": "内部字段",
    "updated_at": "内部字段",
}

# 疑似夹带原文：长句 + 引号 / 省略号残留（excerpt 截断会留「…」）。
# 这只是提醒；白名单约束字段结构，不验证散文内容的隐私或披露许可。
LONG_TEXT = 180
QUOTEY = re.compile(r"[“”「」『』]|…|\.{3}")


def _walk_strings(obj: Any, path: str = ""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")


def load_profile(pid: str, user: str | None) -> tuple[dict[str, Any], str]:
    from intelligence.services.perspective_lab import _BUILTIN_PROFILES, profile_path, resolve_perspective_id
    from intelligence.userspace import user_space

    pid = resolve_perspective_id(pid)
    if user:
        p = profile_path(user_space(user), pid)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")), str(p)
    if pid in _BUILTIN_PROFILES:
        return dict(_BUILTIN_PROFILES[pid]), f"内置画像 _BUILTIN_PROFILES[{pid!r}]"
    raise SystemExit(
        f"找不到画像 {pid}。\n"
        f"  蒸馏画像由 userspace 定位，支持 FORESIGHT_USERS_DIR（要 --user）；\n"
        f"  内置的有：{sorted(_BUILTIN_PROFILES)}"
    )


def _project_fields(prof: dict[str, Any], *, with_confidence: bool) -> tuple[dict[str, Any], list[str]]:
    """逐层白名单；不能让允许的父字段变成任意字典的披露通道。"""
    allowed_records = {
        "market_lenses": {"name": str, "description": str, "weight": (int, float)},
        "reasoning_patterns": {"name": str, "rule": str},
        "confidence": {"article_count": int, "known_gaps": list},
    }
    dropped = []

    def record(value, fields, path):
        if not isinstance(value, dict):
            raise ValueError(f"{path}: 必须是对象")
        result = {}
        for key, val in value.items():
            if key not in fields:
                dropped.append(f"{path}.{key}")
                continue
            if not isinstance(val, fields[key]) or (key == "known_gaps" and any(not isinstance(x, str) for x in val)):
                raise ValueError(f"{path}.{key}: 非预期类型，拒绝导出")
            result[key] = val
        return result

    out = {}
    for key in [*ALLOW, *(["confidence"] if with_confidence else [])]:
        val = prof.get(key)
        if val in (None, [], {}, ""):
            continue
        if key == "confidence":
            out[key] = record(val, allowed_records[key], key)
        elif key in allowed_records:
            if not isinstance(val, list):
                raise ValueError(f"{key}: 必须是列表")
            out[key] = [record(v, allowed_records[key], f"{key}[{i}]") for i, v in enumerate(val)]
        elif key in {"display_name", "type"}:
            if not isinstance(val, str):
                raise ValueError(f"{key}: 必须是字符串")
            out[key] = val
        else:
            if not isinstance(val, list) or any(not isinstance(v, str) for v in val):
                raise ValueError(f"{key}: 必须是字符串列表")
            out[key] = list(val)
    return out, dropped


def export(pid: str, user: str | None, *, with_confidence: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    prof, src = load_profile(pid, user)

    out, nested_dropped = _project_fields(prof, with_confidence=with_confidence)

    dropped_known = {k: DENY_REASON[k] for k in prof if k in DENY_REASON and k not in out}
    # 白名单之外、也不在解释名单里的——schema 长出了新东西，必须点名。
    unknown = sorted(set(prof) - set(ALLOW) - set(DENY_REASON))

    flags = []
    for path, s in _walk_strings(out):
        if len(s) >= LONG_TEXT or QUOTEY.search(s):
            flags.append({"field": path, "len": len(s), "head": s[:70]})

    report = {
        "source": src,
        "exported_fields": sorted(out),
        "dropped_with_reason": dropped_known,
        "dropped_unknown": unknown,
        "dropped_nested": nested_dropped,
        "possible_verbatim": flags,
        "review_required": "仅做字段投影，不证明散文没有隐私或版权原文；披露前需人工确认。",
    }
    return out, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perspective", required=True)
    ap.add_argument("--user")
    ap.add_argument("--out", help="写到文件；不给就打到 stdout")
    ap.add_argument("--with-confidence", action="store_true", help="带上 article_count / known_gaps")
    ap.add_argument("--quiet", action="store_true", help="只出 JSON，不出报告（报告走 stderr）")
    a = ap.parse_args(argv)

    data, rep = export(a.perspective, a.user, with_confidence=a.with_confidence)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        print(text)

    err = sys.stderr
    print(f"\n来源：{rep['source']}", file=err)
    print(f"已导出字段（{len(rep['exported_fields'])}）：{rep['exported_fields']}", file=err)
    if rep["dropped_with_reason"]:
        print("\n故意没导（白名单外）：", file=err)
        for k, why in rep["dropped_with_reason"].items():
            print(f"  - {k}：{why}", file=err)
    if rep["dropped_unknown"]:
        print(
            f"\n⚠ 画像里有 {len(rep['dropped_unknown'])} 个本工具不认识的字段，**没有导出**："
            f"{rep['dropped_unknown']}\n"
            "   schema 长出了新东西。确认它是框架（该导）还是来源（不该导）后，"
            "再决定要不要加进 ALLOW。",
            file=err,
        )
    print(rep["review_required"], file=err)
    if rep["dropped_nested"]:
        print(f"已丢弃未获准子字段：{rep['dropped_nested']}", file=err)
    if rep["possible_verbatim"]:
        print(
            f"\n⚠ 这 {len(rep['possible_verbatim'])} 处看着像夹带了原文片段"
            "（超长句，或残留引号/省略号——excerpt 截断会留「…」）。\n"
            "   白名单已经挡掉了 raw 与 excerpt 字段，这里只是提醒你再扫一眼：",
            file=err,
        )
        for f in rep["possible_verbatim"][:12]:
            print(f"     {f['field']}（{f['len']} 字）：{f['head']}…", file=err)
    if a.out:
        print(f"\n已写入 {a.out}", file=err)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
