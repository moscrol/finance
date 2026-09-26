# H-03: 历史控制的材料来源分区

## 身份与结论

- WIP #845 源码 `b6de1a38c2a66fd4c9f94fda1c29d0b22e29bc16`，父 `7c99f389e9c72668663449dedeacd7fe4830cbdd`；原 #833 `7edfe24e76afbd5c365fbf97dd2414847b086f88` 不移动。
- 短 `材料如下：\n那它们见顶后谁接力？` 与未闭合 `「那它们见顶后谁接力？` 两种正常版反例的安全断言已转绿。前者按材料归属排除历史控制，后者因边界不确定先澄清。受测合法续问保留窗口、截止和 local_only。
- 整体历史仍 **CHANGES_REQUIRED / 未验收**：此 SHA 没有完整 Python/前端/E2E/registry 全叶结论，没有独立终审或自然四题复验；旧自然 not_passed 不翻案。局部通过不是合入许可。
- 未合并、部署、生产回填、删除工作树或重启付费审核；不接管 #814、runtime/财务或其他邻线。

## 修复与取舍

共享 `user_task.classify_top_level_regions` 在材料归属确定后、编号题组认领前生成 control_text；控制识别复用它，不另造历史问句黑名单。所有未闭合引号都标记不确定，不再要求其中先有权限关键词；ASCII 英文词内撇号不是引用起点。材料和编号题原文仍保留。

TaskFrame 的历史推断/主体识别读取未裁剪的原始输入，普通指代回填也先分区再 strip，防止旧末行提取或去首部空格丢失来源容器。展示字段仍沿用旧格式。没有重写 H-02 的逐轴合同编译或用户显式范围变更逻辑。

## 固定源码定向检查

以下五组文件不重复：

| 收据目录 | 结果 |
| --- | --- |
| frozen-history-controller | 168P |
| frozen-conversation-delivery | 191P |
| frozen-partition-neighbors | 187P / 4S |
| frozen-history-assembly | 309P |
| frozen-e2-extra | 130P |

合计 **985P / 4S**，首尾 clean、HEAD 和记录的源码哈希一致。4S 是原有跳过，不改为通过。Ruff 全仓通过；frozen-diff 只对干净工作树 diff 检查，提交前也执行过 diff-check。

新仓内来源分区测试 67 例，包含原两输入、材料容器、引号、缩进、直接控制器、连续回放、真实 run_turn 送达、合法独立续问、英文撇号和编号题。正常量具 `frozen-normal` 为 **157P = 41 + 49 + 67**，与 985P 重叠，不加总。

## 变异验证

每次独立进程临时撤一处保护，finally 恢复 code object。有效条件是 pytest exit1、call 阶段真实 AssertionError、零 collection/setup/teardown 错误、首尾身份及源码哈希相同。

| 模式 | F / P |
| --- | --- |
| partition | 24 / 17 |
| history-infer | 15 / 26 |
| follow-up | 6 / 35 |
| resolution-hint | 1 / 40 |
| cutoff | 4 / 37 |
| history-contract | 42 / 7 |
| history-replay | 2 / 47 |
| history-authority | 17 / 32 |
| history-delivery | 3 / 46 |
| history-backfill | 1 / 48 |
| material-mask | 20 / 47 |
| unclosed-quote | 22 / 45 |
| frame-source | 6 / 61 |
| followup-source | 2 / 65 |

十四种均有效；不是独立审核。边界夹具禁并计数 socket/DuckDB，H-02/H-03 另计意外模型调用。真实入口在研究执行前截停；仅验证合同/意图/工具登记，不宣称执行 history_query。常规回归含临时 DB，不能说 985 项都零 DB。

## 失败与旧探针分账

1. `before-source-partition`：在父 7c99 加新测试、尚未修改产品时 **48F / 18P**。后续新增一个缩进真实入口用例，最终新文件为 67 例；不伪称同一测试文件哈希。
2. `dirty-source-partition-01`：**4F / 152P**，定位先 strip 再判来源的旁路；第二轮 **156P**。后续 dirty 回归仅属开发过程，不移签固定源码。
3. `frozen-original-adjacent`：原样运行 H-02 的旧探针，**1F / 1P**。失败是诊断打印无条件访问 `material_contract.data_scope` 的 AttributeError，未抵达安全断言。不能记为“两原件全部通过”，也不是实际安全断言失败。
4. `frozen-original-adjacent-diagnostic`：新副本仅让诊断字段接受 None，输入和最终安全断言不变，**2P**。旧探针原字节以 `legacy-adjacent-input.py.txt` 保留，补丁副本另存；仓内原两输入断言也通过。

`check.py.txt` 是最终记录器快照；开发早期记录器尚未把 research_contract 加进 SHA256 清单，早期身份范围以各自 receipt 为准。冻结检查已经覆盖。没有为了日志格式改写原件，也没有覆盖旧五包。

## 封存

每个日志/JSON 复制原字节，Python 辅助文件追加 `.txt` 防 pytest 误收集。`sources.json` 记录源路径、长度、SHA256 与改名映射；`candidate.patch` 固定父→候选。清单覆盖除自身外全部成员，提交后另核不可变 Git blobs。发布与记忆回执放包外，不追加到本冻结包。
