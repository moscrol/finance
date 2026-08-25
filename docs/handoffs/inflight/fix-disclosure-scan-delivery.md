# fix/disclosure-scan-delivery

## 这个分支做什么

披露扫描 P0.5 投递卫生（live 回写，稿 v1.2）：`partial` 只认主名单词截断；excluded 公开稿每档封顶 3 条；`L_reg` 收窄（含「受理」/裸「注册证」不进）。

## 当前状态

已提交 `c4a4ea17` 并推 gitea，**PR #392 open，合并等用户确认**。树内无其他未提交改动。生产 8792 仍在 P0 码 `af71f048`，未切本单。

## 下一步

1. 用户确认 → 合 #392 → 切 8792 → 重放探针题 `run_20260825_155459_372046` 核对公开稿形状（开篇不再「查询未跑完」、回购最多 3 条）。
2. P1（残差写手 / PDF 抽品种金额 / 自定义窗口）、P1-b（残差 UX 分列）另开分支，见稿 §12。

## 未验证 / 已知边界

- 未做 live 复跑；合入切码前公开稿新形状只有夹具证据。
- render「附录词未查完」行收集所有 `skipped_budget`，主名单词被跳时也会列在「附录词」标签下（P0 存量措辞；此时 partial 开篇已兜底，本单未动）。

## 已验证

三叶全绿 @ `c4a4ea17`：python（ruff + 全量 pytest **6452P / 12S / 0F**，`.venv-workbench` 解释器）；frontend（lint/typecheck/test/build）；e2e（playwright **15 passed**）。定向 21 条含新增（G8 预期反转、受理≠L_reg、回购封顶 3+另 N 条）。消费方核查：编排层只走三个公共入口，无人直接判 `budget_hit`/partial 字符串。

## 踩过的坑

- 封顶只能落渲染层：`to_dict` 收据必须保留全量 excluded，否则裁判/回读丢证据。
- L_reg 排「受理」是标题级子串排除（含「受理」一律不进）；若出现既含「受理」又含「获批」的联合标题会落 unclassified——方向是 fail-closed（漏进 excluded 兜底，不是漏进主名单），可接受。
- worktree 里跑 e2e 要带 `WORKBENCH_E2E_PORT`（8791 被占，勿杀勿 reuse——那是别人的收据）+ `WORKBENCH_PYTHON=主树 .venv-workbench`（树内无 venv，回退宿主 python 缺 uvicorn）。

## 工具沉淀盘点

无新工具：三处都是既有模块内语义修正，生产探针 run + git diff 一次定位，无重复手工排查可脚本化。存量红对照这轮用不上（全绿）。
