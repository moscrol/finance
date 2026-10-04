# docs/harness-arms-smoke-1004 在途交接（2026-10-04）

## 这个分支做什么
记录 #40 上线与 G 列冒烟（GLM 用 8792 对比 GLM 用 Pi）。全文见 `docs/handoffs/2026-10-04-deploy-post40-and-harness-arms-smoke.md`；
预注册追加了 10-04 修订。

## 决策与被否方案
| 采用 | 否决 / 理由 |
|---|---|
| 部署 main tip bd2c58b37，在快照里重跑全量 | 否「拿 PR 头收据」：规程不许 |
| Pi 只挂一个 finance_call 工具 | 否 sandbox 黑名单：答案散在多处，堵不全 |
| 控制台组件钉 bd2c58b3775f | 否沿用 40fd：与 P 不同码 |
| Pi 是新增变体，R 仍是 thin_react.py | 否「Pi 即 R」：先前误写，已更正 |

## 当前状态
8792 已在 bd2c58b3775f（含 #40），三验与探针全过。G 列只冒烟了 D1：Pi 7/7，P 6/7（n=1）。批量未启动。本分支未合入。

## 已验证
门禁 20399/0 收据可采信；前端门禁可采信；材料题切前 3 轮、2 拒，切后 1 轮、0 拒；长电口径与数据日正确；gitea 备份 OK。

## 未验证 / 已知边界
- P 把盘面题分流到 workflow，不走 Episode；P 的模型随路径变（材料题 glm-5.3，其它 flash）。
- F3：Pi 只记错配；P 的 workflow 没有 served_model，准入 exit 2。
- arena 臂隔离只能靠遵守。

## 下一步
1. 用户定：分流处理、模型钉法、两臂或三臂、预算。
2. 补 F3 后冻结各臂哈希，再开 G 列批量。
3. 用户重启 arena，交 `ARENA-ARM.md`。

## 踩过的坑
- 从 origin/main 切出的分支上游是 main，推送要写全分支名。
- 恢复判分器的 main() 会覆盖旧 analysis/，只 import 用 score_case。
