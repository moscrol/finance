# fix/kb-path-fail-closed

## 这个分支做什么
金融仓更好消费 KB：路径 fail-closed、队列盯年龄、L3 页读侧、出队去伪。

## 当前状态
干净树 `/Users/a77/fwp-wt-kb-path-fail-closed` @ `76e247c1`。Gitea #379 open，未合。主仓脏树不要碰。

三刀已提交：① 死路径不再回退 Desktop/`/Users/lbq`；② 回执盯 oldest received age，`resolved_themes` 仍只认 ingested，ask 可读 L3 wiki 页、不写 relations；③ 出队丢掉完整概念页/过宽 `concept_ingest`，占位页和真缺仍抛，disclosure 不动。

## 未验证 / 已知边界
- 全量 pytest / webapp 未跑（Gitea 无 CI）。
- 未钉 `gitea/main`+发布索引（须绑 L3 relations 第二落点）。
- `fact_status` 等 KB `disclosure/fact-status-evidence-index` 合 main。
- 存量 received 里 Mini LED/石油等是 escalate_stub，不是完整页，**不要按「有页」skip**。
- KB 主检出脏且整份队列未跟踪，不在那棵树 mark。

## 下一步
1. 合 #379 等你确认；合前本机 ruff + pytest。
2. 存量 disclosure 按 oldest age 消费（最老：8/17 光通信）。
3. 占位页升 L1 走 concept-ingest，不自动写正文。
4. 再谈钉发布树。

## 踩过的坑
- `QueueHealth.open_count` 写了测试读不算，生产 `render_status` 必须读。
- 「有概念页」≠ skip；8/24 分诊区分完整页 / 占位 / 过宽 / 真缺。

## 已验证
路径/队列/L3/出队门：相关 pytest 绿；path-literals 49→37。

## 工具沉淀
出队门复用 KB `auto_triage_ima_queue` 口径，未抽新脚本（一次对照）。
