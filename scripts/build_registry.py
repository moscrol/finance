#!/usr/bin/env python3
"""build_registry.py — 工具 / skill 注册表生成器（A-S0：scan + --check，只读）。

定位
----
跨三仓扫描所有 ``skills/<name>/SKILL.md`` 的 frontmatter，汇成一份机读注册表
``skills.registry.json``，并如实记录各 agent 目录（``.claude`` / ``.agents`` /
``.devin`` / ``.windsurf``）对每个 skill 的视图（symlink 视图 vs 物理拷贝），以
及跨仓重复，供后续 ``check-parseability`` 与各 ``AGENTS.md`` 表回填使用。

铁律（与三仓 AGENTS.md 一致）
------------------------------
- **只读**：本脚本只写 ``skills.registry.json`` 一个产物，绝不改任何 SKILL.md /
  agent 目录 / 视图，绝不删文件。
- **确定性 / 幂等**：排序输出；仓库内容不变时再次 ``scan`` 产物字节不变
  （``generated_at`` 在内容不变时保持原值）。
- **扩展 skills-lock.json**：``sourceType`` 取 ``local`` | ``github``，沿用
  ``computedHash`` 语义；lockfile 里的 github 源 skill 也并入注册表。
- **多仓友好**：自动探测同级仓库；``--check`` 在只 checkout 单仓的 CI 环境下，
  仅比对在场仓库拥有的条目（缺仓条目跳过），不会误报。

子命令
------
- ``scan``                扫描 → 生成 / 刷新 ``skills.registry.json``。
- ``--check`` / ``check``  重建并与已提交的注册表比对；有漂移则以非 0 退出（供 CI）。
- ``check-parseability``   元校验：每个 ``SKILL.md`` 的 frontmatter 是否可被扫描器
  正确解析（含非空 name/description，name 与目录名一致）；不可解析则非 0 退出（供 CI）。
- ``backfill-tables --check`` / ``generate-views --check``  校验文档表 / agent 视图是否最新。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 仓库与目录约定
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]            # finance-workspace-private/
REPOS_DIR = REPO_ROOT.parent                               # 同级仓库所在目录
REGISTRY_PATH = REPO_ROOT / "skills.registry.json"
REGISTRY_VERSION = 2
GENERATOR_ID = "scripts/build_registry.py@1"

# 已知仓库：dir 名 -> 短代号（注册表 key 前缀，消除跨仓同名歧义）。
KNOWN_REPOS: list[tuple[str, str]] = [
    ("finance-workspace-private", "ws"),
    ("knowledge-base-private", "kb"),
    ("finance-research-site", "site"),
]

# agent 视图目录（固定顺序，保证确定性）。
AGENT_SKILL_DIRS = [".claude/skills", ".agents/skills", ".devin/skills", ".windsurf/skills"]

# 合法的跨仓拆分声明：同名 skill 在多仓出现属有意拆分，不算漂移。
DECLARED_SPLITS: dict[str, dict[str, object]] = {
    "disclosure-archive": {
        "reason": "有意拆分：金融仓=抓取/capture 侧，知识库仓=apply 侧（见各仓 CLAUDE.md）。",
        "repos": ["ws", "kb"],
    },
}

# backfill-tables：把各仓文档里那张手写 skill 表转成「生成块」。
# 成员（行集合）由 skills.registry.json 权威同步；触发词列人工维护，新增行用
# 注册表触发词预填。块外内容一律不动。
TABLE_MARKER_BEGIN = (
    "<!-- BEGIN GENERATED: skills-table | scripts/build_registry.py backfill-tables"
    " | 成员同步自 skills.registry.json；触发词列人工维护，新增行自动预填 -->"
)
TABLE_MARKER_END = "<!-- END GENERATED: skills-table -->"

# 需要回填的文档表：(仓目录名, 仓短名, 文档相对路径, 章节标题)
DOC_TABLES = [
    ("finance-workspace-private", "ws", "CLAUDE.md", "## Skills 目录"),
]


# ---------------------------------------------------------------------------
# frontmatter 解析
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict[str, str]:
    """提取 SKILL.md 顶部 ``--- ... ---`` 之间的简单 ``key: value`` 字段。

    这些文件的 frontmatter 是单行 ``name`` / ``description``，用极简解析即可，
    避免引入 PyYAML 依赖；若装了 PyYAML 则优先用它。
    """
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    block = m.group(1)
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(block)
        if isinstance(loaded, dict):
            return {str(k): str(v) for k, v in loaded.items() if v is not None}
    except Exception:
        pass
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip()
    return out


_TRIGGER_SPLIT = re.compile(r"[、，,/;；]+")


def _extract_triggers(description: str) -> list[str]:
    """从 description 中抽取「触发词」段，切成关键词列表。"""
    m = re.search(r"触发词[:：]\s*(.*?)(?:。\s*注意|。\s*备注|注意[:：]|备注[:：]|$)", description, re.S)
    if not m:
        return []
    seg = m.group(1).strip().rstrip("。 ")
    parts = [p.strip() for p in _TRIGGER_SPLIT.split(seg) if p.strip()]
    return parts


def _extract_note(description: str) -> str:
    """抽取「注意 / 备注」段（消歧说明），无则空串。"""
    m = re.search(r"(?:注意|备注)[:：]\s*(.*)$", description, re.S)
    return m.group(1).strip() if m else ""


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 扫描
# ---------------------------------------------------------------------------

def _present_repos() -> list[tuple[str, str, Path]]:
    """返回当前文件系统上在场的 (dir名, 短代号, 绝对路径) 列表。"""
    out: list[tuple[str, str, Path]] = []
    for name, short in KNOWN_REPOS:
        root = REPOS_DIR / name
        if root.is_dir():
            out.append((name, short, root))
    return out


def _scan_canonical(repo_name: str, short: str, root: Path) -> dict[str, dict]:
    """扫描一个仓库 ``skills/<name>/SKILL.md``，返回 key -> 条目。"""
    skills: dict[str, dict] = {}
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return skills
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        skills[f"{short}/{name}"] = _make_entry(repo_name, short, root, name, skill_md, agent_only=False)
    return skills


def _make_entry(repo_name: str, short: str, root: Path, name: str, skill_md: Path, *, agent_only: bool) -> dict:
    fm = _parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
    description = fm.get("description", "")
    entry: dict[str, object] = {
        "name": fm.get("name", name),
        "repo": repo_name,
        "sourceType": "local",
        "skillPath": skill_md.relative_to(root).as_posix(),
        "description": description,
        "triggers": _extract_triggers(description),
        "note": _extract_note(description),
        "entrypoint": None,            # A-S0 暂不推断入口命令，后续阶段补
        "computedHash": _sha256(skill_md),
        "agentOnly": agent_only,       # True = 仅存在于 agent 目录、skills/ 无规范源
        "views": [],                   # 同仓内引用本 skill 的 agent 目录视图
    }
    if name in DECLARED_SPLITS and short in DECLARED_SPLITS[name]["repos"]:  # type: ignore[index]
        entry["split"] = {
            "declared": True,
            "reason": DECLARED_SPLITS[name]["reason"],
            "repos": DECLARED_SPLITS[name]["repos"],
        }
    return entry


def _attach_views_and_agent_only(repo_name: str, short: str, root: Path, skills: dict[str, dict]) -> None:
    """扫描本仓 agent 目录，把 symlink/物理拷贝挂到对应 skill 的 views；
    没有规范源的（如 obsidian）登记为 agentOnly 规范条目。"""
    for agent_dir_rel in AGENT_SKILL_DIRS:
        agent_dir = root / agent_dir_rel
        if not agent_dir.is_dir():
            continue
        for child in sorted(agent_dir.iterdir(), key=lambda p: p.name):
            if not child.is_dir() and not child.is_symlink():
                continue
            name = child.name
            key = f"{short}/{name}"
            rel = child.relative_to(root).as_posix()
            if child.is_symlink():
                target = child.readlink().as_posix() if hasattr(child, "readlink") else str(child)
                if key in skills:
                    skills[key]["views"].append({"path": rel, "type": "symlink", "target": target})
                continue
            # 物理目录
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            if key in skills:
                # 同仓既有规范源、又有物理拷贝 → 记为 copy 视图（漂移候选）
                skills[key]["views"].append({"path": rel, "type": "copy", "computedHash": _sha256(skill_md)})
            else:
                # 无规范源的 agent-only skill：首次出现立为规范，后续同名物理目录记为 copy 视图
                skills[key] = _make_entry(repo_name, short, root, name, skill_md, agent_only=True)


def _cross_repo_duplicates(by_repo: dict[str, dict[str, dict]]) -> list[dict]:
    """跨仓重复：同一 skill 名在多于一个仓出现物理实体（规范或 agent 拷贝），
    且未声明为合法拆分。"""
    locations: dict[str, list[dict]] = {}
    for short, skills in by_repo.items():
        for key, entry in skills.items():
            name = key.split("/", 1)[1]
            loc = {"repo": entry["repo"], "short": short, "skillPath": entry["skillPath"],
                   "agentOnly": entry["agentOnly"]}
            locations.setdefault(name, []).append(loc)
            for v in entry["views"]:
                if v["type"] == "copy":
                    locations[name].append({"repo": entry["repo"], "short": short, "skillPath": v["path"],
                                            "agentOnly": entry["agentOnly"]})
    dups: list[dict] = []
    for name in sorted(locations):
        repos_involved = {l["short"] for l in locations[name]}
        if len(repos_involved) <= 1:
            continue
        dups.append({
            "name": name,
            "declaredSplit": name in DECLARED_SPLITS,
            "locations": sorted(locations[name], key=lambda l: (l["short"], l["skillPath"])),
        })
    return dups


def _merge_lockfile(by_repo: dict[str, dict[str, dict]]) -> None:
    """并入 knowledge-base/skills-lock.json 中的 github 源 skill。"""
    kb_root = REPOS_DIR / "knowledge-base-private"
    lock = kb_root / "skills-lock.json"
    if not lock.is_file():
        return
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    kb = by_repo.setdefault("kb", {})
    for name, spec in sorted((data.get("skills") or {}).items()):
        key = f"kb/{name}"
        if key in kb:
            continue
        kb[key] = {
            "name": name,
            "repo": "knowledge-base-private",
            "sourceType": spec.get("sourceType", "github"),
            "skillPath": spec.get("skillPath", ""),
            "source": spec.get("source", ""),
            "description": "",
            "triggers": [],
            "note": "",
            "entrypoint": None,
            "computedHash": "sha256:" + spec["computedHash"] if spec.get("computedHash") and not str(spec["computedHash"]).startswith("sha256:") else spec.get("computedHash", ""),
            "agentOnly": False,
            "views": [],
        }


def build_payload() -> dict:
    """构建注册表 payload（不含易变的 ``generated_at``）。"""
    present = _present_repos()
    by_repo: dict[str, dict[str, dict]] = {}
    for repo_name, short, root in present:
        skills = _scan_canonical(repo_name, short, root)
        _attach_views_and_agent_only(repo_name, short, root, skills)
        by_repo[short] = skills
    _merge_lockfile(by_repo)

    all_skills: dict[str, dict] = {}
    for short in [s for _, s in KNOWN_REPOS if s in by_repo]:
        for key in sorted(by_repo[short]):
            entry = by_repo[short][key]
            entry["views"] = sorted(entry["views"], key=lambda v: v["path"])
            all_skills[key] = entry

    repos_meta = [
        {"name": name, "short": short, "present": (REPOS_DIR / name).is_dir(),
         "skills": sum(1 for k in all_skills if k.startswith(f"{short}/"))}
        for name, short in KNOWN_REPOS
    ]

    return {
        "version": REGISTRY_VERSION,
        "generator": GENERATOR_ID,
        "repos": repos_meta,
        "declaredSplits": DECLARED_SPLITS,
        "crossRepoDuplicates": _cross_repo_duplicates(by_repo),
        "skills": all_skills,
    }


# ---------------------------------------------------------------------------
# 序列化 / 比对
# ---------------------------------------------------------------------------

def _dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _load_existing() -> Optional[dict]:
    if not REGISTRY_PATH.is_file():
        return None
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _strip_volatile(payload: dict) -> dict:
    out = dict(payload)
    out.pop("generated_at", None)
    return out


def _present_shorts() -> set[str]:
    return {short for name, short in KNOWN_REPOS if (REPOS_DIR / name).is_dir()}


def cmd_scan() -> int:
    payload = build_payload()
    existing = _load_existing()
    if existing is not None and _strip_volatile(existing) == _strip_volatile(payload):
        # 内容未变：保留原 generated_at，产物字节不变（幂等）。
        payload["generated_at"] = existing.get("generated_at", "")
    else:
        payload["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # 把 generated_at 放到稳定位置（version/generator 之后）。
    ordered = {
        "version": payload["version"],
        "generator": payload["generator"],
        "generated_at": payload["generated_at"],
        "repos": payload["repos"],
        "declaredSplits": payload["declaredSplits"],
        "crossRepoDuplicates": payload["crossRepoDuplicates"],
        "skills": payload["skills"],
    }
    REGISTRY_PATH.write_text(_dumps(ordered), encoding="utf-8")
    n = len(ordered["skills"])
    print(f"[scan] 写出 {REGISTRY_PATH.relative_to(REPO_ROOT)}：{n} 个 skill，"
          f"{len(ordered['crossRepoDuplicates'])} 处跨仓重复。")
    return 0


def _frontmatter_block(text: str) -> Optional[str]:
    """返回 SKILL.md 顶部 ``--- ... ---`` 之间的原文；无该块时返回 None。"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    return m.group(1) if m else None


