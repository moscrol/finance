# 夜跑配置发布已完成，业务效果待验

## 这个分支做什么
#827已合并并切两个夜跑job；本枝只留收口指针，不接管#810/429等工作线。

## 决策与被否方案
- 等资源空档、成功夹具自动回收+3GiB运行底线；否删他人树或拼接诊断绿。
- main漂移后合#830得c097；否旧全量移签，最终对象重验。
- Spec@2ea6、Quality@b0cf原签名保留；8安装输入逐字一致，否冒称审过#830。
- 快进合入保持受测SHA；备份/双job先卸载/loaded核验，否跨job事务承诺。
展开：`../2026-09-21-nightly-deployment-complete.md`。

## 当前状态
#827于18:42合入，main精确c097d712f；18:43发布`CONFIG_DEPLOYED_NOT_EXECUTED`。sync/生成/L2三根adcda94b5；两个job复读idle/runs0。没有kickstart/手动采集/删旧根。六文件备份、自有锁已释放；生产库、其他四job、8792和旧根发布前后不变。证据文档另在`docs/nightly-deployment-receipt-0921`。

## 已验证
c097 Python12502P/0F/0error/85S/2X，Ruff0；前端110P/E2E34P2S；registry五项、生成7+4、hooks通过。main精确收据校验0。
Quality单次24请求PASS/两个low；53P+62断言；最终树根复跑Spec21/Quality62。封存`docs/verification/2026-09-21-nightly-deploy-resume/manifest.json`。

## 未验证 / 已知边界
旧配置18:30自然sync于18:36退出2：东财RemoteDisconnected、当日个股0行；staging拒换库，主库stat未变。不是新装根效果。今日真实采集/关键值/日报/L2/生成未通过。
8792由他会话18:13切f2c3e9e1a；本轮未动，readiness仍503（快照9/21、库9/18）。独立签名非整个c097审查。安装器不验根语义、无跨job事务；实际loaded核验不可省。

## 下一步
配置部署完成；按授权范围观察20:40及下次18:30真实收据。若要今日补采另确认，走canonical daily-full，不强制换失败staging。旧根/失败库/审查原件保留。收尾文档尖不继承c097全量。

## 踩过的坑
资源入场检查不是全机资源锁，后续会话仍可开测试；运行期采样不可省。部署等待期间主干、8792、定时job都会变化，发布前重采。安装后runs重置0不是业务成功。
