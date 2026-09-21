# OPT-08 · 子研究持久化前置切片（P1a）

## 范围与锚点

继续保留自有 runtime + ResearchHarness，只吸收 pi/dsh 行为合同，不再叠框架。
P0 保存失败/截断合同见 [前一快照](2026-09-18-runtime-contracts-p0.md)。
本片业务代码 `e336093e6061f4240bc1cba0045c599700c7c85f`；测试补强及冻结验收
`7f6b201d028fa53dd9671f5841809d2383caccfb`（仅新增一道竞态测试并改变异目标）。
两提交均已在 `fix/runtime-contracts-0918`；没有合 main、部署或真实付费模型实验。

本片是**子研究独立存储与活进程整树故障隔离**，不是消费 ResumePlan 的恢复 driver。
“能找到子日志”不等于“能重新开车”，更不等于研究质量已提升。

## 按发现顺序

1. 子研究原来只有父账摘要。加入 `BranchRun` / `BranchEpisodeRef`：每次 invocation 唯一，
   `branch-1` 仅作显示号。父事件存子引用，子 configure/state 存 `branch_parent`；预算 view、
   trace、证据 owner 使用持久 ID。子完整模型/工具历史独立保存，不复制进父工具结果。
2. PLAN 与工具两条入口均先可靠保存 `branch_started`，确认失败不启动子工作。
   `BranchRequest` 显式传同一 store；无 store 的调用仍如实标 ephemeral。
3. `FencedEpisodeStore` 把父/子/兄弟关键保存失败合成一棵活树的故障状态。原始 coordinator
   入口也统一包一次。锁只包 store IO，回调锁外执行、不反取其他 ledger 锁；一个观察者抛错
   不饿死其余取消通知。只透明转发真实 `episode_dir`，不让内存 store 假装有磁盘 spool。
4. 第一版失败子支只留下父费用：父 input17/output3，漏了子 input11/output7。只加有界排空
   仍红；继续将 `branch_failed` 纳入 token 汇总，窗内读数才变为 input28/output10、llm2。
   后又发现缓存复用 telemetry 会二次计费，改按本批新到的分支终态事件汇总子调用数。
5. 子授时从当前时刻重建会延长父截止；改为与父绝对截止、收尾保留窗、工具批次 cutoff
   相交，再应用原有 0.9 安全余量。失败后只在原窗口内等待已在飞的子协调器，不续时。
6. 查询缓存不发布仍不足以保护父账：晚归回调会改变已返回父事件/证据。新增批次局部
   `ToolResultScope`，截止或返回时原子关闭父交付；缓存发布仍用独立 QueryPublishGuard。
   真实线程池 + 事件屏障测试覆盖正常/保存失败两种超窗，晚归前后父结果与磁盘前缀不变。
   这不强杀线程，不声称超窗子费用已完整结转；子自身日志仍可能继续。
7. 共享模型客户端不能全局开关 sink。`private_model_output()` 用 ContextVar 隔离调用权限，
   实测 GLMModelClient 父稿可流、子稿不流，子响应完整私存。其他自带出口的 client/SDK 不外推。
8. 子保存失败的进度不再说“主研究继续”；投影配对优先用唯一引用，旧日志兼容显示号。
   `sub_research` 明确 replay=never；非终态关联树在任何恢复合成前拒绝，待整树对账。
9. 首轮固定变异 `shared_tree_health` 存活：下一次 store 写闸掩盖了共享健康读取缺席。
   利用真实 `model_pending` 单步接缝，把兄弟写失败放在父意图确认之后、模型派发之前；
   模型桩只计实际调用、不自带取消守卫。撤共享健康读取后真实多调用一次模型，恢复后零调用。
   没删变异、没改结果预期，首轮证据原样保留。

## 取舍

| 方案 | 评价 | 结果 |
|---|---|---|
| branch-N 直接作日志身份 | 同批可读，但重复 invocation 撞 ID，终态错误配对 | 否；显示号与持久 ID 分离 |
| 父账存全部子历史 | 父上下文膨胀、私有草稿混进公开出口 | 否；双向引用 + 子独立日志 |
| 一支保存失败只停自己 / 全进程熔断 | 前者父仍可能发新效果；后者误伤无关树 | 否；每棵活任务树共享 fence |
| 持 store 锁等模型或跨 ledger 回调 | 慢 IO 串行化，ABBA 死锁 | 否；只锁保存、锁外通知 |
| 保存失败清掉所有结果 / 无限排空 | 前者丢费用，后者无界且假称超时已停 | 否；原窗口内私有结算、窗外交付关闭 |
| 只靠缓存发布守卫 | 挡不了直接父账回调与 evidence append | 否；缓存与父账分别守门 |
| 临时关闭共享客户端 sink | 并行兄弟/父臂互相影响 | 否；每调用上下文的公开许可 |
| 有子日志就独立 retry | 重置共享预算，可能铸第二棵子树 | 否；未对账关联树先拒绝 |

## 固定版本验证

