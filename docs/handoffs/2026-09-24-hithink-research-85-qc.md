# #85 续推：同 SHA 门禁与 K3 双轴复审

## 身份与结论

PR **#894** 保持 WIP，承接 #810；两张 PR 均未关闭，未合入、未部署。本快照续接 `2026-09-23-hithink-research-observations-85.md`，不覆盖旧快照。

- 本轮冻结候选：`62777a76d7812bf5eebe070892e5977b2aa93003`，已推 `gitea/fix/hithink-research-85`。
- 编码基线：`c9dd71dfd678855b61662100ec74625b92ad1f1b`。收尾 main 为 `5bf47a5ae9aa16768c0ef2df614177253764aeb6`，只新增 #901 文档合并；收据校验漂移 1 ≤ 5，merge-tree 无冲突。
- 正式门禁树：`~/.finance-runtime/reviews/hithink-research-85-20260923/continue-03/candidate/finance-workspace-private`；独审使用同根 `qc/candidate/finance-workspace-private`，两棵均为独占 detached 树。
- Python、frontend、E2E、registry 及 Spec/Quality 都绑定上述候选，不绑定后续文档 tip。文档回写不产生一张新的全量收据；合入仍需用户确认，并按最终 PR tip 核对门禁。
- Spec 与 Quality 均 **PASS_WITH_LIMITS**。Quality 前轮 M1 经独立复核撤销；不是作者自行豁免。

## 按发生顺序

1. 资源恢复后，旧 `a84c49920` 的完整 Python 最终正常完成：14719P/0F/0E，85S/2X。曾发出的 INT 没有使这张最终收据中断，不能把它重写成失败。
2. main 前进超过漂移限额且涉及共同入口，前向至 c9dd71dfd，冻结 `09b437c2f`。该候选四叶通过（Python14928P），Spec17P；Quality8P却给 CHANGES_REQUIRED，原报告保留在 continue-02。
3. 唯一中等级 M1 认为：4001×3 → 429×1 → URLError 后必须改记限流并继续。原始 C2 明确禁止普通网络错误被重分类，C3 只允许“类型化429耗尽”转 partial。作者没有修改实现以迎合该解释，新增4项回归并提交62777a76d，再冻结重验。
4. K3 新轮用受控单调时钟，比较有/无429以及真正的429时间/次数耗尽。实际触发的是普通次数界；限流计数1<10，等待累计6.4s<300s。Quality 正式撤销 M1，认定“出现429后永久接管请求”没有合同依据。
5. 62777a76d 完整门禁与两轴复审收齐后才回写本快照。旧轮、首红、阳性对照、沙箱阻断和撤销前报告均未覆盖。

## 决策与被否方案

| 方案 | 裁定与原因 |
|---|---|
| 只按真正导致停止的条件分类 | 采用。429额度耗尽才为HithinkRateLimitError；普通次数先耗尽仍为HithinkAPIError，不因过程里出现过429而改变身份。 |
| 按前轮M1把后续普通错误一并记限流 | 否。违反审查前已存在的C2/C3；不能以一次异常可复现代替合同依据。新增回归锁住边界，业务实现未变。 |
| 作者自行把CHANGES_REQUIRED改成PASS | 否。保留原报告和原合同，回应标明作者意见，再由K3独立裁决；两组互不读取对方结论。 |
| 用旧SHA的绿结果覆盖新增测试后的候选 | 否。62777a76d重新跑四叶和六个独立阶段；前轮数据仅作历史。 |
| 为沙箱放宽源码、凭据或网络权限 | 否。作者测试收集被拒就记blocked；独立探针在WORK设pytest.ini。宿主正常入口的94P和完整门禁另账，不冒充审查者执行。 |

## 收据与验证

以下路径均相对 `~/.finance-runtime/reviews/hithink-research-85-20260923/continue-03/`。

