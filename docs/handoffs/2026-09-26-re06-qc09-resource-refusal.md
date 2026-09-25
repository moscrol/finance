# RE06 QC09 真实执行器通过，E2启动前资源拒绝

## 背景与边界

用户明确要求继续，故本轮新建QC09，将7434a38a1的证据父目录准备函数接入冻结前流程。QC06损坏、QC07插件失败、QC08夹具失败原件均不覆盖、不重跑。产品候选仍为 `a30e7e4594ac09310271739c8beb30ee8b2cd3ef`，base `03352758cf9b31e3f5d179b517be48cb89588679`。本轮不固定新main，也不移签旧工程绿。

R=`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`；Q=`R/qc-evidence-isolated-09`。锁定Python3.12.13/httpx0.28.1/Node22.23.2。仅E2 execute/report准入，本切片最多11新请求，总上限218，不扩大timer/consent或部署权限。

## 执行顺序

1. 起始预算186/218余32，无本任务执行器进程，专用编辑树干净；主检出他人改动不碰。
2. 新候选detached worktree固定a30e。准备脚本复制Q08源码与原探索材料，继承前核旧归档hash；不继承动态通过。部署最新review_io_sandbox与用户目录插件，调用prepare_evidence_groups建立全新证据根及四组父目录，再冻结输入及执行器身份。
3. 13项离线命令检查通过，含39项标准库回归、9组SDK文件工具写边界、菜单/传输/阶段/工件检查及缺前置收据拒绝；离线阶段0模型/0pytest。
4. 09-26 00:51真实执行器预检通过。Python控制10例9P/1F，唯一失败为test_deliberate_controller_red；UI控制2例1P/1F，唯一失败为controller deliberate red；作者collect-only收集109例，实际执行0例。JUnit、原始日志、固定源、OS策略及三份收据hash均核对。不能把两个故意失败算产品缺陷，也不能把作者收集当109通过。
5. 00:52真实gateway工具往返通过：mirasim-kimi/kimi-k3，两次请求均HTTP200，一次read工具执行，返回随机哨兵内容。只证明通道与工具结果回传，不是独审。
6. 00:53尝试启动execute/e2，宿主资源门禁exit75：load1=8.97412109375>8；existing_pytest=0/projected=1，磁盘35.7923GiB，两项均未超标。execute阶段目录尚未创建，E2模型请求/探针均为0。拒绝即停，无等待、重试、杀他人进程或调高阈值。
7. 最终188/218余30。本切片已用2，后续最多再9（execute最多6、report最多3），不是再给11。timer/consent仍未准入。

## 决策与被否方案

| 方案 | 结果与理由 |
| --- | --- |
| 把控制预检和gateway通过记为E2独审通过 | 否：没有E2模型交付、候选探针或业务语义审查 |
| 负载短暂超标，等一会自动重试或放宽8阈值 | 否：现有授权是一次拒绝即停，不把瞬时资源观察变成自动排队 |
| 因资源拒绝撤销同批已通过预检，下一次全部重跑 | 否：execute尚未启动，没有夹具/源码失败；同身份收据仍可复核，重复gateway会白耗额度 |
| 新授权后在同Q09以独立尝试收据续E2 | 选：先复核源码/候选/冻结输入/收据完整性和预算，再重新资源准入；保留原BLOCKED收据，不覆盖，不重跑gateway |

本轮没有新增通用抽象，只部署并验证正式prepare_evidence_groups。准备/启动/归档脚本属于本批次可重现证据，均已归档；不另建能力清单。

## 证据

归档提交 `e72745965`：`docs/handoffs/evidence/2026-09-26-re06-qc09-resource-refusal/manifest.json` 列529件，源/归档/该提交Git blob逐项hash一致。credential.json凭据相关元数据仅记录排除项及hash，原件留本地，不复制进Git。

- 真实预检：`Q/execution-boundary-preflight-v3.json`，sha256=`1ac2eb591d78580f9bf596416ca4cf9696baba9e8cf22a9b8ecb509884b1c943`。
- Python/UI/作者收集原件：`Q/evidence/controller-v3/`三次run目录。
- gateway：`Q/gateway/receipt.json`，status=PASS，requests=2。
- 唯一E2启动拒绝：`Q/host-steps/execute-e2/{launch.json,receipt.json,stdout.log.txt}`，complete=true/exit75/BLOCKED。
- 资源台账：`Q/work/reviewer-pytest-admissions.jsonl`，4次准入记录及1次拒绝；这是观察次数，不是5次候选测试。
- 分离事件与核账：`R/qc09-resource-incident-0926/`。
- 归档脚本：`R/archive_qc09.py`，create-only，不可重跑覆盖；还验证QC08归档507件及其全部当前源未变。

## 下一步

资源窗口明确、用户重新授权后，可续同批Q09。先核预算188及固定SHA/干净树，验证execution/IO预检source_sha256、冻结execution-manifest、gateway收据和原件hash。使用新的宿主尝试路径记录启动，不直接重跑已存在的 `run_qc09_step.py execute-e2`（create-only会拒绝），不修改已归档脚本或原host-step收据，不再次prepare/freeze。调用同一未启动的run_stage_v3 execute e2；成功才check_execution_v3 e2，再stage_admission_v3 report e2。任一拒绝即停。

资源台账若因新授权合法append，旧归档仍不可变；验证旧字节为前缀，不重新签旧manifest为最新源hash。若任何冻结源码/身份改变，则不能沿用Q09通过收据，必须新批重新绑定。

仍欠E2语义判官独立覆盖、三组C1-C10、timer C7、consent C6、#76自然金融验收及新main组合工程。未push、开PR、合main或部署，无本任务后台进程。
