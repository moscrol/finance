# E2 P3e：QueryResolver 词典早读闸门独立审查归档

固定应用 revision：`0b83e14f5c6e664772d617f075a24911f16f7547`；父提交：`39af312f51fa73f7a3db3b7f8c1fa8f8420213c9`。
独立报告裁定：**通过，仅限 P3e 词典早读闸门**。这不是完整 P3、E2 全链、合并、部署或正式 T2→T3/Knevo 许可。

## 独立收据

- 修正版 focused：作者测试 + 独立补针 **41 passed**，禁止 IO 尝试 **0**，pytest/shell exit **0**。
- 相关回归：**347 passed**，禁止 IO 尝试 **0**，pytest/shell exit **0**。
- 两个改动 Python 文件 Ruff：**All checks passed**，exit **0**。
- 首次 focused 启动器失败保留：**36 errors / 5 failed**；因 `/tmp` 与 macOS resolved `/private/tmp` 比较错误，误拒合成 DuckDB 连接 **41 次**。修正仅 resolve DATA 根，未放宽生产路径；该失败不抹除，也不作为通过依据。
- `manifest-check.json` 复核归档源文件与固定工作树字节哈希；`final-head.txt` 固定最终 revision；`final-status.txt` 为空表示工作树 clean。

报告逐字节保存于 [report.md](report.md)，审查输入于 [qc-prompt.txt](qc-prompt.txt)，单次启动记录于 [launch.json](launch.json)。完整证据在 `evidence/`；本目录的 SHA-256（不含 manifest 文件自身）见 [sha256-manifest.txt](sha256-manifest.txt)。

## 范围限制

本裁定只证明 `QueryResolver.resolve` 在明确 `material_only` 时，于实体/主题/证券词典及其缓存读取前复用材料合同，并沿既有文本理解路径返回；普通、full、local_only 的既有解析保持。未覆盖 controller 更早 history/context、静态路由/日历先验、注入式 resolver、可信继承、来源过滤、恢复/压缩、交付后读取及 P4–P7。不得将 41P/347P 外推为完整 P3，也不得据此运行正式 T2→T3/Knevo。

原始失败、修正版日志、启动器 v1/v2、独立补针和 IO 计数均保留，未为展示而修剪或重跑。
