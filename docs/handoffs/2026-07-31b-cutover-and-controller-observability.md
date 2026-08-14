# Session handoff — 切换落地 + controller 留证（2026-07-31 第二段）

**先读** `docs/handoffs/2026-07-31-harness-goal-and-references.md`（Start Here，目标/环境/待办/资料库的总入口，本轮已就地更新）。
这份只记本段发生的事和**留给你的决定**。

---

## 1. 当前状态

```
线上 8792     610feb21（已切，healthy）
              属主 launchd com.a77.finance-workbench（KeepAlive）
指针          /Users/a77/finance-workspace-runtime → finance-workspace-610feb21…
本地 main     801f56b0（比线上多一个 docs commit，无需重切）
工作 clone    /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
              ⚠️ 独立 clone、**没有 origin**；工作区干净
测试          3881 passed / 11 既有环境失败（两种配置一致）；ruff 165 = 基线
```

**回滚**（旧快照别删）：

```bash
ln -sfn /Users/a77/.finance-runtime/finance-workspace-028bab570b160f0166aa4c83865a29d1fc31e5c8 \
        /Users/a77/finance-workspace-runtime
launchctl kickstart -k "gui/$(id -u)/com.a77.finance-workbench"
```

> 注意：切换**前**实际在跑的是 `30d6471a`，不是指针指的 `028bab57`。回滚到 028bab57
> 等于比原状态新一个 commit；要精确还原就把上面路径换成 `30d6471a…` 那个快照。

---

## 2. 本段做完的（3 个 commit + 1 个 merge）

| commit | 内容 |
|---|---|
| `2ed27ca9` | 待办 A：controller 降级留证——`llm_failure_reason` 枚举 + `llm_failure_detail` 原文进 trace |
| `3cd94bbd` | 待办 D：核实 inc-4258 形状不成立，把「已输出就不回退非流式」钉成不变量 |
| `610feb21` | merge：`fix/foresight-required-outputs`（26 commit）→ 本地 main |
| `801f56b0` | docs：Start Here 归位 + 三个坑 |

两条都**零行为变化**。A 里刻意**没有**补分类器盲区（`LLM 调用失败（TimeoutError）` /
`LLM 预算不足` 仍落 `provider_unavailable`）——`stable_llm_fallback_reason` 同时是 judge 的
fail-closed 闸门（`_TRANSIENT_JUDGE_REASONS`），多认一个瞬时原因等于为观测放宽一次严格层。
盲区写在 docstring 里，要改先补 judge 侧测试。

---

## 3. 留给你的两个决定

### ① 推 GitHub —— 没做，需要你定并法

```
origin/main（GitHub）        0430d544   ← 共同祖先
本 clone main                801f56b0   = 0430d544 + 本轮 26 commit
数据仓 main                  901dcd7b   = 0430d544 + 它自己的提交
数据仓当前分支                fix/degrade-disclosure，压着 137 个未提交改动
```

本 clone 没有 origin，推要经数据仓。技术上 `origin/main → 801f56b0` 是快进、不会覆盖任何
东西，但推完**数据仓自己的 main 就变成 diverged**，下次在那边 `git pull`（还带着 137 个
脏文件）会很难受。所以停在这里等你决定：是先把数据仓那条线并进来再推，还是就让它分叉。

**切换不依赖这一步，已经切完了。**

### ② `.finance-runtime` 约 13G（106 个快照）—— 没动

属删除操作，不在批准范围。清理前 `git worktree list`，**线上在用的 `610feb21…` 和回滚要用的
`028bab57…` / `30d6471a…` 必须留**。

---

## 4. 下一步建议：待办 G

Start Here §4 新增的。线上实测（合并前后 A/B 一致，**不是本轮引入**）：

```
llm_budget : 本轮 LLM 调用 4 次（失败 0 次），其中 caller=synthesis 成功 6435ms
synthesize : status=fallback, fallback_reason=None, stream={}
smoke      : model.used=False, provider=None
```

`status` 的定义是 `"validated" if result.synthesis is not None else "fallback"`
（`conversation_orchestrator.py:2637`），所以它只是在说「synthesis 是 None」，
**为什么是 None 没人记**。先查 `result.prepared_synthesis_messages` 为空时是不是整段被跳过——
跳过和失败是两回事，现在共用一个 `None`。修法同 A：各给各的枚举。

和待办 A 是同一个病，也是 Start Here §3「信息在系统里但没送到」的第五例。

---

## 5. 会让你测错代码的三件事（本段代价最大的收获）

细节在 Start Here §2 坑 0，这里只放结论：

1. **决定加载哪份代码的是进程 cwd，不是 PYTHONPATH。** `python -m uvicorn` 让
   `sys.path[0]=''` 排在 PYTHONPATH 前面，而数据根 `/Users/a77/finance-workspace-private`
   底下就有一个 `intelligence/` 包。本段第一次 canary 就这么测成了数据仓工作树
   （当时压着 137 个未提交改动），**而原有的两条防坑检查全绿**。
2. **cwd 在启动时解析符号链接** → 只切指针不重启完全无效。线上此前跑 `30d6471a` 就是这么来的。
3. **8792 属主是 launchd KeepAlive**，手工 `kill` + `nohup` 会被它抢走端口，
   自己 bind 失败静默退出。重启用 `launchctl kickstart -k`。

起完 server 必须验三件事（`/api/health` 的 `source_revision` 报的是数据仓，判断不了代码版本）：

```bash
grep -c "address already in use" <log>                  # ① 必须 0
ps eww <pid> | tr ' ' '\n' | grep ^PYTHONPATH=           # ② 必须是你的快照
lsof -a -p <pid> -d cwd -Fn | grep '^n' | sed 's/^n//'   # ③ 必须是你的快照 ← 真正决定的
```

**判断一个 degraded 是不是自己引入的，别猜——跑 A/B。** 同一问题、同一 env，分别打合并前后
两个快照的旁路 server，比 `trace.jsonl` 里 `synthesize` 那步的 `output_summary`。
本段就是这么把「degrade 是既有行为」钉死的，花 1 次 LLM 配额。

---

## 6. 两条方法论（本段又被验证一次）

- **测试要先证明自己能抓 bug。** A 的前三条测试我先用了「宁德时代最近怎么样」「PQC最新消息」，
  都被确定性路由层截胡、压根没走到 LLM——断言全绿但什么都没测。换成「随便聊聊未来」才真正
  覆盖，成功那条加了 `called` 哨兵钉住这点。D 的闸门测试也做了摘掉即红的验证。
- **「核实」是要拿实据的，不是拍脑袋说风险低。** D 原本的判断（合成层不执行工具所以风险低）
  结论对，但真正让人敢下手的是那三条可复核的实据（全仓一处 `"stream": True`、两条回退触发点
  都在首个 delta 之前、流中断抛的是 IncompleteRead）。
