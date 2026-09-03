# Hosted Alpha 身份门与配额：部署 Runbook

- 日期：2026-08-27；2026-09-03 增补 §1.4 并发守卫、§2 第 5 步 Bypass、§6 备份与拨测、§7 接线顺序
- 代码：`intelligence/api/auth.py`（认证 + 身份改写）、`intelligence/api/quota.py`（日配额）、
  `intelligence/api/app.py` `RunSupervisor`（准入与排队）、`scripts/install_workbench_backup.py`、`scripts/probe_workbench_health.sh`
- 上游决策：`docs/superpowers/specs/2026-07-11-workbench-self-use-to-invite-beta-design.md` §10.2
  「服务端可信 user_id、禁止客户端自报 user」。本文是其 **Alpha 缩水实现**（3–10 个可信
  内测用户），不是阶段 C 全量（PostgreSQL / 托管认证 / 证据网关仍按设计稿排期）。

## 0. 一句话原理

公网流量走 Cloudflare Tunnel 回源到本机 `127.0.0.1:8792`（Mac 不开任何入站端口）；
Cloudflare Access 在边缘完成邮箱 OTP 登录并给每个请求注入一枚 JWT；
后端中间件**验签** JWT → 邮箱查邀请名单得 `user_id` → **强制改写**请求里一切
客户端身份声明（`?user=` 与 JSON body 的 `"user"` 字段）。存量端点零改动。

### 为什么验签 JWT，而不是信任 Access 的明文邮箱头

Access 同时注入明文头 `Cf-Access-Authenticated-User-Email`。信任它的前提是
「没有任何流量能绕过 Cloudflare 直达后端」——本机其他进程、配置错误的第二条
隧道都能伪造明文头。验签把信任锚定到 Cloudflare 团队域的公钥（JWKS）上，
伪造者必须持有 Cloudflare 的私钥才能通过。这是「认不出来就 fail closed」。

> 可迁移知识点：authn（你是谁）只能由服务端从**可验证凭证**推导；任何客户端
> 自报字段（query/header/body）都不可信。这条在任何 Web 系统通用，面试常考。

### 方案选型对比（为什么是 CF Tunnel + Access）

| 方案 | 用户门槛 | 暴露面 | 适用 |
|---|---|---|---|
| Tailscale 私网 | 装客户端、进 tailnet | 零公网 | 2–3 个极信任的人 |
| **CF Tunnel + Access（本文）** | 零安装，浏览器 + 邮箱验证码 | 认证在边缘层，Mac 不开端口 | Alpha 3–10 人 |
| VPS/容器部署 | 零安装 | 标准生产形态 | Beta；需解决 DuckDB 快照同步、KB 索引搬迁、Keychain→Secret Manager、web_search 换源 |

认证选型：设计稿已定「优先托管认证，不自建密码系统」。CF Access 是零代码近似；
Beta 换托管 IdP（Clerk / Supabase Auth / Auth0）+ 邀请码时，只需替换
`CfAccessVerifier`（换 JWKS 地址与 claim 名），中间件与名单机制原样保留。

## 1. 服务端配置

### 1.1 邀请名单

JSON 对象文件：邮箱（大小写不敏感）→ user_id（须符合 `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`）：

```json
{
  "you@example.com": "linxiaoqi5111",
  "friend-a@example.com": "alpha-friend-a"
}
```

建议放 `~/.local/share/finance-workbench/beta-users.json`（不进 git）。
**热重载**：文件 mtime 变化自动生效，加人无需重启、不打断在跑的 SSE；
重载失败（JSON 坏了）保留旧名单，不放行任何新身份。

### 1.2 环境变量（加进 `~/.local/bin/start-finance-workbench`）

