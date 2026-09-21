# O-K3-001：调用级收据归属修复与源码验收

## 当前结论与授权

K3归属审查收口后用户回复「继续」，本轮只续 #814 修复；没有新增模型会话/预算、合 main、部署、生产回填、删真实工作树或接管Arena。

代码 `a092a021c3d7d978c4dfd9551e74aa984a523f18` 已推原 #814，**作者源码工程验证通过**。旧 v3 `47530e20` 的 `CHANGES_REQUIRED` 与K3双轴未终审历史保留；新代码未独立复审，整体接受仍阻塞。06:02Z远端main为 `c615adbd2f861e23f2c8d03631833f98b3ae5aba`，未在其上构建/验证新组合。

证据目录：`docs/verification/2026-09-21-ownership-reentrant-repair/`，115文件（含README、不含manifest），2,564,341字节；manifest逐成员保存大小、SHA256和本机原件路径。旧五包30/30/86/26/450原字节不变。原件根 `~/.finance-runtime/reviews/ownership-reentrant-repair-20260921/`。

## 背景与发现顺序

1. 固定v3审查的Quality探针发现：外层测试内调用同进程 `pytest.main()`，内层先占外层唯一收据；外层1P，但gate读取内层2P/不同目标并返回0。PID（进程号）相同不足以区分两次调用。操作员用完整候选环境契约复现，未证明失败外层会被放绿，也不推断旧全量数字污染。
2. 本轮在独占修复树 `~/fwp-wt-test-gate-receipt-identity-0921` 的 `54913deb9` 上先加测试。第一组9例旧码6F/3P；修改后同组9P。没有改旧审查树或失败文件。
3. `conftest.py` 将写资格绑定本次Config（pytest调用配置对象）：环境PID继续挡继承的子进程；Config私有stash存 `(PID, 认领路径)`，内层Config没有资格。`add_cleanup`释放自己认领的环境状态，覆盖配置报错与正常结束；顺序顶层调用可重领，不清除继承的owner。
4. 扩展最终15个新增参数化测试：不同目标/同目标执行与收集、内层失败/外层失败、顺序成功/配置失败（原owner缺席或空串）、继承self/foreign PID、路径变更、子进程/嵌套shell gate与真实并发会合。相关四模块71P。
5. 隔离复制精确旧源码配最终测试得到11F/4P；三个变异逐一打红，还原15P。另用旧操作员复现装置派生的精确源码/完整环境契约副本，子进程对照、同进程复验均正确记外层1P，无文件已存在告警。
6. 代码提交a092，仅改hook与测试两个文件；净树跑全量Python gate，收据/JUnit/终端对账后推原分支。文档尖不继承源码收据。

## 方案对比

| 方案 | 评价 | 决定 |
|---|---|---|
| 只保留不可覆盖唯一文件 | 防覆盖、不证明第一位写者是谁 | 不足 |
| 仅PID相等允许写 | 分得清父子进程，分不清同进程重入 | 替换归属判据 |
| 只校target字符串 | 同文件运行不同子集仍可错记计数 | 否决 |
| 模块级标志或只在sessionfinish清理 | pytest可重载conftest；配置失败没有正常sessionfinish | 否决 |
| Config局部凭据 + 环境PID + cleanup | 界定调用与继承边界，清理覆盖异常前期，支持顺序重领 | 采用 |

只改所属层，不修改tree/进程退出码校验、收据schema、不可覆盖写入及latest导航规则。该机制防合作任务误归属，不是恶意同用户写者/测试代码沙箱；未承诺线程并发调用pytest支持。

## 验证与成立条件

解释器统一 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。P=通过，F=失败，S=跳过，X=预期失败。

| 对象 | 实测 | 原件/归档相对路径 |
|---|---|---|
| 首批9例旧→新，dirty诊断 | 6F/3P → 9P | `red-new/`、`green-new/` |
| 最终相关四模块，dirty诊断 | 71P | `focused-final/` |
| 精确旧hook + 最终15例，合成仓 | 11F/4P，无装置error | `old-source-final-tests/` |
| 三变异，同15例 | 去Config证明7F、去cleanup4F、同PID重领6F；基线/还原15P | `mutation-results.json`、`mutations/` |
| 精确a092副本复验 | 子进程/同进程两种均gate0、外层target/1P | `exact-source-reproduction.json` |
| a092干净源码全仓 | Ruff通过，pytest **11963P/85S/2X/17 warnings/0F**；gate0，1784.292s | `clean-source-full/` |
| a092原树回读/条件检查 | 两者exit0 | `source-readback/`、`source-compatibility/` |

唯一完整收据 `clean-source-full/receipts/gate-QQdiL9Bn/pytest.json`；其SHA256 `d513bb5f8c30f15613db0c6a1ac433b395e46bd3e044fee9a731ae7d5269705d`。前后净树同a092，目标为该修复树全根目录，JUnit12050项与11963P/85S/2X一致。X来自JUnit/控制台，不是收据字段。

shell仍只留pytest末15行；JUnit是逐项结果，不是完整stdout。正式测试用小环境夹具，精确复现另复制完整原契约以排除装置差别。首尾身份不证明中途绝无改后还原。全量一次，耗时不作性能结论。

## 工具沉淀与后续

- 永久守卫已进 `tests/test_main_gate_receipt.py`；有限变异/复现/封存脚本随证据保存，`.py/.sh/.log`加`.txt`只改档名、不改字节。大临时树、DB、Git对象、缓存与latest导航排除，不声称保存了全部临时状态。
- 方法回写harness独占且不落后main的 `docs/receipt-identity-board-0921`，BUILD §5/KIT提交 `9f1c80b0b681e6fce89fe118377a67387f756e9a` 已推PR14；共享harness主树脏内容未碰。
- v3作者/Spec/Quality三树保持净树47530e20；#813源码未改。旧Codex阻断、K3未终审、旧失败读数均保留。
- **本轮没有三单新组合、latest-main集成、frontend/E2E/registry叶，也没有独立复审。** 单分支11963不能与旧组合12068直接增减比较；修复不能继承旧组合绿。
- 下一步先确定集成基线、冻结新组合并跑全叶；追加独立审查会话及预算另授权。main合并、部署、完整副本302132父子发布/恢复演练、生产回填、真实树删除分别确认。
