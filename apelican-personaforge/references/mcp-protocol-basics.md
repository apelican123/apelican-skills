# MCP 协议速查

## Streamable HTTP

- 端点通常为 `/mcp`。
- POST 请求使用 `Content-Type: application/json`。
- 客户端应声明 `Accept: application/json, text/event-stream`。
- 响应可能是 JSON 或 SSE；透明代理不得无故缓冲/重写流。
- 通知没有 JSON-RPC `id`，成功处理后通常返回 202/204，不生成伪响应。

## 生命周期

1. `initialize`：协商版本、能力、`serverInfo` 和 `instructions`。
2. `notifications/initialized`：客户端确认初始化。
3. `tools/list`：返回完整工具定义。
4. `tools/call`：按 schema 调用。
5. `ping`：返回空 result。

不要只为“看起来新”硬编码单个协议版本；按 SDK/规范协商并与主流兼容版本回归。

## 有状态上游

若 initialize 响应头含 `mcp-session-id`：

- 保存到该上游会话；
- initialized/list/call 都回带；
- 400 session 错误时清除并重建一次；
- 多上游分别维护，不串用；
- Worker 实例内 Map 不是强持久保证，需要接受冷启动重建或使用合适持久层。

## 工具结果

```json
{
  "content": [{ "type": "text", "text": "{\"items\":[]}" }],
  "structuredContent": { "items": [] }
}
```

若声明 `outputSchema`，对象根的 `structuredContent` 必须验证通过。工具业务失败设置 `isError: true`；协议格式/方法错误使用 JSON-RPC error。

## 传输边界

- 请求体默认限制约 1 MiB，并按业务调整；
- 响应解析设置硬上限；未知大响应流式转发；
- 超时使用 `AbortController`；
- 不盲目重试非幂等操作；
- 代理保留必要的 `mcp-session-id`、内容类型和协议相关头，剥离 hop-by-hop 与客户端认证头。
