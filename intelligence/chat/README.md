# 飞书 IM 入口（已退役）

`python3 -m intelligence.cli feishu-bot` 现在 **exit 2**，不连 WebSocket、不读凭证。
这和飞书 **Bitable 写入**退役是两件事：Bitable 是复盘表；这里是聊天机器人。

问答请用：

```bash
python3 -m intelligence.cli ask "<问题>"
```

生产会话走 Workbench Episode。旧旗标（`--echo` / `--app-id` 等）仍能解析，但一律进退役闸。

若本机曾经 `launchctl load` 过 `com.financeworkspace.feishu-bot`：

```bash
launchctl unload ~/Library/LaunchAgents/com.financeworkspace.feishu-bot.plist
```

本目录还留着历史实现与 launchd 模板，避免旧 import 崩；**不要再 load**。
`dream-collect` 仍可读历史 transcript jsonl，不必再跑 bot 采集。
