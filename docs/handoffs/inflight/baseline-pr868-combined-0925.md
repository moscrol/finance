# #868 联合候选离线门禁

## 这个分支做什么
独立树组合 main d217 + #910 2d7b + #911 6c6a，交原 owner 审阅采用；不接管独审/L6/生产授权。

## 当前状态
受测候选 `adbe0ba11822f02530def67e4c375af28f6e23f2`；本交接是后加文档，不继承整仓收据。owner 仍89624eac7、树干净。运行/临时服务已结束，无新付费、未合main/部署8792。
完整决策与证据：`docs/handoffs/2026-09-25-pr868-combined-offline-gates.md`。

## 决策与被否方案
| 选了 | 否了 | 理由 |
| --- | --- | --- |
| 新树冻结组合全量验 | 加总旧收据、改owner树 | 身份与并发边界 |
| INDEX按原报告纠偏 | findings空就撤补验 | reason仍要求行为证据 |
| 原件格式问题单列 | 修剪封存日志求绿 | 不改证据字节 |
| 只读定位C3探针接口 | 改封存探针、续旧预算 | 独审需新运行身份 |

## 未验证 / 已知边界
adbe尚无独审。同期另一会话c3c7只签f261：spec C7 verified但有limits，C3未验，终稿BLOCKED_INCOMPLETE_EVIDENCE；账目315/320不归本分支。跨批/跨轴汇总不改各轴结论。
L6自然金融质量、真实模型自主研究、真来源/子研究/反证修订及8792身份均未验证。完整PR diff格式exit2，8个继承封存文件有空白；相对owner原件无差异，不据此豁免检查。

## 下一步
1. owner审阅采用组合；原#910/#911保持WIP。
2. 冻结最终候选，在全新根重绑输入/环境并另取独审预算；逐轴补证，不能直接启动保留历史配置的repair生成物。
3. 独审后另批L6；最新组合门禁、main合入、部署分开授权。

## 踩过的坑
首轮负载8.761>8零测试，另根准入不提阈值。C3旧探针把list.append当observer，headers的status=参数触发TypeError；仅复现签名错误，未重跑独立探针，见#868评论6961。内层C3/C7计数不重复加总。

## 已验证
锁定`~/fwp-wt-pi-research/.venv-workbench/bin/python`，3.12.13/httpx0.28.1/指纹66726d345bf37ce5。adbe Ruff/全仓15969P、0F/E、88S、2X，收集16059，精确full-scope收据通过；前端120P、E2E34P/2S、registry五项绿。沙箱双轴C3各3P/C7各66P仅作者检查。
根`~/.finance-runtime/reviews/pr868-combined-20260925/attempt02/`；收据`receipts/gate-4Qw8d2n1/pytest.json`；内层`inner-author/`，JUnit逐例保留。
