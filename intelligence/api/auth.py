"""Hosted Alpha 身份门：Cloudflare Access JWT → 服务端可信 user_id。

对应 2026-07-11 内测设计稿 §10.2「FastAPI 验证 JWT，禁止客户端自报 user」。

拓扑假设：uvicorn 只绑 127.0.0.1，公网流量经 cloudflared 隧道回源，
Cloudflare Access 在边缘完成登录（邮箱 OTP / IdP），放行的请求带
``Cf-Access-Jwt-Assertion`` 头。本模块在应用层再验一次签名——不信任
明文邮箱头（``Cf-Access-Authenticated-User-Email``），因为任何能触达
回环端口的本机进程都能伪造明文头，而验签把信任锚定到 Cloudflare 的
公钥（JWKS）上。

行为契约：

- ``WORKBENCH_AUTH_MODE=off``（默认）：与历史行为完全一致，``?user=``
  继续生效，本机自用不受影响。
- ``WORKBENCH_AUTH_MODE=cf_access``：所有 ``/api/*`` 请求必须携带有效
  JWT；验签 + ``aud``/``iss`` 校验通过后，取 ``email`` claim 查邀请名单
  得到 user_id，然后**强制改写**请求中一切客户端身份声明（query string
  的 ``user`` 参数与 JSON body 顶层 ``"user"`` 字段）。端点存量代码零
  改动——它们看到的 user 永远是服务端推导的身份。
- fail closed：缺 token / 验签失败 / email 不在名单 → 401/403；
  JWKS 拉取失败 → 503。认不出来就拒绝，不降级放行。

豁免：``/api/health*`` 与 ``/api/readiness``（本机运维探活），豁免时
剥掉 ``user`` 参数，只暴露服务默认身份下的健康信息。非 ``/api/`` 路径
（前端静态资源）不拦——它们是公开 JS bundle，且边缘层已有 Access。
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from intelligence import userspace

ENV_AUTH_MODE = "WORKBENCH_AUTH_MODE"
ENV_TEAM_DOMAIN = "WORKBENCH_CF_ACCESS_TEAM_DOMAIN"
ENV_AUDIENCE = "WORKBENCH_CF_ACCESS_AUD"
ENV_USER_MAP = "WORKBENCH_AUTH_USER_MAP"

MODE_OFF = "off"
MODE_CF_ACCESS = "cf_access"

_ASSERTION_HEADER = b"cf-access-jwt-assertion"
_EXEMPT_PATHS = frozenset(
    {
        "/api/health",
        "/api/health/live",
        "/api/readiness",
        "/api/health/ready",
    }
)
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


class AuthError(Exception):
    """带 HTTP 状态码的认证失败。中间件捕获后直接回 JSON，不进端点。"""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    team_domain: str = ""
    audience: str = ""
    user_map_path: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AuthSettings":
        env = os.environ if env is None else env
        mode = (env.get(ENV_AUTH_MODE) or MODE_OFF).strip().lower()
        if mode == MODE_OFF:
            return cls(mode=MODE_OFF)
        if mode != MODE_CF_ACCESS:
            raise ValueError(
                f"未知 {ENV_AUTH_MODE}={mode!r}（只支持 {MODE_OFF}/{MODE_CF_ACCESS}）"
            )
        team_domain = (env.get(ENV_TEAM_DOMAIN) or "").strip()
        audience = (env.get(ENV_AUDIENCE) or "").strip()
        raw_map = (env.get(ENV_USER_MAP) or "").strip()
        missing = [
            name
            for name, value in (
                (ENV_TEAM_DOMAIN, team_domain),
                (ENV_AUDIENCE, audience),
                (ENV_USER_MAP, raw_map),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                f"{ENV_AUTH_MODE}={MODE_CF_ACCESS} 需要同时配置：{', '.join(missing)}"
            )
        return cls(
            mode=MODE_CF_ACCESS,
            team_domain=team_domain,
            audience=audience,
            user_map_path=Path(raw_map).expanduser(),
        )


class UserDirectory:
    """邀请名单：email（小写规范化）→ user_id。

    JSON 对象文件，例如 ``{"alice@example.com": "alice"}``。文件 mtime
    变化时自动重载（加人无需重启、不打断在跑的 SSE）；重载失败保留旧
    名单——旧名单仍是「曾经审核过」的名单，不会放行任何新身份。
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._map: dict[str, str] = {}
        self._load(required=True)

    def lookup(self, email: str) -> str | None:
        self._maybe_reload()
        return self._map.get(email.strip().lower())

    def _maybe_reload(self) -> None:
        try:
            mtime = self._path.stat().st_mtime
        except OSError:
            # 文件被移走：保留内存里的旧名单继续服务。
            return
        if mtime == self._mtime:
            return
        with self._lock:
            if mtime == self._mtime:
                return
            try:
                self._load(required=False)
            except (OSError, ValueError, json.JSONDecodeError):
                # fail closed 的方向是「不放行新身份」，旧名单继续生效。
                self._mtime = mtime

    def _load(self, *, required: bool) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            if required:
                raise
            return
        if not isinstance(raw, dict):
            if required:
                raise ValueError(f"邀请名单必须是 JSON 对象：{self._path}")
            return
        parsed: dict[str, str] = {}
        for email, user_id in raw.items():
            # 逐条过 userspace 校验：坏 user_id 在启动时就炸，不进运行期。
            parsed[str(email).strip().lower()] = userspace.resolve_user_id(
                str(user_id)
            )
        self._map = parsed
        try:
            self._mtime = self._path.stat().st_mtime
        except OSError:
            self._mtime = None


