# RE06 QC07 写入隔离与离线接线

时间：2026-09-25 18:51 +0800。用户要求“推进”。仍仅本地有界工程与独审准备，不增加218次请求上限，不push/开PR/合main/部署。

## 身份与当前结论

候选仍为 `a30e7e4594ac09310271739c8beb30ee8b2cd3ef`，基座 `03352758cf9b31e3f5d179b517be48cb89588679`。R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，新Q=`R/qc-evidence-isolated-07`。新建独立候选树，候选及作者树均核对干净。修补只在协调分支与新Q，未改受审产品。

**结论仅为 `OFFLINE_PASS_DYNAMIC_NOT_ADMITTED`。** 本轮0模型请求、0 pytest调用，预算仍186/218余32；没有后台任务或自动重试。QC07尚无真实gateway、execute或report。三组独审、C1-C10、新main组合工程、#76自然金融验收均不因此完成。

## 按发现顺序

1. 开工确认专用分支干净；主检出有其他会话改动，不使用它编辑。QC06损坏现场继续拒收。
2. 新增正式 `scripts/review_probes/review_io_sandbox.py`：从既有已审读/网络策略中精确替换共享work写授权；不认识的额外写规则即拒绝。宿主证据不能与任何可写子树重叠。保留原读权限，避免重开此前凭据/源码/目录元数据问题。
3. 文件工具通过host指定的stage/group接入原受限writer，模型参数不能自授身份；文件工具本身再受组/阶段OS策略限制。只有本阶段交付文件可改，新探针create-only；拒收据、冻结输入、其他组/阶段和链接重定向。
4. 探针运行目录改为每次独立的 `scratch/<group>/<run-id>`，收据/日志/沙箱策略改为宿主写的 `evidence/<group>/<run-id>`。Python临时用户态、pytest临时目录、Vitest缓存与JUnit均进入本次scratch。子进程仅获该scratch写权，环境采用允许清单。
5. 测试子进程退出后由宿主复制JUnit进证据目录；拒绝软链接、硬链接、FIFO、过大输出及软链接父目录，目标必须新建。记录和复核实际沙箱策略、helper哈希、原始退出码，仍不代签任意测试代码的语义可靠性。
6. 18:41资源检查：load1=3.3755、已有pytest=3、预计4、空闲46.13GiB，exit75。未等待、未重查、未启动pytest或模型，继续的只是标准库/原生沙箱离线测试。
7. 完成9种真实SDK文件工具组合及原生探针子进程的接线验证。所有交付仅写入专用fixture，不在真实work/e2留下假的EXECUTE/FINAL。Python/UI包装器的动态预检未运行，不能把原生Python边界测试当作它已经通过。
8. 离线记录器有一次断言失败：它预期gateway和stage都因缺执行预检被拒，而stage实际更早因缺gateway收据被拒。保留原RUNNING记录与失败脚本，另写completion说明并核对原日志，没有重跑模型、资源检查或测试。它不是候选缺陷，也不改旧记录成成功。

## 证据与验证

[归档清单](evidence/2026-09-25-re06-qc07-write-boundary/manifest.json)保存482件原始字节及来源/SHA256，另有清单本身。一次性控制器以文本快照存档，不冒充可跨项目直接执行的工具。通用写策略与JUnit取证helper及测试进入正式scripts/tests。

- 标准库unittest：25项通过，其中writer13项、OS/取证helper12项；含真实sandbox-exec、软硬链接、删除/改名、跨阶段写、只写scratch、父目录软链接、FIFO/大小限制。撤掉OS限制后，临时收据确实被覆盖。Ruff通过。
- `Q/io-boundary-preflight.json`：e2/timer/consent三组乘explore/execute/report三阶段，真实SDK注册工具调用及其沙箱Python子进程；合法交付可写/可读，收据不可写，新探针不可覆盖。另有原生scratch探针、软硬链接、后代进程继承限制的验证。0模型/pytest。
- 菜单、SDK退出码传输、阶段命令边界、最终工件检查点四项预检通过，均绑定当前源文件哈希。
- E2探索输入逐字节保留，仅新建当前执行工具绑定 `inputs/frozen-explore-e2-v3/execution-manifest.json`；未继承旧动态结论。
- 缺执行预检时gateway入口拒绝，缺gateway时execute入口拒绝；未授权timer阶段在取凭据前拒绝。相关输出在 `Q/offline-validation/`，汇总在 `Q/offline-validation-completion.json`。
- 锁定环境再核Python3.12.13/httpx0.28.1。QC06 incident.json所列全部文件哈希仍相符，坏收据未恢复。

## 决策对比

| 选择 | 被否方案 | 原因 |
| --- | --- | --- |
| 文件工具与任意探针分别受OS写策略限制 | 只用write helper或提示词 | 探针Python可绕过文件工具直接写盘 |
| 每次scratch与宿主evidence分开 | 收据留在可写work、只chmod文件 | 父目录可替换，文件权限不足以保全证据 |
| 由宿主快照子进程JUnit，保留不可信输出定位 | 让探针自己补收据 | 收据作者与被审代码必须分开；JUnit仍不保证测试语义 |
| 新Q07、旧Q06不动 | 原批修改后续跑、修复坏JSON | 历史失败与首次损坏原件不能洗成通过 |
| 先为E2切片限定最多11次新请求 | 沿用旧37次三组计划 | 实际只余32；其他组保留后续单独准入，不压缩质量或加预算 |
| 本轮资源拒绝后停动态 | 自动等待/重试或杀他人进程 | 单次准入不是配额预留，不能接管邻线资源 |

## 接手步骤与边界

先核 `R/inspect_status.py`，重新获得资源准入后依次执行，任一步拒绝即停止：

1. `Q/execution_boundary_preflight_v3.py`：实际Python包装器预期10例/9P1个故意失败、UI2例/1P1个故意失败；作者仅收集。这里仍是宿主基础设施验证，不是独审阳性对照。只能在真实完成后生成PASS；缺失时禁止手工补收据。
2. `Q/run_gateway.py`：真实通道最多2请求。它在取凭据前要求当前IO预检、执行预检与资源准入。
3. `Q/run_stage_v3.py execute e2`：最多5工作+1收尾请求。E2执行manifest已经准备，**不要再次调用stage_admission execute的prepare或重跑prepare_qc07**。
4. `Q/check_execution_v3.py e2`：逐运行核原日志、JUnit、退出码、来源、子进程策略与收据。合格后才 `Q/stage_admission_v3.py report e2`，最多2工作+1收尾请求。
5. 上述切片总上限11，不代表必耗11；timer/consent不在本切片许可内。完成后重新核剩余额度，再为它们规划。C2语义判官缺覆盖时仍需独立补探针，否则not_verified/BLOCKED。

所有Python入口均用 `R/candidate/.venv-workbench/bin/python`，Node用R/toolchain/bin/node。`tools-v3.sb`仅是收窄前模板，不能直接拿它跑探针。修改任何已绑定工具须产生新预检与绑定，不修改旧PASS哈希刷绿。

真实pytest/UI包装器、实际模型下的收据完整性及产品语义尚未验证；本轮不宣称恶意任意代码已获得全面安全认证。最后一次正式主干漂移为main64847上的54>5拒收，本轮未重签当前main。a30e旧工程绿不签当前主干，更不签部署。

工具盘点：可复用写策略已在scripts/tests，并有撤保护反例；固定路径控制器保存字节快照，不另建运行框架。共享harness-reference仍是脏且旧的他人工作树，未修改；可迁移方法更新在agent-memory既有门禁笔记。
