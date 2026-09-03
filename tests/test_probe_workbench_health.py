"""外部拨测脚本：阈值、状态翻转只通知一次、恢复通知、webhook 载荷。"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_workbench_health.sh"

pytestmark = pytest.mark.skipif(shutil.which("curl") is None, reason="需要 curl")


class _Fixture:
    def __init__(self) -> None:
        self.health_code = 200
        self.webhook_bodies: list[dict] = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - http.server 约定
                self.send_response(fixture.health_code)
                self.end_headers()

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                fixture.webhook_bodies.append(json.loads(self.rfile.read(length)))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_args):
                return

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"


@pytest.fixture()
def probe(tmp_path):
    fixture = _Fixture()
    state = tmp_path / "probe.state"

    def run(**env_overrides: str) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "PROBE_URL": f"{fixture.base}/api/health",
            "PROBE_STATE_FILE": str(state),
            "PROBE_WEBHOOK_URL": f"{fixture.base}/hook",
            "PROBE_FAIL_THRESHOLD": "2",
            "PROBE_TIMEOUT_SEC": "5",
        }
        env.update(env_overrides)
        return subprocess.run(
            ["bash", str(_SCRIPT)], env=env, capture_output=True, text=True, check=False
        )

    fixture.run = run  # type: ignore[attr-defined]
    fixture.state = state  # type: ignore[attr-defined]
    yield fixture
    fixture.server.shutdown()


def test_down_only_after_threshold_and_notifies_once(probe):
    assert probe.run().returncode == 0
    probe.health_code = 503
    first = probe.run()
    assert first.returncode == 0, "第一次失败还没到阈值，仍算 up"
    assert probe.webhook_bodies == []
    second = probe.run()
    assert second.returncode == 1
    assert "Workbench DOWN" in second.stdout
    assert len(probe.webhook_bodies) == 1
    assert "http=503" in probe.webhook_bodies[0]["text"]
    third = probe.run()
    assert third.returncode == 1
    assert len(probe.webhook_bodies) == 1, "持续 down 不重复通知"
    assert probe.state.read_text().splitlines() == ["down", "3"]


def test_recovery_notifies_and_resets_counter(probe):
    probe.health_code = 500
    probe.run()
    probe.run()
    assert len(probe.webhook_bodies) == 1
    probe.health_code = 200
    recovered = probe.run()
    assert recovered.returncode == 0
    assert "RECOVERED" in probe.webhook_bodies[-1]["text"]
    assert probe.state.read_text().splitlines() == ["up", "0"]


def test_feishu_payload_shape(probe):
    probe.health_code = 404
    probe.run(PROBE_WEBHOOK_FORMAT="feishu")
    probe.run(PROBE_WEBHOOK_FORMAT="feishu")
    body = probe.webhook_bodies[-1]
    assert body["msg_type"] == "text"
    assert "Workbench DOWN" in body["content"]["text"]


def test_unreachable_target_counts_as_failure(probe):
    result = probe.run(PROBE_URL="http://127.0.0.1:9/api/health")
    assert result.returncode == 0
    assert probe.state.read_text().splitlines() == ["up", "1"]
