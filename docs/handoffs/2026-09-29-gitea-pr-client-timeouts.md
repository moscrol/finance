# gitea_pr.py 客户端超时与回读（fix/gitea-pr-timeouts，PR #961）

日期 2026-09-29。分支从 `gitea/main@33023225d` 开；实现 `2e7199f8b`，变异读数与 defensive-patterns 第 15 条 `5a87a7aef`。

## 背景

`scripts/gitea_pr.py` 文首第 8 条声称「合并 POST 报错但其实已生效：POST 失败不退出，先回读再定结论」。实现只接住了 HTTP 错误码：`_api()` 用 `urlopen(timeout=30)`、只把 `HTTPError` 转成 `SystemExit`；`cmd_merge` 只 `except SystemExit`。客户端超时 / 断连两头都漏，脚本在回读、核验、`--record` 之前就崩了。`cmd_open` 同样暴露。

两种结果都出现过：#854（09-23）合并 POST 超时、服务端已合、PR 仍 open、无记录，人工补记录 + 指针关闭；#959（09-29 01:17）合并 POST 超时、没合成，靠进程内把 urlopen 超时改 170 s 重跑才合上（33023225d，记录 `~/.finance-runtime/reviews/pi-anchor-0928/merge-record-959.json`）。开 PR 侧：#863 超时未创建、#870 超时已创建。

## 按发现顺序

1. **读代码**确认缺口在 `_api` 与 `cmd_merge` 之间那条缝：各自的 except 都对，拼起来漏掉传输错误。
2. **读服务端日志**（`/opt/homebrew/var/gitea/log`，app.ini `LEVEL = debug`，router 行带每个请求的服务端耗时）。#959 的合并 POST 在服务端 **30282 ms** 处以 500 结束：`git push origin base:refs/heads/main` 01:17:27 开始、01:17:34 被杀，`InternalServerError: git push:`。30.28 s 正是客户端 30 s 超时的时刻 → **客户端挂断让 Gitea 取消请求上下文，把 push 杀在半路**。超时不只是丢了回答，它本身制造结果。
3. **#854 同形、结果相反**：服务端共 51.7 s；push 01:08:10 开始，客户端约 01:08:20 挂断，push 继续跑，01:08:40 pre-receive 返回 200（ref 已更新），01:08:42 返回 500。main 前进了，PR 再没被标成 merged。这解释了记忆里「PR 对象 open 但 base.sha 已指向合并提交」——**判合没合必须看 base ref，不能只看 PR 的 `merged`**。#781（09-17）同形：返 500 时 main 已前进。
4. **开 PR 日志里成簇的「201 in 30.0s」**：00:59:30 那条（#959 第二次 open，确实开成了）同一秒伴随一串 `context canceled`（Actions 通知、commit status 等被取消）。这些读数是被 30 s 客户端截断的，不是真实耗时，真实尾部只会更长。
5. **量分布**（09-21~29 全部保留日志，服务端耗时）：

   | 调用 | n | p50 | p90 | p99 | 最慢 | >30 s |
   |---|---|---|---|---|---|---|
   | `POST …/merge` | 137 | 3.0 s | 17.7 s | 51.7 s | 72.3 s | 6 |
   | `POST /pulls`（开 PR） | 168 | 5.8 s | 30.2 s | 173 s | 211 s | 30 |
   | `GET /pulls`（列表） | 425 | 0.1 s | 7.2 s | 34 s | 67.7 s | 12 |
   | `GET /pulls/N` | 2092 | 0.3 s | 2.7 s | 24.7 s | 37.4 s | 8 |
   | `POST …/comments` | 553 | 0.5 s | 4.9 s | 42 s | 60.8 s | 13 |

6. **翻页**：当时只有 3 张 open PR，但 `_open_pr_for_head` 只看第一页（limit=50，本机 app.ini 未改 `MAX_RESPONSE_ITEMS`，默认 50）。新的「没开成」判定依赖它看全，所以改逐页。`list` 子命令没改（closed 有近千张，全翻会慢且刷屏；它是展示用，不做判定）。
7. **3.9 兼容**：`/usr/bin/python3` 是 3.9.6，3.10 之前 socket 超时抛的是 `socket.timeout`，不是 `TimeoutError`。两者都是 `OSError` 子类，所以按基类接（`_TRANSPORT_ERRORS = (OSError, http.client.HTTPException)`）。

## 决策与被否方案