```bash
export WORKBENCH_AUTH_MODE=cf_access
export WORKBENCH_CF_ACCESS_TEAM_DOMAIN=<team>.cloudflareaccess.com   # Zero Trust 团队域
export WORKBENCH_CF_ACCESS_AUD=<Access 应用的 Application Audience (AUD) tag>
export WORKBENCH_AUTH_USER_MAP=$HOME/.local/share/finance-workbench/beta-users.json

# 日配额（预占式；0 或不设 = 不限）。owner 豁免：
export WORKBENCH_DAILY_RUN_QUOTA=20
export WORKBENCH_QUOTA_EXEMPT_USERS=linxiaoqi5111

# 内测用户没有本机 Chrome CDP，web_search 必须关闭（或换 server-side API 后再开）：
export FINANCE_WEB_SEARCH=0

# 方法论端点门（防蒸馏第二道闸）：非名单用户访问 run trace / run context /
# 学习面板一律 403。未设置 = 不限制：
export WORKBENCH_FULL_ACCESS_USERS=linxiaoqi5111

# 并发守卫（见 1.4）。三项默认全等于历史行为（2 worker / 不限每用户 / 队列无界）：
export WORKBENCH_RUN_WORKERS=4                 # run 线程数；run 主要在等 LLM，I/O 等待不吃 GIL
export WORKBENCH_MAX_ACTIVE_RUNS_PER_USER=1    # 同一用户同时只许 1 个在途（排队+执行），第 2 个 429
export WORKBENCH_MAX_QUEUED_RUNS=4             # worker 全忙后最多排 4 个，再来 429 + Retry-After
```

配置不完整（cf_access 缺团队域/AUD/名单）**启动即抛**，不带病上线。
依赖：`PyJWT[crypto]>=2.8`（已在 `intelligence/api/requirements.txt`，venv 已含）。

### 1.4 并发守卫：三条规则与用户会看到什么

代码：`intelligence/api/app.py` `RunSupervisor`（测试 `intelligence/tests/test_api_run_admission.py`）。

| 规则 | 触发 | 用户看到 | 为什么 |
|---|---|---|---|
| 每用户在途上限 | 同一用户已有 ≥N 个 run 在排队或执行 | 429「你还有 1 个研究在进行中，请等它完成或先取消」，`Retry-After: 15` | 一个人连点五次不该占满全部 worker；公平性 |
| 系统队列上限 | worker 全忙且队列已满 | 429「系统繁忙：x 个在跑、y 个在排队」，`Retry-After: 30` | 明说「等不了」好过静默排队然后超时 |
| 排队不计时 | 进队后等 worker | 状态先 `queued` 再 `running`；15 分钟执行期限从**真正开跑**起算 | 此前期限从提交起算，排队 12 分钟只剩 3 分钟可跑 |

细节：
- `WORKBENCH_QUOTA_EXEMPT_USERS` 里的用户（owner）**同样免于每用户上限**——自用脚本会连发；但系统队列上限对所有人生效，它保护的是机器不是公平性。
- 准入预检在占配额**之前**，被拒的请求不留 run 记录、不扣当日次数；预检与入队之间输了竞态的极少数请求，run 记 `failed/admission_rejected`、配额退回（`RunQuota.release`）。
- 对话路径同样受控：被拒时助手气泡收口为 failed 并附「本轮未受理」，不会永远转圈。
- 重启恢复的 run 不过准入（崩溃前已受理），否则同一用户两个在途 run 会丢一个。
- `GET /api/readiness` 的 `workers` 段新增 `queued` / `max_active_per_user` / `max_queued`，拨测和排障看这里。
- 互斥范围仍是**单进程**（与配额同一条边界，见 §4.2）。多 worker 进程部署前必须换共享存储。

### 1.5 额度账本：赠送 + 月度充值（2026-09-03）

代码：`intelligence/api/credits.py` `CreditStore`（测试 `intelligence/tests/test_api_credits.py`，22 例）；
运营入口 `scripts/workbench_credits.py`。与 §1.2 的**日配额**是两件事：日配额是防刷的节流阀（一天最多 N 次），
额度账本是**钱包**（一共还能用多少次，由 owner 赠送和用户充值决定）。两道同时生效：先占钱包、再占日配额，
任一拒绝把另一道退回。

```bash
export WORKBENCH_CREDITS=1                 # 开钱包。不设 = 历史行为，不扣不查
export WORKBENCH_CREDITS_SIGNUP_GIFT=30    # 用户第一次提问时自动赠送的次数（0/不设 = 不自动送，全靠手工 grant）
# 豁免复用 WORKBENCH_QUOTA_EXEMPT_USERS（owner 不记账）
```

