#!/usr/bin/env python3
"""skill-dispatcher · 顶层路由器

扫描 skills/ 下所有 SKILL.md 的 frontmatter，提取触发词和描述，
对用户输入做关键词匹配，返回最佳匹配的 skill 路径和 SKILL.md 内容。

用法：
  python3 skills/dispatcher/scripts/route.py "完成6.24的全量复盘"
  python3 skills/dispatcher/scripts/route.py "搜研报 消费电子"
  python3 skills/dispatcher/scripts/route.py --list          # 列出所有可路由 skill
  python3 skills/dispatcher/scripts/route.py --json "复盘"   # JSON 输出

工作原理：
  1. 遍历 skills/*/SKILL.md，解析 YAML frontmatter 中的 name / description
  2. 从 description 中提取"触发词：xxx、yyy、zzz"列表
  3. 对用户输入做三层匹配：
     a) 精确触发词命中（最高优先）
     b) 触发词子串命中
     c) description 关键词命中（最低优先）
  4. 输出匹配结果：skill 名称、路径、置信度、SKILL.md 首段摘要
  5. 无匹配时提示 fallback 路径（通用 DuckDB 查询 / 直接问用户）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]  # skills/dispatcher/scripts/ → 金融/
SKILLS_DIR = ROOT / "skills"

# ── 不可路由的 skill（工具库、非独立触发） ──
EXCLUDED = {"ifind", "lib", "dispatcher"}

# ── 特殊路由规则（高风险任务先走 task-planner） ──
TASK_PLANNER_TRIGGERS = {
    "批量", "批处理", "大回填", "全量回补", "多天", "跨日期",
    "开新题材", "新概念图谱",
}


def parse_skill(skill_dir: Path) -> dict | None:
    """解析单个 skill 目录的 SKILL.md frontmatter。"""
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return None
    
    text = md.read_text(encoding="utf-8", errors="replace")
    
    # 提取 YAML frontmatter
    fm_match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        return None
    fm = fm_match.group(1)
    
    # name
    name_m = re.search(r"^name:\s*(.+)", fm, re.M)
    name = name_m.group(1).strip() if name_m else skill_dir.name
    
    # description（可能多行）
    desc_m = re.search(r"^description:\s*(.+?)(?=\n\w+:|\Z)", fm, re.DOTALL | re.M)
    description = desc_m.group(1).strip().replace("\n", " ") if desc_m else ""
    
    # 提取触发词（支持多种格式）
    triggers: list[str] = []
    # 格式1: "触发词：xxx、yyy" 或 "触发词严格限定：xxx、yyy"
    tw_m = re.search(r"触发词[^：:]*[：:]\s*(.+?)(?:\.|。|仅当|$)", description)
    if tw_m:
        raw = tw_m.group(1)
        triggers = [t.strip() for t in re.split(r"[、,，/]", raw) if t.strip()]
    
    # 格式2: "Use when the user asks to xxx, yyy"
    use_m = re.search(r"Use when[^.]*?asks?\s+to\s+(.+?)(?:\.|,\s*or\s|$)", description, re.I)
    if use_m:
        en_triggers = [t.strip() for t in re.split(r"[,，、/]", use_m.group(1)) if t.strip()]
        triggers.extend(en_triggers)
    
    # 格式3: "触发：xxx" (简写)
    tw_m2 = re.search(r"(?<!\S)触发[：:]\s*(.+?)(?:\.|。|$)", description)
    if tw_m2 and not tw_m:
        triggers.extend([t.strip() for t in re.split(r"[、,，/]", tw_m2.group(1)) if t.strip()])
    
    # pattern metadata
    pattern_m = re.search(r"pattern:\s*(.+)", fm, re.M)
    pattern = pattern_m.group(1).strip() if pattern_m else ""
    
    # also metadata
    also_m = re.search(r"also:\s*\[(.+?)\]", fm)
    also = [a.strip() for a in also_m.group(1).split(",")] if also_m else []
    
    # has scripts?
    scripts_dir = skill_dir / "scripts"
    has_scripts = scripts_dir.is_dir() and any(scripts_dir.glob("*.py"))
    
    # 首段摘要（frontmatter 后第一段文字）
    body = text[fm_match.end():].strip()
    first_para = ""
    for line in body.split("\n"):
        if line.startswith("#"):
            continue
        if line.strip():
            first_para = line.strip()
            break
    
    return {
        "name": name,
        "dir": skill_dir.name,
        "path": str(skill_dir.relative_to(ROOT)),
        "description": description,
        "triggers": triggers,
        "pattern": pattern,
        "also": also,
        "has_scripts": has_scripts,
        "summary": first_para[:200],
    }


def load_all_skills() -> list[dict]:
    """扫描 skills/ 下所有 SKILL.md，返回解析结果列表。"""
    skills = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name in EXCLUDED or d.name.startswith("."):
            continue
        info = parse_skill(d)
        if info:
            skills.append(info)
    return skills


def match_skill(query: str, skills: list[dict]) -> list[dict]:
    """对用户输入做三层匹配，返回按得分排序的结果列表。
    
    得分规则：
      - skill name 精确匹配：+200
      - 精确触发词匹配（query 包含完整触发词）：+50 + len(触发词)*10
        （更长的触发词 = 更精确 = 更高分；"全量复盘" > "复盘"）
      - 触发词子串匹配（query 是触发词子串）：+30
      - description 关键词匹配：+5 / 词
    """
    query_lower = query.lower().strip()
    results = []
    
    for sk in skills:
        score = 0
        matched_triggers = []
        
        # name 精确匹配
        if sk["name"].lower() == query_lower or sk["dir"].lower() == query_lower:
            score += 200
        
        # 触发词匹配
        for trig in sk["triggers"]:
            trig_lower = trig.lower().strip()
            if not trig_lower:
                continue
            if trig_lower in query_lower:
                # 更长的触发词得分更高：
                # "全量复盘"(4字) = 50 + 40 = 90
                # "复盘"(2字) = 50 + 20 = 70
                score += 50 + len(trig_lower) * 10
                matched_triggers.append(trig)
            elif query_lower in trig_lower:
                score += 30
                matched_triggers.append(f"~{trig}")
            # 2-gram overlap for longer triggers
            elif len(trig_lower) >= 4:
                overlap = sum(1 for i in range(len(trig_lower) - 1)
                              if trig_lower[i:i+2] in query_lower)
                if overlap >= 2:
                    score += overlap * 5
                    matched_triggers.append(f"≈{trig}")
        
        # description 关键词匹配
        desc_lower = sk["description"].lower()
        # 提取 query 中 >= 2字 的中文词
        query_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", query_lower)
        query_tokens += re.findall(r"[a-z]{3,}", query_lower)
        for tok in query_tokens:
            if tok in desc_lower:
                score += 5
        
        if score > 0:
            results.append({
                **sk,
                "score": score,
                "matched_triggers": matched_triggers,
            })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def check_task_planner_gate(query: str) -> bool:
    """检查是否应该先走 task-planner 采访。"""
    query_lower = query.lower()
    return any(t in query_lower for t in TASK_PLANNER_TRIGGERS)


def format_output(results: list[dict], query: str, as_json: bool = False) -> str:
    """格式化输出。"""
    if as_json:
        return json.dumps(results[:5], ensure_ascii=False, indent=2)
    
    lines = []
    needs_planner = check_task_planner_gate(query)
    
    if needs_planner:
        lines.append("⚠️  检测到批量/高风险关键词 → 建议先走 task-planner 采访前置")
        lines.append(f"   路径: skills/task-planner/SKILL.md")
        lines.append("")
    
    if not results:
        lines.append(f"❌ 未匹配到 skill（输入: {query!r}）")
        lines.append("")
        lines.append("Fallback 路径：")
        lines.append("  1. 纯数据查询 → 直接用 DuckDB read-only 查询")
        lines.append("  2. 市场问答 → 先查 DuckDB 有无相关数据，再用知识库补充")
        lines.append("  3. 新功能/新题材 → 走 task-planner 采访后再决定")
        lines.append("  4. 问用户确认意图")
        return "\n".join(lines)
    
    top = results[0]
    lines.append(f"✅ 最佳匹配: {top['name']}")
    lines.append(f"   路径: {top['path']}/SKILL.md")
    lines.append(f"   得分: {top['score']}  命中: {', '.join(top['matched_triggers'][:5])}")
    if top.get("has_scripts"):
        lines.append(f"   脚本: {top['path']}/scripts/")
    lines.append(f"   摘要: {top['description'][:120]}")
    
    if len(results) > 1:
        lines.append("")
        lines.append("其他候选：")
        for r in results[1:3]:
            lines.append(f"  - {r['name']} (得分:{r['score']}) {', '.join(r['matched_triggers'][:3])}")
    
    return "\n".join(lines)


def list_all(skills: list[dict]) -> str:
    """列出所有可路由 skill。"""
    lines = ["可路由 skill 列表：", ""]
    lines.append(f"{'名称':<28} {'触发词（前3）':<50} {'模式':<12}")
    lines.append("-" * 90)
    for sk in skills:
        trigs = "、".join(sk["triggers"][:3]) if sk["triggers"] else "(无显式触发词)"
        lines.append(f"{sk['name']:<28} {trigs:<50} {sk['pattern']:<12}")
    lines.append("")
    lines.append(f"共 {len(skills)} 个可路由 skill")
    return "\n".join(lines)


def run_prime(query: str) -> None:
    """检索前置：路由之后自动跑 prime，把校准+个人库+图谱前缀一并带出（失败只降级不阻断路由）。"""
    import subprocess

    cmd = [sys.executable, "-m", "intelligence.cli", "prime", query]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        print(f"\n[prime 检索前置降级：{exc}]", file=sys.stderr)
        return
    if proc.returncode == 0 and proc.stdout.strip():
        print("\n" + proc.stdout.rstrip())
    else:
        err = (proc.stderr or "").strip().splitlines()
        tail = err[-1] if err else f"exit {proc.returncode}"
        print(f"\n[prime 检索前置降级：{tail}]", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="skill dispatcher 路由器")
    ap.add_argument("query", nargs="*", help="用户输入（自然语言）")
    ap.add_argument("--list", action="store_true", help="列出所有可路由 skill")
    ap.add_argument("--json", action="store_true", help="JSON 格式输出")
    ap.add_argument("--top", type=int, default=3, help="返回前 N 个匹配")
    ap.add_argument("--show-skill", action="store_true", help="同时输出匹配 skill 的 SKILL.md 全文")
    ap.add_argument("--no-prime", action="store_true", help="跳过 prime 检索前置（默认每次路由都附带）")
    args = ap.parse_args()
    
    skills = load_all_skills()
    
    if args.list:
        print(list_all(skills))
        return
    
    query = " ".join(args.query)
    if not query:
        query = sys.stdin.read().strip()
    if not query:
        print("用法: route.py <用户输入>", file=sys.stderr)
        print("      route.py --list", file=sys.stderr)
        sys.exit(2)
    
    results = match_skill(query, skills)
    print(format_output(results[:args.top], query, as_json=args.json))

    # 检索前置：路由后默认附带 prime 前缀（校准+个人库+图谱），--no-prime / --json 时跳过
    if not args.no_prime and not args.json:
        run_prime(query)
    
    # 如果 --show-skill 且有匹配，输出 SKILL.md 全文
    if args.show_skill and results:
        skill_md = SKILLS_DIR / results[0]["dir"] / "SKILL.md"
        if skill_md.exists():
            print("\n" + "=" * 60)
            print(f"SKILL.MD: {results[0]['path']}/SKILL.md")
            print("=" * 60)
            print(skill_md.read_text(encoding="utf-8", errors="replace"))


if __name__ == "__main__":
    main()
