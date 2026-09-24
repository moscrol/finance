# 2026-09-22 RAG readiness 续接：单次实跑完成，行情新鲜度仍阻塞

## 范围与身份

用户按任务而非 session 文件归并未收口项，本轮只接「RAG readiness 诊断 / #844 / 数据新鲜度 / readiness 实跑」，不重新盘点其他任务。

- 工作树：`/Users/a77/fwp-wt-rag-probe-diagnostics-0921`，采样与定向测试提交 `a25cf7e244aad0392c617a8a5a02984a82b7f518`，树干净。业务实现仍是 `3451c1d65`；之后仅交接文档变化。
- 生产：8792 / `adcda94b5e401158f1c3aa51f210e1e8d0f0b713` / recovery 树 / `continuous_glm` / `glm-5.3-flash`，不是 #844 候选。重算 intelligence 包指纹与启动值一致，受跟踪文件干净。
- 实跑窗口：2026-09-22 17:58:43–17:58:52 +08:00。
- 本轮无业务源码修改、无外部市场数据抓取、无生产补库、无真实检索/写手题、无重建索引、无服务重启/模型切换、无合并/部署。

## 按发现顺序

1. 开窗主树有他人未提交改动，未触碰；接续原来的干净任务树。主树 code-map 返回 ready，只作定位，现状最终对照候选和生产源码。
2. 旧交接 00:17 的采样没有调用 readiness，因为该 GET 会执行 `ensure_recovery()`、初始化用户存储并创建目录。此次先向用户说明副作用边界，再按“readiness 实跑”做一次请求，不将它标为纯只读。
3. `GET /api/readiness` 单次、客户端总超时 15 秒、连接超时 3 秒、无重试：curl rc=0，HTTP **503**，耗时 **780.664ms**，响应 `missing_critical=["market_data_consistency"]`。这是这一样本唯一失败项，不是普遍唯一根因或历史 timeout 的归因。
4. 同一响应的 RAG 参数协议兼容，必要四参数齐全；五个可选过滤/receipt 参数缺失，提示 legacy。worker `ready` / active=1 / model_load_count=1 / recoveries=0；queries_served=6 是进程累计值，不是本轮新发六题。采样前后服务及 worker PID/启动时间不变。
5. 生产门比较 `fact_market_daily.max(trade_date)` 与快照 served 日期。本次主库为 **2026-09-18**，快照已由旧交接的 09-21 推进到 **2026-09-22**，所以正常拒绝就绪。快照自报 `akshare_exact` / `complete` / `fresh`，现有契约 PASS；本轮不据此签供应商真值或快照所有字段质量。
6. 显式 `duckdb.connect(read_only=True)` 查询 canonical 表，五张关键事实表最新日均为 09-18，09-21 和 09-22 均 0 行。另按 `information_schema` 枚举所有含 trade_date 的 fact 表/视图，最大日期原件已封存；并非全库所有表同一天，有 09-02、09-08、09-15 和空表。
7. 不能只验行数：09-18 个股 5553 行中 amount 非空 5552；主线板块 71 行的 today_pct/amount/strength 均为空。来源是 `local:mainline-v1`；`compute_local_stats.compute_mainline_local` 只插入题材—板块名单、source、updated_at，不插入这三个行情数值。因此这里是字段用途边界，不据此宣布新数据损坏，也不把名单关系当完整行情。
8. 用当前 KB 代码的 `RagStore._index_wide_gates()` 检查盘上元数据，空 chunks/向量占位，不加载索引载荷、不遍历 wiki。macOS sandbox 禁网络/文件写；生产环境仅取已知 RAG 标量设置，来源 ps 未提供带引号的环境序列化，保留此限制。索引建于 09-18 13:23:40Z，169635 chunks，年龄 3.8595 天 < 默认 14 天；chunk_profile 一致，整库年龄/切块无 stale/unknown；向量与 BM25 元数据对齐。**没有验证逐页内容新鲜、真实召回、worker 当前加载内容身份。** `source_dirty=true` 不作为整库一票否决。
9. #844 在 Gitea 实查仍 open / WIP / 未合并，远端 head 为 `18c6215791e5`；本地 `894ad9f65`、`a25cf7e24` 及本轮文档尚未推送。Gitea 报 mergeable=false 不能单独推出冲突（WIP 本身会拦）。未执行推送、评论、关单或合并。

## 数据覆盖摘要

下表仅表示 **09-18** 的行和指定字段覆盖，09-21/09-22 下列全部为零。

| canonical 表 | 行数 | 非空字段数 |
|---|---:|---|
| fact_market_daily | 1 | total_amount / advancers / sh_index_close 各 1 |
| fact_stock_daily | 5553 | close / pct_chg 各 5553，amount 5552 |
| fact_sector_daily | 403 | pct_chg / amount / diff_ratio 各 403 |
| fact_sector_stock_daily | 52769 | price / pct_chg / amount 各 52769 |
| fact_mainline_sector_daily | 71 | today_pct / amount / strength 各 0；只承诺名单关系 |

