# 2026-09-21 夜跑部署缺口前向收尾

## 范围与授权

用户在昨日工作树/PR只读审计后要求「你来推进」。本轮认领未被其它在途工作覆盖的夜跑装机差距，完成候选、预检和离线验收准备；**不把这句话当合main、生产切换、真实采集或删树授权**。主检出`b4a35fa2c`有他人代码/数据改动，本轮从fetch后的`gitea/main@adcda94b5e401158f1c3aa51f210e1e8d0f0b713`新开`fix/nightly-deploy-closeout-0921`，树`~/fwp-wt-nightly-deploy-closeout-0921`。

归属/回填/收据#812/#813/#814仍由原会话推进；#810与429、Arena、研究线不混入本单。8792另行部署，不用切UI冒充修夜跑。

## 按发现顺序

1. 原夜跑sync=`finance-workspace-sync@6382c13b`，生成=`finance-generation-387028b846a2`，L2=`finance-l2-d433b90788c0`。虽然#795/#796已经进main，装机两份plist和nightly wrapper仍旧。
2. 原sync唯一未提交源码`sync_akshare_index_daily.py`（local禁止复盘会兜底）与最新main逐字一致。旧runlog与quality产物全部留在旧根，未搬走/提交/覆盖。
3. L2的`scripts/moneyflow/**`及`method_validation.py`共18个文件，与候选逐字一致；三个旧root的提交都是当前main祖先，没有需要硬摘入的独有补丁。
4. 新建三个完整固定检出，均为已合main `adcda94b5e40`：`~/.finance-runtime/finance-sync-adcda94b5e40`、`finance-generation-adcda94b5e40`、`finance-l2-adcda94b5e40`。这是待切候选，不是已经装机。源码版本固定，sync既有runlog/quality仍会写进其树，不能宣称运行后整树永久干净。
5. 两份仓内夜跑模板只改代码根键；执行时间、计划local、数据库、用户域、解释器和日志路径保持不变。手动S7入口的同步根默认值同步更新。S7 Python wrapper及底座`finance-s7-sync@418515c0`不变。
6. 原`install_eval_launchd.sh`每次无条件重装6项任务，未知参数也会照装。改为可选`--nightly-only`和无副作用`--dry-run`；未知/矛盾参数早拒绝。窄安装只能更新两个wrapper/两个plist，共享`ops_python.sh`若与装机不同先拒绝，不能借夜跑发布影响另四项任务。
7. 新隔离行为测试首轮156P/1F：macOS `plutil -lint`会接受一个OpenStep普通字符串，语法绿不是合法LaunchAgent。补Label准确匹配与`RunAtLoad=false`语义检查，单独覆盖坏XML、标量配置、错任务和加载即执行。返修安装/接线53P；5个撤保护变异均被捕获。首红见证据`iteration-history.json`，不伪造没保存的全量原始日志。
8. 固定代码`2137345daa44daefa0d029ba4c2de89e0f725b2a`推送并开[#827](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/827)，保持WIP。完整门禁终态见下方收据，不把通过移签给后续文档提交。

## 方案取舍

| 方案 | 选择 | 理由 |
|---|---|---|
| 原地checkout/reset旧sync目录 | 否 | 有他人未提交补丁与运维产物；回退点会丢失，且修改生效过程不清晰 |
| 跟随8792软链 | 否 | UI与采集部署生命周期不同，切UI不代表S7/finalize升级 |
| 把三个代码角色合并一个目录 | 否 | 保持现有隔离与独立回退；候选内容相同不等于以后生命周期必须相同 |
| 新版本目录+仅改根指针 | 是 | 不触旧现场，代码身份固定，配置和运行效果可分别验收 |
| 使用原全量安装器重装6任务 | 否 | 扩大变更范围；选择扩展原入口的窄范围/预览，而非另造部署框架 |
| 同时升级S7 staging底座 | 否 | 非此次缺步骤的根因，扩大换库边界风险；只验证旧wrapper与新schema兼容 |
| 把#810/429候选顺带带上线 | 否 | 未合、独立审查与真实盘后整轮未过；不能用本单吞掉其未完成边界 |

## 固定证据与边界

证据目录：`~/.finance-runtime/reviews/nightly-deploy-closeout-20260921/`。

- `preflight.json`：三根revision/树、18个L2与方法文件一致、旧指数补丁一致、装机6文件哈希、候选plist仅代码根键变动。
- `runtime-targeted.json/xml/stdout.txt`：真正待部署`adcda94b5`上80P，涵盖同花顺接线、禁止local复盘会回退、L2文件链及计划一致。
- `runtime-generation-probe.json`和`runtime-finalize-probe/entry-boundaries.json`：待部署固定根上的7+4项路径/告警/拒绝/receive边界通过；假的数据/外呼替身，不是生产日报。
- `s7-probe/result.json`：当前装机S7 wrapper+原S7底座+新候选schema/db helpers，5个合成小库场景通过：成功后换名并带收据；子进程失败、表缺失、日期倒退、第三方写入均拒绝换名。第三方写入保留，其他失败目标字节不变。**不是完整真实数据库副本演练，更不是302132发布验收**。
- `installer-mutations.json`：删范围、删预览、删共享helper保护、删RunAtLoad/Label检查的5个变异均被测试拒绝；没有改生产脚本或被测源码。
- `gate-qc.json`：固定2137345da作者工程通过：Python12460P/0F/85S/2X（JUnit12547条），Ruff0；前端110P，E2E34P/2S；registry五项0；pre-commit适用项全过。四叶首尾干净且revision/tree不变。**独立审核未执行，不是独立PASS，不签生产效果**。
- `python/run.json`保留汇总器初始exit1：它用行首正则取收据，但pytest把`读数收据`接在`[100%]`之后同一行。测试进程本身exit0；没有重跑。`qc_existing_checks.py`只读原stdout中唯一时间戳路径，与SHA/树/起止时间/12547项JUnit及终端计数逐一核对后形成`gate-qc.json`。零项嵌套pytest的另一时间戳收据未采信，也不读共享latest。
- `python/`、`frontend/`、`registry/`、`boundaries/`保留原始命令、stdout、JUnit、收据和首尾身份；仓内副本见`docs/verification/2026-09-21-nightly-deploy-closeout/manifest.json`。

此次被测main仍用旧收据设施，没借用尚未合入的#814：运行原生`python -m pytest`保存完整stdout/JUnit，仅取**本进程终端打印的唯一时间戳收据**复制与核对，不读共享latest冒充本轮。外部run_checks只编排这次固定对象，不是新门禁权威。S7临时探针绑定装机本地wrapper，作为本次兼容性证据装置封存；常规门禁继续复用仓内测试和两个已有边界探针，不另开第二条采集/部署正门。

## 并发变更与结论时点

15:49复查，8792已被另一会话于15:35切到`adcda94b5e40`；部署账本、软链、health三者一致，source_dirty=false、code_matches_repo=true，readiness=ready。#828随后将部署交接合main，基线前移`f783f19c8`，差异仅新增部署快照/移除#770旧inflight两文档。**本轮不重复切8792、不把他会话部署记成自己的动作**；旧“8792仍945c”已失效。本轮固定收据只签2137345da，不签后来的main合流。

夜跑2份plist、3个wrapper/helper加S7 wrapper共6个装机文件哈希仍原样，loaded环境仍旧根，sync runs=3/finalize runs=4不变。`production-unchanged.json`的名字只表示本轮未执行部署，正文如实记录8792已经由别人改变。

## 下一步：需要另行授权的发布窗口

1. 固定#827最终对象，确认独立审核要求；文档尖变动不移签旧代码收据。合main须用户确认、最新合流所有叶子绿。
2. 发布前重新核对`preflight.json`中装机文件哈希；有变化先协调，不能旧备份覆盖新会话。确认两个job不运行、夜跑锁空闲、新根身份和关键文件未变；检查磁盘及数据库状态。
3. 对2份plist+2个wrapper留原样备份，记录权限/哈希；按原子落盘及失败回退规程安装。`--nightly-only --dry-run`只预览；未批准前不运行非dry安装。`--kickstart`不包含在窄安装默认行为里。安装器目前不提供跨两job的事务/自动回滚，失败按备份逐项恢复再bootstrap，不能宣称自动回退。
4. 重载后用`launchctl print`逐键核对生效值，不只看磁盘plist。8792和另四任务应保持不变。
5. 真实采集另授权、只按当日和已有staging正门执行；同花顺latest-only不填历史日期。看模块收据、最大日期、目标日行数和关键行情非空值；零凭证可skip不等于恢复。盘后数据/报告/L2/生成门全验后才报生产恢复。
6. #810观察值、429真实重试样本、研究线语义验收、归属回填/Arena不由本单结案。旧sync/gen/L2根和证据树保留，未授权删除。
