# River / D4 owned results：隔离联合消费者验证（未通过）

## 结论与身份

本轮只建立本地单父测试快照，不合入 main、不推送、不部署。联合验收 **NOT_PASSED**：两个冲突按意图组合后，D10 的完整推断身份与 D4 的事实资格可以共存，但 B 引擎 grounded 合成的材料准入仍会把本例全部 D4 事实挤出。不是模型答错，也不是所有消费路径都失败。

- 联合树：`~/fwp-wt-river-owned-joint-1008`，分支 `baseline/river-owned-joint-1008`。
- 固定代码/测试快照：`642b45358aadbc6ee2f98d11d08e4e349ff97c15`；tree `c234e2af6848534af1ab4f3c811c8eae78a9c6be`。
- 唯一父提交：`bd66de25085ea73c9c62bc7d5472371785f27e33`（本地 `origin/main` 快照，PR #80）。未做远端 fetch/独立同步核验。
- River 来源：`af1f64b9f30dc13ecf0a4f7882456aeb6aac63e8`，原树保持干净；不回写原分支。
- merge base：`82de3fb730a4175170b4e6ba472e130e5ef87ab7`；含冲突标记的预览 tree：`aee44b66b80b9130b6a5a1ec03a99aa12cf86b9a`。
- 私有证据根：`~/.finance-runtime/reviews/river-joint-consumer-20261008/`（下文简称 E）。后续文档 tip 自己的复跑/封存身份看 E/`completion.json`，不把这里的 642 收据移签。

## 按发现顺序

1. 重新用 `merge-tree` 做整枝预览，真实冲突是 `ask_synthesis.py` 与 `docs/agent-product-door.md`。此前窄修五路径与 Codex 的路径不相交，不能推出整枝无冲突。首次输出重定向早于目录创建而失败，重试才得到上述预览；原失败已记在协调记录。
2. 在新树用 `read-tree` 导入整个预览，不是挑文件复制；没有 `MERGE_HEAD`，也没有对原 river/main 执行 merge。产品冲突只去标记、并列两个独立 tag 分支：D4 prose 返回零 claim；D10 原文成为单个 `data:D10:context`、`INFERRED`，不经逐行清洗。文档保留 owned 与历史镜头两章。
3. `ask.py` / `episode_tools.py` 保持自动合并 blob；未修改 main 上的 `owned_results.py`、Episode 协议/运行层或正文资格引擎。新增 `test_history_d4_joint_consumers.py` 五例。三条临时合成 D4 金额为 500 / 501 / null，严格双红分别 false / true / unknown，另有未来日哨兵。测试禁止联网/真实模型，数据库前后哈希一致。
4. 既有八文件 315P 后，联合专门断言暴露红灯。前几次量具修正（provider 检测、无 claim_id 的省略说明行、工具空参数）保留在 `joint-new-*.log`，不混作产品缺陷。扩大 68 文件得 2084P/1F；当时仍是脏树，收据校验因 dirty 拒收，而不是范围被筛选。
5. 捕获实际 grounded 请求，和相同夹具 D4-only 对照；另开干净 detached main 树，只提取测试夹具/驱动，不覆盖生产模块，确认 D4 query_basis 在 grounded 丢失是 main 原有行为。这个对照只签该 metadata 缺口与三条 D4 事实送达，不宣称两个完整请求逐字相同。临时 main 树验净后已拆除，探针与输出保留。
6. 按 pathspec 暂存解决稿，核 index 无标记后提交 642。提交 hooks 通过，但它们显示的父 HEAD 不是 642 的 pytest 结果。642 干净树独立复跑再次为 **2084P/1F/0E/0S，98.88 秒**，同一失败；收据校验 exit 0，含义是红读数可采信，不是测试全绿。

## 红灯的准确含义

失败：`test_history_d4_joint_consumers.py::test_one_ask_request_keeps_d10_and_d4_fact_roles[True]`。它只要求至少一条真实 D4 fact registry 行送达，尚未要求全部三条，更不是全文金融质量断言。

| 同一临时合成夹具 | registry 字符 | 完整 D4 fact 行 |
|---|---:|---:|
| D4 only | 3,574 | 3 |
| D4 + D10 | 11,986 | 0 |

`grounded_claim_registry_block` 先占显式 required D10，再给反证/缺口保留席位，最后普通事实按分数竞争。D10 行 11,228 字符，剩 772；本次被三条 counter、两条 gap 和省略说明用掉。省略说明如实写 12 条未纳入，但没有逐源准入结果。

- D10 + 最短一条 D4 = **11,791**，数学上装得下一条；零 D4 是准入顺序造成，不应说成“一条也绝对装不下”。
- D10 + 三条 D4 = **12,943**，还未加反证/缺口就超预算；只换排序无法同时交付原样全集。
- `DecisionBrief.supports` 仍列出三条 D4 的 ID，但请求中没有其完整事实正文/registry 行。ID 存在不等于材料已送达。
- D4 typed `query_basis` / `strict_double_red` 在 prepared messages 中存在，在实际 grounded 请求中不存在；该现象在干净 main 的 D4-only 已复现，不能全归因于本次合流。
- 普通 B 合成收到完整 D10 与三条 typed D4 facts、query_basis。原生 Episode 同一工具循环收到历史块并实际调用 D4，选择真实交付后的 owned ref，经最终公开重核为 `owned_faithful=1 / free_unassessed=1 / whole_answer=unassessed`。不把精确片段认证扩成全文认证。

