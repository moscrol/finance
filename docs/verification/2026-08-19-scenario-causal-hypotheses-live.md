# P1-C live 对照：情景树互斥因果假说（2026-08-19）

> 代码：`feat/scenario-causal-hypotheses` @ `da0731ba`  
> sidecar：`:8796`，隔离用户 `scenario-causal-0819`  
> 生产 `:8792` 未切（`9de3fd46`）  
> 入口：`POST /api/conversations` → `.../messages`（`continuous_episode`）  
> PR：http://127.0.0.1:3300/a77/finance-workspace-private/pulls/216

## 题目

「基于周二的盘面数据，你认为主线是什么。今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会」

## 判定

**P1-C live 通过。** 公开稿单独写了【互斥因果假说】，不是量能 A/B/C 换皮。

同一现象：美股科技大跌。

- H1：存储供给/价格周期（存储跌 > 算力跌，E19–E21 vs E18）
- H2：AI 高位获利了结的整体回调（费半 −4.98%，E17）
- 裁决：领跌相对强弱倾向 H1 为主、H2 叠加；缺同窗口新闻归因，写「两假说部分并立」
- 操作含义：避开存储链，观察算力链相对强弱

情景分支 A/B/C 仍在（路径），与假说段分开。公开稿丢了 B 支正文（核验裁剪），假说段留下。

**P1-D / 验证器消融 / 海力士源 / 「收盘」用词不是本刀。** 不合、不切 8792。

## 验收

| 条 | 要求 | 读数 | 结果 |
|---|---|---|---|
| 因果 | ≥2 互斥因果假说，不是量能三分支换皮 | H1 存储周期 vs H2 AI 整体回调；A/B/C 仍是路径 | 过 |
| 裁决 | 带证据编号，或写并立 | E18–E21 / E17；「两假说部分并立」 | 过 |
| 禁概率 | 无数值概率 | 无 40% 一类 | 过 |
| 发明阈值 | 不发明 2.2 万亿 / 60 家 / 27% | 公开稿无 | 过 |
| 授权 | 不回退 P0-A | `news_search` + `web_search` 在 allowed；本发未再调用 | 过 |
| E 覆盖 | ≥23 | 28 | 过 |

## 残留

- 核验 `unsupported numeric condition without bound evidence`，outcome `partial`（研究截止）。闸没放宽。
- 公开稿 B 支被裁，假说段未裁。
- `format_quote_line` 仍写「收盘」。
- 本发未调 `news_search`（授权在）。

## 产物

- 验收 run：`~/.finance-runtime/scenario-causal-live/users/scenario-causal-0819/runs/run_20260819_095742_377275/`
- 收据：`~/.finance-runtime/scenario-causal-live/receipt.json`
- sidecar 已停；8792 仍 `9de3fd46`
