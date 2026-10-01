# semantic-consistency / 2026-10-02

## 授权/边界
PR14 draft，不合main、不部署、不改默认off。用户持续GLM总额度开放，ask_user glm_open_budget_scope=preservation_e2e允许必要修复；分批预注册、保留失败、不选优，不逐批问额度。其它模型不自动获授权。旧批及本日01~05均关闭，STARTED_ONCE严禁重启；累计53物理请求。新批可沿用授权，但须新计划/停止条件。

## 最新04：工程清晰，模型改善refuted
实现7fe24b0f52e741ab73d82a3aa73e62fdaf07b918，仅ask_blocks.py历史行+12新测试。不改SQL/snapshot/source_date，显式自然日含边界窗口、各主题首末观测日及max_date==latest的表内截止日记录。有/未见不推市场存在/不存在；不用被截断的30行当前预览做成员判断。
修前9F3P，6/6变异；clean9文件752P/12.67s，官方收据20261001T174512Z-7fe24b0f-d995b79b6da7，checker同SHA/clean/无绕过/基座漂移0。新卡360字符无截断，snapshot不变。图构建缺uvx，详报告。
26零网预检；固定越界旧→越界新→历史新→历史旧。新臂仅内存换canonical E7并重算hash/bindings，原archive/工具事件不改；两对真实wire只差E7标题/正文。8HTTP/8响应/身份0，各2轮；四臂首判只拒17，末判passed。越界15新旧均未拒，正确历史与方向14均保留。范围判据0/0/1/1，完整内容0/4；工程通过不等于模型改善/生产验收。

## 05：焦点两案限定confirmed
04两个新卡首native完整上下文，点名15；新短任务+submit_focused_scope_check。11预检；2HTTP/2响应/身份0，原样64ID。越界false（历史统计/截止日未见不能支持当日归属），历史true（9/8/5及医药事实支持）；7.209/6.499s。未跑完整verify、没有把焦点报告接放行。同模型家族，范围/任务/schema/token帽一起变，非纯注意力A/B，也不是自动全篇覆盖。本轮10回包low均未验证。

## 证据与下一步
报告docs/verification/2026-10-02-mainline-scope-rendering.md；私有根mainline-scope-rendering-20261002、focused-scope-diagnostic-20261002含全部freeze/live/acceptance/postcheck。下一步先设计固定全句/子断言覆盖与当前上下文重审，再验修复/保真、延迟/停序列；禁止人工点名已知问题后当自动方案成功，不重跑04/05选优。
01曾保住方向句但整篇未过；02提示词补充refuted；03逐句大报告首50s超时/身份2，无语义结论。R18旧失败、R24 refuted、R21 partially_confirmed保留；R26仅接口成功。R25 off控制门不因enabled授权放宽；R19保持955+11/旧exit2。
e7旧CI36895093589/36895093840五绿，19241P167S2xfail/1526.73s，checkout4bb1e0c9与e7完整tree a859e688同，不含新12测试或私有runner。新HEAD CI另收。main3a2718c6、生产healthy@2c394978/match=true、队列7385/hash、DB hash/0444未变。生产默认、完整内容/保真稳定性、PR8与原四格先于240未解除。
