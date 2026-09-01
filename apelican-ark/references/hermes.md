# Hermes 与腾讯记忆迁移

## 已确认的目录架构

Hermes 的用户数据根由 `HERMES_HOME` 决定：

- Windows 原生安装：默认 `%LOCALAPPDATA%\hermes`。
- Linux/macOS：默认 `~/.hermes`。
- 显式设置 `HERMES_HOME` 时，以该路径为准。

`$HERMES_HOME/skills/` 是 Hermes 用户技能的主源。常用用户态还包括 `config.yaml`、`.env`、`SOUL.md`、`profile.yaml`、`scripts/`、`assets/`、`tui-widgets/`、`webhooks/`、`plugin-data/`、`memories/`、`cron/`、`hooks/`、`profiles/`、`sessions/`、桌面/统一插件和状态数据库。每个 `$HERMES_HOME/profiles/<name>/` 又是独立 home，complete 必须逐个按同一规则扫描。

Windows 原生布局会把用户态与可重装运行时放在同一根目录。不要原样迁移整个根：`hermes-agent/`、`bin/`、`node/`、`git/`、虚拟环境、`node_modules`、缓存、日志、PID 和锁依赖来源操作系统或进程空间。目标机先安装 Hermes，方舟再覆盖用户态。

## memory_tencentdb 的四个组成部分

1. **数据**：`~/.memory-tencentdb/memory-tdai/`，这是方舟需要备份的腾讯记忆数据目录。
2. **Hermes 配置**：`$HERMES_HOME/config.yaml`，通过以下配置选中 provider：

   ```yaml
   memory:
     provider: memory_tencentdb
   ```

3. **密钥与路径**：`$HERMES_HOME/.env`，可含 LLM/embedding 密钥、`TDAI_GATEWAY_CONFIG`、数据路径和 Gateway 设置；仅在 AES 敏感备份模式中原样收录。
4. **Gateway 配置**：`tdai-gateway.standalone.yaml`。来源位置由 `.env` 的 `TDAI_GATEWAY_CONFIG` 指定，方舟将其收进稳定的包内路径。

Provider 代码不能仅凭目录位置推定为 Hermes 上游内置。它可能位于 checkout：

```text
<hermes-agent>/plugins/memory/memory_tencentdb/
```

方舟先用 Git 跟踪状态与来源核验：若该目录未被当前 Hermes commit 跟踪（当前本机就是 Git 未跟踪目录），complete 必须把源码与逐文件 hash 收进 `hermes-provider/`，恢复到目标 `$HERMES_HOME/plugins/memory/memory_tencentdb/`。只有能给出固定、可验证且兼容的来源时才可不随包保存。TencentDB Node 运行时、`node_modules` 与 `tdownload` 仍不备份。

## 方舟备份范围

### 所有级别

- Hermes 核心用户态：身份、技能、配置、记忆、cron、hooks、profiles 等。
- `.memory-tencentdb/memory-tdai/` 中参与召回和重建的真源数据；明确排除 `instances/*/memory-generation-logs/` 派生生成审计轨迹。该目录包含 prompt、input/output refs、状态与耗时，会被网关滚动清理，不是恢复记忆所需的数据。
- `TDAI_GATEWAY_CONFIG` 指向的 `tdai-gateway.standalone.yaml`。
- 腾讯记忆 SQLite 主库的一致性快照；不复制 WAL/SHM/JOURNAL sidecar。
- `config.yaml`，从而保留 `memory.provider: memory_tencentdb`。
- `.env` 的脱敏副本；选择敏感模式时，原值只进入 AES 加密 ZIP。

### 中等备份

再含 Hermes 的 kanban、platforms、shared、state 等扩展用户态。

### 全量备份

再含 Hermes 本地 sessions、`state.db`、`kanban.db`、`projects.db`、`verification_evidence.db` 等可见会话和索引状态。

### 完整迁移包（complete）