class CfAccessVerifier:
    """验签 Cloudflare Access 的应用 JWT。

    公钥来自团队域的 JWKS 端点（``/cdn-cgi/access/certs``），PyJWKClient
    带缓存；``aud`` 必须等于 Access 应用的 AUD tag，``iss`` 必须是团队域。
    """

    def __init__(
        self,
        team_domain: str,
        audience: str,
        jwks_client: object | None = None,
    ) -> None:
        import jwt as pyjwt

        base = team_domain if team_domain.startswith("https://") else (
            f"https://{team_domain}"
        )
        self._issuer = base.rstrip("/")
        self._audience = audience
        self._jwt = pyjwt
        self._jwks = jwks_client or pyjwt.PyJWKClient(
            f"{self._issuer}/cdn-cgi/access/certs",
            cache_keys=True,
            lifespan=600,
        )

    def verify(self, token: str) -> str:
        """返回 JWT 中的 email；任何验证失败抛 AuthError。"""
        jwt_exceptions = self._jwt.exceptions
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
        except jwt_exceptions.PyJWKClientConnectionError as exc:
            raise AuthError(503, "身份服务暂时不可用（JWKS 拉取失败）") from exc
        except (jwt_exceptions.PyJWKClientError, jwt_exceptions.InvalidTokenError) as exc:
            raise AuthError(401, "无效的访问凭证") from exc
        try:
            claims = self._jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat"]},
            )
        except jwt_exceptions.InvalidTokenError as exc:
            raise AuthError(401, "无效的访问凭证") from exc
        email = str(claims.get("email") or "").strip()
        if not email:
            raise AuthError(401, "访问凭证缺少 email（暂不支持 service token）")
        return email


class AuthGate:
    """认证门面：mode=off 时透明；cf_access 时 token → email → user_id。"""

    def __init__(
        self,
        settings: AuthSettings,
        *,
        verifier: CfAccessVerifier | None = None,
        directory: UserDirectory | None = None,
    ) -> None:
        self.mode = settings.mode
        if settings.mode == MODE_OFF:
            self._verifier = None
            self._directory = None
            return
        self._verifier = verifier or CfAccessVerifier(
            settings.team_domain, settings.audience
        )
        if directory is not None:
            self._directory = directory
        else:
            assert settings.user_map_path is not None
            self._directory = UserDirectory(settings.user_map_path)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AuthGate":
        return cls(AuthSettings.from_env(env))

    @property
    def enabled(self) -> bool:
        return self.mode == MODE_CF_ACCESS

    def authenticate(self, token: str) -> str:
        assert self._verifier is not None and self._directory is not None
        email = self._verifier.verify(token)
        user_id = self._directory.lookup(email)
        if user_id is None:
            raise AuthError(403, f"账号 {email} 不在内测邀请名单中")
        return user_id


