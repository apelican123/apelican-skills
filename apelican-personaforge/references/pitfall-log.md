# 历史踩坑记录与解决方案

## 目录

- #1–#5：SDK、依赖与废弃 API
- #6–#12：SSE、认证、Secret、冷启动与响应解析
- #13–#18：名称、环境、工具冲突、模型选择与上游 Token
- #19–#28：超时、缓存、JSON-RPC、占位符、跨平台与额度
- #29–#32：有状态 session、协议偏差、传输差异与 Windows Wrangler

这些条目是历史证据。执行前先读当前 [templates.md](templates.md)、
[validation-and-release.md](validation-and-release.md) 和官方文档；历史代码不得覆盖当前规范。

> 共 32 条。它们保留问题证据和迁移背景；包版本、协议版本、套餐、价格、认证与 CLI 命令可能已变化。1.1.0 实施时以 `openai-plugin-contract.md`、`templates.md`、`security-checklist.md` 和当前官方文档为准，本文件不得覆盖现行规范。

## 1. agents 包版本不存在

**问题**：
```
npm error code ETARGET
npm error notarget No matching version found for agents@^1.0.0
```

**原因**：`agents` 包没有按 semver 发布版本号。

**解决**：package.json 中用 `"agents": "latest"`。

**仅影响模式 A**：代理模式（B）和聚合模式（C）不依赖 `agents` 包。

## 2. node:async_hooks 模块缺失

**问题**：
```
Uncaught Error: No such module "node:async_hooks".
```

**原因**：`agents/mcp/server` 内部使用 Node.js 的 `async_hooks`，Cloudflare Workers 默认不提供。

**解决**：wrangler.toml 添加：
```toml
compatibility_flags = ["nodejs_compat"]
```

**仅影响模式 A**：代理模式和聚合模式不使用 `agents/mcp/server`。

## 3. McpAgent 类已废弃

**问题**：迁移时报错：
```
New version of script does not export class 'OldClassName' which is depended on by existing Durable Objects
```

**原因**：旧版 `McpAgent` 依赖 Durable Objects，新版本已废弃。

**解决**：迁移到 `createMcpHandler` 无状态架构。如果之前部署过旧版本，在 wrangler.toml 中添加迁移配置：
```toml
[[migrations]]
tag = "v1"
deleted_classes = ["YourOldClassName"]
```

## 4. server.tool is not a function

**问题**：
```
TypeError: this.server.tool is not a function
```

**历史原因**：当时使用的 MCP SDK 主版本改变了工具注册 API。

**当前处理**：检查已安装 `@modelcontextprotocol/server`、`agents/mcp/server` 与 Zod 的类型及
Cloudflare 当前 `mcp-worker` 示例；当前常见 API 使用 `server.registerTool()`，不要仅凭旧文章猜方法名。

## 5. Peer dependency 冲突

**问题**：
```
npm error ERESOLVE unable to resolve dependency tree
```

**原因**：zod v4 与 @modelcontextprotocol/sdk 的 peer dependency 声明冲突。

**解决**：`npm install --legacy-peer-deps`。

## 6. SSE 连接超时

**问题**：MCP 端点无响应，请求超时。

**原因**：缺少 `Accept` 头。MCP 的 Streamable HTTP 传输需要客户端声明接受 `text/event-stream`。

**解决**：请求时必须带：
```
Accept: application/json, text/event-stream
```

## 7. Token 鉴权方式与安全默认值

**历史问题**：旧版私人连接界面只能输入 URL，无法额外配置请求头。

**当前处理**：新私人连接优先 Bearer；公开插件使用 OAuth 2.1。只有维护旧私人连接时才通过
显式开关兼容 URL token 或 API-Key Header。未配置认证必须 fail closed，入口 token 使用
定长摘要比较，并支持短期 previous token 轮换。当前完整实现见 [templates.md](templates.md)
的“公共安全函数”，不要复制旧版直接字符串比较示例。

> URL token 会进入浏览器历史、代理日志和截图，不能用于公开发布。旧版 `return true` 的 fail-open 行为已禁止。

## 8. Secret 传播延迟

**问题**：设置 Secret 后立即测试返回 401。

**原因**：Cloudflare Secrets 需要几秒钟传播到 Worker 实例。

