# 2026-09-21 H-01 控制边界局部返修

## 身份与结论

- WIP [#845](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/845)：`fix/history-forward-boundary-0921@d91aff9d8437fe903f3e643b65d4805aa4cf243c`，本地/远端一致；父#833=`7edfe24e76afbd5c365fbf97dd2414847b086f88`不移动。
- H-01受保护文本控制权的受测路径已修。历史整体仍 **CHANGES_REQUIRED**：合法省略续问丢local_only的H-02在正常版仍2F。局部编号不是新工单。
- 集中证据/交接留在#838；无新独立报告，不把操作员检查称Spec/Quality。没有合main、8792部署、夜跑装机、生产回填、删树或再次模型审核。

## 背景与取舍

旧材料编译器挡住引用，但历史helper和普通追问回填另读raw query，能在controller恢复历史意图；截止投影也有独立消费者。共享`top_level_message_text`复用既有来源分区，所有这些消费者同源；TaskFrame仍保raw_question供分析。不改完整引号解析器，不增加第二份规则，不清空合法历史。

明确续问保Jan1-Sep15窗口、Sep10信息截止及本地上限；取消/新任务/纯材料不受旧授权污染。不继承history不是必须禁所有新研究，独立新任务仍可有自己的研究能力。合法本地能力来自正式LOCAL_READ_CAPABILITIES，包含mainline_context，不能测试里抄窄名单。

新41例通过controller、TaskFrame往返、control投影、Episode合同和history工具登记；没有执行工具。socket/DuckDB连接不仅抛异常，还记尝试并在teardown核零，防异常被吞制造假绿。常规回归含临时数据库，并不宣称所有530例零DB。

H-02是另一种失败形状：`那它们见顶后谁接力？`和`以前有没有类似，失败案例也看看`合法保历史意图与截止，却丢材料合同，允许web_search/web_fetch。须同步继承可信用户权限边界，不能从助手消息恢复，也不能无条件复制上一合同。本次先封局部修复和反例，不把它们掩成完成。

## 固定提交实测

| 检查 | 结果与边界 |
|---|---|
| 新边界例 | 41P，包含于下面193P，不重复相加 |
| history/controller回归 | 168P，6.06秒 |
| material/honesty回归 | 169P，2.28秒 |
| history/assembly回归 | 193P，6.77秒 |
| 全仓Ruff / diff-check | 各exit0 |
| 五单点变异 | partition 24F、infer 15F、follow-up 6F、resolution-hint 1F、cutoff 4F；各总41例、0 errors |
| 正常版H-02 | 2F，0.48秒；未修，不是变异预期红 |

三组共530P；每条命令有120秒上限，禁自动latest收据写入。冻结六次量具均before==after，head/status/六文件哈希一致；三组收据核前后clean同SHA。未跑该SHA完整Python/前端/E2E/registry合入门禁，旧#833作者全量不移签。

## 失败原件与勘误

首替身少relation_path，首次白名单漏mainline_context；均修测试夹具，没有放宽生产限制。一次路径误写旧#833已只撤自身变更并核clean。39例单撤resolution保护仍绿，新增直接raw-resolution正反例后41例击中该变异1F。

量具首版用patch.object恢复__code__触TypeError；pytest有红不够，不认有效变异收据。v2保存original_code、finally直接还原、每mode独立basetemp；五个dirty-v2及六个frozen另留原件。首错traceback仅会话记录，不编造日志；旧pytest输出与首版脚本保留。进程内变异未改磁盘源码。

## 证据和下一步

新包：[README](../verification/2026-09-21-research-tail-forward/history-boundary-repair-01/README.md)，45个manifest成员，收据/日志/失败量具/候选patch；不收tmp和缓存。旧281/28/38三包保持字节。Git提交级完整性另用`scripts/check_evidence_archive.py`核验，发布锚点以归档后记录为准。

下一步修H-02并以新SHA验真实消费者；历史自然四题not_passed、独立终审、与新main/三领域/#841组合仍未验。runtime/财务本轮不启动，共享provider容量失败后既定串行计划仍停。#814归正式收据负责人，不拿c35诊断或中断全量替签。