def cmd_check_parseability() -> int:
    """元校验：每个在场仓的 ``skills/<name>/SKILL.md`` frontmatter 是否可被注册表
    扫描器正确解析（含非空 name/description，且 name 与目录名一致）。

    设计为逐文件检查，不触及 crossRepoDuplicates / declaredSplits，因此：
    - 在只 checkout 单仓的 CI 环境下不会误报；
    - ``disclosure-archive`` 这类合法跨仓拆分（两仓各有规范源）也不会误报。
    """
    present = _present_repos()
    problems: list[tuple[str, str, str]] = []
    checked = 0
    for _repo_name, short, root in present:
        skills_dir = root / "skills"
        if not skills_dir.is_dir():
            continue
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            checked += 1
            dir_name = skill_md.parent.name
            key = f"{short}/{dir_name}"
            rel = skill_md.relative_to(root).as_posix()
            text = skill_md.read_text(encoding="utf-8", errors="replace")
            if _frontmatter_block(text) is None:
                problems.append((key, rel, "缺少 frontmatter（顶部 --- ... --- 块）"))
                continue
            fm = _parse_frontmatter(text)
            name = (fm.get("name") or "").strip()
            desc = (fm.get("description") or "").strip()
            if not name:
                problems.append((key, rel, "frontmatter 缺少 name 字段"))
            elif name != dir_name:
                problems.append((key, rel, f"name 字段({name!r})与目录名({dir_name!r})不一致"))
            if not desc:
                problems.append((key, rel, "frontmatter 缺少 description 字段"))
    if problems:
        for key, rel, msg in problems:
            print(f"[check-parseability] \u2717 {key} ({rel}): {msg}", file=sys.stderr)
        print(f"[check-parseability] {len(problems)} 处 SKILL.md 不可解析/字段缺失/名称不一致"
              f"（共扫 {checked} 个）。", file=sys.stderr)
        return 1
    print(f"[check-parseability] 全部 {checked} 个 SKILL.md frontmatter 可解析、"
          f"name 与目录名一致。")
    return 0


