# 方舟备份格式 2.2

## 包结构

```text
manifest.json
ARK-START-HERE.txt             # AES 包中公开的启动说明
AI-RESTORE.md                  # 给任意 AI 的一句话恢复契约
ARK-BOOTSTRAP.py               # 公开、无凭据；解出 ark-tools 后调用恢复器
ark-tools/...                  # 公开的静态 restore/verify/common 代码
RESTORE.md
secrets-notice.md
RECOMMEND.md
backup-summary.txt
codex/...
workbuddy/...
workbuddy/automations.json   # 可选，只读导出的定义
hermes/...                   # Hermes 可迁移用户态，不含可重装运行时
hermes-memory/.memory-tencentdb/memory-tdai/...
hermes-memory/.memory-tencentdb/tdai-gateway.standalone.yaml
hermes-desktop/...           # Desktop Local Storage/LevelDB + 明确布局/主题
hermes-provider/...          # 自定义且不能核验为上游内置的 Provider 源码
external-roots/...           # 外部真实源；link 本身只记录拓扑
projects/<id>/content/...    # complete 才收，恢复必须显式映射
local-mcp-projects/<id>/content/... # local stdio MCP portable source + reconstruction inputs
SOFTWARE.md
CONFIGURATION.md
INSTALLATION.md             # local MCP 混合安装证据与 embedded fallback；仅说明/数据
REAUTHORIZE.md
```

普通备份可为目录或 ZIP。含用户确认的敏感配置时只能是 AES 加密 ZIP，脚本直接从源文件写入压缩包，不创建明文暂存目录。使用同一口令可通过恢复脚本还原这些配置。ZIP 文件名和成员路径不一定加密，因此不得公开分享。

