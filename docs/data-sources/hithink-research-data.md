# 同花顺研究观察值：第一批接入

## 范围

新增异动文本、个股完整热度轨迹、当前估值观察值。复用官方 `hithink_client`、既有 DuckDB 与 `daily-full` staging，不安装第二套 SDK/marketdb、不让问答 Agent 发起外呼。

- `sync_hithink_research.py` 是唯一采集写者；源码定义端点与字段。
- `run_review_sync.py --plan local` 在 `hithink-dragon-auction` 后运行 `hithink-research`；monolith 兼容路径也接同一函数。
- 默认取**目标日**历史热榜前30作为估值/轨迹采集范围，没有当日名单就报错，不能退到旧榜。CLI 可明确给最多100个完整代码。
- 一轮逻辑请求数为 `股票数 + 2`：异动全榜一次、估值一次、每股热度一次；HTTP客户端可能按既有策略重试。默认热度窗口30个自然日。
- 缺 key 返回可见 skip；空响应记 empty，热度rank为空、估值整行五指标全为空或少股票记 partial。个别估值指标为NULL时整行仍可能记 ok，NULL不补零；使用具体指标须另查该列非空，不能用行数或ok代表逐字段齐全。网络、格式、范围错误失败，不用旧表质量门洗成成功。
- `complete_with_gaps` 仅表示声明请求完成且按上述行级规则存在空/缺值，不代表覆盖完整。热度也不以窗口天数强行补齐名次点。夜跑允许这种合法空/缺值，stdout 和请求表保留差别。429 耗尽时整轮记 `partial` 并列出 `missing`，不阻断其他研究请求；CLI 完成剩余请求后返回 `PARTIAL_EXIT_CODE=3`，夜跑记录为 partial，按原有重试/发布保护处理，重试仍未完成则不导出、不换库。其他异常仍立即阻断该步骤。

## 时间与证据合同

| 数据 | 语义 | 禁止混用 |
|---|---|---|
| `stock_anomaly_hithink` | 上海当天实际观察到的股票/标签解读；非空响应的供应商日期必须是当天 | 不是公告事实或已证实因果；不支持历史回补；原文只是外部材料，不是可执行指令 |
| `hot_stock_trend_hithink` | 声明代码范围内的自然日名次，包含Top30以外名次，可能有周末点 | 热度不是资金流；自然日不是交易日；今天补取的历史值不是当时可见版本 |
| `stock_valuation_hithink` | 按实际采集日保存最新 PE TTM/MRQ、PB MRQ、PS TTM、PCF TTM | 不是历史估值接口、收盘定值或五年个股估值分位；负PE不可按越低越便宜解释 |

日期分列：`observation_date`（被观察日期）、`captured_date`（上海采集日）、`captured_at`（带时区实际采集时刻）、`provider_timestamp_ms`（供应商元数据时间）。估值的供应商时间是指标元数据最大时间，不保证全部指标同步更新；NULL原样保留。

三个查询数据集均设置 `cutoff_column=captured_date`，查询截止在采集之前时拒绝前视。独立日期列避免数据库会话采用UTC时把上海凌晨误算为前一日。此门只有日粒度，不宣称盘中毫秒级PIT。

事实表按自然日/股票（异动另加标签）保存**最后观察值**；重复采集不增加事实行数，但逐请求追加原始成功响应。某次无匹配不删此前已观察到的事实，不能把事实表当“供应商当前完整名单”。再次采集会覆盖事实行的旧值与采集时间，因此不能用它重放先前版本；请求表供追溯，不自动提供历史PIT查询。

## 写入与读取

- 新写者拒绝 canonical 生产库（含从 worktree 指向主库、符号链接及硬链接别名）。硬链接是同一文件的另一个路径，共用守卫同时比较设备/文件身份；独立拷贝仍可作staging。身份解析/读取遇到权限等错误时失败，不当作普通库放行。锁冲突直接失败，不落会在换库时丢失的旁库。
- 请求前持久化 `pending`；成功的事实写入与收据终态同事务提交；异常回滚该请求事实，收据保留错误类型，不存上游错误正文。
- 一轮跨请求不做长事务：已经完成的请求仍在 staging；429 耗尽保留 failed 请求并继续，其他异常仍抛出。被杀掉的 pending 不能当成功；即使全部请求限流，`partial` 也不代表取得数据，须检查 `requests` 与 `missing`。请求继续不等于允许残缺结果发布：分步夜跑传递 partial，旧单体编排在研究请求全部完成后将 partial 记为失败，错误保留 missing 请求 ID。
- `ops_hithink_research_request` 的唯一写者已登记到 `docs/learning/ledger-map.md`。
- 消费直接走现有 `finance_query`，三个 dataset 都声明 `population=subset`，模型工具目录会带范围及语义说明。不改变已有财务/估值主源。