| 概念 | 是什么 | 怎么产生 |
|---|---|---|
| `gift` 赠送 | 不过期（也可给到期日），owner 给的缓冲 | 首次提问自动送 `SIGNUP_GIFT` 次；或 `grant --kind gift` |
| `monthly` 月度充值 | 默认 30 天后到期，用不完作废 | 收到钱后 `grant --kind monthly --runs 200`；将来支付回调调同一个 `CreditStore.grant` |
| 消费顺序 | **先到期的先扣，不过期的最后扣**；同到期日按授予先后 | 月度额度是买来这个月用的，不该被赠送额度挤掉 |
| 单位 | 1 run = 1 次，与日配额同口径（不按 token，见 §4.3） | — |

```bash
# 用 8792 同一个 users 根（FORESIGHT_USERS_DIR 与启动器一致）；写完立即生效，服务端每次扣额都重读文件
python3 scripts/workbench_credits.py grant   --user alpha-friend-a --kind gift    --runs 30  --note "内测赠送"
python3 scripts/workbench_credits.py grant   --user alpha-friend-a --kind monthly --runs 200 --note "9 月充值 ¥xx"   # 30 天到期
python3 scripts/workbench_credits.py grant   --user alpha-friend-a --kind monthly --runs 200 --expires 2026-10-01     # 到 9 月底
python3 scripts/workbench_credits.py balance --user alpha-friend-a
python3 scripts/workbench_credits.py list
python3 scripts/workbench_credits.py revoke  --user alpha-friend-a --grant-id g-2026… --note "退款"
python3 scripts/workbench_credits.py history --user alpha-friend-a
```

用户看到什么：额度为 0 时 `POST /api/runs` 与对话消息都回 429「研究额度已用完（剩余 0 次）。请联系管理员充值…」，
不带 `Retry-After`（不是等一会就有，别让客户端自动重试）；`GET /api/credits?user=` 给余额、各笔授予、最近到期日；
`GET /api/workbench/bootstrap` 里多一个 `credits` 摘要（`remaining` / `next_expiry`）；会话栏页脚显示「剩余额度 N 次 · MM-DD 到期」，0 次时警示色并提示充值（提问受理与 run 收口时刷新）。

账本长什么样：`users/<id>/credits.json`——`grants`（每笔授予的 `amount / remaining / expires_at`）+ `ledger`
（grant / run / refund / revoke 逐笔流水，append-only，对账用）。旁边的 `credits.lock` 是 **flock 文件锁**：CLI 与
服务进程同写一份账本必须靠它，进程内锁护不住；变异实测去掉它跨进程用例必红。

纪律：
- **预占**：与日配额同一套语义，占不到直接 429、零副作用；准入拒收 / 日配额拒绝 / 落盘失败三种「我们自己没服务到」
  的情形都把额度退回（`release` 退最近一次扣账）。**run 跑完失败不自动退**——分不清是谁的锅，owner 用 `grant` 补偿。
- **坏账本 fail closed**：`credits.json` 解析不了 → 503「额度账本损坏」且不改写文件。钱的账本坏了不能当空账本重建
  （那等于把余额清零再送一次赠送）。`balance` / `list` 会标出损坏的用户。
- 过期 grant 的余量不计入余额、不可用、也不删（账在）；`revoke` 只清余量不改历史。
- 自动赠送的判据是「还没有账本文件」，不是「余额为 0」——用完不会再送。

### 1.3 行为矩阵

