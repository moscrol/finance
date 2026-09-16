# E2 P3e：QueryResolver 词典早读闸门独立审查收口

## 背景

E2 材料边界按 v10 拆片推进。P3d 已先关闭 `TurnOrchestrator` 在 Episode 组装前读取旧答案产物、stance pack、研究项目先验和视角的四个生产者；但 controller 更早的 history/context 与 resolver 词典早读仍是独立缺口。本轮只处理后者，避免把“controller 前置读取”“QueryResolver 词典”“可信继承”等不同副作用边界合成一个无法归因的大 P3。

作者在 `0b83e14f` 将 `QueryResolver.resolve` 改为在实体/主题/证券词典入口之前复用既有 `split_user_message` 与 `compile_material_contract`。明确 `material_only` 时仅走既有文本理解，不访问词典、证券名单或其缓存，也不把词典验证出的 anchor/candidates/comparison_entities 带入；普通、full、local_only 保持既有解析。该实现不新增禁令短语表，不把未知边界或“继续”一律改成澄清。

## 发现与决策

1. 独立审查先校验固定 revision、应用差异、作者 README/commands/manifest、产品门及 D1/D2/D4/D7/A13–A17 设计约束；未改应用、测试、题目或评分。
2. 首次 focused 启动器因比较未 resolve 的 `/tmp` 与 macOS 实际 `/private/tmp` 失败，误拒 41 次合成 DuckDB 连接，得到 36 errors/5 failed。该失败属于审查器夹具，不是产品失败；保留原启动器与日志，不用修正版收据抹除它。
3. 修正版只对 DATA 根做路径 resolve，并维持生产路径拒绝、临时 DB 白名单与 native DuckDB connect 包装。focused 原样作者测试加独立补针为 41P，相关八文件回归为 347P，两者禁止 IO 尝试均为 0；两个改动 Python 文件 Ruff 通过。
4. 独立补针不导入作者测试，使用合成实体/材料，覆盖受限冷/热解析、允许路径真实 KB/DB 读取及普通表达。相关回归不是完整作者 453P 的替代收据，API 导入隔离红针仍不纳入通过声明。
5. 结论为 P3e 通过，仅限 QueryResolver 词典早读闸门；不外推为完整 P3 或 E2 全链。报告、失败/修正版证据、收据和 SHA-256 已归档到 `docs/verification/e2-boundary-closeout/p3e-query-resolver-20260915-independent-qc-20260915/`。

## 收据与边界

- `report.md`：独立裁定和逐项覆盖。
- `evidence/focused.log`：首次失败；`focused-v2.log`：41P 修正版；`regression.log`：347P；对应 IO、exit、启动器、独立补针均保留。
- `evidence/manifest-check.json`：固定源文件哈希匹配；`final-head.txt` 为 `0b83e14f...`；`sha256-manifest.txt` 为归档文件哈希索引。
- 产品门已更新：`docs/agent-product-door.md` 明示独立通过、41P/347P、首次误拒41次及“仅限本片”。作者收据 README 也已标为独立 QC 完成。

本片仍不覆盖 controller 前 history/context、静态路由/简称/日历先验、注入式 resolver、预取前歧义与不可恢复基底澄清、可信续轮、四组九类来源过滤、恢复/压缩/子研究/非工具 provider 事实、确定性/legacy 回落、交付后读取及 P4–P7。正式 T2→T3/Knevo 暂不运行。

## 下一步

归档本片后再决定下一片；若继续 v10，先单独勘界 controller 前 history/context 与其 QueryResolver 早读交界，冻结题目和覆盖声明，作者收据后再做独立 QC。不得把本片收据当全链隔离或正式 PK 前置许可。
