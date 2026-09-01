---
slug: apelican-ark
displayName: 方舟
version: 3.2.3
summary: 给 AI 工作环境做本地备份和恢复。换电脑、重装前先预览再备份。适用于：AI备份/助手搬家/技能迁移/记忆备份/方舟
license: Apache-2.0
name: apelican-ark
description: 为 Codex、WorkBuddy 和 Hermes 创建可预览、可校验的本地备份，覆盖技能、设置、记忆、自动化与 complete 模式下的 local stdio MCP 依赖闭包，并迁移 Hermes 的腾讯记忆系统；可生成 AES 凭据舱保存静态密钥并按需封装可迁移 OAuth。用于换电脑、重装前存档、恢复 AI 工作环境或检查方舟备份。默认只读预览，明确确认后才写入；不迁移 Cookie、DPAPI/Keychain、Credential Locker 或设备绑定登录态，不承诺会话能在客户端完整显示。适用于：AI备份/助手搬家/技能迁移/记忆备份/方舟
metadata:
  version: "3.2.3"
---

# 方舟
# 方舟

## 运行前提（先看这个）

- 需要 Python 3.10+（Windows / macOS / Linux 均可）。
- 基础备份、恢复和验证**只需 Python 标准库**，不需要额外安装。
- 只有选择「AES 加密敏感配置包」（含 API Key、Token 等凭据时）才需要额外安装
  `pyzipper>=0.3.6`（`pip install pyzipper`）；缺口令或缺依赖时会直接停止，绝不降级成明文。
- 所有脚本已直接随技能包提供，不要从 Markdown 重新抄写或重建。
- 含敏感配置的备份包加密后请**务必牢记方舟总密码**（见下方「方舟总密码是什么」），
  密码丢失该包将永远无法恢复。


把 Codex、WorkBuddy 与 Hermes 中由用户控制、适合迁移的文件整理成本地备份。Hermes 额外收录 `.memory-tencentdb/memory-tdai/` 数据、`$HERMES_HOME/.env` 和 `TDAI_GATEWAY_CONFIG` 指向的 `tdai-gateway.standalone.yaml`，恢复时自动改写用户路径。安装环境中的 `memory_tencentdb` Provider 位于 Hermes 的 `plugins/memory/memory_tencentdb/`，但它是未纳入 Hermes Git 的自定义插件，不得再视为上游自带运行时：备份预览必须将其标记为“需随包保存或提供已验证的重装来源”；只保存 `memory.provider: memory_tencentdb` 而不保存/重建 Provider 代码属于不完整备份。Node 运行时和 `node_modules` 仍按可重装依赖排除。核心边界：预览必须只读、旧文件必须可找回、设备绑定账号状态始终排除、可迁移 OAuth 只进 AES 且只承诺尝试恢复、会话文件恢复不等于客户端能完整显示、可重装且与操作系统绑定的运行时不进入迁移包。

## 一句话恢复硬约束

用户把任一方舟 ZIP 交给 AI，只说“使用方舟技能恢复这个压缩包”，AI 就必须能完成：识别包型 → 安装目标平台运行时 → 只读预演 → 路径映射/冲突处理 → 隐藏口令输入 → 正式恢复 → hash 与行为验证。不得要求用户先手工解包、搬运脚本或逐项解释配置。

每次修改方舟的备份范围、manifest、加密、路径或依赖时，必须同步检查并更新恢复器、验证器、`AI-RESTORE.md`、公开 bootstrap 和端到端回归。只会打包、不能由这一句话恢复的改动一律视为未完成。

每个 ZIP 都必须自带未加密且不含私人数据的 `ARK-START-HERE.txt`、`AI-RESTORE.md`、`ARK-BOOTSTRAP.py` 和 `ark-tools/`；AES 包还公开只含相对 target/lock/package/fallback/health/reauthorization 证据的非执行 `INSTALLATION.md`。即使新机没有安装 apelican-ark，AI 也能从包本身启动恢复。

## 选择备份级别

向用户展示中文选项，不直接显示内部英文值：