**解决**：等 5-10 秒后重试。如果仍失败：
1. 确认 Secret 名称与代码中 `env.字段名` 完全一致（区分大小写）
2. 运行 `npx wrangler secret list` 确认 Secret 已设置
3. 重新设置（**跨平台命令**）：
   ```bash
   # 推荐方式：交互式输入（跨平台，最安全）
   npx wrangler secret put API_KEY
   # 运行后会提示输入值，输入后按回车，值不会显示在屏幕上

   # macOS / Linux 管道方式
   echo "your-value" | npx wrangler secret put API_KEY

   # Windows PowerShell 管道方式（⚠️ 不要用 echo 带引号）
   "your-value" | npx wrangler secret put API_KEY
   ```

## 9. Windows .wrangler 目录权限

**问题**：
```
Failed to write to output file: open ...\.wrangler\tmp\deploy-xxx\index.js: Access is denied.
```

**原因**：Windows 上 .wrangler 临时目录可能被系统或杀毒软件锁定。

**解决**：
- 方案 1：删除 .wrangler 目录后重试
  ```powershell
  Remove-Item -Path .wrangler -Recurse -Force
  npx wrangler deploy
  ```
- 方案 2：在项目所在目录的父级以管理员身份运行终端
- 方案 3：换一个目录创建项目（如用户目录下的 Documents）

## 10. wrangler 未登录

**问题**：
```
Error: You need to authenticate with Cloudflare to use this command.
```

**解决**：运行 `npx wrangler login`，浏览器会打开授权页面，点击 Allow。

**如果浏览器没有自动打开**：复制终端输出的 URL，手动粘贴到浏览器。

## 11. 冷启动错误

**问题**：首次调用返回"用户不存在"等错误。

**原因**：Cloudflare Workers 冷启动时 Secrets 可能需要几秒才能注入。

**解决**：重试一次即可。这是平台行为，不影响正常使用。

## 12. SSE 响应解析

**问题**：聚合模式下，上游返回 `text/event-stream` 格式，直接 JSON.parse 失败。

**原因**：部分 MCP 服务器返回 SSE 格式而非纯 JSON。

**解决**：解析 `data:` 行提取 JSON：
```typescript
function parseMcpResponse(text: string): any {
  if (text.includes("\ndata:")) {
    const lines = text.split("\n");
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("data:")) {
        const jsonStr = trimmed.slice(5).trim();
        try { return JSON.parse(jsonStr); } catch {}
      }
    }
  }
  if (text.startsWith("data:")) {
    const match = text.match(/^data:\s*(.+)/m);
    if (match) {
      try { return JSON.parse(match[1]); } catch {}
    }
  }
  try { return JSON.parse(text); } catch { return { error: text.slice(0, 500) }; }
}
```

## 13. Worker 名称冲突

**问题**：
```
Error: A worker named "my-mcp" already exists in your account.
```

**原因**：Cloudflare 账号下已有同名 Worker。

**解决**：修改 `wrangler.toml` 中的 `name` 为不同的名称，如 `my-mcp-v2`。

## 14. Node.js 不在 PATH 中

**问题**（Windows）：`node --version` 或 `npx wrangler` 提示"不是内部或外部命令"。

