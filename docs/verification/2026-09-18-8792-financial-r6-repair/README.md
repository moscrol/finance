# R6 财务原件返修：作者离线验证

## 身份与结论

- 金融业务固定提交：`15527aad05efda1b42d8ffac107da94186760378`，与 `manifest.json.business_revision` 一致。
- 树：`~/fwp-wt-8792-financial-r6-repair`；分支：`fix/8792-financial-r6-repair`。
- `gitea/main@d32b8966` + R5 `dfd7b4ff` → 本地候选 merge `87b854e2` → 主修 `d3af28a4` → 公开出口接线修正 `15527aad`。
- **固定版本作者工程检查在下述输入条件下通过；没有新自然模型验收、独立 QC 或并行合流版验收。旧 R6/R3 整题仍 0/4、not_passed。** 未 push、未合 main、未部署/切换 8792。

## 固定版本读数

| 检查 | 结果 | 收据 |
|---|---|---|
| Python 全仓 | 12055 passed / 84 skipped / 2 xfailed / 0 failed | `pytest.txt`、`pytest-receipt.json` |
| Ruff | exit 0 | `ruff.txt` |
| 前端 lint / typecheck / test / build | 全 exit 0；8 文件、107 测试通过 | `frontend-*.txt` |
| 浏览器 E2E（端到端测试） | 34 passed / 2 skipped；隔离端口 8931/8934 | `e2e.txt` |
| 财务 R6 撤保护 | 基线/恢复全套各 91 通过；13 组均实际断言红→恢复绿 | `financial-mutations.json` |
| 原默认 extraction 撤保护兼容 | 基线/恢复各 165 通过；35 组均实际断言红→恢复绿 | `extraction-mutations.json` |
| R6 原件只读检查 | 4 份原答均命中目标坏句；原正确计算件未被误判；12 个输入文件 SHA256 前后不变，socket 连接尝试 0 | `archive-replay.json` |
| 收据条件校验 | 精确 revision、干净树、解释器/依赖/覆盖范围及基座漂移 8 项通过 | `receipt-check.txt` |
| 能力图谱 / 工具包引用 | 两者 exit 0；图谱只验证路径/符号，不是质量认证 | `graph-audit.txt`、`harness-refs.txt` |
| Vault 文档检查 | 20错误/17警告，与改前b8bd6780同组；无新增但**不是通过** | `vault-lint-*.txt`、`vault-lint-diff.json` |

### 注册表必须带跨仓条件

`engineering.json` 是原环境的原始执行记录，**`all_passed=false` 没有改写**：唯一红灯为注册表 `check`。默认同级扫描读到 KB 主检出 `8a413cde5`（且有他人脏文件），其旧 `rag-query` 与金融 main 已接受的登记相反。未执行 scan 覆盖登记、未移动或清理共享 KB。

另用**相同金融 SHA** 的干净 detached worktree，三仓全部在场：

| 仓 | 固定提交 |
|---|---|
| finance-workspace-private | `15527aad05efda1b42d8ffac107da94186760378` |
| knowledge-base-private | `91725ea9ba0252a43665f9e3130142f946c289ae` |
| finance-research-site | `9f60bef076749cdba13cf228ffa6f22141876eb8` |

原生 parseability / check / tables / views / ledger-crosswalk 五项均 exit 0，前后干净且身份不变，见 `registry-pinned.json` 与 `registry-pinned-*.txt`。这份条件化复验不替换宿主红灯，也不声称在新目录重跑了 Python/前端。将来改变组合或外部依赖须重新固定验收，不能复制总通过标记。

## 原件检查不是重新判卷

封存源：`~/.finance-runtime/reviews/8792-financial-live-r6-20260918/`，原件只读。脚本位于 `scripts/review_probes/replay_financial_r6.py`，只跑有限机械门，不跑完整 Episode 或最终公开投影。`retained_for_mechanical_inspection_only` 是供检查的剩余文字，**不是可发布新答案**；原件里的假缺件提示也可能仍在这份文本中，结构检查另列。

- F1：命中原句 19 的 Q3/H1 累计长度误比；原完整关注项不再因尾注报缺件。
- F2：命中原句 2 的“实际取得报告”无文档依据；报告槽仍缺口，个人复查日 2026-10-22 保留。
- F3：命中原句 2 的存货时长、句 10 的全年/半年同长度、句 23 的无依据 0.6 问句阈值。
- 授权题：命中原句 14 的单季现金流误算与累计长度比较；正确值为 18−33.68=−15.68，而非−15.66。
- 只在临时用户目录调用真实登记 writer：三道不登记题 0 行，授权题 1 行、due=2026-10-22；不改原用户台账。

## 首红与边界

- `baseline-red.txt`：有效初始 34 failed / 13 passed；外置更早 `first-red.log` 是 fixture 哈希错误，不当产品缺陷。
- `adversarial-first.txt`：4 failed / 80 passed；补前置免责声明免责、无关公司文档、增长列等边界。
- `deletion-completeness-red.txt`：20 failed；发现删错后仍 completed。
- **`deletion-completeness-green-named-but-red.txt` 实际 8 failed / 82 passed**。文件名不等于结果；后续修复保留既有 marker-loss 缺口，没有放宽它。
- `prior-pytest-receipt.json` / `prior-pytest-red.txt`：`d3af28a4` 全仓 12053 passed / 2 failed，失败是公开文本出口静态门。`15527aad` 修直接 `view(TerminalFacts(...))` 赋值并登记真实 helper，不豁免门禁。
- `manifest.json` 对本目录收据/展示副本和外置原始日志、变异定义、JUnit、diff 做 SHA256（内容指纹）清单。日志展示副本用`.txt`，仅去行尾空白与文件末多余空行以通过diff检查；原`.log`字节不改，原/副本各自指纹及转换写入清单。不把 pytest 临时数据或工作树当封存原件。
- 数字检查限显式期别、单主体、可确定输入链和有限公式；歧义跳过不代表正确。文档形状通过不证明官方来源真实性；F2 公告取回外部故障未修。
- `a31b572f` 的最终公开投影/保留稿回退检查尚未整合；自然续修、跨进程恢复、根预算与来源真实性不由本轮代签。

决策/发现顺序：`../../handoffs/2026-09-18-8792-financial-r6-repair.md`。下一步：先对齐并行分支接缝、固定新组合工程验证；新 live、合 main、部署分别等授权。
