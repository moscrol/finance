# 2026-08-23 SPT 周报回填收口

本会话只写用户空间画像，**没改仓内代码、没翻 `perspective_mode`、没把 SPT 升格进 `reading_baseline`**。
判读基线合入走干净树 `feat/reading-rules-baseline-r2` / Gitea #343，与本单无关。

## 落点（永不进 git）

- 生产身份：`FORESIGHT_USER=linxiaoqi5111`，根 `~/.local/share/finance-workbench/users`
- 真身：`.../linxiaoqi5111/perspectives/profiles/sptfei.json`
- 镜像：已 rsync 到 `users/default/perspectives/`（manifest `raw_path` 改写到 default 根内）
- 生产闸：`GET /api/perspectives?user=linxiaoqi5111` → `display_name=SPT-Molmansk`，`article_count=50`，`profile_confidence=medium`

## 入库

50 篇：2024-2025 跨年综述；2025.33–52（缺 41、48）；六篇具名文（2025-02-09～06-16）；2026.1–34 周报（缺 5、9–10、14–15、20、22、25–26、31–33）。

闭环：`perspective ingest → extract-cards → propose-patches → review-patch`。Agent 代评，可执行且脱离当周才 approve；episodic / 同义改写 / 未回测数字 reject。当周亿数阈值不进画像。

## 画像结构（agent 起草，待你复核）

六镜头：四天时 / 产业渗透率时钟 / 量能状态机 / 筹码与结构 / 故事容量与定价权 / 情绪抱团独立态。

推理模板 13 条，后四条本会话新加：龙回头量能二次确认、夺价补涨分层、共建成败二分、光大建投二分。

## 还缺

- **2026.5**、**2026.31 / 32 / 33**
- **2025.41 / 48**
- 中间若干周（9–10、14–15、20、22、25–26）未喂，不是这次漏抓

## 分层别混

| 层 | 是什么 | 默认 |
|---|---|---|
| `reading_baseline` | 怎么读数 | 开（#343） |
| `proactive_checks` | 漏检闸 | 另树 `fwp-wt-proactive-checks`，未合 |
| `sptfei.json` | 倾向 + 口吻 + BM25 | 开关，默认 `neutral` |

再贴链接就按原闭环继续喂。升格 SPT 成主视角要单独 A/B，不能把倾向写成领域方法。
