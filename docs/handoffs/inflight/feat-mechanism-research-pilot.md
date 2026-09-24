# 机制表示研究

更新2026-09-16；树 `/Users/a77/fwp-wt-mechanism-pilot`，分支 `feat/mechanism-research-pilot`，base c29a64011da4。

## 这个分支做什么

比较逐条整理与机制组织。R04为同材料合成诊断；用户要求8792后，R05为两场真实产品会话观察。

## 决策与被否方案

- 不改生产提示词/个人框架，否直接部署：研究优势未证实。
- 一次占位保留失败，否重抽选赢家；复用存储原语，不伪装收益合同。
- R05路由/材料不同，只作描述，不判机制胜。
- 决策与结果：`docs/verification/2026-09-16-mechanism-pilot-live.md`、`docs/verification/2026-09-16-mechanism-workbench-live.md`；首片背景见 `docs/handoffs/2026-09-16-mechanism-research-pilot.md`。

## 当前状态

全部代码/题包/报告/台账未提交、未推、未合、未部署；不默认提交实验。原树他人改动未碰。

R04：12调用12答卷0失败；下一证据两组6/6，反证集合逐条1/6机制2/6，均未漏gold反证，两组有无依据阈值。无优势结论，原分数不改。原件 `~/.finance-runtime/mechanism-pilot/R-20260916-04/`。

R05：通过8792 conversations及messages完成2场；run均completed、research均partial；采集进程14101已退出。生产db2963d4fbaa未改。工具14/15次，含空结果/报错。原件 `~/.finance-runtime/mechanism-workbench/R-20260916-05/`；入口 `intelligence/eval/mechanism_workbench.py`。

发现：summary路由stock_deep_dive、mechanism路由kol_review；机制组选错最近两期、混经营/投资现金流，判官passed仍漏检；summary无依据历史阈值残留。拒绝长期跟踪仍在隔离summary用户写4条checkpoint，含错日期。测试用户未删，未审计后台对其后续处理。

## 已验证

R05新增6项+R04的37项=43P；收据 `~/.finance-runtime/test-receipts/20260916T143958Z-c29a6401.json`。目标ruff、diff检查通过。R05协议/代码/两receipt/12份文件摘要核对，API最终消息与answer.md一致；服务仍健康。此前180P不是本轮全量收据。

## 未验证 / 已知边界

R04合成天花板；R05作者选题、非盲评、检索未固定、路由不同。未独立核验全部财务事实，未认证研究/预测/收益优势。未跑浏览器/全量pytest/前端，未改生产缺陷。供应商实际模型与token成本未测。

## 下一步

读R05报告后另立修复：禁止跟踪的写入门控、题型/报告期稳定性、现金流类别和证据来源校验；新样本复验。两批均不重跑挑赢家，不改冻结采集代码后续跑旧批。R04复算只用report。

## 踩过的坑

完成请求不等于完成研究；有E号不等于公告原文，网页评论可能混入。工具ok可能仍为空表/脚本错误。E号从tool_result的evidence_id读，不按outcome列表下标推。R05按真实轨迹核对，不信答案自述“两次PDF失败”。
