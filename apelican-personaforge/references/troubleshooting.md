# 故障排查

先判断失败层级：环境 → Cloudflare → 认证 → MCP 协议 → 上游 → ChatGPT。

## 目录

- 环境与命令：Node/npm、curl/PowerShell、Wrangler、代理、Windows 文件锁
- 部署与配置：dry-run、Worker 名称、Secret、占位符
- MCP 协议：initialize、tools/list、HTTP 200 内错误、session、SSE
- 认证：私人入口兼容、上游 401/403、凭证分层
- 模式 C：空目录、同名工具、部分上游失败
- ChatGPT 与设备：模型误选、连接失败、移动/第二设备、套餐与审核
- 日志：脱敏 tail 与停止调试

## Node/npm 不存在

从 https://nodejs.org 安装当前 LTS，关闭并重开终端：

```bash
node --version
npm --version
```

不要通过关闭 TypeScript strict 来掩盖依赖或类型错误。

## Wrangler 登录失败

```bash
npx wrangler@latest login
npx wrangler@latest whoami
```

浏览器未打开时复制终端授权 URL。代理网络下检查 HTTPS_PROXY，但不要把代理凭证写进仓库。

## dry-run 或部署失败

依次检查：

- Worker 名称仅小写字母、数字、连字符；
- compatibility_date 不是未来日期；
- package import 与安装版本一致；
- `wrangler.jsonc` 是合法 JSONC；
- 当前目录确实包含配置和 src/index.ts；
- Windows 文件被锁时，先关闭占用进程，再删除项目内 `.wrangler` 临时目录。

## Secret 设置后仍 401

1. `npx wrangler@latest secret list` 检查名称；
2. 名称必须与 `env.API_KEY` 等字段完全一致；
3. 重新交互设置，避免命令历史；
4. 等待边缘传播；
5. 检查代码是否 fail closed 且读取了正确 header；
6. 不打印 secret 值排错。

## initialize 失败

- Accept 同时包含 JSON 和 text/event-stream；
- response 是合法 JSON 或 SSE `data:` 帧；
- serverInfo.name/version 存在；
- instructions 是字符串；
- 不强制客户端只能使用一个旧协议版本；
- ping 与 notifications/initialized 正常。

## tools/list 报 schema 错误

- inputSchema/outputSchema 根必须为 object；
- 不把原始 JSON Schema 传给只接受 Zod/Standard Schema 的 SDK API；
- 用当前 SDK 类型检查确认 registerTool/update 的参数形式；
- outputSchema 声明后，调用必须返回匹配的 structuredContent。

## HTTP 200 但调用失败

解析正文并检查：

- 顶层 `error`：JSON-RPC 失败；
- `result.isError`：工具业务失败；
- content 只有错误文本但没设 isError：修正工具实现；
- structuredContent 缺失或不匹配 schema。

## 上游 Missing session ID

initialize 响应头若有 `mcp-session-id`，initialized/list/call 都要回带。多个上游分别维护；session 失效只重建一次。

## 超时或内存错误

- 设置 AbortController 超时；
- 限制并发；
- 大响应流式透传；
- 需要解析时有界读取；
- 列表分页，文档分块；
- 不无限重试。

## GPT 不调用或选错工具

检查：

- server instructions 前 512 字符是否包含最关键选择规则；
- 工具 name 是否动作导向；
- title/description 是否说明“何时用/何时不用”；
- 相似工具是否太多；
- 参数是否要求模型填写内部信息；
- 是否应将巨大目录压缩成任务型工具。

## 能 curl 但 ChatGPT 连不上

curl 成功只说明 HTTP 可达。继续检查 SSE/JSON 语义、协议协商、ping、notification、session、工具 schema 与认证方式。优先复用当前 SDK/Cloudflare 官方 handler，不手搓不完整协议。

## Bearer 可用，但旧客户端仍然 401