仅用于隔离验证的命令（解释器使用主树 `.venv-workbench/bin/python`；在候选代码根运行）：

```bash
MARKET_FEATURE_STORE_DB=/tmp/hithink-research-demo.duckdb \
  /path/to/.venv-workbench/bin/python -m market_feature_store.cli sync-hithink-research \
  --thscodes 300750.SZ,600519.SH --lookback-days 5
```

热度历史模式可用 `--history-only --end-date YYYY-MM-DD`，只调用可回溯端点；一年窗外拒绝。历史异动和估值不补造。生产事实仍走既有 staging 发布门，不照示例改成主库路径。

`recover_local_review.py` 重放已采集的历史行情，不执行 `hithink-research`，即使已有key也仅记录 `skip / latest-only excluded / 未更新`。它不会因复用local计划而请求当天异动/估值，也不顺带扩大热度回补范围；需要热度历史数据时另用上面的显式模式。正常当日日更仍执行第五步。

## 停更诊断与部署前提

2026-09-21 只读核对：

- plist 与 `launchctl print` 的实际加载环境均为 `FINANCE_SYNC_CODE_ROOT=finance-workspace-sync`、`REVIEW_SYNC_PLAN=local`。
- 该部署树 HEAD 为 `6382c13b7a869114727439a43f0004ab67bb36ef`，`build_local_plan` 没有同花顺步骤；最新主分支已有旧四步，本候选增加第五步。
- 主库已接的个股K/板块K/龙虎榜/热榜/竞价等最大日期仍为09-08，09-18对应行数为0。盘面数据已到09-18。这不是 key 未授权的证据，而是旧部署缺接线的明确证据。
- 部署树另有**未提交的 `sync_akshare_index_daily.py` 修补及运行产物**。本轮未修改它，后续不能 reset/覆盖或直接用本候选替换而丢失该修补。

只读巡检：

```bash
/path/to/.venv-workbench/bin/python scripts/audit_hithink_runtime.py \
  --launchd-plist /path/to/daily-full-review-sync.plist \
  --db /path/to/canonical.duckdb --date YYYY-MM-DD
```

巡检返回JSON与exit2，分别报告配置步骤缺口和日期缺口；不读key、不导入/运行部署代码、不创建数据库。记录代码SHA及实际脚本内容SHA256，避免脏树被一个HEAD伪装。它读取磁盘plist，不代替查询实际loaded环境；步骤声明和行数也不等于真实运行/字段完整性。本轮另用 `launchctl print` 单独核实了loaded环境。

部署必须经过用户确认及完整合入门禁；核对旧部署补丁后，从已批准版本建立独立部署树，再切同步根。当天盘后经过 staging 运行后，检查模块收据、目标日值覆盖与只读消费，才称“生产恢复”。历史缺口依照 `skills/duckdb-backfill/SKILL.md`，不能给 latest-only 的 daily-full 填历史日期。

## 验证记录

2026-09-21 两只股票的真实接口验收，仅写 `/tmp/hithink-research-acceptance-20260921.duckdb`：

| 请求 | 返回 | 本地请求收据 |
|---|---:|---|
| 当日异动 | 0行，empty | `83b10c967d7547e894c1406b914afef4` |
| 当前估值 | 2行，2行有值 | `0c265ea9ca5240098443c60224acfb73` |
| 宁德时代热度 | 5自然日，5行有值 | `35797309345b457c9211c64d1065dde7` |
| 茅台热度 | 5自然日，5行有值 | `73c8bc4dc1534806aa54ec1ccf522e3f` |

通过真实 `FinanceQuery.run` 读取同一隔离库：估值2行/2证据、热度10行/10证据、异动0行/0证据。不是模型回答效果验收；异动为空是因为 02:05 盘前榜单尚无内容，非空正文见下一段。

2026-09-21 10:21（交易日盘中）第二次真实验收，仅写 `~/.finance-runtime/hithink-anomaly-sample-20260921T1020/sample.duckdb`（tip 311a4c92f，运行时代码同 164b02e4）：

