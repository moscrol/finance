# 在途交接 · cursor/model-unavailable-cold-restart-d7ac

更新：2026-08-13 · A1-R2 冷启动口子已提交

## 这个分支做什么

主路径 `model_unavailable` + 零证据也走冷启动（与 `deadline_exhausted` 并列）。

## 当前状态

- 已提交 `687cc289`。`model_finish` 主动收场仍不进。
- 未部署。#302 RAG、#303 A4 仍待合。

## 下一步

1. 合本 PR（可与 #302/#303 一起切 8792）。
2. A5 日期错位无生产收据证明是 harness bug，不改。

## 未验证

- 生产 A1 重跑。单测 cold_restart 相关 10 passed。

## 踩过的坑

- 不能把所有零证据都当饿死：`model_finish` 是降级信号。

## 已验证

- adapter/coordinator cold_restart 筛选 10 passed。
