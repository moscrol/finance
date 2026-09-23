# Runtime 合同量具与收尾验收

## 这个分支做什么
修量具、验K3局部产物及#884工程门禁；不改运行时产品行为。

## 决策与被否方案
用户新授权“那你继续做到done，直到可以收尾部署”。继续修复与验证，不把就绪冒充已部署，不擅自合main。
已合入main b59d6eed0356（75dfd08c2），补日志437202489。先冻结再验；否决给旧收据换revision。
Python全量原生环境，前端/registry外层沙箱；有其他全量pytest不准入，磁盘至少12GiB。旧1800秒超时不是产品失败统计。
独审按合同分批、固定K3、有限预算；宿主复跑和作者测试不代独立签字。部署与生产写入不在验证范围。

## 当前状态
#884仍WIP，未合main/部署。新轮入口：`~/.finance-runtime/reviews/pr884-closeout-20260923-04/`，授权在authorization.json。完整门禁及独审尚未执行完；缺verification.json或叶子不齐即BLOCKED。
旧轮`pr884-gates-20260923-03` Python到1800秒中止，无终局收据/JUnit；前端与registry绿不能补齐。失败现场保留。
磁盘清理已完成：`disk-cleanup-20260923-pr884/verification.json`，仅删6组成功闲置scratch，保留原始证据。

## 未验证 / 已知边界
当前候选全量门禁待跑；C1-C8独审仍NOT_REVIEWED。未验完整跨进程续跑driver、跨机锁、真实计费、生产问答；spool仅at-least-once。
本机全量不认证CI平台900秒预算。main继续前进须重做组合验收，不移签。

## 下一步
冻结干净候选，新目录跑完整Python/前端/E2E/registry及分批独审；核验PR真实head/base和merge-tree。全部通过后再请求合并/部署确认，不自动撤WIP。
不重复合#865、不动别人的工作树、不中断他人测试、不买额度。

## 踩过的坑
旧tail只在pytest退出后吐末尾，超时无进度；现保留完整实时pytest.log.txt，tee/tail失败拒绿。日志不是最终收据。
外层Seatbelt曾干扰被测沙箱/RSS；Python不套它。Ruff不检查Shell，脚本用bash -n。

## 已验证
日志回归60P，目标Ruff及bash -n通过，原件在新轮logging-regression.*。旧241+23件归档及28种变异仅属其原revision，不移签。
