# Workbench 恢复前向候选与真实数据演练

记录 2026-09-23 23:40 至 09-24 00:15 已完成的动作。工程全仓最终结果另看 [在途交接](inflight/ops-workbench-release-0923.md) 与 [PR #900](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/900)，本文不预签尚未结束的 Python 门。

## 背景与版本

用户要求「继续」。主树仍有其他会话工作，本轮只用独立树。重新 fetch 后基座为 `c9dd71dfd678855b61662100ec74625b92ad1f1b`；#871/#861/#874 与 #893 已由其他协调会话合入。五问三合同已有用户委托裁决，不再作为待用户项。

桥模块虽然已进 main，local 夜跑接桥和后续 QC 修复尚未进入此基座。本轮创建 `fix/recovery-release-forward-0923`，原样 cherry-pick 三个已有修复：

| 原提交 | 本轮前向提交 | 内容 |
|---|---|---|
| `4fa70046f` | `c4c8a7812` | local 接桥、fallback、覆盖 QC、正式 CLI 与生产保护 |
| `981c4d629` | `1c3e09c50` | 跨 retry 保留 fallback 尝试 |
| `3abb7a4d3` | `4255207a4` | 派生写入前拒绝无效 recovery close |

固定候选 `4255207a4607216ab6ce48710a8453579ea5cf91`，tree `ca23caf3052faa6a0f18bae44de4d44338987000`。9 文件、296 增/26 删，无冲突，已推送并开 #900；WIP、mergeable=false、未合入。不包含 FinanceQuery 的 `f22cd22b6`，不包含 RAG owner 的修复，未修改任何 owner 树。

## 发现与演练

证据根 `~/.finance-runtime/reviews/workbench-release-20260923/resume-2340/`。候选在其 `candidate/`，前端同 SHA 在 `frontend/`；身份见 `candidate.json`。

1. 生产只读预检没有 09-23 同花顺 bar，拒绝构造；原失败 staging 可构造 5552/5556 行，覆盖率 0.99928。四缺行：001225.SZ、002961.SZ 为非现金公司行动；601995.SH、920025.BJ 缺相邻前日 bar。两缺名：301686.SZ、920229.BJ。原日期的 5565 范围不能套到本日。
2. 本轮重新运行生产数据门，exit2。没有把首轮读数冒称为本轮新读数。
3. 复用 `db.clone_to_staging` 的 APFS clonefile，将旧 staging 克隆到专属 `bridge-rehearsal.duckdb`，仅作离线输入夹具。系统沙箱禁止网络、禁止写真实 DB 目录、生产 runtime 与用户目录。
4. 正式 `bridge-stock-daily --trade-date 2026-09-23` 指向生产时 exit2，保护生效；指向诊断副本时 exit0，写入5552行。既有按日指纹不变只覆盖其实现中的行数、代码、close、amount、pre_close，不夸大为首轮所有列的完整逐行证明。
5. 再次运行同一 CLI，因目标日已有行拒绝，exit2；此次拒绝前后整个副本 SHA256 相同。生产及原 staging 的 inode、size、mtime 不变，未写生产、未换库。
6. 副本数据总门仍 exit2：板块、市场统计、派生层缺失，09-22 市场13列基线外 NULL 也仍存在。桥接成功不是整日数据恢复成功。

完整参数、日志摘要哈希、时间和源/目标 stat 在 `bridge-rehearsal.json`。`rehearse_bridge.py` 只是这组固定输入的一次性演练驱动，不是新恢复入口，无发布函数调用。

## 当日第三源与名称影响

23:54 冻结腾讯六代码原始响应 `20260923-gap-quotes.raw`。复用 `scripts/audit_dated_quote_capture.py::parse_quotes`，确认代码集合与请求一致、全部为09-23收盘后时间、价格与量额单位关系通过。网络命令 `curl --fail` 成功，但未保留数字HTTP状态，不补造200收据。验证在 `gap-quotes-validation.json`。

- 001225.SZ 和泰机电；002961.SZ 瑞达期货；601995.SH 中金公司；920025.BJ N凯达：用于逐只仲裁，不能直接据此越过公司行动或历史参考价合同。
- 301686.SZ 当日名 C中塑股份；920229.BJ 当日名世纪数码。只是带日期的供应商显示名，不宣称官方历史名称/身份已验证。

`missing-names-impact.json`：只读副本提取两行，在内存 DuckDB 调用真实 `_limit_flags`，仅替换为当日报价名作对照。920229 的92.4/132.0在名称NULL时 `is_down=NULL` 被漏计，具名后为true；301686 的 C 前缀识别为新股、is_down=false。名称不只是显示字段，行数门不能代替消费者验算。

现有 `repair_hithink_stock_day.py` 的 `new_code_names` 是「dump有、旧表无」名单，不是任意改名接口；不能直接用它修改桥接后已有行的NULL名称。后续需沿既有逐字段审计与 staging 合同明确输入、身份和写入路径，不手工 SQL 修生产。

## 已完成的工程核验

- 固定干净425候选：ruff通过，8个相关测试文件138P，正式收据 `focused-receipts/gate-2XBldCus/pytest.json`。
- 原样复制旧独立F1/F2/F3探针，本轮重放5P+22P；复制件与执行日志保留。这是本轮重放，不是新的独立审查签字，不移签旧GLM意见。
- 同425另树前端：install/lint/typecheck/test/build/E2E全部exit0；120P，E2E34P/2S，前后干净且身份稳定。收据 `frontend-receipt/frontend.json`。
- registry 五项exit0。Python完整门正在固定425运行，3600秒上限、无自动重试、与本轮前端串行，无部署动作。
- RAG owner独立候选 `2ac97e68c480d5c419290b18f3fdc0529c46b40c` 于23:59结束：14895P/0F/85S/2X、14982 collected。回读并在原树严格校验revision/范围/依赖/干净/漂移0，exit0；原件复制为 `rag-owner-pytest.json`。其绿收据不可签给425或未验组合树。

## 决策与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 原样前向三项现有修复 | 接上已合合同，保留作者与来源 | 采用，不改其他owner树 |
| 混入FinanceQuery/RAG并借旧收据 | 版本和证据失配，扩大本候选范围 | 否；组合后须新固定版本全验 |
| 旧staging副本演练 | 可以证明实际CLI和输入边界，不能证明新生产基线 | 仅诊断；绝不发布此副本 |
| 5552行/99.9%覆盖即放行 | 名称缺失已证明能影响跌停统计，还有派生缺口 | 否；逐列与消费者结果另验 |
| 六报价直接补库 | 并非公司行动裁决或官方全集，缺正式写入合同 | 否；只冻结证据交恢复owner |

## 协调与线上边界

#861评论6626通知新候选与RAG新绿；名称影响在#900评论6627/#861评论6628，均回读正文一致。本轮未合main、部署、换库或调用模型，没有自动发布器。

00:06线上health200、readiness503，唯一critical为market_data_consistency；runtime仍 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`，干净且代码指纹匹配。后续：对齐#900与RAG修复候选，准入后从新生产基线恢复、闭合逐日逐列/跨日与L2检查，最后才切8792。

本轮复用既有门禁、桥模块、克隆原语和报价解析器。没有新增通用工具或改变能力图；一次性固定输入驱动留在持久证据根，不包装为第二条生产写入链。

## 00:21 后续工程收口

425全仓最终14897P/0F/0E/85S/2X、14984 collected、1662.58秒；前后同SHA且干净。完整四叶控制器 `gates.exit=0`，测试及控制器均退出，绿basetemp由既有脚本清理，未删除他人现场。

收尾main已前进至 `5bf47a5ae9aa16768c0ef2df614177253764aeb6`，#901只有4份docs变化。`full-receipt-check.log` 保留对最新main的零漂移拒绝（rc1、落后1次合并）；另以原冻结基座c9执行 `frozen-base-receipt-check.log`，rc0。工程结果没有变红，但不能移签到最新main或未验组合树，不为追文档提交重复开全仓。

最终回传#900评论6644、#861评论6645，正文均回读一致。收尾health200/readiness503，仍3b7e。四缺行、两缺名及派生/历史NULL未恢复；#900继续WIP、未合入，部署和生产写入仍未执行。原件由证据根 `SHA256SUMS` 绑定，不包含整个诊断DuckDB文件或可清理的检出目录。
