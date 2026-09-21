# 日期差异说明策略

## 这个分支做什么
按各来源实际日期交付真实金融事实；日期不一致只做诊断，不整体拒答。

## 决策与被否方案
- 查询上界用 information_cutoff，否了总览日封顶各表；未知不猜、NULL不补0，比较另核期间/单位/口径。
- K3真实验收走 conversations/messages，否了CLI代签；作者工程、自然答卷、独立审查分账。
- 不因一份自然答卷未越界就认定守住截止：保留只读对抗复现；不边验边改固定候选。
- 展开：`docs/handoffs/2026-09-21-market-date-k3-live.md`；旧决策见同目录`2026-09-21-market-date-advisory.md`。

## 当前状态
受测运行HEAD `786a3b627`，运行代码与c57ec654相同；首尾干净。本轮仅追加作者真实验收记录：`AUTHOR_REAL_ENTRYPOINT_OBSERVED_NOT_ACCEPTED`。证据提交`110b4afe5`后Git对象核验新68/68、旧200/200通过。未push/PR/合main/部署，未补采或写生产库。

## 未验证 / 已知边界
- 当前题错说“本地尚无09-21行情”：readiness已见09-21 fresh/complete快照，Episode实际只交付至09-18的DuckDB事实。local_only不应放开可能联网的工具来补洞。
- 历史题自然证据均≤09-11，但context cutoff仍09-21/runtime_default，history_intent=null。省略日期或直查09-18均返回09-18，系统未强制用户上界。
- 两题judge unavailable/business partial；没有新独立Spec/Quality，没有完整首轮prompt正文（仅hash/字符数和事件），不签产品质量。
- N=1/题，不能比较改善率；未验后来main组合、前端浏览器展示或自然夜跑。其他在途分支不接管。

## 下一步
先修明示截止解析/合同与本地来源可见性，再固定新SHA跑定向反例、完整门禁、真实K3答卷及独立审查。保留local_only授权；不得以展示标签或模型自选日期代替底座校验。合入/生产操作仍需确认。

## 踩过的坑
- “当时A股市场”被路由为company/stock_deep_dive，属于另一个待修问题。
- citation源名经展示sanitizer改写：原标签五条不匹配，经实际转换后15/15与13/13可回溯，不是失证，也不证明每句推论正确。
- 06de误中止理由已勘误；旧工程收据不移签新源码或文档版本。

## 已验证
两真实run completed，K3共7模型轮/15工具调用，证据均local_read；当前48条、历史119观察/118唯一hash。只读对抗复现确认截止缺口。19276已关，8792首尾身份相同；选定DB审计相同，非整库校验。
新证据`docs/verification/2026-09-21-market-date-k3-live/`：65文本原件/68内容文件及SHA清单。原始脚本冻结为.py.txt，不作为通用运行工具。
旧c57作者门禁：12551P/85S/2X、Ruff0、前端110P/E2E34P2S、registry五项0、11变异；原200内容归档不改。只签固定候选工程，不代签本轮质量。
