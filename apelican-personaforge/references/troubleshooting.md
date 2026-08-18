# 常见问题排查

先判断故障在哪一层，不要同时改 Cloudflare、MCP 协议和 ChatGPT 配置：

1. 本机环境；
2. Cloudflare 登录/部署；
3. 用户专属链接校验；
4. MCP 初始化和工具；
5. 上游 API/MCP；
6. ChatGPT 页面或工作区权限；
7. OAuth/公开审核。

每次只改变一项，改后重跑相邻验证门。

## 本机环境

### `node`、`npm` 或 `npx` 找不到

安装当前 Node.js LTS，关闭并重新打开终端，然后运行：

```powershell
node --version
npm --version
npx --version
```

macOS / Linux 使用同样命令。版本要求以项目 `package.json`、所选 SDK 和 Cloudflare 当前文档为准，不把旧文档中的固定版本当永久规则。

### Wrangler 未登录或浏览器没有弹出

```powershell
npx wrangler@latest whoami
npx wrangler@latest login
```

如果终端显示授权 URL 但没有自动打开，手动复制到已登录 Cloudflare 的浏览器。公司网络/VPN 阻断时先换受信任网络或按组织规则配置代理；不要把 Cloudflare API Token 贴进聊天。

### Windows 中 `curl` 参数不工作

PowerShell 的 `curl` 可能映射到 `Invoke-WebRequest`。使用 `curl.exe`，或直接运行随包的 `scripts/audit-mcp.js`。手动测试时不要把真实专属 URL写进脚本文件或终端历史共享记录。

## 生成用户链接

### 生成器提示缺少参数

必须同时提供用户名和 HTTPS Worker 域名：

```powershell
node <skill-dir>\scripts\create-user-link.js `
  --username "你的用户名" `
  --base-url "https://你的-worker-域名"
```

用户名可以含中文；无法转成拉丁标签时会使用 `user-<短哈希>`，不会拿用户名当 Token。

### 同一用户名生成了不同链接，是不是坏了？

不是。`userId` 应保持稳定，随机 Token 每次都必须不同。重新生成并替换同名 Secret 就是轮换；替换后旧链接应失败。

### 不同用户名看起来相近

短哈希用于区分规范化后可能相近的用户名。不要手工删除哈希，也不要自行复制别人的 `userId`；最终以生成器输出为准。

### 输出被保存到终端日志了

把完整链接视为已泄露：先删除或替换该用户 Secret，确认旧链接 401/403/404，再生成新链接。清理终端/集中日志只能作为后续处理，不能代替撤销。

## Cloudflare Secret 和部署

### Secret 设置后仍然 401/404

按顺序检查：

1. `secretName` 与生成器输出完全一致，大小写和下划线没有手改；
2. 粘贴的是 `secretValue`（64 位摘要），不是完整 URL 或原始 Token；
3. `npx wrangler@latest secret list` 能看到该名称；
4. Worker 代码使用同样的 `secretBinding(userId)` 规则；
5. 部署的是刚更新的 Worker 版本；
6. 等待短暂边缘传播后再测。

Secret 值无法读回是正常的。不要为了核对而把摘要写进 `wrangler.toml`、`.env` 或 Git。

### Worker 名称无效或已存在

Worker 名称使用当前 Cloudflare 允许的格式，通常为小写字母、数字和连字符。名称冲突时改成新的可识别名称，不删除现有 Worker，除非用户明确确认目标和恢复路径。

### `deploy --dry-run` 通过但生产失败

dry-run 不证明生产 Secrets、域名路由和上游网络可用。检查：

- 当前 Cloudflare 账号和目标环境；
- Secret 名称是否存在于生产环境；
- 自定义域名/DNS 是否已生效；
- 上游是否允许 Cloudflare 出口请求；
- 最新部署 version ID 与预期是否一致。

失败时回滚单个 Worker 到部署前记录的 version ID，不连带回滚其他服务。

### Windows `.wrangler` 缓存写入失败

先关闭占用项目文件的编辑器、终端和杀毒扫描，确认项目目录可写，再重试。若确需清理缓存，先确认 `.wrangler` 的解析后绝对路径位于当前项目中，并把它移动到任务专用临时隔离目录；不要对模糊变量或上级目录运行递归删除。

## 专属链接返回 401、403 或 404

这三个状态都可以用于 fail closed，先分清请求是否本来就应该失败。

### 正确链接也失败

检查：

1. URL 没有换行、空格、引号或被聊天软件截断；
2. 路径严格为 `/u/<userId>/<43字符Token>/mcp`；
3. `userId` 与 Secret binding 对应；
4. Token 是生成器当次输出的链接内容，未与旧轮换版本混用；
5. Worker 没有把完整路径交给错误的路由；
6. 生产环境存在对应摘要 Secret。

不要通过临时开放固定 `/mcp` 来“证明服务能用”；这会绕开需要验证的安全层。

### 错误 Token 反而成功

立即停止接入和发布。常见原因：

- 认证失败分支返回了 `true`；
- 没有 Secret 时默认放行；
- 只检查路径格式，没比较摘要；
- MCP handler 在认证之前已经执行；
- 固定 `/mcp` 仍公开可用。