## 决策与被否方案

| 选用 | 未采用 | 理由 |
|---|---|---|
| 一次真实 readiness，提前说明接口副作用 | 再把 help 或只读复算冒充 HTTP 实跑 | 补上旧交接明确缺少的证据；不轮询求绿 |
| 分开记协议 / worker / 行情 / 内容新鲜 | 看到 503 就称 RAG 坏了，或看到 worker ready 就称检索质量通过 | 不同判据测不同能力 |
| 保持原始日期与 503 | 改快照日期、放松一致性门、部署 #844 以求绿 | 探针并发去重不生产行情事实 |
| 元数据层核验、内容层未验 | 扫全库正文或用 source_dirty 直接拒绝所有页 | 只检查本轮需要的低成本事实，不越过逐页判据 |
| 继续引用独立行情恢复任务 | 本分支接管历史回填或直接重跑旧日 daily-full | 历史日期不等于当前快照数据日期；避免第二写入链和并发发布 |
| 定向回归，保留 blocked | 复用前轮 230P/4S 作为完整工程或独立审核通过 | 样本、提交和测试分母必须各自绑定 |

## 验证与证据

提交内摘要：`docs/verification/2026-09-22-rag-readiness/summary.json` 与 `raw-manifest.json`。

原件私有目录：`~/.finance-runtime/reviews/rag-readiness-resume-20260922T175900/`。最终 manifest 固定 33 份原件，逐项 SHA256 回读全部一致。原始 HTTP body 含 episode 标识，仅留私有目录；提交摘要不携带这些标识或凭证。

- `readiness.http.json` / `readiness.body.json` / `.headers`：单次 HTTP 状态、正文、计时；curl 没用 fail 模式，**rc0 表示成功收到响应，不表示 readiness 通过**。
- `health-before.*` / `health-after.*`、`processes-before.txt` / `processes-after.txt`：生产身份与进程观测。
- `database-dates.json` / `all-fact-max-dates.json`：显式只读日期、按日行数/非空数、来源。
- `protected-before.json` / `protected-after.json`：启动器、LaunchAgent、快照、索引元数据及索引文件哈希清单本轮不变。主库完整 SHA256 前后均为 `29c26d5cd4dc055b2bfd1429676128da87b372a19ad79bec273d2320364ed102`，stat 亦同；不据此排除所有其他文件的并发活动。
- `index-metadata.stdout.json` / `index-metadata-receipt.json`：元数据层结果、KB 当前代码身份与前后哈希；KB HEAD `8a413cde59cd0d6a7757c845243024a3016b50bc`，不改共享 KB 内容/冲突。
- `targeted.log` / `targeted.xml`：使用主树 `.venv-workbench/bin/python`，干净 `a25cf7e24` **226 passed / 0 failed / 0 skipped**，38.37 秒。六个文件：kb_rag、singleflight、rag_worker、workbench_api 和两组回放脚本测试。`env -i` + 独立 HOME / basetemp，未继承个人台账与联网凭证；离线标志开启。自动收据 `test-home/.finance-runtime/test-receipts/20260922T100200Z-a25cf7e2.json`。
- `ruff.log`：PR 涉及的八个实现/测试/回放 Python 文件检查通过。

本轮未跑全仓 Python、前端、E2E、registry 或独立外审。226 项不是前轮 230P/4S 同一分母，也不是本轮 merge gate。生产仍旧版，响应没有 #844 新加的 failure_kind / elapsed_ms 字段；780.664ms 是客户端整次 HTTP 耗时，不能当新探针性能。

## 后续与停止边界

1. **诊断与一次 readiness 实跑已完成，任务整体继续 blocked。** 行情恢复交由 `fwp-wt-market-recovery-0921/docs/handoffs/inflight/fix-market-recovery-0921.md`；该线仍欠来源/分母/板块/派生/L2 等合同与质量门，不在这里批准写库或发布。
2. 09-21 已是历史日，必须走历史回填规程/冻结日期正确输入；09-22 当日盘后走当日复盘流程。不得机械照抄旧交接“daily-full 补 09-21”，也不手改日期标签。
3. #844 仍需目标 tip 的完整适用门禁、独立审核及用户合并/部署授权。RAG 部署与 K3 / judge-off 分开；本轮不恢复被回滚模型配置。
4. 数据恢复后再做受控 readiness 复验；真实 query、命中页新鲜度、召回质量和 fallback/恢复另验。当前 n=1 无法证明历史间歇 timeout 消失。

## 工具沉淀盘点

没有新增运行时能力或改产品门，本轮不改能力图谱、共享 harness 或门页。正式故障注入/单飞测试已在 #844；只复跑，没有复制一套测试。两份私有采样器分别绑定这次生产 HTTP 取证和元数据门，属于一次性现场证据，不伪装成通用部署工具；泛化需要副作用准入、自动根/PID 发现及脱敏合同的独立测试，超出此次诊断。低层原则（健康不等于就绪、行数不等于值完整、元数据不等于内容新鲜）已有项目规范，未重复建方法论清单。
