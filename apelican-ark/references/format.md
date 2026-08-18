# 方舟备份格式 2.0

## 包结构

```text
manifest.json
RESTORE.md
secrets-notice.md
RECOMMEND.md
backup-summary.txt
codex/...
workbuddy/...
workbuddy/automations.json   # 可选，只读导出的定义
projects/...                 # 可选，只列出并等待人工映射
```

普通备份可为目录或 ZIP。含用户确认的敏感配置时只能是 AES 加密 ZIP，脚本直接从源文件写入压缩包，不创建明文暂存目录。使用同一口令可通过恢复脚本还原这些配置。ZIP 文件名和成员路径不一定加密，因此不得公开分享。

恢复报告和旧文件归档不属于备份包，位置固定在目标用户目录：

```text
~/.ark/restore-reports/<timestamp>/restore-report.md
~/.ark/restore-reports/<timestamp>/workbuddy-automations-restore-plan.json
~/.ark/restore-conflicts/<timestamp>/...
~/.ark/verify-reports/verify-<timestamp>.md
```

## manifest 关键字段

```json
{
  "schemaVersion": "2.0",
  "tool": {"name": "ark", "version": "3.0.0"},
  "createdAt": "ISO-8601 UTC",
  "sources": {
    "codex": {"home": "原设备路径", "found": true},
    "workbuddy": {"home": "原设备路径", "found": true}
  },
  "options": {
    "profile": "basic|advanced|full",
    "profileLabel": "中文说明",
    "includeSecrets": false,
    "zipEncrypted": false,
    "dedupe": "none|keep-newest|skip|merge"
  },
  "entries": [
    {
      "relPath": "codex/config.toml",
      "originPath": "原始绝对路径",
      "source": "codex|workbuddy|workbuddy-connector|project",
      "size": 123,
      "sha256": "64位十六进制",
      "type": "config",
      "linkTarget": null,
      "sanitized": true
    }
  ]
}
```

`originPath` 只用于说明快照来源；恢复目标只能由 `relPath` 与目标 home 映射得到，不能把 `originPath` 当写入路径。

## 级别

| 中文选项 | 内部值 | 主要内容 | 默认不含 |
| --- | --- | --- | --- |
| 基础备份（身份、技能、配置、记忆、自动化） | `basic` | 精确白名单 | 会话、敏感配置、缓存 |
| 中等备份（再含连接器与项目索引） | `advanced` | 根级扩展内容 | 会话、敏感配置、缓存 |
| 全量备份（再含能找到的会话文件与索引） | `full` | 会话正文与实际存在的索引文件 | 敏感配置、缓存 |

全量级的会话只代表归档其可见文件。客户端列表、索引格式、版本和服务端数据都可能影响显示；恢复后可能只能使用记忆，旧聊天无法完整显示或继续打开。不得把 hash 通过解释成“所有会话都能续聊”。

## 账号与敏感配置

- 账号登录文件、Cookie、系统钥匙串、DPAPI/设备绑定数据和云端 OAuth 授权始终排除，任何备份级别或加密选项都不能放行。
- `--include-sensitive-config` 只保留所选范围内的用户自管配置值，并强制写入 AES ZIP。
- “文件恢复成功”只证明加密包可读取且内容一致，不证明第三方账号、连接器授权或登录状态仍有效。

## 类型

`entries[].type` 可为：`identity`、`skill-file`、`config`、`memory`、`automation`、`project`、`conversation`、`secret`、`other`。

- `sanitized: true`：包中是替换敏感值后的内容，`sha256` 对应脱敏版。
- `secret: true`：用户自管的敏感配置文件，仅允许在单独确认后进入 AES 加密包。
- `linkTarget`：源项为符号链接；恢复时只允许相对目标且不得逃出对应根目录。
- `suspicious[].matches`：只记录高置信规则标签，不保存命中的疑似敏感值原文。

## 恢复安全契约

- `--dry-run` 与 `--apply` 互斥；默认行为等同 `--dry-run`。
- dry-run 不写目标目录、不写备份包、不生成报告、不归档冲突。
- apply 覆盖前始终归档旧文件；不删除目标中多出的文件。
- `--fresh` 检测到现有环境时停止，不做清空。
- ZIP 读取拒绝绝对路径、`..`、重复 manifest 与符号链接成员。
- WorkBuddy 自动化禁止 SQL 写库，只生成待官方接口执行的计划。
- 已知配置中的旧用户主目录自动适配；报告列出变化。

## 完整性与真实性

manifest hash 用于发现包内损坏和恢复差异，不是数字签名。能同时修改文件与 manifest 的人仍可伪造一致性；备份必须放在可信介质中。
