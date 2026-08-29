# 在途交接 · test/conformance-seam-census

- **工单**：`docs/superpowers/specs/2026-08-29-conformance-seam-census-workorder.md`（主树 untracked）。前置工单（运行时缝）在分支 `test/runtime-conformance-suite` @ `9b49ac0a`，两单互不阻塞。
- **分支状态**：任务 A+B 均完成，待验收合并。基线 main@c3514529。
- **交付物**：
  - 任务 A：`docs/verification/2026-08-29-conformance-seam-census.md`——7 条够格/已覆盖缝 + 14 条不够格名单，每行带代码出处；素材由子代理走六层地图收集，落盘前抽查复核 6 处关键出处全部命中。
  - 任务 B：`intelligence/tests/conformance_tools/`（参数表+声明表+棘轮+T-1..T-7+声明完整性），读数 **86 passed**（`.venv-workbench/bin/python -m pytest intelligence/tests/conformance_tools/ -q`，2026-08-29）。ruff 对套件目录全过。
- **资产回写（本单核心交付）**：`~/harness-reference/TOOLKIT.md` 新增 A+ 节（三问格式：失败形状/关键设计/移植要改什么，收录判据「≥2 实现且独立演化；实现数要数装配面」一并写入）；`KIT.md` 审计节指针已更新为完成态。⚠ 该仓当时已有他人在途改动（BUILD/PLAYBOOK 等），本次只动 TOOLKIT.md/KIT.md 两处、未提交，随该仓下次收口一并入库。
- **后续工单队列**：P1×3 占位单已立（llm-transport / market-snapshot / datablock，落主树 specs/），并登进 `2026-08-28-backlog-workorders-INDEX.md` 续表（#12-14；#10/#11 登记为已完成待验收）。P2×2（ArtifactProvider/SkillExecutor）登记于普查报告不立单。主树这些文件保持 untracked，与既有 workorder 家族一致，随 main 由用户处理。
- **执行中的定性判断**（供验收对照）：
  1. providers 链降级：8 厂商槽共用 HTTP `complete` 是配置不是实现，真正独立演化的是 transport（http×cli）——P1 占位单明令禁止按厂商名参数化。
  2. 判官链不够格：`CONTINUOUS_VERIFIER_CHAIN` 是异接口串行两段（函数+Protocol），不是一名多实现。
  3. 工具缝的「实现数要数装配面」：注册表层契约单点强制（默认面全绿、baseline 空是如实读数），漂移入口在生产装配换 schema/parse，装配一致性由 pre-commit `tool-reachability` 门禁看守。
- **红线遵守**：pathspec 提交、未合 main、未改生产代码、IMA 通道未碰。全量叶子检查未跑（主树有他人在途改动，只跑 pathspec 范围），全量对账留验收 session。
