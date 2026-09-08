# fix/perspective-profile-ratchet

## 这个分支做什么
画像 `_save_profile` 棘轮：薄副本整表回写拒写。不合 main。

## 决策与被否方案
- 选长度/`article_count` 棘轮 / 否内容哈希 / 换措辞必须过
- 选 `allow_regression` 仅夹具 / 否生产默认可缩 / 删条目走直接编辑 JSON
- 选拒写 / 否静默 merge 磁盘字段 / 调用方会以为薄副本写成功

## 当前状态
棘轮 + ingest/评审重读 + 单测已在本枝。风远用户空间已收口（20/medium，考卷过），**不在本提交里**。展开见 `docs/handoffs/2026-08-28-fengyuan-spt-closeout.md`。

## 未验证 / 已知边界
- 8792 未切本枝：生产 `review_patch` 仍是旧整表回写。
- 未在生产 json 上重放 wipe（夹具已复现薄副本拒写、磁盘不动）。
- 未跑全仓 pytest / 未 push。

## 下一步
1. 合入等你点头。勿强推、勿合 main。
2. 切 8792 前本闸对生产不生效。
3. 数字标定 / 70 条代评抽查另线，不挡这枝。

## 踩过的坑
磁盘已经薄了救不回。棘轮挡的是「内存薄、磁盘厚」。官方 `review_patch` 每次重读仍会整表写——要禁的是过期 dict 进 `_save_profile`。

## 已验证
`pytest` perspective_lab + learning + exam **76P**（解释器 `.venv-workbench`）。

## 工具沉淀盘点
模式已在 `BUILD.md` 棘轮节加了一句实例。没另做脚本：失败形状是「整文档回写」，闸就在写函数上。