def _force_user_param(query_string: bytes, user_id: str | None) -> bytes:
    """删掉客户端自报的 user 参数；user_id 非 None 时注入服务端身份。"""
    pairs = [
        (key, value)
        for key, value in parse_qsl(
            query_string.decode("latin-1"), keep_blank_values=True
        )
        if key != "user"
    ]
    if user_id is not None:
        pairs.append(("user", user_id))
    return urlencode(pairs).encode("latin-1")


Receive = Callable[[], Awaitable[MutableMapping[str, object]]]
Send = Callable[[MutableMapping[str, object]], Awaitable[None]]


async def _drain_body(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        chunks.append(bytes(message.get("body", b"") or b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _replay_body(body: bytes) -> Receive:
    sent = False

    async def receive() -> MutableMapping[str, object]:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


def _rewrite_json_user(body: bytes, user_id: str) -> bytes | None:
    """JSON 对象 body 强制注入 user；不是 JSON 对象则返回 None（原样透传）。

    必须「注入」而非「仅覆盖已有」：body 不带 user 时端点会落到
    ``resolve_user_id(None)`` = 服务器默认身份（owner），那正是要堵的洞。
    """
    if not body:
        return None
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    data["user"] = user_id
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


class IdentityRewriteMiddleware:
    """纯 ASGI 中间件：认证 + 身份改写，一处收口全部 /api/* 端点。

    用纯 ASGI 而非 BaseHTTPMiddleware：后者的 dispatch 在响应对象返回时
    就走出作用域，而 SSE（StreamingResponse）的 body 在那之后才被消费；
    纯 ASGI 的 ``await self.app(...)`` 覆盖整个响应生命周期，语义更稳。
    """

    def __init__(self, app: object, gate: AuthGate) -> None:
        self.app = app
        self.gate = gate

    async def __call__(
        self,
        scope: MutableMapping[str, object],
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http" or not self.gate.enabled:
            await self.app(scope, receive, send)  # type: ignore[operator]
            return
        path = str(scope.get("path", ""))
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)  # type: ignore[operator]
            return
        if path in _EXEMPT_PATHS:
            scope = dict(scope)
            scope["query_string"] = _force_user_param(
                bytes(scope.get("query_string", b"")), None
            )
            await self.app(scope, receive, send)  # type: ignore[operator]
            return

        token = ""
        for key, value in scope.get("headers", []):  # type: ignore[union-attr]
            if bytes(key).lower() == _ASSERTION_HEADER:
                token = bytes(value).decode("latin-1")
                break
        try:
            if not token:
                raise AuthError(401, "缺少访问凭证，请从入口域名访问")
            user_id = self.gate.authenticate(token)
        except AuthError as exc:
            await _send_json_error(send, exc.status_code, exc.detail)
            return

        scope = dict(scope)
        scope["query_string"] = _force_user_param(
            bytes(scope.get("query_string", b"")), user_id
        )
        if str(scope.get("method", "")).upper() in _BODY_METHODS:
            headers = {
                bytes(key).lower(): bytes(value)
                for key, value in scope.get("headers", [])  # type: ignore[union-attr]
            }
            content_type = headers.get(b"content-type", b"").decode("latin-1")
            if "application/json" in content_type.lower():
                body = await _drain_body(receive)
                rewritten = _rewrite_json_user(body, user_id)
                final_body = body if rewritten is None else rewritten
                scope["headers"] = [
                    (key, value)
                    for key, value in scope["headers"]  # type: ignore[union-attr]
                    if bytes(key).lower() != b"content-length"
                ] + [(b"content-length", str(len(final_body)).encode("latin-1"))]
                receive = _replay_body(final_body)
        await self.app(scope, receive, send)  # type: ignore[operator]


async def _send_json_error(send: Send, status_code: int, detail: str) -> None:
    payload = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(payload)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})
