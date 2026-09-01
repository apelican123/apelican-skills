# 方舟踩坑记录

## 预览曾实际写入

旧版恢复的 `--dry-run` 曾归档冲突文件并写入目标目录，却仍声称没有改动。当前规则是：预览和执行参数互斥；预览不创建目标、报告或冲突归档；隔离回归必须断言目标不存在。

## 敏感配置曾可能降级为明文

旧版可能在缺少 AES 依赖时继续生成普通 ZIP。当前规则是：只要包含敏感配置，就必须同时有口令和 `pyzipper`；缺少任一条件立即停止，不能降级。

## 账号状态与配置值曾混为一谈

配置里的用户自管敏感值可以在单独确认后进入 AES 包，但账号登录文件、Cookie、系统钥匙串、DPAPI/设备绑定数据和 OAuth 会话始终排除。恢复配置不代表账号授权有效。

## 会话文件曾被当成聊天完整恢复

全量档只尽力归档本地可见的会话文件和索引。恢复后可能只能继续使用记忆，旧聊天不保证在客户端完整显示或续接。

## 自检参数和校验和曾用错

`ark_selfcheck.py` 不接受 `--skill-dir`。从技能根目录直接运行脚本；公开包修改脚本后，先更新 `checksums.json` 再自检。校验和失败必须阻止打包。

## 公开审核版不能保留加密授权值能力

小红书《Red Skill 服务协议》第 5.1 条把 API 密钥、密码、私钥和凭证列为安全扫描重点。把这类能力改名成“敏感配置”不足以降低风险；公开审核版必须删除发现、保留、加密打包与恢复这些值的参数、依赖和代码路径，并排除私人会话与数据库。个人本地完整版另用独立技能名和醒目禁止上传标识，不能混入 SkillHub 包或公开笔记导流。

## 排除高风险数据的代码仍可能显得在扫描高风险数据

公开版 3.0.0 虽然默认排除账号与会话数据，代码仍主动定位隐藏应用目录，枚举相关目录、文件名、字段名与内容特征，并在 manifest 中保留源绝对路径；平台再次未通过且未给出具体原因。不能断言这些命中就是实际审核原因，但公开包不应出现“公开审核版”等风控分叉措辞，也不应保留实际用途不需要的发现、清洗和恢复代码。

## 选择整个文件夹与“不处理账号数据”不能同时绝对承诺

如果迁移清单不读取文件正文，却允许原样复制整个技能或资料目录，普通非隐藏文件中仍可能嵌入账号或授权数据。公开最小版应拒绝文件夹与非文档输入，只接受用户逐个选择的安全文档类型；否则必须如实说明无法检测正文中的内容，不能用绝对排除措辞。

## 精确文件白名单版本仍可能未通过

4.0.1 已收缩为只处理用户逐个选择的 Markdown 文档，仍在平台审核中未通过，平台未提供具体原因。这不能证明某个词或某段代码就是命中项。此后不再围绕同一类本地资料处理能力继续换词，公开版改为仅根据用户对话生成换机准备清单和新机验收表，不申请文件、设备或网络权限；本地完整工具继续保持独立，不混入公开包。若零权限清单仍未通过，应停止重复提交并等待明确的审核反馈。

## Windows Hermes 根目录混有可重装运行时

Windows 默认 `%LOCALAPPDATA%\hermes` 同时包含用户数据与 `hermes-agent/`、便携 Node/Git、venv 等来源系统运行时。整根原样恢复到另一操作系统会制造不可执行文件和错误绝对路径。方舟只迁移用户态，目标机先安装 Hermes，再把备份映射到目标 `$HERMES_HOME`。

## 腾讯记忆不能只备份一个目录

`.memory-tencentdb/memory-tdai/` 保存 L0-L3 数据，但 provider 激活在 Hermes `config.yaml`，密钥和 Gateway 路径在 Hermes `.env`，网关配置又可能位于 `TDAI_GATEWAY_CONFIG` 指向的外置 YAML。缺任一项都不能称完整数据与配置迁移。方舟把三处作为一个恢复单元，并在目标机收敛到稳定路径；Provider 是否上游内置必须按 Git/来源核验，未跟踪自定义源码随 complete 包保存，可下载的 Gateway 运行时不打包。

## SQLite 主库与 WAL/SHM 不能直接拼包

运行中的 `vectors.db`、`state.db` 等可能处于 WAL 模式。直接复制主库再带上不同时刻的 WAL/SHM 会得到撕裂快照。方舟用 SQLite backup API 生成一致主库，明确排除 sidecar；恢复后由 SQLite 重建 sidecar。

## 腾讯记忆生成日志会制造活跃扫描竞态

