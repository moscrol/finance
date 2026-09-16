# 分范围同意书模板（consent-v1）

参与者假名：`<participant_id>` 　试点：`<pilot_id>` 　协议：`<protocol_version>` @ `<protocol_hash 前 16 位>`

| 范围（`scopes`） | 内容 | 默认 |
|---|---|---|
| `research` | 你的任务耗时、交付物、访谈内容用于本试点研究 | 需勾选 |
| `logging` | 记录你在工具里的操作与运行日志（不含资料原文） | 需勾选 |
| `blind_review` | 你的交付物脱去条件标识后交独立评审打分 | 需勾选 |
| `team_share` | 匿名化后的汇总可在你所属团队内分享 | **默认不含** |
| `external_display` | 匿名化后的汇总可对外展示 | **默认不含** |

- 进入有效测量至少需要 `research` + `logging`；没有 `blind_review` 的产物不评分，质量记为未知。
- 有效期：至 `<cohort_window.end>` 后 90 天，或你撤回为止。
- 撤回 / 删除：随时可撤回任一范围；撤回自 `effective_at` 起生效，之后的事件不进有效测量。你可要求删除明细；「有一位参与者退出」的计数会保留。
- 同意书哈希：`terms_hash = sha256(本文件冻结版)`，与 `consent_version` 一起写进 `consent_changed` 事件；前端勾选表达你的选择，服务端保存生效记录。

签署（假名 / 日期 / 方式）：______

## 事件映射

```json
{"event_type": "consent_changed", "source_channel": "frontend|manual_import",
 "payload": {"consent_version": "consent-v1", "scopes": ["research", "logging", "blind_review"],
             "effective_at": "<带时区时间>", "action": "grant|withdraw", "terms_hash": "sha256:<...>",
             "initiator": "participant", "assistance_source": "none"}}
```
