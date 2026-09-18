## 这个分支做什么
复用Workbench/Episode/history_query与主库，完成市场参照→强势对象→启动/峰值→接力→同口径特征。

## 决策与被否方案
| 选 / 否 / 理由 |
|---|
| 原始用户链+可信合同 / 助手旧答授权 / 防续问扩权 |
| 总授权、观察窗、截止分开 / 一个日期覆盖另一个 / 防偷看未来 |
| JSON边界转换 / 取消参数冻结 / 不为遥测削弱合同 |
| 保存事实第二实现 / 产品公式重跑叫独立 / 避免同源算错 |
| 保存失败继续返修 / 重跑刷成功或工程绿即验收 / 不混证据层 |
展开：`docs/handoffs/2026-09-18-history-market-anatomy-live.md`。

## 当前状态
代码fbd8f2a6、归档3ac74ef5已推WIP #783，未合未部署。固定版本工程通过，第二组真模型四题整组失败；不再等待后台。独立树`~/fwp-wt-history-market-anatomy`，两组隔离服务已停。生产8792仍bf662e93；未改行情库、画像、每日链。
能力图谱/MOC由vault自动同步2cbc314c；harness工具登记fef36d6已推未合，共享BUILD未碰。接着修参数诊断被日期门吞掉；本节点尚未修该问题。

## 已验证
fbd8固定干净树：Ruff、Python11501P/81S/2X、前端107P及三步、浏览器34P/2S、registry五项0；pytest收据八项过。新目录`docs/verification/history-market-anatomy/fbd8f2a6/`含四原答、调用/引用manifest、哈希及裁决acceptance.md。
实际zhipu/glm-5.3-flash同会话四轮保持real/local_only、01-01..09-15授权与09-15截止；第4题不再mappingproxy崩溃。live六原件第二实现20845检查/29skip/0error；非独立人员QC。

## 未验证 / 已知边界
业务仍失败：market类比漏类型后未恢复；股票/板块rank异窗、正文偏前向；immature误当没接上/必须确认；第4题未做启动特征和控制组比较。E号都存在不等于支持正文。
analogues排序未独立验算；未做独立QC/浏览器真研究交付/完整方法认证。隔离停服前缺health-after；首轮漏隔离EpisodeStore，失败事件仍在共享state/episodes。
vault_lint存量19错17警告；图谱audit通过不认证运行可达。每日水位/代码根与方法回检另案。

## 下一步
先补窄回归：可信诊断与事实分型、market漏参反馈、接力成熟度解释与原件主动读取/输出合同。新代码另冻SHA跑门禁和原四题新隔离根，勿覆盖失败。不合main、不部署，分别待用户确认。

## 踩过的坑
immature是峰后不足5日，不是失败；源峰无需先回撤确认。成员路径不等于个股启动。volume_ratio是百分数；标签看专属source。cutoff非入库时点。completed/semantic passed/算术零error都不是业务通过；旧收据不代签新SHA。
