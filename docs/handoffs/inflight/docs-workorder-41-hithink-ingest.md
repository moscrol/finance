# docs/workorder-41-hithink-ingest

树 `/Users/a77/fwp-wt-workorder-hithink`，PR #678，3 个纯文档（工单 + API 实测评估 +
数据进长河消费设计），0 代码。对 `gitea/main` 落后 0、无冲突，**随时可合**。

## ⚠ 先读这条：A–D 已经有人在做，别再派单

`/Users/a77/fwp-wt-hithink-ingest` @ `data-source/hithink-ingest`（2026-09-09 00:23 仍在落笔）
已写出 A/B/C/**D** 四份 sync + 客户端 + schema + 接入 `sync_daily_full`，验收稿 a–e 五份都在。
**再开一个 agent 做 A–D 会撞车。** 工单 §58–80 的 A–D 视为已占坑；E（消费方）仍未开，
但它自述要等 A–D 对数报告，别抢跑。

那棵树 **29 个文件全部未提交**，分支尖 == `gitea/main`（0/0），即工作零备份。
已代它做只读快照（没碰它的树）：

    ~/backups/hithink-ingest-20260909-0045/
      tracked-vs-HEAD.patch   12 文件 / +1141   → git apply
      untracked.tar.gz        17 文件           → tar xzf
      HEAD.txt / status.txt

要它自己提交才算真安全，本轮没替它提交（可能仍在运行中）。

## Parquet 已挪出 /tmp

`~/.finance-runtime/hithink-parquet/`：`hithink_daily_k_10y.parquet`（180MB，10,271,528 行，
sha256 与 /tmp 源逐字节相同）、`_10d`、`_adjustment_factors`、`hithink_sectors.json`、
`hithink_probe.py`（探针脚本不在仓里，只此一份）。
/tmp 原件保留未删——那棵树可能还在引用。**预签名 URL 已过期**，重下需新 key。
`/tmp/hithink-fin-api` 是 `HiThink-Tech/Financial-API@4cb4515` 公开 clone，可重取，未备份。

## 交给用户的两件（agent 做不了）

1. **换 key**：`security add-generic-password -U -s hithink-finance -a a77-api-key -w <新key>`。
   全仓**无任何代码**读这个钥匙串条目（只有文档引用），换完不会有旧值被缓存。
2. **代理加 DIRECT**：`push2his.eastmoney.com` / `push2.eastmoney.com` / `web3.ifzq.gtimg.cn`
   现全解析到 `198.18.x.x`（Shadowrocket fake-IP），30 分钟 K 端点 http=000。
   同花顺 API 本身没有分钟 K，这是唯一的分钟线来源。

## 未做

- 本分支只是文档，不含任何 ingest 代码，合入不影响生产。
- E 单未开。开之前先跟 `data-source/hithink-ingest` 对一次进度，它已经动了 E 的部分文件
  （`source_views.py` / `test_hithink_teaching_sources.py`）。