为满足“只带一个 ZIP 到新电脑”，AES 包把 `ARK-START-HERE.txt`、`AI-RESTORE.md`、`ARK-BOOTSTRAP.py`、`ark-tools/` 和不含源绝对路径/凭据的 `INSTALLATION.md` 作为公开成员；manifest、其余报告和全部用户数据仍使用 AES。新机只需 Python + `pyzipper`，无需另带方舟技能目录。公开 `INSTALLATION.md` 只含相对 target mapping、lock digest、package provenance、fallback/health/reauthorization 类型，不含命令或账户状态。

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
  "schemaVersion": "2.2",
  "tool": {"name": "ark", "version": "3.2.0"},
  "createdAt": "ISO-8601 UTC",
  "sourceUserHome": "原设备用户主目录",
  "sources": {
    "codex": {"home": "原设备路径", "found": true},
    "workbuddy": {"home": "原设备路径", "found": true},
    "hermes": {"home": "原设备 HERMES_HOME", "found": true},
    "hermes-memory": {"home": "原设备 .memory-tencentdb", "data": "原设备 memory-tdai", "found": true, "gatewayConfig": "原设备 YAML 路径"}
  },
  "options": {
    "profile": "basic|advanced|full|complete|credentials",
    "profileLabel": "中文说明",
    "includeSecrets": false,
    "zipEncrypted": false,
    "dedupe": "none|keep-newest|skip|merge"
  },
  "entries": [
    {
      "relPath": "codex/config.toml",
      "originPath": "原始绝对路径",
      "source": "codex|workbuddy|hermes|hermes-memory|workbuddy-connector|project",
      "size": 123,
      "sha256": "64位十六进制",
      "type": "config",
      "artifactClass": "configuration",
      "linkTarget": null,
      "sanitized": true
    }
  ],
  "artifactClasses": {"configuration": 1},
  "externalRoots": [{"id": "root-...", "sourcePath": "...", "archivePrefix": "...", "targetTemplate": "~/.agents/skills"}],
  "links": [{"relPath": "hermes/skills/x", "linkType": "junction", "externalRootId": "root-...", "targetRelativePath": "x"}],
  "softwareInventory": [],
  "projectMappings": [{"id": "project-a", "sourcePath": "...", "archivePrefix": "projects/project-a/content", "requiresExplicitTarget": true}],
  "localMcpProjects": [{
    "id": "default-apple-music-managed",
    "server": "apple-music-managed",
    "profile": "default",
    "sourcePath": "C:/Users/source/AppData/Local/applemusic-readonly-mcp",
    "archivePrefix": "local-mcp-projects/default-apple-music-managed/content",
    "target": {"kind": "localappdata", "relativePath": "applemusic-readonly-mcp", "requiresExplicitMapping": false},
    "commandRelativePath": ".runtime/Scripts/python.exe",
    "argsTemplate": ["-m", "applemusic_readonly_mcp.server"],
    "argsPathRewrites": [],
    "envPathRewrites": [{"name": "APPLEMUSIC_MCP_HOME", "relativePath": "state"}],
    "runtimeRecipe": {"type": "python-uv-lock", "python": "3.11", "runtimeRelativePath": ".runtime", "lockFile": "requirements.lock", "installLocalPackage": true, "verification": {"type": "python-import", "module": "applemusic_readonly_mcp.server"}},
    "installation": {
      "type": "hybrid-portable-v1",
      "nonExecutable": true,
      "target": {"mappingId": "default-apple-music-managed", "kind": "localappdata", "relativePath": "applemusic-readonly-mcp", "requiresExplicitMapping": false},
      "strategyOrder": ["trusted-source-when-verifiable", "embedded-source-fallback"],
      "trustedSource": null,
      "embeddedSourceFallback": {"type": "ark-archive-source", "archivePrefix": "local-mcp-projects/default-apple-music-managed/content", "lockFile": "requirements.lock", "role": "custom-project-source"},
      "runtime": {"name": "python", "version": "3.11", "packageManager": "uv", "recipeType": "python-uv-lock"},
      "lock": {"type": "uv-hash-locked-requirements", "path": "requirements.lock", "sha256": "0000000000000000000000000000000000000000000000000000000000000000", "hashMode": "require-hashes"},
      "packageProvenance": [{"type": "pypi-locked-requirement", "package": "applemusic-mcp", "version": "0.20.0", "hashes": ["sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"], "role": "locked-dependency"}],
      "healthCheck": {"type": "python-import", "module": "applemusic_readonly_mcp.server"},
      "reauthorization": "required"
    },
    "reauthorizationRequired": true,
    "portableState": ["state/managed-playlists.json"],
    "excludedAccountState": ["Windows Credential Locker", "Chrome profile/Cookies", "Music User Token", "device-bound login"]
  }],
  "portableAuth": [{"service": "Codex OpenAI OAuth", "archivePath": "codex/auth.json", "restoreMode": "attempt-then-reauthorize"}],
  "postRestoreActions": [],
  "coverageGaps": []
}
```

`originPath` 只用于说明快照来源；恢复目标只能由 `relPath` 与目标 home 映射得到，不能把 `originPath` 当写入路径。

`projectMappings[].contentIncluded` 明确普通项目正文是否进入包。`complete` 默认只记录 projects.db/cron 映射并令其为 `false`；只有显式 `--projects` 才遍历项目内容并置为 `true`。local MCP 不走这个开关，它是工具依赖闭包，仍按窄根自动收录。

`localMcpProjects[].portableState` 采用代码内固定 allowlist，当前唯一允许值是 `state/managed-playlists.json`；声明集合必须与该项目归档前缀下实际 `state/` entries 双向一致。`postRestoreActions` 同样只接受代码内已知 ID、精确字段和精确文本，它是非执行建议，不允许 manifest 扩展命令、shell 或任意动作。

自动恢复目标也必须命中代码内 allowlist：local MCP 仅允许 `localappdata` 或 `~/.local/share/...`；external root 仅允许已知技能/便携配置模板。其他 local MCP、cron script 和 external root 一律要求显式 map。旧式绝对 link 只允许落到已知技能存储，不得映射到 `.ssh` 等任意 home 目录。npm v3 根闭包同时验证 `dependencies`、`optionalDependencies`、`devDependencies` 与 `peerDependencies`。

`installation` 是 schema 2.2 的加法式、必填 local MCP 子对象，但它没有执行权限。固定键集合只表达目标映射、策略顺序、embedded source fallback、runtime/package manager、lock 摘要、package provenance、health-check 类型和 reauthorization boundary；不允许 `command`、`script`、`argv`、包管理器参数或未知字段。`INSTALLATION.md` 是同一对象的人类可读投影，也只能作为未来 AI 的安装判断依据，不能作为命令输入。

- Python `python-uv-lock` 固定记录 Python 3.11、uv、hash-locked requirements 与包内 custom source fallback。解析器只从 `name==exact-version` 和同行/续行 `sha256` 得出 dependency evidence；不从包名猜 GitHub、PyPI project URL 或 wrapper 来源。Apple Music 的 `applemusic_readonly_mcp` wrapper 没有可验证 remote，因此 `trustedSource` 必须为 `null`；锁定的上游 `applemusic-mcp==0.20.0` 只能列为 dependency provenance，不能替代 wrapper。
- Node `node-npm-lock` 逐项验证 npm v3 `packages` 闭包及依赖边：每个可安装条目都必须有 exact version、官方 `https://registry.npmjs.org` tarball 与 sha512 integrity，且 root spec 只能是版本范围。file/link、Git、HTTP、其他 host、缺失依赖或不完整条目直接使 lock 无效并阻断，不再以 `trustedSource: null` 继续执行；`trustedSource` 仍只为实际 Node entry 所属 root dependency 生成。
- restore 与 verify 先对对象做精确 ID/JSON type/key/path/URL host 校验，再从 `archivePrefix/lockFile` 读取包内 lock，核对其 manifest entry hash，并重新推导整个 `installation` 做完全相等比较。任何 path traversal、host/scheme 变化、lock evidence 漂移或 arbitrary command field 都在写目标前拒绝。