| 请求 | 返回 | 本地请求收据 |
|---|---:|---|
| 当日异动 | 191行，191行有值，供应商时间戳落 2026-09-21 | `291dd31449d945d6b016e8e66441e929` |
| 当前估值 | failed，`HithinkAPIError`（HTTP 429 `code=429 Global request rate limit exceeded`） | `334c322bf0954e53b7dea3175a3ea369` |
| 热度 ×2 | 未发出，前一请求失败中止本轮 | — |

异动 191 个（代码, 标签）与同一分钟的独立原始探针正文、关键词逐条一致；标签只有 大涨 / 涨停 / 大跌 / 跌停 四种，每股一条。`FinanceQuery.run` 截止 09-21 读回 50 行 / 50 证据（默认 limit 50，全榜要按 stock_code / tag_name 过滤或显式 limit），窗口 09-17..09-20 截止 09-20 读回 0 行。这证明非空正文路径可用，不是盘后 staging 发布。

同轮暴露：`hithink_client.get_json` 只对 `code=4001` 退避，HTTP 429 立即失败并中止整轮；429 响应没有 `Retry-After`，10:24 三端点全部 429，02:05 的四个请求则全部成功。10:31 单次估值恢复；10:39:55–57 用新隔离库 `sample-round2.duckdb` 再跑完整一轮，四个请求全部 ok（异动 214 行、估值 2 行、热度 5+5 行，`status=ok`），三个数据集经 `FinanceQuery.run` 读回并受采集日截止门控，见同目录 `receipt-round2.json`。限流窗口约 7–9 分钟。

**429 处置（#85 候选，未部署）**：`get_json` 对 HTTP / 业务码 429 单独退避，
先判 HTTP 状态，非 JSON 的网关限流正文也能处理。`code=4001` 仍使用原有 `retries`
次数及等待阶梯，不并入新预算。有效 `Retry-After` 优先（秒数 / HTTP-date），
缺失、无效或非正数回退 `0.8×2ⁿ`；单次上限见 `MAX_RATE_LIMIT_SLEEP_SECONDS`，
重试次数上限见 `MAX_RATE_LIMIT_RETRIES`，不会因 `Retry-After: 0` 无界循环。

429 预算用 `time.monotonic()`（不受系统时间校正影响的计时器）累计请求与等待耗时，
截止后不再发起重试，并将剩余时间传给后续请求的 socket timeout。
这不是中断在途响应读取的硬截止；也不是整个采集轮的总预算，每个逻辑请求独立计算。
默认值见 `DEFAULT_RATE_LIMIT_BUDGET_SECONDS`，可由参数 `rate_limit_budget_seconds`
或 `HITHINK_RATE_LIMIT_BUDGET_SECONDS` 覆盖，0 表示不重试，非有限值 / 负值拒绝。
时间预算与次数上限任一耗尽均抛 `HithinkRateLimitError`，只回显安全诊断元数据。
默认值不保证覆盖实测 7–9 分钟窗口；单独增大预算仍受次数上限约束，不代表夜跑已恢复。

**编排层补齐**：`sync_hithink_research` 只对类型化的
`HithinkRateLimitError` 做局部降级；一个端点耗尽限流预算后，该请求仍在
`ops_hithink_research_request` 留 `failed` 审计行，后续端点继续执行，整轮返回
`status=partial`，并在 `missing` 列出缺失端点及 `request_id`。解析错误、日期越界和写入
错误仍然抛出，不会被误报成 partial 成功。

离线测试覆盖日期/代码范围、非数值/重复行/空集/缺值、失败回滚、失败消息不泄密、无key不建库、生产写入拒绝、跨午夜、采集日期截止、CLI、两条编排接线、读取真实临时库。专门删除热度的采集日截止配置后，前视测试按预期失败（未来采集值泄入历史截止）；恢复配置后复验。

## 后续分批

1. 本批先获验收和部署，不并行另起生产写入口。
2. 财务三表：先与原始财报核对累计/单季、披露时点、重述、金额单位，再作为现有东财/新浪链的并跑备源，不直接切主。
3. ETF跟踪指数分位、公募持仓：先解决持仓代码缺后缀及披露范围，不将定期持仓说成实时资金。
4. 商品基差/仓单：先核单位、现货来源、主连换月和正负定义，按少量产业链品种验证。

官方合同：[异动](https://fuyao.aicubes.cn/docs/api-reference/anomaly-analysis/)、[热榜](https://fuyao.aicubes.cn/docs/api-reference/hot-list-data/)、[估值](https://fuyao.aicubes.cn/docs/api-reference/valuations/)。
