# mootdx 历史日线通道排障

## 这个分支做什么
定位 mootdx `bars()` 返 0 行的根因，并把「源死亡被静默吞成空数据」改成 fail-fast。只读排查 + 护栏代码；不写生产库，不恢复 09-21 数据。

## 决策与被否方案
| 选了什么 | 否了什么 / 理由 |
|---|---|
| 判定为供应商停供，停止修客户端 | 不换 pytdx/不调参：39 台扫描 15 台可连，K 线 body 恒 2 字节，报文与 pytdx 1.72 逐字段一致 |
| 加健康探针 + 熔断 + CLI 退非零码 | 不再让 `rc=0` 掩盖 `rows_written=0` |
| 探针走 `client.bars()` 真实路径 | 不拿连接状态/`stock_count` 当可用性——正是它俩全绿才骗过两周 |
| 三态 no_route/metadata_only/empty_payload | 不合并成布尔；三者处置不同（换网络/换源/查参数） |
| 不删 `db/*.staging` | 已从孤儿变成今晚失败夜跑（rc=2 未换名）的取证现场 |

## 当前状态
未提交：`mootdx_source.py`、`tests/test_mootdx_source_health.py`（两个新增）、`sync/sync_mootdx_stock_daily.py` + `cli.py`（改）。证据在 `tmp/mootdx-unblock-20260922/`（已 gitignore），结论见 `diagnosis-conclusion.json` 与 `server-sweep.json`。已删 09-17 备份（receipt 第 6 步明示可删）；磁盘现 39Gi。

## 已验证
- 12 项新测试 + 21 项既有相关测试通过；Ruff 全绿。
- 端到端：`sync-stock-daily --limit 1` 打一次性临时库，`rc=2`、`verdict=metadata_only`，附 server/异常原文/换源建议；改前同命令 `rc=0`。
- 回归样本钉住真实 body `2003`（ret_count=800、无 K 线体）会让 tdxpy 抛异常而非返空。
- 生产库只读查询：`fact_stock_daily` 中 mootdx 最后一天 = 2026-09-07（345 万行/689 日），09-08 起逐日换临时源。
- 生产库大小/指纹未变，未创建新 staging。

## 未验证 / 已知边界
护栏只覆盖 mootdx 路径；`sina` / `eastmoney:snapshot` / `hithink` 各源仍可能静默返空，未加同类探针。熔断阈值 50 是推理值（退市停牌零散分布），无历史数据标定。mootdx 通道**不可能修复**，护栏只保证「死得可见」。09-21 仍整日 0 行，三门仍 `rc=2`。

## 下一步
09-21 的数据其实已在 `fact_stock_daily_hithink`（staging 覆盖到 09-22、5553 行/日），缺的是 hithink→`fact_stock_daily` 的 ingest 路径。`repair_hithink_stock_day` **不适用**：其断言与 `stock_name`/`turnover` 继承都假设该日已有旧行，整日 0 行会让 5553 只票全部落入 `new_code_names`（需逐票钉 8 字段预期值）。需新写 ingest 并单独取写库授权。

## 踩过的坑
两表同名列语义全错位：hithink `turnover` 是成交额（元，÷1e8 得 amount）、`volume` 是股（÷100 得手），而 `fact_stock_daily.turnover` 是换手率（hithink 根本没有）。按同名列对齐 INSERT 会灌进量级差 1e8 的脏数据。`adjusted='none'` 必须先断言，否则 `pre_close` 校准语义整套不成立。另：`rows` 是 DuckDB 保留字，别拿来做列别名。
