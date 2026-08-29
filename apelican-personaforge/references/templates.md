# Worker 代码模板（零依赖，上传即跑）

铸造机默认生成**零依赖** Worker：不引入 npm 包、不需要打包构建。一个 `worker.js` + 一个 `metadata.json` 上传即运行。实现的是 MCP over Streamable HTTP（JSON-RPC 2.0 over POST），与 ChatGPT 的 Add MCP server 兼容。

## 文件清单

```text
worker.js        # 主脚本（含工具注册表，按需修改顶部 CONFIG）
metadata.json    # 部署元数据（main_module 必须 = worker.js）
```

## metadata.json

```json
{
  "main_module": "worker.js",
  "workers_dev": true,
  "compatibility_date": "2026-08-01"
}
```

## worker.js 总模板

以下模板涵盖三种形态：

- **单个 REST API**：在 `REST_TOOLS` 注册，每个工具一个 fetch 调用（示例：`search_documents`）；
- **单个 MCP 透传**：在 `MCP_UPSTREAM` 配置后，`tools/call` 原样转发到上游 MCP（适合直接把已有 MCP 接进 ChatGPT）；
- **多 MCP 聚合**：多份上游时扩展 `MCP_UPSTREAMS` 与 `ROUTE` 查找表，用来源路由 + allowlist（见文末说明）。

```javascript
// worker.js — ChatGPT 个人插件铸造机生成的 MCP Server（零依赖）
// 部署后 URL 形如：https://<脚本名>.<subdomain>.workers.dev/u/<令牌>/mcp

// ============ 配置区：铸造流程自动生成，一般无需手改 ============

// REST 工具注册表：每个工具 = { name, description, inputSchema, method, urlTemplate, paramsFromArgs }
const REST_TOOLS = [
  {
    name: "search_documents",
    description: "按关键词搜索文档，返回标题与摘要。适合查找资料；不需要知道文档库结构时用它。",
    inputSchema: {
      type: "object",
      properties: {
        q: { type: "string", description: "搜索关键词" },
        limit: { type: "number", description: "返回条数，默认 5", default: 5 }
      },
      required: ["q"]
    },
    method: "GET",
    // {q} {limit} 会按 args 替换；未提到的参数原样拼到 query
    urlTemplate: "https://api.example.com/v1/search?q={q}&limit={limit}",
    // 可选：额外请求头，值可用 {args:字段} 或固定字符串
    headers: {}
  }
];

// MCP 透传上游：直接转发 tools/list 与 tools/call
const MCP_UPSTREAM = null; // 例如 { "url": "https://upstream.example.com/mcp", "authHeader": "Authorization", "authValue": "Bearer <key>" }
// 多上游时用数组 + ROUTE（见文末「多 MCP 聚合」）

// ============ 以下为协议实现，一般无需修改 ============

const VERSION = "4.0.0";

function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function authOk(request, env) {
  const token = (env.LINK_TOKEN || "").trim();
  if (!token) return false; // 未配置令牌 = 一律拒绝

  const url = new URL(request.url);
  const m = url.pathname.match(/^\/u\/([^/]+)\/mcp$/);
  const pathToken = m ? decodeURIComponent(m[1]) : "";

  const hdr = request.headers.get("Authorization") || "";
  const hdrToken = hdr.startsWith("Bearer ") ? hdr.slice(7).trim() : "";

  return constantTimeEqual(pathToken, token) || constantTimeEqual(hdrToken, token);
}

function jsonRpc(id, result, isError) {
  const payload = { jsonrpc: "2.0", id: id ?? null };
  if (isError) {
    payload.error = { code: -32000, message: typeof result === "string" ? result : "工具调用失败" };
  } else {
    payload.result = result;
  }
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
  });
}

// REST 参数模板替换：{q} -> 对应 args 值；未匹配的保留原样
function fillTemplate(tpl, args) {
  let out = tpl;
  for (const [k, v] of Object.entries(args || {})) {
    out = out.split("{" + k + "}").join(encodeURIComponent(String(v)));
  }
  return out;
}

async function callRESTTool(tool, args, env) {
  const url = fillTemplate(tool.urlTemplate, args);
  const headers = { ...(tool.headers || {}) };
  if (env.UPSTREAM_KEY && !headers["Authorization"]) {
    headers["Authorization"] = "Bearer " + env.UPSTREAM_KEY;
  }

  let resp;
  if (tool.method === "GET") {
    resp = await fetch(url, { headers });
  } else {
    resp = await fetch(url, {
      method: tool.method,
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(args)
    });
  }

  const text = await resp.text();
  // 尽量把 JSON 解析为结构化内容，否则原文返回
  let structured = null;
  try { structured = JSON.parse(text); } catch (_) {}
  return {
    content: [{ type: "text", text: text.slice(0, 8000) || "(空响应)" }],
    ...(structured !== null ? { structuredContent: structured } : {})
  };
}

async function callMCPTool(upstream, name, args, env) {
  const headers = { "Content-Type": "application/json" };
  if (upstream.authHeader && upstream.authValue) {
    headers[upstream.authHeader] = upstream.authValue;
  } else if (env.UPSTREAM_KEY) {
    headers["Authorization"] = "Bearer " + env.UPSTREAM_KEY;
  }
  const resp = await fetch(upstream.url, {
    method: "POST",
    headers,
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } })
  });
  const text = await resp.text();
  let parsed = null;
  try { parsed = JSON.parse(text); } catch (_) {}
  // 透传上游的 result 结构（含 content / structuredContent / isError）
  if (parsed && parsed.result) {
    return parsed.result;
  }
  if (parsed && parsed.error) {
    throw new Error(parsed.error.message || "上游 MCP 调用失败");
  }
  return { content: [{ type: "text", text: text.slice(0, 8000) }] };
}

// tools/list：MCP 上游存在时合并其工具面，REST 工具固定返回
async function listTools(env) {
  const tools = REST_TOOLS.map((t) => ({
    name: t.name,
    title: t.title || t.name,
    description: t.description,
    inputSchema: t.inputSchema,
    securitySchemes: [{ type: "noauth" }] // ChatGPT 端不另走 OAuth；服务端由 LINK_TOKEN 校验
  }));

  if (MCP_UPSTREAM) {
    const headers = { "Content-Type": "application/json" };
    if (MCP_UPSTREAM.authHeader && MCP_UPSTREAM.authValue) headers[MCP_UPSTREAM.authHeader] = MCP_UPSTREAM.authValue;
    else if (env.UPSTREAM_KEY) headers["Authorization"] = "Bearer " + env.UPSTREAM_KEY;
    try {
      const resp = await fetch(MCP_UPSTREAM.url, {
        method: "POST",
        headers,
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" })
      });
      const data = await resp.json();
      if (data && data.result && Array.isArray(data.result.tools)) {
        for (const t of data.result.tools) {
          tools.push({ ...t, securitySchemes: [{ type: "noauth" }] });
        }
      }
    } catch (e) {
      // 上游不可达时仍返回 REST 工具，避免整个插件不可用
    }
  }
  return tools;
}

async function handleToolsCall(body, env) {
  const name = body.params?.name;
  const args = body.params?.arguments || {};

  const restTool = REST_TOOLS.find((t) => t.name === name);
  if (restTool) {
    const result = await callRESTTool(restTool, args, env);
    return jsonRpc(body.id, result);
  }

  if (MCP_UPSTREAM) {
    try {
      const result = await callMCPTool(MCP_UPSTREAM, name, args, env);
      return jsonRpc(body.id, result);
    } catch (e) {
      return jsonRpc(body.id, e.message || "上游调用失败", true);
    }
  }

  return jsonRpc(body.id, "未找到工具: " + name, true);
}

export default {
  async fetch(request, env) {
    // 1. 认证：路径令牌或 Bearer 二选一，错误令牌一律 401
    if (!authOk(request, env)) {
      return new Response("unauthorized", { status: 401 });
    }

    // 2. 只接受 POST JSON-RPC
    if (request.method !== "POST") {
      if (request.method === "GET") {
        return new Response("MCP endpoint ready", { status: 200 });
      }
      return new Response("method not allowed", { status: 405 });
    }
    if (!request.headers.get("content-type")?.includes("application/json")) {
      return new Response("content-type must be application/json", { status: 415 });
    }

    let body;
    try {
      body = await request.json();
    } catch (_) {
      return new Response("invalid json", { status: 400 });
    }

    // 3. 路由 JSON-RPC 方法
    switch (body.method) {
      case "initialize":
        return jsonRpc(body.id, {
          protocolVersion: "2025-03-26",
          capabilities: { tools: {} },
          serverInfo: { name: "apelican-personaforge", version: VERSION }
        });
      case "notifications/initialized":
        return jsonRpc(body.id, {});
      case "ping":
        return jsonRpc(body.id, {});
      case "tools/list":
        return jsonRpc(body.id, { tools: await listTools(env) });
      case "tools/call":
        return await handleToolsCall(body, env);
      default:
        return jsonRpc(body.id, "method not supported: " + body.method, true);
    }
  }
};
```

