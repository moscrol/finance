# FinArena 组合验收候选

## 这个分支做什么
在最新 `gitea/main@728f3271` 上前向整合原 Arena `feat/finance-arena@7162a6cb`，修复参赛端点、远端运行身份和榜单读快照边界，供独立验收。

## 决策与被否方案
- 选独立 FastAPI/React/SQLite 试运行；否决接入 8792 或共享 Workbench 库，避免访客数据和生产服务耦合。
- HTTP 本机例外只允许解析为 loopback（回环地址）；否决 `allow_local` 放行任意公网 HTTP。
- 轮询每次校验远端 `run_id`；不符即失败且不生成可发布比赛，否决只按 URL 和终态接收答案。
- 榜单多查询放入 SQLite 读事务；否决全局锁，保留 WAL 读写并行。
- 组合只证明候选工程兼容；独立 Spec/Quality、main 合入、部署、真实参赛调用仍需授权。

## 当前状态
代码和交接已提交到 `fix/arena-main-ready-0921`；固定组合须以本候选最新提交重新建立，位于新的独占验收树，不能继续使用旧收据。原 PR #811 未改写；此候选待开 WIP 替代 PR。

## 已验证
- Arena Python：43 passed；定向反例先在旧实现失败，修后通过。
- 前一组合 `471f85a22613` 曾完成全仓 Python、前端、Arena 浏览器/smoke、registry 门禁，但其候选尖随后追加了交接文档，旧收据仅作历史证据，不能移签。
- 最新候选须重建组合后重新取得：全仓 Python、前端、Arena 专属浏览器/smoke、registry 五项及合并树检查。

## 未验证 / 已知边界
没有独立 Spec/Quality 签字；没有真实第二家 Agent、负载、身份恢复、容器隔离、公网治理或策略收益结算验收。8816 旧服务和正式库未切换、未写榜；组合验收不等于生产授权。

## 下一步
开一张明确指向本候选的 WIP PR，并在评论中指向 #811；等待独立审查和用户合入授权。审查前不得合 main、切 8792、调用真实参赛端点或删除旧树。

## 踩过的坑
- `run_main_gate.sh` 是 Bash，不能用 Python 启动；错误启动只产生语法错误，未启动 pytest，不得进测试收据。
- 前端收据不能交给 Python 收据校验器；两者 schema 不同，分别保留。
- `latest.json` 不是权威证据；本轮全量收据和每个 Arena 叶子都用独立路径并绑定固定 SHA。

展开决策和历史原件索引：`docs/handoffs/2026-09-21-arena-main-ready.md`；最终组合收据以新验收树为准。