| 范围 | 实测结果 | 原件 |
|---|---|---|
| Python + Ruff | **14932P/0F/0E/85S/2X**，17 warnings；collected=15019，无收窄；dirty=false、exit_status=0。Ruff通过。 | `python-gate.log`、`receipts/gate-ODgFHGso/pytest.json` |
| 收据身份 | 正确SHA、解释器、依赖指纹、完整收集面、漂移1均通过；故意给旧09b437c2f期望SHA时exit1。 | `receipt-check.log`、`receipt-wrong-sha.log` |
| 前端/E2E | install/lint/typecheck/test/build/E2E六步exit0；120P，E2E34P/2S；首尾同SHA、干净。 | `frontend/frontend.json`及六份日志 |
| registry五项 | check、parseability、tables、views、ledger均exit0；本仓绑定候选树，邻仓从/Users/a77解析，非跳过跨仓；反向98条warning单列。 | `registry-*.log` |
| 作者定向 | 正常入口三文件94P；没有收集忽略钩子，不搬迁作者测试。 | `author-targeted.log` |
| 429变异 | 进程内禁用429重试：2F；恢复新进程：2P。源码未改。 | `429-control-{red,restored}.{log,xml}` |
| 混合错误变异 | 进程内把普通API错误全部改判限流：3F；恢复后加编排保护共4P。 | `mixed-error-control-{red,restored}.{log,xml}` |
| Spec | PASS_WITH_LIMITS；独立execute **23P/0F/0E**；人为assert1==2单列1F/exit1；探针前后SHA256一致。 | `qc/report-spec/`；execute命令007/008 |
| Quality | PASS_WITH_LIMITS；独立execute **17P/0F/0E**；人为阳性1F/exit1；M1撤销；探针前后SHA256一致。 | `qc/report-quality/`；execute命令008/009 |
| 生产只读回读 | 8792仍为3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4、source_dirty=false、code_matches_repo=true。不是627候选。 | `health-readback.json` |

两轴各自 explore/execute/report 是六个独立会话，按轴串行。均使用 `mirasim-kimi/kimi-k3`、xhigh、18788订阅网关；本轮54请求，另网关往返2请求，自动重试0、无模型回退。六阶段输入哈希、候选及作者首尾身份均稳定。网关小探针与沙箱预检先通过；工具无凭据、禁网、源码只读，只有WORK可写。

归仓原件见 `docs/verification/2026-09-24-hithink-research-85/README.md`。外部原件哈希在 `SHA256SUMS`，已逐项校验；阶段execution.json另含命令/输出哈希。`STAGE_COMPLETE`只表示阶段交付与身份检查，不是质量判定。

## 限制与保留项

- 两个explore都违反“不跑测试”的阶段约定提前试跑。原件和偏差已披露；最终统计仅计各自独立execute一次，不把两次读数相加。阶段纪律目前仍非机械执行权限隔离。
- 两组审查者的作者测试都被源树 `.agents` 元数据权限阻断，0项执行，记blocked而非通过。没有采用前轮Spec的忽略PermissionError收集钩子。宿主94P及14932P补的是作者门禁证据，不改变审查者执行事实。
- Quality F2是基线已有的顶层JSON数组触发AttributeError；不是本轮回归。F4确认未知文件身份抛PermissionError、阻止写入，符合C5，未发现明确合同被破坏。F3“空估值无total”上游可达性未证，继续not_verified，不放宽校验。
- Spec对finance_query只读机制、恢复脚本部分范围为静态核查；Quality没有动态压C4所有入口，详见两份原报告，不宣称穷举全路径。
- 默认每请求时间预算不承诺覆盖真实7至9分钟限流；次数界也独立生效，单独调大秒数不等于延长真实恢复窗口。在途读取不是强制墙钟截止。
- 没有live sync、真实供应商采集、生产写入或删除、launchd重载、8792切换、sync/L2根变更。只读health不证明真实限流恢复、生产数据新鲜度或夜跑恢复。

## 交接与工具盘点

业务回归已归仓；复用既有门禁和#75/RE06审查装置，参数适配、原始脚本和哈希留在证据根。独立探针以`.py.txt`原样封存，不改成作者测试后重复计数。语义裁决方法进入agent-memory的 `reproduced-behavior-is-not-contract-violation.md`，并补入重试预算知识卡；它需要核对合同语义，不以字符串规则冒充自动判官。阶段权限问题留给#75通用装置收敛，不在本金融补丁里顺带扩大执行器。

合并等用户确认；#810接替关闭也须留指针，不静默关闭。若最终PR tip、实现或main基座改变，按实际身份重验，不移签。部署命令仍仅见09-23快照中的授权草稿，本轮没有执行，部署须另立单。
