# fix/extraction-first-closeout · 工单 #53 提取前置 P0 · 第五轮收口

## 这个分支做什么
#53 整条链（P0 + 四轮返修）重放到最新 `gitea/main` 之上（merge-base = main，可快进），
加第五轮收口：自查 2 项 P2（V1 同秒不同确认动作共享 script_id；V2 导出残片只有预览、不可逆）
修复 + 14 条新测试 + **变异 runner 入仓**（31 条冻结定义）。
收据（唯一读数与 SHA 来源）`docs/verification/2026-09-14-extraction-first-p0.md`
§1.2 / §3.5 / §4 / §6。

## 当前状态
工程收口完成，**未推、未合 main、真人实验未开跑**。顶端以 `git log -1` 为准，不抄 SHA。
- 变异 31/31 RED→GREEN + 还原全绿；runner 与冻结定义已提交（`scripts/review_probes/`），
  证据 `~/.finance-runtime/reviews/extraction-closeout-20260915/mutations-<sha>/`（complete=true）。
- 全叶门禁在专建 gate 树全绿；全量收据 `check_test_receipt.py --expect-revision` 绑定 exit=0；
  对冻结基线（= 当前 main）的差量逐条点名。
- 三、四轮复审的 20 条探针在被测树重放 20/20 绿。
- merge-tree 对 `gitea/main` 预演 0 冲突（收据 §8）。

## 下一步
1. 下轮复审固定**当时顶端**复核；通过且**用户明说**才合 main，不推不合。
2. 合并后清理：`feat/extraction-first-p0` 与各 QC 分支、工作树 `~/fwp-wt-extraction-first-closeout`、
   `~/.finance-runtime/reviews/extraction-closeout-20260915/baseline/` 与 `gate/` 两棵 detached 树。
3. 真人实验（spec §7 三项阈值）仍待用户填写，工程完成不替代真人效果。

## 踩过的坑（本轮新增，前四轮见 feat-extraction-first-p0.md 历史与收据）
- **QC 快照目录里跑探针，测的是快照里的旧代码**：`/private/tmp/extraction-qc-<sha>/` 是整棵
  冻结仓（自带根 conftest.py），在里面收集 = import 旧 intelligence，10 红全是已修缺陷在旧代码
  上的红。探针要复制到中立目录、从被测树根跑。**红先归因再入档，两种跑法都留档。**
- **「跳过的锚点等于没有牙」已从纪律变成 exit code**：runner 锚点失配直接中止，不靠人记得。
- 幂等键第四课：键修对了，**以键为输入的派生身份（record id / 事件指向）也要跟着走**——
  键与 id 是两层，各要有自己的牙。
