# fix/sync-code-root · 夜跑代码根 + staging 旁路 + L2 独立于同步守卫

## 状态：已合入新 main、未推未开 PR。门禁绿，但**夜跑不能宣告恢复**

尖 `7a4d8885`。已 merge `gitea/main@694584df`（含 PR #738）并解两处冲突。
合入预演 `bbd008ee` 全量：ruff 绿、pytest **9461P / 0F / 77skip / 1xfail**。

## 本轮新增：工单 #51（L2 不再被同步失败连坐）

`finalize)` 里 `run_l2_branch` 已提到质检守卫**之前**——L2 读逐笔日包，不依赖同步段
产物。守卫在前的代价已经发生：`feature_l2_*` 两表 max 停在 2026-09-09，9-10 / 9-11
两天没有行。**生成段的门没松**：守卫非 0 仍中止、L2 失败仍挡住生成、两个失败各自
notify、退出码不吞。没有恢复 `all)`。

「不许嵌套调 S7」从文本断言改成行为测试（`_run_nightly_finalize`：真启动脚本 + 假
python/moneyflow/osascript + `zsh -x` xtrace）。原断言过滤掉了以 `/bin/zsh /Users`
开头的行，而真实嵌套调用恰好是那个形状，塞回去照样绿。变异测试双向验证会咬。

#51 验收：**1/2/3/4 已做；5（装机副本同改）、6（9-10/9-11 补数）未做**。

## 补跑命令改了，别再用 `&&`

```
nightly-full-review-s7.sh <date>; s7=$?
nightly_full_review.sh finalize <date>; fin=$?
echo "sync rc=$s7 finalize rc=$fin"; [ "$s7" -eq 0 ] && [ "$fin" -eq 0 ]
```

`&&` 会让同步失败时 finalize 根本不启动，L2 跟着丢；裸分号又会让同步失败被收尾的
成功掩盖。所以两条都跑、两个码分别接住。SKILL.md 与 ops-pitfalls.md 已同步。

## 根解析缺省落到会漂的共用树：同一形状五处

1 sync 子进程 `SYNC_ROOT` · 2 三处质检闸门 · 3 `run_sync()` 裸相对路径 · 4 两个手动
入口缺省 —— 均已修。**5 生成段 `python -m intelligence.cli daily` 未修 → 工单 #50。**

## 装机副本（口径要准，别跑安装脚本覆盖）

5 个脚本字节一致；s7 仅注释不同；6 份 plist 配置等价（比 `EnvironmentVariables`，
不是字节）。`nightly_full_review.sh` 装机副本与仓内源有三组实质差异：moneyflow 根用
`$DATA_ROOT`、**缺 L2 挂账暂停**、**缺三处 `skip_method_flywheel` 留痕**（9-11 没有
跳过记录就是它）。装机副本**不在仓内全量的验证范围内**，备份 `*.bak-pre-*-20260912`。
暂停开关差异可能是 L2 迁闲鱼日包后的有意决定，动之前先找 L2 负责人确认契约。

## 未决

1. **9-10 / 9-11 补 L2**：`run_l2_pipeline.sh <date>` 逐日，读数写进验收。
2. 装机副本同改 + 干净 shell 实跑（#51 验收 5）。动手前先答工单 §3 三问。
3. 生成段代码根 → 工单 #50。
4. 名单基线停在 9-02；同花顺日更没接进 `local` 的 16 步（相关表停 9-08）。本轮未复算。

背景与被否方案见 `docs/handoffs/2026-09-12-nightly-code-root-outage.md`。