| WORKBENCH_AUTH_MODE | /api/*（豁免外） | ?user= 与 body user | 适用 |
|---|---|---|---|
| `off`（默认） | 不拦 | 客户端自报生效（历史行为） | 本机自用，现 8792 不受影响 |
| `cf_access` | 无有效 JWT → 401；邮箱不在名单 → 403 | **一律被服务端身份覆盖** | 内测 |

豁免路径（本机运维探活，剥掉 user 参数后放行）：
`/api/health`、`/api/health/live`、`/api/readiness`、`/api/health/ready`。
非 `/api/` 路径（前端静态 bundle）不拦，边缘层已有 Access。

## 2. Cloudflare 侧（一次性，约 20 分钟）

人工步骤已收成向导（**不改 8792 启动器、不 kickstart**；配完的 env 落
`~/.local/share/finance-workbench/alpha.env`，接上启动器需你确认）：

```bash
bash scripts/hosted-alpha-wizard.sh
```

前提：Cloudflare 账号 + 一个托管在 Cloudflare 的域名（免费计划够用）。现有隧道
`a77-exec` 已服务 `*.industry7view.com`，向导默认建议在同一条隧道加
`beta.industry7view.com → 127.0.0.1:8792`，而不是再开一条（两条 cloudflared 抢同一份 cert 会互相踩）。

**顺序：先建 Access 应用（下面第 1–5 条），再加 DNS 与 ingress。** 主机名一旦回源到 8792 而 Access
还没建，8792 就是无认证公网可达——后端 auth 此刻仍是 `off`。Access 按主机名配置，DNS 不存在时也能先建。

Zero Trust 控制台 → Access → Applications → Add：
1. 类型 Self-hosted，域名填 `beta.<你的域名>`；
2. Policy：Allow，Include = Emails（逐个填邀请邮箱）——与后端名单**双层白名单**；
3. 登录方式默认 One-time PIN（邮箱验证码），无需接 IdP；
4. 建好后复制 **Application Audience (AUD) tag** → `WORKBENCH_CF_ACCESS_AUD`；
   团队域在 Zero Trust → Settings → Custom Pages 可见（`<team>.cloudflareaccess.com`）。
5. **再建一个** Self-hosted 应用，域名 `beta.<你的域名>`、路径 `api/health`，Policy 选 **Bypass**、
   Include = Everyone。这是给 VPS 外部拨测（§6.2）放行的：后端本来就豁免 `/api/health*`
   （`auth.py` `_EXEMPT_PATHS`，且剥掉 `user` 参数只暴露默认身份的健康信息），差的只是边缘层这一道。
   不配这条，拨测拿到的永远是 302 登录页。

Access 建好之后，再开门（在现有隧道上，不新建 tunnel）：

```bash
cp ~/.cloudflared/config.yml ~/.cloudflared/config.yml.bak.$(date +%Y%m%d%H%M%S)
# 在 ~/.cloudflared/config.yml 的 ingress: 列表最前面插入两行：
#   - hostname: beta.<你的域名>
#     service: http://127.0.0.1:8792
cloudflared tunnel ingress validate
cloudflared tunnel ingress rule https://beta.<你的域名>/     # 应命中 8792 那条
cloudflared tunnel route dns a77-exec beta.<你的域名>
launchctl kickstart -k gui/$(id -u)/com.cloudflare.cloudflared   # 挂在用户域，不要 sudo/system
```

## 3. 验收清单（改完必跑）

```bash
# 1) 本机探活豁免仍通
curl -s http://127.0.0.1:8792/api/health | head -c 200

# 2) 本机直打业务 API（无 JWT）→ 401
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8792/api/conversations   # 期望 401

# 3) 浏览器走 beta.<域名> → 邮箱 OTP → 页面可用；bootstrap 返回的 user 是名单里的 user_id
# 4) 冒充测试：登录 A 账号后 F12 改 fetch 加 ?user=<B 的 id> → 返回的仍是 A 的数据
# 5) 名单外邮箱登录（若边缘策略放行了）→ 后端 403
# 6) 配额：普通用户发第 N+1 个问题 → 429 中文提示
# 7) 并发：同一账号开两个标签页几乎同时提问 → 第二个 429「在进行中」；取消第一个后可再发
# 8) 备份：python3 scripts/install_workbench_backup.py run（读 plist 同款 env）→ VPS 上
#    <target>/latest 指向今天、last-success.txt 是今天；再按 §6.1 恢复流程试还原一个测试用户目录
# 9) 拨测：VPS 上手跑一次 probe 脚本 → 退出码 0；把 8792 停 3 分钟 → 收到 DOWN 通知，拉起后收到 RECOVERED
```

自动化：`intelligence/tests/test_api_auth.py`（21 例）、`test_api_quota.py`（10 例）、
`test_api_run_admission.py`（8 例）覆盖验签/冒充/豁免/回归/并发不超卖/准入与排队，
`tests/test_install_workbench_backup.py`、`tests/test_probe_workbench_health.py` 覆盖备份快照与拨测状态机。

## 3.5 防蒸馏立场（为什么是这三道闸）

被蒸馏的完整条件是：**稳定入口 + 大批量采样 + 完整推理过程可见**。彻底防不住
（能看到输出就能学），能做的是抬成本、去教材、可追责：

1. **日配额**掐吞吐——蒸馏需要成百上千次系统性采样，`WORKBENCH_DAILY_RUN_QUOTA=20`
   之下扫完题材空间要几个月；
2. **方法论端点门**去教材——蒸馏一套 agent 最值钱的不是答案文本，而是
   trace 里的工具编排顺序、证据组装与纠偏回路（对照自家蒸 Knevo 的经验：
   同题多采样 + 推理过程是蒸馏的两大原料）。内测用户只拿到回答与引用；
3. **协议追责**——内测协议写明禁止批量抓取/蒸馏/转售，`interactions.jsonl`
   按用户留痕，异常提问模式（模板化、系统性覆盖）人工可查。

结构性护城河不在文本层：盘面 DuckDB 历史、知识库证据链、corrections 画像
和每日数据管线不随回答外泄，蒸馏者拿不到底层数据与持续更新。

## 4. 已知边界（Alpha 明知妥协项，Beta 前必须处理）

1. **知识库未脱敏**：`kb_search`/`evidence_*` 仍连全量私有 KB（含研报正文、私有笔记）。
   Alpha 仅限可信朋友 + 口头/书面协议；设计稿的证据发布状态机
   （candidate→published）与公开索引是 Beta 硬门槛，未做前不得扩员。
2. **配额与准入的互斥范围都是单进程**：配额 = 进程内锁 + `users/<id>/run_quota.json`；
   准入 = `RunSupervisor` 锁内数自己的 futures。当前部署（launchd 单 uvicorn 进程）内正确；
   改多进程/多实例前必须换共享存储（SQLite `BEGIN IMMEDIATE` / Postgres 行锁），
   并把 run 队列持久化——这是设计稿阶段 C「拆 Research Worker」那一项，不在 Alpha 做。
   额度账本（§1.5）多一把 flock 文件锁，**同一台机器**多进程安全（CLI 与服务进程同写），跨机器仍不行。
3. **run ≠ token**：日配额与额度账本都按 run 次数记，不按 token 计费。deep 档一次 run 的
   LLM 花费远大于 quick 档；定价按最贵档位估算，或引导内测用户 BYOK。run 失败不自动退额度（§1.5）。
4. **数据新鲜度单点**：`daily-full` 仍依赖本机 Chrome 的 fupanhui 登录态，
   Mac 关机 = 全体用户数据停更。盘后同步写库时段用户查询可能撞 DuckDB
   单写者锁（代码已识别为 lock 错误而非文件缺失），可接受偶发失败。
5. **BYOK 持久化绑 macOS Keychain**：隧道模式服务器就是这台 Mac，不受影响；
   迁 VPS 时要换 Secret Manager。
6. **service token 未支持**：JWT 缺 `email` claim 一律 401，机器对机器访问
   （监控拨测等）走本机回环豁免路径。

## 5. 回滚

任何异常：`start-finance-workbench` 里 `WORKBENCH_AUTH_MODE=off`（或删掉该行）
→ `launchctl kickstart -k gui/$(id -u)/com.a77.finance-workbench`，行为立即回到
本机自用形态。隧道侧可 `cloudflared tunnel delete` 或在 Zero Trust 里禁用
Access 应用（禁用后无人能过边缘层，等效下线）。
并发守卫单独回滚：删掉三条 `WORKBENCH_RUN_WORKERS` / `..._PER_USER` / `..._QUEUED_RUNS` 再 kickstart，
执行器回到「2 worker、不限、无界」的历史行为；代码不用退。

## 6. VPS 的用途：异地备份与外部拨测（应用不搬过去）

Alpha 阶段应用留在 Mac（数据管线依赖本机 Chrome 登录态、Keychain、本地 DuckDB 与 KB 索引）。
VPS 只做两件 Mac 自己做不到的事：**存一份不在这台机器上的副本**，以及**从外面看服务在不在**。

### 6.1 备份（Mac → VPS，launchd 每晚）

对象：`FORESIGHT_USERS_DIR`（内测用户全部对话 / run / 纠偏 / 配额，实测 151 个用户目录 472MB，本地全量 8 秒）。
形状：每日快照目录 + `rsync --link-dest` 硬链接（没变的文件不占新空间、变了的保留旧版本）+ `latest` 软链 + 保留 14 天。
为什么不是单目录镜像：镜像会把「今天写坏的数据」覆盖到唯一副本上，快照才有回退点。

```bash
# VPS 侧一次性：建目录、确认 Mac 能免密登录（launchd 下没人输密码）
ssh vps 'mkdir -p /srv/backup/finance-workbench'
ssh -o BatchMode=yes vps true && echo ok

# Mac 侧（在主检出树跑，plist 会钉住这棵树的脚本路径）
python3 scripts/install_workbench_backup.py install --target vps:/srv/backup/finance-workbench --at 03:40 --keep-days 14
python3 scripts/install_workbench_backup.py run     # 立刻跑一次，别等到明早才发现 ssh 不通
ssh vps 'ls -la /srv/backup/finance-workbench; cat /srv/backup/finance-workbench/last-success.txt'
```

日志 `~/Library/Logs/com.a77.finance-workbench-backup.log`；退出码 2 = 预检失败（源目录空 / ssh 不通），1 = rsync 失败。
安装器会先跑一遍预检，跑不通就拒绝挂载——不把一个注定失败的任务塞进 launchd。

**恢复流程（备份没演练过等于没有）**：
```bash
# 还原某个用户到某天的状态（先停 8792，避免边写边还原）
launchctl bootout gui/$(id -u)/com.a77.finance-workbench
mv ~/.local/share/finance-workbench/users/<uid> ~/.local/share/finance-workbench/users/<uid>.broken-$(date +%Y%m%d)
rsync -a vps:/srv/backup/finance-workbench/2026-09-02/<uid>/ ~/.local/share/finance-workbench/users/<uid>/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.a77.finance-workbench.plist
```
验收第 8 条要求真的对一个测试用户目录走一遍。

### 6.2 外部拨测（VPS cron 每分钟）

```bash
# VPS 上
scp scripts/probe_workbench_health.sh vps:/opt/finance/probe_workbench_health.sh
ssh vps 'chmod +x /opt/finance/probe_workbench_health.sh'
# crontab -e（VPS）：
# * * * * * PROBE_URL=https://beta.<域名>/api/health PROBE_WEBHOOK_URL=<飞书自定义机器人 webhook> PROBE_WEBHOOK_FORMAT=feishu /opt/finance/probe_workbench_health.sh >> /var/log/workbench-probe.log 2>&1
```

行为：连续 3 次非 200 才判 down；只在 up→down、down→up 翻转时各通知一次，不刷屏。
探 `/api/health` 是「进程在不在」；想探「真能服务」换 `/api/health/ready`，但盘后 DuckDB 同步窗口会 503（§4.4），阈值要放宽到覆盖那段时间。
前提是 §2 第 5 步的 Access Bypass；没配的话拿到 302，三分钟后必报 down——把它当成「Bypass 没配」的提醒。

## 7. 接线顺序（人工步骤，一次性）

> 进度 2026-09-03：第 1 步已完成——8792 = `c88c81da5120`（PR #547，链切五步，回滚锚 `cutover-20260903d-rollback-8792.txt`），
> 启动器已带 §1.2 的四条并发守卫 env（`RUN_WORKERS=4 / PER_USER=1 / QUEUED=4 / EXEMPT=linxiaoqi5111`），准入 429 已在生产实测。
> **auth 仍 `off`**，第 2–6 步待真人。

1. 部署运行快照：按 `docs/workflows/acceptance-workflow.md` §4 链切五步（新建 detached 快照 + 切软链）；
   `scripts/deploy_workbench_runtime.sh` 是 rsync 进现有快照的旧形态。合并 ≠ 生产跑上了。
2. `bash scripts/hosted-alpha-wizard.sh` 走完六步（隧道路由、Access 应用、AUD、名单）；§2 第 5 步的 Bypass 应用一并建。
3. 把 `alpha.env` 的内容加进 `~/.local/bin/start-finance-workbench`（含 §1.2 的三条并发守卫），
   `launchctl kickstart -k gui/$(id -u)/com.a77.finance-workbench`。
4. 跑 §3 验收九条。第 2 条（无 JWT 直打 → 401）不过，其余全部作废。
5. §6.1 装备份并立刻 `run` 一次、演练一次恢复；§6.2 装拨测并制造一次 down 看通知到不到。
6. 把 §4 已知边界原样发给内测用户，再加人（改 `beta-users.json` 即可，热重载不重启）。
