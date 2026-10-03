# Harness预算获批后的零模型预检 — 2026-10-04

## 背景与范围

用户对“独立Spec/Standards复审＋首批最多12格真实Workbench预验，新增总支出上限人民币50元”回复**批准**。这是共用总额，包含作者、核验、修复、子研究、判卷、失败和重试；不是每项50元。原“验收通过后上线”的条件授权保留，预算批准不等于质量或发布通过。

产品pin仍为`25de6994bdb79b57e9cf06fcb81f6f5796c67079`。本轮起始文档头`dfe3a666bcf74e7da7e531b4df91b20a30190a1a`，重新fetch后main仍为`108835e27d2e926ffd95077536badb6d061ea096`。PR #30仍Draft/OPEN/CLEAN，无auto-merge；起始文档头的五项检查已成功。25de完整工程门禁保留在前轮封口，本轮没有重跑或转签。

新证据根：`~/.finance-runtime/reviews/harness-budgeted-preflight-20261004/`。先读其中`approval.md`与`preflight-findings.md`；旧`harness-release-20261004/`、`harness-integration-20261003/`不覆盖。

## 按发现顺序

1. 读取任务与评论、Git/PR、远端主线及既有预算入口。FINANCEWORKS-3从blocked恢复in_progress推进预检。首次并行命令依赖另一路建目录，四处重定向失败；随后串行建目录重读，失误记录在approval.md。
2. 脱敏核对launcher：内置与普通LLM都走智谱`/api/coding/paas/v4`，请求模型分别为`glm-5.3-flash`和`glm-5.3`。只读配置不是回包身份，未改生产。
3. 核对[官方Coding FAQ](https://docs.bigmodel.cn/cn/coding-plan/faq)：自建应用应使用标准API，指定工具外不能享用Coding额度。“套餐耗尽不扣余额”不能拿来证明Workbench免费或有50元硬帽。
4. 取得[官方API价格](https://docs.bigmodel.cn/cn/guide/start/pricing)：flash输入/输出0.8/2.8、glm-5.3为8/28元每百万token，缓存命中分别0.23/2。保守预算不依赖优惠或缓存命中。仓内`glm-5.3*`旧通配价不能当flash实价；本轮未顺手修改产品报表。
5. 官方财务页跳到登录页，实际账户余额/资源包/收费协议尚未知。已请用户在日常Chrome登录`https://bigmodel.cn/finance/overview`后回复“已登录”；不索要密钥或验证码、不充值。关闭本轮新建两页签，用户原页签不动。
6. 零模型复验既有调用预占与代理取消测试，33项通过；另用真实payload构造器＋假响应＋socket/subprocess拒绝钩子验证16种组合：agent两入口及通用chat默认不带`max_tokens`，合成入口的显式帽不传播。现有`LLM_REASONING_EFFORT=low`能统一启用两模型要求的思考模式，无需为此改产品代码。
7. 现有调用台账是每turn物理尝试帽，研究root账本是工具次数/时间帽；两者都不是本批共享人民币预算。旧K3代理及F4缓冲运输也没有该能力。尚未建立每次出站前覆盖输入/输出及推理、失败/重试、独审和判卷的保守货币预占，停止在首次模型请求前。

## 决策与被否方案

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 在隔离实验中核对标准API账户及计价，再补共享准入 | 符合自建应用接口范围，费用前提可查；仍需账户登录和实现硬帽 | 选，未启动 |
| 把Coding套餐视为Workbench免费调用 | 适用范围不成立；也没有账户扣费证明 | 否 |
| 仅设调用次数、900秒超时或合成输出帽 | 无法涵盖单次默认长输出、推理token、所有子调用及断线后计费 | 否 |
| 使用Claude的美元预算选项直接复审 | 没证明它按真实GLM账单在运输前预占；历史CLI估价未知 | 暂不启动 |
| 缺usage按0结算，出账后再停 | 已发出的请求可能已收费，事后控制不保证总额 | 否；保留未知及预占 |
| 顺手改生产通道、产品预算层或重开旧实验 | 扩大本轮范围，改变已验产品及冻结实验 | 否；先完成独立预检 |

## 验证与证据边界

- `budget-audit/offline-enforcement.log`：33 passed，exit0；收据`budget-audit/test-receipts/20261003T230241Z-dfe3a666-45a513eb55f0.json`，HEAD=dfe、dirty=false、Python3.12.13、依赖指纹`66726d345bf37ce5`。目标为运输预算、调用来源与K3假上游测试，固定SHA收据审计通过，**不是全量**。
- `budget-audit/probe-payload-controls.py`及`payload-controls.json`：16个作者离线断言、Ruff通过；没有发真实请求，不证明实际Workbench或所有子调用已被货币闸覆盖。
- `pricing/`保留公开资料、浏览器价目表、登录阻塞及关闭页签回执；静态pricing抓取exit56亦保留，成功结果另存。
- `status/launcher-public-fields.json`只含白名单配置及源哈希，无凭证、未执行launcher；`intake/pr.json`绑定起始文档头，不转签本次文档提交的CI。
- 本轮新增产品模型请求0、独审请求0；无新增模型调用费用。历史审查费用不归零，当前主会话宿主账单也不由此推断。
- 生产软链仍指`finance-workspace-ffe1c60d84da`；未合入、未部署，此观察不代health/readiness。

## 接手顺序

先读最新任务版本/评论和本轮树外状态。用户登录后只读核对标准API账户；在现有运输入口实现并离线验证共享硬帽，逐次预占物理请求、token、时间与CNY，封住直连/CLI旁路。无法建立保守上界继续停止，批准不会过期变成无上限。

之后才冻结题目、完整多轮脚本、数据快照、同模型同权限同预算、6对AB/BA各3对顺序、串行间隔、匿名全文评分及停止规则，走`claim_ledger_id.py`预注册。最多12格，不保证50元能跑完；失败保留，不补跑选优。新Spec/Standards仍未完成，12格不代正式质量门；R17/R19/240、共享Memory及其他活动树不动。

## 工具归位

复用仓内测试和HTTP构造器，没有另造实验运行器。树外payload脚本是绑定本版本私有函数的作者诊断，暂不升格为通用工具：缺的货币准入仍须实现并验证，文档与诊断不能冒充补洞。共享harness-reference及旧封口脚本只读不改。
