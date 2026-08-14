# fix/l3-evidence-title-only — 低信号公告冒充证据 + 空集造假证据

日期：2026-08-14 ｜ worktree：`/Users/a77/fwp-wt-l3-evidence` ｜ 状态：**已提交，未合 main**

## 这个分支做什么

修 `intelligence/services/l3_evidence.py` 两个缺陷：治理噪声公告被当成证据端给模型；
CLI 合法返回空集时凭空造出一条假证据。

## 当前状态

- 已提交 `f12df8fe`，工作区干净，未 push、未合 main。
- ① 解析层按 `triage_level` 丢弃 P2/P3，**fail-open**：只有上游明确标了才丢，
  没这个字段的源（互动易、历史/测试载荷）一律保留。口径不是拍的——上游
  finhot `disclosure_lookup/evidence_card.py` 自己就写着「P0/P1 生成证据卡，P2/P3 跳过」。
- ② `_parse_lookup_output` 里 `if parsed:` 把「JSON 解析出 0 条」和「不是 JSON」
  并成同一个 falsy 分支，空集会落到纯文本兜底、把第一行 `[` 当成证据标题。
  **这个 bug 在 main 上一直存在**，① 只是让它变常见。

## 已验证

- 生效行为（真实 CLI，非 mock）：英维克 `--days 90 --source cninfo`
  修前 4 条 P2 治理噪声 → 修后 **0 条 + 空集专用措辞**（「未取得可注入的 L3 证据；
  读作公司端尚未兑现……不得据此否定题材」）。
- `--level P0,P1` 直查同样是 0 条，佐证「确实没有够格公告」不是过滤过头。
- 全量 `intelligence/tests + tests` **4819 passed / 4 skipped**；ruff check 通过。
- 新增 6 条测试，含 2 条变异测试。

## 未验证 / 已知边界

- **只验了 cninfo 一个源、英维克一家公司。** 互动易（sse_einteract）没有
  `triage_level`，走 fail-open 保留，未实测。
- 未验证「过滤后 L3 证据变少」对答案质量的净影响——理论上空集措辞比噪声更有用，
  但没跑 A/B。
- 命令模板 `FINANCE_L3_COMPANY_CMD` 仍在 launcher 的 env 里，**没动**；判据放在
  解析层就是为了不依赖模板。改模板不会影响本修复。

## 下一步

1. 跑一家**有** P0/P1 公告的公司（如近期有订单/中标公告的），确认没被误杀。
2. 合并后重跑证据消费率：l3_lookup 那 19 条 100% 成功的噪声退出证据池后，
   分母不再被灌水，`scripts/audit_episode_tool_outcomes.py` 的读数会变。

## 踩过的坑

- **我最初提的「一行谓词」修法是错的**：`if not body or body == title` 会把
  巨潮真实形态（summary==title）全切掉，而测试夹具正是拿它当有效证据断言的。
  测试挡住了我——公告标题本身是事实（有日期、URL、标题带 fact_type）。
- 判据别写进命令模板：模板由 env 覆盖，等于把判据交给配置，就是「配置两处、
  改一处不生效」的老坑。
