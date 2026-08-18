# OpenAI 插件契约（基线：2026-08-18）

本文件是实现和审核的控制性摘要；出现冲突时以最新官方文档为准。

## 1. MCP 服务

- 使用稳定的服务器 `name`、语义化 `version` 和明确 `instructions`。
- `instructions` 最关键的工具选择、安全和顺序规则放在前 512 个字符。
- 支持 Streamable HTTP；客户端可能协商不同协议版本，不要无理由硬编码只接受单一版本。
- 正确处理 `initialize`、`notifications/initialized`、`tools/list`、`tools/call`、`ping` 和 JSON-RPC 错误。
- 有状态服务必须正确传递 `mcp-session-id`；无状态服务不要制造不必要的 session。

## 2. 工具定义

每个工具至少包含：

- 稳定、动作导向的 `name`；
- 人类可读 `title`；
- 说明何时使用、何时不用的 `description`；
- 对象根 `inputSchema`，每个参数有可判定含义；
- 结构化返回时的对象根 `outputSchema`；
- 与真实副作用一致的 `annotations`。

推荐注解：

```json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "openWorldHint": true,
  "idempotentHint": true
}
```

不得为提高审核通过率而把写入、删除、支付、外发或公开发布工具误标为只读。

## 3. 结果与兼容

结构化工具同时返回：

```json
{
  "structuredContent": { "items": [] },
  "content": [{ "type": "text", "text": "{\"items\":[]}" }]
}
```

`structuredContent` 必须通过该工具的 `outputSchema`。错误使用 `isError: true`，并给模型可行动的简短说明；不要把协议失败包装成普通成功文本。

## 4. 公司知识 `search` / `fetch`

只有需要 OpenAI 标准知识检索兼容时才实现，且保持只读。

`search`：

```json
{
  "name": "search",
  "inputSchema": {
    "type": "object",
    "properties": { "query": { "type": "string" } },
    "required": ["query"],
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "results": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "id": { "type": "string" },
            "title": { "type": "string" },
            "url": { "type": "string" }
          },
          "required": ["id", "title", "url"]
        }
      }
    },
    "required": ["results"]
  }
}
```

`fetch` 接受稳定 `id`，返回完整条目。若要让 ChatGPT 生成可打开引用，`url` 必须是用户能访问的非空 canonical URL。上游没有真实 URL 时保留为空并明确报告“不能生成可打开引用”，绝不伪造。

## 5. 认证

- 上游 API Key/Client ID 只放云端 Secret；ChatGPT 的认证选项保护的是 MCP 连接，不是上游 API。
- 私人自用开发连接可使用带用户名标识和独立随机 Token 的云端专属能力 URL，并在 ChatGPT 选择“无身份验证”；完整 URL 本身就是 Token 和访问入口，验证在 Cloudflare 完成。这是私人兼容模式，不是公开审核认证。
- 每位用户独立部署优先；同一 Worker 只为少量可信用户提供一人一链接、一人一摘要 Secret，并验证跨用户错配失败。大量用户、公开发布或需要独立账户数据/scope 的 ChatGPT 公网连接使用 OAuth 2.1。DCR/CIMD 可免去本地手填 OAuth client 配置，但不能因此把固定 `/mcp` 选择为“无身份验证”。
- 私人开发连接在支持自定义 header 的其他客户端可使用 fail-closed Bearer；URL 查询 token 仅作现有连接兼容。
- 每个工具准确声明 `securitySchemes`：匿名工具用 `noauth`，受保护工具用 `oauth2` 和所需 scopes；SDK 兼容层若使用 `_meta.securitySchemes`，必须在生产 `tools/list` 中验证客户端实际可见。
- 工具运行时缺少或不满足 scope 时，返回 `isError: true`，并在 `_meta["mcp/www_authenticate"]` 给出包含 `error` 与 `error_description` 的 Bearer challenge。
- OAuth 元数据、授权/令牌端点、PKCE、scope、重定向 URI 和错误行为都需端到端验证。
- 只有用户身份和授权范围确实允许时才执行高风险操作。

## 6. 公开审核

准备并验证：

- 稳定生产 URL、支持与隐私链接；
- 清晰的插件名称、图标、描述和分类；
- 真实可复现的登录/授权流程；
- 所有工具正常输入、异常输入、权限不足和上游错误；
- 元数据扫描无占位符、内部名称、密钥或误导性副作用；
- 不依赖 Secure MCP Tunnel 作为公开生产入口。

## 官方来源

- https://developers.openai.com/plugins/build/mcp-server
- https://developers.openai.com/api/docs/mcp
- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/plugins/deploy/app-review
- https://developers.openai.com/plugins/guides/optimize-metadata
