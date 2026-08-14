# 2026-08-13b · 夜间修复循环 + 全量验收 + knevo 对照（R13–R15）

## 循环产出（全部已合并部署）

| PR | 内容 | 生产判决 |
|----|------|---------|
| #301 | A3 冷启动（饿死型带工具重开） | R12 金收据 |
| #302 | RAG worker 缓存键跳过不可哈希 RagStore | 预热 166s→70s ready |
| #303 | 唯一少 1 位哈希 → `truncated_hash` FORMAT | 单测钉死 |
| #304 | `model_unavailable` 零证据也进冷启动 | 单测钉死 |
| #306 | 工具批次记账烧穿 root 账本时结平不抛 | **R14 判决通过** |

8792 = `3b7158a8`，clean，ready。旧 runtime `09dacdeaca30`/`bcd3b6ce64f7` 保留。

## R13 全量 A 组（合并末态首跑）

9/10 completed；A3 31.6s 硬失败。**收据表（`dump_episode_receipts.py`）当场改判**：
`tier=None stop=None repair=0/0` = 失败在修复层够得着之前，不是饿死。
翻 `continuous-episode.json` 钉死：`ValueError: root seconds budget exhausted`
从工具批次记账逃逸炸掉整个 run → #306。

**方法论**：收据表应为每轮验收固定第一步——它区分「修复层 bug」和
「修复层够不着的 bug」，两者修法完全不同。

## R14 A3 复跑（#306 判决）

31.6s 异常硬失败 → **71.8s completed**（降级），收据完整，修复轮进得去
（reentry granted=24s）。零证据残留是 understanding 层立案问题：
「立新能源」被吞「立」字解析成 theme「新能源」，错路由 theme-research。

## R15 B/C 全量 + knevo 对照

18/18 completed。对比包：mid_freq eligible=7/8，long_tail eligible=4/10
（`*.comparison-queue.json` 与 run JSON 同目录，Mac 私有仓未提交）。

抽样对照（我们 vs knevo 冻结参照）：

- **C1 未来日**：双方都没编数（诚实度平），但 knevo 指出 07-25 是周六，
  我们只说「证据不足」——**缺交易日历判定**，待立案。
- **C2 春节休市**：双方都没识别春节假期、都如实报缺口；我们更简洁。
- **B1 光刻胶**：显著差距。knevo 给出催化剂驱动全景（管制 8/16 生效）；
  我们 0 证据 + 核验删空。部分是刻意 fail-closed，但 theme 题 0 证据
  说明 kb/graph 检索没接上（与 A3 实体识别同族）。
- **B6**：2.1s 秒答是合法澄清路径（题需贴材料），非炸机。

修复层收据：B2/B4/B5/C1/C7 共 5 次 30s/24s 瞬态重试全部按窗发放，
`repair_model_unavailable` 仅 B4 二连超时后出现（熔断按设计）。

## 遗留立案

1. **实体识别吞前缀**：「立新能源」→「新能源」，A3/B 系 0 证据的共同上游。
2. **交易日历判定**：C1 该答「周六休市」而不是「证据不足」。
3. A7/A10 语义核验预算、governor 主动升档——设计评审项。
4. C2/C4/C5 degrades=9~10 偏高，核验层剪裁量值得一看（未必是 bug）。

## 产物索引（Mac 私有仓 `intelligence/eval/runs/`，未提交）

R13 `20260813T0115Z-r13-postmerge-full.json` ·
R14 `20260813T0155Z-r14-a3-postfix.json` ·
R15 `20260813T0200Z-r15-{midfreq,longtail}.json` + 两份 comparison-queue
