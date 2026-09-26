# 独立 Spec 复核：不通过

受测树 `/Users/a77/fwp-wt-financial-ratio-units-0920`，最终 HEAD `7149e236576bdda5463407cf67f11095d7940dd2`，代码提交 `8d281985fc3739832881f3cbab0d174a532caeb5`，对照基底 `d8d6196baebdb1108a81ae01466e9df6397dc4fc`。只读审阅；未改候选、生产或原外部探针，未联网、调用模型或合并。

## 需修复：标签在报告期前时，差值单位丢失

规格要求：“bp、基点、百分点属于差值量纲，不能换算后认证为绝对比例”，且散文与表头、单元格、产物应一致。设计源为 `docs/superpowers/specs/2026-09-20-research-closeout-design-review.md:22`；实施计划要求“从产物列、表头、单元格和明确正文值槽识别单位；任何明确差值单位均不能成为比例值”。

`intelligence/services/research_delivery_checks.py:230–240` 的现有“标签在前”分支只令 `remainder = tail`，未提取前缀标签中的单位；`_PROSE_VALUE` 仅看到报告期后的数值。因此 `含金量(bp)：2026中报1.588。`、`含金量（基点）：2026中报1.588。`、`含金量(百分点)：2026中报1.588。` 都被当作无单位比例。

独立真实出口复现：三个句子分别在 judge `off` 和本地恒通过 stub 两种模式下，`calculation_copy_findings` 为空，`SemanticEpisodeVerifier.verify` 均返回 `completed`、原句完整保留、`repair_output_ids=()`。共 **6 个应拒而未拒**。

这是既有解析路径的单位遗漏：同格式合法 `含金量：2026中报1.588。` 可通过，错误 `含金量：2026中报9.999。` 可拒；`2026中报含金量(bp)为1.588。` 也能拒。上述对照两模式共 **6 个通过**。不需要引入 q 分支的新语法。

建议在既有前缀分支提取明确的局部标签单位，传入同一单位核验；保留增长/变化等排除条件、报告期与主体限制，并为这三个句子补真出口回归及合法对照。

## 证据与边界

- `selected-pytest.log`：三现有测试模块中与 ratio / product / financial_contradiction / correct_rounding 相关的 **134 passed，92 deselected**。未重复整仓。
- `independent-probe-result.json`：独立主矩阵 **102/102 检查通过**，包括别名真假值、bp/BP/bps/BPs/基点/百分点/个百分点的五种位置、非法产物与好产物并存、合法单位及排除列、空绑定/异主体/缺输入/不同报告期、两种真实出口模式与修正清债。
- `label-scope-result.json`：上述 **6 个失败 + 6 个正常对照**；另外 **4 条跨报告期诊断未赋予通过/失败判定**，不作本轮阻断依据。
- `original-probe-result.json`：未改动的原外部探针在本 HEAD 重新执行的原始输出。保邻句等既有边界不纳入本片修复要求。
- 作者的红绿、撤保护日志及 manifest 已读取；源码 hash 与作者固定收据一致。它们属于作者证据，本轮未再变异候选。

各分母分别报告，不能相加当作全量收据；未签署全仓、合流树、真实模型或金融自然质量通过。

复跑失败与对照：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/financial-ratio-review/spec/probe_ratio_label_scope.py --root /Users/a77/fwp-wt-financial-ratio-units-0920
```

脚本输出 JSON 中每例的预期、实际、通过标志及公开答案；它本身是诊断脚本，进程退出 0 不代表 Spec 通过。末尾身份、文件 hash 与候选洁净状态见 `review-manifest.json`。
