# 日期差异、严格截止与本地快照

## 这个分支做什么
逐来源真实日期交付事实，日期不同不整体拒答；用户严格截止由系统强制，local_only能读已有行情快照。

## 决策与被否方案
- 上界复用InformationCutoff，取用户/调用方较早日且保requested；否了只靠模型自觉。
- 新快照工具仅补有市场授权的local_only回合；否了放开联网market_data。material_only与封存无根均不探生产路径。
- 历史只读截止内日文件自身身份/质量，不借latest/meta；保NULL/0、原JSON下标，快照口径不冒充复盘主线。
- 严格截止隔离未来证据及文本/gaps/trace，并隔离缓存；否了只过滤证据列表。
- 展开：`docs/handoffs/2026-09-22-market-cutoff-snapshot.md`。

## 当前状态
源码b41c8d475+b1e04452b已提交，固定受测b1树e104eb0fc。证据f7d417238已封并核新250/250、旧68/68及200/200 Git对象；后续仅交接文档。结论AUTHOR_TARGETED_CHECKS_PASSED_ACCEPTANCE_BLOCKED。无push/PR/合main/部署/补采/生产写入；本轮检查进程已结束。

## 未验证 / 已知边界
完整Python未开跑：8GiB准入不足，最后约3.2GiB；b41等待器已停，不删他人数据/降安全线。独立Spec/Quality旧b41尝试因模型容量错误无结论，b1未审。新K3未跑，上轮AUTHOR_REAL_ENTRYPOINT_OBSERVED_NOT_ACCEPTED仍有效；旧两题judge unavailable/partial不翻案。
有限日期句式不是通用NLU或PIT证明；市场题误路由company/stock_deep_dive未修。未验后来main组合、夜跑或生产效果；未动8792。

## 下一步
恢复资源后核main及授权，在干净固定版本跑完整Python、独立两审，再用原两题真实conversations/messages复验K3写手+GLM判官，核截止/快照/公开稿/引用。改码则新SHA重新绑定验收。外部新K3目录的run_live.py仍为旧身份副本，不能直接跑。

## 踩过的坑
读取替身内抛断言会被loader吞掉：b41变异21/22，改为记录路径后断言，b1该项被捕获。口头中止进度误报已勘误。收据不能移签；外部runner有E702，不能称全部脚本Ruff绿。模式命中须核上下文，不用标识符形状泛放行。

## 已验证
b1干净固定：326P/JUnit一致、Ruff0、24/24变异、前端110P/E2E34P2S、registry五项0。精确收据20260921T165015Z-b1e04452；主树.venv-workbench解释器，依赖3328bed61f3e21ea。247原件/1,313,993字节相等，250内容文件+清单；扫描249文件/238命中/32唯一值均代码上下文，未分类0，非零命中认证。19651/19654/19276无监听；无本轮生产健康认证。
