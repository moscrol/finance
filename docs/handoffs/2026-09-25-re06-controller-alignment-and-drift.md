# RE06 执行控制器续推与主干漂移

记录时间：2026-09-25 12:04 +0800。用户本轮要求“继续”；仅本地工程/独审准备，无扩大预算、push、PR、合 main 或生产授权。

## 身份与结论

固定候选 `a30e7e4594ac09310271739c8beb30ee8b2cd3ef`，基座 `03352758cf9b31e3f5d179b517be48cb89588679`。工程树及 QC 树末核均干净，未改应用或独立探针断言。

证据根 R：`/Users/a77/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-locked`，Q=`R/qc-execution-final-06`。本轮摘要、源码 SHA256、收据指针及正式主干漂移检查原文：`Q/continuation-0925.json`；记录器为 `R/record_continuation_0925.py`。

本轮未发模型请求。逐行核账仍 **181/218，余37**；final06 尚未运行 gateway/独审阶段。8个实际阶段工作请求合27，加8个终稿为35，另gateway2。原 `preparation.json` 的 `stage_reserved_final_requests=6` 是元数据错误，原件保留，当前摘要明确为8；总额未增加。

## 按发现顺序

1. 首次资源观察 load1约3.26、pytest=0、空闲58.55GiB，允许尝试；这不是资源预留。
2. 启动前发现执行准入会对已复用的冻结目录再次 `mkdir(exist_ok=False)`，检查器又沿用旧批次执行工具哈希。改为逐字验证复用原件，保留原 `manifest.json`，另写当前 `execution-manifest.json` 绑定当前执行包装器。`--prepare-only` 已完成e2冻结准入，0模型。
3. 三组执行提示仍要求已禁用bash。改为首个 `run_probe({"role":"baseline"})`，工具按固定角色序列执行；后续补充探针使用具名文件。timer/consent未冻结的迁移探针中旧候选路径做纯路径替换，断言未改。原提示/迁移文件在 `Q/input-alignment-0925/`，改动哈希见 `changes.json`。
4. `run_stage_v3.py` 增加冻结输入/当前工具哈希及剩余额度核对；report注入已有宿主执行事实，仍不代签语义。扩展执行边界收据覆盖控制器/菜单/准入/检查器。
5. 11:50:53 +0800 真正执行边界预检被资源门拒绝：load1=13.35498，pytest=3、预计4，空闲55.659GiB，exit75。没有自动重试、没有后台等待、没有停止外部任务。随后只读观察到PR868前向及agent-foundation测试；PID是时点事实，不沿用。
6. 继续静态排查确认已安装Pi SDK的bash工具对非零退出码抛异常，原typed工具会在读取阳性对照收据前中断。仅受控 `run_probe` 内将“命令已结束”作为工具交付，原 `result.json` 仍存实际exit，收据须与原exit、marker、hash、revision/role相符；普通bash和启动异常不改语义。保留对照1F，不变为测试成功。
7. 无模型、无pytest/子进程的SDK模拟验证：exit0/1/75/127，受控与非受控共8组合；原始结果不变、普通非零仍抛错、spawn异常仍抛错。菜单检查涵盖三组顺序、首次只准baseline、禁止bash、资源/对照不合格即停。工件检查与阶段边界重新通过，新收据另存，不覆盖旧件。
8. Gitea `ls-remote`确认main=`79861f07e48573b6b5bd378b28880e484f509905`。正式 `check_test_receipt.py --require-full-scope --expect-revision a30e... --base-drift-max 5 --main-ref 79861...`：身份/环境/范围/计数通过，**合并漂移27>5，exit1拒收**。主干已有应用和静态发布包变更，不能再沿用“只有文档漂移”的说法。未刷新/重跑候选。

## 方案取舍

| 选择 | 被否方案 | 理由 |
| --- | --- | --- |
| 复用原探针并另绑当前执行工具 | 重写探针/覆盖原manifest/重做探索 | 保独立来源与首次失败，又避免旧工具哈希被误当当前身份 |
| 受控工具交付与测试exit分离，交叉验证原件 | 全局吞异常/把对照exit1改exit0 | 预期失败也应可核验，工具返回不等于业务通过 |
| 本轮资源拒绝即停 | 等一会自动重试/杀他人pytest | 首检不预留资源，遵守同机其他owner及无自动重试边界 |
| 主干漂移拒收另记 | 提高阈值/将旧绿背书新main | 固定代码的工程读数不能迁移到新组合 |

## 收据与未验

- `Q/probe-menu-preflight-0925.json`：PASS；纯离线菜单规则，不是独立业务测试。
- `Q/probe-transport-preflight.json`：PASS；真实SDK配模拟operations，0子进程，不是沙箱端到端。
- `Q/artifact-checkpoint-preflight-0925.json`、`Q/stage-boundary-preflight-v3-0925.json`：PASS；0真实模型/pytest。
- `Q/execution-boundary-preflight-v3-1790308253470557000/receipt.json`：BLOCKED_RESOURCE_GATE。其控制收据 `work/controller-v3/runs/controller_preflight-1790308253566705000/receipt.json`，hash `ccc16fd33d133e20358e3ecf4ab763307a6e74496c374b1d7888c8b326666010`。
- 最新控制器修改后仍**没有**有效 `execution-boundary-preflight-v3.json`，不能启动gateway。旧artifact/stage收据不适用于新review源码；run_stage已指向新版本化收据。
- e2 reviewer/author本轮均未执行；三组终审/C1-C10、C2语义判官独立覆盖及#76自然验收未完成。工程既有15470P/86S/2X、前端122P/E2E34P2S只归a30e锁定环境，不是独审。

## 接手顺序

1. 用户重新续推后，先 `R/inspect_status.py` 核实际账和外部资源，不能沿用本轮PID或把允许观察当预留。禁止自动重试、扩大预算或重新准备final06。
2. 有资源才人工运行 `Q/execution_boundary_preflight_v3.py`；此前拒绝目录保留。它校验新的stage-boundary收据；整套通过后才允final06的gateway（最多2请求）。
3. e2已经 `--prepare-only`，不要再重复冻结：核 `execution-manifest.json` 后用 `run_stage_v3.py execute e2`。execute后必须 `check_execution_v3.py e2`；失败即停。timer/consent仍需各自探索和准入，不能直接复用旧报告裁决。
4. 固定候选审查结论只签a30e。要推进合入，需要另固定当前main组合，重新工程准入；不允许将新组合塞进现有冻结身份。#76及发布授权独立。

工具盘点：本轮仅修任务专属审查控制器，源码及收据留在持久证据根且哈希绑定。新增离线验证未涉及应用能力，不推广为共享正式审查工具；真实沙箱端到端仍缺，不能以模拟PASS宣称控制链全部验收。
