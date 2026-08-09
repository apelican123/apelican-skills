# 零基础部署：从 0 到可调用

按顺序执行，不跳步。命令默认在新建的项目目录中运行。每一步都包含验证门：
只有看到预期结果才进入下一步；失败时先按 [troubleshooting.md](troubleshooting.md)
排查，不要靠“部署似乎成功”跳过证据。

## 目录

- 目标与模式：第 1–2 步
- 环境与账号：第 3–4 步
- 项目、文件和依赖：第 5–8 步
- Secret 与部署：第 9–10 步
- 认证和协议回归：第 11–13 步
- ChatGPT、多设备与回滚：第 14–15 步
- 最后执行“模式专属验证”

## 第 1 步：决定目标

先回答：

- 只给自己/团队开发使用：选择私人连接。
- 要提交公开插件：从一开始就规划 OAuth 2.1，不使用共享 URL token 作为正式认证。
- 数据只在本机/内网：选择 OpenAI Secure MCP Tunnel，跳到 [local-tunnel-deploy.md](local-tunnel-deploy.md)。
- 需要 24 小时在线：选择 Cloudflare Workers，继续下文。

**验证门 1**：写下 `私人/公开`、`Worker/Tunnel` 两个选择以及原因。预期只有一条
主部署路径；若两者都选，必须说明它们服务于不同环境，不能把 Tunnel 当公开生产入口。

## 第 2 步：判断上游模式

| 你手里的东西 | 模式 |
|---|---|
| REST 文档、API URL、API Key | A 翻译 |
| 一个 MCP URL | B 代理 |
| 多个 MCP URL 或巨大工具目录 | C 编排 |

准备一张不含密钥值的清单：端点、认证头名称、工具/接口、读写行为、分页、限流和预期结果。

**验证门 2**：对照上表能唯一选出 A/B/C，并用无副作用请求验证上游真实类型。
模式 B/C 至少取得 initialize 和 tools/list；若拿不到，停止生成代理代码并先修上游连接。

## 第 3 步：安装基础软件

需要 Node.js 当前 LTS（建议 20+）和 npm。

检查：

```powershell
# Windows PowerShell
node --version
npm --version
```

```bash
# macOS / Linux
node --version
npm --version
```

没有命令时，从 https://nodejs.org 下载 LTS。安装后关闭并重新打开终端，再检查一次。

**验证门 3**：`node --version` 与 `npm --version` 都以状态码 0 结束，Node 满足当前
Cloudflare/依赖要求。只看到安装程序完成不算通过；必须在新终端重新运行命令。

## 第 4 步：登录 Cloudflare

先注册 https://dash.cloudflare.com ，再运行：

```powershell
npx wrangler@latest login
npx wrangler@latest whoami
```

```bash
npx wrangler@latest login
npx wrangler@latest whoami
```

浏览器出现授权页面时点击允许。`whoami` 能显示账号信息才继续。

**验证门 4**：`whoami` 显示预期 Cloudflare 账号；若有多个账号，核对将要部署的
Account ID/名称，但不要把完整 ID 写进公开技能或聊天记录。

## 第 5 步：创建项目

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Path my-mcp, my-mcp\src -Force
Set-Location my-mcp
```

macOS/Linux：

```bash
mkdir -p my-mcp/src
cd my-mcp
```

确认当前目录：

```powershell
Get-Location
```

```bash
pwd
```

**验证门 5**：当前目录的最后一级是 `my-mcp`，且 `src` 存在。Windows：
`Test-Path .\src`；macOS/Linux：`test -d ./src`。任一失败都先纠正目录。

## 第 6 步：创建四个文件

从 [templates.md](templates.md) 选择 A/B/C，在当前 `my-mcp` 目录创建：

```text
my-mcp/
├── package.json
├── tsconfig.json
├── wrangler.jsonc
└── src/
    └── index.ts
