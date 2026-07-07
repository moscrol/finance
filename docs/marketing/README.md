# Marketing 素材事实库（P0）

对应 spec：`docs/superpowers/specs/2026-07-05-marketing-agent-chain-design.md`
执行清单：`docs/superpowers/plans/2026-07-05-marketing-agent-chain-p0.md`

定位：营销内容以**介绍产品**为主线（产品是什么、能做什么、怎么用），教学向内容仅辅线（每批 ≤20%）。证据先于文案，不承诺收益，P0 人工审核发布。

## 目录结构

```text
docs/marketing/
├── README.md                 # 本文件
├── products.yaml             # 产品定义与对外表达边界（can_say / cannot_say）
├── features.yaml             # 功能事实，每条带 evidence_refs
├── claims.yaml               # 可对外卖点声明，带证据与禁用改写
├── personas.yaml             # 目标人群（主线/辅线）
├── content-briefs/           # 生成任务 brief
├── generated/                # 生成的内容批次
└── performance/              # 发布效果台账 JSONL
```

## 写入者与流程

- YAML 契约：人工或 agent 维护，改动需过 `scripts/validate_marketing_contracts.py`。
- `generated/`：Content Generator（agent）输出，人工审核后才可对外发布。
- `performance/marketing-performance.jsonl`：人工发布后登记效果，唯一写入口为人工/agent 逐行 append。

## Review Gate 摘要（发布前必查）

1. 事实：每个卖点绑定 claim_id 或 feature_id；未登记能力标记 `unsupported_claim`。
2. 合规：不承诺收益/稳赚/自动赚钱，不给买卖指令，不包装为投资建议。
3. 隐私：不出现 `.env`/token/私有路径/未脱敏数据；内部路径对外须替换为泛化描述或截图。
4. 质量：目标人群能听懂、有具体场景、有明确 CTA。

校验：`python3 scripts/validate_marketing_contracts.py`
