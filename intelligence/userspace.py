"""多用户应用态命名空间 (per-user application state).

把「画像 / 记忆 / 反馈 / 策略 overlay」这些**因人而异**的状态，从共享代码与
共享市场数据里剥离出来，按 ``intelligence/users/<user_id>/`` 收口。这样：

- 现在只有一个用户也能照常跑（``default`` 用户）；
- 以后服务多个用户时，只要给一个新的 ``--user <id>`` 即可隔离其全部状态；
- foresight 仍然**可离线**：本模块只读写本地 JSON / JSONL，不依赖 DuckDB、不联网。

每个用户目录里的文件（运行时生成，已 gitignore，不入库）：

- ``profile.json``           用户**钉住**的画像（人写，优先级最高）
- ``profile.derived.json``   ``refresh-profile`` 自动派生的候选（带来源/as_of/stale 标记）
- ``foresight_memory.jsonl`` 问过的问题记忆回路
- ``interactions.jsonl``     用户反馈（PR2：越用越懂）
- ``strategy_params.json``   个人策略参数 overlay（PR2：稀疏覆盖共享 baseline）

向后兼容：``default`` 用户沿用历史文件位置
(``foresight_profile.local.json`` / ``foresight_profile.example.json`` /
``foresight_memory.jsonl``)，所以既有的单用户用法零迁移、提问记忆不断档。

跨机同步：设环境变量 ``FORESIGHT_USERS_DIR`` 可把整个 ``users/<id>/`` 大脑目录
重定位到任意路径（支持 ``~`` 展开）。指向云同步盘（如 Obsidian 沉淀 vault 内的隐藏
目录 ``<vault>/.foresight``）后，profile / 派生画像 / 问题记忆 / interactions /
会话 buffer 全部随 vault 一处同步，两台机器共享同一个大脑；不设则落在仓库内
``intelligence/users/``（单机）。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INTEL_DIR = REPO_ROOT / "intelligence"
USERS_DIR = INTEL_DIR / "users"

DEFAULT_USER = "default"
ENV_USER = "FORESIGHT_USER"
# 把整个 users/<id>/ 大脑目录重定位到云同步盘（跨机同步）。
ENV_USERS_DIR = "FORESIGHT_USERS_DIR"

# 既有单用户的历史文件位置（default 用户沿用，保证连续性）。
LEGACY_PROFILE_EXAMPLE = INTEL_DIR / "foresight_profile.example.json"
LEGACY_PROFILE_LOCAL = INTEL_DIR / "foresight_profile.local.json"
LEGACY_MEMORY = INTEL_DIR / "foresight_memory.jsonl"

# user_id 约束：字母/数字开头，仅允许 [A-Za-z0-9._-]，长度 1-64；杜绝路径穿越。
_USER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def users_dir() -> Path:
    """users 根目录：``FORESIGHT_USERS_DIR`` 环境变量（``~`` 展开）> 仓库内默认位置。

    指向云同步盘即可让每个用户的全部应用态随之同步，实现「两机一个大脑」。
    """
    override = os.environ.get(ENV_USERS_DIR)
    if override and override.strip():
        return Path(override.strip()).expanduser()
    return USERS_DIR


def resolve_user_id(user_id: str | None) -> str:
    """解析并校验 user_id：显式参数 > ``FORESIGHT_USER`` 环境变量 > ``default``。"""
    raw = (user_id if user_id is not None else os.environ.get(ENV_USER)) or DEFAULT_USER
    raw = str(raw).strip()
    if raw in {".", ".."} or "/" in raw or "\\" in raw or not _USER_ID_RE.match(raw):
        raise ValueError(
            f"非法 user_id：{user_id!r}（只允许字母数字与 . _ -，需以字母/数字开头，长度≤64）"
        )
    return raw


@dataclass(frozen=True)
class UserSpace:
    user_id: str
    root: Path
    profile_path: Path
    derived_path: Path
    memory_path: Path
    interactions_path: Path
    strategy_params_path: Path

    @property
    def is_default(self) -> bool:
        return self.user_id == DEFAULT_USER

    def ensure_dir(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root


def user_space(user_id: str | None = None) -> UserSpace:
    """把一个 user_id 解析成它名下所有应用态文件的路径。"""
    uid = resolve_user_id(user_id)
    base = users_dir()
    root = base / uid
    # default 用户：未重定位时记忆沿用历史位置，避免既有提问记录断档；
    # 一旦设了 FORESIGHT_USERS_DIR（跨机同步），则统一收口到重定位目录。
    use_legacy = uid == DEFAULT_USER and base == USERS_DIR
    memory_path = LEGACY_MEMORY if use_legacy else root / "foresight_memory.jsonl"
    return UserSpace(
        user_id=uid,
        root=root,
        profile_path=root / "profile.json",
        derived_path=root / "profile.derived.json",
        memory_path=memory_path,
        interactions_path=root / "interactions.jsonl",
        strategy_params_path=root / "strategy_params.json",
    )


# --------------------------------------------------------------------------- #
# 画像加载与合并：effective = profile.json（钉住，优先）⊕ profile.derived.json（派生）
# --------------------------------------------------------------------------- #
def _load_json_obj(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return {}, f"画像解析失败：{path}（{exc}）"
    if not isinstance(data, dict):
        return {}, f"画像不是 JSON 对象：{path}"
    return data, None


def load_base_profile(us: UserSpace) -> tuple[dict[str, Any], list[str]]:
    """读取用户钉住的画像（profile.json）。default 用户回退到历史 local/example。"""
    warnings: list[str] = []
    data, warn = _load_json_obj(us.profile_path)
    if warn:
        warnings.append(warn)
    if not data and us.is_default:
        for legacy in (LEGACY_PROFILE_LOCAL, LEGACY_PROFILE_EXAMPLE):
            data, warn = _load_json_obj(legacy)
            if warn:
                warnings.append(warn)
            if data:
                break
    return data, warnings


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _derived_entries(value: Any, key: str) -> list[dict[str, Any]]:
    """派生文件里某个列表字段（focus_themes/watchlist）的规整读取。"""
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, dict) and str(item.get(key) or "").strip():
            out.append(item)
        elif isinstance(item, str) and item.strip():
            out.append({key: item.strip()})
    return out


def _merge_list(pinned: list[str], derived: list[dict[str, Any]], key: str) -> list[str]:
    seen = {re.sub(r"\s+", "", p) for p in pinned}
    out = list(pinned)
    for entry in derived:
        if entry.get("stale"):
            continue
        name = str(entry.get(key) or "").strip()
        if not name:
            continue
        norm = re.sub(r"\s+", "", name)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(name)
    return out


def effective_profile(us: UserSpace) -> tuple[dict[str, Any], list[str]]:
    """合并后的「生效画像」：钉住项在前，再并入未过期的派生项。"""
    base, warnings = load_base_profile(us)
    derived, dwarn = _load_json_obj(us.derived_path)
    if dwarn:
        warnings.append(dwarn)

    pinned_themes = _str_list(base.get("focus_themes"))
    pinned_watch = _str_list(base.get("watchlist"))
    derived_themes = _derived_entries(derived.get("focus_themes"), "theme")
    derived_watch = _derived_entries(derived.get("watchlist"), "name")

    profile: dict[str, Any] = {
        "name": base.get("name"),
        "style": base.get("style"),
        "horizon": base.get("horizon"),
        "focus_themes": _merge_list(pinned_themes, derived_themes, "theme"),
        "watchlist": _merge_list(pinned_watch, derived_watch, "name"),
        "recent_questions": _str_list(base.get("recent_questions")),
    }
    if not base and not us.is_default:
        warnings.append(
            f"用户「{us.user_id}」暂无画像（{us.profile_path} 不存在）；"
            f"先 `refresh-profile --user {us.user_id} --apply` 或手动放一份 profile.json。"
        )
    return profile, warnings
