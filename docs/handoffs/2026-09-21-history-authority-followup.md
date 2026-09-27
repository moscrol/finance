# 历史缓存当前授权与单次受锁读取续修

## 背景与发现顺序

#841在#832/a140上接替#829的历史来源绑定返修。前次代码f90、文档bbd的完整证据仍保留。续查发现HistorySession缓存命中引用时绕过当前会话检查；在临时store用私有`_write_run`改变run.session_id后仍可读。没有找到普通用户经公开入口修改既有归属的证据，因此结论限定为陈旧缓存授权风险，不称已证公开可利用线上越权。

最初用双读检查授权，随后否决：先检查后读取会留下TOCTOU（检查与使用之间的时间窗口），且合法请求重复校验内容。最终授权下沉RunStore，复用现有每run文件锁，锁前核路径、锁内重载元数据和重验授权，校验并仅读一次字节；成功之后才写缓存。refresh替换有效引用集合，不再只增不减。

错误合同的两次反例保留：dirty-scope-v2的1F/98P来自测试误要求visibility撤销抛ValueError，修测试以保原FileNotFoundError；dirty-consumers的1F/144P则是真退化，未知run不再抛原ValueError，修实现而非放宽消费者。dirty-combined及precommit-targeted最终315P是bbd上的诊断，不是724收据。

## 决策与被否方案

| 方案 | 评价与结果 |
|---|---|
| 缓存命中直接读；只在refresh或未命中检查授权 | 否决。元数据/归属可能变，旧缓存不是当前授权。 |
| 先读一次验归属，再读一次取内容 | 否决。重复读取且留检查/使用窗口。 |
| 在HistorySession增加另一套锁或授权实现 | 否决。存储消费者会分叉，writer也未必遵守新锁。 |
| RunStore复用每run写锁，锁内重载并单次验证读取 | 采用。共同存储边界承担授权；可选conversation_id保持旧调用方兼容。 |
| 把工件缺失统一改成会话错误 | 否决。消费者依赖既有错误合同；会话范围未知run/归属不匹配用ValueError，登记工件不可用保留FileNotFoundError。 |
| refresh只追加 | 否决。过期登记/可下载状态仍出现在展示索引；改为重建替换，不改别名和定义。 |
| 全量绿后放宽main漂移阈值 | 否决。固定版本测试和当前合流门是不同问题；漂移exit1原件保留。 |
| 为归档新增通用运行平台 | 否决。正式行为保护已进测试，现有前端/收据/Git归档工具可复用；本轮硬绑定工装只作源码快照保存。 |

锁只协调遵守同一`_run_state_lock`的writer，不防任意直接改盘。哈希与provenance只证明内部一致，不能认证原始用户和原件真实性。此边界已同步产品门页和能力图谱。

## 已完成与精确版本

- 代码`7249378a5bdb9b01cc62ec3bca13af3149bd48df`已提交推送：5文件，244增/34删，包含runtime、产品门页及24项新测试。
- 证据`50c9bfcf243b47b985469f21b3883a91792f3000`已推送，80文件/326556字节，仅docs。提交后`check_evidence_archive.py`核Git文件集合及blob：79/79非manifest文件，ok=true/errors=[]；旧f90包73/73且与前版无差异。两版外部完整JUnit及真实原件哈希均通过。
- #841正文已补当前724/50c9结论，旧f90正文留作历史；评论5461。仍open/WIP、未merged、mergeable=false，base仍#832分支。#809/#829原头、#832与#833源码未改。
- 记忆在隔离detached树回写项目索引、原有方法笔记和能力图谱；并存其他人的#844/日期策略/#845记录，未动共享脏树。文档提交`134bc4cf00ead405fa2a882afc2986175598f40a`已正常快进推至agent-memory。rebase只作用于这份记忆文档，不是金融候选代码；原b33/141为途中未发布身份。

## 已验证

全量使用主树`.venv-workbench/bin/python`，`umask 022`、净环境、独占basetemp、1800秒上限、失败夹具保留策略。执行13:37:08.168418Z至13:50:48.940014Z，首尾724/clean/identity_stable。12659P/87S/2X/17warnings，0F/0error，809.93秒。收据`20260921T135039Z-7249378a.json`精确checker0；JUnit12748项，相对f90新增24项无删除，89项skip/xfail名称、类型和理由一致。定向315P，收据`20260921T133438Z-7249378a.json`。

同SHA前端六步全部exit0，110项单测与E2E34P/2S；六条Ruff/registry/crosswalk均0，crosswalk保留98条反向链接warning。前端每份日志大小/hash已独立核对。七项内存撤保护对应2/1/3/1/4/1/2个行为失败，无收集/导入错误；磁盘源码首尾不变。

真实JSON复制进临时RunStore离线回放225行/9页，每页25，累计905次卡恢复含重复元数据。初查/授权reader同源卡、重叠页hash、源特征一致，原件不变，模型调用0。不认证原始用户归属，不签自然引用或金融质量。

`receipt-drift`明确exit1：相对`gitea/main@028a251a1b2ca98245326a6b59376f4f7f8e5e81`共同祖先f2c3，13个提交中6个merge，超过5个merge上限。精确SHA通过不能抹掉当前main批次门阻断。后续文档tip不移签724，更不签后来main。

记忆图谱原审计92行257→258断言、206→207项在途/未校验；接到同时更新的远端后最终93行265断言、214项在途/未校验，均exit0。分母变化包含他人更新，不全算本轮能力增长；新增存储符号仍按分支标PENDING。

## 证据与工具沉淀

主包`docs/verification/2026-09-21-history-authority-followup/`；提交后回执包`docs/verification/2026-09-21-history-authority-closeout/`。完整运行根`~/.finance-runtime/reviews/react-trace-integration-20260921/history-authority/`。正式保护在`tests/test_history_artifact_scope.py`和`tests/test_run_store_history_artifacts.py`；重复执行与变异工装的原源码已进主包`scripts/*.py.txt`，硬绑定版本/路径/原件，不假装支持任意项目。复用现有`run_frontend_gate.py`、`check_test_receipt.py`、`check_evidence_archive.py`，不另造门禁。可迁移方法写回既有`gate-covers-only-its-return-value.md`。

封存工具曾因遗漏`AssertionError: assert`前缀中断；查原XML后补实际前缀，仍要求行为失败、exit1且无error，不改失败原件。仅执行转录和主包README记载这一工具错误，没有独立原始日志，不冒称已保存。`find -printf`在macOS失败、直接rg单行XML输出溢出均未用于结论，最终用标准XML解析器比较。

## 后续与禁止事项

1. 保持WIP。最终合流必须冻结届时base/head重新运行全部工程叶；不降漂移阈值、不把无冲突当组合通过，不接管他人的#833/#845或#814验证线。
2. 独立Spec/Quality尚无724结论；旧K3超时不代签，新增预算需明确确认。自然金融仍not_passed：225/25和候选12.6/16.5引用、判官消费、#793板块排序/同窗/候选范围/改判条件、#794展开/版本/预算/取消/可发现性仍未完成。
3. 未授权合main、部署8792、写生产、关闭#793/#794或新增自然模型请求；本轮均未执行。不得自动补绑漏引数字或复开K3求绿。
4. 磁盘余量约8.9Gi，未来全量继续用owned临时目录和采样，勿删失败原件、他人工作树或真实运行目录。此前并行pytest收据撞名，两组合计不能当正式收据；本轮Python串行。
