# FinArena 前向整合与组合验收记录

## 背景
原 `feat/finance-arena@7162a6cbe304` / PR #811 是一条独立的匿名盲评试运行线，原 worktree `/Users/a77/fwp-wt-finance-arena` 保持干净且有本机 8816 服务。为避免改写该现场，从最新 `gitea/main@728f327160bbd` 新建 `/Users/a77/fwp-wt-arena-main-ready-0921`，把原分支 squash 为一条候选提交，再放入既有所有权修复组合树。

## 发现与修复顺序
1. 旧实现允许 `allow_local=True` 时把公网 HTTP 地址视作测试端点。新增公网 IPv4/IPv6 反例，旧实现 2F；修复后 HTTP 仅接受解析结果全部为 loopback，HTTPS 仍允许受控 loopback。
2. 旧实现 POST 得到运行编号后，GET 轮询只看终态，不校验响应正文的编号。新增返回无关编号/缺失编号反例，旧实现 2F；修复后身份不符进入失败运行，保留已完成的另一方输出，但不创建 Match。
3. 旧榜单先查已发布比赛再查投票，两个查询可能看到不同提交点，发布并发时会出现投票找不到比赛。新增 SQLite trace 交错反例，旧实现暴露 `KeyError`；修复 `connect(write=False)` 显式 `BEGIN`，让榜单两条查询共享同一读快照，并保持 WAL 读写并行。

## 固定对象
- Arena 候选提交：`371a08e8598efcf53ee4b870ad69a1877a5f5802`，分支 `fix/arena-main-ready-0921`，已推 `gitea`。
- 组合：`e1b63b1a5b7c066b7377bbd2d005051863331001` + 候选，固定提交 `471f85a226134d441b801dd4e5a0dbe964e07aa2`。
- 组合基准：`gitea/main@728f327160bbd2485cb635e7ef09d040d718d7b5`。独占树：`/Users/a77/fwp-wt-ownership-arena-gates-0921`。

## 验证与收据
- Arena 定向后端：43 passed，日志由 `arena-python/run.json` 绑定固定 SHA。
- 全仓 Python：`12104 passed / 85 skipped / 2 xfailed`，17 warnings，637.86 秒；权威收据 `~/.finance-runtime/reviews/arena-main-ready-20260921/python/receipts/gate-pbwPTmDi/pytest.json`，revision 和 dirty 均核对。
- 前端通用门禁：frozen install、lint、typecheck、test、build、test:e2e 全部 0，`frontend/frontend.json` 记录首尾身份稳定。
- Arena 专属浏览器：build 0，桌面/手机 8 passed；七档 smoke 结果为无水平溢出、无超宽元素、无缺图、无 page error，截图保存在组合树 `intelligence/webapp/test-results/local-smoke/`，临时 18826 服务已停止。
- Registry：parseability、check、backfill-tables、generate-views、ledger crosswalk 全部 exit 0。
- `git merge-tree --write-tree gitea/main HEAD` exit 0；组合树最终干净。

## 边界和裁决
这些是作者工程门禁与反例回归，不是独立 Spec/Quality 结论；没有发起付费外审。没有真实第二家 Agent 调用、公开部署、策略收益、身份恢复、容器隔离、负载或网络出口验收。不得把 8816 旧服务的状态、任何 live probe、旧 PR 文本或旧收据移签到 `471f85a2`。

原始失败证据：旧实现定向红日志在 `~/.finance-runtime/reviews/arena-main-ready-20260921/author/red.log`，保留不覆盖；错误的 Python 启动日志为 `arena-main-ready-0921-python.log`，仅作为操作错误记录。

## 后续
候选应开 WIP PR 明确替代/前向整合 #811，并等待独立审查及用户合入授权。main、8792、生产库、正式榜、旧 worktree 和旧服务均未改变。
