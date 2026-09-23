# OPT-08 · 恢复保存确认前置切片

## 范围与锚点

实施枝 `fix/runtime-contracts-0918`，代码与测试固定在
`371b0ef767cc8c23d0203f1e549cead27c85f9ac`。
前置子存储验收见 [P1a快照](2026-09-18-runtime-contracts-p1a.md)，P0见
[保存/截断快照](2026-09-18-runtime-contracts-p0.md)。旧快照描述的是当时状态；
本片取代其“恢复合成尚未同步保存、旧 finish 会遮住 repair”的待办，不改写旧快照。

这是**恢复判定路径的保存确认**，不是跨进程继续执行的 driver。
`ResumePlan` 仍是下一动作的数据描述，不是免费重试许可；未对账关联父子树仍拒绝恢复。
未 push 金融枝、未合 main、未部署、未做生产中断或付费模型质量实验。

## 按发现顺序

1. 盘点恢复现场时发现 `_Synthesizer.add` 先把合成结算加进内存、再 `append(sync=False)`。
   热 loop 的下一次意图可能冲刷此前结算，恢复控制路径却没有“必定还会有下一次调用”的保证。
   因而返回下一动作或 done 检查点时，所依赖的结算可能尚未确认保存。
2. 新建 `test_episode_restore_persistence.py`，先把“磁盘可见”和“同步确认”拆成两种事实。
   初始测试真实断言红，记录 `/tmp/runtime-contracts-restore-confirmation-red.log`；
   收据 `20260918T113320Z-49a8717d.json` 是 dirty 初始反例，不冒充冻结验收。
3. 改为逐条 `append(sync=True)` 确认后才更新内存；下一动作的检查点、闭合 finish/done
   各自确认后才返回。写前或写后丢 ACK（确认响应）的异常原样向上传播，不给 plan/outcome，
   不重试、不回滚已落盘前缀，也不继续后续写入。
4. 原实现看到任意历史 finish 就报终态，吞掉同进程修复已经推进的现场。
   新判据：done 必须对应最后 finish，且检查点序号就是日志尾；非终态的历史 finish
   后必须有已进入当前检查点的 `repair_reentry`，否则拒绝猜测。缺 finish 的 done、
   缺 done 的 finish、done 后额外后缀均只读拒绝。
5. 初版测试覆盖闭合路径的保存故障，随后补齐返回 plan 路径的 model_error/state
   写前与写后故障，避免只测“失败完成”、漏掉“失败却获准下一步”。
6. 再用真实 `GLMAgentRuntime.start` / 同进程 session.resume 生成修复前缀，在第3次模型
   派发入口捕获 JSONL 与 model_pending 检查点，复制到临时目录重开：恢复应返回 repair/
   retry_model/turn-3，而非旧 already_terminal；恢复本身不再调模型、不写日志。
   模型/行情工具仍是测试替身，这不是杀进程续跑实测。
7. 固定提交后复用原 mutation runner，七项逐个撤保护、断言红、还原绿。
   同时在干净实施树跑四叶工程检查，测试期间不改被测源码；收齐收据之后才写本文。

## 方案对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 沿用异步结算，等下一意图冲刷 | 恢复可能没有下一动作，检查点会领先确认前缀 | 否 |
| 恢复低频控制路径逐条同步保存 | 多一点磁盘开销，但每条确认边界明确 | 采用 |
| 捕获保存异常仍返回 best-effort plan | 调用者会误当成可继续派发新效果的许可 | 否；异常直接传播 |
| 写后 ACK 丢失就回滚/重试 | 数据可能已落盘，且外部效果无法随文件回滚 | 否；保留前缀、交付不确定 |
| 任意 finish 或 done 都是可靠终态 | 会吞新 repair，也把不完整检查点当成功 | 否；当前检查点与日志尾一致 |
| 只要有历史 finish 就永久拒绝 | 破坏已合法推进的同进程修复 | 否；承认已检查点的 repair_reentry |
| 一致 done 推出上次用户收到结果 | 存储状态不能证明 ACK/SSE/调用方送达 | 否；只报告当前可见闭合状态 |
| 同步保存已修就开放 driver | 预算/证据/授权/单写者现场仍未齐 | 否；另补现场、再接同一 loop |

## 固定 371b0ef7 验收

解释器：主树 `.venv-workbench/bin/python`，Python3.12.13，依赖指纹
`3328bed61f3e21ea`。证据根 `~/.finance-runtime/reviews/runtime-contracts-371b0ef7/`。

