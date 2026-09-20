# #50 生成段代码根独立复核：0f6c2810

## 裁决

**退修，3 项 P2；不进入合并/部署。** P2 表示需要修正的边界正确性问题，不代表已发生生产事故。作者正常路径验证可信，但新增可执行反例推翻了“写入位置指进代码树一定失败”和“子脚本一定来自固定代码快照”的完整断言。

- 被审代码：`0f6c28101b92d654338e705c357778cf1d818a85`。
- 已 fetch 的主干：`gitea/main@1fef3d276d0e251158803fc09d5a81e60d79241b`；左右差为 0/4，含前置 local-plan 修复。`git merge-tree --write-tree gitea/main 0f6c2810` exit 0，仅说明机械合流无冲突。
- 作者交接尖端：`6e8c5a2a`；相对冻结代码只有两份交接与 #50 工单文档变化。
- 独立工作树：`/Users/a77/fwp-wt-qc-generation-root-0f6c2810`，分支 `docs/qc-generation-root-0f6c2810`。复跑时版本控制内容与被冻结代码一致，树干净；随后只新增审查探针和证据文档，没有改运行时代码。
- 本轮未 push/合并/部署，未请求复盘会、模型或知识库接收链，未读写生产 DuckDB/用户态，也未操作主检出或旧污染副本的 WIP。

## 发现

### R1 · P2：父目录通过不代表实际写入路径通过

位置：`scripts/run_daily_generation.py:43–55,74–77`；实际写入在 `intelligence/workflows/daily_review.py:103,442`、`scripts/render_daily_review_briefing.py:71–84`。

启动器验证 exports、daily、matrices、users、episodes 的根，但没有验证即将使用的日期子目录/用户子目录/具体文件；cross-day 质量结果目录甚至未纳入该列表。预先存在的软链即可把正常路径引入代码树，不需要运行期间替换链接或恶意 Python。

| 配置（全部临时树，启动前即存在） | 实测 | 违反的合同 |
|---|---|---|
| `DATA/app/users/root-test → CODE/qc-user` | exit 0，真实 metrics writer 新增 `CODE/qc-user/workflow_metrics.jsonl` | 用户态写入代码树没有拒绝 |
| `DATA/复盘/daily/2026-09-11 → CODE/qc-report` | exit 0，真实 renderer 新增 HTML 和 PNG | 日报输出根验证没覆盖日期目录 |
| `DATA/skills/daily-full-review/state → CODE/qc-quality` | exit 0，真实 CLI 新增 `quality-2026-09-11.json` | 已存在的运行状态写入未被覆盖 |

**返修要求**：对本轮会消费的最终写入目标做规范化与代码根排除，包括用户实例、日期目录、质量状态、摘要和已有文件软链，而非只判断父根。可在计划构建/副作用前集中验证，也可由 writer 统一校验；保留合法外置用户态与相对路径的数据根语义。无需扩成 OS 沙箱，本项只要求挡住启动前已可确定的错根路径。

### R2 · P2：摘要参数由两套解析器解释，缩写绕过检查

位置：`scripts/run_daily_generation.py:56–61`；下游 `intelligence/cli.py:1268,1293,1754–1755`。

启动器设置 `allow_abbrev=False`，又用 `parse_known_args` 将不认识的参数继续交给原 CLI；原 daily parser 保留 argparse 的默认缩写能力。因此：

```text
--dry-run --summary-json CODE/qc-summary.json  → exit 2，零写入（对照）
--dry-run --summary-j    CODE/qc-summary.json  → exit 0，CODE/qc-summary.json 被写入
```

不是干跑状态是否写摘要的问题，而是**同一逻辑参数在检查与消费阶段有不同含义**。

**返修要求**：复用同一份解析结果/参数规范化，或让最终 daily parser 也拒绝缩写（不要简单把前置 `allow_abbrev=True` 当修复，须覆盖歧义与重复参数）。验 `--summary-json value`、`--summary-json=value`、合法缩写的拒绝或等价校验及重复参数“最后一次生效”语义；数据根合法摘要仍能写，错根摘要在任何写入前拒绝。

### R3 · P2：绝对子脚本路径仍可能解引用到数据树代码

位置：`intelligence/workflows/daily_review.py:293–299`；启动器只对 `scripts/run_daily_generation.py:22–25` 的少数入口文件做 `resolve(strict=True)` 检查。

`CODE_ROOT / relative` 只保证路径文本在代码根，没有保证实际文件仍在根内。设置：

```text
CODE/scripts/render_daily_review_briefing.py → DATA/scripts/render_daily_review_briefing.py
```

