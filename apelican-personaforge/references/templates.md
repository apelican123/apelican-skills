# Cloudflare 模板

生成项目前先核对当前官方示例与安装版本类型：

- https://developers.cloudflare.com/agents/model-context-protocol/guides/remote-mcp-server/
- https://developers.cloudflare.com/workers/best-practices/workers-best-practices/

SDK 导出路径可能随版本变化。以下是结构模板；以当前官方文档和 TypeScript 类型为准，不盲目复制旧 import。

## 目录

- 四个公共文件
- 公共安全函数
- 模式 A：REST → MCP（含常见 REST 适配）
- 模式 B：单 MCP 透明代理
- 模式 C：多个/巨大 MCP
- 环境变量与 Secret 总表
- 模板级验证命令
- 上线前禁止项

## 四个公共文件

### package.json

```json
{
  "name": "my-mcp",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "wrangler dev",
    "check": "tsc --noEmit",
    "dry-run": "wrangler deploy --dry-run",
    "deploy": "wrangler deploy --keep-vars"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "latest",
    "@modelcontextprotocol/server": "latest",
    "agents": "latest",
    "zod": "latest"
  },
  "devDependencies": {
    "@cloudflare/workers-types": "latest",
    "typescript": "latest",
    "wrangler": "latest"
  }
}
```

代理/编排模式若不使用 MCP SDK，可移除未使用的 runtime dependencies。不要额外安装与任务无关的插件。

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "lib": ["ES2022"],
    "types": ["@cloudflare/workers-types"],
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

### wrangler.jsonc

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "my-mcp",
  "main": "src/index.ts",
  "compatibility_date": "YYYY-MM-DD",
  "compatibility_flags": ["nodejs_compat"],
  "observability": {
    "enabled": true,
    "head_sampling_rate": 1
  }
}
```

把日期改成部署日或最近已发布的日期，不写未来日期。

## 公共安全函数

私人公网连接使用统一入口鉴权：它位于 `/mcp` handler 之前，因此会覆盖
`initialize`、notification、`tools/list`、`tools/call`、GET/SSE 与会话 DELETE，
而不是只保护某一个工具。

默认优先 `Authorization: Bearer`。为了不破坏不能自定义 Header 的旧私人连接，
可以显式开启 `?token=`；也可以按需开启 `X-API-Key`。兼容开关默认关闭，避免
新部署无意把 token 放进 URL、代理日志或浏览器历史。公开插件应替换为 OAuth 2.1。

```ts
async function hash(value: string) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}

