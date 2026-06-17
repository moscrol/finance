"""飞书 chat 入口（决策 2：v1 飞书内部，公开版二期）。

本包托管「飞书机器人 ←长连接→ 常驻进程」这条链路。当前阶段 B-S0 = 回声 bot：
仅验证长连接打通（收到 ``im.message.receive_v1`` 即把文本原样回声），**还未**接入
``intelligence.cli ask``。后续阶段再把回声替换为 in-process 调 ``ask``、交互卡片、多模态。

设计取舍见 ``intelligence/chat/README.md``。bot 进程从 Mac 主动外连飞书（长连接 /
WebSocket），无需公网回调 URL、ICP 或入站隧道；凭证复用现有飞书自建应用，永不进 git。
"""