def cmd_check() -> int:
    existing = _load_existing()
    if existing is None:
        print("[check] 找不到 skills.registry.json，请先运行 `scan`。", file=sys.stderr)
        return 2
    rebuilt = build_payload()
    present = _present_shorts()
    all_present = present == {s for _, s in KNOWN_REPOS}

    def _skills_subset(skills: dict) -> dict:
        if all_present:
            return skills
        return {k: v for k, v in skills.items() if k.split("/", 1)[0] in present}

    exp_skills = _skills_subset(existing.get("skills", {}))
    got_skills = _skills_subset(rebuilt["skills"])

    added = sorted(set(got_skills) - set(exp_skills))
    removed = sorted(set(exp_skills) - set(got_skills))
    changed = sorted(k for k in set(got_skills) & set(exp_skills) if got_skills[k] != exp_skills[k])

    drift = bool(added or removed or changed)
    # crossRepoDuplicates / declaredSplits / repos 仅在全仓在场时纳入比对。
    meta_drift = False
    if all_present:
        for field in ("crossRepoDuplicates", "declaredSplits", "repos", "version", "generator"):
            if existing.get(field) != rebuilt.get(field):
                meta_drift = True
                print(f"[check] 字段漂移：{field}")

    if not all_present:
        skipped = sorted(set(existing.get("skills", {})) - set(exp_skills))
        print(f"[check] 部分仓在场（{sorted(present)}），跨仓项已跳过；"
              f"忽略缺仓 skill {len(skipped)} 个。")

    if drift:
        for k in added:
            print(f"[check] + 新增 {k}")
        for k in removed:
            print(f"[check] - 缺失 {k}")
        for k in changed:
            print(f"[check] ~ 变更 {k}")

    if drift or meta_drift:
        print("[check] 注册表与源不一致，请运行 `python3 scripts/build_registry.py scan` 并提交。", file=sys.stderr)
        return 1
    print("[check] 注册表与源一致。")
    return 0


