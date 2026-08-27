# fix/retire-feishu-market-daily

## 这个分支做什么
从夜跑/`daily-full`/CLI 拿掉已退役的飞书 `sync-market-daily`。市场指标只走 `sync-market-overview`。

## 当前状态
本树已提交（待推、未合）。编排/`daily-full`/CLI 已去掉飞书步，模块 fail-closed。脏树夜跑编排已同步去掉该步，勿混提。08-21 质检对齐见日期快照。

## 未验证 / 已知边界
- 未 live 过一夜「无飞书步」的 S7。
- 新浪 `index-daily` 仍在；上证今晚是复盘会兜底，未改编排。
- 与写入守卫、sector-daily 只扫 `.FP` 是三件独立活。

## 下一步
1. 用户确认后 pathspec 提交本树 8 文件+本交接，推 `gitea`，合 main 再等一声。
2. 要换新浪：overview 顺手写 `sh_index_*`，AkShare 降兜底。
3. 别在 `feat/reading-rules-baseline-batch1` 上混提。

## 踩过的坑
- 质检时 `MARKET_FEATURE_STORE_DB` 仍指向已换名删除的 `.staging`，闸门报库不存在。先 `unset` 再打生产。
- 退役源当欠账去补 = 用户纠偏。飞书不是缺口。

## 工具沉淀盘点
无新脚本。闸门形态复用 `sync_to_local.py`。手法：一张事实表留双写链，旧源挂了整步变红。

## 已验证
定向 4 绿（retired-feishu 三测 + plan 顺序）。08-21 生产闸门 COMPLETE/PASS，质检快照 `docs/handoffs/2026-08-22-daily-full-0821-quality.md`。
