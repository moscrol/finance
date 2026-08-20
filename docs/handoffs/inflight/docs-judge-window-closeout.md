# docs/judge-window-closeout

## 这个分支做什么
把判官窗三笔（#269/#272/#276）的过期 inflight 收成日期快照。

## 当前状态
文档未推。代码已在 `gitea/main`。**未切 8792**。

## 未验证 / 已知边界
见 `docs/handoffs/2026-08-20-judge-first-attempt-50.md`。

## 下一步
推本分支并合进 main（只文档）。不要切 8792。

## 踩过的坑
旧 `inflight/fix-judge-grant-starvation.md` 还写「#269 未合、四条路待拍板」——会误导。

## 已验证
质检双轴无硬违规。DEFAULT=50 / leftover(49)拒。