- 基础备份（Codex、WorkBuddy、Hermes 的身份、技能、配置、记忆、自动化；不含会话与敏感配置）→ `basic`
- 中等备份（再含连接器、Hermes 扩展状态与项目索引；不含会话与敏感配置）→ `advanced`
- 全量备份（再含能找到的会话、Hermes 状态库与索引；敏感配置仍需单独确认）→ `full`
- 完整迁移包（Hermes 全 profiles、Desktop 可迁移偏好、外部技能/配置源与 link、cron/projects.db/local stdio MCP 依赖闭包、自定义 Provider；未知 Hermes 根级项 fail-closed）→ `complete`
- 凭据舱（静态 API Key、Bot Token、邮箱授权码、Hermes/Codex/Nous/OpenCode 可迁移 OAuth；不含记忆、会话和项目，强制 AES）→ `credentials`

全量备份中的“会话”只是尽力保存本地可见文件。受客户端索引、版本和服务端数据限制，恢复后可能只能继续使用记忆，旧聊天无法在客户端完整显示或继续打开。公开描述只写已经验证的具体结果和限制。

`complete` 是显式的 Hermes 迁移模式，不等于无界扫描整块磁盘：默认只记录 Hermes `projects.db` 和 cron 明确登记的项目/workdir 映射，不复制普通项目正文；只有用户显式加 `--projects` 才闭合并打包这些项目内容。config/link 明确引用的外部技能源，以及每个 profile `mcp_servers` 中由绝对 command/args 路径证明的窄 local stdio MCP 项目仍自动收录，因为它们属于 AI 工具本体。项目恢复必须使用 manifest `projectMappings` 与 `--project-map ID=PATH`；local MCP 只接受窄项目根和带锁重建配方，不能证明根或确定性重建方式就记为阻断 coverage gap。Hermes 根出现未知项时必须停止并更新分类，不能静默遗漏或把未知目录当运行时。

## 安全工作流

1. 先运行只读预览。未指定 `--apply` 时，备份脚本默认只扫描；不得创建目录、ZIP、报告或清单。
2. 展示文件数、体积、技能、自动化、排除项、脱敏项与重复技能，再让用户确认范围。
3. 如需项目数据，先运行 `--list-projects` 展示真实存在的项目，让用户确认后再加 `--projects`。
4. 单独询问是否包含用户自管的敏感配置。默认不包含；账号登录、Cookie 和设备绑定授权不在选项内。
5. 显式确认后，用 `--apply` 创建备份；再运行验证工具。
6. 恢复时先 `--dry-run`，用户确认后另起一次命令使用 `--apply`。
7. 恢复完成后检查技能、身份、配置、路径、自动化和连接器登录状态，不以“文件存在”代替可用性检查。
8. 涉及 Hermes 或腾讯记忆时，读取 `references/hermes.md`；确认目标系统已安装 Hermes，再用 `hermes doctor` 与记忆健康检查验证运行时。
9. 每次方舟备份生成并验证完成后，主动提醒阿豪检查项目文件夹是否已同步到网盘；方舟默认只保存项目映射，不以方舟包替代项目网盘备份。

## 敏感配置与账号边界

> ⚠️ **备份了敏感配置，请一定记住方舟总密码**：含敏感配置的备份包用 AES-256 加密，
> 恢复时必须输入同一把密码；密码丢失后该包无法解密，凭据部分将永远无法恢复。
> 建议创建时就用密码管理器保存（详见下方「方舟总密码是什么」）。

面对用户时说“本地加密的敏感配置”，并明确可迁移 OAuth 只是尽力恢复，设备绑定登录态始终不迁移。

- `--profile credentials` 自动收录用户自管静态密钥，并把 Hermes/Codex/Nous/OpenCode 的可迁移 OAuth JSON 作为“尝试恢复”项；只允许进入 AES ZIP。
- 其他备份级别用 `--include-sensitive-config` 收录静态配置值，用 `--include-portable-oauth` 额外封装可迁移 OAuth。
- Cookie、系统钥匙串、Windows Credential Manager、DPAPI、macOS Keychain、Desktop safeStorage 和设备绑定授权始终排除。
- 含凭据时强制直接写 AES 加密 ZIP，不建立明文暂存目录；缺口令或缺 `pyzipper` 必须停止，绝不降级成普通 ZIP。
- 优先使用 `--password-env` 或 `--prompt-password`；不要把口令直接写进命令、聊天、文档或 manifest。
- 使用同一口令时，加密包可以由 `ark_restore.py` 恢复；发布前回归必须覆盖“生成加密包 → 只读预览零写入 → 正式恢复 → 逐文件 hash 一致”。
- 恢复配置文件不代表账号登录有效。换机后按新设备流程重新登录，不尝试恢复或验证 Cookie、OAuth 会话和设备绑定登录态。
- ZIP 成员路径可能可见；含敏感配置的备份不得公开分享或上传公共仓库。
- 所有处理都在本机完成；脚本不得联网或上传备份内容。
- Hermes 的 `.env` 与 `tdai-gateway.standalone.yaml` 可能同时含密钥；要实现密钥迁移，必须显式启用敏感配置并使用 AES 口令。