async function equalSecret(left: string, right: string) {
  const [a, b] = await Promise.all([hash(left), hash(right)]);
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

interface PrivateAuthEnv {
  MCP_AUTH_TOKEN?: string;
  MCP_AUTH_TOKEN_PREVIOUS?: string;
  ALLOW_LEGACY_QUERY_TOKEN?: string;
  ALLOW_API_KEY_HEADER?: string;
}

function suppliedClientTokens(request: Request, env: PrivateAuthEnv) {
  const candidates: string[] = [];
  const authorization = request.headers.get("authorization") ?? "";
  const bearer = authorization.match(/^Bearer\s+(.+)$/i)?.[1]?.trim();
  if (bearer) candidates.push(bearer);

  if (env.ALLOW_API_KEY_HEADER === "true") {
    const apiKey = request.headers.get("x-api-key") ?? request.headers.get("x-mcp-token");
    if (apiKey?.trim()) candidates.push(apiKey.trim());
  }

  if (env.ALLOW_LEGACY_QUERY_TOKEN === "true") {
    const url = new URL(request.url);
    for (const name of ["token", "access_token", "api_key"]) {
      const value = url.searchParams.get(name);
      if (value?.trim()) candidates.push(value.trim());
    }
  }
  return candidates;
}

async function authorized(request: Request, env: PrivateAuthEnv) {
  if (!env.MCP_AUTH_TOKEN) return false; // fail closed
  const accepted = [env.MCP_AUTH_TOKEN, env.MCP_AUTH_TOKEN_PREVIOUS].filter(
    (value): value is string => Boolean(value)
  );
  for (const supplied of suppliedClientTokens(request, env)) {
    for (const expected of accepted) {
      if (await equalSecret(supplied, expected)) return true;
    }
  }
  return false;
}

function proxyCorsHeaders() {
  return new Headers({
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET, POST, DELETE, OPTIONS",
    "access-control-allow-headers": [
      "authorization", "content-type", "accept", "mcp-protocol-version",
      "mcp-session-id", "last-event-id", "x-api-key", "x-mcp-token",
    ].join(", "),
    "access-control-expose-headers": "mcp-session-id",
    "access-control-max-age": "86400",
  });
}

function withProxyCors(response: Response) {
  const headers = new Headers(response.headers);
  for (const [name, value] of proxyCorsHeaders()) headers.set(name, value);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function corsPreflight() {
  return new Response(null, { status: 204, headers: proxyCorsHeaders() });
}
```

`MCP_AUTH_TOKEN_PREVIOUS` 仅用于无停机轮换，迁移完成后删除。查询参数兼容只适合
私人旧连接；若客户端能发 Header，应关闭 `ALLOW_LEGACY_QUERY_TOKEN`。

## 模式 A：REST → MCP

使用当前 SDK 的 `McpServer` 与 Cloudflare stateless MCP handler。核心结构：

```ts
import { McpServer } from "@modelcontextprotocol/server";
import { createMcpHandler } from "agents/mcp/server";
import { z } from "zod";

interface Env extends PrivateAuthEnv {
  API_KEY: string;
  MCP_AUTH_TOKEN: string;
}

const API_BASE_URL = "https://api.example.com";
const MAX_BYTES = 4 * 1024 * 1024;

async function readBounded(response: Response) {
  if (!response.ok) throw new Error(`Upstream HTTP ${response.status}`);
  const declared = Number(response.headers.get("content-length") ?? 0);
  if (declared > MAX_BYTES) throw new Error("Upstream response too large");
  const reader = response.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_BYTES) { await reader.cancel(); throw new Error("Upstream response too large"); }
    chunks.push(value);
  }
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { merged.set(chunk, offset); offset += chunk.byteLength; }
  return new TextDecoder().decode(merged);
}

async function searchApi(env: Env, query: string, limit: number) {
  const response = await fetch(`${API_BASE_URL}/search`, {
    method: "POST",
    headers: { authorization: `Bearer ${env.API_KEY}`, "content-type": "application/json" },
    body: JSON.stringify({ query, limit }),
    signal: AbortSignal.timeout(20_000),
  });
  return JSON.parse(await readBounded(response));
}

function createServer(env: Env) {
  const server = new McpServer(
    { name: "my-mcp", version: "1.0.0" },
    { instructions: "Search records when the user asks for information from the connected service. This example tool is read-only." }
  );

  server.registerTool("search_records", {
    title: "Search records",
    description: "Search the connected service. Use when the user needs matching records. Do not use for web search.",
    inputSchema: z.object({
      query: z.string().min(1).max(500).describe("Natural-language query"),
      limit: z.number().int().min(1).max(20).default(10),
    }),
    outputSchema: z.object({
      results: z.array(z.object({ id: z.string(), title: z.string(), url: z.string() })),
    }),
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true },
  }, async ({ query, limit }) => {
    try {
      const data = await searchApi(env, query, limit);
      const structuredContent = { results: data.results ?? [] };
      return { structuredContent, content: [{ type: "text", text: JSON.stringify(structuredContent) }] };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: error instanceof Error ? error.message : "Search failed" }] };
    }
  });
  return server;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext) {
    const path = new URL(request.url).pathname;
    if (path === "/health" && request.method === "GET") {
      return Response.json({ status: "ok", service: "my-mcp" });
    }
    if (path !== "/mcp") return new Response("Not found", { status: 404 });
    const handler = createMcpHandler(() => createServer(env), {
      route: "/mcp",
      legacy: "stateless",
    });
    if (request.method === "OPTIONS") return handler(request, env, ctx);
    if (!(await authorized(request, env))) return new Response("Unauthorized", { status: 401 });
    return handler(request, env, ctx);
  },
} satisfies ExportedHandler<Env>;
```

把示例 search 改成真实任务。每个新增工具都补齐 schema、annotations、超时和结果验证。

### 模式 A 常见 REST 适配

不要把所有 API 假设成 `POST + Bearer`。先用上游文档或无副作用请求确认，再修改：

```ts
// GET + query
const url = new URL("/items", API_BASE_URL);
url.searchParams.set("query", query);
await fetch(url, { headers: { "x-api-key": env.API_KEY } });

