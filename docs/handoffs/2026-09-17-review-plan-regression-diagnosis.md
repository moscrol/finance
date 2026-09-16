# 2026-09-17：09-16 缺数是日更档位被误改，不是自建链路未实现

## 结论与前次更正

用户指出「全量复盘不是已经修复成自建版本了吗」。核查确认：自建 `local` 模式已经实现、合入，
且 09-14、09-15 生产同步成功。09-16 缺数根因是 **09-15 22:29 的另一会话将两个装机 plist
从 local 改为 auto 并重载**，不是自建计算代码缺失。

本结论取代 `2026-09-16-l2-scoped-deployment.md` 的恢复顺序第 1 条，以及 PR #773 评论 4867
中「先确认复盘会登录」的建议。登录报错是错误选中旧计划后的直接失败点，不是应恢复的日更依赖。
纠偏已通过 `intelligence.cli record-correction` 登记，id=`e30f5f50dacc`。

本轮只诊断和更正交接，**没有修改任务配置、部署代码或生产数据库**。

## 证据链

1. 已合提交 `198b95f0`（09-12 17:47）明确固定两份仓内 plist 为 `local`，理由是复盘会不再作为
   日更主源。`gitea/main@d433b907` 中仍为 local。`tests/test_eval_launchd_wiring.py` 也断言两者 local。
2. 真正同步代码根为 `~/finance-workspace-sync@6382c13b`，不是旧主检出树。
   它包含 `PLANS=(full, cheap, local, auto)` 及 `build_local_plan`，也包含已合预检修复 `4baa6516`。
3. 生产 `logs/daily-full-review.out.log`：
   - 09-14 18:30：`plan=local (requested=local)`，跳过 CDP/登录检查，18:33:35 同步成功。
   - 09-15 18:30：同样 local，18:35:07 同步成功。
   - 09-16 18:30：变成 `plan=cheap (requested=auto)`，登录/连接预检失败，子流程 rc=3，未发布 staging。
4. 两份 `.plist.bak-fix-plan-20260915` 都是 local；当前两份装机 plist 与 launchctl 有效配置都是 auto。
   sync 的备份与当前环境差异只有 `REVIEW_SYNC_PLAN: local -> auto`。
5. 操作来源已追到会话 JSONL（仅定向解析相关记录，没有复制其他会话内容）：
   `~/.pi/agent/sessions/--Users-a77-finance-workspace-private--/2026-09-15T03-38-39-114Z_01a0a325-3289-7057-b176-9a3b935afe15.jsonl`
   - 834/838/842 行：在 `~/finance-workspace-private` 查询旧同步脚本，得到不含 local 的旧白名单。
   - 846 行：`git log --all -S "'local'"` 搜单引号字符串；实际新增白名单使用双引号，搜索无结果不能证明不存在。
   - 848 行，UTC 14:29:32（本地 22:29:32）：断言「代码从来没有这个 plan」，执行
     `PlistBuddy -c "Set :EnvironmentVariables:REVIEW_SYNC_PLAN auto"`，备份并重载 sync/finalize。
   - 849 行：操作输出明确为两份 `-> auto`，两个任务重新注册。
   - 862 行：该会话事后报告改档行为与上述错误理由。
6. 本轮零副作用探针导入实际同步目录代码：`resolve_plan('auto', '2026-09-16') == 'cheap'`；
   `preflight(require_fupanhui=False) == []`，并将网络调用设为必报错，实测网络调用 0 次。
   local 的 16 步存在，未执行写库步骤。
7. 对生产库只读运行 `check_daily_review_data.py 2026-09-16 --phase data --plan local`：
   所选 19 张事实/特征表当日均 0 行、最新 09-15，exit 2。不是完整数据被错误显示为缺失。

## 因果链

```text
看错代码树，误判 local 不存在
  -> 装机配置 local 改 auto
  -> 09-16（周三）auto 解析为 cheap
  -> cheap 仍要求复盘会连接与登录
  -> 18:30 预检失败，未采集、未发布当日数据
  -> L2 当日 top100 候选为 0，三榜未完成
```

09-16 的 L2 部署仅改 finalize 代码根并保留原环境，故未造成这次改档，但也未识别并修复它。
前次部署的 115P 对代码与仓内模板成立，不涵盖装机配置与仓内模板的逐项一致性。

## 正确恢复方向

1. 备份后将 sync/finalize 的有效档位同时恢复 local，保留已验收 L2 独立代码根，不把整个旧 plist 原样覆盖回来。
2. reload 后核对 launchctl 有效环境、脚本导入来源、日期解析与选中步骤；同步生产代码应来自专用同步目录。
3. 沿既有 daily-full/S7 staging 正门补 2026-09-16，数据门按 local 验。已跨日，不能把当前日快照标成 09-16。
4. 当日数据通过后再跑该日 L2、生成段，分别验证。发现生成段仍不传计划时先修其接线，不能再通过改 auto 掩盖。
5. 后续部署验收增加「装机生效配置 vs 已验收模板/明确覆盖」检查；只测仓内 local 断言挡不住人工改 plist。

未作承诺：恢复 local 不等于已补齐数据；历史取数、完整日包解压与发布仍须实际验证。
本轮没有新建修复分支或运行补数。8792 不涉及本问题，不应随此切换。
