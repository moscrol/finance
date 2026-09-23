# #86/#87 合并收口

## 这个分支做什么
完成 #86 部署帮助 fail-closed 与 #87 晨汇消费 source→label→teaching object→river 验收修复，并合入当前 main。

## 决策与被否方案
- 用 `6401dc3c1` 接替旧 #846/#847，否了合旧 WIP head；新 PR #902 已合入 `3bb81b9638f9`。
- KB #157 先独立审查后合入 `a2cfb2b8d963`；finance 只读消费不替代 #61 数据恢复。
- 同 landing 的 material days 按 `briefing_daily` 完整聚合；否了按单 material day 报 `source_rows`，避免审计输入与 expected 不一致。

## 当前状态
finance #902、KB #157 已 merged；#846/#847 已写接替指针并 closed。当前代码无未提交改动。未部署、未重启 8792、未抓 IMA、未写生产 DuckDB/标签、未发布数据。

## 已验证
- finance K3-r4 PASS（6401，19 请求，40 targeted passed）；KB K3-r4 PASS（f4b，21 请求，extractor 1338 行一致）。
- 分支 full Python：6401 收据 `gate-ukMPqDRw/pytest.json`，14886 passed / 85 skipped / 2 xfailed；clean、full scope、base drift 0。
- 合后 main `3bb81b9638f9` 四叶：Python `gate-ztYypNq8/pytest.json` 同上；frontend 六步 exit0、`frontend/frontend.json` identity_stable=true/dirty=false；registry 五项 exit0。
- 合并记录：`finance-merge-902.json`、`kb-merge-157.json`；合并树与预览树一致。

## 未验证 / 已知边界
#61 生产只读数据核查仍 INCOMPLETE；没有 live 恢复证据。ordinary 仍 `trade_date_only`，strict 只过滤 teaching object 的 recorded_at，不是全市场历史冻结；summary object 不是全文 briefing RAG。独立报告仅为离线证据审查。finance PASS 留有非阻塞 P3：重复 label 有代码检查但无专门注入测试；rsync 非原子是基线风险。

## 下一步
若继续推进，只能先取得 #61 的具体恢复命令、日期、备份/回滚点和生产写入授权，再做 live 验收；否则保持当前代码合入、数据与部署不动。

## 踩过的坑
旧 b956 full gate 在编辑期间运行，虽 14886 passed 但 dirty/身份变化，不能采信；只认 6401 分支 gate 与 3bb 合后 gate。临时合并 CLI worktrees 已移除，审查树与收据保留。
