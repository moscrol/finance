# 2026-09-16 · 授权合并与消息可见性门禁补漏

## 背景

用户明确授权按#592→#747合入main，不切生产8792。两次合前均fetch、校验原精确head收据、merge-tree并比对结果树；#592合入c1f8416a，#747改base=main后合入918f8d5a。最终业务合并点在独立干净树全套验证9749P/0F、77S/2xfail、前端76P、E2E15P、Ruff与registry/crosswalk全0。对应收据与PR评论见 `../verification/2026-09-16-release-merge.md`。

## 按发现顺序

1. INDEX与交接仍写等待授权，所以追加6份Markdown回执e2e7d11a，PR #748。不是第二次改业务。
2. 文档head全量9748P/1F：`test_real_conversation_round_trip_persists_skills_sse_and_three_turns` 第三轮消息pending。原样定向5P/1F复现，不当作单次环境抖动，也不覆盖失败收据。
3. 本树代码地图为空，query只返回正门；未作空图架构结论。精确读测试、runtime、store及git show c50714f7：run先claim终态，message紧跟revise。两次落盘，取消竞争决定claim必须先行；测试已存在 `_wait_message_terminal` 供引用/追问使用，三轮 `_send` 却未使用。
4. 最小修复：`_send` 先等run、再等message，返回二者既有返回值；每轮后续读取也不会抢跑。等待仍10秒，原状态、内容、引用、技能、SSE断言不变。已有消息等待补HTTP raise_for_status，错误不伪装成重试。
5. 新增事件屏障回归：真API、真store；claim完成后暂停消息终稿，只有第一次GET真实读到pending才放行。必须真的经历窗口，且_send返回时消息已完成，不用sleep赌机器调度。初次适配器桩漏ContinuousTurnResult必填字段，门禁报run failed；补齐后才产生下述通过读数，失败日志仍保留。
6. 进程内变异禁用消息等待（不改磁盘）稳定1F，断言“_send仅等run，未等消息终稿”；正确版本文件7P。变异在旧等待形状上有效，不只是测试返回值桩。
7. 更新#748范围为状态文档+测试同步补漏，未改runtime、规则、生产配置、数据。最终head及合入main仍分别跑完整四叶，最终结果放#748评论而非为了嵌入SHA不断提交文档。

## 方案对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 反复跑原样测试直到绿 | 漏报竞态，先前9749P已证明能偶然通过 | 否 |
| sleep、增大超时、skip/xfailed | 碰调度或放宽验收；原错误不是超时 | 否 |
| runtime把消息写到run claim之前 | 改取消竞争/崩溃语义，扩大已明确合同 | 否 |
| 仅第三轮最终GET轮询 | 修当前断言，但下一轮仍可能抢读前一轮pending | 否 |
| _send统一复用既有消息终态等待 | 读哪个对象就等哪个对象；保持全部断言与有限上界 | 采用 |
| 事件屏障+禁用等待变异 | 固定因果窗口，证明门禁能杀掉原失败形状 | 采用 |

## 证据与边界

根 `~/.finance-runtime/release-merge-20260916/`：
- docs-pytest.log：1F/9748P，Python收据20260915T171122Z-e2e7d11a.json。
- docs-integration-recheck.log：1F/5P，收据20260915T171217Z-e2e7d11a.json。
- message-wait-focused.log：新桩缺字段失败，不能读成修复成功。
- message-wait-mutation.log/.exit：禁用等待1F/exit1，1.04s；收据20260915T172254Z-e2e7d11a.json（修改中定向）。
- message-wait-fixed.log/.exit：7P/exit0，23.95s；收据20260915T172320Z-e2e7d11a.json（修改中定向）。

这些定向读数不冒充#748最终head、main全量；最终精确revision与merge状态以#748 API/最新评论核实。原主检出大量他人改动未动，文档/测试只在独立分支树提交。8792仍e40f22b83717，未部署，不重新写共享旁路库。

## 后续 / 不要做

#748门禁红则留开，不因“只改测试”豁免；绿后完成此次合并状态回写、最终main再验。人工至少30条stage_manual、另行部署授权与自然20次成本样本仍是独立后续，不能在本轮代填或花费API凑数。

迁移原则：终态的有效范围属于被提交的对象，跨对象投影须等自身完成信号。屏障回归已归位到测试而非一次性脚本；通用原则记agent-memory，harness-reference当前BUILD.md脏，不覆盖它。