```

必须替换的占位项：

- `my-mcp`：你的 Worker 名称，小写字母/数字/连字符；
- `API_BASE_URL` 或 `UPSTREAM_URL(S)`；
- Secret 名称必须与代码中的 `env.XXX` 一致；
- 示例工具名称、description、input/output schema；
- server name、version、instructions。

不要把真实密钥写进任何文件。

组装 `src/index.ts` 时：

- 模式 A：复制“公共安全函数”＋“模式 A”代码，并保留其 import；
- 模式 B：复制“公共安全函数”＋“模式 B”代码；
- 模式 C：先实测所有上游，再让本技能按“模式 C”门槛生成完整文件；不得只复制规则列表就部署；
- 同一个函数只保留一份，不能同时混入 A/B 两个 `export default`。

**验证门 6**：四个文件均存在，并扫描尚未替换的占位符。

```powershell
Get-ChildItem package.json,tsconfig.json,wrangler.jsonc,src\index.ts
Get-ChildItem -Recurse -File | Select-String -Pattern 'example\.com|YYYY-MM-DD|<your-|tunnel_xxx'
```

```bash
test -f package.json && test -f tsconfig.json && test -f wrangler.jsonc && test -f src/index.ts
grep -RInE 'example\.com|YYYY-MM-DD|<your-|tunnel_xxx' . --exclude-dir=node_modules
```

预期四个文件存在，生产构建前占位符扫描无结果。示例代码尚未改完时允许有结果，但不得进入部署。

## 第 7 步：安装依赖

使用模板中的 `package.json`：

```powershell
npm install
```

```bash
npm install
```

若 npm 报 peer dependency 冲突，先核对当前官方包版本；只有确认是已知兼容冲突时才使用：

```bash
npm install --legacy-peer-deps
```

不要把它当默认修复。

**验证门 7**：`npm install` 状态码为 0，随后运行 `npm ls --depth=0`；预期没有
`UNMET DEPENDENCY`。不要仅凭生成了 `node_modules` 判断成功。

## 第 8 步：本地检查

```powershell
npx tsc --noEmit
npx wrangler@latest deploy --dry-run
```

```bash
npx tsc --noEmit
npx wrangler@latest deploy --dry-run
```

有错误先修复，不要带错部署。重点检查：占位 URL、包导入、schema、未来 compatibility date。

**验证门 8**：两条命令状态码均为 0；dry-run 输出包含 Worker 入口和预计上传内容，
但没有真实部署。再运行占位符扫描，必须无结果。

## 第 9 步：设置 Secret

交互输入最安全，值不会写入命令历史：

模式 A：

```bash
npx wrangler@latest secret put API_KEY
npx wrangler@latest secret put MCP_AUTH_TOKEN
```

模式 B/C：

```bash
npx wrangler@latest secret put UPSTREAM_TOKEN
npx wrangler@latest secret put MCP_AUTH_TOKEN
```

若上游需要多个凭证，逐个设置。确认名称：

```bash
npx wrangler@latest secret list
```

私人连接的 MCP_AUTH_TOKEN 使用密码管理器生成的高强度随机值。公开发布应改为 OAuth 2.1。

若必须兼容旧客户端的 URL token，再设置普通环境变量
`ALLOW_LEGACY_QUERY_TOKEN=true`；模板随后同时接受 Bearer 和
`?token=` / `?access_token=` / `?api_key=`。能发送 Header 的客户端不要开启。
需要兼容 `X-API-Key` / `X-MCP-Token` 时设置 `ALLOW_API_KEY_HEADER=true`。
这些是兼容选项，不是额外插件。

注意：`MCP_AUTH_TOKEN` 是“客户端访问你的 Worker”的入口凭证；
`UPSTREAM_TOKEN` 是“Worker 访问原服务”的凭证。两者不能复用。

**验证门 9**：`secret list` 只显示名称且包含当前模式所需项；代码中的每个
`env.XXX` 都能在 [templates.md](templates.md) 的变量表中找到。不得打印 Secret 值验证。

## 第 10 步：首次部署

```powershell
npx wrangler@latest deploy --keep-vars
```

```bash
npx wrangler@latest deploy --keep-vars
```

记录输出的 HTTPS URL 与 Version ID。不要把含 token 的 URL贴到公开 issue、截图或文档。

**验证门 10**：部署命令状态码为 0；访问 `/health` 返回 `status: ok`；
`npx wrangler@latest deployments status` 能看到刚才的部署。只有 URL、没有部署记录不算通过。

## 第 11 步：验证未认证请求

把 URL 改成自己的完整 `/mcp` 地址。

Windows PowerShell：

```powershell
$McpUrl = "https://my-mcp.<your-subdomain>.workers.dev/mcp"
$Init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}'
try {
  (Invoke-WebRequest $McpUrl -Method Post -ContentType "application/json" -Headers @{Accept="application/json, text/event-stream"} -Body $Init).StatusCode
} catch {
  [int]$_.Exception.Response.StatusCode
}
```

期望 `401` 或 `403`。

macOS/Linux：

```bash
MCP_URL="https://my-mcp.<your-subdomain>.workers.dev/mcp"
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$MCP_URL" \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}'
```

**验证门 11**：无凭证和随机错误凭证都必须是 401/403；若任一得到 MCP 数据，立即停止，
不要连接 ChatGPT。`/health` 可公开，但不得返回工具、上游 URL 或 Secret 名称。

## 第 12 步：验证正确认证

把 token 只放进当前终端变量。

Windows PowerShell：

```powershell
$Token = Read-Host "MCP token"
$Headers = @{Accept="application/json, text/event-stream";Authorization="Bearer $Token"}
$Response = Invoke-WebRequest $McpUrl -Method Post -ContentType "application/json" -Headers $Headers -Body $Init
$Response.StatusCode
$Response.Content
```

macOS/Linux：

```bash
read -s MCP_TOKEN
curl -s -X POST "$MCP_URL" \
  -H "authorization: Bearer $MCP_TOKEN" \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}'