**解决**：
1. 确认 Node.js 已安装：检查 `C:\Program Files\nodejs\` 目录是否存在
2. 重新安装 Node.js（选择 "Add to PATH" 选项）
3. 安装后重启终端（关闭并重新打开）
4. 如果仍不行，手动将 Node.js 路径添加到系统环境变量 PATH

**问题**（macOS）：`zsh: command not found: node`

**解决**：
1. 如果用 Homebrew 安装：`brew install node`
2. 如果用 nvm 安装但找不到：运行 `source ~/.nvm/nvm.sh` 或将其加入 `~/.zshrc`
3. 安装后**重启终端**

## 15. PowerShell curl 别名冲突

**问题**（Windows）：运行 `curl` 实际调用的是 PowerShell 的 `Invoke-WebRequest` 别名，参数不兼容。

**解决**：
- 方案 1：使用完整路径 `C:\Windows\System32\curl.exe`（Windows 10+ 自带）
- 方案 2：用 `Invoke-WebRequest` 的 PowerShell 语法（见 troubleshooting.md）
- 方案 3：安装 Git Bash 后使用其自带的 curl

## 16. 聚合模式工具名冲突

**问题**：多个上游返回同名工具，导致调用路由错误。

**解决**：聚合模板中已处理——遇到同名工具时保留第一个出现的。如果需要特定上游的工具，调整 `UPSTREAMS` 数组顺序。

## 17. ChatGPT 插件不调用工具

**问题**：插件已创建，但 ChatGPT 对话中不调用工具。

**解决**：
1. 确认插件状态为"已启用"（插件列表中有开关）
2. 在对话中 `@` 插件名称
3. 明确要求使用工具（如"用 XX 搜索..."）
4. 检查 `tools/list` 是否返回了工具（测试 3）

## 18. 上游 Token 过期

**问题**：之前能用的服务突然返回错误。

**原因**：上游平台的 Token 可能有时效性。

**解决**：
1. 到上游平台重新获取 Token
2. 更新 Secret（**跨平台命令**）：
   ```bash
   # 推荐方式：交互式输入（跨平台）
   npx wrangler secret put UPSTREAM_TOKEN

   # macOS / Linux
   echo "新Token" | npx wrangler secret put UPSTREAM_TOKEN

   # Windows PowerShell（⚠️ 不要用 echo 带引号）
   "新Token" | npx wrangler secret put UPSTREAM_TOKEN
   ```
3. 等 10 秒后重试

---

## 对抗式审查新增（#19-#28）

## 19. 上游请求无超时导致 Worker 挂起

**问题**：代理模式或聚合模式下，如果上游 MCP 服务器无响应，Worker 请求会一直挂起，直到 Cloudflare Workers 的全局超时（30 秒/50 秒，视计划而定）才返回错误。

**原因**：`fetch()` 默认没有超时机制。

**解决**：模板已修复，使用 `AbortController` 设置超时：
```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 秒超时
try {
  const res = await fetch(url, { ...init, signal: controller.signal });
} catch (e) {
  // 超时或连接失败，返回 504
} finally {
  clearTimeout(timeoutId);
}
```

**影响模板**：proxy（15 秒）、aggregator（10 秒/上游）。

## 20. 聚合模式缓存永不过期

**问题**：聚合模式的 `toolCache` 是模块级全局变量，在 Worker 实例存活期间永不刷新。如果上游新增或删除了工具，缓存不会更新，导致新工具不可用或旧工具调用失败。

**原因**：缓存没有 TTL（生存时间）机制。

**解决**：模板已修复，添加 5 分钟 TTL：
```typescript
let toolCache: Map<string, number> | null = null;
let toolCacheTime = 0;

async function getToolMap(env: Env): Promise<Map<string, number>> {
  const now = Date.now();
  if (toolCache && (now - toolCacheTime) < 5 * 60 * 1000) return toolCache;
  // ... 重新查询上游 ...
  toolCache = map;
  toolCacheTime = Date.now();
  return map;
}
```

## 21. 聚合模式 JSON-RPC ID 为浮点数

**问题**：旧代码用 `Date.now() + Math.random()` 生成 JSON-RPC ID，结果是浮点数（如 `1709876543210.123`）。部分上游 MCP 服务器期望整数 ID，可能拒绝或错误处理浮点 ID。

**原因**：`Math.random()` 返回 0-1 之间的小数。

**解决**：模板已修复，改用递增整数计数器：
```typescript
let rpcIdCounter = 0;
function nextRpcId(): number {
  rpcIdCounter = (rpcIdCounter + 1) % Number.MAX_SAFE_INTEGER;
  return rpcIdCounter;
}
```

## 22. 占位符 URL 未修改导致静默失败

**问题**：用户复制模板后忘记修改 `API_BASE_URL`（模式 A）或 `UPSTREAM_URL`（模式 B）或 `UPSTREAMS` 数组（模式 C），部署后调用时上游返回 404 或 DNS 解析失败，但没有明确的错误提示。

**原因**：模板中 `example.com` 是占位符域名，实际不存在。

**解决**：模板已修复，在处理 MCP 请求前检查是否包含 `example.com`：
```typescript
if (API_BASE_URL.includes("example.com")) {
  return new Response(
    JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32603, message: "API_BASE_URL is not configured..." } }),
    { status: 500, headers: { "Content-Type": "application/json" } },
  );
}
```

> 测试 3（工具列表）会立即暴露此问题，返回明确的错误消息而非静默失败。

## 23. Worker 名称不符合命名规则

**问题**：部署时报错：
```
Error: Worker name "My_MCP" is invalid. Names must be 1-63 characters, lowercase, alphanumeric, with hyphens.
```

**原因**：Cloudflare Worker 名称有严格限制。

**解决**：名称规则：
- 1-63 个字符
- 仅小写字母、数字、连字符（`-`）
- 不能以连字符开头或结尾
- 不能包含下划线（`_`）、大写字母、空格

**合法示例**：`my-mcp`、`pkulaw-mcp`、`my-mcp-v2`
**非法示例**：`My_MCP`、`my.mcp`、`-my-mcp`、`my-mcp-`

## 24. 旧 URL Token 兼容方式的编码与泄漏风险

**问题**：设置了含特殊字符的 `MCP_AUTH_TOKEN`（如 `sk-test&abc`），ChatGPT 调用时 URL 被截断，鉴权失败返回 401。

**原因**：Token 通过 URL 参数传递（`?token=xxx`），以下字符会破坏 URL 解析：
- `&` — 截断参数（最常见）
- `=` — 干扰键值对解析
- `#` — 截断 URL（fragment 标识符）
- `+` — 被解析为空格
- `空格` — 截断 URL
- `%` — 干扰 URL 编码
- `/` — 干扰路径解析
- `?` — 干扰查询参数开始
- `@` — 干扰 URL 权限段

