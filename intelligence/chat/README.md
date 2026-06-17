# 飞书 chat 入口（B-S3：接 `ask` 交互卡片 + 按钮回调）

> 决策 2 定稿：**v1 飞书内部，公开版二期**。当前是 **B-S3 接 `ask`（交互卡片）**——
> 收到文本题材词，**进程内**调 `intelligence` 的 `ask`，数秒回**六段**（结论/证据链/分歧反证/
> 后续验证点/交易含义/引用来源）+ `[S#]/[G#]/[R#]` 引用，渲染成**飞书交互卡片**（抬头按召回
> 状态变色：PASS 绿 / WARN 橙 / FAIL 灰）；收到非文本回友好提示。
> `--reply-format text` 退回 **B-S2 纯文本**；`--echo` 退回 **B-S0 回声 bot**（只验证长连接，不接 `ask`）。

## 这一步做什么 / 不做什么

- ✅ 长连接（WebSocket）接收 `im.message.receive_v1`；文本 → **进程内** `run_ask` → 渲染**六段交互卡片**回去。
- ✅ 卡片：彩色抬头（按召回状态）+ `主题/盘面/召回` 摘要行 + 六段 markdown 分块 + 编号引用；超长按段截断并注明。
- ✅ `--reply-format text` 退回纯文本；`--echo` 保留 B-S0 回声自检；非文本统一回「暂仅支持文本」提示；检索异常降级为友好提示、不串味。
- ✅ 卡片上的**按钮交互**（🔍 深钻 / 🔁 换题材 / 🔗 看证据链）已接入（B-S3b）：点击经 `card.action.trigger` 回调路由，即时 toast + 后台线程补发后续卡片。**需在飞书后台开启「卡片回调」事件订阅**。
- ❌ 多模态（语音/图片）属后续 B-S4 阶段，尚未接入。
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
# 仓库根目录执行（默认 ask 模式 + 交互卡片：发题材词 → 六段卡片 + 引用）
python3 -m intelligence.cli feishu-bot
# 知识库不在同级时显式指向：--kb-wiki /path/to/knowledge-base-private/wiki
# 退回 B-S2 纯文本（不发卡片）：--reply-format text
# 退回 B-S0 自检（只回声、不接 ask）：--echo
# 开模块 fan-out（更全但更慢、可能触 DuckDB）：--ask-modules
# 其它：--ask-top-companies N | --ask-max-chars N（回复正文上限，超长截断）| --log-level debug
```

在飞书里给 bot 发个题材词（如「液冷」），数秒收到六段**交互卡片** + `[S#]/[G#]/[R#]` 引用即说明 B-S3 打通；
`--reply-format text` 时回纯文本（B-S2）；`--echo` 时发什么回什么即说明 B-S0 长连接通。

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
- [ ] 飞书里给 bot 发题材词「液冷」，数秒收到**六段交互卡片**（彩色抬头 + 摘要行 + 六段 + `[S#]/[G#]/[R#]` 引用）；
- [ ] 加 `--reply-format text` 进程发「液冷」收到等价**纯文本**六段（B-S2 回退）；
- [ ] 另起 `--echo` 进程发「你好」收到「你好」回声（B-S0 自检）；
- [ ] 发一张图片，收到「暂仅支持文本」提示；
- [ ] 回复期间 `lsof` 证 bot 进程**零** `market.duckdb` 句柄；
- [ ] `launchctl load` 后进程常驻，杀掉能被 `KeepAlive` 拉起。

## 卡片按钮回调（B-S3b，已接入）

卡片底部 3 个按钮（🔍 深钻 / 🔁 换题材 / 🔗 看证据链），每个按钮 `value` 带 `{action, query, theme}`；
点击经 `card.action.trigger` 回调，`run()` 里注册的 `on_card_action` 解出动作后：

- **秒级响应**：回调同步只返回一个 `toast` 提示（飞书要求回调快速返回）；
- **重活后台跑**：深钻=`use_modules=True, detail=True` 重跑回更全的卡片；看证据链=重跑后展开完整证据链卡片；
  换题材=纯引导卡（不重跑 ask，提示用户回复一个新题材词）。重活在 daemon 线程里跑完再 `reply` 回原消息。
- 仅 `--reply-format card` 模式出按钮；`text` 模式无按钮。任何重跑异常都降级为灰底提示卡，bot 不崩；仍保持零 DuckDB。

## 后续阶段

B-S4 多模态（语音走飞书 ASR、图片走 pdf-ingest）。公开版作为合规门控的独立二期。
