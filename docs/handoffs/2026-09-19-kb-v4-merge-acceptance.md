# 双索引 v4 两仓合并验收：代码已合，生产未切

## 结论与授权

用户回复“允许”后，按**两仓新增修复进入合并验收**执行；不扩大为部署、解锁或恢复维护授权。
2026-09-19（UTC+8）仅处理以下两张代码 PR，未合其他在途任务：

| 仓库 | PR | 合前 main | 已验且已合入的完整提交 |
|---|---|---|---|
| 金融 | [#786](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/786) | `d32b8966237e1b8241dd5377e9a9a659423e212b` | `2b4948a4015e53fd1fde5bb1e50147582abde2da` |
| KB | [#153](http://127.0.0.1:3300/a77/knowledge-base-private/pulls/153) | `91725ea9ba0252a43665f9e3130142f946c289ae` | `c141a424a16faed2cc959c0839e6b0ea29ced481` |

Gitea API 以 `fast-forward-only`（只快进，不造另一份代码身份）合并，PR 均为 merged。
合并前、合并后各一轮完整工程门禁通过，合后再 fetch 并严格核收据与实际 main 全 SHA 相等。
本页及归档是随后的文档交付，不把上述收据冒充文档新 HEAD 的全量测试。

**8792 仍为 `bf662e9310ff751a4c31763815ee78fb7d6d5122`，未重启、未换运行链接。**
生产双索引两个目录和 24 文件的防写、三个 post-* maintenance-skip 保留。
长期受保护维护链仍未实现，14 页历史冲突仍隔离，未认证答案质量。

## 按发现顺序

1. 核工作树和最新 Gitea main。共享金融主树有他人在途文件，KB 共享正文有既有变动；不认领、
   暂存、清理或切分支。在新操作根下创建一对标准仓名的干净 detached 检出，固定上述完整 SHA。
   建树使用命令级安全 hooksPath，原 pre-commit 逐字节保留，不恢复旧写索引钩子。
2. 两仓本机 `merge-tree` 无冲突、均满足祖先快进条件。金融相对旧99只有286个文档/教训路径；
   KB 相对23b只有两份交接，但仍按本轮新 SHA 完整重验，不借旧收据代签。
   复用的五个 fixture 文件与672abcc5逐字节相同，没有带入该分支的历史研究产品功能。
3. `env -i`、umask022 启动前置门禁，金融venv跑Python，明确配对KB根和独立遥测路径。
   前端构建不改变跟踪文件；四叶及KB守卫全绿后，才在PR留言精确读数并允许合并。
4. Gitea仓设置允许仅快进；现有CLI未暴露此选项，现场脚本复用其凭据/API实现，额外核固定head、
   base、绿叶和收据，再请求 `head_commit_id` + `fast-forward-only`。未改仓设置、未强推或手工补标。
   先KB #153、后金融 #786，远端 main 与被测 SHA 全等。
5. 合后重新 fetch，在同一干净固定检出重跑全部门禁。并另开只读窗口核生产保护与资料，
   用合后最终SHA重新跑真实双索引消费者；不把候选99的真实检索结论直接搬给新提交。
6. 合后后端全量结束后核精确收据、实际远端main、目标根、依赖、构建后清洁性；归档原始字节。
   旧生产漂移、v3缺页、d95 E2E红、e9脏构建、058线程污染及消费者R1/R2/R3错误判据均保留。

本轮是**同一执行会话在隔离检出复验**，不是独立 agent 审查或新自然模型质量验收。

## 工程收据

操作根 `OP=$HOME/.finance-runtime/kb-v4-merge-20260919`；固定树为
`OP/pre/{finance-workspace-private,knowledge-base-private}`。`pre` 是目录名，不表示合后仍验旧代码。
两仓HEAD在前后两轮均固定不变，合后另核远端main身份。

| 叶子 | 合前 | 合后 |
|---|---:|---:|
| 金融 pytest | 11,491P / 0F / 73S / 2xf；17 warnings | 同左 |
| 前端测试 | 110P / 8文件 | 同左 |
| E2E（真实浏览器端到端测试） | 34P / 2S | 同左 |
| KB pytest（tests + skills/lib/rag/tests） | 837P / 0F；1 warning | 同左 |
| Ruff、registry五项、前端安装/lint/typecheck/build | 全exit0 | 全exit0 |
| KB relations/sizes/quality/log/index | 全exit0 | 全exit0 |
| all.exit / 两棵固定树 | 0 / 干净 | 0 / 干净 |

金融测试解释器 `$HOME/finance-workspace-private/.venv-workbench/bin/python`，Python3.12.13，
依赖指纹 `3328bed61f3e21ea`。两份收据均dirty=false、全树0脏、未绕依赖门禁：

- 合前：`$HOME/.finance-runtime/test-receipts/20260918T171255Z-2b4948a4.json`，866.26秒。
- 合后：`$HOME/.finance-runtime/test-receipts/20260918T174518Z-2b4948a4.json`，1364.39秒。
- `check_test_receipt.py <精确收据> --expect-revision <完整2b SHA> --require-target <固定树>
  --base-drift-max 0` 两份均exit0；合后结束时间2026-09-18T17:45:18Z。
- 前端隔离端口18971/18974；没有占用或切换8792。KB守卫17:46:12Z完成。

只报告本窗耗时，不从一次前后差异推断性能改善/退化，也没有加长超时、删断言或重跑碰绿。
原始pytest文本含2个xfailed，JSON counts不列此字段，不读成“没有xfailed”。

## 最终提交真实消费者与只读窗口

`consumer-post-merge/summary.json`（17:26:04Z）绑定金融2b与KBc141：两索引14个服务用例通过，
另有全文直接CLI命中恢复的 `raw/毫米波雷达-演讲稿.md`。实际BGE-M3查询子进程用KB `.rag_venv`，
不换模型、排序、预算或过滤。先核候选资格与token交集，合法空结果按空回执验。

- 显式代码/wiki/普通/全文根覆盖故意错误ambient根；要求fresh，核实际过滤封套及作用域。
- 有过滤请求实际走CLI，不冒称热worker；无过滤hybrid在两份常驻worker各连续查两次，
  PID、代码身份、模型加载一次与查询计数增量均核对。换资料根不得复用原worker。
- PID91084/93344已关闭且ps证实不存在；索引前后所有文件SHA一致。
- 全文L3“液冷”的前三项只因“液”单字posting命中，**不能当液冷证据或相关性通过**。

`readonly-after-merge/`（17:21:13Z）新窗口：26项flags/device/inode符合原日记，24文件SHA未变，
无truncate/create的写意图打开均被拒。冻结21,819文件新增/删除/变化0；实时同数量，仅
`wiki/relations/access_log.jsonl`变动。8792 healthy、源码干净且匹配旧bf662e93。
这是该时点观察，不是永久新鲜度证明，也不证明长期写者维护已安全。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 干净固定检出验精确SHA | 主共享脏树跑全套或直接拉main | 避免混入他人修改及共享hook副作用 |
| 仅快进并固定head | 普通merge新提交却沿用分支收据 | 被验身份与交付身份相同，base不满足即停止 |
| 合后重验并严格核远端 | 用旧99/23b或全机latest代签 | 新文档HEAD仍是新身份；测试范围和目标不能猜 |
| 独立记录检索接线与相关性 | 命中非空即算研究质量通过 | 合格posting不等于回答题意，过滤合法空也可能正确 |
| 代码合入与生产切换分开 | 合完顺手解除防写/恢复旧hook | 长期维护链尚未实现，源变动后仍需重新验鲜和回滚准备 |

## 归档与边界

原件：[`../verification/2026-09-19-kb-v4-merge/`](../verification/2026-09-19-kb-v4-merge/)，
164份哈希条目，另有SHA256SUMS本身；清单与实际文件集合闭合、无symlink替代。
含两轮门禁、两份精确收据、Gitea结果、消费者/现场输出与惰性脚本文本。
索引、raw、完整源清单、访问遥测和模型缓存不入Git。

复用既有secret-pattern扫描，2个命中人工核为 `HF_HUB_OFFLINE` 与
`intelligence.services.kb_code_identity` 代码标识符；不是全面秘密审计。
原始日志的行尾空白原样保存：金融全归档 `git diff --cached --check` exit2，手写文档exit0；
KB文档exit0。不改字节/哈希求格式绿，原pre-commit照常执行。
归档与本页不能为未来文档提交代签工程全量；后续文档PR的收据独立登记。

## 接手与禁止事项

原代码分支inflight随本页转档；**不要再把“等待合并确认”当阻塞**，但部署仍被以下事项阻断：

1. 实现并故障注入验证[受保护维护方案](2026-09-18-kb-guarded-maintenance-plan.md)：
   覆盖hook/ingest/手动build/update/fetch/publish；只写新代，双份验收后同一manifest发布。
   第二份失败、半写、崩溃、遗留锁、换链、源漂移、旧worker及远端失败都应保旧代可读。
2. 部署前按届时最新main、实际资料与发布包重验，不把本次staging临时路径当长期发布合同。
   获得生产操作授权后才准备启动器/运行链接/台账备份，受控切换与回滚；另验真实Workbench
   Episode入口、readiness与双索引热worker。答案质量/rerank/生产时延未签。
3. 不递归清uchg、不恢复旧无保护hook、不覆盖远端旧资产、不改raw或代解14页冲突。
   必要解除仅走旧OP的日记绑定恢复器，前提是维护/切换方案已经验收。
4. 没有本轮gate/consumer后台任务需等待，未安装自动提升/解锁/上线任务。

工具沉淀：复用已有收据检查器、Gitea凭据/API、既有消费者判据与只读检查；现场脚本固定两张PR
和路径，归档为可复核样本，不伪装成通用维护服务。未发明并行parser、测试框架或长期锁。
本窗没有新通用机制需要改harness-reference；其BUILD.md仍有他人在途修改，未认领。