# ---------------------------------------------------------------------------
# backfill-tables：回填文档里的手写 skill 表
# ---------------------------------------------------------------------------

def _split_cells(line: str) -> list[str]:
    """``| a | b |`` -> ``["a", "b"]``。"""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep_row(cells: list[str]) -> bool:
    """markdown 表的分隔行 ``|---|---|``。"""
    return bool(cells) and all(c and set(c) <= set("-: ") for c in cells)


def _canonical_skills(short: str, payload: dict) -> tuple[list[str], dict[str, list[str]]]:
    """返回某仓规范 skill 名（排除 agentOnly）及 name->triggers 映射。"""
    names: list[str] = []
    triggers: dict[str, list[str]] = {}
    for key, entry in payload["skills"].items():
        if not key.startswith(short + "/"):
            continue
        if entry.get("agentOnly"):
            continue
        name = entry["name"]
        names.append(name)
        triggers[name] = entry.get("triggers", [])
    return names, triggers


def _locate_region(lines: list[str], section: str) -> tuple[int, int, int]:
    """定位章节标题行及待替换区间。

    返回 ``(heading_idx, region_start, region_end)``，区间为闭区间。
    - 已有标记块：区间从 BEGIN 标记到 END 标记（含）。
    - 首次回填：区间为紧随标题的那张连续 markdown 表。
    """
    heading_idx = next(
        (i for i, l in enumerate(lines) if l.strip() == section), None
    )
    if heading_idx is None:
        raise ValueError(f"未找到章节标题：{section}")
    j = heading_idx + 1
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    if j >= len(lines):
        raise ValueError(f"章节 {section} 下没有内容")
    if lines[j].strip() == TABLE_MARKER_BEGIN:
        end = next(
            (k for k in range(j, len(lines)) if lines[k].strip() == TABLE_MARKER_END),
            None,
        )
        if end is None:
            raise ValueError("找到 BEGIN 标记但缺少 END 标记")
        return heading_idx, j, end
    if lines[j].lstrip().startswith("|"):
        end = j
        while end + 1 < len(lines) and lines[end + 1].lstrip().startswith("|"):
            end += 1
        return heading_idx, j, end
    raise ValueError(f"章节 {section} 下未找到 skill 表")


