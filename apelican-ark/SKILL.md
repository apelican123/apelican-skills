---
name: apelican-ark
description: 为 Codex 和 WorkBuddy 创建可预览、可校验的本地备份，覆盖技能、设置、记忆和自动化；可按需增加连接器、项目索引、会话文件和本地加密的敏感配置。用于换电脑、重装前存档、恢复 AI 工作环境或检查方舟备份。默认只读预览，明确确认后才写入；不备份账号登录或 Cookie，不承诺会话能在客户端完整显示。
---

# 方舟

把方舟当成 Codex 和 WorkBuddy 的搬家工具：先把用户想带走的内容列清楚，确认后再打包；到了新设备，仍然先预览，确认后再恢复。始终守住四件事：预览不能偷写文件，新设备的原文件要能找回，账号登录状态始终排除，会话文件恢复不等于客户端能完整显示。

## 开始前先做这几件事

1. 读取 [references/quick-start.md](references/quick-start.md)。
2. 先运行 `scripts/ark_selfcheck.py`；核心检查失败时停止。
3. 基础备份只需 Python 3.10+ 标准库。只有 AES 加密敏感配置包需要 `pyzipper`。
4. 所有脚本已直接随技能包提供，不要从 Markdown 重新抄写或重建。

## 先问用户想搬多少

向用户展示中文选项，不直接显示内部英文值：

- 基础备份（身份、技能、配置、记忆、自动化；不含会话与敏感配置）→ `basic`
- 中等备份（再含连接器与项目索引；不含会话与敏感配置）→ `advanced`
- 全量备份（再含能找到的会话文件与索引；敏感配置仍需单独确认）→ `full`

全量备份中的“会话”只是尽力保存本地可见文件。受客户端索引、版本和服务端数据限制，恢复后可能只能继续使用记忆，旧聊天无法在客户端完整显示或继续打开。公开描述只写已经验证的具体结果和限制。

## 先预览，再动文件

1. 先运行只读预览。未指定 `--apply` 时，备份脚本默认只扫描，不得创建目录、ZIP、报告或清单。
2. 展示文件数、体积、技能、自动化、排除项、脱敏项与重复技能，再让用户确认范围。
3. 如需项目数据，先运行 `--list-projects`，只列出真实存在的项目；确认后再加 `--projects`。
4. 单独询问是否包含用户自管的敏感配置，默认不包含；账号登录、Cookie 和设备绑定授权不在选项内。
5. 显式确认后，另起命令用 `--apply` 创建备份，再运行验证工具。
6. 恢复时先 `--dry-run`；用户确认后另起命令使用 `--apply`。
7. 恢复后检查技能、身份、配置、路径、自动化和连接器登录状态，不以“文件存在”代替可用性检查。

## 常用命令

以下示例使用 Windows 的 `python`。macOS/Linux 将其替换为 `python3`，路径分隔符改为 `/`。

```powershell
$ark = "<技能目录>"

# 只读环境自检
python "$ark/scripts/ark_selfcheck.py"

# 默认只读预览
python "$ark/scripts/ark_backup.py" --profile basic

# 用户确认后创建备份
python "$ark/scripts/ark_backup.py" --profile basic --apply

# 完整性检查与只读恢复预演
python "$ark/scripts/ark_verify.py" "<备份目录或zip>"

# 恢复预览；与 --apply 互斥
python "$ark/scripts/ark_restore.py" "<备份目录或zip>" --dry-run

# 用户再次确认后执行恢复
python "$ark/scripts/ark_restore.py" "<备份目录或zip>" --apply
```

## 可选：本地加密敏感配置

先用普通话说明：只有所选范围内、由用户自己管理的敏感配置值才会进入单独的本地加密包；账号登录文件、Cookie 和设备绑定授权始终不备份，换机后需要重新登录。

- `--include-sensitive-config` 只处理所选范围内的用户自管配置值；账号登录文件、Cookie、系统钥匙串、DPAPI/设备绑定数据和云端 OAuth 授权始终排除。
- 含敏感配置时必须直接写 AES 加密 ZIP，不建立明文暂存目录；缺口令或缺 `pyzipper` 必须停止，绝不降级成普通 ZIP。
- 优先使用 `--prompt-password`；不要把口令直接写进命令、聊天、文档或 manifest。
- 使用同一口令时，加密包可由恢复脚本还原；本版已完成“生成 → 只读预览 → 正式恢复 → 逐文件 hash 一致”的隔离测试。
- 恢复配置文件不代表账号登录有效。换机后按新设备流程重新登录，不尝试恢复或验证 Cookie、OAuth 会话和设备绑定登录态。
- ZIP 成员路径可能可见；含敏感配置的备份不得公开分享或上传公共仓库。
- 所有处理都在本机完成；脚本不联网、不上传备份内容。

```powershell
python "$ark/scripts/ark_backup.py" --profile advanced --include-sensitive-config --prompt-password --apply
```

加密包也要先预览、再恢复：

```powershell
python "$ark/scripts/ark_restore.py" "<备份zip>" --dry-run --prompt-password
python "$ark/scripts/ark_restore.py" "<备份zip>" --apply --prompt-password
```

## 恢复时守住这些规则

- 覆盖前把旧文件移到目标用户目录的 `~/.ark/restore-conflicts/<时间戳>/`；不删除本地多出的文件。
- 报告写到 `~/.ark/restore-reports/<时间戳>/`，不修改备份包。
- `--fresh` 只是一项空环境断言；检测到已有环境就停止，不删除目标。
- 自动适配已知配置中的旧用户主目录，并在报告中列出；外置盘和自定义程序路径仍需检查。
- WorkBuddy 自动化只生成恢复计划，由 AI 使用官方自动化接口逐项创建并回读；禁止直接写产品数据库。
- 项目数据默认只列出，不自动写回未知项目路径。
- 会话文件只报告是否就位。受客户端索引、版本和服务端数据限制，恢复后可能只剩记忆可用，旧聊天不一定能完整显示。

## 需要时读取

- [references/format.md](references/format.md)：备份结构、schema 与恢复安全契约。
- [references/environment-and-compatibility.md](references/environment-and-compatibility.md)：环境变量、跨平台命令与依赖。
- [references/troubleshooting.md](references/troubleshooting.md)：出错时读取。
- [references/pitfall-log.md](references/pitfall-log.md)：安全事故与最低回归门禁。
- [references/permissions-and-behavior.md](references/permissions-and-behavior.md)：读取、写入、依赖、联网和明确排除项。
- [references/provenance.md](references/provenance.md)：设计来源与非隶属声明。
