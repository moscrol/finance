# AIHOT 公开消息手动导入

两个命令把已取得的公开消息追加到既有观察台账。默认 dry-run（只预览，不写入），加 `--apply` 才写。
CLI 可用不代表已开通真实 AIHOT 实例、A 股信源或连续采集；本入口不安装定时任务，不调用模型、不访问文章原文、不写行情库。

## 映射与输入

先复制 [映射模板](../examples/aihot-attention-mapping.example.json) 到私有运行目录，替换所有 `<…>` 占位符；不要将真实运行资料提交 Git。

- `sources` 按上游 `source.name`（或字符串 `source` / `sourceName`）精确匹配；`participant_key` 是明确核对的独立出版集团，`kind` 是来源类别。
- `entities` 将自己起的别名对应到核实后的 canonical 板块 `id` / `name`；命令只验证格式和引用，不代替核实真实板块身份。
- `items` 按上游字符串 `id` 精确匹配；`event_key` 是人工复核的事件组，`origin_key` 是核对后的转载原始来源，`entity_keys` 引用上面的别名。`removed: true` 追加撤回版本，改回 `false` 追加恢复版本。
- 不确定时删掉该映射项，或显式使用空映射 `{}`。未知来源、未归组、无板块和缺发布时间会保留缺口，不从标题猜归属或独立性。未知映射字段和错误类型拒收。

离线文件支持完整条目数组，或 `schemaVersion: 1`、`items` 数组及终页 `page: {"hasMore": false, "nextCursor": null}` 的封套。
数组由操作者确认已合并所有页；命令不能从数组证明远端采集覆盖。单页 `hasMore: true` 的原始 API 响应拒收。
条目需带非空字符串 `id`、文本 `title`、无凭据的 HTTP(S) 原文地址 `links.original`（也兼容 `url`）。不要导入 minimal 投影或将精选榜误称完整公开条目。

```bash
.venv-workbench/bin/python scripts/import_aihot_attention.py export.json --mapping mapping.json
# 核对 accepted / mapped / grouped / unknown_sources 后，明确追加：
.venv-workbench/bin/python scripts/import_aihot_attention.py export.json --mapping mapping.json --apply
```

## 显式实例拉取

以下地址是占位，须换成自己已核实的实例根地址，可含挂载路径。

```bash
.venv-workbench/bin/python scripts/pull_aihot_attention.py \
  --base-url https://YOUR-AIHOT-HOST --mapping mapping.json
# 核对后，同一命令加 --apply 才追加台账。
```

拉取只访问给定实例的 `/api/v1/items`，固定 `mode=all&window=7d&by=published&limit=100`。
范围仅为**该实例近 7 日按发布时间筛选的 public eligible 条目**，不等于全网、全市场或连续覆盖。dry-run 仍会访问该实例。

| 边界 | 默认与上限 |
| --- | --- |
| 页数 | `--max-pages 10`，允许 1–50；每页最多 100 条，最多读取 5,000 个条目位置 |
| 响应 | 每页最多 4 MiB；坏 JSON、坏 schema、冲突重复 ID、重复游标、页预算用尽、响应不完整都整批拒收 |
| 时间 | `--timeout 15` 秒 socket 超时（上限 60）；`--total-timeout 120` 秒整次拉取期限（上限 300），均须为有限正数；慢 DNS 或慢速持续响应也不能无限等待 |
| 目标 | 基址拒绝凭据、查询串、fragment；不继承环境代理，不跟随任何 HTTP 重定向，需要操作者显式填最终实例地址 |
| 离线输入 | 导出最多 40 MiB / 10,000 条，映射最多 4 MiB；JSON 重复键、非有限数、无效 UTF-8 拒收 |

同 ID 且内容完全相同可去重；同 ID 异内容整批拒收，不让先到的一条掩盖修订。
不同 ID 指向同一归一原文 URL 时，只有完整内容、来源和映射相同才合并（允许跟踪参数不同），稳定选择字符串排序最前的 ID；其余冲突整批拒收。
同一材料在**后续完整导入**中发生变化，沿既有台账版本链追加；相同快照重跑或重排不会重复写入。跨批次上游身份 ID 变化仍按既有服务合同保留为一次修订。

## 落点与结果

唯一写入实现是 `intelligence.services.opinion_attention.append_observations`，两个命令共用既有文件锁、幂等检查和版本链。
默认路径由 `default_ledger_path()` 解析：`data_repo_root()/state/opinion-attention/observations.jsonl`，环境变量 `OPINION_ATTENTION_LEDGER` 可覆盖；临时验收可用 `--ledger /tmp/aihot-check/observations.jsonl`，优先于环境变量。
真实导出、映射、台账留在私有运行目录，勿提交 Git。卖方观点、公司画像与行情 DuckDB 不受此入口写入。

全部校验通过后才追加。空导出不创建台账；输入/分页错误退出码为 `2`，`written: false`，既有台账字节不变。
存储 I/O 故障可能发生在写入之后，此时 `written: null`，须检查台账再重试，不能把它当作“零写入”。
正常输出仅含计数与范围摘要，不回显原文、映射内容、URL 或上游错误正文。

`recorded_at` 始终为本机这次实际适配时间，不能通过上游时间或命令参数倒填；`publishedAt` 和 `discoveredAt` 各自保留含义。
未来发布时间拒收；缺少时区的发布时间保留为缺口，不计热度。公开消息和摘要始终为 `unreviewed`，不自动升格为已核实公司事实，也不能据此宣称舆论正在升温或降温。
