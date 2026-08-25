# fix/kb-path-fail-closed

## 这个分支做什么
已合 #379。本文只留合后消费指针。

## 当前状态
#379 @ `1b81728d`。主仓脏树不要碰。合后消费在 KB 活库：太辰光坪山基地已 archive-only（`disc-20260825-0001`），光通信任务仍 received。

## 未验证 / 已知边界
- 未 apply、未钉发布树。
- 云南锗业 7/24 合同 PDF 未拆。
- KB 主检出仍脏，只追加了本刀归档/报告。

## 下一步
1. 拆云南锗业 7/24 合同，主题相关再归档。
2. 太辰光拿地/出让合同后再考虑升 realized。
3. `fact_status` 等 KB 那支合 main。

## 踩过的坑
- 巨潮 `gssz0{code}` 会空结果；orgId 要查 `szse_stock.json`。
- 「有概念页」≠ disclosure 已补。

## 已验证
#379：ruff / 6420P / webapp 绿后合入。

## 工具沉淀
出队门已在 #379。orgId 查表未抽脚本（一次对照）。
