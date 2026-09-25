# 审计分支整合 main724：四叶尚未启动

## 版本与结论

固定主干：`72402839075e3eefdee7b185db015a0545096b22`。审计分支原HEAD：`8e1d6fc28a2d96bf2015b1be965802c5f7c6385e`。二者实际merge为候选`bb556febd41fed492bdd9d2c10ac95075f9d6726`，保留双方历史，无手工冲突解决。

| 层次 | 状态 | 证据与边界 |
|---|---|---|
| 固定主干整合 | PASS | `integration.json`记录两个父提交与8个新增路径；只合进审计分支，不是合回main |
| 静态检查 | PASS | 干净`bb556febd`全仓Ruff、代码/文档/JSON/YAML差异检查exit0，见`static-checks.json`及两日志 |
| Python、frontend、E2E、registry四叶 | BLOCKED | 资源门持续拒绝，四叶均未启动，没有任何本候选的测试收据 |
| 生产装配、真实模型采用、金融质量 | UNKNOWN | 本轮无生产请求、真实模型调用或用户数据读写 |
| 合入main、发布 | BLOCKED | 未push、开PR、合回main或部署；尚需实际候选四叶、验收与用户确认 |

本次不是只补文档：固定主干比此前已整合的`9d5b9800a`多6个提交、8条路径，其中4个Python路径涉及按模型设置推理强度、API时间预算及对应测试。`effective_reasoning_effort`使请求参数与预算读取同一生效配置。本轮保留这项主干功能，但不启用环境配置、不代签#76真实运行。

纠偏写入、记忆预取、Episode工具/协议/后验校验、会话编排及HTTP异常测试相对`8e1d6fc28`无差异；这只是范围复核，不代替组合测试。

## 资源阻塞原件

`admission-01.json`是早期单次拒绝；`admission-frontend.jsonl`是随后有限等待的41次连续观测，UTC 10:48:07至11:08:09，均`admitted=false`。期间检测到1至4个其他pytest进程，最小空闲磁盘45,968,220,160字节，高于12GiB门槛；阻塞项是其他pytest而非磁盘。采样不是全机锁，不据此推断其他任务的质量或性能。

原计划串行执行前端/浏览器、注册表、Python，每组先重新准入。等待器在第一组之前达到20分钟上限并退出，`controller.json`记录`leaves=[]`、`complete=false`、`blocked_leaf=frontend`及结束时刻。退出后已查无PID 88052；没有本任务测试、浏览器服务或等待器遗留。没有终止或排除其他任务进程。

`manifest.json`核对8份归档原件的字节与SHA-256。哈希只证明归档完整，不能变成测试通过证据。原始产物目录：`/tmp/architecture-main724-bb556febd.k8BCPV/`。

归档文档编辑后的`audit_ledger_spec_crosswalk.py`单项对账exit0，原有98条反向warning保留。该检查发生于文档尚未提交的工作树，不是对干净`bb556febd`执行完整registry五项，不能填作四叶通过。

## 不移用的旧结果

- `78b25943f`的HTTP22P、24文件824P及收据校验仍有效，但只签该SHA；见`docs/verification/2026-09-25-workbench-memory-faults/README.md`。
- `698fd172d`的Python16423P、前端123P、E2E34P/2S及registry五项通过仍只属于旧版本；见`docs/verification/2026-09-25-architecture-main-integration/README.md`。
- 本次没有重采生产health/readiness，既有readiness UNKNOWN不变。主干携带的#76第二批NOT_PASSED及数值预检问题仍由原owner处理，不借其模型预算。
- `data-quality-check`相对固定主干没有触发路径，见`integration.json`。不触发不等于专项已运行。

## 续跑

1. 先确认干净工作树与实际待测SHA，再运行`scripts/review_probes/gate_resources.py --path .`；准入与测试启动必须顺序执行。不要用历史PID代替新采样。
2. 使用现有`scripts/run_frontend_gate.py`完成前端和E2E；使用registry工作流的五条命令；使用`scripts/run_main_gate.sh`跑全仓Python，再用`check_test_receipt.py --require-full-scope`核对。每组记录同一SHA，任何红或未运行都不能合。
3. 沿用主树`.venv-workbench/bin/python`、白名单环境、umask022、独立临时用户/部署台账/收据目录及可清理的basetemp；先查测试端口是否空闲。
4. 本轮未新增运行时或测试修复，无需重做整合本身。若在后继文档HEAD跑测试，只签实际受测SHA；最终合入前另核届时主干，不在测试期间追随远程移动候选。

决策快照：`docs/handoffs/2026-09-25-architecture-main724-integration.md`。
