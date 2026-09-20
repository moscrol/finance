# FinArena 邀请试运行

## 这个分支做什么
独立金融 Agent 评测入口：用户匿名比较、邀请投票、运营调用与发布；研究偏好和策略实绩分开。

## 决策与被否方案
- 独立 FastAPI/React/SQLite，否决挂 8792，隔离公众与私人数据。
- 正式票需邀请身份+平台运行，否决 demo 填榜；胜率只描述统计，策略只事前登记。
- 真实试测按公开交付判读，否决以 completed 或中间答稿冒充业务通过。
- 设计/操作见 `docs/finance-arena.md`；试运行收据见 `docs/handoffs/2026-09-20-finance-arena-pilot.md`。

## 当前状态
实现 `c8390b98`、前轮交接 `c495a640`；本轮 8792 测试报告随本交接提交。未 push/PR/合 main。
树 `/Users/a77/fwp-wt-finance-arena`；解释器用主树 `.venv-workbench/bin/python`。
Arena 前轮已启动 `http://127.0.0.1:8816/`，本轮未复查其进程；默认库 `~/.local/share/finance-arena/arena.sqlite3`，本轮未写榜。
用户要求先测 8792：已用独立账号做三轮真实问答，无人工重试，全部结束；未改代码/配置/行情库或部署。
报告：`docs/handoffs/2026-09-20-finarena-8792-live-probe.md`；原件 `~/.local/share/finance-arena/probes/8792-20260920T144303Z/`。

## 已验证
- Arena 前轮固定实现：后端32P、前端110P、Arena桌面/手机E2E8P；lint/typecheck/双构建、全仓Ruff及七档宽度smoke通过。
- 8792前后为干净部署 `bf662e93`，模型glm-5.3-flash，health/ready正常；结束active=0、queued=0。
- 真实样本：财务算例66秒、追问58秒均被证据合同拦成无答案，模型中间核心计算正确；行情91秒给出主要正确数字，但错称`.FP`为同花顺，漏查下跌1151家。三份研究状态均partial，无完整通过样本，不外推整体正确率。

## 未验证 / 已知边界
本轮不是Arena协议参赛、独立评审或修复验收。未调用第二家Agent，未测网页交互/负载/选股组合实绩。未实现事实专家评分、身份恢复、容器隔离或公网治理；策略收益仍空。
未跑全仓Python、原Workbench E2E及完整registry合入检查，不具备合入签字。前轮共享记忆未提交混合改动，vault_lint仍有既有失败。

## 下一步
先据原件对照已有在途修复，区分用户条件与真实事实的证据要求，修正板块来源及缺数查询；修复另行验收，不动生产求绿。随后授权真实参赛接入与审核发布，补独立评分/成交账本/公网治理。

## 踩过的坑
- HTTP成功/run completed不等于任务完成；保留公开答案、研究状态和独立核对。
- Workbench不直接兼容arena-v1；探针传user，不传user_id。
- 版本进request_id、同题指纹去重；arena-public/dist-arena与原前端隔离。
- E2E临时库不是正式榜；不把试测票或中间答案发布为成绩。
