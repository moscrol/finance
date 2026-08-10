#!/usr/bin/env python3
"""问答前的 RAG 就绪自检：向量层能不能作为证据用。

为什么需要它：知识库的索引新鲜度守卫在索引与源不一致时 fail-closed，拒绝把召回
结果当证据（这是对的）。但它只在**查询时**才报错，而工作台历史上把该错误显示成
"wiki-rag 检索失败（退出码 3）"，看不出该做什么。实测该状态从 2026-07-29 23:34
起持续了一整天没被发现——期间向量层是唯一召回准确的那层，它一停，问答就只剩
噪声较大的结构化层加盘面数据。

守卫的判定范围只覆盖被索引的目录（wiki/entities、concepts、sources、synthesis、
briefings），并且要求源**已提交**：单跑 rag update 不够，因为索引会记下
source_dirty=true，本身又构成不新鲜。

退出码：0 可用作证据；1 不可用（含补救动作）；2 无法判定（缺路径/脚本）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# 知识库是**平级仓**（与本仓同一父目录），所以从脚本位置上推两级再拼名字，
# 不写死家目录。此前是 Path("/Users/a77/knowledge-base-private")。
# 注意这只是**回退值**：`--kb-root` 与 `KB_ROOT` 环境变量优先级都更高（见 main），
# 所以知识库真放在别处时仍可显式指定，本次改动只是让"没指定"时的猜测不依赖某个人的家目录。
DEFAULT_KB = Path(__file__).resolve().parents[2] / "knowledge-base-private"
INDEXED_DIRS = ("entities", "concepts", "sources", "synthesis", "briefings")


def _index_meta(index_dir: Path) -> dict | None:
    meta = index_dir / "meta.json"
    if not meta.is_file():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _dirty_indexed_paths(kb: Path) -> list[str] | None:
    """索引覆盖目录下未提交的文件。None 表示 git 不可用。"""
    pathspecs = [f"wiki/{name}" for name in INDEXED_DIRS]
    try:
        proc = subprocess.run(
            ["git", "-C", str(kb), "status", "--porcelain", "--", *pathspecs],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return [line[3:].strip().strip('"') for line in proc.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-root", default=os.environ.get("KB_ROOT") or str(DEFAULT_KB))
    parser.add_argument(
        "--index-dir",
        default=os.environ.get("RAG_INDEX_DIR") or "",
        help="默认取 <kb-root>/.rag_index",
    )
    parser.add_argument("--quiet", action="store_true", help="就绪时不输出")
    args = parser.parse_args(argv)

    kb = Path(args.kb_root).expanduser()
    index_dir = Path(args.index_dir).expanduser() if args.index_dir else kb / ".rag_index"

    if not kb.is_dir():
        print(f"[rag-readiness] 无法判定：知识库路径不存在 {kb}", file=sys.stderr)
        return 2
    meta = _index_meta(index_dir)
    if meta is None:
        print(
            f"[rag-readiness] 不可用：索引 meta 缺失或损坏 {index_dir}\n"
            f"  补救：在知识库仓跑 rag update 建索引",
            file=sys.stderr,
        )
        return 1

    problems: list[str] = []
    if meta.get("source_dirty") is True:
        problems.append(
            "索引是在脏工作区上建的（source_dirty=true）"
            "｜补救：提交知识库改动，post-commit hook 会在干净源上重建"
        )
    dirty = _dirty_indexed_paths(kb)
    if dirty is None:
        problems.append("无法读取 git 状态，未能确认索引与源是否一致")
    elif dirty:
        listed = "、".join(dirty[:4]) + (f" 等 {len(dirty)} 项" if len(dirty) > 4 else "")
        problems.append(
            f"索引覆盖目录有 {len(dirty)} 个未提交文件：{listed}"
            "｜补救：提交它们（单跑 rag update 不够，守卫要求源已提交）"
        )

    if problems:
        print("[rag-readiness] 向量层不可用作证据：", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f"[rag-readiness] 就绪 | 构建={meta.get('built_at')} "
            f"| chunks={meta.get('num_chunks')} | revision={str(meta.get('source_git_revision'))[:12]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
