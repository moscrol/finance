"""Hosted Alpha 身份门测试。

覆盖：JWT 验签（签名/过期/audience）、邀请名单（403/热重载）、
身份改写（query 冒充、JSON body 冒充均被服务端身份覆盖）、
豁免路径、mode=off 的存量行为回归、启动 fail fast。
"""

import json
import os
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
jwt = pytest.importorskip("jwt")
cryptography = pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from intelligence.api import app as app_module  # noqa: E402
from intelligence.api.auth import (  # noqa: E402
    AuthGate,
    AuthSettings,
    CfAccessVerifier,
    UserDirectory,
)
from intelligence.api.quota import RunQuota  # noqa: E402

_TEAM = "test-team.cloudflareaccess.com"
_AUD = "aud-test-1234"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _StaticJWKS:
    """离线 JWKS：固定返回配好的公钥，不出网。"""

    def __init__(self, public_key) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str):
        return SimpleNamespace(key=self._public_key)


def _token(
    private_key,
    email: str | None,
    *,
    aud: str = _AUD,
    iss: str = f"https://{_TEAM}",
    exp_offset: int = 600,
) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + exp_offset,
    }
    if email is not None:
        claims["email"] = email
    return jwt.encode(claims, private_key, algorithm="RS256")


def _headers(private_key, email: str, **kwargs) -> dict[str, str]:
    return {"Cf-Access-Jwt-Assertion": _token(private_key, email, **kwargs)}


def _base_env(tmp_path, monkeypatch):
    users_root = tmp_path / "users"
    repo_root = tmp_path / "repo"
    repo_root.mkdir(exist_ok=True)
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users_root))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("FORESIGHT_USER", "owner")
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    monkeypatch.delenv("WORKBENCH_AUTH_MODE", raising=False)
    monkeypatch.delenv("WORKBENCH_DAILY_RUN_QUOTA", raising=False)
    return users_root, repo_root


@pytest.fixture()
def auth_client(tmp_path, monkeypatch, rsa_key):
    _, repo_root = _base_env(tmp_path, monkeypatch)
    map_path = tmp_path / "beta-users.json"
    map_path.write_text(
        json.dumps(
            {"alice@example.com": "alice-beta", "bob@example.com": "bob-beta"}
        ),
        encoding="utf-8",
    )
    settings = AuthSettings(
        mode="cf_access",
        team_domain=_TEAM,
        audience=_AUD,
        user_map_path=map_path,
    )
    gate = AuthGate(
        settings,
        verifier=CfAccessVerifier(
            _TEAM, _AUD, jwks_client=_StaticJWKS(rsa_key.public_key())
        ),
        directory=UserDirectory(map_path),
    )
    return TestClient(
        app_module.create_app(
            repo_root=repo_root, auth_gate=gate, run_quota=RunQuota()
        )
    )


def test_missing_token_rejected(auth_client):
    resp = auth_client.get("/api/conversations")
    assert resp.status_code == 401


def test_health_exempt_from_auth(auth_client):
    assert auth_client.get("/api/health").status_code == 200


def test_valid_token_maps_to_invited_user(auth_client, rsa_key):
    resp = auth_client.post(
        "/api/conversations",
        json={"title": "研究一下"},
        headers=_headers(rsa_key, "alice@example.com"),
    )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "alice-beta"