Node 配方默认不含 native marker。只有根 `package-lock.json`/`npm-shrinkwrap.json` 的 `packages["node_modules/keytar"]` 精确匹配受审计的 keytar 7.9.0 条目时，`runtimeRecipe` 才可增加以下固定对象；对象缺字段、多字段、类型变化或任一值变化都会在写入前被恢复器拒绝：

```json
"nativeCredentialAddon": {
  "type": "keytar",
  "version": "7.9.0",
  "resolved": "https://registry.npmjs.org/keytar/-/keytar-7.9.0.tgz",
  "integrity": "sha512-VPD8mtVtm5JNtA2AErl6Chp06JBfy7diFQ7TQQhdpWOl6MrCRB+eRbvAZUsbGQS9kiMq0coJsy0W0vHpDCkWsQ==",
  "hasInstallScript": true
}
```

锁中没有 keytar 时 recipe 保持不变；存在 keytar 但版本、registry URL、integrity 或 install-script 标志不符时产生阻断性 coverage gap，complete 不得出包。

Hermes 额外映射：`hermes/` → 目标 `$HERMES_HOME`；`hermes-memory/.memory-tencentdb/memory-tdai/` → 目标用户 `~/.memory-tencentdb/memory-tdai/`。外置 Gateway YAML 收敛到 `~/.memory-tencentdb/tdai-gateway.standalone.yaml`，恢复后再改写 `.env` 与 YAML 内部绝对路径。可重新下载的 TencentDB Node 运行时与插件副本不进入包。`instances/*/memory-generation-logs/` 是会被网关滚动清理的派生生成审计轨迹，不参与召回并明确排除；records/profiles/conversations/scene_blocks/metadata 与 SQLite 记忆真源仍收录。

## 级别

