# #81 ReAct 轨迹链 · #832 前向接手（L5，09-27）

## 这个分支做什么
#832 是 #81 唯一产品载体。09-27 接手：以 Pi 本地合流 `11d63a717`（含旧头 27034ce44）为底，合 main `34dd58468`（无冲突）与 #892 文档 `37797b3d5`（INDEX 取 main；QUEUE 取 main 并补回 #81 行），快进推回本分支。本地分支名 `fix/react-trace-qc-fwd-0926`，树 `/Users/a77/fwp-wt-l5-react-0926`。

## 决策与被否方案
- 沿用 Pi 合流，不重做；#892 原件已并入，建议关闭 #892 并留指针到 #832。
- K3/GLM 独审停用，按用户委托改 Claude 范围化复核；0304 旧批不补签。
- C3 缺的是测试不是产品：旧用例只测「先错后对」，补「先有效取证→参数失败→合法修正」3 例。
- 取消有两层（回合后检查 + registry 派发前检查），只撤一层会存活；变异改为整体撤取消信号。

## 当前状态
代码 `922ff8a23`，其后只有本文档提交；已推 #832（WIP）。产品增量只有 `episode_semantic_verifier.py`（C6），C1–C5 产品代码已在 main。未合 main、未部署、未写生产，零模型请求。

## 已验证
- 固定 7 文件 479P、扩大 178 文件 5384P/8S（均 @6945677b3）；最终头读数见证据目录 `final.log`。
- 变异（复用 runner）：C3×3、C5×2、C6×2 全红、还原全绿；手工 C5 页坐标归零 4F。
- 复核 PASS_WITH_LIMITS：`~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L5/review.md`。

## 未验证
全仓 python / 前端 / E2E / registry 四叶；#76 自然金融验收与 live 模型；C3 新例是脚本模型、只走 finance_query。

## 下一步
协调者合并预览跑四叶后合入。合后把 `docs-react-trace-chain-0923`、`fix-react-trace-closeout-0921`、`fix-react-trace-closeout-forward-0924` 三份 inflight 归档。#841 另见其 PR 评论。

## 踩过的坑
变异 runner 遇存活变异会中止并留临时树，要自己 `git worktree remove`；`TMPDIR` 指到证据目录可避开 /tmp。
