# #50 返修：校验最终路径，而非只校验父根

## 冻结对象与裁决边界

- **作者侧返修复验通过，待独立复核**；本记录不撤销旧版本的退修裁决，也不是合并或部署授权。
- 原冻结 `0f6c28101b92d654338e705c357778cf1d818a85`；独立审查及未修改判据的探针提交 `9b974691de91f13ae2af6a6a846cf03d66760a5c`。
- 返修代码 **`387028b846a21a1327d964af8c4b428367f88fcf`**，分支 `fix/generation-root-boundary-guards`，开发树 `/Users/a77/fwp-wt-generation-root-guards`。
- 干净 detached 验证树 `/Users/a77/fwp-wt-generation-root-guards-validation`：全量前后 git 状态为空；前端安装/构建有 ignored 产物。后续交接提交只含文档和证据，不改变被冻结代码。
- `gitea/main@1fef3d276d0e251158803fc09d5a81e60d79241b`，本轮再次 fetch 未变，收据基座漂移检查为 0。
- 未 push、合并、部署；未请求复盘会、生产日报、模型或 KB 接收链，未改生产 DuckDB、用户态或资金口径，未碰主检出 WIP。

## 因果与发现顺序

1. 原实现已让正常生成从固定快照加载，且原全量绿，但独立审查发现三种静态错根配置：用户/日期/状态后代软链写入 CODE_ROOT、摘要缩写绕过校验、绝对脚本路径软链执行数据树代码。原审查见 [0f6c2810 QC](../verification/2026-09-15-generation-root-0f6c2810-qc.md)。
2. 保留冻结代码与 QC 探针，从 `9b974691` 新建返修树；先增加 20 项回归，修复前 **17 failed / 25 passed**，失败对应上述反例与重复参数语义，不是解释器缺包。
3. R2：提取 `intelligence.cli.daily_options_from_args`，启动器调用原 `build_parser()` **只解析一次**，预检和最终 `parsed.func(parsed)` 使用同一 Namespace。原 daily 工作流、摘要 writer、合法缩写和重复参数最后生效语义不变。
4. R3：`scripts/run_daily_generation.py::_validate_code_snapshot` 在导入项目代码前只读扫描 `intelligence/market_feature_store/scripts/skills/evolution` 元数据，检查代码软链真实归属。允许代码根内链接；拒绝外逃链接，包括未选步骤的嵌套脚本和 daily workflow 模块。构建/缓存/持久化目录按代码中的排除名跳过；这是显式快照前提，不是任意 Python 执行隔离。
5. R1：新增 `intelligence/workflows/generation_paths.py`。解析有效日期并构建/过滤既有计划；校验 exports、当日 HTML、矩阵目录、显式/环境用户实例、episode、质量状态，所选归档 increments、checkpoint 日文件以及摘要/计划具体输出。遍历既有后代并解引用，跟随合法外置目录，用已访问物理目录集合避免循环；任何目标入代码根就在步骤/metrics 写入前 exit 2。
6. 首轮定向 107P、冻结探针 7/7 后，增加合法循环、外置目录嵌套回链及三处删闸测试；最终定向 **158P**。总计相对初版新增 **25 项**生成边界测试。
7. 冻结 `387028b8`，再开干净树重跑所有本机等价检查；没有用旧版全量冒充新版结果。先前独立审查者在本轮已参与修复，故这些结果是作者侧复验。

## 选型与被否方案

| 方案 | 评价 / 结果 |
|---|---|
| 保留两套 parser、只调 `allow_abbrev` | 否：同一输入在校验与消费阶段仍可解释不同，重复参数/歧义持续漂移 |
| 禁止所有缩写 | 可简化但改变既有 CLI；本次否，选择复用原解析结果 |
| 只检查 exports/users 等父根 | 否：后代目录和文件已有软链仍能写进代码树，独立探针已证伪 |
| writer 全面新增强制沙箱 | 否：本单只修启动接线；会扩到所有直接 daily 及其他入口，影响面失控 |
| 静态检查已知写入树/具体输出 | 选：启动前可拒绝现存错根链接，不读文件正文、不搬存量；代价是元数据遍历随目录体量增长，未做生产规模耗时认证 |
| 每次执行后才核验 `__file__` | 否：模块顶层/旧脚本副作用已经发生，非零退出也不能撤销 |
| 检查代码面链接再 import | 选：直接/嵌套执行共同受快照归属前提保护；合法内部链接保留 |
| 全流程 cd 到 CODE_ROOT / 全局改 Python 环境 | 否：历史相对数据输出会漂，或污染独立 L2；维持生成 cwd=数据根与原局部环境边界 |

## 行为与变异证据