**解决**：优先迁移到 Bearer；公开插件迁移到 OAuth 2.1。必须维持旧私人 URL token 时，使用高强度 URL-safe 随机值并正确编码，禁止公开分享完整 URL。

> 即使完成 URL 编码，查询参数仍可能进入日志和历史记录，因此只能作为旧私人连接的临时兼容方案。

## 25. macOS Homebrew 安装的 Node.js 全局包权限问题

**问题**（macOS）：用 Homebrew 安装 Node.js 后，全局安装 npm 包时报错：
```
EACCES: permission denied, access '/usr/local/lib/node_modules'
```

**原因**：Homebrew 安装的 Node.js 全局目录归 root 所有。

**解决**：
- 方案 1（推荐）：用 nvm 安装 Node.js，避免权限问题
  ```bash
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  source ~/.zshrc  # 或重启终端
  nvm install --lts
  ```
- 方案 2：修改 npm 全局目录到用户目录
  ```bash
  mkdir ~/.npm-global
  npm config set prefix '~/.npm-global'
  echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.zshrc
  source ~/.zshrc
  ```
- 方案 3：用 `sudo`（不推荐，可能导致后续权限混乱）

## 26. PowerShell 执行策略限制（已移除独立脚本）

> **已优化**：独立验证脚本 `verify.ps1` 已移除，验证命令直接内嵌在 `references/templates.md` 中。用户无需运行脚本，直接复制命令到终端即可。

**历史问题**（Windows）：运行 `.ps1` 脚本时报错：
```
File C:\...\verify.ps1 cannot be loaded because running scripts is disabled on this system.
```

**历史原因**：Windows 默认禁止运行 PowerShell 脚本（执行策略为 Restricted）。

**当前方案**：使用 `references/templates.md` 中的内联命令，无需脚本文件，不受执行策略限制。如果仍需运行 `.ps1` 脚本：
- 方案 1（临时）：运行时加 `-ExecutionPolicy Bypass`
- 方案 2（永久）：`Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`

## 27. macOS zsh 与 bash 差异（已移除独立脚本）

> **已优化**：独立验证脚本 `verify.sh` 已移除，验证命令直接内嵌在 `references/templates.md` 中。

**历史问题**（macOS）：`verify.sh` 在 macOS 默认终端中运行异常，`echo -e` 不识别颜色代码。

**历史原因**：macOS Catalina+ 默认 Shell 是 zsh，zsh 的 `echo` 不支持 `-e` 参数。

**当前方案**：使用 `references/templates.md` 中的 curl 命令（macOS 自带 curl，无兼容性问题）。

## 28. Cloudflare Workers 免费额度耗尽

**问题**：Worker 突然返回 1000+ 错误码，日志显示：
```
Worker exceeded daily limit of 100000 requests
```

**历史原因**：当时使用的 Cloudflare 免费计划额度耗尽。套餐和额度会变化；聚合模式每次 tools/list 触发 N 个上游请求，仍可能显著放大用量。

**解决**：
- 方案 1：在 Cloudflare 控制台确认当前套餐、额度和重置时间
- 方案 2：根据当前官方价格评估升级，不使用本历史记录中的旧价格
- 方案 3：减少不必要的请求：
  - 聚合模式缓存已验证的目录与映射，不在每次 `tools/call` 前查询全部 `tools/list`
  - 在 ChatGPT 中禁用不常用的插件，减少自动调用

---

## 有状态上游 MCP 实战新增（#29-#32）

> 来源：把一个含多个端点的**有状态**第三方 MCP 平台用聚合模式接入 ChatGPT 的脱敏实战。此前测试的若干上游是无状态服务，因此旧模板没有暴露 session 问题。

## 29. 有状态上游 MCP 必须管 session（最重要）

**问题**：用代理（模式 B）或聚合（模式 C）接某个上游 MCP 时，ChatGPT 连接失败，或 `tools/list` 返回空、工具调用报 `400 Bad Request: Missing session ID`。但换成无状态上游时正常。

