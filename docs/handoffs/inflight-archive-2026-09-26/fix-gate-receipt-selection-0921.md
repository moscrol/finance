# 门禁收据本地诊断，正式方案归#814

## 这个分支做什么
定位历史/运行时包装器收据脱节与UTF-8 Bash变量误解析，留下反例；不是第二正式生产方案。

## 决策与被否方案
本次stdout路径与实测退出码绑定；否并发global latest冒充本轮。
查见#814已含唯一收据、Config重入所有权、只读身份后停止第二路线；否重复长期维护。细节见docs/research-tail-closeout-0921上的`../2026-09-21-research-tail-forward-integration.md`。

## 当前状态
本地c35f61d37db3a26916902aeae688f82458591ebd，源码clean，未推/未开PR。基于f2c3e9e1，仅改scripts/run_main_gate.sh和tests/test_run_main_gate.py。#814评论5363有接替指针，不能拿本诊断成绩代签其K3独立审核。
17:53操作员对本轮pytest PID51140发SIGINT，冗余全量已停；收据8146P/22S、exit2，包装器rc4。后台均已结束，不等待旧PID、不重跑求绿。

## 未验证 / 已知边界
无全量PASS、无独立审核；不包含#814同进程同目标重入的完整所有权方案，不可等价替代。未合/部署/接管#814恢复；原K3异常结束仍由原线处理。

## 下一步
只保留诊断代码/patch与撤保护原件；正式修复和后续审核沿#814。不要为本枝新开生产PR。

## 踩过的坑
FWP_TEST_RECEIPT_DIR写方未接，旧包装器查错目录；报错$LATEST紧跟中文括号在Bash/UTF-8下被吞为变量名，原历史/运行时rc1保留。显式回放0不是原包装器0。
SIGINT清理引发tmp_path KeyError及退出码矛盾，门禁拒绝。临时完整stdout被包装器自身清掉，只保留真实留下的尾部和收据，不宣称完整中断日志。

## 已验证
固定15P、Ruff0；六项撤保护各断言红、基线/恢复绿；前端六步0。作者门禁/领域原始回放分账。
归档：`docs/verification/2026-09-21-research-tail-forward/author-and-small-review/`，含patch、15P/中断收据与operator-stop。交接只在docs分支，源码身份未变。
