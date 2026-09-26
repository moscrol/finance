# 同花顺研究数据第一批：候选与部署缺口

## 背景及发现顺序

用户在unused-data调查后授权“按照最佳推进”。本轮承诺隔离开发验证，合并、部署、生产换库另行确认。主树是旧detached HEAD且有他人修改，所以从 `gitea/main@728f3271` 建立 `feat/hithink-research-data`，工作树 `~/fwp-wt-hithink-research-data`。只用主树 `.venv-workbench/bin/python`。

1. 官方文档与13请求调研已经确认权限和返回，详见vault `00_inbox/2026-09-21-hithink-unused-data-assessment.md`。本轮不混用问财key或旧MCP认证。
2. 数据大多停09-08。先查18:30同步配置，发现部署树 `finance-workspace-sync@6382c13b` 的local计划没有同花顺步骤，而基线main已有四步。后来用 `launchctl print` 的白名单字段核实actual loaded环境一致，last exit0不能证明没排进计划的步骤更新成功。
3. 只读发现部署树有未提交指数修补与运行产物；不覆盖、不reset、不自动部署候选。
4. 新增采集器、请求审计、三张观察表、查询读口、local第五步及monolith兼容接线；产物全部是并跑源，不改原财务主源。
5. 新增只读 `scripts/audit_hithink_runtime.py` 将上述排查变为退出码诊断。本轮生产结果exit2：步骤缺失，09-18主行情/板块行情无行；不是供应商权限错误的结论。
6. 两股真实试采写临时库，再用真实FinanceQuery消费者读回；完成相关回归与截止保护变异验证。
7. 代码提交 `0604732423f97ea7ba1279973a75c666a13e9bda`；随后在干净提交上复跑定向回归。当前未push、未合并、未部署。

## 方案取舍

| 问题 | 选用 | 否决及理由 |
|---|---|---|
| 第一批范围 | 异动原文归档、完整热度轨迹、估值观察值 | 暂缓三表/基金/期货全量：累计/单季、披露时点、代码后缀与单位尚未对账 |
| 存储/网络 | 复用官方客户端、DuckDB staging和既有finance_query | 不另装SDK/marketdb，不让agent外呼或另建生产写入链 |
| 抽样范围 | 默认当日热榜前30，允许显式最多100码 | 不默认全市场请求，不用旧榜冒充今日范围 |
| 历史 | 热度单独history-only；采集日期参与查询截止 | 拒绝给当天异动/最新估值换历史日期；供应商元数据时间不能代表统一定价时刻 |
| 审计 | pending先写，事实+成功收据同事务；保原响应、只存错误类型 | 不用HTTP200或行数推完整，不落含key风险的错误正文 |
| 版本 | 事实存最后观察值；请求留原件 | 未做PIT版本读写，不声称可以重演历史当时的所有状态 |
| 部署 | 保存明确的部署/数据差距，等验收授权 | 不直接覆盖有指数热补丁的旧树；作者测试不是合入或装机许可 |

详细合同、命令和实际请求ID见 `docs/data-sources/hithink-research-data.md`。

## 验证与收据

- 干净 `06047324`，相关Python回归 **445 passed / 8 skipped / 0 failed**。跳过的8项均为既有 `test_finance_query_contains.py`，隔离工作树没有本地主库。收据 `~/.finance-runtime/test-receipts/20260920T181549Z-06047324.json`，`dirty=false`。UTC收据日期20日对应上海21日。
- 范围：全部同花顺采集/审计/预览测试、分步发布/恢复、写入守卫、数据registry、finance_query及授课框架相关读口。完整命令由上述JSON的target记录。
- 全仓Ruff、单仓consumption registry和dataset注册检查通过；提交时层级/字段/路径/工具可达性/运行时目录/禁提交文件门禁通过。
- 变异：暂时删除热度dataset的 `cutoff_column=captured_date`，历史截止测试按预期1F；恢复后上述445P。不把这份预期失败隐藏或解释为环境抖动。
- 真实官方请求4个，临时库 `/tmp/hithink-research-acceptance-20260921.duckdb`：两股估值2行，热度10自然日点（每股5点），异动empty。实际FinanceQuery读回估值2行/2证据、热度10行/10证据、异动0行/0证据。
- 首版新增消费者测试3F是测试错把“子集”声明预期放在纯行文本；范围声明实际位于模型工具schema目录，改测真实目录后通过。没有为过测试删除范围声明。
- 未运行本候选全量pytest/前端/E2E/独立审查，不借用基线或其他分支完整绿收据；未验LLM自然提问效果、盘后非空异动、真实夜跑发布、生产字段完整性和正式日更恢复。

## 接手边界

1. 先审本候选，再跑完整等价CI；需要合并/部署时取得用户确认。生产根仍是旧版本，不能称修复已生效。
2. 装机前保存并核对 `finance-workspace-sync` 的指数热补丁，不丢用户改动；按批准版本建独立部署根。
3. 当天盘后沿原daily-full staging跑，检查请求状态、当日关键值非空及消费者；异动非空验证单独确认。历史缺口按duckdb-backfill规程，不伪造latest-only数据。
4. 财务三表与现有东财/新浪并跑核对后再补，不马上切主源；基金代码和商品单位各自验证。
5. 专用巡检已进scripts及测试，不留一次性/tmp工具。它针对本仓同花顺表/配置，不抽成通用framework；harness-reference工作树已有他人BUILD.md修改，本轮未动该仓。
