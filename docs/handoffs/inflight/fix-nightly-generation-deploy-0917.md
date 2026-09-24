# 夜跑生成根正式部署

## 这个分支做什么
将装机finalize生成段接到已验双根launcher，保留L2/数据根，补真实launchd验收。

## 决策与被否方案
- 现役wrapper最小接线，生成独立FINANCE_GENERATION_CODE_ROOT；否全局换根/覆盖旧wrapper，会回退L2暂停逻辑。
- 完整冻结387028b8，只在生成子进程切代码根；数据/users/episodes不迁移，不改S7或8792链。
- 展开及回滚：`docs/handoffs/2026-09-17-nightly-generation-deployment.md`。

## 当前状态
代码2fa28a4f、日期文档73cd22f6已提交，未push/合main。装机wrapper与finalize plist已部署，三态配置一致；生成树`~/.finance-runtime/finance-generation-387028b846a2`干净，L2仍d433b90788c0，plan=local。
真实launchd主动触发09-17 23:44:01–23:45:44，exit0；任务结束、目录锁释放，无待续主管。不是仅终端补跑。
收据根`~/.finance-runtime/generation-deploy-20260917/`（RUN）；备份与哈希见deployment-receipt.json，归属看冻结摘要，不读以后覆盖的canonical摘要。

## 未验证 / 已知边界
- 下一次20:40时钟触发未发生；18:30 sync未重跑。本次L2已有complete故跳过重扫，非新包验收。
- 方法daily rc0但capture=refused：旧v3协议不接受当前v6标签。未迁移/登记成功，不能篡改旧协议或回拨时钟。
- 快照仍前次22:03恢复发布的09-17，本次没改；readiness一致不是Workbench真实模型episode验收。
- KB9任务只receive到queue-4，不apply/解他人UU；无真人视觉验收。静态根预检不是OS沙箱。
- 本枝未跑全仓Python/前端/E2E/registry四叶或独立模型QC；旧作者全量不替本枝合流准入。原返修交接的“未部署”是旧状态，以本单为准。

## 下一步
观察下一夜真实自动触发；方法新协议及active另办。源码合main须固定候选四叶+用户确认。重装不得从旧模板抹掉生成根。回滚先确认无任务、当前哈希仍匹配，再只恢复RUN里的finalize脚本/配置；不动sync/L2/数据。

## 踩过的坑
终端不继承plist环境，手动finalize须显式传两个代码根。方法命令成功不等于capture成功。通用作用域/三态核验已进正式测试；发布主管留RUN，不另建常驻框架。KIT/BUILD在独立harness枝0d52848已push未合，主树BUILD他人WIP未碰。

## 已验证
生成47P、原边界探针独立复跑7/7；wrapper固定2fa28a4f四文件87P（收据20260917T154229Z-2fa28a4f.json），内存删子进程根赋值被回归抓住。Ruff/zsh/plutil/diff通过。
真实生成19步PASS，同日/跨日/L2/报告门通过，12实物哈希与23:48 readiness已记；graph audit rc0。RUN内generation-summary-frozen.json、launchd-result.json、post-deploy-verification.json可复核。
