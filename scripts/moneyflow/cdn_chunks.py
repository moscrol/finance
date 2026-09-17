"""4MB Range 分片拉网盘大文件（整文件 GET 会被 CDN 403）。"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from baidu_share import bduss
from l2_paths import cache_dir, inbox_path

UA = "netdisk;P2SP;2.2.93.105"
CHUNK = int(os.environ.get("L2_CDN_CHUNK", str(4 * 1024 * 1024)))
WORKERS = int(os.environ.get("L2_CDN_WORKERS", "6"))


class Locator:
    def __init__(self, pan_path: str):
        self.pan_path = pan_path
        self._lock = threading.Lock()
        self._urls: list[str] = []
        self._i = 0
        self._auth = requests.Session()
        self._auth.cookies.set("BDUSS", bduss(), domain=".baidu.com", path="/")
        self._auth.headers["User-Agent"] = UA
        self.refresh()

    def refresh(self) -> None:
        response = self._auth.get(
            "https://pcs.baidu.com/rest/2.0/pcs/file",
            params={
                "method": "locatedownload",
                "app_id": 250528,
                "path": self.pan_path,
                "ver": 2,
                "vip": 2,
            },
            timeout=30,
        )
        response.raise_for_status()
        urls = [u["url"] for u in (response.json().get("urls") or []) if u.get("url")]
        if not urls:
            raise RuntimeError("locatedownload 无 url")
        with self._lock:
            self._urls = urls
            self._i = 0
        hosts = [u.split("/")[2] for u in urls[:4]]
        print(f"locate n={len(urls)} hosts={hosts}", flush=True)

    def url(self) -> str:
        with self._lock:
            if not self._urls:
                raise RuntimeError("no urls")
            url = self._urls[self._i % len(self._urls)]
            self._i += 1
            return url


def fetch_chunk(locator: Locator, start: int, end: int) -> bytes:
    headers = {"User-Agent": UA, "Range": f"bytes={start}-{end}"}
    last = None
    for attempt in range(6):
        url = locator.url()
        try:
            response = requests.get(url, headers=headers, timeout=60)
            if response.status_code in (403, 401) and attempt == 2:
                locator.refresh()
            if response.status_code != 206:
                last = f"status={response.status_code} host={url.split('/')[2]}"
                time.sleep(0.3 * (attempt + 1))
                continue
            if len(response.content) != (end - start + 1):
                last = f"len={len(response.content)} expect={end - start + 1}"
                continue
            return response.content
        except Exception as exc:  # noqa: BLE001 — 分片重试要吞瞬时网络错
            last = type(exc).__name__
            time.sleep(0.3 * (attempt + 1))
    raise RuntimeError(f"chunk {start}-{end} failed: {last}")


def download(name: str, size: int, dest: Path | None = None, pan_file: str | None = None) -> Path:
    out = dest or (cache_dir() / name)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    if size <= 0:
        raise ValueError(f"{name} size={size}")
    if out.exists() and out.stat().st_size == size:
        print("already complete", out, flush=True)
        return out
    if not tmp.exists():
        with tmp.open("wb") as handle:
            handle.truncate(size)
    mark = tmp.with_suffix(tmp.suffix + ".ok")
    finished: set[int] = set()
    if mark.exists():
        finished = {int(x) for x in mark.read_text().split() if x.strip().isdigit()}
    starts = list(range(0, size, CHUNK))
    pending = [start for start in starts if start not in finished]
    print(
        f"{name} size={size} chunks={len(starts)} pending={len(pending)} workers={WORKERS}",
        flush=True,
    )
    remote = pan_file or f"{inbox_path()}/{name}"
    locator = Locator(remote)
    t0 = time.time()
    done_bytes = len(finished) * CHUNK
    lock = threading.Lock()
    mark_lock = threading.Lock()

    def one(start: int) -> int:
        end = min(start + CHUNK, size) - 1
        data = fetch_chunk(locator, start, end)
        with lock:
            with tmp.open("r+b") as handle:
                handle.seek(start)
                handle.write(data)
        with mark_lock:
            with mark.open("a") as handle:
                handle.write(f"{start}\n")
        return len(data)

    got = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(one, start): start for start in pending}
        for fut in as_completed(futs):
            nbytes = fut.result()
            got += nbytes
            done_bytes += nbytes
            if got // (80 * 1024 * 1024) != (got - nbytes) // (80 * 1024 * 1024):
                dt = max(time.time() - t0, 1e-6)
                print(
                    f"  {done_bytes / 1e9:.2f}/{size / 1e9:.2f} GB {got / dt / 1e6:.1f} MB/s",
                    flush=True,
                )
    tmp.replace(out)
    if mark.exists():
        mark.unlink()
    print(f"saved {out} bytes={out.stat().st_size}", flush=True)
    return out