## 方舟总密码是什么

它不是微信、邮箱或 OpenAI 的账号密码，而是用户新设的一把“备份箱钥匙”。方舟用它对整个凭据 ZIP 做 AES-256 加密：创建时隐藏输入一次，恢复时再输入同一个密码。密码不写进 ZIP、manifest、聊天或命令历史；丢失后凭据舱无法解密。建议用密码管理器保存一条独立的 20 位以上随机密码，或 5 个互不相关的随机词，不与任何平台密码复用。

## 备份命令

```powershell
$ark = "<技能目录>"

# 默认只读预览
python "$ark/scripts/ark_backup.py" --profile basic

# 确认后执行普通目录备份
python "$ark/scripts/ark_backup.py" --profile basic --apply

# 全量归档，不含敏感配置
python "$ark/scripts/ark_backup.py" --profile full --zip --apply

# Hermes 完整迁移预览（仍严格零写入）
python "$ark/scripts/ark_backup.py" --profile complete

# 完整迁移包；如含配置值，必须用 AES ZIP
python "$ark/scripts/ark_backup.py" --profile complete --include-sensitive-config --prompt-password --apply

# 小型凭据舱：不含记忆/会话/项目；创建时隐藏输入一次方舟总密码
python "$ark/scripts/ark_backup.py" --profile credentials
python "$ark/scripts/ark_backup.py" --profile credentials --prompt-password --to-desktop --apply

# 可迁移凭据：从环境变量读取 AES 口令
python "$ark/scripts/ark_backup.py" --profile advanced --include-sensitive-config --password-env ARK_BACKUP_PASSWORD --apply

# 三端完整换机包：Codex + WorkBuddy + Hermes + 腾讯记忆 + 会话 + 密钥
python "$ark/scripts/ark_backup.py" --profile full --include-sensitive-config --prompt-password --apply

# 查看项目范围
python "$ark/scripts/ark_backup.py" --list-projects
```

备份脚本保留 `--include-secrets` 与 `--zip-password` 仅为旧版兼容；新流程不要主动推荐。`--keep` 不再删除旧备份，只提示用户手动整理。

## 验证命令

```powershell
# 包内 hash + 只读恢复预演；报告写到目标用户 ~/.ark/verify-reports/
python "$ark/scripts/ark_verify.py" "<备份目录或zip>"

# 只有用户明确提供沙箱目录时才执行真实沙箱恢复；工具不会自动删除它
python "$ark/scripts/ark_verify.py" "<备份目录或zip>" --sandbox-apply "<沙箱用户目录>"
```

验证通过只证明所选包内文件一致、恢复流程可执行；不证明第三方服务登录态、设备绑定凭据或客户端版本兼容。

## 恢复命令

```powershell
# 严格只读，且与 --apply 互斥
python "$ark/scripts/ark_restore.py" "<备份目录或zip>" --dry-run

# 另起命令执行
python "$ark/scripts/ark_restore.py" "<备份目录或zip>" --apply

# 加密包
python "$ark/scripts/ark_restore.py" "<备份zip>" --dry-run --password-env ARK_BACKUP_PASSWORD
python "$ark/scripts/ark_restore.py" "<备份zip>" --apply --password-env ARK_BACKUP_PASSWORD

# 新电脑只有一个 ZIP 时：先从 ZIP 解出公开的 ARK-BOOTSTRAP.py
python ARK-BOOTSTRAP.py "<备份zip>" --dry-run --prompt-password

# 凭据舱默认不覆盖目标已有 OAuth；空白新机直接恢复即可
python "$ark/scripts/ark_restore.py" "<ark-credentials.zip>" --dry-run --prompt-password
python "$ark/scripts/ark_restore.py" "<ark-credentials.zip>" --apply --prompt-password
# 只有明确确认目标旧凭据应被替换时再加 --replace-portable-auth

# 恢复 complete 项目（ID 从 CONFIGURATION.md/manifest 读取）
python "$ark/scripts/ark_restore.py" "<备份>" --dry-run --parts codex,workbuddy,hermes,hermes-memory,hermes-desktop,hermes-provider,external-roots,local-mcp-projects,projects --project-map "<id>=<新项目路径>"
```