- 对 Hermes 默认 home 与所有 named profiles 应用根级闭集分类；未知项 fail-closed。
- 收 `cron/jobs.json`，解析其 skills/script/workdir；再闭合被引用脚本、外部技能真实源和 workdir 项目。
- 收 `projects.db` 一致快照，并把登记项目真实内容放入 `projects/<id>/content/`；不会默认写回旧绝对路径。
- 收 junction/symlink 拓扑，真实源只保存一次；不跟随 junction 静默实体化。
- 收 Hermes 技能依赖的已知外置配置：`~/.agents/skills`、Himalaya、Yescan、OpenCLI 与 WorkBuddy key fallback；敏感值仍只进 AES，Cookie/OAuth 仍排除。
- 收 Windows `%APPDATA%\Hermes`、macOS `~/Library/Application Support/Hermes`（Linux `~/.config/Hermes`）中的 Desktop 可迁移子集。`Local Storage/leveldb` 承载 `ctx.storage`、布局、主题与 prompt snippets；live lock 必须报告并在 apply 前停止。
- 遍历默认 home 与每个 named profile 的 `config.yaml`，显式解析 local stdio MCP 的 `command`、`args`、`env`。只有绝对 launch path 能收敛到带确定性 lock 的窄项目根时才标为 covered；否则是阻断 coverage gap。

### Local stdio MCP 项目

- Python 项目收 `src/`、`pyproject.toml`、`requirements*.in/lock`、launchers、`scripts/`、`tests/`、README/SPEC/AGENTS/LICENSE；Node 项目收 portable source、`package.json` 与 `package-lock.json`/`npm-shrinkwrap.json`。普通 Hermes project 的广范围规则不适用于这里。
- 可选 state 只能逐文件放行。目前 Apple Music MCP 仅允许 `state/managed-playlists.json`；`.runtime`、`.venv*`、`node_modules`、build/cache、`.git`、`state/.applemusic-mcp`、Chrome profile/Cookies、confirmations、tokens、credentials 永久排除。
- schema 2.2 的 `localMcpProjects` 记录 profile/server binding、source/archive/target mapping、command/args/env path rewrite、typed runtime recipe、portable state、excluded account state 与 `reauthorizationRequired`；每项还必须有非执行 `installation`，把 target、`trusted-source-when-verifiable → embedded-source-fallback`、lock/runtime/package-manager、可审计 package provenance、health check 与重新授权边界结构化，并生成人类可读 `INSTALLATION.md`。
- `installation` 只从已收项目证据和 lock 推导。Python wrapper 始终用 embedded custom source；requirements 只贡献 exact pin + sha256 evidence，不推断 repository URL，并拒绝任何 installer/source 指令。现有 Apple Music wrapper 没有 Git remote，`applemusic-mcp==0.20.0` 即使在 lock 中也只是上游依赖证据，不能代替 wrapper。Node 只有整个 npm v3 lock closure 的每个 resolution 都是 exact 官方 registry tarball + sha512 integrity 且依赖边闭合时才允许重建；任一 file/link/Git/HTTP/缺失证据都阻断。
- restore/verify 会从包内 lock 重新推导 installation 并完全比较。该对象与 `INSTALLATION.md` 均不得提供或执行 command/script/argv；任何未知字段、路径越界、非 HTTPS/非 npm registry URL、lock hash/evidence 不一致都在写入前拒绝。
- 恢复器不执行 manifest shell。Python 仅允许 Python 3.11 + uv + hash lock + local package install + import；Node 默认仅允许 `npm ci --ignore-scripts` + entry check。ms365 的可选 keytar 7.9.0 需要 install script 生成 native binding，单独使用 `ignore-scripts` 会让它回退为 token cache 旁的 encryption-key 文件，只能防止随手查看，不能维持 Windows Credential Locker 姿态。方舟只信任根 npm lock 中精确的 keytar 7.9.0 registry URL、integrity 和 `hasInstallScript: true`：匹配时写入固定 typed marker，由代码自有 argv 定向 `npm rebuild keytar --foreground-scripts` 并执行 `require('keytar')`；不匹配时 complete 以 coverage gap 阻断。运行时必须在目标操作系统本机重建。
- Apple Music 的 Windows Credential Locker、Music User Token、Chrome Cookies 和 device-bound login 必须在新机重新获取。import/code health 通过不等于账号健康，恢复/验证报告必须分别展示。

