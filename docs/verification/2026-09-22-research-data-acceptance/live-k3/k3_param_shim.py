"""Harness-side adapter: forward /v1/* to the local gateway, dropping params k3 rejects.

The candidate under test always sends ``temperature``; this gateway's kimi-k3
answers 400 for it (gpt-5.6-sol accepts it). Changing the candidate would change
the artifact under acceptance, so the fix belongs in the shell, not the code.

Declared deviation: sampling temperature becomes the provider default instead of
the caller's value. Nothing else is rewritten; body, headers and streaming pass
through untouched. This is a test harness, never a production path.
"""
from __future__ import annotations

import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 8080
DROP_KEYS = ("temperature",)
LISTEN_PORT = 8081
dropped_counter = {"requests": 0, "dropped": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep the probe log readable
        pass

    def _proxy(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        dropped_counter["requests"] += 1
        if body:
            try:
                payload = json.loads(body)
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                removed = [k for k in DROP_KEYS if k in payload]
                for key in removed:
                    payload.pop(key, None)
                if removed:
                    dropped_counter["dropped"] += 1
                    body = json.dumps(payload).encode()
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in {"host", "content-length", "connection"}}
        headers["Content-Length"] = str(len(body))
        conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=600)
        try:
            conn.request(method, self.path, body=body, headers=headers)
            upstream = conn.getresponse()
            self.send_response(upstream.status)
            for key, value in upstream.getheaders():
                if key.lower() in {"transfer-encoding", "connection", "content-length"}:
                    continue
                self.send_header(key, value)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            while True:
                chunk = upstream.read1(65536)
                if not chunk:
                    break
                self.wfile.write(b"%X\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        finally:
            conn.close()

    def do_POST(self):
        self._proxy("POST")

    def do_GET(self):
        self._proxy("GET")


if __name__ == "__main__":
    print(f"shim :{LISTEN_PORT} -> {UPSTREAM_HOST}:{UPSTREAM_PORT}, dropping {DROP_KEYS}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", LISTEN_PORT), Handler).serve_forever()
