# 方舟新手最短流程

## 先自检

在技能目录执行：

```powershell
python .\scripts\ark_selfcheck.py
```

macOS / Linux 使用：

```bash
python3 ./scripts/ark_selfcheck.py
```

“基础备份：可用”后再继续。只有需要 AES 敏感配置包时，才要求 `pyzipper`。

## 先选备份范围

- **基础备份**：身份、技能、设置、记忆和自动化；不含会话和敏感配置。
- **中等备份**：在基础备份上，再加入连接器与项目索引；仍不含会话和敏感配置。
- **全量备份**：在中等备份上，再加入本地能找到的会话文件与索引；敏感配置仍要单独确认。

账号登录文件、Cookie 和设备绑定授权不属于任何一档，换机后按新设备流程重新登录。

## 旧设备备份

1. 先选基础备份：身份、技能、设置、记忆、自动化；不含会话与敏感配置。
2. 只读预览：

```powershell
python .\scripts\ark_backup.py --profile basic
```

```bash
python3 ./scripts/ark_backup.py --profile basic
```

3. 看清文件数、体积、排除项和脱敏项。
4. 用户确认后另起命令执行：

```powershell
python .\scripts\ark_backup.py --profile basic --apply
```

```bash
python3 ./scripts/ark_backup.py --profile basic --apply
```

5. 验证：

```powershell
python .\scripts\ark_verify.py "<备份目录或zip>"
```

```bash
python3 ./scripts/ark_verify.py "<备份目录或zip>"
```

6. 把备份复制到可信介质；不要公开分享。

## 新设备恢复

1. 先安装并启动一次 Codex 与 WorkBuddy。
2. 只读预览：

```powershell
python .\scripts\ark_restore.py "<备份目录或zip>" --dry-run
```

```bash
python3 ./scripts/ark_restore.py "<备份目录或zip>" --dry-run
```

3. 检查覆盖、新增、路径适配和本地多出项。
4. 用户确认后另起命令执行：

```powershell
python .\scripts\ark_restore.py "<备份目录或zip>" --apply
```

```bash
python3 ./scripts/ark_restore.py "<备份目录或zip>" --apply
```

5. 查看 `~/.ark/restore-reports/`。
6. 打开实际技能和连接器做健康检查；按报告处理需重新授权的项目。

## 需要本地加密敏感配置时

先确认设备和介质可信，再使用隐藏输入；不要把口令写进命令：

```powershell
python .\scripts\ark_backup.py --profile advanced --include-sensitive-config --prompt-password --apply
```

```bash
python3 ./scripts/ark_backup.py --profile advanced --include-sensitive-config --prompt-password --apply
```

缺少 `pyzipper` 时必须停止，不得生成未加密替代包。

用同一个口令恢复：

```powershell
python .\scripts\ark_restore.py "<备份zip>" --dry-run --prompt-password
python .\scripts\ark_restore.py "<备份zip>" --apply --prompt-password
```

```bash
python3 ./scripts/ark_restore.py "<备份zip>" --dry-run --prompt-password
python3 ./scripts/ark_restore.py "<备份zip>" --apply --prompt-password
```

加密包能恢复配置文件，不代表账号登录仍有效。方舟始终排除账号登录文件、Cookie、系统钥匙串、设备绑定数据和云端 OAuth 会话。
