# 跨设备安装与使用

本技能包以 Markdown 说明为主，并保留两个可直接运行的 JavaScript 小工具：生成一人一条的专属能力链接，以及审计 MCP。小红书上传页已经明确展示支持 `.js`，因此不再为了旧兼容假设把可执行脚本强行压进 Markdown。技能不要求额外 Codex 插件、私人 MCP、固定用户名或固定磁盘路径。

## 安装技能包

1. 解压后保留根目录名 `apelican-personaforge`。
2. 把整个目录复制到客户端支持的 Skills 目录。常见用户级示例：
   - Codex：`~/.codex/skills/apelican-personaforge/`
   - WorkBuddy：`~/.workbuddy/skills/apelican-personaforge/`
   - 其他支持 `SKILL.md` 的客户端：使用其当前文档指定的用户级技能目录。
3. 重启或刷新客户端的技能列表。
4. 用“把一个 REST API 做成我的 ChatGPT 个人插件，请一步一步带我完成”测试触发。

**验证**：客户端能识别名称 `apelican-personaforge`，先用普通话确认你想带进 ChatGPT 的能力，再判断私人专属链接、OAuth 或 Tunnel；如果只复制 `SKILL.md` 而丢失 references 和 scripts，安装不完整。

## Windows、macOS 与 Linux

- 文档采用 UTF-8 Markdown；解压工具不得改编码。
- Windows 使用 PowerShell 命令块；macOS/Linux 使用 bash 命令块。
- 路径含空格时使用当前 shell 的引用规则，不把示例 `~` 展开成作者机器路径。
- Node/npm/Wrangler 在每台实际执行部署的机器上单独验证。

**验证**：运行 `node --version`、`npm --version`、`npx wrangler@latest whoami`；
读取四个项目文件并完成 `tsc --noEmit` 与 Wrangler dry-run。

## 多设备调用 Cloudflare Worker

Worker 部署后，第二台设备通常只需要该用户自己的完整 HTTPS 专属 URL，或 OAuth/Tunnel 对应的连接方式。
不要复制 Cloudflare API Token、上游 API Key、`.wrangler` 目录或项目中的 Secret。

第二设备回归：

1. `/health` 返回最小状态，不泄露工具或上游；
2. 错用户名、错误 Token 和跨用户错配为 401/403/404；
3. 正确认证完成 init/initialized/ping/list；
4. 工具数量与第一设备一致；
5. 调用一个只读工具，关键字段一致；
6. 写工具不用于自动迁移测试。

## Tunnel 不等于云端多设备

OpenAI Secure MCP Tunnel 连接的是一台持续在线的主机。手机或其他电脑可以通过同一工作区
使用该连接，但原主机、Tunnel client 和本地 MCP 必须保持运行。迁移主机时重新取得控制面
凭证并重做 Tunnel 的全部验证，不复制明文凭证或依赖作者机器路径。

## 发布包完整性

发布者提供 ZIP 的 SHA-256。使用者解压后确认：

- 根目录只有技能需要的 Markdown 和已说明的 `.js` 文件；
- `SKILL.md` 在根目录；
- `references` 与 `examples` 层级未扁平化；
- 没有 `.env`、`.dev.vars`、日志、缓存、`node_modules`、真实链接或私人项目配置；
- ZIP 哈希与发布说明一致。
