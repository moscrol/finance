# fix/retire-feishu-market-daily

## 这个分支做什么
从夜跑/`daily-full`/CLI 拿掉已退役的飞书 `sync-market-daily`。

## 当前状态
**已合 `gitea/main`**：PR #336，merge `d5cb4e2f`（功能提交 `cc5d2e4e`）。无在途。

## 未验证 / 已知边界
- 未 live 过一夜「无飞书步」的 S7。
- 新浪 `index-daily` 仍在编排。
- 写入守卫、sector-daily 只扫 `.FP` 未合。

## 下一步
无本单。新浪改复盘会、sector-daily `.FP`、写入守卫另开干净树。

## 踩过的坑
- 合入前全量 8 红是会话残留 `L2_PAUSED=1`，不是回归；`unset` 后 6067 绿。
- `MARKET_FEATURE_STORE_DB` 指已删 `.staging` 会让闸门报库不存在。

## 工具沉淀盘点
无新脚本。闸门复用 `sync_to_local.py` 形态。

## 已验证
ruff；pytest 6067/13 @ 同树；webapp lint/typecheck/test/build。
