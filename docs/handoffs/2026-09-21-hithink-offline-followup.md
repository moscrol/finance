# 同花顺续轮：订阅额度阻塞与离线证据链补强

## 授权与派发结果

用户在“仅使用现有ChatGPT订阅、不走K3计费API、不加购额度”的方案后要求继续。合main、部署、live同步及生产数据修改仍暂停。

2026-09-21北京时间04:51，仅通过Codex app-server执行账号/额度元数据读取，没有初始化模型审查会话：

- 登录类型为chatgpt；`ordinaryUsageAllowed=false`。
- 周窗口已用100%，`credits.hasCredits=false`、余额0。
- 服务返回`resetsAt=1790442405`，即北京时间2026-09-27 01:06:45。此时间不是保证届时可用的预约。
- 两个预先建立的164b02e4 detached审查树均未启动模型、未修改文件，已用非force worktree remove清理。没有切换账号/计费API、购买额度或设置自动重试。

原始元数据仅在本机证据目录保留，文档不收录账号标识或凭证：
`~/.finance-runtime/hithink-independent-20260921-fNTsHb/account-preflight.json`
SHA256：`0084c5ef4077986945ea5bcffd4f275e7596173f2f3d617d1220f205d20325cb`。

因此独立Spec/Quality为**未执行，额度阻塞**，不是PASS、FAIL或K3裁决。额度探针仅是当前快照，不预占额度，也不是通用付费上限控制器；下一次派发前必须重新核对普通订阅请求是否允许，不能仅凭登录成功或旧快照启动。

## 离线补强

用户继续要求推进后，检查了采集器、三份查询定义、证据生成和既有测试。现有测试已覆盖数值读回，但未断言异动正文/关键词/请求ID的完整消费；NULL消费及重采后的旧截止也可补强。

提交`eebf4e895a81f7122e3afb32979743bacd6c8cd6`仅修改`tests/test_hithink_research.py`：

1. 合成非空异动经实际采集器、DuckDB、FinanceQuery后，正文、带引号关键词、请求收据ID进入查询结果及证据；保留供应商解释标记和L4层级。
2. 估值NULL在查询结果仍为NULL，不生成虚构的结构化数值observations。
3. 次日重采历史热度覆盖采集日期后，昨日截止看不到被覆盖的旧版本；新截止可见，事实不重复增行，两次请求收据保留。

没有改运行时代码；`git diff 164b02e4 eebf4e895 -- market_feature_store intelligence scripts`为空。合成正文不是供应商真实样本，也不证明自然Workbench回答或模型提示注入防护通过。

| 方案 | 决定与理由 |
|---|---|
| 改用计费API或追加额度 | 否：超出授权 |
| 把作者复测称为独立审查 | 否：验收主体不同 |
| 重复原全量测试代替独立签字 | 否：不能解除独立审查阻塞 |
| 补强尚未直接断言的消费合同 | 采用：零模型调用、无供应商外呼，回归归仓 |
| 修改生产或伪造非空真实异动 | 否：越过授权和证据边界 |

## 验证与原件

所有新证据位于`~/.finance-runtime/hithink-independent-20260921-fNTsHb/`。

- 迭代树：同花顺文件39 passed；只用于作者迭代，不是干净SHA收据。
- 三次进程内变异：正文丢失、查询NULL转0、重采保留旧采集日期。各执行1项，均在目标断言失败；源码文件不修改。分别见`mutation-drop-text.log`、`mutation-null-to-zero.log`、`mutation-stale-capture-date.log`。
- 注意：三个并行pytest在同秒、同SHA下打印了同一个原生收据路径，文件被覆盖，不能给三次运行分别签字。只采信各自原始终端日志及实际失败断言；不要把那个共用JSON当作三个独立原件。收据基础设施已有另案#814，本分支未夹带全局conftest改动。
- 干净固定`eebf4e895`：11个相关测试文件**250 passed、8 skipped**，全仓Ruff通过，前后HEAD与status一致。原生收据`~/.finance-runtime/test-receipts/20260920T211530Z-eebf4e89.json`已复制为`targeted-receipt.json`；`targeted-status.json`核对SHA、解释器、测试目标、退出码和执行数。
- 本轮没有重新跑全量Python或前端。旧11964P/85S/2X及前端收据仍只签164b02e4，不能移签到eebf4e895或后续文档tip。

`mutation_probe.py`和`run_targeted.py`是绑定本次固定候选的复算recipe，不是新CI/生产入口；正向回归已归仓。账号探针只执行一次，实验API和费用语义没有足够样本，未包装成通用工具或改共享harness。

## 接手条件

- PR #810保持WIP/open。新的文档提交不重新签署测试SHA。
- 旧Spec/Quality任务单仍固定164b02e4运行时代码，可补读`164b02e4..eebf4e895`的测试增量；若审查目标改为新tip，须在派发任务和报告中一致点名，不迁移旧结论。
- 下一轮额度可用后才派发隔离审查，不自动跨账号/换API/充值；两份报告不得互读。
- 非空真实异动、自然Workbench回答、正式staging发布及生产恢复仍未验。旧部署树的指数修补和运行产物不得reset/覆盖；8792、L2、launchd、生产库本轮未改。
- 实际合入候选tip仍须独立审查和完整门禁，发布另需用户授权。本轮没有重新审计生产新鲜度，沿用的09-08停更描述属于前轮只读快照。
