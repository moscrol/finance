# Workbench 组合发布：数据 HOLD

## 这个分支做什么
组合行情保护、RAG 与 Workbench 修复，核对生产恢复及发布条件。主树不动，未合 main/部署/换库。

## 决策与被否方案
| 采用 | 否决 / 理由 |
|---|---|
| 历史缺名保留未知，streak 真消费才拒绝 | NULL 转 False 会虚构断板；全窗口校验又会误伤无关旧行 |
| 工程、真实入口、数据门分账 | 代码绿和 health200 不能抵消日期错位 |
| 完整身份门保持阻断 | 历史候选、相同行数不证明当前成员身份 |
展开：`../2026-09-24-workbench-release-engineering-green-data-hold.md`。

## 当前状态
受验代码 `eb4ec08f0680f9ba8cdaf5f3e8a95be34861b12a` 已推 Gitea；基座 `3bb81b9638f9`。当前后继仅写交接，不把 eb4 收据移签它。
PR #900 只是协调入口，head 仍为另一分支4255207a。FinArena #82 已封存，不重开。
生产仍3b7e473575b0，DB inode216161353/size3855626240/mtime_ns1790168645608937291未变；health200/readiness503。无正式 staging、生产写入或L2处理。本轮长测已全部自然结束。

## 未验证 / 已知边界
80/403板块缺113个成员位置；49有历史候选但未认证，31无候选。9/22原新浪捕获确在当日02:12，但不是交易时点证明，且缺301686/689009/920229。正式恢复参数尚未接入三日staged编排，完整数据/same-day/cross-day/L2未关。
自然问答完成且无内容降级，但readiness前后503：快照9/23、市场库9/22。索引source_dirty和legacy CLI缺可选receipt仍披露。独审做过未采用并行提案，非盲审；旧失败不翻案。

## 下一步
等待新增来源授权：一个缺员板块按原历史日期只读取证复盘会；不重启夜跑，未答复不请求。五问三合同不重问。
闭合身份、逐日名称/IPO/停复牌/参考价，再接正式恢复编排并验新SHA。重取生产基线后才clone_to_staging；全部数据门、备份、原子换库和独立验收通过，再等合并/部署确认。

## 踩过的坑
bool(None)不是确定非涨停。文件加工时间不是源观察时间。2ddd首次checker误用--receipt-dir为调用错误，原件保留；更正后rc0。磁盘约43GiB不代表解压峰值已算清。

## 已验证
证据根 `~/.finance-runtime/reviews/workbench-release-20260924/`：`history-candidate/full-receipts/gate-Zgg3Ayou/pytest.json`。eb4干净树，15171 collected，15084P/0F/0E/85S/2X；固定解释器/依赖3328bed61f3e21ea，full-scope/根目标/0基座漂移checker0。前端123P、E2E34P/2S、五项registry均0。
相关207P；原独立历史探针旧2ddd为6F/3P，新eb4回放9P。相邻`workbench-release-20260924-independent/eb4-live/`封存35项变异及一次真实Episode结果，整体仍HOLD。
