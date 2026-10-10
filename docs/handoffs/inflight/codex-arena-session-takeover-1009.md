## 这个分支做什么
草稿#83长河接续：实现实验性原生Pi复核/一次修订，验证质量边界；不合main/部署/回填。

## 决策与被否方案
| 采用 / 否决 | 理由 |
|---|---|
| 同源typed旁路 / 改作者材料、重读库 | 隔离复核收益，原writer文本/INFERRED/48KB不变。 |
| 共享回执校验+Pi续写 / 伪造Episode、第二金融引擎 | 领域规则仍在Python，Pi只调模型和驱动。 |
| 原稿保留、同稿复用裁决 / 吞稿或抽审求绿 | 失败可核查且不伪造进步。 |
| 实验性且不默认 / 负例总拒绝就上线 | 真审核仍漏类型错、误报和回执失败。 |

背景：[本轮实现与失败](../2026-10-10-native-history-review-implementation.md)、[原实答](../2026-10-10-river-live-financial-acceptance.md)。

## 当前状态
产品a6bbe24f1，后续文档tip另计；97fd→9cd→4366→a6实施旁路、具名审核、有限修订、12条分批与完整性分审。已推#83，保持Draft。根`~/.finance-runtime/river-review-implementation-20261010/`，最终只认completion/RESULT及batched同SHA收据。当前默认Pi和Workbench不启用新复核；原金融全文NOT_PASSED未翻案。

## 已验证
新定向68P、strict TS/Ruff；最终全量/前端/专项/registry与远端head状态看batched工程收据，不移签旧4a的21763P。原生脚本provider覆盖拒→修订、持续拒、坏回执、取消、新题重置、非事实洗白、同稿不重复审。实际GLM旧稿正反对照已留证：high整稿/low整稿/保口径/分批四组各自身份，任何一组未证明审核可靠。

## 未验证 / 已知边界
真实审核仍把正delta当尾段转正、把符号相反当方向反向；正例有坏JSON/额外字段被拒，分批也有length。synthetic/本地前提未进审核上下文另作误报，不算抓错。模型reviewed不是蕴含证明。未通过控制前不再开新完整作者首发；新路径不签真库/泛化/Workbench。旧20日归档10日可读未补。

## 下一步
核completion确认所有模型/门禁终态；读batched/batch-audit.json具体原句和拒绝理由，不能只看总状态。需决定复核路线是否继续，或改以明确陈述类型/算子及程序持有结果文字约束；与并行质量owner协调，不按错句堆正则。#49→#53顺序、#71旧工程结果和未合部署不变。

## 踩过的坑
supported是本句可保留，不是是否含事实；issues只作备注。一个真子句不能赎回整句。scope只存一次，逐句存索引，否则桥接超512KB。小批必须全部齐备再查完整性；缺批不可通过。JSON围栏可剥一层但重复键/多余字段仍拒。嵌套复核usage额外分账；stream delta未复核。
