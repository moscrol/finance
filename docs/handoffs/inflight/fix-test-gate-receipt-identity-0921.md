# 每轮测试收据身份

## 这个分支做什么
修主门禁共享latest串轮、失败读回、嵌套pytest抢父收据与只读模式tree漏验。

## 决策与被否方案
- 唯一不可覆盖文件；否决latest作本轮证明。
- configure先认领owner；否决结束才认领，子pytest不写父文件。
- tree在执行/只读/基线比较都核；否决用有无进程退出码决定身份检查。
- 新组合新收据；否决向文档尖移签。前史见`2026-09-21-test-gate-receipt-identity.md`。

## 当前状态
新码cdf6647cf已推原WIP #814；未合main。v1 321712b6失败、v2 e1b63b1a历史作者绿保留。
新固定组合47530e20已推baseline/ownership-gates-v3-0921，独占树冻结。它包含#812来源6c74fa012、#813来源5994230d及本代码cdf6647cf。后续交接文档不推进固定树、不继承该收据。
完整续轮在协调树`~/fwp-wt-ownership-closeout-0921/docs/handoffs/2026-09-21-ownership-resume.md`；86文件归档在同树`docs/verification/2026-09-21-ownership-resume/`。

## 已验证
只读路径7例旧版7F/28P，修后相关56P；cdf6647cf干净源码尖真门禁56P。合法历史收据新helper读回0，旧零计数收据仍4。
47530e20全量12068P/85S/2X，前端110P/E2E34P2S，lint/typecheck/build、finance-only registry五项0；三叶前后净树同SHA。唯一全量`v3/python/receipts/gate-Idx5hl80/pytest.json`，回读/条件校验0。全叶只签47530e20。

## 未验证 / 已知边界
没有独立Spec/Quality或合入授权。PID只隔离合作进程，不是同用户恶意写者沙箱；首尾Git身份不证明中途未改后还原。只读gate要求当前树绑定，通用check_test_receipt的跨树相容性检查是另一用途。

## 下一步
按协调树新review-request对47530e20获授权独立复核，未发自动队列。main或代码漂移须新组合新门禁；三单和组合不可重复合。生产、服务、删树分别确认，旧失败原件不得补写求绿。

## 踩过的坑
随机名只挡平级并发，owner需启动前认领；树身份是所有模式的不变量，进程退出码仅是执行模式的附加条件。通用规则回写既有知识笔记与harness PR14（7b40fe0）。