```

确认：HTTP 200、没有 JSON-RPC error、有 serverInfo 与 instructions。

如果开启了旧 URL token 兼容，还要用同一个 initialize 请求测试一次：

```powershell
$LegacyUrl = "$McpUrl?token=$Token"
Invoke-WebRequest $LegacyUrl -Method Post -ContentType "application/json" `
  -Headers @{Accept="application/json, text/event-stream"} -Body $Init
```

```bash
INIT_JSON='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}'
curl -s -X POST "$MCP_URL?token=$MCP_TOKEN" \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  --data "$INIT_JSON"
```

随后分别验证 `tools/list`、`tools/call`；不能只验证 initialize。若连接完全迁移到
Bearer，再删除 `ALLOW_LEGACY_QUERY_TOKEN` 并重新部署。

**验证门 12**：正确 Bearer 返回成功；错误 Bearer 失败；启用哪一种兼容载体，就逐一
验证哪一种。若设置了 `MCP_AUTH_TOKEN_PREVIOUS`，新旧 token 暂时都成功；删除旧 Secret
并重新部署后，旧 token 必须失败。

## 第 13 步：枚举并真实调用

将请求 method 改为 `tools/list`，确认每个工具都有 name/title/description/inputSchema/annotations。然后选一个明确无副作用的工具发 `tools/call`，检查 JSON-RPC error、result.isError 和 structuredContent。

完整检查表见 [validation-and-release.md](validation-and-release.md)。

推荐同时打开 Inspector：

```bash
npx @modelcontextprotocol/inspector@latest
```

**验证门 13**：initialize、initialized、ping、tools/list 全部成功；工具数量符合预期；
每个只读工具至少有一个正常 fixture；业务失败要体现为 `result.isError=true`，不能只看 HTTP 200。

## 第 14 步：连接 ChatGPT

根据当前 OpenAI 界面创建 Developer mode MCP 连接，填稳定 Server URL 或选择 Tunnel。界面与可用套餐可能变化，按 [chatgpt-setup.md](chatgpt-setup.md) 和 OpenAI 当前官方文档操作。

创建后核对工具数量，并在对话中完成一次真实调用。能创建连接不等于已通过公开插件审核。

**验证门 14**：ChatGPT 显示的工具数量与 Inspector 一致，并能在明确应调用的提示下
调用正确工具。再用一个“何时不该调用”的提示验证不会误选。若需要多设备使用，按
[cross-device-use.md](cross-device-use.md) 在第二台设备或第二个客户端做只读回归。

## 第 15 步：保存回滚信息

```bash
npx wrangler@latest deployments status
npx wrangler@latest versions list
```

记录当前和上一个可用 version ID。后续修改继续遵循 dry-run、部署、生产回归、失败回滚。

**验证门 15**：发布记录至少包含 Worker 名、生产 URL、当前与上一 version ID、时间、
auth/init/list/call 结果和回滚命令。不要为了测试回滚而破坏正常生产；在真实故障或隔离环境中
验证回滚后，必须再次运行 auth/init/list/call。

## 模式专属验证，不可省略

| 模式 | 发布前必须额外证明 |
|---|---|
| A 翻译 | 用原始 REST 请求和 MCP 工具请求查询同一条数据，关键字段一致；GET/POST、Header 名和分页与上游文档一致 |
| B 代理 | 上游与代理的工具数量、名称和只读调用结果一致；SSE 不被缓冲；session header 能往返；客户端凭证不出现在上游请求 |
| C 编排 | 每个上游单独 init/list/call；同名工具映射明确；目录缓存和并发有界；只读 allowlist 拒绝写类工具；单个上游故障可定位 |

任何一项缺证据，只能报告“部署准备完成”或具体缺口，不能报告“已验证可用”。
