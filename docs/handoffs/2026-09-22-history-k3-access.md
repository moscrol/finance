# 2026-09-22 #841 K3 启动阻塞封存

## 背景
用户要求继续 #841 的独立 Spec/Quality 审查，不启动金融自然探针、不切生产写手、不合并或部署。固定 `fedce252330dce1065238f58e6c914417219ec53`，业务代码仍为 f73；本轮只形成证据和交接。

## 发现顺序与决定
1. 宿主一次凭证刷新成功，证明本地 resolver 可用但未测试模型。两次 K3 审查在 controller 沙箱内调用同一 resolver，均 exit70、模型请求0、无终稿；保留原 execution、credential、stderr、空 events。
2. 用 `/usr/bin/true` 替换 python3、保留原 shell resolver，离线复现两次完全相同 stderr SHA：here-document 临时文件创建被禁止；默认和指定 TMPDIR 都失败。原先“HTTPS 被沙箱拦截”的判断撤回。
3. 直接执行相同 Python 正文的夹具测试四分支通过，但不证明真实 bootstrap 修复。外层 controller 内启动 tools sandbox 的 echo 对照 exit71，说明嵌套沙箱同样不可用。故不再盲目重跑或放宽隔离。
4. 失败后改过 Spec 启动器草稿但未执行；草稿与执行时输入分开保存，原输入按 execution 哈希重建。`launch.py` 未被原 execution 的 inputs 哈希覆盖，重建不宣称已认证。

## 方案取舍
| 方案 | 评价 | 结果 |
| --- | --- | --- |
| HTTPS白名单/仅改TMPDIR | 前者语法失败且归因错误，后者精确复现仍红 | 保留失败，不当修复 |
| Python直接执行解析器正文 | 四种离线夹具通过，但嵌套工具沙箱仍红 | 仅候选启动方式，未验真实集成 |
| 去掉外层沙箱立即续跑 | read/write与凭证边界未证明等价，且本轮尝试已结束 | 不执行，先验完整设施 |
| 将599P或凭证可用算独立通过 | 未向模型发请求，没有终稿 | 继续BLOCKED |

## 收据
- 新归档：`docs/verification/2026-09-22-history-k3-access/`，README、summary、两轴执行输入与失败原件、离线诊断、重建说明。
- 两轴：Spec 1.338s / Quality 1.466s，24请求/600s上限，实际0请求，状态 `BLOCKED_BOOTSTRAP_NO_MODEL_DISPATCH`。
- fedce 定向作者回归：599 passed、0 failed/error/skipped；收据 `20260921T180311Z-fedce252.json`，checker exit0。不能代替独立签字。
- 本轮自然金融探针0；自然仍 `not_passed`。磁盘及共享范围边界未放宽。

## 未完成 / 下一步
先把审查设施修到：凭证初始化不依赖受限 shell here-doc；工具隔离不嵌套 sandbox；真实运行有完整终稿收口、候选/作者树首尾身份与 provider 请求收据。修复必须先做无网络离线验证，再经新授权、新输出目录、准确 SHA 启动一次有界独立审查。不要将夹具绿、作者599P或旧 Codex 读取日志当终稿。

独立审查通过后，另行冻结金融题目、写手/判官模型、provider 硬上限、服务端墙钟和停止规则，才做自然验收。最后才做 main tip 组合验收；合入与部署均需用户确认。不要改生产启动器、切写手、接管 #793/#794 或 #833/#845。

## 证据边界
`access-preflight.json` 的 claims 未签名验证；hash 只证明字节，不证明上游事实。`TMPDIR` 对照、直接 Python 夹具和 nested sandbox 记录都是诊断，不是产品安全/可用性签字。旧包不改，原失败原件保留；详细背景见同目录 README。
