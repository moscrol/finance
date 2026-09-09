#!/bin/zsh
# 05 验收服务器启动器：复刻生产启动器的环境（只 source 其 `^export ` 行，密钥仍从 Keychain 取、
# 不落盘不打印），再覆盖四项：代码根（被测工作树）、用户目录（仓库外临时目录）、验收用户、端口。
#
# 用法：start_05_server.sh <code_root> <port> <users_dir> [log_file]
#   code_root : 被测代码树（PYTHONPATH + WORKBENCH_REPO_ROOT）
#   port      : 8791/8795/8797/8798 之一（docs/workbench/local-site.md 只允许这些做短期验收）
#   users_dir : FORESIGHT_USERS_DIR，必须在仓库外；不存在则以 0700 创建
# 数据根 FINANCE_WS 沿生产（主树 /Users/a77/finance-workspace-private），不复制数据。
set -euo pipefail
code_root="${1:?code_root}"
port="${2:?port}"
users_dir="${3:?users_dir}"
log_file="${4:-/tmp/cap05-server-${port}.log}"
prod_launcher="/Users/a77/.local/bin/start-finance-workbench"

case "$port" in 8791|8795|8797|8798) ;; *) print -u2 -- "✗ 端口 $port 不在验收白名单 8791/8795/8797/8798"; exit 1;; esac
test -d "$code_root/intelligence" || { print -u2 -- "✗ $code_root 不是代码树"; exit 1; }
test -f "$prod_launcher" || { print -u2 -- "✗ 生产启动器不存在：$prod_launcher"; exit 1; }
if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
  print -u2 -- "✗ 端口 $port 已被占用"; exit 1
fi

# 只导入生产启动器的 export 行：拿到与 8792 相同的 provider 链、档位、判官、L3、RAG 配置。
env_lines="$(mktemp)"
grep '^export ' "$prod_launcher" > "$env_lines"
# shellcheck disable=SC1090
source "$env_lines"
rm -f "$env_lines"
[[ -n "${FORESIGHT_BUILTIN_LLM_API_KEY:-}" && -n "${OPENAI_API_KEY:-}" ]] || {
  print -u2 -- "✗ Keychain 取不到网关 key，拒绝以空 key 起服务（会静默降级成模板答案）"; exit 1
}
curl -s -m 3 -o /dev/null "${LLM_BASE_URL%/v1}/v1/models" || { print -u2 -- "✗ 网关 ${LLM_BASE_URL} 不可达"; exit 1; }

mkdir -p "$users_dir" && chmod 700 "$users_dir"
# 判官二进制若被自动更新清掉（生产启动器钉的是带版本号的下载件），允许显式指到现存文件；
# 不设则完全沿生产（可能是 unavailable，那是 01 的接缝，验收记录里如实写）。
if [[ -n "${CAP05_JUDGE_BIN:-}" ]]; then
  export LLM_JUDGE_GROK_BIN="$CAP05_JUDGE_BIN"
fi
if [[ -n "${CAP05_JUDGE_SANDBOX:-}" ]]; then
  export LLM_JUDGE_GROK_SANDBOX="$CAP05_JUDGE_SANDBOX"
fi
export PYTHONPATH="$code_root"
export WORKBENCH_REPO_ROOT="$code_root"
export FORESIGHT_USERS_DIR="$users_dir"
export FORESIGHT_USER="cap05"
# 验收用户不豁免配额；单活跃 run 由客户端串行保证。
export WORKBENCH_QUOTA_EXEMPT_USERS="cap05"

cd "$code_root"
print -- "code_root=$code_root port=$port users_dir=$users_dir log=$log_file revision=$(git -C "$code_root" rev-parse --short HEAD)"
exec /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m uvicorn \
  intelligence.api.app:app --host 127.0.0.1 --port "$port" >> "$log_file" 2>&1
