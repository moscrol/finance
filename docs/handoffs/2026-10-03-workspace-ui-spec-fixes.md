# Workbench 规格复审修复 · 2026-10-03

实现提交 `d69c02557789cd19db69f9e909c18ee3bf454174`，修复基线 `e01a60b86f6227e994d3656845b6444e27f4f6de`。接续 [首次恢复记录](2026-10-03-workspace-ui-recovery.md)，保留其失败和验证边界。尚未通过规格复验、质量审查或精确提交全仓门禁；未推送、合入主线或部署。

## 发现与修复

独立规格审查给出五个反例。先在真实 FastAPI 路由与组件边界加测试，得到后端 12 failed / 1 passed、日报 4 failed、图线和六轨 5 failed，然后修复：

1. `require_complete` 拒绝的区间不再从曲线输出数字。板块曲线补齐交易日索引，缺行或空涨跌幅后累计值保持未知；前端保留空点位置，分段画线和面积。严格请求加载期间清除上一请求的数值。
2. 个股图线采用原聚合的 `pre_close` 基准，完整数据下首日涨跌进入曲线、图尾等于标量。全区间基准缺失不改用首日 close。查询使用用户原始实体，避免解析后的名字扩大范围，并复用确定性去重。
3. 个股轨带 `n_with_pct`。涨跌幅全空时计数为 null、单元格为缺口且不画平衡条；部分覆盖显示有效数／名单数，真实 0 保留。
4. 成分资金按原 `FUND_CALIBERS` 区分来源，混源返回 null 和 `mixed:*`；单源保留覆盖数并用 DECIMAL 求和。六轨展示口径，不将复盘会自有口径统一称为主力净流入。同一夹具与原 `scan_cross_section` 判定一致。
5. 显式日报日期独立于市场窗口；缺行情或超出行情目录仍请求原日期归档并显示行情缺口。仅未选日期或用户点“最新”时接受最新日。覆盖归档存在／缺失 × 行情日期缺失／目录外四种组合，并增加真实 App 的归档缺行情 E2E。

非严格标量沿用原算法。累计收益字段不完整时，响应增加 `coverage.missing_return_dates`、估计说明并置 `trustworthy=false`；严格模式将标量和曲线一并拒绝。`coverage.complete` 仍是行情行覆盖，页面明确称“行情行覆盖”，不将其解释为收益字段完整。未整体重写底层 `range_aggregate`。

| 选择 | 未采用 | 原因 |
|---|---|---|
| 非严格估计明示缺口，严格模式拒数 | 补零并跨缺口续算 | 保护旧消费口径，不伪造完整性 |
| 原 pre_close 和确定性去重 | 图线另选首日 close | 同一响应指标与图尾应同口径 |
| 有效覆盖和来源传给 UI | 只修 SQL，前端仍显示正常覆盖 | 读者必须看得见缺失与混源 |
| 归档按显式日期请求 | 行情末日替换归档日 | 两种数据的存在性相互独立 |

## 静态产物与身份检查

总整合者发现旧候选 GitHub E2E 加载旧静态包，本地正式前端门禁也在构建后因 Git dirty 拒绝收据。Vite 输出到受跟踪的 `intelligence/api/static`；GitHub frontend 与 E2E 是独立检出，E2E 作业没有先构建。

本次将当前修复源码生成的 `index.html`、`index-DTK0xWLj.js`、`index-B0CgFHVg.css` 纳入实现提交，移除旧哈希资产。未从别树复制生成包、未纳入真实 public 数据。旧恢复记录“提交无 static 变动”只对旧候选成立。

连续构建三文件 SHA-256 完全一致；提交后再次 `pnpm build`，`git diff --exit-code HEAD -- intelligence/api/static` 通过且整树干净。没有排除产物路径或放宽 dirty 检查。JS 544.87 kB（gzip 168.15 kB）的单块体积提示保留。

## 验证与证据

- 14 个定向后端文件：271 passed / 35 skipped，43.07s。新 `test_river_route_contracts.py` 的 13 项使用临时完整 canonical schema 与真实路由。35 项为既有真库依赖跳过。
- 全部前端组件：21 文件、187 passed；最后行情行标签和历史空窗口夹具调整后，相关 6 项再通过。
- 前端 lint、typecheck、build、改动 Python Ruff 和提交钩子通过。
- 完整三端 E2E：46 passed / 2 skipped，1.3m；原会话、SSE、取消、深挖和研究进化用例保留。
- 后端收据 `~/.finance-runtime/test-receipts/20261003T054051Z-e01a60b8-9edbcc15e3bc.json` 是提交前 dirty 定向收据，不是新 SHA 全仓放行证据。

独立外部目录 `~/.finance-runtime/verification/workspace-ui-closeout-1003/spec-fixes/` 包含红灯、修复后、重复及提交后构建日志、静态哈希、E2E 截图和后端收据。独审原文保留于 `~/.finance-runtime/reviews/workspace-closeout-1003/ui-spec-review.md`。

## 测试启动审计隔离遗漏

实现者手动 `pnpm test:e2e` 未设置 `FINANCE_DEPLOY_LEDGER`，FastAPI 启动钩子向 canonical 部署账本追加了 10 条测试启动事件，时间为 04:55Z、04:59Z、05:01Z、05:07Z、05:42Z 的五组双服务启动。全部端口 19071／19074，snapshot_path 指向本 UI 工作树；它们是 `startup`，不是生产 `switch`，不能作为部署证据。

原账本未删改。外部目录的 `test-startup-attribution.json` 保存逐条原记录、行哈希、时间、PID、端口、argv 和现存日志指针；未保存当时 health 响应的事实明确标记。结束后 `lsof` 确认两个端口均无监听。后续所有 E2E 必须用独立 `FINANCE_DEPLOY_LEDGER`；正式 `scripts/run_frontend_gate.py` 已有该隔离，继续使用它。

## 下一步与沉淀

冻结文档提交后交原规格审查者复验五项，再质量独审；总整合者跑精确提交全仓门禁、更新 PR。保留旧中止／dirty／CI 失败收据。未修改用户源树、Pi 活动树、其他任务树、真实新闻或生产市场数据，未调用真实模型或重启生产服务。

保护固化为路由、组件和 E2E 回归。构建身份问题沿用原门禁和受跟踪产物合同；启动归属留在外部证据，不另建部署台账。
