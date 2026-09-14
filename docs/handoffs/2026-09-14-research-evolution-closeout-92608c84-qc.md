# 研究进化四轨收尾复核 · 92608c84

## 结论与范围

**认可 05 作为 06 集成验收候选；本轮未发现新增业务代码阻断项。收尾有两处 P3 文档一致性问题，不要求业务返修，不构成合并 main / 产品放行许可。**

本轮只审 05 收尾、自报证据与跨轨交接风险。01/02/04 核 HEAD、干净度与相关交接；未重新验四轨全部代码，未实施 06 组合验收。未修改四轨文件、业务实现、主检出树或生产数据。

隔离审查树：`/private/tmp/research-evolution-closeout-92608c84`；起点 `92608c84886c148446955790e1e9e52d2cbc7187`。审查分支 `docs/qc-research-evolution-closeout-92608c84` 仅添加本报告与自己的交接。

## 按发现顺序

### 1. 固定交付与工作树

主检出树为 detached HEAD 且存在他人未提交改动，因此另开固定在交付 SHA 的工作树测试。

| 轨 | 实际 HEAD | 开工时 git status --short |
|---|---|---|
| 01 | `6cc5748a5ee5752ae1531064bee82c9b9392330c` | 空 |
| 02 | `e27b3352ed07040d09262968ce58311d2096728a` | 空 |
| 04 | `fcc7838c08bbe2248463dc178dbac4d49d32a5da` | 空 |
| 05 | `92608c84886c148446955790e1e9e52d2cbc7187` | 空 |

`92608c84` 相对前次独立复核候选 `8a7baedd`，以及相对代码修复 `ded78479`，差异都只在 05 inflight 与 PROGRESS 两份文档；业务代码及测试没有新变化。本地远程跟踪 refs 不包含四轨 HEAD；未 fetch 远端，不能将此升级为实时远端状态证明。

### 2. 独立复跑与作者收据

在尚未添加审查文档的干净 `92608c84` 上：

- 主树 `.venv-workbench/bin/python -m pytest -q -rf -p no:cacheprovider intelligence/tests/test_product_value_*.py`：**125 passed，exit=0**。
- 原 Round-9 `check_product_value_task_receipt.py`，显式 `QC_TREE` 指向候选：**8 passed，exit=0**。脚本从 `b3c631b9` 的现有审查树原样执行。
- Round-10 原 `product_value_no_run_matrix.py`：**20 scenarios passed**；包括协议适用/入账子集、估算/未知费用、覆盖不明、其他任务费用及事件逆序幂等，检查公开 task/component 归属。
- 全仓 `ruff check .`：**All checks passed**；`git diff --check` 通过。

候选模块原件：`~/.finance-runtime/test-receipts/20260914T034035Z-92608c84.json`，revision 全长吻合、dirty=false、worktree_dirty_total=0、dependency_gate_bypassed=false。

作者全量原件：`~/.finance-runtime/test-receipts/20260914T025114Z-ded78479.json`，实读 **9665 passed / 77 skipped / failed=0 / error=0 / exit_status=0**，dirty=false、dirty_paths=[]、worktree_dirty_total=0、解释器正确。此为作者历史全量，不是本轮独立全量；没有用同 SHA 的零收集收据代替它。

外置 probe 的 pytest 收据名含 `b3c631b9`（探针所在树），不是目标业务 SHA；目标以命令的 `QC_TREE` 和矩阵 `target_revision` 核验。原始输出：`/private/tmp/research-evolution-closeout-92608c84-evidence/{module.log,original-probe.log,matrix.json}`。

### 3. P3：当前行动项仍引用旧候选 SHA

位置：`docs/superpowers/plans/2026-09-13-research-evolution/05/PROGRESS.md:198`。

最新的「Round-10 复验通过」节末尾仍让 06 使用 `05 8a7baedd`；用户交付表是 `92608c84`，05 inflight 则要求使用本分支 HEAD。两者代码相同，所以不是漏修复，但旧候选没有本次补上的消费提示。集成人照当前行动项取提交时，会漏掉刚写的交接更新。

建议：历史 QC 的被测 SHA 保留 `8a7baedd`，当前交付指针统一到 `92608c84`（代码修复 `ded78479`）。不要为统一交付指针而改写历史收据归属。

### 4. P3：旧动作继承风险的落档位置与自述不符

定位对照：

- `docs/handoffs/inflight/feat-research-evolution-05-product-value.md:25–28`：下一步只有接线/授权及 unknown 消费、规则重复提示；未记录旧 snooze/close 语义。
- **01 候选**的 `docs/handoffs/inflight/feat-judgment-maintenance-01.md:23–24`：已记录 J12 附带语义及旧 key 衔接风险。

因此不是「风险完全没记」，而是收尾自述「上述关键事项已写入 05 交接下一步」把路径说错。只读 05 交接的接手者可能漏掉待裁决的产品语义。

建议：06 联测任务显式引用 01 交接，并列验收步骤：构造 A→歧义 B→复现 A；分别带旧 snooze、close 动作；通过产品入口和 reducer 后的结果核对历史动作 rejected、复现 open=1、历史链无环，以及界面反馈。是否继承旧动作由产品决定，不由这次审查擅自改成自动继承。不能只检查 assess 产出的 open 数。

05 inflight 实测 **3068 B**；`scripts/session_facts.sh:279` 阈值为 **3072 B**，确实在预算内，仅余 4 B。若加跨轨风险指针，须压缩已有内容，不宜直接追加超预算。

## 06 接手清单

1. 固定四轨交付 SHA 后形成组合候选；单轨通过不等于组合通过。
2. unknown 行保留组件、执行/任务坐标，不能只按 id 去重或作为组件列表唯一键；同一 attempt 的 writer/review 两缺口及镜像补账场景应能区分。
3. 上述 J12 语义走真实入口与完整状态归约验证，并明确记录是否允许继承旧动作；当前代码是不继承。
4. 无 run 组件规则在 measure/summarize 两处重复：当前一致且矩阵通过，只列维护建议，不为此重开代码返修。
5. 集成候选按现行规则跑 Python、前端 lint/typecheck/test/build、E2E、registry 检查；真人试点、产品效果与商业证据另验。合 main、部署仍需用户授权。

计数口径建议：`PV4–PV13 + 7 项追加问题 = 17` 是后续增量，首轮 PV1–PV3 另计。「十一轮（round-1 至 round-10）」若把 Round-8 附加条件与补遗分别算轮，应显式说明，不把轮数用作放行依据；本轮未逐份重验全部历史先红后绿证据。

## 决策与被否方案

| 选择 | 否决方案与理由 |
|---|---|
| 05 可交 06，保留两处 P3 文档意见 | 不因纯文档漂移打回业务；代码无增量且复跑通过 |
| 历史收据认代码 SHA，当前行动认交付 SHA | 不把 ded78479 全量改写成 92608c84 独立全量；也不继续用旧 docs tip 做当前交付指针 |
| 旧动作继承留产品裁决，给对路径和验收步骤 | 不擅自改变历史节点事件语义，不把 assess 数量当全链验收 |
| 复用已提交领域探针 | 本轮无新算法/失败形状，不新建脚本或通用门禁；脏的 harness-reference 不动 |

## 未验证

未独立重跑全量、全部早期 QC 或所有历史红绿对照；未复算「17 项」之外的历史总缺陷数；未验证 06 当前代码、四轨组合、前端/E2E/registry、生产数据与真人试点。以上检查不支持直接合并或部署。
