# RE06 QC08 真实控制预检与夹具前提修补

## 执行结果

本轮根据用户“推进”，新建 `qc-evidence-isolated-08`，未重跑或修改QC06/QC07。产品候选仍为 `a30e7e4594ac09310271739c8beb30ee8b2cd3ef`，基座 `03352758cf9b31e3f5d179b517be48cb89588679`，两份候选树干净。

R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-evidence-isolated-08`。

1. 新批冻结前接入46e094bc0用户目录插件；探索原件逐字节继承，旧动态结论不继承。E2仍最多11次新请求，timer/consent未准入。
2. 发现 `R/inspect_status.py` 原硬编码列表只到QC06。因QC07零模型，原186读数仍正确；修为额外识别 `qc-evidence-isolated-*` 并核候选身份，旧脚本存 `inspect_status_before_qc08.py`。临时台账验证新批3次准入计入、离线夹具7次不计、错序拒收。此为单候选单执行者账本检查，不宣称跨进程原子额度服务。
3. 新批bootstrap改用锁定Python；gateway自身上限收窄到既定2次；review凭据解析器PATH也使用锁定解释器。没有访问真实凭据或发出模型请求。
4. QC08离线13项命令检查通过，含36项unittest、9组SDK/原生写隔离、工具菜单/传输/阶段/工件检查和缺前置收据拒绝。
5. 23:51资源准入：load1=3.934，已有pytest1，预计2，空闲39.41GiB。真实Python控制器收集10例，8P/2F、exit1，JUnit和日志均完整。
6. 预期失败为 `test_deliberate_controller_red`。额外失败为 `test_other_artifacts_and_frozen_probes_are_not_writable`：`evidence/e2`父目录未建立，向counterfeit.json写入时报FileNotFoundError，而非PermissionError。没有观察到成功越权写入，但该断言没有触达所需权限检查，不能签通过。
7. 外层计数校验拒绝，原预检收据仍RUNNING；另有host-step终态BLOCKED和独立incident，不改原件。UI控制、作者收集、gateway、E2 execute/report均未启动。0新模型，累计186/218、余32；无动态重试、无本任务后台。

## 决策与修补

| 方案 | 结果与理由 |
| --- | --- |
| 把FileNotFoundError也当权限拒绝 | 否：缺目录并不证明写策略有效，撤保护也可能仍报同错 |
| 把预期改成8P/2F | 否：会接受额外夹具失败并掩盖真正的权限回归 |
| 在失败Q08里补目录后重跑 | 否：本轮已到停止条件，保留冻结批次完整历史 |
| 准备阶段显式建立证据组父目录，另加真实OS反例 | 选：在正确前提下验证PermissionError，并证明删前提会红 |

`review_io_sandbox.prepare_evidence_groups(evidence)` 已加入正式工具，创建全新的evidence及controller-v3/e2/timer/consent目录；拒绝已有树、相对或非规范路径，不修旧证据。下一批准备脚本必须用此函数替代原来的裸evidence.mkdir，且在冻结前完成。

新3项标准库回归覆盖真实sandbox写拒绝、删除e2父目录后复现FileNotFoundError、已有证据不重用、软链父目录拒收。与旧边界/用户目录测试合跑39P，Ruff通过。**尚未把新函数接进新的动态批次，本轮没有重跑完整执行器。**

作者验证另有一次命令错误：从主检出树运行unittest discover时遗漏 `-t <本工作树>`，导入scripts.review_probes失败；明确顶层后15P，随后以专用树cwd合跑39P。incident保留命令/错误观察，不伪装成原始进程日志，不计候选失败。

## 证据与提交

修补及证据提交 `7434a38a1`，未push。507件原件在 `docs/handoffs/evidence/2026-09-25-re06-qc08-controller-fixture/`，manifest所列源文件、归档与该提交Git blob均逐字节核对通过。

- 原预检：`Q/execution-boundary-preflight-v3-1790351478223965000/`。
- 真正pytest：`Q/evidence/controller-v3/controller_preflight-1790351478303257000/`。
- 宿主单步记录：`Q/host-steps/execution-preflight/`；启动器只记录单次明确步骤，不连跑、不重试。
- 事件/39P/Ruff：`R/qc08-controller-incident-0925/`。
- 准备/离线/归档脚本均按原字节收录；日志直接映射为 `.log.txt`，清单保留原路径。
- 旧QC07两组仓内归档仍逐项相同；旧资源源台账的合法追加不改旧manifest。QC08输入helper仍是冻结前旧版，新正式helper不覆盖它。

## 下一步与边界

下一轮先核预算和资源。新建全新批次，复制新helper和已修用户目录插件；在准备阶段调用prepare_evidence_groups，再绑定新路径/源码/探索输入。先真实Python/UI控制预检，成功后才gateway、E2 execute、check_execution、report；任何拒绝即停。不要重跑prepare_qc08、归档器或原QC08预检，不手工写PASS。

真实插件已成功导入并进入10例收集，这是比QC07新增的观察；不代表完整执行器通过，更不代表独审。三组C1-C10、C2语义、timer C7、consent C6、#76自然验收、新main组合工程仍欠。未push、PR、合main、部署，不接管邻线。
