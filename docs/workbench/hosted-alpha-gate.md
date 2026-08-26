# Hosted Alpha 身份门与配额：部署 Runbook

- 日期：2026-08-27
- 代码：`intelligence/api/auth.py`（认证 + 身份改写）、`intelligence/api/quota.py`（日配额）
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
```

配置不完整（cf_access 缺团队域/AUD/名单）**启动即抛**，不带病上线。
依赖：`PyJWT[crypto]>=2.8`（已在 `intelligence/api/requirements.txt`，venv 已含）。

### 1.3 行为矩阵

| WORKBENCH_AUTH_MODE | /api/*（豁免外） | ?user= 与 body user | 适用 |
|---|---|---|---|
| `off`（默认） | 不拦 | 客户端自报生效（历史行为） | 本机自用，现 8792 不受影响 |
| `cf_access` | 无有效 JWT → 401；邮箱不在名单 → 403 | **一律被服务端身份覆盖** | 内测 |

豁免路径（本机运维探活，剥掉 user 参数后放行）：
`/api/health`、`/api/health/live`、`/api/readiness`、`/api/health/ready`。
非 `/api/` 路径（前端静态 bundle）不拦，边缘层已有 Access。

## 2. Cloudflare 侧（一次性，约 20 分钟）

前提：Cloudflare 账号 + 一个托管在 Cloudflare 的域名（免费计划够用）。

```bash
brew install cloudflared
cloudflared tunnel login                       # 浏览器授权
cloudflared tunnel create finance-workbench
cloudflared tunnel route dns finance-workbench beta.<你的域名>
```

`~/.cloudflared/config.yml`：

```yaml
tunnel: finance-workbench
credentials-file: /Users/a77/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: beta.<你的域名>
    service: http://127.0.0.1:8792
  - service: http_status:404
```

常驻：`cloudflared service install`（launchd）。

Zero Trust 控制台 → Access → Applications → Add：
1. 类型 Self-hosted，域名填 `beta.<你的域名>`；
2. Policy：Allow，Include = Emails（逐个填邀请邮箱）——与后端名单**双层白名单**；
3. 登录方式默认 One-time PIN（邮箱验证码），无需接 IdP；
4. 建好后复制 **Application Audience (AUD) tag** → `WORKBENCH_CF_ACCESS_AUD`；
   团队域在 Zero Trust → Settings → Custom Pages 可见（`<team>.cloudflareaccess.com`）。

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
```

自动化：`intelligence/tests/test_api_auth.py`（14 例）与 `test_api_quota.py`（10 例）
覆盖验签/冒充/豁免/回归/并发不超卖，`pytest intelligence/tests/test_api_auth.py intelligence/tests/test_api_quota.py` 可单独跑。

## 4. 已知边界（Alpha 明知妥协项，Beta 前必须处理）

1. **知识库未脱敏**：`kb_search`/`evidence_*` 仍连全量私有 KB（含研报正文、私有笔记）。
   Alpha 仅限可信朋友 + 口头/书面协议；设计稿的证据发布状态机
   （candidate→published）与公开索引是 Beta 硬门槛，未做前不得扩员。
2. **配额互斥范围是单进程**：预占用进程内锁 + `users/<id>/run_quota.json`。
   当前部署（launchd 单 uvicorn 进程）内正确；改多进程/多实例前必须换
   共享存储（SQLite `BEGIN IMMEDIATE` / Redis INCR）。
3. **run ≠ token**：配额按 run 次数记，不按 token 计费。deep 档一次 run 的
   LLM 花费远大于 quick 档；额度按最贵档位估算，或引导内测用户 BYOK。
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
