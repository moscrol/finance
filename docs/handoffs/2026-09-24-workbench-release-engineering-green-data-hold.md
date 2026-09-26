# Workbench 组合验收：工程通过，数据仍 HOLD

## 状态与身份

本记录写于所有本会话全仓门结束之后。未合 main、未部署 8792、未创建正式恢复 staging、未换库、未写生产数据。FinArena #82 已归档，不重开；#76 FA-2 不在范围。

受验代码提交是 `eb4ec08f0680f9ba8cdaf5f3e8a95be34861b12a`，基座为 `gitea/main@3bb81b9638f97b4773ce0f338df3a505b7c0162f`；远端 main 已用 `ls-remote` 核对。工作树 `/Users/a77/fwp-wt-workbench-release-0924`，分支 `fix/workbench-release-0924`。代码候选已推本机 Gitea。本文及 inflight 是后继文档提交，不能把 eb4 收据移签到文档提交或未来组合。

证据根定义：

- `R=~/.finance-runtime/reviews/workbench-release-20260924`
- `I=~/.finance-runtime/reviews/workbench-release-20260924-independent`

PR #900 是协调入口，其 head 仍为另一条 `fix/recovery-release-forward-0923@4255207a`；没有擅自替换该分支或关闭 PR。候选分支不是 #900 当前 head，禁止混签。

## 按发现顺序

1. `62d1ae` 的旧完整门自然结束，15027 passed / 85 skipped / 2 xfailed，仅签该 SHA。
2. `f3f5bf532` 在 `_limit_flags` 拒绝目标日 NULL、纯空白和 ASCII 控制字符名称；`compute_stock_high_local` 不再吞 `InvalidStockName`。三条实际 CLI 的内存/隔离夹具验证了非零退出及派生表不变。
3. 合入独立 delivery-status 回归，组成 `2ddd43f85`。其完整门自然结束，15060 passed / 85 skipped / 2 xfailed，15147 collected，checker rc=0；前端及 registry 通过。没有中止或把旧结果改成新版本结果。
4. 独立方发现历史行边界：当前名称有效，前日名字 NULL 时，SQL NULL 经 `bool(None)` 被当成已断板，连板高度从 2 变成 1；空字符串又算成 2。两种确定结果都缺身份依据。
5. `eb4ec08f0` 保留历史名称未知状态，只在 `_streak` 实际消费该行时、任何派生写入前拒绝，错误带代码和真正的历史日期。三个调用点均传代码。有效非涨停行之后的更早历史不再消费，当日总览不消费历史 streak。
6. 新增 24 项历史保护回归；相关 13 文件 207 passed。独立方原 v2 探针原样复制回放 9 passed；它在 2ddd 原件为 6 failed / 3 passed。历史红保留。
7. eb4 完整工程门、独立变异验证及一次真实自然入口结束。工程门通过，但自然验收整体不通过：readiness 前后 503，关键项 `market_data_consistency=false`。

## 决策与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 把缺名当普通股或把 NULL 布尔化成 False | 生成貌似完整但没有身份依据的统计 | 否 |
| 校验窗口里任一旧名称无效就全拒绝 | 会把有效断板之后的无关旧缺口、无需连板的总览一起阻断 | 否 |
| 保留未知，实际消费时拒绝 | 既保真，也限制阻断范围；先于 DELETE/INSERT | 采用 |
| 用 49 个历史完整候选自动拼接当前成员 | 数量相等、包含已知成员仍不等于当前身份成立 | 否，仅留假设 |
| 用当前名单或文件 mtime 给历史名称定日 | 文件加工时间不是上游观察时间；同日凌晨也不证明交易时点 | 否 |
| 原 9/22 凌晨具名捕获作为进一步证据 | 原 receipt 和 70 页哈希可核，但只有盘前窗口且少三个身份 | 保留线索，不放行 |
| 以工程绿、health200 或一次问答完成代替发布 | 不覆盖数据日期一致性与真实恢复 | 否，HOLD |

## 精确版本验证

### eb4 工程门

`R/history-candidate/full-receipts/gate-Zgg3Ayou/pytest.json`：

- 干净树，Python 3.12.13，解释器为主树 `.venv-workbench/bin/python`。
- 依赖指纹 `3328bed61f3e21ea`；未绕过依赖门。
- 15171 collected；15084 passed、0 failed、0 error、85 skipped、2 xfailed；17 条警告。
- 无 ignore/deselect/keyword/markexpr/last-failed/maxfail 裁剪。
- `check_test_receipt.py` 绑定完整 scope、工作树根目标、完整 SHA、零基座漂移，rc=0，见同根 `receipt-check.log`。
- `python.exit`、`gates.exit` 和五项 registry exit 均为 0。

前端收据 `R/history-candidate/frontend-receipt/frontend.json`：同一 SHA、前后干净且身份稳定；install/lint/typecheck/test/build/E2E 均 0。单元 123 passed；端到端 34 passed / 2 skipped。跳过不是执行通过。

2ddd checker 首次误用不存在的 `--receipt-dir`，usage rc=2 留在旧 `receipt-check.log`；更正后的 `receipt-check-verified.log` rc=0。这是调用配置错误，不是产品失败，也未删原件。

### 独立与真实入口