**原因**：上游是**有状态的 Streamable HTTP** 服务器。`initialize` 时它在**响应头**里返回 `mcp-session-id`，之后所有请求（`notifications/initialized`、`tools/list`、`tools/call`）都必须带这个 header，否则返回 `400 Missing session ID`。而：
- 模式 B 代理只透传 `Content-Type`/`Accept`/`Authorization` 三个头，**漏转了 `mcp-session-id`**；
- 模式 C 的 `callUpstream` 直接 POST，**压根不做 initialize 握手**，自然没有 session。

无状态上游不需要 session，所以表现为「唯独这个上游不行」。

**判断方法**：直接 curl 上游 `initialize`，看响应头有没有 `mcp-session-id`；再**不带** session 调 `tools/list`，若返回 `400 Missing session ID` 即是有状态上游。

**解决**：为每个上游维持独立 session——`initialize` 取 `mcp-session-id` → 带 session 发
无 id 的 `notifications/initialized` → 带 session 发真正调用；session 失效时最多重建一次。
Worker 内存不是持久存储，冷启动后必须能重新 initialize。模式 B 透传客户端 session；模式 C
根据实测上游生成完整 session 管理，见 [templates.md](templates.md) 的当前门槛。不要复制旧版
硬编码协议版本、读取完整 SSE 文本或给 notification 添加 JSON-RPC id 的历史代码。

> 模式 B（单上游透明代理）更简单的修法：把客户端带来的 `mcp-session-id` 头**原样转发**给上游即可（见 templates.md 模式 B）。

## 30. curl 能连但 ChatGPT「连接失败」（手搓服务的协议偏差）

**问题**：Worker 用 curl 测 `initialize`、`tools/list` 都返回 200，但 ChatGPT 创建插件时始终「连接失败」。本技能的标准模板（模式 A 的 `createMcpHandler`、修正后的 B/C）没这问题，**只有手搓 / 让别的 AI 随意改写后的服务容易踩**。

**原因**：curl 不挑协议细节，ChatGPT 的 MCP 客户端更严格。手搓服务常见偏差（可逐项对照排查）：
- 响应用纯 `application/json`，而非 SSE 帧（`text/event-stream`）
- `initialize` 硬编码返回过旧的协议版本（如 `2024-11-05`）
- 没实现 `ping`（返回 `-32601`）
- 没处理 `notifications/initialized`（应回 `202`）
- 上游有状态却没管 session（见 #29，会导致工具列表为空）

**解决**：优先复用模板，别手搓。若必须手写 `/mcp`：
1. 客户端 `Accept` 含 `text/event-stream` 时，响应回 SSE 帧（响应头 `Content-Type: text/event-stream`）：
   ```
   event: message
   data: {"jsonrpc":"2.0","id":1,"result":{...}}

   ```
2. `initialize` 按当前 SDK/规范协商协议版本，不无理由硬编码单一旧版本
3. 实现 `ping` 返回 `{}`；`notifications/*` 返回 `202`
4. 有状态上游按 #29 管 session

## 31. /sse 与 /mcp 是两种不同传输，别混淆

**问题**：看到上游同时提供 `/mcp` 和 `/sse` 两种 URL，以为「要 SSE 就把 URL 末尾的 `mcp` 改成 `sse`」。

**原因**：`/sse` 是旧的 **legacy HTTP+SSE** 传输（`GET /sse` 开流 + `POST /messages` 发消息，两段式）；`/mcp` 是新的 **Streamable HTTP** 传输（单端点）。是两套不同协议，不是同一服务换个路径。ChatGPT 按本技能用的是 `/mcp` Streamable HTTP。「需要 SSE」指的是 `/mcp` 的**响应帧格式**要是 `text/event-stream`，**不是**改 URL 路径。

> 另外，有些上游文档里写了 `/sse` 端点，实际可能未开通（返回 404），以实测为准。

## 32. Windows 上 Wrangler 报钥匙串错误

**问题**（Windows）：`npx wrangler whoami` / `deploy` 报：
```
@napi-rs/keyring is required for OS keyring storage on Windows but is not installed.
```

**原因**：wrangler 4.x 在 Windows 用系统钥匙串存登录凭据，缺 `@napi-rs/keyring` 就读不到已登录态。

**解决**：升级 Wrangler、重新登录并按 Cloudflare 当前官方文档检查 Windows 凭证存储。自动化环境可使用最小权限的 `CLOUDFLARE_API_TOKEN` 环境变量，令牌不得写入源码、命令历史或公开日志。本公开技能不要求安装其他插件。