`instances/*/memory-generation-logs/` 是包含 prompt、input/output refs、状态与耗时的派生审计轨迹，网关会按保留策略滚动清理。旧扫描先 `scandir` 后 `stat/hash`，文件可能在两步之间消失，使 complete 产生 `source-changed-or-unreadable` 并永远无法稳定预览。3.2 将该精确目录名归为 `derived-memory-generation-audit-log` 并排除；records、profiles、conversations、scene blocks、metadata 与 `vectors.db` 等召回真源仍备份，SQLite 继续用一致性快照。回归必须证明日志不进包、排除原因可见、核心记忆仍在。

## 嵌套进程锁不能当用户文件读取

旧规则只在 Hermes 根级识别进程锁，像 `kanban/.dispatcher.lock` 这种嵌套互斥锁仍会进入 hash，活跃进程占用时产生假 coverage gap。3.2 将点前缀 `.*.lock`、精确 `LOCK/lock/lockfile` 与 `*.pid` 加入通用 runtime file pattern；不使用笼统的 `*.lock`，因此 `requirements.lock`、`uv.lock`、`poetry.lock` 和项目内重建锁仍会保留。注册项目和 local MCP 继续走独立收录规则。

## 行级脱敏曾把密钥原文带回输出

旧 `redact_lines` 在自由文本行命中高置信密钥后，仍拼接原行前 120 字符，足以泄露完整 token。3.1 只输出固定占位符和规则标签，测试必须断言命中行的前缀、后缀与密钥都不在备份文本。

## Junction 不能当普通目录递归

Windows Junction 可能指向 `~/.agents/skills`、`~/.codex/skills` 或其他真实源；跟随它会制造重复副本并掩盖单一真源。complete 记录 link 类型、目标 external root 与相对路径；目标不可读时列 coverage gap，绝不跟随。恢复失败则留下 `.ark-link-degraded.json`。

## Hermes 新根级项不能静默漏掉

静态白名单在 Hermes 更新后会遗漏小众目录。complete 使用闭集分类：用户态、可重装运行时、账号/设备状态或显式 gap，任何未知根级项都停止预览/apply。普通级别仍可跳过，但必须在 coverage gaps 中说明。

## complete 不能带着 coverage gap 出包

只读预览可以列出 live 写入、锁、缺失项目、断裂 link 等问题，但 `--apply` 必须对阻断性 coverage gap fail-closed。否则“清单里诚实写了缺口”仍会生成一个名为完整、实则缺文件的包。

## 项目内容不能套用应用缓存白名单

项目里的 `.git/`、`logs/`、`dist/`、`build/`、`out/` 可能是历史、交付物或用户数据。complete 只排除明确可重装的依赖/编译缓存（如 `node_modules`、venv、Rust `target`、`__pycache__`），保留 Git 历史和普通项目产物；单文件大小默认不限。

## 大文件和 JSON 数组也可能藏凭据

旧版只扫描小于 4MB 的文本，较大的 `.txt`/配置文件可把 token 原样带进明文包；JSON 数组里的标量 token 也曾绕过字典递归。3.1 对大文件做流式高置信扫描，并递归替换 JSON 数组/根标量：非 AES 模式命中即排除或脱敏，AES 模式才保留。

## 不能把父进程环境变量自动灌入 profile

Gateway、测试进程或另一个 profile 的 ambient env 不等于当前 profile 的配置。方舟只记录所需变量名；可迁移值来自各 profile `.env` 的 AES 备份，`TDAI_GATEWAY_CONFIG` 也优先读取源 profile `.env`。旧 `.ark-portable-environment.env` 只保留供人工审查，恢复器不再自动 merge。

## Manifest 里的映射字段也是不可信输入

只校验 `entries[].relPath` 不够；`externalRoots.targetTemplate`、`archivePrefix`、`links.targetRelativePath`、project/root id 都可能把写入引到目标 home 之外。schema 2.1 恢复前逐项验证逻辑 id、相对路径与 containment，并拒绝带阻断 coverage gap 或缺失 Provider 来源的 complete manifest。

## Tracked Provider 也可能有本地修改

`git ls-files` 只能证明上游跟踪过，不能证明工作树干净或 remote 可重建。Provider 目录 tracked 但 dirty，或 tracked+clean 却没有固定 remote/commit 时，同样必须把当前源码随 complete 包保存并逐文件 hash；只有 tracked+clean 且 remote+commit 可验证时才依赖重装。

## 恢复不能边写边发现包损坏

恢复 apply 在第一次写目标前先核对全部已选成员的存在性与 hash。中途 I/O/link 失败时，回滚本轮已创建内容，并把冲突归档中的旧文件移回；回滚结果写入恢复报告。

## Live cron ticker 不是可迁移数据