// 自定义 Header
await fetch(new URL("/search", API_BASE_URL), {
  method: "POST",
  headers: { "api-key": env.API_KEY, "content-type": "application/json" },
  body: JSON.stringify({ query }),
});

// 统一网关以 api_name 区分服务
await fetch(API_BASE_URL, {
  method: "POST",
  headers: { authorization: `Bearer ${env.API_KEY}`, "content-type": "application/json" },
  body: JSON.stringify({ api_name: "search_records", params: { query } }),
});
```

表单、签名请求、双向 TLS 或 OAuth 刷新不能套上述片段；按上游规范实现并增加专属 fixture。

## 模式 B：单 MCP 透明代理

透明代理不应默认缓冲 SSE；保留 MCP 协议 Header，客户端凭证不转给上游。
上游认证与私人入口认证是两层独立配置：入口可用上面的兼容验证，上游则按服务
实际要求选择 Bearer、API-Key Header、Basic、query token、OAuth access token
或无认证。不要假设所有上游都接受 `Authorization: Bearer`。

```ts
interface Env extends PrivateAuthEnv {
  UPSTREAM_TOKEN: string;
  MCP_AUTH_TOKEN: string;
  UPSTREAM_AUTH_KIND?: "bearer" | "api-key" | "basic" | "query" | "none";
  UPSTREAM_AUTH_NAME?: string;
}

const UPSTREAM_URL = "https://upstream.example.com/mcp";

function applyUpstreamAuth(url: URL, headers: Headers, env: Env) {
  const kind = env.UPSTREAM_AUTH_KIND ?? "bearer";
  if (kind === "none") return;
  if (!env.UPSTREAM_TOKEN) throw new Error("Missing UPSTREAM_TOKEN");
  if (kind === "bearer") headers.set("authorization", `Bearer ${env.UPSTREAM_TOKEN}`);
  else if (kind === "api-key") headers.set(env.UPSTREAM_AUTH_NAME ?? "x-api-key", env.UPSTREAM_TOKEN);
  else if (kind === "basic") headers.set("authorization", `Basic ${env.UPSTREAM_TOKEN}`);
  else if (kind === "query") url.searchParams.set(env.UPSTREAM_AUTH_NAME ?? "token", env.UPSTREAM_TOKEN);
}

