# 2026-09-22 Runtime #843 K3 独立审查收口

## 背景
用户明确要求用现有 `mirasim-kimi/kimi-k3`，替代等待 Claude 付费授权。本场绑定完整文档 tip `8e4797478afe82ce16d83fbb7750bd8df162196d`，代码仍为 `9fbcc9196`，不是旧 `53f265d7c` 审查准备包，也不移签作者测试或历史外审。

## 执行过程
1. 固定候选 `/Users/a77/.finance-runtime/reviews/runtime-pr843-k3-20260922/candidate`，HEAD/status 首尾均为 `8e4797478afe82ce16d83fbb7750bd8df162196d` / clean；作者树同样 clean。
2. 前三次启动在模型调用前失败：首次/第二次是凭证脚本在 macOS 沙箱内无法创建 here-doc 临时文件，第三次是错误的 `sandbox-exec` 网络语法。三次均零 provider request，原始目录保留。
3. 正式场 `runtime-pr843-k3-20260922-execution-01` 由宿主先取短期凭证；pi 固定 `mirasim-kimi/kimi-k3`、40 请求/1200 秒、无重试/回退；模型 bash 工具单独进入禁写候选、禁网沙箱，只有审查输出可写。沙箱实测源码/外部写入和网络均拒绝，工具未继承 token。
4. K3 共 40/40 request admissions，约 352.8 秒后按硬帽 exit 75。候选和作者树未变；没有 REPORT.md，模型 `verdict.json` 保留初始 BLOCKED 占位。故独立审查裁决是 BLOCKED，不是 PASS/CHANGES_REQUESTED。

## 局部动态证据
- writer/reentry 独立探针 15/15：同任务跨实例、跨进程 flock、不同任务并行、step/close 交错、拒绝后继续完成、关闭后接管和已有日志拒绝均通过。
- parent/child failure fence baseline 13/13：子任务首次 configure 写失败后父树失败，兄弟不调用模型/工具，公开投影 failed，磁盘无模型/工具效果。
- 同一 fence 撤保护 mutation：父结果错误变为 durable/partial、父模型调用增加、失败后写入增加；探针有效捕获。
- restore/repeatability 修正夹具后 23/23：重复恢复按 call id 去重，保留 phase/reserved_ids，不推进捕获前缀，不重新铸预算，身份/能力/工具/截止日/legacy snapshot/预算篡改门禁拒绝。
- K3 首次 restore 探针曾因夹具未创建预算对象而红，后续补夹具后绿；原首红从事件轨迹保留，不能把第一次红算产品缺陷。
- 原 persistence 定向 pytest 首跑 42/44 通过，2 项在 app 导入期因仓库 conftest 清掉 `FORESIGHT_USERS_DIR` 而打开真实默认路径失败；宿主仅将 `userspace.USERS_DIR` 指向新临时目录后同文件 44/44 通过。这是环境诊断，不是 K3 独立终稿。

## 未签范围
`episode_evidence` v3/io_effect、公开投影/SSE delivery_pending/截断输出、完整真实消费者、跨进程恢复 driver、lease、未知外部效果/费用对账、检查点后私有现场恢复、最新 main 组合、合并部署、自然金融质量均未完成动态验收。局部绿不能填补这些分母。

## 证据入口
完整轨迹与收据：`~/.finance-runtime/reviews/runtime-pr843-k3-20260922-execution-01/`；宿主 QC：`qc-summary.md`、`qc/receipt.json`、`qc/environment/receipt.json`。本快照不写 token，不改共享审查队列，不构造 Claude 签字。

## 证据校正与隔离边界
这些计数是探针自己报告的检查项，含setup，不是51项独立行为合同。fence检查中的`or True`使reason子条件恒真，不给该子条件覆盖信用；父状态/调用次数/写入次数四项变异失败仍为有效行为差异。变异脚本预期抓红时自身exit0，不能写成候选pytest退出1。独审只有baseline与mutation，宿主另在新输出目录验证还原绿，不能把后者记成K3完成。

恢复探针首版缺预算对象，TypeError后同名日志被覆盖；首版源码与首红已从原始events按tool call拆出到`qc/trajectory/`。既有pytest曾通过tail展示、复用JUnit文件，首跑/补跑必须对照原轨迹，不能声称每次完整stdout均保存。原件哈希与复跑哈希已核验；宿主两条脚本只写新QC目录，没有修改K3原件。

沙箱仅用于bash子进程；read/write工具是应用层路径检查，宿主pi没有OS沙箱，未完成符号链接竞争和恶意逃逸证明。`controller.sb`虽留在输入中但正式command未使用。正式凭证扩展不校验Plus/有效期（早期参考实现有），仅解析claims；因此不能由参考实现推断本场Plus/期限硬门生效。没有token明文落文件的已知轨迹，但不能把这一环境实现宣传为凭证安全通用组件。40请求准入确实挡住第41次；金额不受此计数证明，零价metadata不是费用收据。

## 决策与被否方案
| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 等Claude付费 | 与用户改用现有K3指令不符 | 不继续等待 |
| 凭证脚本在OS沙箱初始化 | here-doc临时文件被拒，零请求 | 保留失败原件，宿主先取凭证 |
| 宿主/工具嵌套沙箱 | 本机sandbox_apply拒绝 | 单层工具沙箱，明确宿主信任边界 |
| 局部探针绿即签完整PR | 未审项和终稿缺失 | BLOCKED |
| 达帽自动续场 | 违背本次一次有界执行 | 不续场 |
| 占位报告+文字阶段提醒 | 本场仍耗完请求而无终稿 | 不当作收口保证，后续先补机器收口合同 |

## 工具归位与后续
`qc.py`与`qc_environment.py`封存本场轨迹、检查哈希、复跑指定原件并诊断测试默认目录，留在证据根，未作为新产品门禁安装。未将临时K3 runner迁为通用工具：其阶段收尾、完整stdout保留、凭证期限检查和read/write隔离尚不合格，复制进scripts会把本次失败固化成第二条常用通道。方法补充进现有证据卫生笔记，后续应修已有审查设施而不是再抄一份适配器。

本场没有确认新的产品缺陷；宿主44P不清除原独审42P/2F记录，也不补终审。继续独审需新授权与新输出目录，沿原轨迹补未审项、优先形成报告，不重复全量初读。完成后再验最新main组合；合并和部署分别确认。