### 凭据舱（credentials）

- 只收 Hermes/Codex/WorkBuddy 配置与 `.env`、Himalaya 授权码、Yescan/OpenCLI/WorkBuddy fallback 等外置敏感配置。
- 默认把 Hermes/Codex/Nous/OpenCode JSON OAuth 作为 best-effort 项封装；新机先验证 refresh token，失效再重授权。
- 不收记忆、会话、项目或 Desktop localStorage，因此包很小，可和资料包分开高频备份。
- Cookie、MCP OAuth cache、ms365/Windows Credential Manager、DPAPI、Keychain、safeStorage 和设备绑定会话始终不收。
- 强制 AES-256；需要用户自设并保存一条独立的方舟总密码。

### 始终排除

- 已由固定 Hermes commit 跟踪且可从同一官方来源重装的 bundled Provider；未跟踪/自定义 Provider 不在此排除项。
- TencentDB Gateway 运行时、`tdownload/`、`node_modules/` 与其他可重新下载的源码/依赖。
- Hermes 源码 checkout、Python venv、便携 Node/Git、构建缓存。
- 日志、PID、锁、更新缓存和来源机进程状态。
- 每个 profile 的 `state-snapshots/`：Hermes `hermes_cli.backup` 把它定义为更新前 quick snapshot，并在自身 full backup walk 中排除以避免重复携带 state DB；因此属于派生恢复/runtime state。只有这个已由源码证明的名称被分类，其他未知根项继续 fail-closed。
- `auth.json`、Cookie、系统钥匙串、DPAPI 和设备绑定登录态。换机后仍按新设备流程登录。
- Desktop `Network/`、Cookies、connection/connection token、Local State 中的 DPAPI/safeStorage、设备 OAuth；即使 AES 也不放行。

## 原文件与运行时从哪里下载

- 腾讯官方仓库：<https://github.com/TencentCloud/TencentDB-Agent-Memory>
- 官方中文安装说明：<https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/main/README_CN.md>
- npm 包名：`@tencentdb-agent-memory/memory-tencentdb`
- Hermes 官方仓库：<https://github.com/NousResearch/hermes-agent>

新系统安装当前版 Hermes 后，先用 `hermes plugins`/provider discovery 核验相容 Provider。若 manifest 携带自定义源码，方舟恢复到用户 Provider 路径；若未携带，则 manifest 必须给出已验证来源。Gateway 运行材料仍按腾讯官方 README 为目标操作系统重新安装；不要跨 Windows、Linux、macOS 或 CPU 架构复制 `node_modules`。

方舟恢复会删除 `.env` 中指向来源机源码/`tdownload` 的活动 `MEMORY_TENCENTDB_GATEWAY_CMD`，保留并改写数据、YAML 和密钥路径，让新系统使用官方安装的目标平台运行时或 Hermes 自动发现逻辑。

## 完整备份步骤（含密钥）

1. 完整迁移先关闭 Hermes Desktop；如需最稳妥快照，也可停止会写腾讯记忆/cron/session 的 Gateway。方舟会为 SQLite 做在线一致快照，并跳过易变且不参与召回的 `memory-generation-logs`；其余真源文件若在扫描后变化或不可读，complete apply 仍会 fail-closed，不生成“缺文件的完整包”。
2. 运行只读预览：

   ```powershell
   python "$ark/scripts/ark_backup.py" --profile complete --include-sensitive-config
   ```

   未带 `--apply` 时不会创建目录、ZIP、报告或 manifest。

