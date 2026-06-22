#!/usr/bin/env python3
"""在 Mac 上由模板生成 checkpoint-recheck 的 launchd plist（codepoint 安全）。

为什么不用 README 里的 `sed`：当路径含多字节（如 `金`）或空格时，`sed` 模板替换
不可靠；而且我们要做两件 `sed` 不好做的事——按需删掉留空的 env key、并在 `--apply`
之后注入 `--db-path`。所以用 Python 在 Mac 本地生成，生成后必过 `plutil -lint`。

运行位置：**Mac 本地**（读 ~/.evolve_root、读 clone 内模板、写 ~/Library/LaunchAgents）。
经隧道下发示例：`cat build_plist.py | python3 skills/.../scripts/mac.py -`（脚本走
stdin，避免把脚本正文里的多字节当参数传）。

配置（全部经环境变量，缺省值对应当前这台 Mac）：
    PYTHON              python3 解释器；默认 /usr/bin/python3
    FORESIGHT_USER      foresight 用户 id；默认 linxiaoqi5111
    RECHECK_CLONE       main 独立 clone 路径；默认 ~/finance-workspace-recheck
    EVOLVE_ROOT         含 db/market_feature_store.duckdb 的工作区；缺省读 ~/.evolve_root
    FORESIGHT_USERS_DIR 共享大脑台账根（如 <vault>/.foresight）；留空=不跨机，删该 key
    SUBCONSCIOUS_VAULT  Obsidian vault 根（人类可读回检日志落这里）；留空=删该 key
    KNOWLEDGE_WIKI      知识库 wiki 根（kb_evidence 回检用）；留空=删该 key
"""
from __future__ import annotations

import os
import re

HOME = os.path.expanduser("~")
PY = os.environ.get("PYTHON", "/usr/bin/python3")
USER = os.environ.get("FORESIGHT_USER", "linxiaoqi5111")
CLONE = os.environ.get("RECHECK_CLONE", os.path.join(HOME, "finance-workspace-recheck"))

evolve = os.environ.get("EVOLVE_ROOT", "").strip()
if not evolve:
    with open(os.path.join(HOME, ".evolve_root"), encoding="utf-8") as f:
        evolve = f.read().strip()
DUCKDB = os.path.join(evolve, "db", "market_feature_store.duckdb")

TEMPLATE = os.path.join(CLONE, "intelligence", "dream",
                        "com.financeworkspace.checkpoint-recheck.plist")
DEST = os.path.join(HOME, "Library", "LaunchAgents",
                    "com.financeworkspace.checkpoint-recheck.plist")

ENV = {
    "KNOWLEDGE_WIKI": os.environ.get("KNOWLEDGE_WIKI", ""),
    "FORESIGHT_USERS_DIR": os.environ.get("FORESIGHT_USERS_DIR", ""),
    "SUBCONSCIOUS_VAULT": os.environ.get("SUBCONSCIOUS_VAULT", ""),
}

assert os.path.exists(DUCKDB), f"duckdb not found: {DUCKDB}"
assert os.path.exists(TEMPLATE), f"template not found: {TEMPLATE}"

text = open(TEMPLATE, encoding="utf-8").read()
text = text.replace("__PYTHON__", PY).replace("__WORKSPACE__", CLONE).replace("__USER__", USER)

# 只保留非空 env；全空则整段 EnvironmentVariables 删掉（cron 退回仓库内默认台账）。
env_items = {k: v for k, v in ENV.items() if v.strip()}
if env_items:
    rows = "".join(
        f"        <key>{k}</key>\n        <string>{v}</string>\n"
        for k, v in env_items.items()
    )
    new_block = "    <key>EnvironmentVariables</key>\n    <dict>\n" + rows + "    </dict>\n"
else:
    new_block = ""
text = re.sub(
    r"[ \t]*<key>EnvironmentVariables</key>\s*<dict>.*?</dict>\s*\n",
    lambda _: new_block, text, count=1, flags=re.DOTALL,
)

# clone 里没有 duckdb（被 gitignore），在 --apply 之后注入 --db-path 指向 evolve 的库。
needle = "        <string>--apply</string>\n"
assert needle in text, "could not find --apply argument line"
inject = needle + "        <string>--db-path</string>\n" + f"        <string>{DUCKDB}</string>\n"
text = text.replace(needle, inject, 1)

os.makedirs(os.path.dirname(DEST), exist_ok=True)
os.makedirs(os.path.join(CLONE, "logs"), exist_ok=True)
with open(DEST, "w", encoding="utf-8") as f:
    f.write(text)
print("WROTE:", DEST)
