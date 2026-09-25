"""飞书 IM 入口已退役：锁闸，不连 WebSocket、不读凭证。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from intelligence.chat import feishu_bot
from intelligence import cli

_REPO = Path(__file__).resolve().parents[2]


def test_cli_registers_retired_subcommand() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["feishu-bot", "--app-id", "a", "--app-secret", "b"])
    assert args.func is cli.cmd_feishu_bot
    help_text = parser.format_help()
    assert "已退役" in help_text


def test_cmd_feishu_bot_exits_2_without_reading_credentials() -> None:
    called: list[str] = []

    def boom(*_args: object, **_kwargs: object) -> None:
        called.append("creds")
        raise AssertionError("退役闸不得解析凭证")

    args = cli.build_parser().parse_args(["feishu-bot"])
    with mock.patch.object(feishu_bot, "build_config", side_effect=boom), mock.patch.object(
        feishu_bot, "resolve_credentials", side_effect=boom
    ):
        rc = cli.cmd_feishu_bot(args)
    assert rc == feishu_bot.RETIRED_EXIT
    assert called == []


def test_run_prints_retired_message(capsys) -> None:
    rc = feishu_bot.run(feishu_bot.BotConfig(app_id="a", app_secret="b"))
    assert rc == feishu_bot.RETIRED_EXIT
    err = capsys.readouterr().err
    assert "已退役" in err
    assert "intelligence.cli ask" in err
    assert "Workbench" in err


def test_module_main_exits_2_without_credentials() -> None:
    assert feishu_bot.main([]) == feishu_bot.RETIRED_EXIT
    assert feishu_bot.main(["--app-id", "a", "--app-secret", "b", "--echo"]) == feishu_bot.RETIRED_EXIT


def test_cli_process_exits_2_without_env_credentials() -> None:
    env = {k: v for k, v in os.environ.items() if k not in {"FEISHU_APP_ID", "FEISHU_APP_SECRET"}}
    proc = subprocess.run(
        [sys.executable, "-m", "intelligence.cli", "feishu-bot"],
        cwd=str(_REPO),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == feishu_bot.RETIRED_EXIT
    assert "已退役" in proc.stderr
    assert "ask" in proc.stderr


def test_cli_help_is_side_effect_free() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "intelligence.cli", "feishu-bot", "--help"],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "已退役" in proc.stdout
