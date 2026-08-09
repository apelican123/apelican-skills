# OpenAI 插件规范

> 规则会变化。实施前以 OpenAI 最新官方文档为准：
> - https://developers.openai.com/plugins/build/mcp-server
> - https://developers.openai.com/api/docs/mcp
> - https://developers.openai.com/plugins/build/auth
> - https://developers.openai.com/plugins/deploy/app-review
> - https://developers.openai.com/plugins/guides/optimize-metadata

## MCP 服务器

- 提供稳定的 serverInfo.name 与语义化 version。
- initialize 返回有用的 instructions；最重要的工具选择、安全和顺序规则放在前 512 字符。
- 支持 Streamable HTTP，并正确处理 initialize、notifications/initialized、tools/list、tools/call、ping 与 JSON-RPC 错误。
- 不无理由硬编码只接受一个协议版本；按当前 SDK 和规范协商。
- 有状态服务正确处理 `mcp-session-id`；无状态服务不制造无意义 session。

## 每个工具

- `name`：稳定、动作导向，如 `search_documents`。
- `title`：便于人类阅读。
- `description`：明确用途、禁用场景、前置条件和返回内容。
- `inputSchema`：对象根；写明 required、格式、单位、范围、枚举和默认值。
- `outputSchema`：结构化返回时必须提供对象根 schema。
- `annotations`：真实声明只读、破坏性、开放世界和幂等性。

示例注解：

```json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "openWorldHint": false,
  "idempotentHint": true
}
```

写入、删除、支付、发帖、发信等工具不能为了“看起来安全”而误标为只读。

## 工具结果

结构化工具同时返回：

```json
{
  "structuredContent": { "items": [] },
  "content": [{ "type": "text", "text": "{\"items\":[]}" }]
}
```

`structuredContent` 必须通过 outputSchema。业务失败设置 `isError: true`；协议错误使用 JSON-RPC error，不能把失败伪装成普通成功文本。

## 标准知识检索

需要公司知识/文档检索兼容时，提供只读：

- `search(query)`：返回 `results[]`，每项至少有稳定 `id`、`title`、`url`。
- `fetch(id)`：按 search 的稳定 ID 返回文档标题、正文、URL 与可选 metadata。

可点击引用要求真实、用户可访问的 canonical URL。上游没有 URL 时返回空值并说明限制，不得伪造。

## 认证与发布

- 私人 Developer mode：可使用 OpenAI Tunnel 或 fail-closed Bearer。
- 公开插件：实现 OAuth 2.1，并为工具声明准确 securitySchemes 与 scope。
- OAuth 资源服务器发布受保护资源 metadata；未授权 HTTP 响应用 `WWW-Authenticate: Bearer`
  指向 metadata，工具级授权失败按当前 Apps SDK 要求提供 `_meta["mcp/www_authenticate"]` challenge。
- 工具 `securitySchemes`、资源 metadata、实际 scope 校验和运行时 challenge 必须一致；只写元数据
  而不验证 token，或只返回 401 而缺少发现信息，都不能算完整 OAuth 接入。
- 公开审核还需稳定生产 URL、支持/隐私资料、可复现授权流程、异常输入和权限错误测试。
- OpenAI Secure MCP Tunnel 仅适合私人/开发连接，不是公开生产入口。

验证：未登录时出现正确授权流程；授权后 token 的 issuer/audience/expiry/scope 被服务端验证；
撤销或过期 token 失败；低 scope 不能调用高权限工具；重新授权后仅恢复已授予范围。
