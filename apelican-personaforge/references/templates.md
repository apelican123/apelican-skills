# Cloudflare 实现模板

代码生成前先查看 Cloudflare 当前示例与所选 SDK 的类型，避免把过期包名写死：

- https://developers.cloudflare.com/agents/model-context-protocol/guides/remote-mcp-server/
- https://developers.cloudflare.com/workers/best-practices/workers-best-practices/

## 公共配置

```toml
name = "my-mcp"
main = "src/index.ts"
compatibility_date = "YYYY-MM-DD"
compatibility_flags = ["nodejs_compat"]

[observability]
enabled = true
```

日期不能晚于 Cloudflare 已发布的日期。密钥使用 `wrangler secret put`，不写入本文件。

专属能力 URL 会把 Token 放进请求路径。此模式关闭会记录完整路径的 invocation logs/traces；保留必要的脱敏应用日志：

```toml
[observability.logs]
enabled = true
invocation_logs = false

[observability.traces]
enabled = false
```

## A. REST 翻译为 MCP

无持久状态时使用当前 `McpServer` + Cloudflare `createMcpHandler`，不要新建旧 `McpAgent`。

```ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { createMcpHandler } from "agents/mcp"; // 以当前官方导出为准
import { z } from "zod";

interface Env { API_KEY: string; [binding: string]: string | undefined }

function createServer(env: Env) {
  const server = new McpServer(
    { name: "documents-mcp", version: "1.0.0" },
    { instructions: "Search before fetch when the ID is unknown. This server is read-only." }
  );

  server.registerTool("search_documents", {
    title: "Search documents",
    description: "Search connected documents. Use before fetch when the ID is unknown. Do not use for web search.",
    inputSchema: z.object({
      query: z.string().min(1).max(500).describe("Natural-language search query"),
      limit: z.number().int().min(1).max(20).default(10),
    }),
    outputSchema: z.object({
      results: z.array(z.object({ id: z.string(), title: z.string(), url: z.string() })),
    }),
    annotations: {
      readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true,
    },
  }, async ({ query, limit }) => {
    const data = await boundedApiCall(env, query, limit);
    const structuredContent = { results: data.results };
    return {
      structuredContent,
      content: [{ type: "text", text: JSON.stringify(structuredContent) }],
    };
  });
  return server;
}
```

`boundedApiCall` 必须：HTTPS、认证头、`AbortController` 超时、`response.ok` 检查、有界读取、字段白名单和错误脱敏。

入口先检查路径与认证，再调用 handler：

```ts
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext) {
    const url = new URL(request.url);
    if (url.pathname !== "/mcp") return new Response("Not found", { status: 404 });
    if (!(await authorized(request, env))) return new Response("Unauthorized", { status: 401 });
    return createMcpHandler(() => createServer(env))(request, env, ctx);
  },
};
```

不同 SDK 版本的构造器和 handler 导出可能变化；以安装版本类型和 Cloudflare 当前示例为准，并用真实 `tools/list` 检查 schema 可序列化。

## B. 单 MCP 透明代理

原则：

- 不解析时直接流式透传 `Response.body`；
- 只复制必要头，客户端凭证不转给上游；
- 注入上游 Secret；
- 透传上下行 `mcp-session-id`；
- 使用超时，但不要在超时前把未知大 SSE 全部读入内存；
- 若要改 metadata，先有界读取，再重建响应，且保留 JSON/SSE 语义。

核心转发：

```ts
const headers = new Headers({
  "content-type": request.headers.get("content-type") ?? "application/json",
  accept: request.headers.get("accept") ?? "application/json, text/event-stream",
  authorization: `Bearer ${env.UPSTREAM_TOKEN}`,
});
const sid = request.headers.get("mcp-session-id");
if (sid) headers.set("mcp-session-id", sid);

const upstream = await fetch(UPSTREAM_URL, {
  method: request.method,
  headers,
  body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
  signal: AbortSignal.timeout(30_000),
});
return new Response(upstream.body, { status: upstream.status, headers: upstream.headers });
```

如果上游工具缺 title/annotations/outputSchema，代理可在 `initialize` 和 `tools/list` 上做小型兼容层；禁止猜测副作用。

## C. 多 MCP / 巨型 API 编排

默认不把几百上千工具直接交给模型。优先注册：

1. `search_tools(query, platform?, limit?)`：只返回准确候选的 name/description/input_schema；
2. `execute_read_tool(name, arguments)`：只允许 allowlist 或经严格分类的只读工具；
3. 少量高价值写工具：逐个注册，准确注解并要求确认。

实现要求：

- 各上游独立 session；
- 工具目录缓存 5 分钟左右并支持主动刷新；
- 枚举并发 4–8，按上游容量调节；
- 名称冲突显式前缀或映射；
- search 必须真正按名称/平台/描述评分，零匹配返回空，不用目录头部兜底；
- 执行器在调用前再次核对工具存在、输入 schema 和读写分类；
- 写类正则只能作为额外拒绝层，不能代替 allowlist；
- session 失效仅重建一次；
- 不在每次 call 前重新枚举所有上游。