恢复行为：

- 覆盖前把旧文件移到目标用户目录的 `~/.ark/restore-conflicts/<时间戳>/`；不删除本地多出的文件。
- 报告写到 `~/.ark/restore-reports/<时间戳>/`，不修改备份包。
- `--fresh` 只是一项空环境断言；检测到已有环境就停止，不删除目标。
- 自动适配已知配置中的旧用户主目录，并在报告中列出；外置盘和自定义程序路径仍需检查。
- `--apply-automations` 已停用。WorkBuddy 自动化只生成恢复计划，由 AI 使用官方自动化接口逐项创建并回读；禁止直接写 `workbuddy.db`。
- `projects` 默认只列出，不自动写回未知项目路径。
- 默认恢复范围已包含 `hermes` 与 `hermes-memory`。Windows 映射到 `%LOCALAPPDATA%\\hermes`，Linux/macOS 映射到 `~/.hermes`；可用 `--target-hermes-home` 覆盖。
- schema 2.2 的默认范围还包含 `hermes-desktop`、`hermes-provider`、可自动映射的 `external-roots` 与 `local-mcp-projects`。Desktop userData 映射到 Windows `%APPDATA%\\Hermes`、macOS `~/Library/Application Support/Hermes`、Linux `~/.config/Hermes`；只恢复 Local Storage/LevelDB 和明确的布局/主题文件。
- `localMcpProjects` 只携带 portable source、锁文件、launchers/scripts/tests/文档和显式 portable state。每项 schema 2.2 `installation` 是非执行数据：固定 target mapping、`trusted-source-when-verifiable → embedded-source-fallback`、lock/runtime/package manager、lock-derived package provenance、health check 与 reauthorization，并生成 `INSTALLATION.md`。Python 只从 hash lock 记录 exact pin/hash，不猜 repository URL，且拒绝全部 installer/index/find-links/trusted-host 指令；custom wrapper（包括无 Git remote 的 Apple Music wrapper）必须 embedded，上游 `applemusic-mcp 0.20.0` 只能是 dependency evidence。Node 必须逐项验证整个 npm v3 lock closure；file/link、Git、HTTP、非官方 registry、缺 version/resolved/sha512 integrity 或未锁定依赖一律阻断，不再通过 `trustedSource: null` 降级安装。restore/verify 必须从包内 lock 重新推导并完全比较，拒绝 traversal、未知键和 arbitrary command 字段。
- 恢复器只执行内置 allowlist 配方：Python 3.11 + `uv venv` + hash-locked `uv pip sync` + 本地包安装，或 `npm ci --ignore-scripts` + Node entry check；`installation`、`INSTALLATION.md` 与 manifest 不能提供任意 shell。ms365 的可选 `keytar` 是例外中的固定例外：仅当根 npm lock 的 `node_modules/keytar` 精确包含代码内审计的 7.9.0 registry URL、integrity 与 `hasInstallScript: true` 时，配方才加入精确 `nativeCredentialAddon` 标记，并由恢复器固定执行 `npm rebuild keytar --foreground-scripts` 和 `require('keytar')`；锚点不符是阻断 coverage gap。
- Apple Music MCP 的 `.runtime`、`.venv*`、build/cache、`.git`、`state/.applemusic-mcp` Chrome profile/Cookies、confirmations、tokens、credentials、Windows Credential Locker、Music User Token 和 device-bound login 永不进入包。代码 import/MCP 入口健康与账号授权分开报告，新机必须重新授权；方舟不会执行 Apple API 写操作。
- Junction/symlink 先恢复真实 external root，再重建拓扑；目标系统不支持时只创建 `.ark-link-degraded.json` 标记，绝不静默复制目标树。
- `projects` 默认不恢复；选择该 part 时必须逐项提供 `--project-map`。覆盖仍进入目标用户 `~/.ark/restore-conflicts/`。
- local stdio MCP 默认恢复到 manifest 的 `home`/`localappdata` 窄相对目标；`requiresExplicitMapping: true` 时无论 target kind 都必须提供 `--local-mcp-map ID=PATH`。可执行参数由 recipe 类型重建：Python 仅为 `-m <已验证模块>`，Node 仅为归档根下单一 entry path；不照抄任意 manifest argv。源运行时不复制，目标运行时在目标操作系统本机重建；跨平台 dry-run 可看映射，但 apply 不会伪造另一系统的运行时。
- 腾讯记忆数据固定恢复到 `~/.memory-tencentdb/memory-tdai/`，外置 YAML 收敛到 `~/.memory-tencentdb/tdai-gateway.standalone.yaml`；自动改写 Hermes `.env` 的配置与数据目录、YAML 的 `data.baseDir`，并移除来源机本地 Gateway 命令以便目标系统重新发现运行时。
- 腾讯记忆的 `instances/*/memory-generation-logs/` 是含 prompt、input/output refs、状态和耗时的易变生成审计轨迹，不参与召回；方舟明确排除它，避免网关清理与扫描竞态。`records/`、`profiles/`、`conversations/`、`scene_blocks/`、metadata 与 `vectors.db` 等记忆真源仍收录，SQLite 主库继续走一致性快照。
- 目标机恢复 `memory.provider: memory_tencentdb` 前，必须同时满足其一：备份包含当前自定义 Provider 源码及来源 manifest；或已从固定、经验证的官方来源重新安装相容版本并通过 provider discovery。安装环境源码树内的未跟踪 Provider 不能假定目标 Hermes 自带。Gateway 运行材料按 `references/hermes.md` 重装，恢复后必须实际执行 provider discovery、`/health` 和新会话 recall。
- `.db` 主库使用 SQLite backup API 生成一致快照；对应 WAL/SHM/JOURNAL 不复制，恢复后由 SQLite 重建。

