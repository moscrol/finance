"""本机告警通道的最小契约。

这条链路的前身（`notify_feishu.py`）没有任何测试，于是它每晚 HTTP 400、
告警一次都没送达，却没人发现——`|| true` 把证据也一起吞了。所以这里钉三件事：

1. 落盘真的落了（这是事后能回答「昨晚到底报没报」的唯一凭据）；
2. 弹窗可关（夜跑 shell 自己已经内联弹过一次，不能再弹第二次）；
3. 弹窗失败不影响成败判定，且任何情况下都不抛异常——告警脚本炸了不许拖垮被告警的流程。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "notify_ops.py"


@pytest.fixture
def notify_ops(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("notify_ops_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ALERT_LOG", tmp_path / "nested" / "alerts.log")
    return module


def test_alert_is_appended_with_timestamp(notify_ops):
    with mock.patch.object(notify_ops, "_desktop_notify") as popup:
        assert notify_ops.send_alert("同步段失败 rc=3") is True
    lines = notify_ops.ALERT_LOG.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    stamp, _, text = lines[0].partition("\t")
    assert text == "同步段失败 rc=3"
    assert stamp.startswith("20") and "T" in stamp  # ISO 时间戳，便于 tail 后按天筛
    popup.assert_called_once()


def test_second_alert_appends_not_overwrites(notify_ops):
    with mock.patch.object(notify_ops, "_desktop_notify"):
        notify_ops.send_alert("第一条")
        notify_ops.send_alert("第二条")
    lines = notify_ops.ALERT_LOG.read_text(encoding="utf-8").splitlines()
    assert [line.split("\t", 1)[1] for line in lines] == ["第一条", "第二条"]


def test_desktop_can_be_switched_off(notify_ops):
    """夜跑 shell 自己内联弹过窗；这里再弹就是同一件事响两声。"""
    with mock.patch.object(notify_ops, "_desktop_notify") as popup:
        assert notify_ops.send_alert("staging 失败", desktop=False) is True
    popup.assert_not_called()
    assert "staging 失败" in notify_ops.ALERT_LOG.read_text(encoding="utf-8")


def test_cli_no_desktop_flag_is_not_part_of_the_message(notify_ops, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["notify_ops.py", "--no-desktop", "⚠️ S7", "rc=2"])
    with mock.patch.object(notify_ops, "_desktop_notify") as popup:
        assert notify_ops.main() == 0
    popup.assert_not_called()
    assert notify_ops.ALERT_LOG.read_text(encoding="utf-8").split("\t", 1)[1].strip() == "⚠️ S7 rc=2"


def test_popup_failure_does_not_fail_the_alert(notify_ops):
    """没有 GUI 会话（launchd 后台）时 osascript 会失败，落盘仍必须算成功。"""
    with mock.patch.object(notify_ops.subprocess, "run", side_effect=OSError("no gui")):
        assert notify_ops.send_alert("无头环境") is True
    assert "无头环境" in notify_ops.ALERT_LOG.read_text(encoding="utf-8")


def test_unwritable_log_returns_false_without_raising(notify_ops, tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("我是文件不是目录", encoding="utf-8")
    notify_ops.ALERT_LOG = blocked / "alerts.log"
    with mock.patch.object(notify_ops, "_desktop_notify"):
        assert notify_ops.send_alert("落不了盘") is False  # 不抛异常，只如实报 False


def test_empty_message_is_refused(notify_ops):
    with mock.patch.object(notify_ops, "_desktop_notify") as popup:
        assert notify_ops.send_alert("   ") is False
    popup.assert_not_called()
    assert not notify_ops.ALERT_LOG.exists()
