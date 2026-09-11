# 飞书 Bitable 写入指南

凭证配置在 `~/.claude/shared/feishu_config.json`，脚本自动读取。

## 表结构

| 表 | table_id | 说明 |
|---|---------|------|
| 每日指标 | `tbljGvjtl1IC44hb` | 每天 1 条记录 |
| 板块趋势 | `tblshRMmRnQYrM4K` | 每天最多 20 条（每个上榜板块 1 条） |

Bitable URL: `https://pcnyt9i9lfme.feishu.cn/base/RnRfbT9F1asuFFsQpAyccMmHn2b`

## 获取 Token

```bash
TOKEN=$(python3 -c "
import json
from pathlib import Path
c = json.loads(Path('$HOME/.claude/shared/feishu_config.json').read_text())
import urllib.request
req = urllib.request.Request(
  'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
  data=json.dumps({'app_id': c['app_id'], 'app_secret': c['app_secret']}).encode(),
  headers={'Content-Type': 'application/json'})
print(json.loads(urllib.request.urlopen(req).read())['tenant_access_token'])
")
```

## 查重

```bash
curl -s "https://open.feishu.cn/open-apis/bitable/v1/apps/RnRfbT9F1asuFFsQpAyccMmHn2b/tables/<table_id>/records?filter=CurrentValue.[日期]=\"YY-MM-DD\"" \
  -H "Authorization: Bearer $TOKEN"
```

如果已有该日期的记录，跳过写入。

## 每日指标表字段

全部为 text 类型：日期(YY-MM-DD), 阶段, 天数, 冰点, 成交额, 较昨日比, 20日均, 相对量能比, 量能状态, 涨停, 跌停, 涨, 周均线, 偏离度, 前三占比, 集中度, 行业1, 占比1, 行业2, 占比2, 行业3, 占比3

## 板块趋势表字段

日期(text YY-MM-DD), 板块(text), 当日涨幅/3日涨幅/5日涨幅/10日涨幅(text, 空串表示未上榜), 全周期出现(checkbox: 仅在四个周期全部上榜时为 true)

## 写入流程

1. 获取 token
2. 查两个表是否已有该日期 — 有则跳过
3. batch_create 每日指标 (1 条)
4. batch_create 板块趋势 (最多 20 条唯一板块)
5. 验证两次写入均返回 `code: 0`

## 格式规范（必须遵守）

所有字段为 text 类型，写入时必须统一格式：

| 字段 | 格式 | 示例 |
|------|------|------|
| 日期 | `YY-MM-DD` | `26-05-20` |
| 成交额 | 纯数字，不带"亿" | `29534.18` |
| 20日均 | 纯数字，不带"亿" | `29163.21` |
| 较昨日比 | 正数带`+`，负数带`-`，带`%` | `+2.33%` / `-13.48%` |
| 相对量能比 | 带`%` | `101.27%` |
| 偏离度 | 正数带`+`，负数带`-`，带`%` | `+0.16%` / `-1.28%` |
| 前三占比 | 带`%` | `48.0%` |
| 占比1/2/3 | 带`%` | `28.9%` |
| 涨停/跌停/涨 | 纯数字 | `61` |
| 天数 | 纯数字 | `5` |
| 周均线 | 纯数字 | `4155.47` |
| 行业1/2/3 | 中文名 | `电子` |
| 阶段/量能状态/集中度 | 中文名 | `顶部横盘` / `正常` / `集中` |