- **R1**：用户实例、日期目录、质量状态、已有 report JSON/metrics 文件、episode 子目录、snapshot increments 指入代码根均被拒；另验安全外置用户目录中藏回链仍拒绝、合法目录循环有界且能写正常 metrics。
- **R2**：完整选项、`=`、合法缩写、重复参数覆盖；最后一次值安全时成功，最后一次入代码根时拒绝；不能用拒绝全部缩写代替此合同。
- **R3**：renderer、theme brief、matrix 嵌套脚本、daily workflow 的外逃链接均在执行前拒绝；旧代码正常退出/抛异常两种均不能出现哨兵。代码根内软链仍成功。
- 三处变异只改 pytest 的独立副本，顺序为正常拒绝 → 删校验 → 实测 metrics/summary 写到代码树或旧模块哨兵执行 → 恢复 → 再拒绝。正常验证树从未被变异。
- 原 `scripts/probe_generation_code_root.py` 未改：从 QC 工作树执行，`--repo` 指向新冻结树，**7 passed / 0 failed**。结果每项 exit 2、代码文件清单无变化、旧代码哨兵未执行。称“原独立探针复跑”，不称本轮独立验收。
- 夹具：临时 DuckDB，替换质量结果与 SQL collector；真实 launcher/CLI/runner/writer 和子进程。episode 用存储接口夹具写入，不是实际模型回合；策略矩阵业务 SQL 未跑。

## 检查、命令与收据

解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13，依赖指纹 `3328bed61f3e21ea`；`umask 022`，Python 用清洁环境 `env -i PATH="$PATH" HOME="$HOME" KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki`。前端 pnpm 10.12.1。

本机证据前缀 `~/.finance-runtime/reviews/generation-root-guards/`；[manifest](../verification/generation-root-guards-387028b8/manifest.json) 记录 SHA-256，结构化探针与全量收据已落同目录仓内证据副本。

| 检查 | 结果 | 日志 / 收据 |
|---|---|---|
| 修前生成边界回归 | 17F / 25P | `generation-root-guards-before.log`，保留反例 |
| 提交前定向（10 文件，含变异） | 158P / 0F | `generation-root-guards-targeted-final.log`；当时补丁未提交，不能冒充冻结收据 |
| 冻结 Python 全量 | **9704P / 77S / 2 xfailed / 17 warnings**，394.12s，exit 0 | `387028b8-pytest.log`；`~/.finance-runtime/test-receipts/20260915T022354Z-387028b8.json`，dirty=false、依赖门未绕过 |
| 收据校验 | exit 0，revision/解释器/指纹/全量目标/基座漂移 0 均通过 | `387028b8-receipt-check.log` |
| Ruff、zsh 语法、diff、提交钩子 | exit 0 | `387028b8-ruff.log`；`zsh -n skills/daily-full-review/scripts/nightly_full_review.sh` |
| 前端 | lint/typecheck/build exit 0；**76 tests** | `387028b8-frontend-{install,lint,typecheck,test,build}.log` |
| E2E（端到端） | **15P**，46.8s | `387028b8-e2e.log`；fixture 后端、端口18874、清空模型密钥 |
| 注册表 | 四项 exit 0，无缺仓跳过 | `387028b8-registry.log`；check-parseability/check/backfill-tables --check/generate-views --check |
| 台账 crosswalk | exit 0，**96 条反向 warning 保留** | `387028b8-crosswalk.log` |
| 原独立探针 | 7/7，exit 0 | `387028b8-counterexamples.{json,log}` |

收据校验在冻结验证树运行：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/check_test_receipt.py \
  /Users/a77/.finance-runtime/test-receipts/20260915T022354Z-387028b8.json \
  --expect-revision 387028b846a21a1327d964af8c4b428367f88fcf \
  --require-target /Users/a77/fwp-wt-generation-root-guards-validation --base-drift-max 0
```

跨仓条件：registry 读取知识库 `87fabcc0705fe37192cbd9a53559f2917a8155fa` 当时工作树（105 条状态）及研究站 `e63f04856b147662b128fc252d46d0307b0766f2` 当时工作树（1 条状态），**不是干净跨仓 revision 验收**；未改它们。Python 数值计算/utcnow 警告、pnpm 忽略 esbuild 安装脚本提示和 Node 弃用提示保留，实际 build/E2E 通过。

## 待验边界与下一步

1. 新人对 `387028b8` 做独立复核，至少不改判据复跑原探针，并检阅 preflight 覆盖与合法配置对照；旧 `0f6c2810` 退修证据不改。
2. 静态预检不是 OS 沙箱：不防运行期恶意换软链、不认证未枚举的新写入、外部 KB 接收器代码或受信代码的任意行为。直接调用 `intelligence.cli daily` 的其他使用者不自动获得启动器保护。缺直接脚本仍在既有 runner 边界明确失败，不搜索数据树兜底。
3. 没有认证真实模型网关/模型 episode、矩阵业务计算、KB 接收及生产同日/跨日/L2 三道门。上线前还要确认完整 runtime 快照，不能拿测试 import 代替部署验收。
4. 合并/部署/生产补跑另等用户明确授权；本地分支含前置 local-plan 修复，不能只取返修一张提交到未知基线。
5. 工具已有：原离线探针保留在 `scripts/`，三处变异进回归；不另造通用壳。共享 `harness-reference/BUILD.md` 仍有他人 WIP，未改 KIT/BUILD/TOOLKIT；原探针 B 档索引登记待其干净后补。通用教训归既有 `gate-covers-only-its-return-value`，能力图谱更新原节点，不另建能力清单。