修复后重跑错误 Token、未知用户名和跨用户错配三项测试。

### A 的 Token 放到 B 的路径也成功

说明多用户没有真正隔离。检查 Worker 是否按 URL 中的 B `userId` 读取 B 的摘要，而不是使用全局共享 Token。修复前不要给第二位用户交付链接。

### 每个人链接不同，但仍能看到彼此数据

入口隔离成功不等于上游数据隔离。若 Worker 对所有 `userId` 使用同一个管理员 API Key，用户仍可能访问同一数据。需要按 `userId` 映射独立上游凭据/scope，或切换 OAuth 2.1。

## MCP 协议和工具

### HTTP 200 但审计失败

MCP 错误可能在 JSON-RPC body 或 `result.isError` 中。查看审计输出的 `failures`，不要只看 HTTP 状态。

### `initialize` 失败

检查：

- 端点支持 Streamable HTTP；
- 请求 `Accept` 包含 `application/json, text/event-stream`；
- 协议版本在客户端和服务器支持范围；
- 返回稳定 `serverInfo` 和非空 `instructions`；
- 有状态旧服务是否要求 `mcp-session-id`。

新 stateless Worker 优先使用 Cloudflare 当前 `createMcpHandler`。旧 `McpAgent`/legacy transport 只在有明确兼容需求时保留迁移通道。

### `tools/list` 为空

逐层检查：

1. 上游能否独立 `initialize` 和 `tools/list`；
2. 上游 Secret 是否存在且未过期；
3. 工具注册代码是否执行；
4. 有状态上游的 session header 是否回带；
5. 多 MCP 枚举是否因单个超时被整体中断；
6. 缓存是否需要主动刷新。

### 有工具但 ChatGPT 调用失败

检查工具 `description`、输入 schema 和真实 API 参数是否一致；确认返回 `content`，声明 `outputSchema` 时同时返回匹配的 `structuredContent`。写工具的权限和确认注解不能标成只读。

### SSE 看起来像乱码

`event:` / `data:` 行是 Server-Sent Events 帧，不一定是错误。使用 MCP Inspector 或审计脚本解析；不要用会把未知大流全部读入内存的临时代码替代生产流式透传。

### 上游超时或响应太大

先直接测试上游，再调整有界超时。列表分页、文档分块和响应大小必须有上限；写操作不能因超时盲目重试。

## ChatGPT 侧

### 找不到 Developer mode 或 Plugins 页面

Developer mode 的可用性取决于当前账号、产品界面和工作区策略。按 OpenAI 当前文档检查 **Settings → Security and login**；组织账号还要确认管理员策略。不要把旧版“某个固定套餐一定有/一定没有”写成永久规则。

### 表单没有“无身份验证”选项

先确认当前页面是否把认证方式自动从服务器或连接类型推断。如果页面只要求公网 MCP URL，粘贴专属链接即可，不要额外添加 OAuth 或上游 API Key。若页面明确要求一种本技能未覆盖的认证，停止并按当前官方文档调整，不能选一个近似项硬过。

### ChatGPT 显示连接失败，但 MCP Inspector 成功

检查：

- 工具 schema 和 annotations 是否全部可序列化；
- 专属链接模式是否残留 OAuth `securitySchemes`；
- `notifications/initialized`、`ping`、`tools/list` 是否都正常；
- ChatGPT 是否缓存旧元数据；部署后在连接页面 Refresh，再开新对话测试；
- 账号或工作区是否允许该连接。

### ChatGPT 不调用工具

先确认连接已在当前对话启用，再用一条自然但明确的请求测试。若仍不调用，检查工具名、title、description、参数说明和正反向测试集；不要仅通过在提示词里强制点名工具来掩盖元数据问题。

### 手机端暂时看不到

先在 OpenAI 当前文档支持的表面完成创建和验证，再检查移动端版本、同一账号/工作区和同步状态。不要把某一旧客户端的页面位置写成跨平台固定入口。

## OAuth 和公开发布

### 未认证请求没有进入登录流程

检查 401 响应的 `WWW-Authenticate`、protected-resource metadata、授权服务器 metadata、PKCE `S256`、CIMD/DCR 或预定义客户端配置，以及 `resource` 参数是否一致。

### scope 不足只返回普通错误文本

工具错误应带 `_meta["mcp/www_authenticate"]` challenge，并准确说明所需 scope。普通 200 文本错误无法让客户端正确发起再授权。

### 私人链接能用，为什么不能公开提交？

私人链接只是 Developer mode 的私人入口。公开插件需要稳定公网域名、OAuth 2.1、组织/个人验证、隐私与支持材料、准确工具权限、测试提示和 OpenAI review。不要用“私人可用”替代“审核通过”。

## 需要提供报错时

可以提供：错误状态、错误消息、发生步骤、Worker version ID、工具名、脱敏后的路径结构和审计 `failures`。

不要提供：完整专属 URL、Token、Secret 值、Authorization header、Cookie、上游私人数据、Cloudflare 账号敏感信息。截图前先遮挡这些内容。
