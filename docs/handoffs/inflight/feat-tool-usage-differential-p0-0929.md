# 在途交接 · feat/tool-usage-differential-p0-0929

2026-09-29；隔离树 `/Users/a77/fwp-wt-tool-usage-audit-0929`，基线 `gitea/main@2b66c3740`。认领 `R-20260827-14` **P0 离线审计**，不碰运行时、生产库、工具路由与 P1。完整读数、偏差与原件路径见 `../2026-09-29-tool-usage-differential-p0.md`。

## 当前状态

已加只读脚本、定向测试与三组聚合报告；3P、Ruff 绿。历史 08-27 当前根有 **748** 份（原工单 747），多一份探针；output 差值 **425** 与原表逐项相等，但 suspicious 1198 vs 1193。历史 run 没有代码 revision，报告明写 `UNAVAILABLE`，未伪造跨版本范围。**原单的“同一样本四组数/代码 revision 跨度”尚不能签满，不能把本单标 done 或合主干。**

## 下一步

独立审查：固定原 747 份 manifest 或裁决样本漂移，找到可靠 run→revision 映射或明确接受回溯缺失；逐条变异验证、完整门禁与收据自证后才解除 WIP。勿把差值当模型质量结论，不要并行开 P1 在线遥测。
