# #84 前向与去重决策快照

## 背景与发现顺序

主检出有他人改动，未在其中施工。从 gitea/main@626d8a508 建 `fwp-wt-board-hardening-0923`，没有把旧 #812/#813/#814 三单组合当成当前验收对象。本次依据脚本、测试、工单和提交差异判断。

先前向失效路径、父仓误识别、查询失败、固定基准和任意脏文件保护；再核 #876 发现只把看板改成“不是删除许可”仍不满足去重和具体进程/plist输出。提取 `worktree_safety.py`，两个入口真正调用同一采样。随后测试发现真实宿主有损坏XML plist，补异常转未知及密封夹具；NUL状态记录保留空格/重命名，plist用标准库同时支持XML/二进制。

整仓串行扫描在120s/900s预算内未完成；改最多4路只读并发，保持注册顺序/冻结基准。低预算实机重试在清单查询即失败，JSON返回trees=null，未冒充完整清单。最终成功JSON契约在隔离仓CLI测试验证。没有以该冒烟宣称真实整仓成功。

归属实测推翻工单预期：6 baseline、1 ops、5 detached，不是7 baseline；dirty是两项tracked删除，不是未跟踪。12/12不是采样main祖先，全部保留。Arena证据经完整SHA找到对应目录；v3/v4旧K3结论不升级。表与原始读数在 verification 同名目录，并抄入#64。

## 方案对比

| 问题 | 采用 | 被否及原因 |
|---|---|---|
| 去重 | 两入口共用状态、引用、祖先查询 | 只改文案仍有两套判断；整枝搬入会带其他工单 |
| dirty保护 | 任意未提交文件阻塞；ignored另列 | #876整目录豁免会吞真实修改；不能只过滤代码 |
| 失败语义 | -1/unknown_reason，具体blockers | 查失败按0/干净会制造删除依据 |
| 只读Git | GIT_OPTIONAL_LOCKS=0 | status默认会刷新索引；本树发现一把空残锁，无持有者后仅移除这一把 |
| 资源 | 定向和registry先验，四叶BLOCKED | 剩9.4GiB且多轮他人全量并发，不启动新一轮重负载 |
| 交付 | WIP #895 + #812接替评论 | 不关闭旧PR、不把旧K3或本轮48P说成四叶通过 |

## 验证与发布

源码 `18bfc3af96731d2df1d172c3047c189f5a6303a0`：干净树48P；registry五项0，首尾同SHA/dirty=false；ruff与提交钩子通过；merge-tree对626d8a508无冲突。旧main九反例9F；内存撤文档dirty保护1F，未改源文件。四叶缺全量Python/frontend/E2E。

证据根 `~/.finance-runtime/reviews/worktree-board-hardening-20260923/`：`focused-clean.log`、`focused-receipts/20260923T140129Z-18bfc3af-fee7bf2202e4.json`、`registry.json`、`legacy-red.log`、`mutation.log`。收据不签后续文档提交。

#812评论6514、#895评论6522，已回读确认；#812仍open。首次评论POST超时但后来回读发现已写入，故只PATCH补#895指针，不重复发帖。显式NO_PROXY绕过本机请求代理后API正常；没有改全局配置或重启Gitea。

## 后续与禁止

先协调资源窗口，再在届时最新集成基线上补四叶、完整看板JSON。合入须用户确认；真实拆树由#64重新验所有条件并确认名单。本轮未删除真实worktree、未清理生产数据、未重跑K3。清理脚本的年龄/detached/删除动作保留#876策略，不能以看板/本PR代替#64授权。

工具沉淀：复用已存在两入口，把重复的只读判据收为仓内共享模块；不是新增通用门禁或harness能力，因此未改harness-reference/KIT。反例运行及一次性盘点保留在verification可复算，不留仅在聊天中的脚本。项目记忆只加一行指针。
