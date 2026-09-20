# FinArena 前向整合与组合验收记录

## 背景
原 `feat/finance-arena@7162a6cbe304` / PR #811 是一条独立的匿名盲评试运行线，原 worktree `/Users/a77/fwp-wt-finance-arena` 保持干净且有本机 8816 服务。为避免改写该现场，从最新 `gitea/main@728f327160bbd` 新建 `/Users/a77/fwp-wt-arena-main-ready-0921`，把原分支 squash 为一条候选提交，再放入既有所有权修复组合树。

## 发现与修复顺序
1. 旧实现允许 `allow_local=True` 时把公网 HTTP 地址视作测试端点。新增公网 IPv4/IPv6 反例，旧实现 2F；修复后 HTTP 仅接受解析结果全部为 loopback，HTTPS 仍允许受控 loopback。
2. 旧实现 POST 得到运行编号后，GET 轮询只看终态，不校验响应正文的编号。新增返回无关编号/缺失编号反例，旧实现 2F；修复后身份不符进入失败运行，保留已完成的另一方输出，但不创建 Match。
3. 旧榜单先查已发布比赛再查投票，两个查询可能看到不同提交点，发布并发时会出现投票找不到比赛。新增 SQLite trace 交错反例，旧实现暴露 `KeyError`；修复 `connect(write=False)` 显式 `BEGIN`，让榜单两条查询共享同一读快照，并保持 WAL 读写并行。

## 固定对象
- Arena 候选分支：`fix/arena-main-ready-0921`；本记录提交后仍需以最新尖建立新的固定组合，不能复用下述历史组合收据。
- 历史组合：`e1b63b1a5b7c066b7377bbd2d005051863331001` + 旧候选，`471f85a226134d441b801dd4e5a0dbe964e07aa2`；仅作不可移签的历史证据。
- 组合基准：`gitea/main@728f327160bbd2485cb635e7ef09d040d718d7b5`。最终独占树和 SHA 由后续验收交接记录确定。

## 验证与收据
- 历史组合的 Arena 定向、全仓 Python、前端、专属浏览器/smoke、registry 收据均已封存，但候选尖追加了本交接后失效，不移签到新尖。
- 最新组合必须重新取得并核对：Arena 定向后端、全仓 Python、前端通用门禁、Arena 专属浏览器/smoke、Registry 五项和 `git merge-tree`；所有收据都要绑定新固定 SHA。

## 边界和裁决
这些是作者工程门禁与反例回归，不是独立 Spec/Quality 结论；没有发起付费外审。没有真实第二家 Agent 调用、公开部署、策略收益、身份恢复、容器隔离、负载或网络出口验收。不得把 8816 旧服务的状态、任何 live probe、旧 PR 文本或旧收据移签到 `471f85a2`。

原始失败证据：旧实现定向红日志在 `~/.finance-runtime/reviews/arena-main-ready-20260921/author/red.log`，保留不覆盖；错误的 Python 启动日志为 `arena-main-ready-0921-python.log`，仅作为操作错误记录。

## 后续
候选应开 WIP PR 明确替代/前向整合 #811，并等待独立审查及用户合入授权。main、8792、生产库、正式榜、旧 worktree 和旧服务均未改变。
