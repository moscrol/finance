# #83 / PR813: main1751 整合与独审交付阻塞

## 当前结论

**ENGINEERING_PASS_QC_BLOCKED_SANDBOX_IDENTITY_AND_DELIVERY**。尚不具备合入批准条件。新候选已快进推至 PR813 head，保持 open/WIP/unmerged；没有合 main、没有生产回填，没有重启8792或修改launchd。

- 产品候选 `ae3f812e1c1e142953b657ba41f30fce23e7c14a`，树 `/Users/a77/fwp-wt-backfill-ready-main1751-0925`。
- 已整合 main `1751e21e0fd30642e0b223604b64b30e38c46f41`。最后观测 main `853c4b7fac1321d2e442bef813b71980143c79b4`，新增 #927 仅三个文档文件；实测 merge-tree 无冲突，最新 full-scope 校验通过。不把 ae3 收据移签为合并预览树的收据。
- 工程根 `/Users/a77/.finance-runtime/reviews/pr813-ready-main1751-20260925`；旧 f650 根 `pr813-ready-20260925`。
- 归档 `docs/verification/2026-09-25-backfill-302132-main1751-continuation/`：2738份、13957191字节，manifest SHA256 `48b49f88eaf6cc55fad582895f24c59cbbd89a871f10f33613b5f458f3852c3d`。原始全量pytest XML含JWT形字符串，保留在本机；路径、大小和哈希见 `external-raw-artifacts.json`，没有用base64伪装脱敏。

## 工程与数据证据

所有本段新候选收据绑定干净 ae3，而不是旧3c5或f650：

| 检查 | 实测 |
| --- | --- |
| ruff / Python全量 | ruff通过；16259 passed、0 failed、93 skipped、2 xfailed；collected16354 |
| 定向 | 118 passed |
| 前端 | lint/typecheck/build通过，123单测通过 |
| E2E | 34 passed、2 skipped |
| registry | 5项exit0 |
| 完整范围收据 | 无deselect/keyword/mark筛选，解释器/依赖/干净revision匹配；最新main漂移仍在原门禁内 |
| 完整库副本演练 | apply/verify/37项外部验收通过；错误parquet拒绝、amount负控拒绝；本轮父备份恢复哈希一致；演练前后生产stat与各fact最新日期一致 |

新候选完整库演练 apply `76788ef7b105`、verify `b9c285a003ab`，原库与恢复 SHA256 `5f8e86cd854b7c6569cdcb62bfb5e9861d1d3a804d8f521480003185323dc91e`。窗内11行变64行，close/pct_chg/amount各64非空，technical39/window161，保护行全列多重集不变。它是宿主演练，不冒充独审执行。

## 发现顺序与取舍

1. 在 main79861 上冻结 f650，作者全量15760P、前端/E2E/registry/完整库演练通过。测试期间 main 经 #868 推进到1751，旧scope门禁因19个合并祖先漂移拒收。保留旧绿与拒收，不改标签；另建ae3并重跑全量。
2. 独审改用完整独立clone、真实302132+000001哨兵历史与市场日历切片。数据在生产只读锁内冻结；副本不是完整生产库。冻结时一次 DuckDB `ATTACH ?` 参数解析失败，原件保留，固定路径字面量后才成功。
3. 批11探索无有效交付；批12路径定位耗尽执行预算。批13固定供应测试，24P，完成C1-C7 `PASS_WITH_LIMITS`，计数审计有效，但身份是f650，不转给ae3。
4. ae3 批14加直接双向全行差集，25P，确认53 INSERT、仅06-23既有行变化；执行阶段耗尽无交付。批15 gateway最终回显不符，未进入审查。批16-19均25P，但没有获接受的终稿。
5. 对批16-18的初步归因曾把缺id/多claim当作首个拒收原因，随后原始controller与离线复现证明：首个拒收实际都是终稿达到6000字符上限，分别7349/7472/7318。缺id、缺claims原文、多出第8条claim是并存的次级缺陷。此处纠正初判，不覆写原始结果。
6. 批18增加完整类型schema，仍未约束总长度；批19每字段限长、离线最坏4817字符，但模型来源说明超360字符，且XML被写成“路径+说明”。批20来源字段600字符、XML固定实际路径，离线最坏4932字符；原6000字符硬门、阳性对照与错误不得PASS等硬门始终未放宽。
7. 批20实际23P/2F：真实日期演练与低空间拒绝两例在沙箱内先遇“干净检出”守卫。宿主前后身份及事后同沙箱只读诊断均干净，不能倒推当时失败无效；直接原因之外的根因尚未证实。终稿又多出F1-F3 claim，未被工具接受。至此停止模型请求，没有重跑失败pytest，没有补签。

| 方案 | 判断 |
| --- | --- |
| 把f650已通过独审移给ae3 | 否：业务源码虽相同，身份与main组合已变 |
| 放宽阳性对照、删失败case、接纳超长/非法终稿 | 否：会把缺证据改写成通过 |
| 用宿主事后身份诊断冲销批20的2F | 否：时间与观察主体不相同 |
| 批次固定上限、独立保留拒收、另做离线准备诊断 | 采用；但最终仍未获合格QC交付 |
| 宣称已部署或重启Workbench | 否：本任务只是专用CLI回填的受控执行准备，生产另需授权 |

## 请求与证据来源

批11-20共138请求；加上既有批04-10的121，批04-20累计259。原始分阶段计数见归档summary，不包括准备脚本和离线诊断。

批20仍为gateway4/explore2/execute4/report1，总11上限，无自动重试。25供应case构成为既有审查断言7+3（宿主修fixture）与宿主新15；不是模型新写的25个测试。C6在三个宿主见证内调用三个作者测试函数体各两次，共六次嵌入调用，standalone作者pytest为0。

## 下一步与禁止动作

- 先在零模型请求的冷沙箱中捕获 `_code_revision` 原始git stdout/stderr和调用时机，定位批20为何出现dirty；目前只能说宿主事后诊断干净，不能说产品或沙箱已修好。
- 交付格式应完整离线验证，含长度、claim集合、绝对XML路径、来源说明，再决定是否申请/开启一个明确预算的新独审批次。批20不重跑、不补签，不把批19的25P当完整QC批准。
- 接着复核PR完整SHA、最新main差异、merge-tree与收据条件；若main增加代码，不能照搬ae3检查。
- 工程根的 `seal_ready.py` / `publish_ready.py` 是未执行的ready-only草案，不能用它们推断已就绪。实际归档写入者为 `seal_continuation.py`。
- #802已closed/unmerged，评论6446保留→#813指针，两个旧分支保留，不重复关闭。
- 合入和生产授权仍false。生产命令与回滚点草案见本次归档的 `production-authorization-draft.md`；未来生产需重新冻结基线、记录逐字授权、使用本轮父收据的backup_path/SHA。发现WAL停下，不删除；不要照搬父备份旧模板中的删WAL提示。
- 文档树代码旧，不从 `/Users/a77/fwp-wt-backfill-302132-0923` 做验收或生产。

本轮审查控制器、离线格式负控和诊断作为一次性证据归档，没有注册成产品能力。共享harness的通用化改动需单独审查，避免把固定本机路径与本工单数据契约包装成通用组件。
