# 报告期前比例标签单位返修

独立 Spec 在固定 `7149e236` 发现：`含金量(bp)：2026中报1.588。` 等三种差值单位，在 off / 本地 passed stub 两种真实语义出口仍 completed。原无单位1.588正常过，9.999能拒，证明现有“标签在报告期前”语法丢了单位，属于本片遗漏。原 `financial-ratio-review/spec/` 探针与结果保留不动；协调者确认其末尾SHA/clean封存后才编辑。

## 决策

仅修改 `research_delivery_checks.py` 的既有前缀分支：从同句、当前报告期前最近比例标签提取单位，并与报告期后括号单位一起交给现有 `_ratio_unit`。标签在冒号处截止，避免第一期的百分比单位误串到第二期单独声明的“倍”。保留原增长/变化排除；另句的bp和前期数值不能提供标签单位。

否掉从整段前文搜索bp：会把别的事实单位带到当前比例。否掉只检查数值后缀：无法关闭原反例。未拓展 q 多值语法、保稿/E2、财务复算、模型、预算或权限。

## 验证与身份

代码提交 `26fadf33e8ef30a708b6fdd661283c8a5487d8cc`，在首片8d281985与文档7149e236之上，只改一个实现模块、两个既有测试文件及计划。后续只有文档更新。

新证据单独放 `/Users/a77/.finance-runtime/reviews/research-closeout-20260920/financial-ratio-fix/prefix-unit-repair/`：

- 新增原三单位×两模式六反例，另加显式“倍”不能覆盖差值前缀、正常比例/倍/百分比、错值、同比环比变化、另句单位、缺期间数据、两个期间各自标签等对照。`prefix-red.log` 13F/16P → `prefix-green.log` 29P。
- `mutation-prefix-unit.log`：只把 `prefix_unit = _ratio_unit(prefixes[-1].group())` 撤为空串，同组再13F/16P。`mutation-results.json` 留命令与恢复后hash。
- `label-scope-after.json`：原独立探针不改断言重放12P/0F；原4条scope诊断整个记录与旧结果逐条相同。该输出在提交前产生，内含HEAD仍为7149；不冒充固定提交收据。
- `fixed-related-green.log`：干净固定26fadf33上的两个相关模块134P。收据 `/Users/a77/.finance-runtime/test-receipts/20260920T040521Z-26fadf33.json`。`ruff.log` 与提交门禁通过。

首片351P仍只属于8d281985，本轮未重复351P或跑整仓。原先自然金融交付失败不翻案；最终文档HEAD交由协调者重新跑同一Spec轴，再进入Quality。未合main、未部署或读写生产。