先确认旧客户端是否只能把 token 放在 URL 或 `X-API-Key`。私人部署可分别开启
`ALLOW_LEGACY_QUERY_TOKEN=true` 或 `ALLOW_API_KEY_HEADER=true`，重新部署后用
initialize、tools/list 和 tools/call 三段请求验证。不要为了兼容而取消鉴权；公开
插件也不要把这些共享 token 路径当 OAuth 替代品。

## Worker 能认证，调用上游却是 401/403

这是两层认证混淆。`MCP_AUTH_TOKEN` 只验证客户端到 Worker；上游可能要求 Bearer、
自定义 API-Key Header、Basic、query token、OAuth access token、HMAC 或其他签名。
按上游文档选择适配器，并确认 Header 名称、前缀、scope、受众和过期时间。

## 查看日志

```bash
npx wrangler@latest tail
```

日志必须脱敏。排错完成后删除临时调试输出，不记录 Authorization、cookie、token 或私人正文。

## 没有 curl 或不熟悉命令行

Windows 使用 `Invoke-WebRequest`；macOS/Linux 使用 curl；也可运行：

```bash
npx @modelcontextprotocol/inspector@latest
```

Inspector 仍需正确 URL 和认证。看到界面不代表协议通过，必须完成 init/list/call。

## Node 太旧或命令不存在

安装当前 Node.js LTS 后关闭并重开终端。Windows 用 `Get-Command node,npm`，
macOS/Linux 用 `command -v node npm` 确认命令来自预期安装位置，再检查版本。

## Wrangler 命令不存在或浏览器登录无反应

优先使用 `npx wrangler@latest`，避免依赖全局安装。浏览器未打开时复制终端授权 URL；
完成后必须用 `whoami` 读回账号。公司代理/VPN 下先确认 HTTPS 访问，代理凭证不得写进项目。

## Windows 的 `.wrangler` 写入或锁定错误

确认当前目录有写权限并关闭仍占用项目的 dev/编辑器进程。只处理当前项目内的 `.wrangler`
临时目录，不删除用户目录、仓库根目录或其他项目缓存。重新 dry-run 后才继续。

## Worker 名称无效或已存在

名称使用小写字母、数字和连字符。名称已存在时先确认它是否属于本项目；不要为了通过部署
覆盖陌生 Worker。修改名称后重新核对 URL、Secret 目标和回滚记录。

## 上游 URL 或示例占位符未替换

部署前扫描 `example.com`、`YYYY-MM-DD`、`<your-`、`tunnel_xxx`。发现任何生产路径占位符
就停止；不要等 404/500 后再猜是哪一个文件漏改。

## tools/list 为空

按顺序验证上游自身 tools/list、工具是否在创建 server 时注册、schema 转换是否报错、
模式 C 的目录缓存是否把失败误记为空。空数组可以是真实结果，但必须有上游证据。

## 模式 C 某些工具缺失或同名

逐个上游单独列举工具，检查并发失败、session、分页、缓存 TTL 和名称冲突映射。
同名工具必须显式前缀或映射，不能“先到先得”静默覆盖。部分上游失败要返回可定位信息。

## SSE 看起来像乱码

`data:` 行是事件流帧，不是普通 JSON。透明代理应流式转发；命令行测试要解析事件帧，
或使用 Inspector。不要为了看起来整齐而对未知大 SSE 调用 `response.text()`。

## 手机或第二台设备看不到连接

核对账号、目标工作区、客户端版本、Developer mode/连接器权限和连接是否在当前界面受支持。
Cloudflare Worker 可跨设备访问；Tunnel 仍要求原主机在线。不要把上游 Secret 复制到第二设备。

## 额度、套餐或审核描述不一致

删除旧文章中的固定额度结论，查看当前 OpenAI 和 Cloudflare 官方页面及实际控制台。
私人连接、公开提交、审核通过、移动端可见是四个不同状态，不能互相推断。
