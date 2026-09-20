# FinArena 邀请试运行

## 这个分支做什么
独立金融 Agent 评测入口：用户匿名比较、邀请投票、运营调用与发布；研究偏好和策略实绩分开。

## 决策与被否方案
- 独立 FastAPI/React/SQLite，否决直接挂 8792，隔离公众与私人投研数据。
- 正式票必须邀请身份+平台运行，否决用 demo 填榜。
- 胜率仅描述统计；策略仅事前登记，否决未验证的收益模拟。
- 细节：`docs/handoffs/2026-09-20-finance-arena-pilot.md`；操作：`docs/finance-arena.md`。

## 当前状态
代码已提交 `c8390b98`，本交接随文档提交。未推送、未建 PR、未合 main。
树 `/Users/a77/fwp-wt-finance-arena`；解释器用主树 `.venv-workbench/bin/python`。
本机 `http://127.0.0.1:8816/` 已启动，检查时 PID 46557，日志 `/tmp/finance-arena-8816.log`。生产 8792/数据未动。
数据默认 `~/.local/share/finance-arena/arena.sqlite3`；4 套虚构题，正式对战/正式票均为 0，未做付费调用。
共享记忆仅追加能力节点与项目索引，未提交该仓混合改动。

## 已验证
- c8390b98 干净树：后端专项 32P；收据 `~/.finance-runtime/test-receipts/20260920T142005Z-c8390b98.json`。
- 全仓 Ruff、提交钩子；前端 lint/typecheck、110 项已有测试、Arena 与原 Workbench 构建通过。
- Arena 桌面/手机 E2E 8P；七档宽度 smoke 无溢出/缺图/脚本异常，截图在 `intelligence/webapp/test-results/`。
- graph_audit exit 0，新节点为 PENDING（仅在分支）；不等于业务效果验证。

## 未验证 / 已知边界
真实参赛 Agent 尚未授权接入；现有 Workbench API 不直接兼容 arena-v1。网络与正式票测试是隔离夹具，不是参赛结果。
无专家事实评分、隔离工具审计、真实身份防串票、账户恢复或公网部署。无交易成交与收益结算；策略字段仍由运营核对原答案。
未跑全仓 Python、原 Workbench E2E 或完整 registry 合入检查，不具备合入签字。共享 vault_lint 仍因既有死链/元数据失败（日志 `/tmp/finance-arena-vault-lint.log`），未修无关记忆。

## 下一步
先验收本机交互，再授权两家 Agent、固定任务/数据范围并做真实运行；之后补独立评分、前向成交账本和公网身份/限流/备份。不要为了空榜好看而造正式票。

## 踩过的坑
- 参赛版本必须进上游 request_id；重复题按任务指纹去重覆盖。
- `arena-public` 不与原前端共享素材；`dist-arena` 不覆盖 Workbench。
- row_factory 由 sqlite3 内部读，字段扫描已按标准库例外放行。
- E2E 临时服务/库只用于测试；禁止把 `arena_e2e.serve` 当试用服务启动。