建议的写类拒绝词仅用于 defense in depth：

```ts
const WRITE_LIKE = /(^|_)(create|add|update|edit|delete|remove|send|post|publish|upload|comment|like|follow|unfollow|favorite|order|pay)(_|$)/i;
```

## 一人一条专属能力 URL（私人使用默认）

生成器见 `scripts/create-user-link.js`。它用用户名生成稳定的 `userId` 标签，同时为每次链接生成至少 32 个随机字节；用户名不参与 Token 推导。Cloudflare Secret 只保存 Token 的 SHA-256 摘要：

```text
URL:    /u/<userId>/<43字符base64url Token>/mcp
Secret: MCP_USER_<USER_ID>_TOKEN_SHA256=<64字符SHA-256摘要>
```

少量可信用户共用 Worker 时，按 URL 中的 `userId` 选择各自的 Secret。A 的 Token 放到 B 的路径时，Worker 会读取 B 的摘要并拒绝：

```ts
type CapabilityEnv = Record<string, string | undefined>;

async function sha256Hex(value: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function equalHex(left: string, right: string) {
  if (!/^[a-f0-9]{64}$/iu.test(left) || !/^[a-f0-9]{64}$/iu.test(right)) return false;
  const a = left.toLowerCase();
  const b = right.toLowerCase();
  let diff = 0;
  for (let i = 0; i < 64; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function secretBinding(userId: string) {
  return `MCP_USER_${userId.replace(/-/gu, "_").toUpperCase()}_TOKEN_SHA256`;
}

async function capabilityUser(pathname: string, env: CapabilityEnv) {
  const match = /^\/u\/([a-z0-9][a-z0-9-]{1,62})\/([A-Za-z0-9_-]{43})\/mcp$/u.exec(pathname);
  if (!match) return null;
  const [, userId, token] = match;
  const expectedHash = env[secretBinding(userId)];
  if (!expectedHash) return null;
  const suppliedHash = await sha256Hex(token);
  return equalHex(suppliedHash, expectedHash) ? userId : null;
}
```

入口在调用 MCP handler 前完成校验，并把 `userId` 传给后续上游凭据/scope 映射：

```ts
export default {
  async fetch(request: Request, env: CapabilityEnv, ctx: ExecutionContext) {
    const url = new URL(request.url);
    const userId = await capabilityUser(url.pathname, env);
    if (!userId) return new Response("Not found", { status: 404 });

    // 如果上游数据按用户隔离，在这里根据 userId 选择该用户自己的凭据或 scope。
    return createMcpHandler(() => createServer(env, userId))(request, env, ctx);
  },
};
```

不要把所有用户链接映射到同一个能读取全部数据的上游管理员凭据。每位用户最好独立部署；共用 Worker 仅用于少量人工管理的可信用户。大量用户、独立账号/scope 或公开审核使用 OAuth 2.1。

只有校验通过才把请求交给 MCP handler；错误用户名、错误 Token 或缺少 Secret 返回 401/403/404。完整 URL 只交付一次，不写进源码、Git、日志、示例或公开材料。ChatGPT 表单选择“无身份验证”；固定 `/mcp` 不得直接匿名开放私人能力。

## 私人 Bearer 认证

仅适用于支持自定义 Authorization header 的私人客户端。ChatGPT 单人自用默认优先专属能力 URL；公开发布改用 OAuth 2.1。

```ts
async function digest(value: string) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}

async function equalSecret(left: string, right: string) {
  const [a, b] = await Promise.all([digest(left), digest(right)]);
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

async function authorized(request: Request, env: { MCP_AUTH_TOKEN?: string; MCP_AUTH_TOKEN_PREVIOUS?: string }) {
  const configured = [env.MCP_AUTH_TOKEN, env.MCP_AUTH_TOKEN_PREVIOUS].filter(Boolean) as string[];
  if (!configured.length) return false;
  const auth = request.headers.get("authorization") ?? "";
  const supplied = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  if (!supplied) return false;
  for (const expected of configured) if (await equalSecret(supplied, expected)) return true;
  return false;
}
```

## 结果和大文档

- 列表限制条数并支持 cursor；
- 文档 fetch 设置字符/字节上限；
- 返回 `truncated`、`next_offset` 和单独的分块工具；
- 解析前检查 `content-length`，流读取时累计字节并在硬上限中止；
- 不把 base64 媒体塞进普通文本结果，使用资源/媒体内容块或可授权 URL。

## 禁止上线的占位项

- `example.com`、假 URL、空工具描述；
- 硬编码 token/API key；
- 所有工具一律 `readOnlyHint: true`；
- 输出声明了 schema 却不返回 structuredContent；
- 没有真实目标的万能代理工具；
- 只用 HTTP 200 判断成功。
