# 同花顺研究数据：复核返修与证据交接

## 范围与授权

只延续本分支同花顺任务，不代做其他分支的K3。用户最新边界是可逆工程、测试、文档；暂停合main、部署、付费外审、删除生产数据和触发live同步。此前部署准备不代表当前授权。PR [#810](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/810)保持WIP/open。

本轮是作者在独占固定检出上的复算与代码复核，**不是第二位审查者的独立Spec/Quality签字**。没有启动收费评审，也不借其他PR的K3结论。代码基座728f3271，业务06047324，历史恢复返修e98e8791，最新代码164b02e4c4d4afbb2e28930fd7ac275f1322742d已推送。

## 发现与返修

### 历史恢复误用latest-only步骤

首轮干净347b987c全量为11954P/1F/85S/2X。唯一失败是`tests/test_recovery_refresh_integration.py::test_successful_leaves_write_current_run_only`，原断言8次而实得10次。

`recover_local_review.child`对两个历史日期复用local计划，新增研究步骤也被执行；有key时会触发采集器的过去日期拒绝，阻断恢复。原集成测试将数据叶子替成stub，先暴露计数而非实际异常。

| 方案 | 裁定与理由 |
|---|---|
| 只把8改10 | 否：把真实历史路径回归洗绿 |
| 放宽latest-only日期门 | 否：今天异动/估值不能冒充过去观察值 |
| 恢复时自动取热度history-only | 否：恢复已有行情不等于授权扩大采样，股票范围和请求量须显式选择 |
| 历史恢复显式skip并留原因 | 采用：不进入研究执行函数；当日日更保留第五步 |

修复e98e8791保留四个已有同花顺历史步骤、必需步骤失败传播及staging门；新增有key/无key两针，检查两日`skip / latest-only excluded / 未更新`收据。新针修复前2F、修复后相关97P。97P属于迭代脏树，不冒充干净候选收据。

搜索了`HITHINK_STEPS`、`build_plan`、`build_local_plan`及动态加载调用点。代码地图构建超时后仍stale；结论依据具体源码，不借失鲜地图作全仓架构断言。daily-full含latest-only来源，历史缺口仍走专门恢复/回填协议。

### 共用写入守卫漏认硬链接

复核发现既有`write_path.is_canonical_production`仅比较解析路径：硬链接是同一文件的不同名字，`resolve()`不能区分它与独立副本。研究写者虽复用该守卫，仍可能绕过“不得直写canonical”承诺。

仅用临时假文件复现：旧守卫硬链接针红，研究采集入口继续到被设为必失败的凭证检查；符号链接/独立拷贝控制为绿。没有对真实生产文件建链接或试写。

164b02e4在共用守卫比较设备/文件身份，不另造研究专用实现。不存在的普通staging可创建，独立拷贝不误拦；权限等身份读取错误传播为失败，不解释为非生产。增加硬链接、符号链接、拷贝、三处身份异常及采集前拒绝测试，连研究/恢复/staging相关153P。它不是权限沙箱，不承诺抵抗检查后的并发路径替换。

合同同时澄清：估值value_rows是至少一个指标有值的行数，个别指标NULL时整行仍可能ok；NULL不补零。热度不按窗口天数补齐缺日，行数或ok不能证明逐字段完整。

## 验证与收据

统一解释器为主树`.venv-workbench/bin/python`，完整门使用清空个人launcher变量的环境、umask022、独占固定检出。所有旧原件保留，不跨SHA移签。

| 身份/范围 | 结果 | 证据 |
|---|---|---|
| 347b987c首轮全量 | 11954P/1F/85S/2X；历史恢复真回归 | `~/.finance-runtime/hithink-research-release-20260921/python-checks/` |
| e98e8791首次补跑 | 外层1500秒截止，约93%，exit124；进度有1F，无最终完整失败报告 | `~/.finance-runtime/hithink-research-recheck-20260921/python-checks/` |
| e98e8791完整补跑 | 11957P/85S/2X，原生exit_status=0 | `~/.finance-runtime/hithink-research-complete-20260921/receipt.json` |
| 硬链接返修迭代 | 旧版2F/2P；返修相关153P | 同上目录`hardlink-red.log`、`hardlink-focused.log` |
| 164b02e4完整Python | **11964P/85S/2X**；17条既有数值/弃用警告；exit0 | `~/.finance-runtime/hithink-research-guard-20260921/receipt.json`、`pytest.log.txt` |
| 164b02e4前端 | lint/typecheck/build通过；8文件110P；E2E34P/2S | 同上目录`frontend-receipt/frontend.json`及六份日志 |
| 164b02e4Ruff/注册/台账 | 全部exit0，首尾身份稳定 | 同上目录`registry-checks/status.json` |

最新原生收据：`~/.finance-runtime/test-receipts/20260920T195746Z-164b02e4.json`。解释器/依赖门未绕过、dirty=false、完整目标为独占检出；`check_test_receipt.py --expect-revision 164b02e4c4d4afbb2e28930fd7ac275f1322742d --base-drift-max 5`通过。fetch后基座仍728f3271。85项跳过不等于所有路径已覆盖。

首次补跑的收集器曾匹配到同SHA、零执行的JSON；现有收据检查器明确拒绝，不能拿exit0洗成全量。证据`hithink-research-recheck-20260921/zero-receipt-rejected.log`。后续收集器改绑定本进程终端实际输出的收据，并核执行数/退出码。另一次定向命令曾拼错测试文件名、exit4零执行，原日志`hardlink-green.log`保留但不采信；153P在独立的`hardlink-focused.log`。

本交接是代码提交之后的文档，不把164b02e4收据移签成后续文档tip或main。将来合入前仍须对实际候选tip重验。

## RAG诊断边界

中止补跑的1F按相同收集顺序定位到`test_warm_worker_survives_first_timeout_and_drains_the_late_response`；缺最终堆栈，不能据此确定根因。该用例单跑通过，RAG源码/测试在本PR无改动，之后完整套件通过也不抹掉这个观察。

额外假进程反例：20ms预算、子进程sleep200ms，正常约22.9ms放弃；在flush后人为停顿350ms，约361.6ms仍返回结果，表明计时起点在发送之后。它证明一个受控边界，不证明原全量失败必由此造成。未改RAG生产逻辑，留给其owner另核请求预算合同。

证据：`~/.finance-runtime/hithink-research-complete-20260921/check_rag_dispatch_timing.py`及`rag-dispatch-timing.json`。源文件SHA256为`fd800dbb9a8d221489ef5db98c953340bbd8f91b7a1aba35a80624e61e3bf9ef`；脚本固定e98e8791检出，清理检出后复现须先恢复该固定版本。

## 实采存档与运行侧

最新164b02e4再次用真实FinanceQuery只读消费先前官方两股样本：估值2行/2证据、热度10点/10证据、异动0行/0证据，非空证据的信息日均09-21；截止09-20时历史热度不可见。早先删去采集日截止的反事实为0→8→0行，代码配置已恢复。

本轮复算无新外呼，样本SHA256前后均`28539a935c069df1ae45135f2241864603ad807e1e19dff719614ed8388a83f3`。原`/tmp/hithink-research-acceptance-20260921.duckdb`已另复制同哈希备份至`~/.finance-runtime/hithink-research-guard-20260921/samples/`，不提交二进制。`archived-sample.json`与旧`archived-cutoff-mutation.json`为证据。它不是新采样、自然模型回答或非空异动正文验收。

只读巡检`audit-after.json`仍报gaps/exit2：loaded同步根`finance-workspace-sync@6382c13b`、plan=local、not running、runs3/last exit0；源码缺同花顺步骤，六张检查表最大日09-08、09-18零行。配置/声明/行数不是实际执行或字段完整证明，loaded另见`loaded-sync.txt`。

旧树未提交指数修补与候选对应文件字节一致，不能reset/覆盖；其余运行产物亦未改。本轮未改plist、重载launchd、触发同步、切8792/生成/L2或换生产库。早先部署草稿未执行，已加无条件退出并删旧pyc，不作为上线入口。前端检出在检查结束、身份核验后清理，测试端口19181/19184无监听；只清本轮临时物，证据保留。

## 接手与工具归位

1. 独立审查者从合同、164b02e4代码diff和原始收据自主复核，不用作者总结代签Spec/Quality；本轮未启动收费调用。
2. 非空异动正文、自然Workbench问答、盘后staging正式发布及生产新鲜度尚未验。当前不执行发布；合并/部署须另获明确授权。
3. 历史热度走显式history-only，异动/当前估值不伪造历史；财务、基金、商品后续批次不在此轮扩张。
4. 正向回归归仓；复用原生收据、前端门、注册审计。证据目录脚本只是固定候选/样本的验收recipe，不新立通用CI或生产入口。文件身份原则补入agent-memory既有`atomic-name-claim-is-not-complete-publication`；未动他人脏harness-reference。
