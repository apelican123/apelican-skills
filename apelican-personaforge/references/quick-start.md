# 从零开始：把一个能力接进 ChatGPT

这条路径默认面向第一次部署的普通用户。你不需要先弄懂 MCP、隧道或 OAuth；先准备已有能力的接口材料，技能会判断后面的实现方式。

## 0. 先选使用范围

- **只给自己用（默认）**：在自己的 Cloudflare 账号部署，生成一条带用户名标识的专属能力链接；ChatGPT 选择“无身份验证”。
- **给少量可信用户用**：优先让每个人各自在自己的 Cloudflare 账号部署；确需共用一个 Worker 时，一人一链接、一人一摘要 Secret，并做跨用户错配测试。
- **大量用户、独立账号数据或公开发布**：使用 OAuth 2.1，不能继续用人工管理的链接 Token 代替多用户权限系统。

上游 API Key/Client ID 始终放在 Cloudflare Secrets。完整专属链接也是访问密钥，不能公开或截图。

## 1. 准备项目

在项目目录确认当前 Node.js、npm 和 Wrangler 可用。版本要求以项目依赖和 Cloudflare 当前文档为准。

### Windows PowerShell

```powershell
node --version
npm --version
npx wrangler@latest whoami
```

### macOS / Linux

```bash
node --version
npm --version
npx wrangler@latest whoami
```

如果 `whoami` 未登录，运行 `npx wrangler@latest login`，在浏览器完成授权后再继续。

**验证门 1**：终端显示当前 Cloudflare 账号，而不是未登录或权限错误。

## 2. 生成并检查 Worker

根据上游类型使用 [templates.md](templates.md) 的 REST 翻译、单 MCP 代理或多 MCP 编排模式。生成后先运行：

```powershell
npm install
npm test
npx tsc --noEmit
npx wrangler@latest deploy --dry-run
```

macOS / Linux 使用同样命令。

`wrangler.toml` 或 `wrangler.jsonc` 中的兼容日期必须是 Cloudflare 已发布日期，不写未来日期。专属链接会把 Token 放进路径，因此关闭会记录完整路径的 invocation logs/traces，只保留脱敏应用日志。

**验证门 2**：测试、类型检查和 dry-run 都成功；任何占位 URL 或缺失 Secret 都不能被当成已完成。

## 3. 为用户创建独立链接

在技能目录运行随包提供的 JavaScript 工具。用户名只是标签，工具会自动加短哈希并生成独立的 256 bit 随机 Token。

### Windows PowerShell

```powershell
node <skill-dir>\scripts\create-user-link.js `
  --username "你的用户名" `
  --base-url "https://你的-worker-域名"
```

### macOS / Linux

```bash
node <skill-dir>/scripts/create-user-link.js \
  --username "你的用户名" \
  --base-url "https://你的-worker-域名"
```

工具只在当前终端显示一次：

- `userId`：规范化后的用户名标识；
- `secretName`：Cloudflare Secret 名称；
- `secretValue`：随机 Token 的 SHA-256 摘要；
- `privateUrl`：要粘贴到 ChatGPT 的完整专属链接。

不要把输出保存进项目文件、聊天记录、截图或 Git。若终端会被录屏或集中采集日志，改在受信任的本地终端运行。

**验证门 3**：不同用户名得到不同 `userId`、不同 Secret 名称和不同链接；重复为同一用户名生成时 `userId` 稳定，但 Token 必须变化。

## 4. 把摘要放到 Cloudflare

运行命令后，按提示粘贴 `secretValue`。不要粘贴完整 URL，也不要粘贴 URL 中的原始随机 Token。

### Windows PowerShell

```powershell
npx wrangler@latest secret put <上一步的-secretName>
```

### macOS / Linux

```bash
npx wrangler@latest secret put <上一步的-secretName>
```

上游凭据逐项用独立 Secret 设置，例如：

```text
UPSTREAM_API_KEY
UPSTREAM_MCP_TOKEN
```

**验证门 4**：`npx wrangler@latest secret list` 能看到 Secret 名称，但任何命令和文档都看不到 Secret 值。

## 5. 部署并做三种拒绝测试

记录旧生产 version ID，再部署：

```powershell
npx wrangler@latest deploy --keep-vars
```

随后准备三条只存在当前进程的 URL：

1. 正确的本用户完整链接；
2. 同一用户名但 Token 错误的链接；
3. A 用户 Token 拼到 B 用户路径形成的跨用户错配链接（多人 Worker 才需要）。

按 [validation-and-release.md](validation-and-release.md) 运行审计。

**验证门 5**：正确链接能完成 `initialize` 和 `tools/list`；错误 Token、未知用户名、跨用户错配均返回 401/403/404。审计输出不得回显任何 URL。

## 6. 接入 ChatGPT

按 [chatgpt-setup.md](chatgpt-setup.md)：

1. 启用当前账号/工作区允许的 Developer mode；
2. 新增 MCP/plugin 连接；
3. 粘贴 `privateUrl`；
4. 身份验证选择 **无身份验证**（若当前表单显示此项）；
5. 核对工具并做一个真实只读调用。

ChatGPT 不需要上游 API Key、Cloudflare Secret、Token 摘要或 OAuth client secret。

**验证门 6**：ChatGPT 能列出预期工具，并用自然语言请求得到一次真实只读结果。

## 7. 交付撤销和轮换方法

- **撤销单个用户**：删除该用户的摘要 Secret 或从 Worker 允许映射中移除对应 binding，重新部署并确认旧链接失败。
- **轮换单个用户**：用相同用户名重新运行生成器，替换同名 Secret 的摘要，只把新 `privateUrl` 私下交给该用户；旧链接必须立即失败。
- **链接泄露**：先撤销，后排查日志/截图/分享范围，再生成新链接；不能只提醒用户“不要再用”。
- **多人增加**：每位用户重复第 3–5 步，不复制上一位的 Token 或 Secret。

## 何时停止使用这条快速路径

出现以下任一情况，切换 OAuth 2.1：用户数量需要自动注册/回收、每人有独立账号数据或 scope、组织权限复杂、需要公开上架、链接可能经第三方系统广泛流转。专属能力链接是方便的私人入口，不是完整身份系统。

本地/内网数据使用 OpenAI Secure MCP Tunnel，读 [local-tunnel-deploy.md](local-tunnel-deploy.md)，不要用临时公网转发冒充长期生产入口。
