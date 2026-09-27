# RE06 QC07 真实预检在 userspace 插件加载期拒绝

## 背景与执行事实

本轮按既定顺序核对预算、固定候选、冻结输入、资源后启动真实执行器预检。候选仍为 `a30e7e4594ac09310271739c8beb30ee8b2cd3ef`，基座 `03352758cf9b31e3f5d179b517be48cb89588679`，两份候选树干净。工具修补不改变产品受验对象。

证据根 R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-evidence-isolated-07`。

1. 23:14资源允许：宿主收据记录load1=4.9253，已有pytest1，预计2，空闲45.05GiB。此前18:41的资源拒绝仍有效，但不描述这一轮。
2. `Q/execution_boundary_preflight_v3.py` 启动一次 `controller_preflight`，真正创建了pytest子进程。它在加载 `inputs/qc_userspace_isolation.py` 时exit1，未进入收集、没有JUnit，`counts=null`。
3. 根因：执行器把 `QC_ISOLATED_USERS_DIR` 指向本次 `scratch/controller-v3/<run>/users`；旧插件第9行仍断言目标位于 `Q/work`。这是测试执行环境的契约冲突，不是候选业务断言失败，也不是预期的9P/1F控制结果。
4. 上层预检因计数断言失败exit1，原预检收据停在 `RUNNING`。原件保留，另写事件结论，不手工补状态或PASS。
5. 后续UI控制、作者收集、gateway、E2 execute/report均未启动。没有自动重试，没有模型请求，没有本任务遗留运行进程。预算仍186/218，余32。

## 决策与被否方案

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 直接删掉userspace目录检查 | 会失去错误路径的早期拒绝，掩盖显式配置与默认回退不一致 | 否 |
| 原地替换Q07插件再改manifest重跑 | 使同一冻结批次混入另一份执行器身份，且违反失败即停 | 否 |
| 保留Q07全部原件，提交新插件模板和消费者回归，下个新批次再接线准入 | 分开历史失败、修补工程与未来动态结论 | 选 |
| 把exit1算作预期故意失败 | 未收集测试，无法满足10 collected/9 passed/1 failed | 否 |

## 修补及验证

代码与16件证据已提交 `46e094bc0`，未push。

- 新模板 `scripts/review_probes/qc_userspace_isolation.py` 只供新批次在冻结前复制到 `<review>/inputs/`，本轮没有覆盖Q07旧插件。
- 目标必须是宿主指定的当前 `scratch/<已知组>/<运行号>/users`，拒绝相对路径、路径穿越、软链、旧work、跨运行目标、错误层级及缺少运行目录。
- `FORESIGHT_USERS_DIR` 必须与默认回退目标一致。插件验证后才导入并设置 `userspace.USERS_DIR`；测试清掉显式环境变量后仍落到本次scratch。
- 新11项标准库unittest覆盖部署位置的真实插件导入和用户目录消费者，含恢复旧work检查后合法scratch路径被拒的变异。与旧writer/OS隔离回归合跑36项通过，Ruff通过。
- 验证仅属作者离线工程；没有重跑真实pytest/UI包装器，不证明模型独审、完整收据不可变性或C1-C10。

可迁移知识：权限收窄后，要同时验证真实调用方设置的路径和被调用方的默认回退。低层“禁止越权”通过，不保证合法任务能启动。保护已在插件及正式回归中，不另造通用执行框架。

## 收据与原件

仓内归档 `docs/handoffs/evidence/2026-09-25-re06-qc07-userspace-rejection/`，`manifest.json` 列16件源路径和SHA256；已逐项核对源文件、归档与 `46e094bc0` 的Git blob字节相同。

- 原预检：`Q/execution-boundary-preflight-v3-1790349291351155000/`。
- 原子进程：`Q/evidence/controller-v3/controller_preflight-1790349291387123000/`；收据hash `a4e40d8388b03c9cc3cd1e22cca2f9be40d1c39360736ced6959d047408270d3`。
- 分离事件及离线日志：`R/qc07-userspace-incident-0925/`；记录器 `R/record_qc07_userspace_failure.py` 已按原字节归档，使用create-only，勿重跑覆盖。
- 旧482件仓内归档均未改；对应源文件481件未变，资源台账合法追加506字节，旧字节仍是前缀。本轮不宣称482个源hash全等，也不修改旧manifest。

## 后续与禁止事项

先核预算和资源，再准备新的、重新绑定执行工具及输入的新批次，把新模板在冻结前接入；所有路径及收据身份必须指向该新批次。先做真实Python/UI执行器预检，成功后才gateway与E2执行/事实核验/report。原E2切片最多11次新请求的上限没有放宽，timer/consent仍需另准入。

禁止重跑或改写QC06/QC07失败原件，不把离线36P或旧a30e工程绿迁移到新批次/新main。仍欠三组独审、C2语义判官、timer C7动态UI、consent C6同族分类、#76自然验收；合入需另固定最新main组合重验。没有push、PR、合main或生产授权。