`cron/ticker_heartbeat` 与 `cron/ticker_last_success` 会在 Gateway 运行时持续变化，第一次真实出包因此在写前复核阶段正确停止。3.1 将它们归为进程心跳/派生状态并始终排除；权威 cron 定义仍是 `cron/jobs.json`。

## 根 manifest 与技能 manifest 不能混淆

第一次真实全量 ZIP 验证发现，包内技能/插件自带多个 `manifest.json`，旧恢复器把所有 `*/manifest.json` 都当成 Ark 根，误报“实际 12 个”。3.1 现在优先要求 ZIP 根的唯一 `manifest.json`；只有整包确实被单一目录包裹时才接受 `<wrapper>/manifest.json`，嵌套技能 manifest 只是普通数据。

## 凭据舱与资料包分离

大体积资料包默认不含明文密钥；`credentials` 模式单独生成小型 AES-256 ZIP，收静态 API Key、Bot Token、邮箱授权码和外置敏感配置，并按“尝试恢复”封装 Hermes/Codex/Nous/OpenCode OAuth JSON。Cookie、DPAPI/Keychain、Credential Manager、Desktop safeStorage 和设备绑定状态仍排除。恢复时目标已有 OAuth 默认保留，只有显式 `--replace-portable-auth` 才覆盖。

“方舟总密码”不是任何平台账号密码，而是用户新设的备份加密口令。创建和恢复各输入一次，方舟不保存；丢失后凭据舱不可解密，也不能与平台密码复用。

## Desktop LevelDB 与账号状态不是一回事

`Local Storage/leveldb` 含 `ctx.storage`、用户布局、主题和 prompt snippets，可迁移但 live 时可能锁定；complete 探测并报告一致性，apply 遇锁停止。`Network/Cookies/connection token/Local State/DPAPI/safeStorage` 永久排除并写入 REAUTHORIZE.md。

## 只记 MCP 名称会恢复出一条死 command

3.1.1 的 complete 配置清单知道 `mcp_servers` 名称，却没有从 stdio `command`/`args` 关闭本地项目依赖。来源命令若指向项目内 `.runtime/Scripts/python.exe`，新机即使恢复 `config.yaml` 也只得到不存在的绝对路径。3.2 对每个 Hermes profile 显式解析 stdio binding，只从绝对 launch path 推导带 marker/lock 的窄项目根；收 portable source 和重建输入，拒绝扫描 home、AppData 或 LocalAppData 根。无法证明根、模块或 lock 时生成阻断 coverage gap，不能把“配置已还原”写成 MCP 可用。

来源 runtime 仍不迁移：`.runtime`、`.venv*`、`node_modules`、build/cache 和平台二进制全部排除。schema 2.2 只允许代码内置的 Python/uv 或 Node/npm 配方，manifest 不能携带任意命令。apply 在目标 OS 本机重建后执行 import/entry check，再改写对应 profile config；失败要回滚 source/runtime/config，不得留下半成功状态。

## `npm ci --ignore-scripts` 会破坏 ms365 的 Credential Locker 姿态

`@softeria/ms-365-mcp-server` 0.145.2 可选使用 keytar；keytar 7.9.0 依赖 install script 生成 native binding。Ark 为避免供应链脚本默认执行 `npm ci --ignore-scripts`，但只做到这里会使 `require('keytar')` 失败，ms365 随后把 encryption key 放到 token cache 旁的文件中，上游只把这种方式描述为防止随手查看。不能因为 Node entry syntax check 通过，就声称 Windows Credential Locker 已恢复。

修复必须保持窄而固定：只解析根 npm lock 的 `packages["node_modules/keytar"]`；仅当 version 7.9.0、官方 registry URL、固定 integrity 与 `hasInstallScript: true` 全部匹配时写入唯一 typed marker。恢复器对该对象做精确键、值和 JSON 类型校验，然后用代码内置 argv 定向执行 `npm rebuild keytar --foreground-scripts` 与 `node -e "require('keytar')"`。manifest 不能选择包名、版本、URL、integrity 或命令；锁中 keytar 不匹配就是阻断 coverage gap，重建或加载失败进入既有事务回滚。无 keytar 的 Node E2E 保持 marker-free。

## Apple Music 代码健康不等于账号授权

Apple Music MCP 的 portable `managed-playlists.json` 只含受管歌单元数据，可以逐文件收录；Windows Credential Locker、Music User Token、Chrome profile/Cookies、confirmations、tokens、credentials 和 device-bound login 不能迁移，也不能因为 ZIP 使用 AES 就放行。恢复报告必须把 `passed-python-import` 与 `reauthorization-required` 分开，且任何验证都不得调用 Apple API 写端点。

## “给未来 AI 的安装指导”不能变成第二条命令执行面

