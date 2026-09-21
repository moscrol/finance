# claude/hithink-429-retry-handling-80eeca

## 这个分支做什么

把同花顺 HTTP 429 全局限流并入 `get_json` 退避路径（原先只重试 `code=4001`，429 中止整轮）。
内容 = `feat/hithink-research-data` 全部 + 修复提交 `dd2fae334`。

## 决策与被否方案

理由展开 `docs/handoffs/2026-09-21-hithink-429-backoff.md`；契约 `hithink-research-data.md`「429 处置」节。

| 选了 | 否了 | 为什么 |
|---|---|---|
| 独立墙钟预算 | 复用 `retries=4` | 那套总共等 5.6s，窗口 7min，等于把失败推迟六秒 |
| 默认 300s | 600s+ | 「夜跑愿意阻塞多久」是用户的取舍，留参数+环境变量 |
| 先判 HTTP 状态再判 code | 只扩 code 白名单 | 限流正文未必 JSON，只认 code 仍撞「非 JSON」 |
| 不动编排层 | 让单请求失败不中止整轮 | 超出本轮授权范围 |
| 叠 feat 上推自己分支 | 直接推 feat 更新 #810 | feat 另有活跃 worktree；落点留给用户 |

## 当前状态

`dd2fae334` 已提交并推 `gitea/claude/hithink-429-retry-handling-80eeca`，树干净。
**未开 PR**——并入 #810 还是开栈式 PR 待用户定。合入与部署仍未授权。

## 未验证 / 已知边界

- **没有真实 429 复现**：新路径只被离线替身压过，真实网关上「退避后重试成功」样本 **= 0**。
- 默认 300s **短于**实测窗口上沿（10:24→10:31 约 7min）：救瞬时限流，不保证救整个全局窗口。
- `Retry-After` 秒数 / HTTP-date 两种形态都只在替身上验过（上游实测不发此头）。
- 夜跑 18:30 时段会不会撞 429，仍无证据（02:05 那次四请求全成功）。
- 编排层未动：`_capture` 单请求失败即 `raise`，`complete_with_gaps` 对抛出型失败够不到。

## 下一步

1. 用户定 PR 落点（并入 #810 / 以 feat 为 base 开栈式 PR）。
2. 盘后 18:30 之后在隔离库跑一轮全采集，取夜跑时段限流证据。
3. #810 的独立 Spec/Quality 等 09-27 Codex 额度恢复；若并入，审查范围需覆盖本修复。

## 踩过的坑

- 本分支初始停在 merge-base（=main）。**只 diff 单个文件就断言「两边运行时一致」是错的**——
  `diff --stat` 全量才看见采集器 372 行只在 feat 上。
- 变异**不能整份回退到修复前**：新测试引用新符号，9 条全红在 `AttributeError`，被测行为
  一次没跑到，全红等于零信息。保留符号、每次只坏一个行为点。
- `resp.headers` 硬依赖被仓内既有响应替身打红（它们没这属性），改 `getattr` 回退。

## 已验证

- 全量 pytest @ `dd2fae334`：**11975 passed / 0 failed / 85 skipped，exit 0**，收据
  `test-receipts/20260921T033414Z-dd2fae33.json`（`dirty:false`）。**同 revision 另有
  一份 `032247Z` 是 counts 全 0 的空跑，取最新那份。** ruff 与 12 道 pre-commit 全过。
- 三次定点变异各只红对应层：429 识别红 6、`Retry-After` 红 3、预算检查红 3；
  `test_4001_retries_then_ok` 与「非限流码立即失败」三次都绿。
