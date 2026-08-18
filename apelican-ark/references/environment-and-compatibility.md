# 环境与兼容性

## 前置条件

- Python 3.10 或更高版本。
- 基础、中等、全量（不含敏感配置）只使用 Python 标准库。
- AES 加密的敏感配置包额外需要 `pyzipper>=0.3.6`。
- Codex 与 WorkBuddy 的目录结构可能随版本变化；始终以预览清单与恢复后健康检查为准。

## 环境变量

| 变量 | 是否必需 | 用途 | 获取方式 |
| --- | --- | --- | --- |
| `CODEX_HOME` | 否 | 覆盖 Codex 默认目录 `~/.codex` | 只有自定义过 Codex 数据目录时，填写该目录 |
| `WORKBUDDY_HOME` | 否 | 覆盖 WorkBuddy 默认目录 `~/.workbuddy` | 只有自定义过 WorkBuddy 数据目录时，填写该目录 |
| `ARK_BACKUP_PASSWORD` | 否 | 通过 `--password-env ARK_BACKUP_PASSWORD` 临时提供 AES 口令 | 用户自行创建；默认更推荐 `--prompt-password` |

方舟不需要 API Key。连接器自己的授权不会被当成方舟运行依赖。

## 安装可选依赖

macOS / Linux：

```bash
python3 -m pip install "pyzipper>=0.3.6"
```

Windows PowerShell：

```powershell
python -m pip install "pyzipper>=0.3.6"
```

## 只读自检

macOS / Linux：

```bash
python3 ./scripts/ark_selfcheck.py
```

Windows PowerShell：

```powershell
python .\scripts\ark_selfcheck.py
```

自检不会创建备份、恢复文件或修改 Codex/WorkBuddy 目录。`pyzipper` 缺失只会关闭 AES 敏感配置包能力，不影响普通快照。

## 临时使用口令环境变量

默认使用 `--prompt-password`。只有自动化环境确实需要变量时，才在当前终端临时设置并在命令结束后清除。

macOS / Linux：

```bash
read -r -s -p "方舟口令: " ARK_BACKUP_PASSWORD; echo
export ARK_BACKUP_PASSWORD
python3 ./scripts/ark_backup.py --profile advanced --include-sensitive-config --password-env ARK_BACKUP_PASSWORD --apply
unset ARK_BACKUP_PASSWORD
```

Windows PowerShell：

```powershell
$secure = Read-Host "方舟口令" -AsSecureString
$env:ARK_BACKUP_PASSWORD = [System.Net.NetworkCredential]::new("", $secure).Password
python .\scripts\ark_backup.py --profile advanced --include-sensitive-config --password-env ARK_BACKUP_PASSWORD --apply
Remove-Item Env:ARK_BACKUP_PASSWORD
```

不要把真实口令写进脚本、命令历史、文档、聊天或 manifest。