def _render_doc(orig: str, short: str, section: str, payload: dict) -> str:
    """重建文档：替换章节下的 skill 表为生成块，块外内容不动。"""
    lines = orig.split("\n")
    heading_idx, start, end = _locate_region(lines, section)
    marker_mode = lines[start].strip() == TABLE_MARKER_BEGIN
    row_lines = lines[start + 1:end] if marker_mode else lines[start:end + 1]

    existing_rows: list[tuple[str, str]] = []
    for l in row_lines:
        if not l.strip().startswith("|"):
            continue
        cells = _split_cells(l)
        if len(cells) < 2 or cells[0] in ("Skill", "skill") or _is_sep_row(cells):
            continue
        existing_rows.append((cells[0], cells[1]))

    names, triggers = _canonical_skills(short, payload)
    canon = set(names)

    existing_trig: dict[str, str] = {}
    existing_order: list[str] = []
    pointer_rows: list[tuple[str, str]] = []
    for col0, col1 in existing_rows:
        bare = re.split(r"[（(]", col0, 1)[0].strip()
        if bare in canon:
            existing_trig[bare] = col1
            if bare not in existing_order:
                existing_order.append(bare)
        else:
            pointer_rows.append((col0, col1))

    ordered = existing_order + sorted(canon - set(existing_order))

    block = [TABLE_MARKER_BEGIN, "| Skill | 触发词 |", "|-------|--------|"]
    for name in ordered:
        trig = existing_trig.get(name)
        if trig is None:
            regs = triggers.get(name) or []
            trig = "、".join(regs) if regs else "（待补：SKILL.md 无触发词字段）"
        block.append(f"| {name} | {trig} |")
    if pointer_rows:
        block += ["", "跨仓引用（规范源在知识库仓，本仓不放正文）：", "",
                  "| Skill | 触发词 |", "|-------|--------|"]
        block += [f"| {c0} | {c1} |" for c0, c1 in pointer_rows]
    block.append(TABLE_MARKER_END)

    remainder = lines[end + 1:]
    while remainder and remainder[0].strip() == "":
        remainder.pop(0)
    new_lines = lines[:heading_idx + 1] + [""] + block + [""] + remainder
    return "\n".join(new_lines)