| 决策 | 方案 | 评价 | 结果 |
|---|---|---|---|
| 默认超时 | 60 / 120 / 180 / 300 / 不设 | 合并最慢 72 s，120 够合并；开 PR 最慢 211 s，180 仍漏 1 次；不设则服务端真卡死时永不返回 | **300 s**（≈ 211 × 1.4）。等得久的代价只在服务端真慢时才付，挂断的代价是半截状态，两边不对称 |
| 旋钮个数 | 一个 `GITEA_API_TIMEOUT` / 读写分开两个 | 读也慢到 67.7 s；两个旋钮记不住，也没有读写需要不同值的证据 | 一个 |
| 回读判据 | 只看 PR `merged`（旧）/ `merged` + base ref / 只看 base ref | 只看 `merged`：#854 / #781 会被判成「没合」；只看 base ref：会把别人刚合的 PR 当成我们的 | **`merged` + `git ls-remote` base ref**；base 前进时要求 tip 的双亲含 head 才认作这次落地 |
| 回读用什么读 base | `git ls-remote` / API `GET /branches/main` / `git fetch` | API 与出问题的是同一路；fetch 太重；ls-remote 走 git smart-HTTP，日志里一直 60–200 ms，且是记忆里验证过的判据 | ls-remote |
| 4xx | 同样轮询 / 只读一次 | 4xx 是明确拒绝（WIP 标题 405 等），轮询 120 s 是白等 | 只读一次 |
| 自动重 POST | 回读确认没合就重 POST / 从不 | 服务端可能在窗口外才落地（#854 断开约 20 s 后才更新 ref）；重 POST 会在已含 head 的 main 上失败，或更糟 | **从不**；hint 写清安全重跑的步骤 |
| 异常分型 | 在 `_api` 把超时也转成 `SystemExit` / 分两型 | 混成一型，「明确拒绝」与「结果未知」只能靠字符串猜（defensive-patterns #12） | `GiteaHTTPError(SystemExit)` 带 `status` + `GiteaTransportError` |
| 接异常的范围 | 基类 `(OSError, HTTPException)` / 裸 `Exception` | 裸 `Exception` 会把编程错误误报成「服务端结果未知」 | 基类 |
| 退出码 | 沿用 0/1/2 / 新增 3 | 「没合成」可以安全重跑，「结果未知」不可以，脚本调用方要能区分 | 新增 **3** |
| 同族 guard | 改 / 不改 | 已有回读，PATCH 报错只需别跳过它（几行），`--off` 顺手也核标题 | 改 |
| 同族 close | 改 / 不改 | 先贴评论再关：评论 POST 超时会在关闭前退出，不会静默关闭，代价是重跑可能重复贴指针。修它要评论回读 + 分支删除补偿，收益低 | **不改**，靠 `main()` 兜底退 3 并提示回读；列后续 |
| 测试打哪层 | 换 `_api` / 换 `urlopen` | 缺陷就在 `_api` 与 `cmd_merge` 之间，换 `_api` 看不见 | 换 `urlopen`，真 `_api` 照跑；假仓地址用 `.invalid`，漏换也打不到真 Gitea |
| 回读预算 | 30 / 60 / 120 / 300 s | #854 的 ref 在断开后约 20 s 才更新、#781 约 12 s | **120 s**（约 6 倍余量），间隔 10 s，可调 |

## 验证与收据

- 定向：`tests/test_gitea_pr.py` 28 passed（原 15 + 新 13，含参数化）；`intelligence/tests/test_defensive_patterns_doc.py` 3 passed；ruff 通过；`/usr/bin/python3`（3.9.6）语法、`--help`、坏环境变量拒绝冒烟通过。
- 变异（2e7199f8b 上逐门拆，各确认替换恰好 1 处，清 `.pyc`，git 还原后树干净）：十道门全部让对应测试变红，明细在测试文件超时一节开头。
- 活跑：本 PR（#961）就是用分支上的新 `open` 开的，走的是正常路径（`outcome=created`），报错路径没有在真 Gitea 上跑过。
- 四叶（python / frontend / e2e / registry-check）：读数见 PR #961 评论。
- **不成立 / 没验证的**：
  - 没在真 Gitea 上制造超时：那会真的中止一次服务端写。
  - `Do=squash/rebase` 的「落地未标记」识别只按 `Do=merge` 的双亲判据，其余风格会报 `unknown`（本仓合并一律用 merge）。
  - 极端负载下（09-23 晚 GET 60–170 s）回读 GET 会吃掉整个预算，结果是 `unknown` / 退 3。这是有意的保守。

## 后续要做

- `close`：评论 POST 报错后按正文回读评论，再决定关不关（可选，收益低）。
- 本轮的变异脚本（替换计数=1、清 `.pyc`、git 还原、树干净断言、期望红 ⊆ 实际红）可做成 `scripts/` 工具，把 `TOOLKIT.md` 里「变异验证（手法，非脚本）」变成工具。
- 合入后改记忆 `gitea-pr-merge-via-api-with-keychain-token`：「cmd_merge 只接 SystemExit」那句失效。

## 不要做

- **别把超时改回 30 s**，也别按「平时 3 s 就回来」缩短：挂断会把服务端的写杀在半路（第 2、3 步）。
- **别在「没合成」之后自动重 POST**：窗口外落地是真的（#854）。重跑先 `show`，再带 `--expect-head/--expect-base`。
- **别只看 PR 的 `merged` 判合没合**：#854 / #781 都是 main 已前进、`merged=false`。
- **别把 except 放宽到裸 `Exception`**：编程错误会被记成「服务端结果未知」，永远查不出来。

## 复算默认值

服务端日志保留约 8 天（按天轮转 gz）。重新定超时时照这个量：

```bash
cd /opt/homebrew/var/gitea/log && { for f in gitea.log.*.gz; do gzcat "$f"; done; cat gitea.log; } > "$TMPDIR/gitea-all.log"
/Users/a77/finance-workspace-private/.venv-workbench/bin/python - <<'PY'
import os, re
from collections import defaultdict
pat = re.compile(r"completed (\w+) /api/v1/repos/a77/[^/]+/(\S+) for \S+, (\d+) [^@]*? in ([\d.]+)ms")
groups = defaultdict(list)
for line in open(os.path.expandvars("$TMPDIR/gitea-all.log"), errors="replace"):
    m = pat.search(line)
    if not m:
        continue
    method, rest, _status, ms = m.groups()
    rest = re.sub(r"\d+", "N", rest.split("?")[0])
    groups[f"{method} {rest}"].append(float(ms) / 1000)
for key, secs in sorted(groups.items()):
    secs.sort()
    q = lambda p: secs[min(len(secs) - 1, int(p * len(secs)))]
    print(f"{key:28} n={len(secs):4} p90={q(.9):6.1f}s p99={q(.99):6.1f}s max={secs[-1]:6.1f}s")
PY
```

注意：客户端先挂断时服务端记的是挂断那一刻（成簇的「in 30.0s」），真实尾部要看用长超时客户端的那几次。
