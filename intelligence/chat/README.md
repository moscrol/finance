# 飞书 chat 入口（B-S2：接 `ask` 纯文本）

> 决策 2 定稿：**v1 飞书内部，公开版二期**。当前是 **B-S2 接 `ask`（纯文本）**——
> 收到文本题材词，**进程内**调 `intelligence` 的 `ask`，数秒回**六段**（结论/证据链/分歧反证/
> 后续验证点/交易含义/引用来源）+ `[S#]/[G#]/[R#]` 引用；收到非文本回友好提示。
> 加 `--echo` 退回 **B-S0 回声 bot**（只验证长连接，不接 `ask`）。

## 这一步做什么 / 不做什么

- ✅ 长连接（WebSocket）接收 `im.message.receive_v1`；文本 → **进程内** `run_ask` → 渲染六段纯文本回去。
- ✅ `--echo` 保留 B-S0 回声自检；非文本统一回「暂仅支持文本」提示；检索异常降级为友好提示、不串味。
- ❌ 不渲染交互卡片、不做多模态（语音/图片）——都是后续 B 阶段。
- ❌ **零 DuckDB**：`ask` 只读 `market_feature_store/exports/*-theme-candidates.json` + 知识库 `wiki/relations`；
  模块 fan-out 默认**关**（`--ask-modules` 才开，可能触 DuckDB、变慢）。不碰 `exec.industry7view.com` 通用 exec 隧道。

## 架构（为什么不需要公网入站）

```
飞书开放平台  ←——长连接(WebSocket，出站)——  feishu_bot 进程（常驻 Mac，launchd）
                                              └─ 收到事件 → 进程内 run_ask 六段（--echo 时回声）→ 飞书 reply API
```

bot 从 Mac **主动外连**飞书，全程出站。**无需**公网回调 URL、域名 ICP 备案或入站隧道。

## 1. 装依赖

长连接需官方 SDK `lark-oapi`（本仓其余命令仍零依赖）：

```bash
pip install -r intelligence/chat/requirements.txt
```

## 2. 凭证（永不进 git）

复用现有飞书自建应用的 `app_id` / `app_secret`，按优先级取：

1. 环境变量 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`；
2. `~/.claude/shared/feishu_config.json`（仓外，本机现有飞书配置）。

若 `feishu_config.json` 里还没有 `app_id` / `app_secret` 字段，补上即可（该文件在仓外、不入 git）：

```json
{ "app_id": "cli_xxxxxxxxxxxx", "app_secret": "xxxxxxxxxxxxxxxxxxxxxx", "...": "其余现有字段保留" }
```

## 3. 飞书开放平台一次性配置（open.feishu.cn，你来操作）

在你现有自建应用里：

1. **添加「机器人」能力**（应用功能 → 机器人 → 启用）。
2. **权限管理**：开 `im:message`（接收消息）、`im:message:send_as_bot`（发消息）。
3. **事件订阅**：订阅方式选 **「长连接」**；添加事件 **「接收消息 `im.message.receive_v1`」**。
   - 长连接模式下无需填回调 URL，也不必配 `Encrypt Key` / `Verification Token`。
4. **创建版本并发布**，等审核/生效。
5. 让 bot 能收到消息：把机器人**加进一个群**，或在「机器人」里允许单聊。

## 4. 跑起来

```bash
# 仓库根目录执行（默认 ask 模式：发题材词 → 六段 + 引用）
python3 -m intelligence.cli feishu-bot
# 知识库不在同级时显式指向：--kb-wiki /path/to/knowledge-base-private/wiki
# 退回 B-S0 自检（只回声、不接 ask）：--echo
# 开模块 fan-out（更全但更慢、可能触 DuckDB）：--ask-modules
# 其它：--ask-top-companies N | --ask-max-chars N（回复字数上限，超长截断）| --log-level debug
```

在飞书里给 bot 发个题材词（如「液冷」），数秒收到六段结构化回复 + `[S#]/[G#]/[R#]` 引用即说明 B-S2 打通；
加 `--echo` 时发什么回什么即说明 B-S0 长连接通。

## 5. 常驻（launchd）

模板：`intelligence/chat/com.financeworkspace.feishu-bot.plist`。安装步骤：

```bash
REPO_DIR="$(pwd)"                       # 在仓库根目录执行
PY="$(which python3)"
mkdir -p "$REPO_DIR/logs"
# 替换占位后装到用户 LaunchAgents（不要把含密钥的 plist 提交进 git）
sed -e "s#__REPO_DIR__#${REPO_DIR}#g" -e "s#__PYTHON__#${PY}#g" \
    intelligence/chat/com.financeworkspace.feishu-bot.plist \
    > ~/Library/LaunchAgents/com.financeworkspace.feishu-bot.plist
launchctl load  ~/Library/LaunchAgents/com.financeworkspace.feishu-bot.plist   # 启动
launchctl list | grep feishu-bot                                               # 确认在跑
# 日志：logs/feishu-bot.out.log / logs/feishu-bot.err.log
# 停止：launchctl unload ~/Library/LaunchAgents/com.financeworkspace.feishu-bot.plist
```

> `logs/` 已被 `.gitignore`（`*.log`）忽略；plist 模板本身不含密钥，替换占位后的副本请放在
> `~/Library/LaunchAgents/`、不要提交。

## 验证清单（Mac 在线后）

- [ ] `pip show lark-oapi` 有版本；
- [ ] `python3 -m intelligence.cli feishu-bot` 打印「长连接接入中（ask 模式）」且不报错退出；
- [ ] 飞书里给 bot 发题材词「液冷」，数秒收到**六段** + `[S#]/[G#]/[R#]` 引用；
- [ ] 另起 `--echo` 进程发「你好」收到「你好」回声（B-S0 自检）；
- [ ] 发一张图片，收到「暂仅支持文本」提示；
- [ ] 回复期间 `lsof` 证 bot 进程**零** `market.duckdb` 句柄；
- [ ] `launchctl load` 后进程常驻，杀掉能被 `KeepAlive` 拉起。

## 后续阶段（不在 B-S2 内）

B-S3 交互卡片（深钻/换题材/看证据链按钮）→ B-S4 多模态（语音走飞书 ASR、图片走 pdf-ingest）。
公开版作为合规门控的独立二期。
