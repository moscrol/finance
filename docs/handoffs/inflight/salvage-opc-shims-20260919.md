# OPC shim 封存 · 2026-09-19

## 这个分支做什么
只保全脏主树三个指定shim的原字节，供恢复/审计；不是修复候选。

## 决策与被否方案
选`.py.txt`档案而非覆盖运行源码，避免回退新main或把旧shim装成实现。不提交整个Codex检查点，不清理他人工作树。

## 当前状态
档案提交`1cc7fb140a92efd3bad637c3dc62f351bb6b9ab8`已推Gitea。三个原文件与提交内档案逐字节一致；其后本枝仅补本交接。
文件/manifest/原因见`docs/verification/2026-09-19-opc-shims/README.md`。

## 已验证
提交门禁通过；manifest记录每文件字节数/SHA-256/Git blob及原路径。09-18 finalize日志/工作流摘要确认实际用冻结生成根387028b846a2，不依赖这三份shim。

## 未验证 / 已知边界
封存不认证shim运行正确，也不证明其他入口无依赖。不清原主树，不合main，不部署，不替#50源码合流验收。

## 下一步
本枝无实现工作。需恢复时仅向新隔离目录还原并核manifest，再审查用途。整体收口接续`q/research-data-readiness`，本轮QC发现误删可信句阻塞，见其`docs/handoffs/2026-09-19-t3-convergence-qc.md`。

## 踩过的坑
工具临时tree/checkpoint不是正式提交备份；旧主树相对新main的大删除不是本轮删除。部署身份看代码根和执行日志，不只看WorkingDirectory。