只携带 embedded source 虽然可离线恢复，却缺少可审计的 trusted-source/fixed-version/target-path 指引；反过来把安装命令或猜测的仓库 URL 写进 manifest，又会让数据成为任意执行入口并把 custom wrapper 偷换成上游依赖。3.2 使用加法式 `installation`：固定目标映射、两段式策略顺序、embedded fallback、typed runtime/lock、package evidence、health check 与 reauthorization；同时生成只读 `INSTALLATION.md`。

证据必须来自包内 lock。Python 只解析 exact pin + sha256，Apple Music 的 `applemusic-mcp==0.20.0` 仅是 dependency provenance，wrapper source 仍 embedded；Node 只接受实际 entry root dependency 的 exact version、`https://registry.npmjs.org` tarball 和 sha512 integrity。restore/verify 在写入前重新推导并完全比较，严格拒绝 traversal、非 registry URL、unknown/arbitrary command 字段。执行仍只有代码自有的 `python-uv-lock`/`node-npm-lock` allowlist recipe。

## 路径安全不等于状态内容安全

仅用 `_safe_posix_rel()` 检查 `portableState` 只能阻止 `../`，仍会放行 `state/.applemusic-mcp/.../Cookies` 这类合法相对路径。3.2 恢复器必须同时验证代码内状态 allowlist、声明去重、manifest entries 与声明集合双向一致；当前只允许 `state/managed-playlists.json`。同理，`postRestoreActions` 即使不由 Python 直接执行，也会展示给未来 AI，必须按代码内固定 ID/字段/文本精确验证，拒绝未知动作和额外 `commands`/shell 字段。

## complete 不能因为项目索引自动吞掉普通资料树

projects.db/cron 的登记关系需要迁移，但“知道项目在哪”不等于“用户授权把整个项目正文装进本次包”。真实预览曾在桌面“双考”目录长时间 hash，偏离了迁移插件/MCP/数据的目标。3.2 默认只生成 `projectMappings` 并写 `contentIncluded: false`；只有显式 `--projects` 才遍历普通项目。local stdio MCP 与外部技能源属于 AI 工具本体，继续按窄依赖闭包自动收录。

## state-snapshots 不能凭名字猜成用户态

真实 complete 预览曾在 Loki profile 的 `state-snapshots/` fail-close。Hermes 源码把它定义为每 profile 更新前 quick snapshot，并在自身 full backup walk 中显式排除，理由是避免把 state DB 每个 snapshot 再打包一次；因此 3.2 仅把这个精确名称归入派生 recovery/runtime state。相邻或未来未知根项仍维持 fail-closed，不能用 `*snapshot*` 通配降级。

## Lock 证据不能只挑可信项后仍执行完整 lock

独立 NO-GO 评审证明，忽略 Python index/find-links 指令或只从 npm lock 摘出安全 root evidence，仍会把未验证的原 lock 交给包管理器。3.2 现在拒绝所有 Python installer directive，并验证 npm v3 的整个 registry resolution/依赖闭包；任何 file/link、Git、HTTP、非官方 registry、缺 version/integrity 或缺失依赖都成为阻断 gap。keytar marker 还必须在目标写入前及 foreground rebuild 前从当前嵌入 lock 精确再推导。

## 二次路径改写也必须属于恢复事务和精确验证

`.env`、Gateway YAML、projects.db 可能因 plan skip 而未进入初始 `changed`，local-MCP config 也曾被 verifier 用文件名 blanket-ignore。所有 in-place repair 现在写前做冲突快照并加入同一 rollback；sandbox 只豁免 manifest 明确绑定的 profile config，随后逐项核对 code-owned command、typed args 与 env path。`--fresh` 同时检查全部 selected parts，包括 Desktop、Provider、external roots、projects 和每个 local-MCP 自动/显式目标。

## manifest 的 false 不是授权

独立二次评审证明，把 `requiresExplicitMapping` 改成 `false` 曾可让恶意 manifest 自动写入 `~/.ssh`；泛化的 `~/...` external template 和 legacy absolute link 也有同类问题。恢复器必须忽略“布尔值即授权”的思路，重新按代码内精确 allowlist 判断 local target、external template 和 link destination。npm 根 `peerDependencies` 也会触发 npm 自动解析，必须进入 lock closure 校验。

## 活跃真状态与活跃缓存不能一刀切

Hermes 运行中会持续改写 `channel_directory.json`、`cron/jobs.json` 和技能 `.usage.json`。前两者是真状态，apply 必须在收尾阶段重新读取有效 JSON，继续走结构化脱敏/AES 边界并固化为内存 payload；后者只是调用缓存，可按精确文件名排除。不能为了让 preflight 通过就笼统跳过所有变化文件，也不能反复要求整轮扫描期间保持不变。
