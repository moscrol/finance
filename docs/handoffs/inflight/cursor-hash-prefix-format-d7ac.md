# 在途交接 · cursor/hash-prefix-format-d7ac

更新：2026-08-13 · A4 截断哈希口子已提交，待合

## 这个分支做什么

唯一少 1 位的证据哈希按 FORMAT（`truncated_hash`），不再当伪造硬拒。

## 当前状态

- 已提交 `a14b5398`。0/多匹配、少 2 位、混进真伪造仍 INTEGRITY。
- 回灌文案不带完整哈希。
- 未部署。#302 RAG 热修仍待合。

## 下一步

1. 合本 PR 后才进 8792（可与 #302 一起干净切）。
2. A5 日期错位定因。

## 未验证

- 生产 A4 重跑。单元测试已绿。

## 踩过的坑

- 不能自动补全哈希：那是改绑定，不是纠格式。
- 前缀太短不能放：碰撞面把 INTEGRITY 凿开。

## 已验证

- `test_episode_protocol.py` 18 passed；相关 hash/finish 18 passed。
