# fix/kb-path-fail-closed

## 这个分支做什么
#379 已合。合后消费指针。

## 当前状态
光通信五家 + CPO（长电/通富）已查。归档在干净树 `disclosure/optical-cpo-0825`，不等脏主检出。任务仍 received。

## 未验证 / 已知边界
- 未 apply、未钉发布树。
- CPO 无点名公告；长电临港 78 亿是先进封装，未塞进 CPO。
- KB 脏树 `fix/rss-l3-auto-promote` 里别人的实体/RSS **没动**。

## 下一步
1. 8/17 先进封装（长电临港工厂进展可归档）。
2. 太辰光拿地、锗业交货后再升 realized。
3. `fact_status` 等 KB 那支合 main。

## 踩过的坑
- 脏树只追加、不提交；本刀用 `gitea/main` 干净树 pathspec。
- 标题无 CPO ≠ 没有先进封装。

## 已验证
#379 已合。KB 本刀 5 文件已推。

## 工具沉淀
无新脚本。