`I/eb4-live/sealed-evidence.json` 封存 35 项变异：历史 3、隔离 sidecar 2、启动 16、传输 12、delivery-status 2。每项红变体均被检出，恢复后对应测试通过。独立方做过一份未采用的并行提案，因此不是盲审；其 137P 属于该提案，不签 eb4。旧 fixture 的 1F/2P 与错误 cwd 导致的收集错误亦分别隔离。

真实入口由独立方在隔离用户/Episode 存储、生产路径禁止写入的环境执行。`natural-acceptance-corroboration.json` 确认：同用户同问题，真实 Episode 运行完成、829 字回答、glm-5.3-flash 实际使用、语义检查通过、内容降级和泄漏命中均为 0；RAG worker 服务计数从 1 到 7。一次样本不证明速度或金融质量提升，相关判官不等于独立金融 QC。

真实 BGE-m3 混合检索冷预热在原 360 秒预算内完成，两次未缓存查询在原 90 秒预算内各返回 6 个 fresh 命中，模型加载一次。索引 `source_dirty=true` 和 legacy CLI 缺少可选 `--receipt` 等能力仍披露；不冒充完整索引新鲜度或任意并发证明。

自然验收整体 `passed=false`：readiness 前后均 503，仅关键项 `market_data_consistency` 失败，市场快照 09-23 / 数据库市场日期 09-22。没有放宽关键检查。

另一次 GLM 独审 `R/name-independent/` 只签 2ddd 目标日保护的有限范围：独立探针 2P、作者 77P 分账、故意错误断言 1F 被检出，报告 PASS_WITH_LIMITS。它不覆盖历史行保护、完整恢复或 eb4，不能移签。

## 数据证据与未关的门

- 80/403 板块仍缺 113 个声明成员位置。`complete-baseline-audit.json` 和 `generation-baseline-audit.json` 只有 49 个历史候选，另 31 个连候选也没有；49 个同样尚未成为经认证的当前身份。
- `saved-sector-payload-shapes.json` 只读核对了 09-03 保存的 403 条 search payload：均是 19 个标量字段，只有 stock_count，没有成员列表，不能补身份。
- `sina-name-window-audit.json` 校验原封存 manifest、receipt 和 70 页 raw。真实捕获窗口为 09-22 02:12:06 至 02:13:11 +08；5564 个身份全部属于当日声明的 5567 范围，缺 301686.SZ、689009.SH、920229.BJ。payload 无名称生效日期，盘前观察不能自动当交易时点名称全集。
- 09-21/22/23 声明范围分别 5565/5567/5568，不升级为官方历史市场全集。停牌留分母、不造 bar、不算平盘。
- 002991.SZ、301004.SZ 除息参考扣减已由具名实施公告闭合，分别 0.6191467 / 0.7832210，对应 09-23 参考前收 37.65 / 33.82，涨跌幅 -0.40% / -2.63%。只签这两个事件，不覆盖全市场复权。
- 09-21 市场缺行、09-22 市场 13 个 NULL，以及逐日 IPO/复牌/公司行动/参考价仍须在不可混日的输入清单中逐项闭合。
- `recovery_members` / `recovery_nontrading` 仍未接入真正的本轮三日 staged 恢复编排。现有双日 Eastmoney/Sina 恢复器不是三日 Hithink 输入的现成入口，不可直接拿来发布。
- L2 三日包只确认存在，未下载、解压、处理。收尾磁盘约 43 GiB 可用，释放不是本会话所为；解压峰值、锁、ledger、处理范围和行一致性尚未完成。不能把压缩包大小当总峰值。

## 生产状态

`R/production-state-final.json`：DB inode `216161353`、size `3855626240`、mtime_ns `1790168645608937291` 与先前基线一致；health200/readiness503；线上仍 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`。这是观察证据，不是未来换库基线；正式执行仍须重新取基线。

本会话三个工程控制器及其 pytest 均已自然退出。独立方自己的 worker/sidecar 已清理。没有停止别人的进程、清理历史失败批次或修改生产指针。

## 下一步与授权边界

已向用户提出一个新增来源授权问题，尚未收到答复：是否允许对一个缺员板块按原历史日期做一次复盘会只读取证。不恢复夜跑，不写生产；未获同意前不执行。若响应日期或成员不完整，仍不能放行；即便一个样本有效，也不是获准批量重启。

先闭合身份与逐日名称/状态/参考价输入，再把恢复参数接进既有 `run_daily_full_staged` 公共入口，补正式编排测试及新组合全门。随后从新生产基线 `clone_to_staging`，通过完整数据门、same-day/cross-day/L2、事务回读、备份与原子换库。最后还需要 readiness 与独立验收通过及合并授权，才能合 main、部署 8792。

## 沉淀盘点

修复和回归已入仓。审查器复用了既有隔离工具，没有新建一套 provider/凭证机制。证据脚本保留在 R：这批历史候选筛选及来源审计依赖本次冻结日期和原件，尚无稳定通用输入合同，未包装成可发布工具，也不作为新生产写入链。

可迁移原则进入共享记忆 `10_knowledge/nullable-classification-must-preserve-unknown.md`：保留未知、按实际依赖拒绝、先于副作用、避免全表旧缺口过度阻断。它不扩张为价格/复权等所有未知都已处理。
