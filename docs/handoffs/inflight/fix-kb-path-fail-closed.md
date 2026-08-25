# fix/kb-path-fail-closed

## 这个分支做什么
已合 #379。本文只留合后消费指针。

## 当前状态
#379 @ `1b81728d`。主仓脏树不要碰。光通信五家已查：太辰光 `0001` + 云南锗业磷化铟合同 `0002`，均 archive-only。任务仍 received。

## 未验证 / 已知边界
- 未 apply、未钉发布树。
- 合同客户豁免、金额是区间，不能当已确认收入。
- KB 主检出仍脏，只追加本刀归档/报告。

## 下一步
1. 8/17 CPO disclosure（先长电/通富，勿重扫太辰光/旭创/天孚）。
2. 太辰光拿地、锗业交货后再升 realized。
3. `fact_status` 等 KB 那支合 main。

## 踩过的坑
- 巨潮 `gssz0{code}` 会空结果；orgId 要查 `szse_stock.json`。
- 「有概念页」≠ disclosure 已补。

## 已验证
#379：ruff / 6420P / webapp 绿后合入。

## 工具沉淀
出队门已在 #379。orgId 查表未抽脚本（一次对照）。
