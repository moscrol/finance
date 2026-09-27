# Runtime 合后独审收尾

## 这个分支做什么
保存 #865 合后固定 760248ecebc7 的门禁、K3 独审与宿主补跑分账结果；仅文档，无产品改动。

## 决策与被否方案
维持 BLOCKED，不用全量绿代独审；不自动续 K3，不修宽探针后追认通过。背景/首红/授权勘误见 `docs/handoffs/2026-09-23-runtime-postmerge-k3-qc.md`。

## 当前状态
K3 已结束：32 探索+1 终稿，报告完整但八合同均 NOT_REVIEWED。宿主已补跑并核实收据。文档基座 ffd1b7f15，不把 760248 收据移签此基座；本轮未推送、未合文档、未部署。#865 合入与下层关闭事实按日期快照核对，不重复执行。

## 未验证 / 已知边界
C1 保存失败、C4 锁争用、C5 重入、C6 inbox、C7 前缀身份未获本场动态独立签字；C2/C3/C8 也只有局部宿主旁证。没有真实计费/跨机锁/完整跨进程恢复驱动验收。原跨 episode 异常类型是否满足调用者合同待验。

## 下一步
先修探针副本量具并保留原件，再按单合同有界动态复验。新的模型场次需要明确范围/预算，不自动续场；生产操作另办。不要动原候选/对照树或删首红。

## 踩过的坑
r2 prompt 可写路径仍指旧目录，实际沙箱只放行 r2；声称提供的收据副本未创建。旧 archive 缺 27 文件，原因未核，不称完整。原 merge JSON 中“授权原话”是助手误记，已追加勘误，不覆盖或倒填原件。

## 已验证
固定 760248ecebc7：Ruff 绿、14568P/0F/85S/2X、collected=14655、dirty=false；精确 SHA + full-scope 收据校验 exit0。K3 原件哈希有效，候选/对照树不变。
宿主原探针 8P/2F：mappingproxy JSON 序列化错误；跨 episode 被 ValueError 拒绝而探针仅接受 RestoreUnavailable。身份变异 collection error 不算有效抓红；预算 shadow 未接入测试。既有交付/截断子集 34P/127 deselected，不升级整体。
证据根：`~/.finance-runtime/reviews/runtime-postmerge-k3-20260923-r2/`；完整门禁见相邻 `runtime-identity-effects-20260922/gate-latest-760248ecebc7/`。