def cmd_backfill(check: bool) -> int:
    payload = build_payload()
    changed = False
    for repo_name, short, rel, section in DOC_TABLES:
        path = REPOS_DIR / repo_name / rel
        if not path.exists():
            print(f"[backfill] 跳过（仓不在场）：{repo_name}/{rel}")
            continue
        orig = path.read_text(encoding="utf-8")
        new = _render_doc(orig, short, section, payload)
        if new == orig:
            print(f"[backfill] 无变化：{repo_name}/{rel}")
            continue
        changed = True
        if check:
            print(f"[backfill --check] 过期：{repo_name}/{rel}")
        else:
            path.write_text(new, encoding="utf-8")
            print(f"[backfill] 已更新：{repo_name}/{rel}")
    if check:
        if changed:
            print("[backfill --check] 文档 skill 表与注册表不一致，请运行 "
                  "`python3 scripts/build_registry.py backfill-tables` 并提交。", file=sys.stderr)
            return 1
        print("[backfill --check] 文档 skill 表与注册表一致。")
    return 0


# ---------------------------------------------------------------------------
# generate-views：以 skills/<name> 为唯一源，把 agent 目录视图规范为相对 symlink
# ---------------------------------------------------------------------------

def _canonical_names_on_disk(root: Path) -> set[str]:
    """某仓 ``skills/`` 下拥有 SKILL.md 的规范 skill 名集合。"""
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return set()
    return {p.parent.name for p in skills_dir.glob("*/SKILL.md")}


def _view_target(agent_dir: Path, canonical_dir: Path) -> str:
    """agent 目录项指向同仓 canonical 源的相对 symlink 目标（如 ``../../skills/x``）。"""
    return os.path.relpath(canonical_dir, start=agent_dir)