| 中文选项 | 内部值 | 主要内容 | 默认不含 |
| --- | --- | --- | --- |
| 基础备份（Codex、WorkBuddy、Hermes 的身份、技能、配置、记忆、自动化） | `basic` | 精确白名单 + 腾讯记忆 | 会话、敏感配置、缓存 |
| 中等备份（再含连接器、Hermes 扩展状态与项目索引） | `advanced` | 根级扩展内容 | 会话、敏感配置、缓存 |
| 全量备份（再含能找到的会话、Hermes 状态库与索引） | `full` | 会话正文与实际存在的索引文件 | 敏感配置、缓存、可重装运行时 |
| 完整迁移包 | `complete` | Hermes 全 profiles、完整根级用户态、Desktop 可迁移状态、外部技能/配置源、cron/projects.db/local stdio MCP 依赖、自定义 Provider | 账号状态、来源机运行时；未知 Hermes 根级项直接停止 |
| 凭据舱 | `credentials` | 静态密钥、Bot Token、邮箱授权码、外置敏感配置和可迁移 OAuth JSON；强制 AES | 记忆、会话、项目、Cookie、DPAPI/Keychain、设备绑定状态 |

`complete` 只对 Hermes 建立依赖闭包。Codex/WorkBuddy 继续使用审计白名单，避免把插件缓存与客户端运行时当用户产物。项目只来自 Hermes `projects.db` 与 cron 的 `workdir`，且拒绝用户 home 或文件系统根；目标路径由 `--project-map` 明确给出。local stdio MCP 则逐 profile 解析 `command`/`args`/`env`，只从绝对 launch path 向上寻找带 `pyproject.toml` + hash lock 或 `package.json` + npm lock 的窄根；无法证明时生成阻断 coverage gap，不以 PATH 猜测或扫描整块 home/AppData。

全量级的会话只代表归档其可见文件。客户端列表、索引格式、版本和服务端数据都可能影响显示；恢复后可能只能使用记忆，旧聊天无法完整显示或继续打开。不得把 hash 通过解释成“所有会话都能续聊”。

## 账号与敏感配置

- `credentials` 或 `--include-portable-oauth` 可封装 Hermes/Codex/Nous/OpenCode 的 JSON OAuth refresh/access token，恢复语义是“尝试验证，失效则重授权”，不是永久登录保证。
- Cookie、浏览器 profile、系统钥匙串、Windows Credential Manager、DPAPI、macOS Keychain、Desktop safeStorage 和设备绑定状态始终排除。
- `--include-sensitive-config` 只保留所选范围内的用户自管配置值，并强制写入 AES ZIP。
- “文件恢复成功”只证明加密包可读取且内容一致，不证明第三方账号、连接器授权或登录状态仍有效。

## 类型

`entries[].type` 可为：`identity`、`skill-file`、`config`、`memory`、`automation`、`project`、`conversation`、`secret`、`link`、`other`。`artifactClass` 进一步表达 `desktop-portable-state`、`custom-provider-source`、`external-root-content`、`local-mcp-project-source`、`link-topology` 等恢复语义。

- `sanitized: true`：包中是替换敏感值后的内容，`sha256` 对应脱敏版。
- `secret: true`：用户可控文件中的可迁移凭据，仅允许进入 AES 加密包。
- `linkTarget` + `linkType`：源项为 symlink/junction。绝对目标必须通过 `externalRootId` 或用户显式映射解析；不能解析就停止 apply。目标系统不能建 link 时生成降级标记，不复制目标树。
- `suspicious[].matches`：只记录高置信规则标签，不保存命中的疑似凭据原文。

## 恢复安全契约