真实启动器/CLI/runner 随后执行了数据树脚本：

- 数据树脚本抛 `QC_DATA_TREE_SCRIPT_EXECUTED`：最终 exit 1，但**旧代码已执行**，不是根校验挡住。
- 数据树脚本只打印同一哨兵并正常退出：最终 exit 0，整条 workflow PASS。

**返修要求**：副作用前验证所选计划的实际执行文件 `resolve(strict=True)` 位于同一固定代码根，拒绝外逃软链；嵌套脚本遵守相同规则。若快照完整性是前提，可统一校验快照/选中执行闭包，不应声称字符串拼接已经做到。验收要看哨兵**从未执行**，不能把旧代码自身报错当成 fail-closed。

## 可复跑证据

已落仓 `scripts/probe_generation_code_root.py`；支持 `--repo <返修树>`，每项用独立临时副本，不修改待验工作树。退出码 0=全部合同通过、1=反例、2=探针不可用。当前 **7 项中 1 对照通过、6 项反例失败，exit 1**，分属上述三类缺陷。

```bash
# 在审查树执行；返修后把 --repo 指向返修树，不改此探针判据。
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/probe_generation_code_root.py \
  --repo /Users/a77/fwp-wt-generation-root-validation-0f6c2810
```

- 结构化反例：[generation-root-0f6c2810/counterexamples.json](generation-root-0f6c2810/counterexamples.json)。
- 指纹清单：[generation-root-0f6c2810/manifest.json](generation-root-0f6c2810/manifest.json)。
- 本机证据目录：`~/.finance-runtime/reviews/generation-root-0f6c2810/`。
- 夹具复用作者 `tests/test_generation_code_root.py::rig`：临时 DuckDB、质量结果/SQL collector 替换；真实 Python、launcher、CLI、runner、writer 执行。用户态反例不依赖手工 episode 写入，用真实 workflow metrics writer 即可复现。矩阵 SQL/真实模型不在本反例判据内。

## 正常检查与证据边界

| 检查 | 本轮动作 / 读数 |
|---|---|
| Python 定向回归 | 干净 `0f6c2810` 独立复跑 **133 passed / 0 failed**，17.82s；收据 `~/.finance-runtime/test-receipts/20260915T014156Z-0f6c2810.json`，dirty=false、解释器/依赖门正常 |
| 原生成调用点变异 | 包含于上行：临时副本改回裸 `-m` 执行数据树哨兵，恢复成功；未变异开发树 |
| Ruff / zsh 语法 / diff | 本轮独立 exit 0；新增探针 Ruff 也通过 |
| 作者 Python 全量 | 校验 `20260914T181625Z-0f6c2810.json` exit 0，可采信 **9679P/77S/2xfail/17 warnings**；核对原日志一致。本轮没有再跑全量，不冒称独立全量 |
| 作者前端/E2E/registry | 查验原日志：76 tests、15 E2E、registry 四项通过；**本轮未复跑**，不得称独立全套验收 |
| 作者警告 | 17 Python warnings、crosswalk 96 warnings保留；共享图谱其他分支失效引用按作者已知边界保留，本轮未复审/改动它 |

定向分两批早期读数为 87P 和 46P；后一批当时有未跟踪审查探针，不把它冒充干净收据。随后移走探针，干净冻结树把两批**合并重跑为上表133P**。反例门也在没有审查探针的目标树上执行，脚本从仓外启动；再移回脚本供提交。新增六个红反例不是原133条的失败项，两个分母不相加、不混淆。

## 范围与下一步

1. 作者按 R1/R2/R3 返修并加回归；同一探针全部通过且正常对照仍绿后，再交独立复核。当前不能以原全量绿覆盖新发现的合同缺口。
2. 保持显式外置用户状态、不扩散 Python 环境到独立 L2；不用把整流程 cd 到代码根或搬数据来掩盖问题。
3. 独立复核完成之后，仍需用户明确批准推送/合并/部署。冻结源码检查不能替代完整 runtime 快照部署验证。
4. 真实模型、矩阵业务计算、同日/跨日/L2 三道生产门及 KB 接收仍待另行授权验收，本次不称“生产日报恢复”。

工具沉淀：本任务专用门已落 `scripts/`，通用教训追加到既有 `gate-covers-only-its-return-value`；`harness-reference/BUILD.md` 有他人 WIP，不为登记而动共享脏树，TOOLKIT 的新探针索引待其干净后补（分类 B：离线行为探针）。本报告不代作者修 runtime，保留冻结对象与独立复核边界。
