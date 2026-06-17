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
- ``scan``    扫描 → 生成 / 刷新 ``skills.registry.json``。
- ``--check`` 重建并与已提交的注册表比对；有漂移则以非 0 退出（供 CI）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="工具/skill 注册表生成器（scan + --check，只读）")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("scan", help="扫描三仓生成/刷新 skills.registry.json")
    p_check = sub.add_parser("check", help="比对注册表与源，有漂移则非 0 退出")
    p_check.set_defaults(cmd="check")
    parser.add_argument("--check", action="store_true", help="等价于 check 子命令")
    args = parser.parse_args(argv)

    if args.check or args.cmd == "check":
        return cmd_check()
    if args.cmd == "scan" or args.cmd is None:
        return cmd_scan()
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
