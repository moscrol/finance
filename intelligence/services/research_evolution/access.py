"""范围与归属（spec 06 §1 / §4.4 / I06）。

本机受信单用户模式下，现有 API 的 ``?user=`` 查询参数**不是认证**：目录隔离只是「各写各的目录」。
本批新增接口的有效 owner 规则：

- ``cf_access`` 模式：``IdentityRewriteMiddleware`` 已把 ``user`` 改写成经 JWT 验证的用户 → 直接采信；
- ``off`` 模式（无认证层）：有效 owner 固定为服务配置的用户（``userspace.resolve_user_id(None)``，即
  ``FORESIGHT_USER`` 或 ``default``），再加运维显式允许的名单 ``RESEARCH_EVOLUTION_ALLOWED_USERS``；
  客户端传来的 ``user`` 只要不在允许集内 → ``owner_forbidden``，**不回显**它是否存在。

请求正文里的 ``owner_user_id`` 永远不能替代访问控制；01–05 的库函数会再核一次 owner，这里先拦。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from intelligence import userspace
from intelligence.services.research_evolution.contracts import ERR_NOT_FOUND, ERR_OWNER_FORBIDDEN, ApiError

ENV_ALLOWED_USERS = "RESEARCH_EVOLUTION_ALLOWED_USERS"
AUTH_MODE_OFF = "off"
SUBDIR = "research_evolution"


def allowed_users_from_env(env: dict[str, str] | None = None) -> frozenset[str]:
    raw = (env if env is not None else os.environ).get(ENV_ALLOWED_USERS, "")
    out: set[str] = set()
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.add(userspace.resolve_user_id(piece))
        except ValueError:
            continue
    return frozenset(out)


@dataclass(frozen=True)
class AccessPolicy:
    """部署允许的用户上下文。``configured_user`` 是服务配置用户；``identity_trusted`` 为真表示上游已认证。"""

    configured_user: str
    allowed_users: frozenset[str] = frozenset()
    identity_trusted: bool = False

    @classmethod
    def from_env(cls, *, auth_mode: str | None = None, env: dict[str, str] | None = None) -> "AccessPolicy":
        configured = userspace.resolve_user_id(None)
        mode = (auth_mode or (env if env is not None else os.environ).get("WORKBENCH_AUTH_MODE", AUTH_MODE_OFF) or AUTH_MODE_OFF).strip().lower()
        return cls(
            configured_user=configured,
            allowed_users=allowed_users_from_env(env),
            identity_trusted=(mode != AUTH_MODE_OFF),
        )

    def resolve_owner(self, requested_user: str | None) -> str:
        """把请求里的 ``user`` 解析成有效 owner；越界一律 ``owner_forbidden``。"""
        if requested_user is None or not str(requested_user).strip():
            return self.configured_user
        try:
            uid = userspace.resolve_user_id(str(requested_user))
        except ValueError:
            raise ApiError(ERR_OWNER_FORBIDDEN, "当前部署不允许该用户上下文") from None
        if self.identity_trusted:
            return uid
        if uid == self.configured_user or uid in self.allowed_users:
            return uid
        raise ApiError(ERR_OWNER_FORBIDDEN, "当前部署不允许切换用户")


@dataclass(frozen=True)
class OwnerContext:
    """一次请求内经验证的归属：owner、用户态根、本批私有子目录。"""

    owner_user_id: str
    user_root: Path
    evolution_root: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evolution_root", self.user_root / SUBDIR)

    @property
    def validation_root(self) -> Path:
        return self.user_root / "research_validation"

    @classmethod
    def for_owner(cls, owner_user_id: str) -> "OwnerContext":
        us = userspace.user_space(owner_user_id)
        return cls(owner_user_id=us.user_id, user_root=Path(us.root))


def require_same_owner(actual: str | None, ctx: OwnerContext, *, what: str = "对象") -> None:
    """对象归属与请求 owner 不一致 → ``not_found``（不泄漏对方对象存在性）。"""
    if actual is None or str(actual) != ctx.owner_user_id:
        raise ApiError(ERR_NOT_FOUND, f"{what}不存在")


def conversation_scope(load_conversation: Callable[[str], Any], ctx: OwnerContext, conversation_id: str) -> Any:
    """按 owner 的 ConversationStore 载入会话；不存在 / 非法 / 越界统一 ``not_found``。"""
    try:
        conversation = load_conversation(conversation_id)
    except (FileNotFoundError, ValueError):
        raise ApiError(ERR_NOT_FOUND, "conversation 不存在") from None
    require_same_owner(getattr(conversation, "user_id", None), ctx, what="conversation")
    return conversation


__all__ = [
    "AUTH_MODE_OFF",
    "ENV_ALLOWED_USERS",
    "SUBDIR",
    "AccessPolicy",
    "OwnerContext",
    "allowed_users_from_env",
    "conversation_scope",
    "require_same_owner",
]
