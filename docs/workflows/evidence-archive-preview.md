# 归档预览：先验证待提交字节，再绑定正式提交

`check_evidence_archive.py` 只读 Git revision（提交版本）里的文件，不读工作区。
`preview_evidence_archive.py` 复用它，用独立临时索引（暂存区）生成无分支引用的预览提交，
避免“本地哈希正确、日志却没有进 Git”。不自动提交、推送或回退历史。

## 操作步骤

1. 确认工作树/分支归属；有他人改动优先另开 worktree。准备完整归档和清单。
2. 用 `prepare` 预览归档目录及本次明确认领的其他路径；非零退出即停。
3. 检查预览 JSON 的路径与 base，显式 pathspec 提交；提交失败立即停。
4. 对正式完整 SHA 运行 `verify`；它检查父提交、完整 tree（全仓文件快照）以及两版归档。
5. 验证通过后才另行推送并回读远端。推送和产品验收各有自己的收据。

### 可执行骨架

先把 `PYTHON` 设为主树 `.venv-workbench/bin/python` 的绝对路径，在认领的工作树内执行。
`TOOL` 指向包含新工具的 checkout；跨 worktree 使用时必须保留 `--repo "$PWD"`。
把示例归档/文件路径替换成真实且已认领的路径，**不要复制历史 #63 的固定 /tmp 路径**。

```bash
set -euo pipefail
: "${PYTHON:?先指定规定解释器}"
TOOL="$PWD/scripts/preview_evidence_archive.py"
ARCHIVE=docs/verification/example
FILES=("$ARCHIVE" docs/handoffs/example.md)
OUT=$(mktemp -d)
# 留存收据供复核；确认归档后再清理，不在这里自动删除。
printf 'receipts: %s\n' "$OUT"

"$PYTHON" "$TOOL" prepare "$ARCHIVE" --repo "$PWD" \
  --paths "${FILES[@]}" > "$OUT/preview.json"
PREVIEW=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["preview_revision"])' "$OUT/preview.json")
BASE=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["base_revision"])' "$OUT/preview.json")
test "$(git rev-parse HEAD)" = "$BASE"
git --literal-pathspecs add -- "${FILES[@]}"
if git --literal-pathspecs commit -m "docs: update evidence archive" -- "${FILES[@]}"; then
  REAL=$(git rev-parse HEAD)
else
  rc=$?
  printf 'commit failed (%s); no verify/push\n' "$rc" >&2
  exit "$rc"
fi
"$PYTHON" "$TOOL" verify "$ARCHIVE" --repo "$PWD" \
  --preview "$PREVIEW" --revision "$REAL" > "$OUT/verified.json"
```

`prepare` exit 0 只表示 **preview_only**；`verify` exit 0 只表示 **committed_bytes_only**。
检测到提交后变化时工具不自动 reset/amend；先保留失败收据并确认归属，再重新预览、前向修复。
无引用 preview 可能被 Git 垃圾回收；应在同次操作内完成复核，保存输出而非把 preview 当长期分支。

## 为什么分两阶段

- **没有选择“提交后失败再 amend”**：用户要求不改历史，且 amend 可能改到别人刚推进的提交。
- **没有选择“仅临时索引跑 checker”**：checker 读的是提交对象，索引还不是可核验的 revision。
- **没有选择“校验器自动提交/推送”**：只读校验与授权副作用分开；工具不替调用者选择提交范围。
- 环境变量必须覆盖每个预览子进程。手工移植时，在唯一临时目录下、子 shell 内先
  `export GIT_INDEX_FILE="$tmp/index"`，再执行所有 Git 命令。仅在第一条命令前赋值不会跨 `&&` 传播。

## 范围与限制

- 路径按仓根解析且作为字面量；拒绝仓外路径、`.`、`.git` 和魔法 pathspec。
- 拒绝继承 `GIT_INDEX_FILE` 等仓库重定向，避免不同 helper 操作不同仓。不是可嵌入 pre-commit 的检查器。
- 不给共享工作树加写锁。预览时 HEAD 漂移会拒绝，正式提交与预览不一致会拒绝；仍优先独占工作树。
- 读取原始 Git 对象：两层工具均使用 `--no-replace-objects`，不接受本地 replacement refs
  （对象替换映射）把同一 SHA 指成别的内容；父身份直接读 commit header，不读会被
  shallow/grafts（浅克隆边界/本地谱系改写）改变的历史展示。替换映射本身不会被删除或改动。
- 使用仓库其余正常 Git 配置；信任其 clean filters 等配置，不是运行不受信仓库的沙箱。
- 不验证远端留存、来源真实性、独立审查 verdict（正式结论）或产品质量；181/181 也可能只是完整保存了一份失败报告。

实现/回归：`scripts/preview_evidence_archive.py`、`tests/test_preview_evidence_archive.py`。
