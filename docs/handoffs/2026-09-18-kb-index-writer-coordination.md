# KB索引写者协调：来源纠正、旧任务完成、临时文件防写生效

## 裁决（2026-09-18 22:23 UTC+8）

用户说「没有开cursor呀，你来协调一下」，授权本会话处理运维冲突。
不再要求用户关闭/寻找Cursor，不再把“待用户协调”作为本轮阻塞。
**尚未上线**：8792仍bf662e9310ff，运行链接/启动器/消费者未改，新代码未合。

## 纠正来源判断

前快照 `2026-09-18-kb-dual-index-deploy-blocked.md` 的“另一Cursor会话”归因错误；保留旧快照
作为当时判断，**本页为更正依据**。原链41455→41453→41444→22475，22475的可执行文件是
`/Applications/Grok Bot.app/Contents/MacOS/Grok Bot`，入口是local-exec-daemon/main.cjs，父30493
也是Grok Bot。旧shell的 `__CURSOR_SANDBOX_ENV_RESTORE` 是继承/模板痕迹，不足以识别应用。
本轮已通过正式 `record-correction` 落用户活台账；未打印或读取Grok Bot凭证。

查询时41444/41453/41455均已退出，日志证实两次任务均exit0：
- 普通：21:23:18–21:24:45，169635块，发布Gitea `rag-index-20260918`。
- 全文：21:24:56–22:04:53，230573块，发布Gitea `rag-index-full-latest`（prerelease）。

这些是旧共享树的产物，没有evidence_metadata_version，**不能冒充本轮隔离迁移成果**。
未删除/覆盖它们或Gitea资产。没有杀任何进程，也没关闭Grok Bot/8792。

## 已完成的本地维护保护

只靠hook暂停挡不住直接build/update。本轮不修改共享脏代码，使用macOS `UF_IMMUTABLE`
（`ls -lO`显示uchg，文件不可变标记）围住两份实际目标：
`~/knowledge-base-private/.rag_index` 与 `.rag_index_full`。

- 先在临时目录验覆盖、追加、创建、替换、删除、整个目录重命名六种操作均EPERM。
  随后恢复原flags，写入恢复；测试未碰生产字节。
- 实际生效于**两个目录+24个常规文件**（上轮18是选定指纹集合，本轮覆盖全部，含旧pickle缓存）。
- 改flags前核打开文件、持久化每项原flags/device/inode/mtime/size/SHA256；改后全量复核。
- 对生产每个文件用**不含O_TRUNC/O_CREAT**的O_WRONLY打开探测，24项均EPERM，无写入。
- 两个现有CLI各跑一次BM25关键词查询“液冷”，各3命中/fresh；仅把访问遥测重定向到现场日志。
  查询前后24文件SHA完全不变。8792健康接口正常，revision/code_matches_repo仍一致。
- 三个post-*继续维护skip，pre-commit不变。普通文档/资料入库未锁。
- 共享Git目录放 `kb-index-maintenance.json` 告知其他会话，不触发Git hook，不动跟踪代码。

### 边界与回退

这不是权限隔离的安全沙箱：同一个macOS用户可以主动清除uchg；它阻止普通写者意外改写，不对抗
主动越过维护约定。**远端Gitea Release的读包/发布不受本地flags拦截**，没有封账号或网络；
也不保护wiki/raw正文不变。未来源变化仍要做freshness/diff。

现场根 `~/.finance-runtime/kb-dual-index-20260918/`，`evidence/production-file-fence.json`
是原flags/身份/字节的唯一恢复日记。解除命令只在受控写者/切换方案就绪后执行：

```sh
PY="$HOME/finance-workspace-private/.venv-workbench/bin/python"
OP="$HOME/.finance-runtime/kb-dual-index-20260918"
"$PY" "$OP/fence_production_indexes.py" \
  --restore-original-flags "$OP/evidence/production-file-fence.json"
```

恢复器会先核目标路径、inode、内容与当前flags，不对未知替换文件清保护；恢复后三个hook仍暂停。
**本轮没执行解除**，也没安装自动解除、自动上线任务。不要用递归 `chflags nouchg` 绕日记。

## 完整门禁（固定候选d95d4921）

- 后端11486 passed / 73 skipped / 2 xfailed / 0 failed。
- Ruff、registry五项、前端lint/typecheck/build exit0；前端107通过。
- **E2E：31 passed / 3 failed / 2 skipped，all.exit=1，禁止上线。**
  - desktop：首轮“结构化对话报告”按钮缺失。
  - mobile：第二轮相同按钮缺失。
  - tablet：个股深挖追问后台已完成，但可见助手消息数仍1而非2。
- 这些不是KB索引迁移完成的证据，也没有把它们先归为偶发/机器负载；保留trace/error-context待查。
- `check_test_receipt.py <receipt> --expect-revision d95d...` 全部匹配，可采信后端收据；
  它仅签后端，不替代E2E。当前分支新文档提交也不能借用该收据伪装当前HEAD全量通过。

本轮没有为得到绿色而重复E2E、加超时或删断言。没有擅自合入新代码。

## 后台迁移与下一步

本轮全文迁移仍由40354→41233在隔离staging运行（以现场pid文件和命令核验，勿盲杀旧PID）；
22:21约58%，尚无成功回执。与对方22:04已完成的旧全文发布不是一件事。

1. 完成本轮staging全文迁移，再按冻结源/实时源分别核覆盖、字段、冲突隔离与真实BGE消费者。
2. 原 `production-index-before.json` 仍留作事故前基线，原整体验收exit1仍成立。
   新fence日记是明确的新维护窗口；不得覆盖原基线让旧断言“变绿”。
3. 解决/定位E2E三红，保留第一次失败与固定提交身份。获用户合并确认之前不合、不部署。
4. 正常双索引更新入口仍待部署；临时flags不应该变成长期生产运行方式。

## 证据与脚本

本轮小收据：`docs/verification/2026-09-18-kb-index-coordination/`。
大trace、测试用户目录仅保留现场 `gate/finance-workspace-private/intelligence/webapp/test-results/`，
不提交zip/数据库/用户数据。e2e日志及三个error-context有归档；命令退出码也入档。

现场脚本（probe/file fence/verify/read）只服务本次已授权运维窗口，精确绑定此操作目录和路径。
它们不构成新的索引构建算法，也没有改公共构建链。本次快照保留脚本以便审计/解除；
若推广为通用维护器，需要路径参数化、身份校验测试及完整恢复故障注入，不能直接复制当长期方案。
