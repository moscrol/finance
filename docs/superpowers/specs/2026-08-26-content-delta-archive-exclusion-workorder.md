# 工单：agent-daily content-delta 被自产归档撑爆的结构性修复（2026-08-26）

- 状态：**待认领**（连续两晚人工 park 后立单；动手前先 grill 归档目录的全部读取方）
- 来源：08-25 与 08-26 两晚 `agent-daily` 均因 `content delta exceeds maximum size`（10MB cap）失败，
  均按 `skills/daily-full-review/references/ops-pitfalls.md` 的 park 手法人工救回（08-26 晚 park 后 21s 全绿）。
- 撑爆源（08-26 实测）：`wiki/raw/disclosures/review-queue/reports/` 6.2M + `wiki/raw/cross-repo-ingest-queue/` 6.3M，均为**未跟踪**且**每日增长**。

## 根因结构（不是偶发脏区）

`build_content_delta` 的保真契约是「相对 HEAD 的改动 + 未跟踪目录都进快照，gitignore 不能缩小 delta」。
但这两个目录是**复盘管线自己每天写入**的归档（L3 报告、kb-queue-receive 归档），次日又被自己扫描——
**自产归档变成自己的 delta**，体积单调增长，park 手法会从「偶发救火」退化成「每晚必做的仪式」。
今晚已是连续第二晚，不修则天天人工。

## 选项对比（认领时择一，勿混做）

| 选项 | 动哪侧 | 优点 | 代价/风险 |
|---|---|---|---|
| **(a) 归档迁出 wiki 扫描面**（推荐） | 写入方：`kb-queue-receive` 归档落点、L3 reports 落点改到知识库根外（如 `<KB_ROOT>/archives/` 或 finance 仓 exports） | 归档本非「知识内容」，本就不该在保真快照面里；契约零开洞 | 跨仓改动；**必须先盘点读取方**——cross-repo-ingest-queue 是 concept-ingest 人工 ingest 的输入位，挪走要同步改该 skill 的指针 |
| (b) `build_content_delta` 排除清单 | 读取方：named archive dirs 显式排除 | 改动最小 | 给保真契约开洞；「排除清单」会被后来者继续加长（棘轮反向） |
| (c) 调大 10MB cap | 配置 | 一行 | ops-pitfalls 明令禁止；只是把爆炸日期后移 |
| (d) 编排器自动 park/unpark | 编排层 | 契约零变化 | 把丑手法固化成机制；park 期间快照对这两个目录**假装不存在**，与 (b) 等价但更隐晦 |

## 验收判据（预注册草案，认领时正式化进台账）

- 连续两晚夜跑 `agent-daily` 不 park 直接过（delta 回 ~3MB 基线，08-25 park 后实测值）。
- concept-ingest / 其他读取方对归档新位置可达（如选 (a)，迁移当日跑一次该 skill 的消费路径核对）。
- 失败形状：迁移后 delta 仍逼近 cap（= 还有第三个自产增长源，重新盘点写入方）。

## 不要做

- 不要在复盘补跑现场顺手改（本单是结构修复，走自己的分支和测试）。
- 不要把归档 commit 进别人的知识库分支（两晚的知识库都在 `fix/rss-l3-auto-promote` 上）。
- 选 (a) 时不要只挪目录不改写入方——那只救一天。