3. 查看输出中的四个来源：`codex`、`workbuddy`、`hermes`、`hermes-memory`。`hermes-memory.data` 应指向现有的 `memory-tdai`，`gatewayConfig` 应指向现有 YAML。
4. 用隐藏口令生成 AES 包：

   ```powershell
   python "$ark/scripts/ark_backup.py" --profile complete --include-sensitive-config --prompt-password --apply
   ```

5. 验证包内 hash 与只读恢复预演：

   ```powershell
   python "$ark/scripts/ark_verify.py" "<ark-时间戳.zip>" --prompt-password
   ```

## 新电脑恢复步骤

1. 安装目标操作系统对应的 Hermes、Python 3.11 与 uv；按 manifest 恢复自定义 Provider 或从已验证来源安装兼容 Provider，不能假定上游内置。
2. 按上一节的腾讯官方链接重新安装目标平台 Gateway 运行材料。运行时不来自方舟备份。
3. 将方舟技能和 AES 备份包放到目标机可读位置。
4. 只读预演：

   ```powershell
   python "$ark/scripts/ark_restore.py" "<备份.zip>" --dry-run --prompt-password
   ```

5. 确认覆盖与冲突归档清单后执行：

   ```powershell
   python "$ark/scripts/ark_restore.py" "<备份.zip>" --apply --prompt-password
   ```

   local stdio MCP 会在这一步把 source 恢复到目标 `home`/`LocalAppData` 映射，重建干净 runtime，改写 Hermes profile config，并执行 import/entry health check。带固定 keytar marker 的 ms365 还必须在报告中同时出现 Node entry 与 credential addon verified；任一重建/加载失败都会中止并回滚。外置 root 使用 `--local-mcp-map ID=PATH`；账号授权仍留给新设备登录流程。

6. 自定义 Hermes 数据目录时显式指定：

   ```powershell
   python "$ark/scripts/ark_restore.py" "<备份.zip>" --apply --prompt-password --target-hermes-home "<新 HERMES_HOME>"
   ```

恢复脚本会自动完成：

- Hermes 用户态写入目标系统的 `$HERMES_HOME`。
- 腾讯记忆数据写入目标用户的 `~/.memory-tencentdb/memory-tdai/`。
- 外置 YAML 固定到 `~/.memory-tencentdb/tdai-gateway.standalone.yaml`。
- 改写 `.env` 的 `TDAI_GATEWAY_CONFIG`、`TDAI_DATA_DIR`、`MEMORY_TENCENTDB_ROOT`。
- 注释来源机的 `MEMORY_TENCENTDB_GATEWAY_CMD`，避免新系统继续引用旧盘符或旧源码。
- 改写 YAML 的 `data.baseDir`。
- 覆盖前把目标机旧文件移入 `~/.ark/restore-conflicts/<时间戳>/`，不删除目标机多出的文件。

## 恢复后验证

依次检查：

```text
hermes doctor
$HERMES_HOME/config.yaml
$HERMES_HOME/.env
$HERMES_HOME/skills/
~/.memory-tencentdb/memory-tdai/
~/.memory-tencentdb/tdai-gateway.standalone.yaml
```

确认 `config.yaml` 仍是 `memory.provider: memory_tencentdb`。再启动 Hermes，执行一次记忆搜索与一次新对话写入，确认 Gateway 健康、旧记忆可检索、新记录可落盘。

## 跨系统边界

方舟备份的数据、配置和路径布局可以在 Windows、Linux、macOS 间映射。目标系统仍需安装其对应的 Hermes、Node 与 TencentDB Gateway 运行时；这是“数据与配置一键恢复、运行时按官方来源重建”，不能表述为一个旧系统压缩包在任意系统零安装直接执行。

文件内容按 hash 校验，但跨文件系统不承诺保留 NTFS ACL/ADS、macOS xattr/quarantine、POSIX owner、hardlink/sparse-file 物理布局或全部可执行位；这些属于系统元数据而非方舟 3.2 的可移植数据契约。大小写/Unicode 冲突、外置盘映射和 Desktop LevelDB 跨大版本兼容必须在目标机 dry-run 与健康检查中确认。
