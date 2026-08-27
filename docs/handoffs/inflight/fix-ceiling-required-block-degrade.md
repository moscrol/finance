# fix/ceiling-required-block-degrade

## 这个分支做什么
W1：marker_loss 对必需块只降级（残块+标注），不挂道歉横幅。横幅只归 C3。

## 当前状态
未提交。树 `/Users/a77/fwp-wt-w1-ceiling-degrade` @ `0ed258b5`。主检出脏树勿动。8792 未切。live 本回合不跑。

## 未验证 / 已知边界
Spec 目标 3（语义质量零删除权）未做：接到 `_repair` 会砸 ~40 既有钉。句仍删，块不再被横幅替换。live / 部署后自然样本未跑，`R-20260821-07` 保持 pending。

## 下一步
1. 用户确认后 pathspec 提交、开 PR。全量已绿，合前若再改代码需重跑。
2. 不要切 8792，除非用户另拍。部署后看 marker_loss>0 的 run：残块在、无「结构缺口」横幅、有【质检降级】。
3. 语义零删除权若要做，另开单，别混本邻域。

## 踩过的坑
- 变异前不要 `git checkout --`：未提交实现会被冲掉。本单用文件备份做变异。
- 批评进质检段走编排器 `_with_review_appendix`，不要写进 verifier `public_answer`（精确相等测试会炸）。

## 已验证
定向 9P + 宽集 210P；变异×2 击杀后还原 9P；全量 5897P/13s/0F；ruff 绿。收据 `~/.finance-runtime/test-receipts/20260821T140357Z-0ed258b5.json`。正文 `docs/verification/2026-08-21-w1-required-block-degrade.md`。

## 工具沉淀
未抽脚本：变异是对邻域语义的临时改回，不构成可复用审计档。