export default {
  async fetch(request: Request, env: Env) {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") {
      return withProxyCors(Response.json({ status: "ok", service: "my-mcp-proxy" }));
    }
    if (url.pathname !== "/mcp") return withProxyCors(new Response("Not found", { status: 404 }));
    if (request.method === "OPTIONS") return corsPreflight();
    if (!(await authorized(request, env))) {
      return withProxyCors(new Response("Unauthorized", { status: 401 }));
    }

    const headers = new Headers(request.headers);
    for (const name of [
      "authorization", "x-api-key", "x-mcp-token", "cookie", "host",
      "content-length", "cf-connecting-ip", "cf-ray",
    ]) {
      headers.delete(name);
    }
    if (!headers.has("accept")) headers.set("accept", "application/json, text/event-stream");
    if (!headers.has("content-type") && request.method !== "GET" && request.method !== "HEAD") {
      headers.set("content-type", "application/json");
    }

    const upstreamUrl = new URL(UPSTREAM_URL);
    applyUpstreamAuth(upstreamUrl, headers, env);

    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      signal: AbortSignal.timeout(30_000),
    });
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.delete("set-cookie");
    responseHeaders.delete("server");
    return withProxyCors(new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    }));
  },
} satisfies ExportedHandler<Env>;
```

OAuth 上游通常还需要 token 获取与刷新逻辑；HMAC、AWS SigV4、双向 TLS 等专有
认证必须按上游文档实现，不能把原始密钥硬塞进 Bearer。`basic` 模式中的
`UPSTREAM_TOKEN` 应是预先生成的 Base64 `username:password`，仍只存 Secret。

只有确实要补 metadata 时才有界解析 initialize/tools/list。不要猜测上游工具的副作用。

## 模式 C：多个/巨大 MCP

不要把上百、上千工具直接暴露给模型。实现时遵循：

1. 各上游 initialize，并保存各自 `mcp-session-id`；
2. 4–8 路受控并发枚举，目录缓存约 5 分钟；
3. 工具名冲突显式前缀或映射；
4. 优先注册 `search_tools`，按名称/平台/描述评分，零匹配返回空；
5. `execute_read_tool` 只执行 allowlist 中的只读工具；
6. 写工具单独注册、准确注解、单独确认；
7. session 失效最多重建一次；
8. 每次 call 不重新枚举全部上游。

拒绝词正则只能做第二层防御，不能代替 allowlist：

```ts
const WRITE_LIKE = /(^|_)(create|add|update|edit|delete|remove|send|post|publish|upload|comment|like|follow|unfollow|favorite|order|pay)(_|$)/i;
```

模式 C 的上游数量、会话行为、命名冲突和安全分类高度依赖实际服务。Agent 必须先实测上游再生成完整代码，不能套一个假装通用但未经验证的静态模板。

这不是省略实现：交付模式 C 时必须生成完整的 `src/index.ts`，并以以下门槛验收：

1. 每个上游分别完成 initialize、initialized、tools/list 和只读 call；
2. session 按上游隔离，失效只重建一次；
3. 同名工具不会静默覆盖，映射结果可解释；
4. 并发有硬上限，响应有大小和超时上限；
5. `execute_read_tool` 只能命中明确 allowlist，拒绝词正则不能充当 allowlist；
6. 任一上游失败不伪装成空结果，返回可定位的部分失败信息；
7. 不手写一个只支持 initialize/list/call 的残缺 MCP 服务器，使用当前 SDK handler；
8. 生成代码必须通过类型检查、dry-run 和生产 init/list/call，缺一项不得称为完成。

## 环境变量与 Secret 总表

| 名称 | 类型 | 模式 | 用途 | 验证 |
|---|---|---|---|---|
| `MCP_AUTH_TOKEN` | Secret | A/B/C 私人公网 | 客户端访问 Worker | 无凭证 401，正确凭证成功 |
| `MCP_AUTH_TOKEN_PREVIOUS` | 临时 Secret | A/B/C | 无停机轮换 | 新旧均成功；迁移后删除并确认旧值失败 |
| `API_KEY` | Secret | A | Worker 调 REST | 真实无副作用 fixture 成功 |
| `UPSTREAM_TOKEN` | Secret | B/C | Worker 调上游 MCP | 上游 init/list/call 成功 |
| `UPSTREAM_AUTH_KIND` | 普通变量 | B/C | `bearer/api-key/basic/query/none` | 与上游文档及实测一致 |
| `UPSTREAM_AUTH_NAME` | 普通变量 | B/C | 自定义 Header/query 名 | 错误名称失败，正确名称成功 |
| `ALLOW_LEGACY_QUERY_TOKEN` | 普通变量 | 私人兼容 | 开启旧 query token | 默认关闭；开启后 query 成功 |
| `ALLOW_API_KEY_HEADER` | 普通变量 | 私人兼容 | 开启 API-Key Header | 默认关闭；开启后 Header 成功 |

Secret 用 `wrangler secret put`；普通变量写入 Wrangler 配置或在控制台设置。不要把真实值写入文档、源码或发布包。

## 模板级验证命令

完成任何模式后必须运行：

```bash
npm install
npx tsc --noEmit
npx wrangler@latest deploy --dry-run
npx @modelcontextprotocol/inspector@latest
```

Inspector 中依次验证 initialize、notifications/initialized、ping、tools/list 和一个无副作用 tools/call。生产验证的 bash 与 PowerShell 请求见 [quick-start.md](quick-start.md)，完整门槛见 [validation-and-release.md](validation-and-release.md)。

## 上线前禁止项

- example.com 等未替换占位符；
- 硬编码凭证；
- 所有工具一律标只读；
- 声明 outputSchema 却不返回 structuredContent；
- 万能执行器可调用写工具；
- 只验证 HTTP 200；
- 在公开文档中放私人 workers.dev 域名或真实 token。
