# 给 OPC 评审开体验入口：操作清单与一个先要拍板的决定

- 对应 BP §3.5「给评审的体验入口」；操作依据 `docs/workbench/hosted-alpha-gate.md`（下称「运行手册」）。
- 本清单只抽步骤、不重复原理；每步标「谁做」——带 Cloudflare 账号、域名、启动器的步骤只有你能做。

## 0. 先拍板：评审拿到的是「账号」还是「演示」

运行手册 §4.1 写明的已知边界：**知识库未脱敏**——内测账号的 `kb_search` / `evidence_*` 连的是全量私有知识库（研报正文、私有笔记）。Alpha 之所以只给 3–10 名可信朋友并签协议，就是这条。给一批不认识的评审开账号，等于把这条边界放开。

| 选项 | 评审看到什么 | 代价 | 建议 |
|---|---|---|---|
| **A. 录屏 + 现场演示（默认）** | 1 分钟录屏（拒答不存在的日期 / 登记判断次日回检）+ 路演现场用你的账号演示 | 零暴露、零配置 | **交申请用这个**；「有 Demo」阶段的要求是能看到真东西，不要求人人有账号 |
| B. 时限账号 | 评审用邮箱验证码登录，看完整产品 | 私有知识库正文对评审可见；需先做 §1–§3 的一次性配置（约半天） | 只在评审明确要求「自己上手」且你接受暴露时用；账号只开路演当周，配额 5 次/天 |
| C. 脱敏账号 | 同 B，但知识库只暴露公开来源 | 需要证据发布状态机（candidate → published），是 Beta 硬门槛，未做 | 现在做不到，不承诺 |

下面 §1–§3 是选项 B 的步骤；选 A 则只需要 §4。

## 1. 一次性：把身份门接上（你做，约半天，运行手册 §2）

1. 前提：Cloudflare 账号 + 托管在 Cloudflare 的域名。现有隧道 `a77-exec` 已服务 `*.industry7view.com`，向导默认在同一条隧道加 `beta.industry7view.com → 127.0.0.1:8792`，**不要再开第二条隧道**（两条 cloudflared 抢同一份证书会互相踩）。
2. 运行向导（不改启动器、不重启 8792；配好的 env 落 `~/.local/share/finance-workbench/alpha.env`）：
   ```bash
   bash scripts/hosted-alpha-wizard.sh
   ```
3. **顺序不能反**：先在 Zero Trust 控制台建 Access 应用（Self-hosted，域名 `beta.<域名>`，Policy Allow + Include = Emails 逐个填评审邮箱，登录方式 One-time PIN），复制 AUD tag；再建第二个 Self-hosted 应用（同域名、路径 `api/health`、Policy Bypass、Everyone）给外部拨测放行；**最后**才加 DNS 与 ingress。主机名先回源、Access 后建的那段时间，8792 是无认证公网可达。
4. 加 ingress 并验证（运行手册 §2 末尾的五条命令：备份 `config.yml` → 插入两行 ingress → `cloudflared tunnel ingress validate` → `ingress rule` 命中 8792 → `route dns` → `launchctl kickstart -k gui/$(id -u)/com.cloudflare.cloudflared`，用户域，不要 sudo）。
5. 启动器环境变量（运行手册 §1.2）接进 `~/.local/bin/start-finance-workbench` 后重启 8792——这一步改生产，按现有 cutover 流程做，留回滚锚。评审用建议值：
   ```bash
   export WORKBENCH_AUTH_MODE=cf_access
   export WORKBENCH_CF_ACCESS_TEAM_DOMAIN=<team>.cloudflareaccess.com
   export WORKBENCH_CF_ACCESS_AUD=<AUD tag>
   export WORKBENCH_AUTH_USER_MAP=$HOME/.local/share/finance-workbench/beta-users.json
   export WORKBENCH_DAILY_RUN_QUOTA=5            # 评审账号 5 次/天够看，蒸馏不够用
   export WORKBENCH_QUOTA_EXEMPT_USERS=linxiaoqi5111
   export FINANCE_WEB_SEARCH=0                   # 评审没有本机 Chrome CDP
   export WORKBENCH_FULL_ACCESS_USERS=linxiaoqi5111   # 评审拿不到 run trace / 学习面板（防蒸馏第二道闸）
   export WORKBENCH_RUN_WORKERS=4
   export WORKBENCH_MAX_ACTIVE_RUNS_PER_USER=1
   export WORKBENCH_MAX_QUEUED_RUNS=4
   ```
   配置不完整（缺团队域 / AUD / 名单）启动即抛，不会带病上线。

## 2. 每次加人：邀请名单（你做，一分钟，运行手册 §1.1）

`~/.local/share/finance-workbench/beta-users.json`（不进 git）加一行，邮箱 → user_id（`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`）：

```json
{
  "you@example.com": "linxiaoqi5111",
  "reviewer-1@example.com": "opc-reviewer-1",
  "reviewer-2@example.com": "opc-reviewer-2"
}
```

文件 mtime 变化自动热重载，不用重启；JSON 写坏了保留旧名单、不放行任何新身份。**同一封邮箱也要加进 Cloudflare Access 的 Policy**（双层白名单）。user_id 用 `opc-reviewer-N` 这种可辨识前缀，路演后删名单即失效；用户目录留着，里面的 `interactions.jsonl` 是评审怎么用产品的第一手记录。

## 3. 开门前的验收（你做，十分钟，运行手册 §3 的 1–7 条）

```bash
curl -s http://127.0.0.1:8792/api/health | head -c 200                                   # 1) 本机探活豁免仍通
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8792/api/conversations        # 2) 无 JWT 直打 → 401
# 3) 浏览器走 beta.<域名> → 邮箱验证码 → 页面可用；bootstrap 返回的 user 是名单里的 user_id
# 4) 冒充：登录 A 后 F12 改 fetch 加 ?user=<B> → 返回的仍是 A 的数据
# 5) 名单外邮箱（若边缘放行了）→ 后端 403
# 6) 配额：第 6 个问题 → 429 中文提示
# 7) 并发：同一账号两个标签页同时提问 → 第二个 429「在进行中」
```

自动化已覆盖：`test_api_auth.py`（21 例）、`test_api_quota.py`（10 例）、`test_api_run_admission.py`（8 例）。

## 4. 无论选哪个都要做：录屏与演示脚本（你做）

录屏两段，各 30 秒，合成 1 分钟：

1. **拒答**：问一个数据仓里没有的日期（例如「2026-09-20 的板块表现」）。期望看到系统声明数据截止日与缺口、不猜。讲一句：「说不出证据就不说，这是地板。」
2. **校准**：登记一个判断（例如「明天 XX 板块若放量则主线切换」）为可证伪点 → 切到次日的回检结果或校准报告。讲一句：「你的判断进台账、被回检，这是招牌。」

现场演示如果时间允许，第三段：问一个题材的发酵链路（消息 → 首板 → 板块双红 → 补涨），让评审看到每个节点带数据出处。

**不要演示**：个股买卖建议、目标价、对明天的价格预测——产品本来就不输出，但现场被评审追问时也不要口头给（第 9 章边界）。

## 5. 路演后收尾

- 选项 B：从 `beta-users.json` 与 Access Policy 删掉评审邮箱；配额回到 Alpha 值（20）。
- 读一遍评审账号目录下的 `interactions.jsonl`：他们问了什么、在哪一步停下，是 V1 用户访谈的免费样本。
- 把评审当场的追问补进 BP 附录 E。