def cmd_generate_views(check: bool) -> int:
    """把各 agent 目录里「对应同仓 canonical 源」的项规范为相对 symlink 视图。

    - 只处理 agent 目录中**已存在**的项；不为「未被任何 agent 引用的 canonical」
      新建视图（视图集合是人工策划的，避免噪音）。
    - 物理拷贝（同仓已有 canonical 源）= DRY 违规：apply 时替换为 symlink，
      ``--check`` 时报漂移。
    - symlink 目标不正确 → apply 修正 / ``--check`` 报漂移。
    - 无同仓 canonical 源的项（agentOnly，如未提升前的 obsidian）保持不动。
    """
    drift = False
    for repo_name, short, root in _present_repos():
        canon = _canonical_names_on_disk(root)
        for agent_dir_rel in AGENT_SKILL_DIRS:
            agent_dir = root / agent_dir_rel
            if not agent_dir.is_dir():
                continue
            for child in sorted(agent_dir.iterdir(), key=lambda p: p.name):
                name = child.name
                if name not in canon:
                    continue  # agentOnly / 无同仓规范源：不动
                canonical_dir = root / "skills" / name
                want = _view_target(agent_dir, canonical_dir)
                rel = child.relative_to(root).as_posix()
                if child.is_symlink():
                    cur = os.readlink(child)
                    if cur == want:
                        continue
                    drift = True
                    if check:
                        print(f"[generate-views --check] symlink 目标不符：{repo_name}/{rel} -> {cur}（应为 {want}）")
                    else:
                        child.unlink()
                        child.symlink_to(want)
                        print(f"[generate-views] 修正 symlink：{repo_name}/{rel} -> {want}")
                else:
                    # 物理拷贝且同仓已有 canonical 源 → DRY 违规
                    drift = True
                    if check:
                        print(f"[generate-views --check] 物理拷贝（应为 symlink 视图）：{repo_name}/{rel}")
                    else:
                        if child.is_dir():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
                        child.symlink_to(want)
                        print(f"[generate-views] 物理拷贝→symlink：{repo_name}/{rel} -> {want}")
    if check:
        if drift:
            print("[generate-views --check] agent 目录视图与 skills/ 源不一致，请运行 "
                  "`python3 scripts/build_registry.py generate-views` 并提交。", file=sys.stderr)
            return 1
        print("[generate-views --check] agent 目录视图与 skills/ 源一致。")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="工具/skill 注册表生成器（scan / backfill-tables / --check）")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("scan", help="扫描三仓生成/刷新 skills.registry.json")
    p_check = sub.add_parser("check", help="比对注册表与源，有漂移则非 0 退出")
    p_check.set_defaults(cmd="check")
    sub.add_parser("check-parseability",
                   help="元校验：每个 SKILL.md frontmatter 可解析且 name 与目录名一致，否则非 0 退出")
    p_bf = sub.add_parser("backfill-tables", help="用注册表回填各仓文档里的手写 skill 表")
    p_bf.add_argument("--check", dest="bf_check", action="store_true",
                      help="只校验文档表是否最新，不写入；过期则非 0 退出")
    p_gv = sub.add_parser("generate-views", help="把 agent 目录视图规范为指向 skills/ 源的相对 symlink")
    p_gv.add_argument("--check", dest="gv_check", action="store_true",
                      help="只校验视图是否规范，不改文件；有物理拷贝/坏链则非 0 退出")
    parser.add_argument("--check", action="store_true", help="等价于 check 子命令")
    args = parser.parse_args(argv)

    if args.cmd == "check-parseability":
        return cmd_check_parseability()
    if args.cmd == "backfill-tables":
        return cmd_backfill(check=args.bf_check)
    if args.cmd == "generate-views":
        return cmd_generate_views(check=args.gv_check)
    if args.check or args.cmd == "check":
        return cmd_check()
    if args.cmd == "scan" or args.cmd is None:
        return cmd_scan()
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
