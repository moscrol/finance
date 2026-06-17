"""本地 Web GUI —— 「越用越懂」回路的可视化入口（零依赖、可离线）。

档 A 实现：仅用标准库 ``http.server`` 把已有 ``services/`` 暴露成 JSON 接口，
再配一个单页前端（``intelligence/web/``）。设计取舍：

- **零新依赖**：纯标准库，``python3 -m intelligence.cli serve`` 一条命令起，浏览器
  开 ``http://127.0.0.1:8765`` 即可，最契合本仓「无构建、可离线」的调性。
- **自动记反馈的第二入口**：卡片上「想深挖 / 关注 / 置顶 / 不看了 / 打分」点一下就
  ``POST /api/interaction``，写进的就是 foresight 读的同一个
  ``users/<id>/interactions.jsonl``——和「对话自动记反馈」汇到一处。
- **多用户**：所有接口带 ``?user=<id>``，天然按用户命名空间隔离。
- **优雅降级**：没有 LLM key 时 foresight 返回上下文摘要 + 亲和度，接口照常 200。

接口一览（详见各 ``_api_*`` 处理函数）::

    GET  /api/health
    GET  /api/users
    GET  /api/foresight?user=&n=&candidates=&date=
    GET  /api/interactions?user=&window=
    POST /api/interaction            {user, kind, themes[], stocks[], rating?, weight?, question?, note?}
    GET  /api/profile?user=
    POST /api/refresh-profile?user=&apply=
    GET  /api/strategy?user=
    POST /api/strategy?user=         {overlay:{...}}
"""

from __future__ import annotations

import argparse
import json
import traceback
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from evolution import params as evparams
from intelligence import userspace
from intelligence.services import foresight, interactions

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = Path(__file__).resolve().parent / "web"

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


@dataclass(frozen=True)
class ServerConfig:
    """启动时一次性设定的运行参数，逐请求透传给各 service。"""

    host: str = "127.0.0.1"
    port: int = 8765
    default_user: str = "default"
    kb_wiki: str | None = None
    db_path: str | None = None
    exports_dir: str | None = None
    llm_model: str | None = None
    llm_timeout: int = 60
    temperature: float = 0.8
    candidates: int = 8
    num: int = 4
    affinity_half_life: float = 14.0
    affinity_boost: float = 0.2


# ---- helpers --------------------------------------------------------------- #
def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "apply"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _affinity_to_dict(aff: interactions.Affinity) -> dict[str, Any]:
    return {"label": aff.label, "kind": aff.kind, "score": aff.score}


def _list_users(default_user: str) -> list[str]:
    found = {userspace.DEFAULT_USER, default_user}
    if userspace.USERS_DIR.exists():
        for child in userspace.USERS_DIR.iterdir():
            if child.is_dir():
                try:
                    found.add(userspace.resolve_user_id(child.name))
                except ValueError:
                    continue
    return sorted(found)


