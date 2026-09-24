#!/usr/bin/env python3
"""运维告警：本机通知 + 落盘一行，零外部依赖、零凭证。

取代 `scripts/notify_feishu.py`（2026-09-11 随飞书自建应用一起退役）。原来那条
链路已经形同虚设：日志里每次都是 `notify_feishu: 异常 HTTP Error 400`——token
换得到，`GET /im/v1/chats` 缺 `im:chat` 权限，也就是说**告警从来没送达过**，
而调用方全是 `|| true` / `except: pass`，谁都不知道。

新通道两条腿，都不依赖网络和密钥：

1. **落盘**：`~/.finance-runtime/alerts.log` 追加一行 `ISO时间\t消息`。这是真凭据，
   事后 `tail` 就能回答「昨晚到底报没报」——飞书那条链路恰恰答不了这个问题。
2. **弹窗**：macOS `osascript display notification`（`run_review_sync.py` 里本来
   就在用的同一招）。GUI 会话不在时静默失败，不影响落盘。

约定与旧版一致，调用方不用改语义：任何异常只打印不抛出，`send_alert` 返回
True/False，CLI 退出码 0=已记录 1=失败，方便 shell 里 `|| true` 兜底。

用法：python3 scripts/notify_ops.py "复盘链失败：同步段 rc=3"
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ALERT_LOG = Path.home() / ".finance-runtime" / "alerts.log"


def _append_log(text: str) -> bool:
    try:
        target = ALERT_LOG.resolve()
        for name in ("FINANCE_CODE_ROOT", "FINANCE_GENERATION_CODE_ROOT"):
            raw = os.environ.get(name, "").strip()
            if raw and target.is_relative_to(Path(raw).expanduser().resolve()):
                raise ValueError(f"alert log resolves inside {name}: {target}")
        ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ALERT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat(timespec='seconds')}\t{text}\n")
        return True
    except Exception as exc:  # noqa: BLE001 - 告警脚本自身绝不抛出
        print(f"notify_ops: 落盘失败 {exc}", file=sys.stderr)
        return False


def _desktop_notify(text: str) -> None:
    """尽力而为的桌面弹窗；没有 GUI 会话时静默跳过。"""
    safe = text.replace('"', "'").replace("\\", "/")[:200]
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{safe}" with title "finance-workspace 告警" sound name "Basso"',
            ],
            timeout=10,
            capture_output=True,
        )
    except Exception:  # noqa: BLE001
        pass


def send_alert(text: str, *, desktop: bool = True) -> bool:
    """记一条告警。落盘成功即算成功——弹窗是锦上添花，不作为成败依据。

    ``desktop=False`` 只落盘。给**自己已经弹过窗**的调用方用：两个夜跑 shell 里
    `notify()` 的第一行就是内联 `osascript`（零依赖，必达本机），再让这里弹一次
    就成了同一件事响两声，看的人会以为出了两个问题。
    """
    text = (text or "").strip()
    if not text:
        return False
    ok = _append_log(text)
    if desktop:
        _desktop_notify(text)
    return ok


def main() -> int:
    argv = list(sys.argv[1:])
    desktop = True
    if "--no-desktop" in argv:
        argv = [a for a in argv if a != "--no-desktop"]
        desktop = False
    text = " ".join(argv).strip() or sys.stdin.read().strip()
    if not text:
        print("用法: notify_ops.py [--no-desktop] <消息文本>", file=sys.stderr)
        return 1
    return 0 if send_alert(text, desktop=desktop) else 1


if __name__ == "__main__":
    raise SystemExit(main())
