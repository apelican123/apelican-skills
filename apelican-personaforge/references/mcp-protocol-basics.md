# MCP 协议速查

## Streamable HTTP

- 端点通常为 `/mcp`。
- POST 使用 `Content-Type: application/json`。
- Accept 声明 `application/json, text/event-stream`。
- 响应可能是 JSON 或 SSE；透明代理不要无故缓冲流。
- notification 没有 JSON-RPC id，成功处理后通常返回 202/204。

## 生命周期

1. initialize：协商版本、能力、serverInfo、instructions。
2. notifications/initialized：客户端确认。
3. tools/list：返回工具定义。
4. tools/call：按 schema 调用。
5. ping：返回空 result。

不要无理由硬编码只接受单一协议版本。用当前 SDK 协商，并测试主流兼容版本。

最小 initialize 请求：

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}
```

服务端返回的 `protocolVersion`、`serverInfo`、`capabilities` 和可选 `instructions` 才是协商结果。
随后发送无 id 的 `notifications/initialized`，再进行 list/call。不要跳过通知后仅凭 initialize 判定兼容。

工具枚举与调用：

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_records","arguments":{"query":"example","limit":3}}}
```

## 有状态上游

initialize 响应头出现 `mcp-session-id` 时：保存、后续回带、各上游隔离；400 session 错误最多重建一次。Worker 内存 Map 不是强持久存储，冷启动时要能重新初始化。

## 错误

- 协议/方法/参数格式错误：JSON-RPC error。
- 工具业务失败：result.isError = true。
- HTTP 200 里也可能装着失败，客户端必须解析正文。

notification 没有 id，不得返回伪造的 JSON-RPC id；方法不存在使用规范 error，而不是把错误
塞进成功 `result`。工具自身失败则返回 `isError: true`，让客户端能区分传输/协议与业务失败。

## 结构化结果

```json
{
  "content": [{"type":"text","text":"{\"items\":[]}"}],
  "structuredContent": {"items":[]}
}
```

声明 outputSchema 时，structuredContent 必须通过验证。