## 使用说明

1. 把上面模板保存为 `worker.js`，按目标修改顶部配置区：
   - 单个 REST API：填 `REST_TOOLS`（每个端点一个条目）；
   - 单个 MCP：填 `MCP_UPSTREAM`，设 URL 与认证头；
   - 多 MCP：见下一节；
2. 部署写入两个 Secret：
   - `LINK_TOKEN`：铸造流程生成的 32 字节随机令牌（必填，不填服务拒绝一切请求）；
   - `UPSTREAM_KEY`：上游 API Key / Bearer（REST 工具自动加 `Authorization: Bearer`；MCP 透传在未配置 `authValue` 时使用）；
3. 按 [verification.md](verification.md) 验证。

## 多 MCP 聚合

上游不止一个时，把 `MCP_UPSTREAM` 替换为数组并在 `handleToolsCall` 增加来源路由：

```javascript
const MCP_UPSTREAMS = [
  { id: "docs", url: "https://docs.example.com/mcp", authHeader: "Authorization", authValue: "Bearer <key>" },
  { id: "wiki", url: "https://wiki.example.com/mcp", authHeader: "Authorization", authValue: "Bearer <key>" }
];
// 工具名为 <来源id>:<工具名>，允许执行的工具放入静态 allowlist：
const ALLOWLIST = ["docs:search", "docs:get", "wiki:search"];
```

- 静态 allowlist 只放行确认安全的工具；上游新增工具默认待审核，目录刷新不自动放行；
- 写操作逐个注册，不能经通用执行器绕过；
- 每个上游独立维护 session；一个来源失败时明确报告该来源不可用，不伪装成完整成功；
- 更多聚合细节（TTL、并发上限、故障隔离）见 [architecture-checklist.md](architecture-checklist.md)。

## 模板中的安全默认

- 未配置 `LINK_TOKEN` 时拒绝一切请求，杜绝「裸 /mcp 匿名暴露」；
- 令牌比较用常量时间，不泄露长度差异；
- 上游密钥只经 Secret 注入（`env.UPSTREAM_KEY`），不硬编码；
- 错误信息不含堆栈、认证头或上游正文；
- 响应正文截断到 8000 字符，防止上游返回超大内容打爆上下文。