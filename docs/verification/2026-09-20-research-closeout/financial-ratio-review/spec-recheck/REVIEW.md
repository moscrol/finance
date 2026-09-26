# 独立 Spec 复验：通过

受测树 `/Users/a77/fwp-wt-financial-ratio-units-0920`；本轮固定 HEAD `d2fc872b4a669685a1175ac4c49c004b5b92155e`，代码提交 `26fadf33e8ef30a708b6fdd661283c8a5487d8cc`。首轮失败 HEAD `7149e236576bdda5463407cf67f11095d7940dd2` 的报告与探针原件保持不变。

## 首轮缺口已闭环

`intelligence/services/research_delivery_checks.py:228–246` 现在在既有“标签在报告期前”分支提取选中标签的单位，并传入相同 `failure_code`。冒号终止标签匹配，多个已明确标注的标签取最近一项；差值单位仍优先，不能被数值后合法“倍”覆盖。正常百分比、倍数及原排除条件保留，未引入 q 的多值对应或保邻句语法。

使用**首轮未修改探针**复跑：`含金量(bp)：2026中报1.588。`、基点与百分点变体，在 judge off 和本地恒通过 stub 两模式均拒绝，公开状态为 `partial`、修复目标为 `metric_evidence`，原输入对象不变，邻句与引用保留。首轮 **6 个失败全部转为通过**，原 **6 个真假对照继续通过**。

## 本轮独立证据

- `label-scope-result.json`：有预期的 **12/12 检查通过**；另 **4 条未判定范围诊断**与首轮逐字段一致，保持未判定，不计入通过分母。
- `independent-probe-result.json`：首轮独立主矩阵重新运行，**102/102 检查通过**。包括三个比例别名真假值，单位位置与优先级，非法产物不可背书，合法单位与增长/变化/非比例列，绑定/主体/报告期范围，以及两种真实出口和修正清债。
- `prefix-pytest.log`：仅两现有测试文件的 `ratio_prefix_unit` 测试，**29 passed，105 deselected**。覆盖正常百分比/倍数、增长变化排除、同句不同报告期各自单位、别句单位不串入、真实出口局部缺口及原件保留。

相对首轮候选，本轮仅一个既有检查模块和两个原测试文件变化，另有三份文档；合并首片后，仍满足“两现有模块＋三现有测试文件”的代码边界。财务别名与输入复算模块未在返修中改变。作者红绿与撤保护记录保留，本轮未修改候选做变异。

这些证据分别报告，未合计为全量收据。**Spec pass 只覆盖本片已约定的有限需求**；不签署合流树、全仓门禁、真实模型、金融自然质量或生产通过，Quality 轴仍由协调者另行处理。

## 复跑

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/financial-ratio-review/spec/probe_ratio_label_scope.py --root /Users/a77/fwp-wt-financial-ratio-units-0920
PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/financial-ratio-review/spec/probe_ratio_spec.py --root /Users/a77/fwp-wt-financial-ratio-units-0920
```

精确 pytest 命令、首尾 SHA/clean、源码与首轮证据 hash 检查见 `review-manifest.json`；首轮身份快照见 `initial-identity.json`。未联网、调用真实模型、改生产或合并。