# --------------------------------------------------------------------------- #
# 请求处理
# --------------------------------------------------------------------------- #
class ForesightHTTPHandler(BaseHTTPRequestHandler):
    config: ServerConfig = ServerConfig()
    server_version = "ForesightGUI/1.0"

    # -- 低噪日志 --
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        print(f"[server] {self.address_string()} {fmt % args}")

    # -- 输出 --
    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- 输入 --
    def _query(self) -> dict[str, str]:
        qs = parse_qs(urlsplit(self.path).query)
        return {k: v[0] for k, v in qs.items() if v}

    def _user(self, query: dict[str, str]) -> str:
        return userspace.resolve_user_id(query.get("user") or self.config.default_user)

    def _read_json_body(self) -> dict[str, Any]:
        length = _int(self.headers.get("Content-Length"), 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    # -- 路由 --
    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        try:
            if path.startswith("/api/"):
                self._route_get_api(path)
            else:
                self._serve_static(path)
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        try:
            if path == "/api/interaction":
                self._api_record_interaction()
            elif path == "/api/refresh-profile":
                self._api_refresh_profile()
            elif path == "/api/strategy":
                self._api_strategy_post()
            else:
                self._send_json({"error": f"未知接口：{path}"}, status=404)
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)

    def _route_get_api(self, path: str) -> None:
        if path == "/api/health":
            self._send_json({"ok": True, "default_user": self.config.default_user})
        elif path == "/api/users":
            self._send_json({"users": _list_users(self.config.default_user)})
        elif path == "/api/foresight":
            self._api_foresight()
        elif path == "/api/interactions":
            self._api_interactions()
        elif path == "/api/profile":
            self._api_profile()
        elif path == "/api/strategy":
            self._api_strategy_get()
        else:
            self._send_json({"error": f"未知接口：{path}"}, status=404)

    def _fail(self, exc: Exception) -> None:
        traceback.print_exc()
        self._send_json({"error": f"{type(exc).__name__}: {exc}"}, status=500)

    # -- 静态文件 --
    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in target.parents and target != WEB_DIR.resolve():
            self._send_json({"error": "非法路径"}, status=403)
            return
        if not target.is_file():
            self._send_json({"error": f"未找到：{rel}"}, status=404)
            return
        self._send_bytes(target.read_bytes(), _MIME.get(target.suffix, "application/octet-stream"))

    # -- API: foresight --
    def _api_foresight(self) -> None:
        q = self._query()
        cfg = self.config
        options = foresight.ForesightOptions(
            user=self._user(q),
            n=_int(q.get("n"), cfg.num),
            candidates=_int(q.get("candidates"), cfg.candidates),
            date=q.get("date") or None,
            exports_dir=cfg.exports_dir,
            kb_wiki=cfg.kb_wiki,
            llm_model=cfg.llm_model,
            llm_timeout=cfg.llm_timeout,
            temperature=cfg.temperature,
            affinity_half_life=cfg.affinity_half_life,
            affinity_boost=cfg.affinity_boost,
        )
        result = foresight.generate(options)
        payload = foresight.result_to_dict(result)
        payload["context_digest"] = result.context_digest
        payload["prompt_preview"] = result.prompt_preview
        self._send_json(payload)

    # -- API: interactions (read) --
    def _api_interactions(self) -> None:
        q = self._query()
        us = userspace.user_space(self._user(q))
        window = _int(q.get("window"), 200)
        half_life = float(q.get("half_life") or self.config.affinity_half_life)
        records, warn = interactions.load_interactions(us.interactions_path, window=window)
        affinity = interactions.compute_affinity(records, half_life_days=half_life)
        self._send_json(
            {
                "user": us.user_id,
                "path": str(us.interactions_path),
                "window": window,
                "half_life_days": half_life,
                "count": len(records),
                "records": list(reversed(records)),
                "affinity": [_affinity_to_dict(a) for a in affinity],
                "warnings": [warn] if warn else [],
            }
        )

    # -- API: interaction (record) --
    def _api_record_interaction(self) -> None:
        body = self._read_json_body()
        q = self._query()
        user = userspace.resolve_user_id(body.get("user") or q.get("user") or self.config.default_user)
        kind = str(body.get("kind") or "").strip().lower()
        if not kind:
            self._send_json({"error": "缺少 kind"}, status=400)
            return
        us = userspace.user_space(user)
        us.ensure_dir()
        path, record = interactions.record_interaction(
            us.interactions_path,
            kind=kind,
            question=body.get("question"),
            themes=body.get("themes"),
            stocks=body.get("stocks"),
            weight=body.get("weight"),
            rating=body.get("rating"),
            note=body.get("note"),
        )
        records, _ = interactions.load_interactions(us.interactions_path, window=200)
        affinity = interactions.compute_affinity(records, half_life_days=self.config.affinity_half_life)
        self._send_json(
            {
                "ok": True,
                "user": user,
                "path": str(path),
                "record": record,
                "affinity": [_affinity_to_dict(a) for a in affinity],
            }
        )

    # -- API: profile --
    def _api_profile(self) -> None:
        q = self._query()
        us = userspace.user_space(self._user(q))
        profile, warnings = userspace.effective_profile(us)
        self._send_json(
            {
                "user": us.user_id,
                "profile": profile,
                "profile_path": str(us.profile_path),
                "derived_path": str(us.derived_path),
                "warnings": warnings,
            }
        )

    def _api_refresh_profile(self) -> None:
        from intelligence.workflows.refresh_profile import (
            RefreshProfileWorkflowOptions,
            run_refresh_profile,
        )

        q = self._query()
        body = self._read_json_body()
        user = userspace.resolve_user_id(body.get("user") or q.get("user") or self.config.default_user)
        apply = _bool(q.get("apply")) or bool(body.get("apply"))
        _summary, proposal, diff, answer = run_refresh_profile(
            RefreshProfileWorkflowOptions(
                user=user,
                top=_int(q.get("top"), 12),
                kb_wiki=self.config.kb_wiki,
                db_path=self.config.db_path,
                apply=apply,
            )
        )
        self._send_json(
            {
                "ok": True,
                "user": user,
                "applied": apply,
                "answer": answer,
                "diff": diff,
                "sources": proposal.get("sources", {}),
                "as_of": proposal.get("as_of", {}),
                "warnings": proposal.get("warnings", []),
            }
        )

    # -- API: strategy overlay --
    def _api_strategy_get(self) -> None:
        q = self._query()
        us = userspace.user_space(self._user(q))
        params, meta = evparams.load_effective_params(overlay_path=us.strategy_params_path)
        overlay_raw: Any = None
        if us.strategy_params_path.exists():
            try:
                overlay_raw = json.loads(us.strategy_params_path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                meta.setdefault("warnings", []).append(f"overlay 解析失败：{exc}")
        self._send_json(
            {
                "user": us.user_id,
                "params": params,
                "meta": meta,
                "overlay_raw": overlay_raw,
                "overlay_path": str(us.strategy_params_path),
                "allowed_sections": list(evparams.OVERLAY_ALLOWED_SECTIONS),
            }
        )

    def _api_strategy_post(self) -> None:
        q = self._query()
        body = self._read_json_body()
        user = userspace.resolve_user_id(body.get("user") or q.get("user") or self.config.default_user)
        us = userspace.user_space(user)
        raw = body.get("overlay")
        if raw is None:
            raw = {k: v for k, v in body.items() if k != "user"}
        overlay, ometa, warnings = evparams.sanitize_overlay(raw)
        if not overlay:
            self._send_json(
                {"error": "overlay 没有可写的策略段（允许：" + ", ".join(evparams.OVERLAY_ALLOWED_SECTIONS) + "）", "warnings": warnings},
                status=400,
            )
            return
        # 版本：沿用入参 _overlay_version；缺省则在当前版本上自增。
        _, cur_meta = evparams.load_effective_params(overlay_path=us.strategy_params_path)
        version = ometa.get("_overlay_version")
        if version is None:
            cur = cur_meta.get("overlay_version")
            version = (int(cur) + 1) if isinstance(cur, int) else 1
        to_write: dict[str, Any] = {"_overlay_version": version}
        to_write.update(overlay)
        us.ensure_dir()
        us.strategy_params_path.write_text(
            json.dumps(to_write, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        params, meta = evparams.load_effective_params(overlay_path=us.strategy_params_path)
        self._send_json(
            {
                "ok": True,
                "user": user,
                "overlay_path": str(us.strategy_params_path),
                "overlay": to_write,
                "params": params,
                "meta": meta,
                "warnings": warnings,
            }
        )


def build_config(args: argparse.Namespace) -> ServerConfig:
    return ServerConfig(
        host=args.host,
        port=args.port,
        default_user=userspace.resolve_user_id(args.user),
        kb_wiki=args.kb_wiki,
        db_path=args.db_path,
        exports_dir=args.exports_dir,
        llm_model=args.llm_model,
        llm_timeout=args.llm_timeout,
        temperature=args.temperature,
        candidates=args.candidates,
        num=args.num,
        affinity_half_life=args.affinity_half_life,
        affinity_boost=args.affinity_boost,
    )


def serve(config: ServerConfig) -> None:
    ForesightHTTPHandler.config = config
    httpd = ThreadingHTTPServer((config.host, config.port), ForesightHTTPHandler)
    url = f"http://{config.host}:{config.port}"
    print(f"[server] 猜你想问 GUI 已启动：{url}  (默认用户={config.default_user})")
    print("[server] Ctrl+C 退出。")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] 已停止。")
    finally:
        httpd.server_close()


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1，仅本机）")
    parser.add_argument("--port", type=int, default=8765, help="监听端口（默认 8765）")
    parser.add_argument("--user", default=None, help="默认用户 id（默认 default 或 FORESIGHT_USER）")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根（含 relations/）；默认 env/auto")
    parser.add_argument("--db-path", default=None, help="覆盖 DuckDB 路径；refresh-profile 用")
    parser.add_argument("--exports-dir", default=None, help="盘面快照 exports 目录；默认仓内约定路径")
    parser.add_argument("--llm-model", default=None, help="foresight LLM 模型；不填则降级为摘要")
    parser.add_argument("--llm-timeout", type=int, default=60, help="LLM 超时秒（默认 60）")
    parser.add_argument("--temperature", type=float, default=0.8, help="LLM 温度（默认 0.8）")
    parser.add_argument("--candidates", type=int, default=8, help="foresight 候选数（默认 8）")
    parser.add_argument("--num", type=int, default=4, help="foresight 每次问题数（默认 4）")
    parser.add_argument("--affinity-half-life", type=float, default=14.0, help="亲和度时间半衰期/天（默认 14）")
    parser.add_argument("--affinity-boost", type=float, default=0.2, help="排序亲和加成权重（默认 0.2）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="猜你想问 / 反馈回路 本地 Web GUI（零依赖）")
    add_arguments(parser)
    args = parser.parse_args(argv)
    serve(build_config(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