## 恢复后检查

- 对照 `backup-summary.txt` 检查技能、身份与记忆数量。
- 打开已适配的 `config.toml`、`mcp.json`、`settings.json`、`models.json`，确认自定义盘符和软件路径。
- 通过官方界面检查 WorkBuddy 自动化是否逐项恢复；未回读前标记为“待恢复”，不要说已完成。
- 启动实际连接器或 MCP 做最小健康检查；设备绑定项如实列为“需重新授权”。
- 对 local stdio MCP 分开核对：锁定依赖同步、本地包 import/Node entry 为 code health；带固定 keytar 标记的 Node 配方还必须报告 credential addon verified。`npm ci --ignore-scripts` 单独使用会让 keytar 缺少 native binding，使 ms365 降级到 token cache 旁的 encryption-key 文件，因此不能把普通 entry check 当成 Windows Credential Locker 姿态已恢复；Cookie、Music User Token 与设备登录仍是 reauthorization-required。
- 对照 `INSTALLATION.md` 检查每个 local MCP 的 target、可信 package evidence 或明确的 unavailable、embedded fallback、lock digest、health-check type 与 reauthorization；该文档不包含可执行命令。
- 运行 `hermes doctor`，检查 `$HERMES_HOME/skills/`、`memories/`、`cron/`；再确认 `.memory-tencentdb/memory-tdai/`、网关 YAML 和记忆搜索可用。
- 会话归档只报告文件与索引是否就位。受客户端索引、版本和服务端数据限制，恢复后可能只剩记忆可用，旧聊天不一定能完整显示。

## 文件

- `references/format.md`：schema 2.2、artifact classes、local MCP typed recipe、映射与安全边界。
- `references/pitfall-log.md`：已发生错误、修复规则与回归闸门。
- `references/hermes.md`：Hermes/腾讯记忆的备份边界、跨系统路径、备份与恢复操作文档。
- `scripts/ark_common.py`：路径、识别、脱敏和安全 ZIP 规则。
- `scripts/ark_backup.py`：默认只读的备份实现。
- `scripts/ark_restore.py`：流式读取、冲突归档、路径适配和恢复报告。
- `scripts/ark_verify.py`：不修改备份包的完整性与恢复预演。
