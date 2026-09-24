"""百度网盘：分享转存 + 列目录。Cookie 只从本机网盘客户端读，不落盘、不打印。"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import unquote

import requests

from l2_paths import cookie_db_path, inbox_path, share_meta_path

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def load_meta(path: Path | None = None) -> dict:
    meta_file = path or share_meta_path()
    if not meta_file.is_file():
        raise FileNotFoundError(
            f"缺少分享入口 {meta_file}（gitignore）。把当日更新的分享 URL 写进去。"
        )
    return json.loads(meta_file.read_text(encoding="utf-8"))


def write_meta(meta: dict, path: Path | None = None) -> None:
    meta_file = path or share_meta_path()
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _cookie_map() -> dict[str, str]:
    db = cookie_db_path()
    if not db.is_file():
        raise FileNotFoundError(f"百度网盘客户端未登录或 Cookie 库不在 {db}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = dict(con.execute("SELECT name, value FROM cookies WHERE length(value)>0").fetchall())
    finally:
        con.close()
    if not (rows.get("BDUSS") or rows.get("BDUSS_BFESS")):
        raise RuntimeError("百度网盘 Cookie 里没有 BDUSS，先打开客户端登录")
    return rows


def bduss() -> str:
    rows = _cookie_map()
    return rows.get("BDUSS") or rows["BDUSS_BFESS"]


def pan_session() -> requests.Session:
    rows = _cookie_map()
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.cookies.set(
        "BDUSS",
        rows.get("BDUSS_BFESS") or rows["BDUSS"],
        domain=".baidu.com",
        path="/",
    )
    stoken = rows.get("STOKEN") or rows.get("STOKEN_BFESS")
    if stoken:
        s.cookies.set("STOKEN", stoken, domain=".pan.baidu.com", path="/")
    s.cookies.set("PANWEB", "1", domain=".pan.baidu.com", path="/")
    return s


def bdstoken(session: requests.Session) -> str:
    payload = session.get(
        "https://pan.baidu.com/api/loginStatus",
        params={"clienttype": 0, "web": 1},
        timeout=30,
    ).json()
    token = (payload.get("login_info") or {}).get("bdstoken")
    if not token:
        raise RuntimeError("loginStatus 无 bdstoken，网盘网页登录态失效")
    return token


def verify_share(session: requests.Session, meta: dict) -> str:
    surl = meta["surl"]
    if surl.startswith("1"):
        surl = surl[1:]
    payload = session.post(
        "https://pan.baidu.com/share/verify",
        params={
            "t": int(time.time() * 1000),
            "surl": surl,
            "channel": "chunlei",
            "web": 1,
            "app_id": 250528,
            "clienttype": 0,
        },
        data={"pwd": meta["pwd"], "vcode": "", "vcode_str": ""},
        headers={
            "Referer": meta["url"],
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    ).json()
    if payload.get("errno") not in (0, -12):
        raise RuntimeError(f"share/verify errno={payload.get('errno')}")
    randsk = unquote(payload.get("randsk") or "")
    if payload.get("randsk"):
        session.cookies.set("BDCLND", payload["randsk"], domain=".pan.baidu.com", path="/")
    session.get(meta["url"], timeout=30, allow_redirects=True)
    return randsk


def share_list(session: requests.Session, meta: dict, dir_path: str) -> list[dict]:
    payload = session.get(
        "https://pan.baidu.com/share/list",
        params={
            "shareid": meta["shareid"],
            "uk": meta["share_uk"],
            "dir": dir_path,
            "page": 1,
            "num": 100,
            "order": "name",
            "desc": 0,
        },
        headers={"Referer": meta["url"]},
        timeout=30,
    ).json()
    if payload.get("errno") != 0:
        raise RuntimeError(f"share list {dir_path} errno={payload.get('errno')}")
    return payload.get("list") or []


def share_file_map(session: requests.Session, meta: dict, month: str) -> dict[str, dict]:
    remote_root = meta["remote_root"].rstrip("/")
    files = share_list(session, meta, f"{remote_root}/{month}")
    return {f.get("server_filename") or "": f for f in files}


def ensure_inbox(session: requests.Session, token: str, dest: str) -> None:
    session.post(
        "https://pan.baidu.com/api/create",
        params={
            "a": "commit",
            "bdstoken": token,
            "channel": "chunlei",
            "web": 1,
            "app_id": 250528,
            "clienttype": 0,
        },
        data={"path": dest, "isdir": 1, "block_list": "[]"},
        headers={
            "Referer": "https://pan.baidu.com/disk/home",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    )


def inbox_list(session: requests.Session, token: str, dest: str) -> dict[str, dict]:
    payload = session.get(
        "https://pan.baidu.com/api/list",
        params={
            "dir": dest,
            "bdstoken": token,
            "channel": "chunlei",
            "web": 1,
            "app_id": 250528,
            "clienttype": 0,
            "num": 200,
            "page": 1,
        },
        headers={"Referer": "https://pan.baidu.com/disk/home"},
        timeout=30,
    ).json()
    if payload.get("errno") != 0:
        raise RuntimeError(f"inbox list errno={payload.get('errno')}")
    return {f["server_filename"]: f for f in (payload.get("list") or [])}


def transfer(
    session: requests.Session,
    meta: dict,
    token: str,
    randsk: str,
    files: list[dict],
    dest: str,
) -> None:
    if not files:
        return
    fsids = [int(f["fs_id"]) for f in files]
    payload = session.post(
        "https://pan.baidu.com/share/transfer",
        params={
            "shareid": meta["shareid"],
            "from": meta["share_uk"],
            "sekey": randsk,
            "ondup": "overwrite",
            "async": 1,
            "channel": "chunlei",
            "web": 1,
            "app_id": 250528,
            "clienttype": 0,
            "bdstoken": token,
        },
        data={"fsidlist": str(fsids).replace(" ", ""), "path": dest},
        headers={
            "Referer": meta["url"],
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=60,
    ).json()
    names = [f.get("server_filename") for f in files]
    print(f"transfer errno={payload.get('errno')} files={names}", flush=True)
    if payload.get("errno") != 0:
        raise RuntimeError(f"share/transfer failed errno={payload.get('errno')}")


def wait_inbox_file(
    session: requests.Session,
    token: str,
    dest: str,
    name: str,
    timeout_s: float = 180,
) -> dict:
    deadline = time.time() + timeout_s
    last: dict[str, dict] = {}
    while time.time() < deadline:
        last = inbox_list(session, token, dest)
        info = last.get(name)
        if info:
            return info
        time.sleep(5)
    raise TimeoutError(f"{dest}/{name} 转存后 {timeout_s:.0f}s 仍未出现")


def ensure_transferred(date_name: str, month: str) -> dict:
    """把分享里的 date_name 转存到 inbox，返回 inbox 文件信息（含 size）。"""
    meta = load_meta()
    dest = inbox_path(meta)
    session = pan_session()
    token = bdstoken(session)
    randsk = verify_share(session, meta)
    ensure_inbox(session, token, dest)
    share_files = share_file_map(session, meta, month)
    remote = share_files.get(date_name)
    if not remote:
        raise FileNotFoundError(f"分享 {month} 目录没有 {date_name}")
    inbox = inbox_list(session, token, dest)
    if date_name not in inbox:
        transfer(session, meta, token, randsk, [remote], dest)
        info = wait_inbox_file(session, token, dest, date_name)
    else:
        info = inbox[date_name]
    return {"meta": meta, "inbox": dest, "file": info}