def test_query_user_impersonation_is_overridden(auth_client, rsa_key):
    created = auth_client.post(
        "/api/conversations",
        json={"title": "bob 的研究"},
        headers=_headers(rsa_key, "bob@example.com"),
    )
    assert created.json()["user_id"] == "bob-beta"
    # alice 带 ?user=bob-beta 仍只能看到自己（空）的列表
    resp = auth_client.get(
        "/api/conversations",
        params={"user": "bob-beta"},
        headers=_headers(rsa_key, "alice@example.com"),
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_json_body_user_impersonation_is_overridden(auth_client, rsa_key):
    resp = auth_client.post(
        "/api/conversations",
        json={"title": "冒充", "user": "bob-beta"},
        headers=_headers(rsa_key, "alice@example.com"),
    )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "alice-beta"
    bob_list = auth_client.get(
        "/api/conversations", headers=_headers(rsa_key, "bob@example.com")
    )
    assert bob_list.json() == []


def test_body_without_user_field_gets_identity_injected(auth_client, rsa_key):
    """body 不带 user 时不得落到服务器默认身份（owner），必须注入认证身份。"""
    resp = auth_client.post(
        "/api/conversations",
        json={"title": "无 user 字段"},
        headers=_headers(rsa_key, "bob@example.com"),
    )
    assert resp.json()["user_id"] == "bob-beta"


def test_unknown_email_rejected(auth_client, rsa_key):
    resp = auth_client.get(
        "/api/conversations",
        headers=_headers(rsa_key, "mallory@example.com"),
    )
    assert resp.status_code == 403


def test_wrong_signature_rejected(auth_client):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    resp = auth_client.get(
        "/api/conversations",
        headers=_headers(other_key, "alice@example.com"),
    )
    assert resp.status_code == 401


def test_expired_token_rejected(auth_client, rsa_key):
    resp = auth_client.get(
        "/api/conversations",
        headers=_headers(rsa_key, "alice@example.com", exp_offset=-60),
    )
    assert resp.status_code == 401


def test_wrong_audience_rejected(auth_client, rsa_key):
    resp = auth_client.get(
        "/api/conversations",
        headers=_headers(rsa_key, "alice@example.com", aud="another-app"),
    )
    assert resp.status_code == 401


def test_token_without_email_rejected(auth_client, rsa_key):
    resp = auth_client.get(
        "/api/conversations",
        headers={"Cf-Access-Jwt-Assertion": _token(rsa_key, None)},
    )
    assert resp.status_code == 401


def test_mode_off_keeps_legacy_self_report(tmp_path, monkeypatch):
    """回归保护：默认（off）行为与历史一致，?user= 继续生效。"""
    _, repo_root = _base_env(tmp_path, monkeypatch)
    client = TestClient(
        app_module.create_app(repo_root=repo_root, run_quota=RunQuota())
    )
    resp = client.post(
        "/api/conversations", json={"title": "本机自用", "user": "zed"}
    )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "zed"
    listed = client.get("/api/conversations", params={"user": "zed"}).json()
    assert [item["conversation_id"] for item in listed] == [
        resp.json()["conversation_id"]
    ]


def test_directory_lookup_and_hot_reload(tmp_path):
    map_path = tmp_path / "m.json"
    map_path.write_text(json.dumps({"A@X.com": "a1"}), encoding="utf-8")
    directory = UserDirectory(map_path)
    assert directory.lookup("a@x.COM") == "a1"
    assert directory.lookup("b@x.com") is None
    map_path.write_text(
        json.dumps({"a@x.com": "a1", "b@x.com": "b1"}), encoding="utf-8"
    )
    future = time.time() + 10
    os.utime(map_path, (future, future))
    assert directory.lookup("b@x.com") == "b1"


def test_directory_rejects_bad_user_id_at_startup(tmp_path):
    map_path = tmp_path / "m.json"
    map_path.write_text(
        json.dumps({"a@x.com": "../escape"}), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        UserDirectory(map_path)


def test_settings_fail_fast_on_incomplete_env(monkeypatch):
    monkeypatch.setenv("WORKBENCH_AUTH_MODE", "cf_access")
    for name in (
        "WORKBENCH_CF_ACCESS_TEAM_DOMAIN",
        "WORKBENCH_CF_ACCESS_AUD",
        "WORKBENCH_AUTH_USER_MAP",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError):
        AuthSettings.from_env()


def test_settings_unknown_mode_fail_fast(monkeypatch):
    monkeypatch.setenv("WORKBENCH_AUTH_MODE", "basic")
    with pytest.raises(ValueError):
        AuthSettings.from_env()


@pytest.fixture()
def restricted_client(tmp_path, monkeypatch, rsa_key):
    """alice 在 full_access 名单，bob 不在——bob 只能看回答，不能看方法论端点。"""
    _, repo_root = _base_env(tmp_path, monkeypatch)
    map_path = tmp_path / "beta-users.json"
    map_path.write_text(
        json.dumps(
            {"alice@example.com": "alice-beta", "bob@example.com": "bob-beta"}
        ),
        encoding="utf-8",
    )
    settings = AuthSettings(
        mode="cf_access",
        team_domain=_TEAM,
        audience=_AUD,
        user_map_path=map_path,
        full_access_users=frozenset({"alice-beta"}),
    )
    gate = AuthGate(
        settings,
        verifier=CfAccessVerifier(
            _TEAM, _AUD, jwks_client=_StaticJWKS(rsa_key.public_key())
        ),
        directory=UserDirectory(map_path),
    )
    return TestClient(
        app_module.create_app(
            repo_root=repo_root, auth_gate=gate, run_quota=RunQuota()
        )
    )


def test_methodology_paths_blocked_for_limited_user(restricted_client, rsa_key):
    bob = _headers(rsa_key, "bob@example.com")
    for path in (
        "/api/runs/run_x/trace",
        "/api/runs/run_x/context",
        "/api/workbench/learning-feedback",
    ):
        resp = restricted_client.get(path, headers=bob)
        assert resp.status_code == 403, path
    # 普通端点不受影响
    assert restricted_client.get("/api/conversations", headers=bob).status_code == 200


def test_methodology_paths_open_for_full_access_user(restricted_client, rsa_key):
    resp = restricted_client.get(
        "/api/runs/run_x/trace", headers=_headers(rsa_key, "alice@example.com")
    )
    # run 不存在是 404——但不是被权限门挡下的 403
    assert resp.status_code == 404


def test_methodology_paths_unrestricted_when_env_absent(auth_client, rsa_key):
    """未配置 full_access 名单 = 不限制（向后兼容）。"""
    resp = auth_client.get(
        "/api/runs/run_x/trace", headers=_headers(rsa_key, "bob@example.com")
    )
    assert resp.status_code == 404
