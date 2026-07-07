# Marketing Agent Chain P0 Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Execute task-by-task, commit per task, tick checkboxes as you go.

**Goal:** 按 spec `docs/superpowers/specs/2026-07-05-marketing-agent-chain-design.md` 落地 P0：素材事实库 + 首批 brief + 首批产品介绍内容 + 效果台账 + schema 校验。

**定位约束：** 内容以介绍产品为主线（产品是什么、能做什么、怎么用），教学向仅辅线（≤20%）；证据先于文案；不承诺收益；人工发布。

**Tech Stack:** 纯文档 + YAML/JSONL + Python 标准库校验脚本（P0 不建索引、不接平台 API）。

---

### Task 1: 数据契约骨架

**Files:**
- Create: `docs/marketing/README.md`（目录说明、写入者、与 spec 的关系、Review Gate 摘要）
- Create: `docs/marketing/products.yaml`（finhot / finance_agent，含 public_boundary can_say/cannot_say）
- Create: `docs/marketing/features.yaml`（每产品 3-5 个核心功能，带 evidence_refs 指向真实 repo 文档）
- Create: `docs/marketing/claims.yaml`（首批 5-8 条卖点声明，带 support_feature_ids、prohibited_rewrites）
- Create: `docs/marketing/personas.yaml`（主观交易者/财经内容创作者=主线，AI 工具爱好者=辅线）

- [x] products.yaml 写入两产品定位与表达边界
- [x] features.yaml 每条 feature 的 evidence_refs 指向可定位的文件/章节
- [x] claims.yaml 全部 support_feature_ids 存在于 features
- [x] personas.yaml 标注主线/辅线优先级

### Task 2: 首批 Content Brief

**Files:**
- Create: `docs/marketing/content-briefs/2026-07-05-launch-batch.yaml`

- [x] content_types 以 feature_showcase / use_case_story / demo_script / pain_point_post 为主
- [x] required_claim_ids 均存在于 claims.yaml
- [x] constraints 包含不承诺收益、对外脱敏私有路径

### Task 3: 生成首批内容

**Files:**
- Create: `docs/marketing/generated/2026-07-05-launch-batch.md`

- [x] 短帖 ≥10 条（每条含 hook/正文/CTA/claim_ids/风险提示）
- [x] 长文大纲 ≥3 篇（标题候选/结构/每节论点/截图位/素材来源）
- [x] 短视频脚本 ≥2 条（口播稿/分镜/录屏清单/video-use brief）
- [x] 每条内容可追溯至少一个 claim_id 或 feature_id
- [x] 教学向内容占比 ≤20%
- [x] 无收益承诺、无买卖指令、无私有敏感路径对外表达

### Task 4: 效果台账

**Files:**
- Create: `docs/marketing/performance/marketing-performance.jsonl`（含 1 条示例结构记录，`next_action: template`）

- [x] 字段与 spec 8.5 一致（content_id/brief_id/persona/channel/hook_type/claim_ids/metrics/human_notes/next_action）

### Task 5: Schema 校验脚本

**Files:**
- Create: `scripts/validate_marketing_contracts.py`（stdlib + PyYAML，仅只读校验）
- Test: 手动运行

- [x] 校验 products 必填字段（id/name/positioning/public_boundary）
- [x] 校验 features.product_id ∈ products、claims.support_feature_ids ∈ features、brief.required_claim_ids ∈ claims
- [x] 校验 performance jsonl 必填字段
- [x] 内置禁用表达扫描（保证收益/稳赚/自动赚钱/明天买什么 等）扫 generated/*
- [x] 运行通过：`python3 scripts/validate_marketing_contracts.py`

### Task 6: 收尾

- [x] 全部 checkbox 勾选、本清单更新
- [x] 逐 task commit 并 push 到 `codex/docs/marketing-agent-chain-spec`
- [x] agent-memory 项目交接回写

### Task 7: 只读生成上下文 CLI（spec §19-3，2026-07-05 追加）

**Files:**
- Create: `scripts/marketing_generation_context.py`
- Test: `tests/test_marketing_contracts.py`

- [x] `--brief <id>` 输出生成上下文包（产品边界/personas/claims+证据/约束/配额），只读不写盘不调 LLM
- [x] `--list` 列出可用 brief；引用未登记契约项时报错退出
- [x] 单测 3 例通过：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_marketing_contracts`