证据：E/`budget-snapshot/` 保存 prepared、完整 registry、实际送达 registry 和实际请求；`admission-trace-snapshot.json` 独立从这些文件核长度和悬空引用；`baseline-d4.json` 为 main 对照。均无真实模型回答。

## 方案取舍

| 方案 | 评价 | 结果 |
|---|---|---|
| 冲突择一保留 | main-only 丢 D10 原子性，river-only 让 D4 prose 铸事实；两个内存替换均被正式证人拒绝 | 否 |
| 并列 D4 guard 与 D10 原块 | tag 不同、责任互补；完整历史来源/表列名/PIT/候选集边界保留 | 已做，仅本地快照 |
| 抬 12K、拆残历史表、删边界说明 | 绕开既定原子合同或预算，不解释联合准入责任 | 否 |
| 删失败断言、改 xfail 或只报 2084P | 把待解决的消费缺口藏起来 | 否，正常红灯保留 |
| 强行把 D4 也设 required / 删除反证席位 | 三事实原样合计已超预算；且任务必需集合、反证保留与降级策略尚未统一，不能为本例硬编码 | 本轮未实施 |
| 接管 owned/wire/finish/repair/carry/restore | 这些不是已定位的最早丢失点，并与 Codex 在途所有权重叠 | 否 |
| 固定红快照并交出实际请求 | 可重复核验消费者契约缺口，不冒充可合入候选 | 已做；下一轮先定准入/缺口合同 |

下一轮建议从既有 `AnswerSpec → registry admission → DecisionBrief / actual request` 接缝继续：先确定任务必须保留的 typed 对象、指导和缺口如何联动；让“送达集合”与下游引用来自同一个选择结果。溢出应明确局部/整体不可完成，不由旧 ID、缓存或自由 prose 补权限。如何在固定预算内承接 D4 元数据与 D10 完整块仍待设计/授权协调，本轮没有新增第二引擎、裁判或台账。

## 已验证及不可移签的边界

- 642 收据：`~/.finance-runtime/test-receipts/20261008T155827Z-642b4535-0ac3aa08fa33.json`；dirty=false、全树脏数 0、依赖门禁未绕过；Python 3.12.13，指纹 `66726d345bf37ce5`。指定 68 文件收集 2085，未加 ignore/k/m/deselect/maxfail；**非全仓 pytest**。唯一 warning 为 Starlette/httpx 弃用提示。Ruff 与层级门禁过。
- `resolution-controls-snapshot.json`：选择任一旧实现都被对应冲突证人拒绝，联合实现在每次替换前后通过；只改内存，不是独立金融裁判。
- 两冻结库、三 cutoff 完整 CLI 信封逐字节等于原 river，块哈希/顺序/INFERRED 保持，库哈希不变；新树独立实测预算如下（这些旧库没有新增 D4 夹具，不能代签联合容量）：

| 样本/截止 | required 行字符 | 总 registry 字符 | 工具 UTF-8 字节 |
|---|---:|---:|---:|
| normal / 2025-04-01 | 11,788 | 11,993 | 15,324 |
| normal / 2025-04-10 | 11,095 | 11,977 | 14,503 |
| changed-gap / 2025-04-02 | 11,659 | 11,864 | 15,093 |

- 旧 result/coverage/direction 的 118/46/60 成员包精确集合、哈希、私有权限复核一致；不追加、不 chmod。0600/0700 不代表文件系统不可变。
- 新真实模型请求 **0**；旧 GLM 全文 `NOT_PASSED` 不翻案。未验全仓/前端/真实生产库/Workbench 真写手与判官/多轮自然会话/独立金融批准；新专门联合证人走直接 B 入口与原生 Episode，不冒充 D4+D10 联合 HTTP 往返（既有 HTTP 历史证人在范围内）。历史日路径、首尾各自水平投影、源日与辅表版本缺口未补。
- Codex 开场为 `1c3101787`，后来切 closeout / ordinary-finish；642 冻结前检查已是 `2ce73ffbde0309110f3740355d1d70256510ff5e` 且两个 Episode protocol 路径脏。只记录、不吸收、不动其修改；末次状态看 E/`coordination-final.json`。所有快照均非锁或双方 ACK。

## 工具沉淀与接续

同请求五个 witness 已进入正式测试；临时预算、main 对照、字节 parity、冲突撤保护、捕获解析脚本均保存在本次证据包，带用途和边界，不留只存在于对话的量具。它们依赖这组固定 revision / 合成夹具，不扩成通用生产入口。可迁移结论是“单个对象的完整送达不蕴含联合输入可送达”，此处已有正常红测试承接；尚无通用准入策略，不另建规则库。

接续先核本分支、Codex 与 main 的实际身份；读本分支 inflight 和 E/completion。修复须保留现在的红证人并补同请求元数据、引用闭合、溢出/反证负控，再对新的干净 revision 重跑。真实 GLM 和真库消费另阶段，不重复抽旧首稿，不以工程绿灯替代金融质量。