- `--dry-run` 与 `--apply` 互斥；默认行为等同 `--dry-run`。
- dry-run 不写目标目录、不写备份包、不生成报告、不归档冲突。
- apply 覆盖前始终归档旧文件；不删除目标中多出的文件。
- `--fresh` 检测到现有环境时停止，不做清空。
- ZIP 读取拒绝绝对路径、`..`、重复 manifest 与符号链接成员；schema 2.2 的 external root/project/local MCP/link 映射字段也做 containment 校验。
- apply 在首次写入前校验全部已选成员；中途 I/O/link 失败时回滚本轮写入并恢复冲突归档中的旧文件。
- WorkBuddy 自动化禁止 SQL 写库，只生成待官方接口执行的计划。
- 已知配置中的旧用户主目录自动适配；报告列出变化。
- Hermes `.env`、Gateway YAML 和腾讯记忆数据目录自动适配到目标系统；自定义 `HERMES_HOME` 可显式覆盖。
- Hermes Desktop 只迁移 Local Storage/LevelDB 与明确布局/主题；Network/Cookies/connection token/DPAPI/safeStorage 永久排除。源或目标 live lock 会在 complete 中报告，apply 时拒绝不一致快照。
- 项目与外置 root 先建立映射，再写文件；所有覆盖仍进入冲突归档。目标平台为 Windows/macOS 时，dry-run 对大小写/Unicode 归一化冲突做 fail-closed；Windows 还拒绝保留名和非法字符。长路径交由目标系统的 long-path 支持与真实写入验证，不能用固定 240 字符阈值误伤来源机本来就能访问的文件。
- complete 的阻断性 `coverageGaps` 非空时，`--apply` 必须停止；schema 2.2 只要含 local-MCP payload，同一检查不信任 `options.profile`，改写 profile 也不能绕过。只读预览可以列出缺口但不能把它们降级成“已完成”。
- complete 项目保留 `.git/` 历史和普通交付物，默认不设单文件大小上限；只排除明确可重装的依赖/编译缓存。
- local MCP 与普通 project 采用不同规则：只收 `src/`、`scripts/`、`tests/`、`bin/`、项目/锁文件、launchers、README/SPEC/AGENTS/LICENSE 和显式 portable state；永久排除 `.runtime`、`.venv*`、`node_modules`、build/cache、`.git`、browser profiles/Cookies、confirmations、tokens、credentials 和系统 keyring。
- `runtimeRecipe.type` 只允许 `python-uv-lock` 或 `node-npm-lock`。恢复器自己构造 argv，`installation`/`INSTALLATION.md`/manifest 无权提供 shell；Python 使用 3.11、`uv venv`、`uv pip sync --require-hashes`、本地包安装与 import，Node 使用 `npm ci --ignore-scripts` 与 entry check。`ignore-scripts` 会同时阻止 keytar 生成 native binding；对上述唯一固定 marker，恢复器随后只用代码自有 argv 执行 `npm rebuild keytar --foreground-scripts --no-audit --no-fund`，再以 `node -e "require('keytar')"` 验证。不会从 installation metadata 读取包名、命令、URL、argv 或其他 lifecycle script。目标系统与运行恢复器的系统不一致时只允许 dry-run，不生成伪跨平台 runtime。
- code health 与 account health 分离：import/entry check 通过仍必须在 `REAUTHORIZE.md`/恢复报告中保留 device-bound reauthorization，绝不恢复 DPAPI、Credential Locker、Keychain 或 Cookies。
- SQLite 主库以 backup API 生成一致快照；WAL/SHM/JOURNAL sidecar 不入包。
- local MCP 的 `requiresExplicitMapping`、`.runtime` 固定路径、无 link、typed args 和选中目标的 `--fresh` 占用均在写入前检查。恢复后二次改写的 `.env`、Gateway YAML、projects.db 与精确 local-MCP profile config 进入同一冲突归档/回滚事务；sandbox verify 只对这些精确 config 做重写后字段校验，不 blanket-ignore `config.yaml`。

## 一句话恢复验收

任何格式变更都必须通过同一验收：只给新 AI 一个方舟 ZIP，并说“使用方舟技能恢复这个压缩包”，AI 能仅依赖包内公开 bootstrap/契约完成 dry-run、映射、解密、apply、verify 与健康检查。备份脚本、恢复器、验证器、`AI-RESTORE.md` 和端到端测试必须同步演进。

## 完整性与真实性

manifest hash 用于发现包内损坏和恢复差异，不是数字签名。能同时修改文件与 manifest 的人仍可伪造一致性；备份必须放在可信介质中。
