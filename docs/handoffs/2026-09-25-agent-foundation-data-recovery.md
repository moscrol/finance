# 2026-09-25 Agent foundation：数据恢复已授权，输入与数据门仍阻塞

## 背景与授权

用户在上一轮询问「是否授权 canonical daily-full 补齐 9 月 23/24 日数据后继续部署」后回复「授权」。本轮已获得生产数据恢复和后续部署授权，不再等待相同授权。此前 `2026-09-25-agent-foundation-deploy-blocked.md` 的未授权描述只代表当时状态，由本记录接续，不修改旧快照。

代码仍未切换，生产数据仍未写入。证据根：`~/.finance-runtime/reviews/agent-foundation-0924/deploy/authorized-data-01/`；其中 `status.json` 与父目录最新 `status.json` 同步，旧状态保存在 `status-before-authorization.json`。原 PR #912 保持 WIP，不是部署完成证明。

## 按发现顺序

1. 核对 `daily-full-review`、`duckdb-backfill`、已安装 S7 夜跑脚本及 `recover_local_review.py`。当前夜跑走 `local`，同步代码根为 `~/.finance-runtime/finance-sync-adcda94b5e40`。历史恢复入口要求日期已核验的新浪历史 JSONL 与完整东财快照；只有所有检查成功才经既有 staging 发布器原子换库。不能拿 latest-only 输入贴到历史日期。
2. 未发现运行中的 nightly/daily/recovery 写入进程，读锁检查通过。保留旧失败 staging 的 APFS 写时复制副本 `nightly-failed-preserved.duckdb`，未覆盖原 staging，也未新启动发布器。
3. 生产只读覆盖检查表明，不止 09-23/24 缺数据：`fact_stock_daily` 到 09-22；`fact_market_daily` 09-21 无行、09-22 虽有行但 13 个关键字段为 NULL；板块及多项派生数据停在 09-18。两天 `check_daily_review_data.py --phase data --plan local` 均 exit 2、INCOMPLETE。停采表与当前 local 必需表须分账，不能按所有历史缺日盲补。
4. 通过现有同花顺客户端取得 `daily-k-10d` 原始 Parquet，1,076,626 字节，SHA-256 `443be228f56f2a87f4239b303dfba57bde7919a367fd5588bc40c90c7d852a0d`。源日期覆盖 09-11 至 09-24；09-23 为 5,556 行/唯一代码，09-24 为 5,557 行/唯一代码。两日开高低收、量额 NULL 检查为 0；另做收盘正值、有限值及非负量额检查为 0。该检查不是完整价格质量、市场全集或停复牌证明。
5. 新浪 `600000.SH` 有 09-23 的真实历史记录，单票探针成功；没有据此宣称全市场历史抓取成功。东财单页探针取得 100 行，源日期 09-24；随后完整快照拉取被现有熔断器以 `UpstreamRefusing` 拒绝。完整快照没有落盘，不用单页成功代替全量成功，也未继续循环重试。
6. 同花顺原始 dump 不提供股票名、参考前收、涨幅、canonical 换手率。其 `turnover` 是成交额，不能当换手率。现有严格预演可计算部分字段，但不等于正式发布：`repair_hithink_stock_day.py` 的真实生产 spec 钉在 09-11，`hithink_recovery_candidate.py` 是纯提案且现有特例钉在 09-21。不能仅换日期或标签把它们套到 09-23/24。仍需按已有恢复合同闭合逐日名称、新股、停复牌、除权参考价及板块身份。
7. 旧失败 staging 的独立副本检查同样 exit 2：09-24 有一行市场汇总、31 个申万行业，但个股行情 0 行，市场汇总的 13 个关键字段为空，多项派生表缺失。因此不能因 `MAX(trade_date)=09-24` 就将它晋升生产。
8. 北京时间 00:41 回读 `/api/health` 为 200、`/api/readiness` 为 503，唯一 readiness 失败项仍为 `market_data_consistency`，快照 09-24 / 市场库 09-22。生产版本仍 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`；启动器与上轮备份字节一致，软链未改。生产库 inode/size/mtime_ns 与此前恢复交接记录一致；该项是元数据比对，不冒称数据库逐字节独立验真。
9. 再次 fetch 后 `gitea/main` 仍为 `03352758cf9b31e3f5d179b517be48cb89588679`。未重跑该 SHA 全仓门禁，未切 8792，未运行真实模型探针；部署账本无端口 startup 歧义未处理。

## 决策与被否方案

| 采用 | 否决 | 理由 |
| --- | --- | --- |
| 将授权状态更新为已授权 | 继续把缺少授权列为阻塞 | 用户已经明确回复授权，当前卡点是输入与数据质量 |
| 保存同花顺原件但不直接写 canonical | 把 dump 字段拼成生产行 | 量额单位、名称、参考价和例外必须满足日期特定合同 |
| 完整东财抓取被拒后保留失败 | 用单页或日期标签凑完整快照 | 单页不覆盖市场，无法满足恢复入口输入要求 |
| 保留旧 staging 的隔离副本并跑数据门 | 将已有 09-24 staging 直接换库 | 有日期行不代表关键值或下游完整 |
| 沿用既有恢复合同与质量门 | 临时 SQL 修日期、放宽门禁或重开发布框架 | 这些做法不能恢复事实，只会隐藏数据缺口 |

## 验证与收据

- `hithink-capture.json`、`hithink-daily-k-10d.parquet`、`hithink-shape-audit.json`：原始取数、日期/代码数量及有限的值检查。
- `sina-600000-2026-09-23-probe.txt`：单票日期化历史探针，不是完整恢复输入。
- `eastmoney-probe.json`、`eastmoney-first-page.raw.json`、`eastmoney-capture.json`：单页成功与全量失败分别留证。
- `data-gate-2026-09-23-before.txt`、`data-gate-2026-09-24-before.txt`、`data-gate-2026-09-24-staging.txt`：三次真实数据门失败，均为 exit 2。
- `health-final.json`、`readiness-final.json`、`status.json`：切换前最终身份、授权与技术阻塞。首次误用不带 `/api` 的探针为 404，原件另存 `*-wrong-route-404.json`，不当作服务故障。
- `MANIFEST.json`：17 份当轮证据的大小和 SHA-256，含保留的失败 staging。后续 PR 评论/提交回读另账，不修改该清单原件。

没有应用代码改动，没有本轮完整工程验收、数据恢复成功或生产发布收据。原 ea42 完整门禁仍只证明 ea42。

## 接续与边界

1. 不重复索要已获的数据恢复/部署授权。复用已保存原件；完整输入未闭合前不启动历史发布器。
2. 接续现有行情恢复合同与协调线，闭合逐日名称、新股/停复牌/参考价、冻结板块成员身份。旧协调交接记录的成员缺口是历史观测，须对本轮目标日期重验，不能直接套用旧分母或旧例外白名单。
3. 输入齐备后，按受保护的 staging 链处理依赖日期及 09-23/24，完成值非空、同日、跨日、L2 等验收后才原子换库。不得把当前日数据贴到历史日期，也不修改缺值基线凑绿。
4. 数据全绿后固定届时主干，重跑精确 SHA 的完整四叶，再处理台账归属、受测解释器接线、切换/回滚与切后业务验收。

工具沉淀：本轮复用取数客户端、日期解析器、数据检查器、恢复发布器及现有熔断器；未创建临时修库脚本。新证据说明旧输入缺失/值空壳被现有门禁检出，不另造一套门禁。原始数据与失败副本留在树外，不进 Git。