| 检查 | 实际结果 | 边界 |
|---|---|---|
| 恢复确认七项撤保护 | 每项断言红→恢复绿，`restore-mutations/results.json` complete=true | baseline/restored-full 各32P，只是两个 restore 测试文件 |
| Ruff / Python全量 | exit0；11537P/81S/2X，17 warnings，515.72s | 作者本机工程验证；n=1不推性能趋势 |
| 前端 lint/typecheck/test/build | 全exit0；107P/8 files | 本机环境，不冒充Linux/CI Node22 |
| E2E | 34P/2S，59.4s | 脚本入口；8893/8894隔离端口，正确传RE06_E2E_URL |
| registry四项 / ledger-spec crosswalk | 全exit0，61个SKILL.md可解析 | 不等于生产装配或真实研究质量 |

完整收据 `~/.finance-runtime/test-receipts/20260918T114840Z-371b0ef7.json`：
revision一致、dirty=false、dirty_paths为空、依赖门未绕过、exit0。
`python-before.txt` / `python-after.txt` 均空；指定解释器七项核验通过，见 `receipt-check.log`。
前端/E2E/registry各有独立日志与exit文件，不借 `7f6b201d` 或 P0 的结果。

七项变异是：同步结算、append异常、done检查点异常、plan检查点异常、terminal前缀一致、
finish必须有完成/修复检查点、历史finish不能遮住真实repair前缀。定义在
`scripts/review_probes/restore_confirmation_mutations.json`，运行器
`scripts/review_probes/run_extraction_mutations.py`；无第二套运行器。

冻结前局部：先198P/3S/1X（`20260918T113452Z-49a8717d.json`），补真实repair与plan故障后
221P/3S/1X（`20260918T113903Z-49a8717d.json`），均dirty、有重叠，不与全量相加。

### 首红继续保留

子存储首轮 `e336093e` 的 shared-health 变异存活与全量 call_provenance 单项失败，
均保留在旧目录。那次503应返回None却返回body的根因仍未确认；同版单文件9P、
`7f6b201d` 和本版全量绿，**都不等于已经修复该缺陷**。本片没有改 llm_refine 的调用逻辑。
若再次出现须定位归属，不以刷绿替代解释；详见P1a快照。

## 能力边界与下一步

- 新合成闭合 outcome 标 `persistence=durable`，只表示该恢复操作的事件/检查点已确认；
  草稿、证据、完整费用与候选答案现场仍未重建。已经一致的终态只读返回 already_terminal，
  不倒推此前 ACK 已送达，更不补发公开答案。
- 写后ACK失败可留下模型结算、finish，甚至done；当次调用仍抛错。只留下finish而未有
  匹配done的日志继续拒绝。存储异常本身不保证有一条故障收据能在下次重启读到。
- JSONL重开和真实runtime前缀验证不等于真实进程中断；当前store锁是进程内，尚非跨进程
  单写者租约。不得对活驱动并发启动合成恢复，也不默认自动恢复。
- 下一步先补完整、版本化恢复现场：授权合同/策略与registry指纹、根预算grant/promotion
  去重身份、E号/owner/日期/原件、查询去重/缓存准入、inbox正文/目标/回执、绝对截止和取消。
  关联父子树需同根预算与未知效果对账，不能独立重试铸第二棵树。
- 然后复用同一loop消费ResumePlan，在临时目录做真实进程中断验收，验证已确认工作不重做、
  预算不重置、消息不丢；再推进E号回读、Workbench插话/wakeup和P2逐工具属性。
- 不开放任意shell/写库/交易，不放宽深度/授权；真模型同预算对照、独立复核、合main与部署
  都另立证据或等用户授权，本片不能签这些结论。

## 工具沉淀

复用固定revision撤保护运行器，新增七条定义而非第二把工具。
“恢复控制路径也须确认保存”和“当前检查点优先于历史终态”已收入工具包分支
`docs/runtime-contracts-0918@e15e764` 的 BUILD，KIT/TOOLKIT同步路由；未合工具包main。
项目能力只回写既有能力图谱，项目笔记更新任务行并新增严格一行索引；两文件由vault
自动同步收入`b70c748b`，非手工push。`graph_audit.py` exit0：80行/190断言无漂移，
139条在途/未校验披露；其中已有类名的MERGED提示仅是符号存在，不能当本片行为已合入。
`vault_lint.py`本片前后均20错误/17警告，错误集合无新增也无移除；与P1a保存的前置日志
比较亦相同。仍有死链、作者枚举及工具包镜像漂移，未擅修受保护区或他人笔记，
不冒称vault全绿。日志`/tmp/runtime-contracts-restore-{vault,graph}-{before,after}.log`。
