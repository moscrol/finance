# 2026-08-16 长尾 15 题 live A/B 窗收口交接（权威版）

roadmap_ref: 另案（P5 质量战线；`docs/verification/2026-08-16-longtail-baseline-frozen-set.md`（FREEZE_ONLY）的 live 后续；权威设计与预注册见 `gitea/main` 的 `2026-08-16-longtail-baseline-skill-injection.md` §3）

> 权威版在本文件。对照数字在 `docs/verification/2026-08-16-longtail-baseline-live-ab.md`。
> 主 checkout（`docs/dsh-absorption-spec`）只留 stub，**不要在那条分支提交**。

一句话：95 槽位 live A/B 已于 13:19 在**双臂健康**的前提下全量重启，15:37:57 `all slots processed`，15:39:07 sidecar 干净退出、8793 已验空。此前 12:48-13:07 的数据因两臂健康不对称（off 臂 rag_worker 挂死）已清出重跑、账留全史。本文件交代现场终态、清污、收据口径、已做清理和环境坑。

证据等级：**[实测]** = 2026-08-16 当场跑过命令/读过产物。

## 1. 现场终态 [实测]

- 收口判定已满足：`runner.out.log` 末行 `all slots processed` **且** `runs/` 覆盖 95/95。
- runner：托管后台进程 pid **36401**（13:19:41 起），顺序跑 95 槽位 = 15 题 × 2 臂 × 3 重复 + 5 护栏题（仅 on 臂 ×1）。15:37:57 自然退出；收口时 `ps -p 36401` 已空。`runner.pid` / 日志 / progress / `score.json` 原地留档。
- off 臂 = 生产 8792，`773b3d7e` 干净树，收口后仍 ready 200（rag_worker=true）。**未重启、未替换。**
- on 臂 = 8793 sidecar（pid **21888**，12:50 起，`ASK_LONGTAIL_BASELINE=on`，同 SHA）。**15:39:07** 干净退出：`sidecar.err.log` 写 `Shutting down` → `Finished server process [21888]`（mtime `2026-08-16 15:39:07`）。收口时 `ps -p 21888` 已空；`lsof -nP -iTCP:8793 -sTCP:LISTEN` 无 LISTEN。
- 查进程一律 `ps -p <pid>`——**本机 `pgrep/pkill -f` 对这些进程系统性失明**（见 §6）。
- 只读计分：`scripts/score_longtail_live_ab.py` → `~/.finance-runtime/longtail-ab-20260816/score.json`（`2026-08-16T07:38:26+00:00`）。outcome=`CONTRAST_PARTIAL`。不翻 `ASK_LONGTAIL_BASELINE` 默认。

## 2. 清污记录（收据必须如实引用） [实测]

- 12:09-13:08 生产 8792 的 rag_worker prewarm 失败且被 `_STARTUP_FAILURE_TYPE` 钉死 → `/api/health/ready` 一直 `not_ready`（critical 缺 rag_worker），而 on 臂 8793 一直 ready。**两臂健康不对称 → 该时段对照不可归因**。
- 已删除的槽位文件：`runs/off_L0{1..8}_r1.json`（12:51-13:07 收集）。`progress.jsonl` 前 8 行保留原始读数（151.0/152.5/151.5/37.0/153.0/93.0/81.5/104.0s），只作取证，不入对照统计。
- off:L09:r1 被 13:08:50 kickstart 中断，无 json、无账行，重启后正常重收。
- 对应 run 目录仍在 `~/.local/share/finance-workbench/users/longtail-ab-0816/runs/`（`run_20260816_1251xx`-`1307xx`），另有 3 个启动残留孤儿 run（12:45/12:49/13:10）——都**不入收据统计**，凭 progress.jsonl 的 slot 行对齐。

## 3. 健康臂早期读数（供核对，不预判；结论以收据为准）

off 臂重跑后：L01 153.9s degraded（134 字边界句）、L05 159.2s degraded、L04 37s completed——与带病期同形，说明该现象与 rag_worker 无关，已立案 `2026-08-16-outlook-verification-budget-regression.md`。判读时记住权威设计 handoff §3 的钉子：outlook 档剥句/降级叠着 #79 比较集绑定，**本刀（骨架）独有信号在残差档**；不要把 outlook 档的预算降级算进骨架的账。

## 4. 收据（已落）

权威对照收据：`docs/verification/2026-08-16-longtail-baseline-live-ab.md`。格式照 bookgap S2。

- 度量（预注册于权威设计 handoff §3，不放宽）：非空 direct_answer 交付率；judge 剥句率；evidence_bound_rate（5pp 门槛）；token/墙钟成本增量。分层报告 outlook vs residual。
- 空壳 vs 诚实缺口：无检索时正文明写「未取得」算合规交付；不要用「看起来有字」当成功。
- 护栏：FREEZE 已登记口径——只跑 on 臂 ×1，确认 `【长尾回答骨架】` 不出现。不补跑 5 槽 off 臂。护栏墙钟 86–203s。
- 回链：FREEZE_ONLY 收据的 `live_ab_ran` 指向对照收据，并写明清污重跑（引本文件 §2）。夹具 `sample_design.live_ab_ran` 保持 `false`（加载器要求）。
- 每槽附 run_id；degraded 槽位不折叠进 failed，单列。
- residual：合规 +53.3pp，eb −50.0pp（诚实缺口替换未核验候选，不是绑定变差），剥句率 INCONCLUSIVE（peel_n=0）。不翻默认。

## 5. 收口后清理（已做）

1. 8793 sidecar 已停：pid **21888** 于 **15:39:07** 干净退出（`sidecar.err.log`：`Shutting down` → `Finished server process [21888]`）。`ps -p 21888` 已空；`lsof -nP -iTCP:8793` 无 LISTEN。launcher 注释明写「评测结束即停，不要用它替换 8792」。
2. runner 托管进程已自然退出，无需再杀；`runner.pid`/日志/progress/`score.json` 原地留档。runtime 目录 `~/.finance-runtime/longtail-ab-20260816/` 不删。
3. **8792 未动**；未翻 `ASK_LONGTAIL_BASELINE` 默认——翻默认必须走对照通过后的另开 PR（权威设计 handoff §2.4 第 4 刀）。

## 6. 环境坑（是否升格 lessons 由 owner 决定） [实测]

1. `pgrep/pkill -f` 对 agent 会话拉起的长 argv/大 env 进程返回假阴性：12:48-12:51 三个 runner 叠启（`start_detached.sh` 的 pgrep 防重入护栏因此失效）、13:06 一次 pkill 实际没杀中、13:09 叠启复发，均由此坑造成。杀进程前必须 `ps -p <pid>` 核对 argv。
2. `nohup + &` 从 agent shell 拉起的孤儿会随 shell 清理死亡（13:09 的 runner 存活 <1 分钟）——长活进程用托管后台或真终端。
3. `launchctl kickstart -k` 连带杀掉服务进程树内起的一切（12:09 部署即因此中断当时 in-flight 的运行）；kickstart 前先确认树内没有别人的活。

## 7. 边界 / 不做什么

- 本窗已关。8792 不因本收口跑任何其他 live 批（包括 10 题窗，见其前置闸）。
- 不改 runner/夹具/触发条件——那是重开窗，不是收口。
- 不在 `docs/dsh-absorption-spec` 提交本文件。
- 10 题窗仍等分诊/预算回归处置，不因本窗收口而开。
