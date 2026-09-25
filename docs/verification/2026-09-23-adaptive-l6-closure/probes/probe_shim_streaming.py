"""Characterize the frozen L6 shim with loopback-only SSE; no model calls.

This diagnostic demonstrates buffering, not the cause of a historical timeout.
Use a fresh output path. The shim source is imported without modification.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shim", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x", encoding="utf-8") as output:
        spec = importlib.util.spec_from_file_location("frozen_l6_shim", args.shim)
        assert spec is not None and spec.loader is not None
        shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shim)
        first = b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
        last = b'data: [DONE]\n\n'
        pause = 0.6
        observations: list[dict[str, float]] = []

        class Upstream(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                row: dict[str, float] = {}
                observations.append(row)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(b"%X\r\n%s\r\n" % (len(first), first))
                self.wfile.flush()
                row["first_sent"] = time.monotonic()
                time.sleep(pause)
                row["end_sent"] = time.monotonic()
                self.wfile.write(b"%X\r\n%s\r\n0\r\n\r\n" % (len(last), last))
                self.wfile.flush()

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        shim.UPSTREAM_PORT = upstream.server_address[1]
        proxy = ThreadingHTTPServer(("127.0.0.1", 0), shim.Handler)
        servers = [upstream, proxy]
        threads = [threading.Thread(target=server.serve_forever) for server in servers]
        for thread in threads:
            thread.start()
        rows = []
        try:
            for name, port in (("direct_control", upstream.server_address[1]),
                               ("frozen_shim", proxy.server_address[1])):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                started = time.monotonic()
                try:
                    conn.request("POST", "/v1/chat/completions", body=b'{}',
                                 headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    chunk = response.read1(65536)
                    received = time.monotonic()
                    body = chunk + response.read()
                    assert response.status == 200 and body == first + last
                    row = observations[-1]
                    rows.append({
                        "path": name,
                        "first_read_bytes": len(chunk),
                        "total_bytes": len(body),
                        "first_byte_seconds": round(received - started, 4),
                        "upstream_to_client_seconds": round(received - row["first_sent"], 4),
                        "received_before_upstream_end": received < row["end_sent"],
                    })
                finally:
                    conn.close()
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=5)
        result = {
            "scope": "offline harness characterization; not independent QC or live acceptance",
            "shim_sha256": hashlib.sha256(args.shim.read_bytes()).hexdigest(),
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "model_requests": 0,
            "local_stub_requests": len(rows),
            "upstream_pause_seconds": pause,
            "observations": rows,
            "buffering_reproduced": (
                rows[0]["received_before_upstream_end"]
                and not rows[1]["received_before_upstream_end"]
                and rows[1]["first_read_bytes"] == len(first + last)
            ),
            "historical_timeout_root_cause_proven": False,
        }
        output.write(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        if not result["buffering_reproduced"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