解释器均为主树 `.venv-workbench/bin/python`（3.12.13，依赖指纹 `3328bed61f3e21ea`）。
完整证据根：`~/.finance-runtime/reviews/runtime-contracts-7f6b201d/`。

| 检查 | 固定 7f6b201d 的结果 | 限制 |
|---|---|---|
| 14 项撤保护 | 每项真实断言红→恢复绿，`mutations/results.json` complete=true | baseline/restored-full 各67P，仅所选三文件，非全仓 |
| Ruff + Python 全量 | exit0；11519P/81S/2X，17 warnings，1062.24s | 作者本机工程收据，不是模型质量 |
| 前端 lint/typecheck/test/build | 四项 exit0；107P/8 files | pnpm10.12.1；本机环境，不等同 CI Node22/Linux |
| 浏览器 E2E | 34P/2S | 脚本运行服务，不是真模型研究 |
| registry 四项 + ledger/spec crosswalk | 全部 exit0 | 不扩成生产部署结论 |

精确全量收据：`~/.finance-runtime/test-receipts/20260918T112340Z-7f6b201d.json`。
被测树：`/private/var/folders/t1/q6rpw6g103vcwpknb7wf3xv80000gn/T/contract-mutations-p0j6308y/tree`。
`python-before.txt` / `python-after.txt` 均空，receipt dirty=false、无 dirty paths、依赖门未绕过；
七项核验 exit0，日志 `receipt-check.log`。补强是在单独测试树完成，未边跑全量边改源码。
之后主实施枝仅 fast-forward 到相同提交，不伪称全量是在主实施树跑的。

### 首轮失败不得覆盖

- `runtime-contracts-e336093e/mutations/results.json`：complete=false，第4项 shared_tree_health 存活，
  后续项未在该轮验完。补强后的14项另目录保存，不用新结果抹掉旧覆盖缺口。
- `runtime-contracts-e336093e/pytest.log`：**1F/11517P/81S/2X**，948.92s，
  精确收据 `20260918T111538Z-e336093e.json`。
  红项 `test_ask_call_provenance.py::test_receipt_covers_calls_and_reuses_outer_budget`，
  预期一次503返回None却收到body。同 revision 同文件单独复验9P（`provenance-recheck.log`，
  收据 `20260918T112452Z-e336093e.json`）。最终7f6b201d全量绿，但该提交只改子研究测试，
  **没有修调用收据产品代码；首红根因尚未确认，不归咎环境、重试或其他 agent。**
  合入前如重现须定位，不以反复刷绿替代故障归属。
- 早期定向失败/修补链（费用、spool、并发测试锁内等待、全局 wait 猴补拦住子线程）
  留在 `/tmp/runtime-contracts-p1a-*.log`；这些读数有重叠，不相加，也不代替固定全量。

## 恢复现场盘点与下一步

| 现场 | 已有依据 | 接 driver 前仍要补/核 |
|---|---|---|
| 位置/意图 | EpisodeState phase、reserved IDs、日志序号、deadline、retry | 消费 ResumePlan 的同一 loop；单写者所有权及重复启动拒绝 |
| 输入/消息 | task 的完整 TaskFrame、prompt_assembled、model_input/turn、消息 fold | 完整授权合同/策略与 registry 指纹重验；不能只拿 configure 哈希复原对象 |
| 根预算 | InMemoryRootBudgetLedger.to_dict 有初始/硬上限/剩余/已授总量 | `_grants`/`_promotions` 去重身份未序列化；无已验证的跨进程重建，不能重新 policy 分配 |
| 证据/查询 | EvidenceLedger 快照、工具事件、QueryLedger 去重/缓存 | 保持 E号/owner/日期/原件及缓存准入，未决查询不能当已完成或免费 |
| Inbox | durable inserted/claimed/discarded + pending IDs | 回灌消息正文/目标/身份与投递回执，不只列 ID |
| 父子关系 | 本片双向引用和独立子历史 | 同根预算与未知效果对账，不能逐子重试 |
| 恢复结算 | `_Synthesizer` 能合成 interrupted/cancelled | 当前 append(sync=False)，且见任意 finish 就视终态：须先修保存确认，再开 driver |

下一小片先修恢复合成的保存确认；随后完整现场、同一 loop driver、临时目录真实进程中断验收。
E号原件回读、Workbench next_step/next_turn、真正 wakeup driver、P2 其余工具属性均仍待做。
不得：启动生产 kill/restart、放宽授权/深度、自动 retry 未知效果、把测试桩读数当金融质量或独立审查。

## 工具沉淀

复用既有固定 revision mutation runner；本轮只新增变异定义与测试，不造第二把运行器。
跨领域模式“父账交付与共享缓存分闸”“多重防线要单独压效果边界”已收入
harness 分支 `docs/runtime-contracts-0918@c2e3c81` 的 KIT / BUILD / TOOLKIT，未合 main。
图谱/项目索引与后续状态见本枝 inflight；vault 存量红与本仓工程收据分账。
