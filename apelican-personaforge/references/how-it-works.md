# 工作原理

Plugin Forge 是 ChatGPT 与上游 REST/MCP 之间的协议适配层：

```text
ChatGPT -> 标准 MCP -> Worker/Tunnel -> REST 或上游 MCP
```

它负责四件事：

1. 对外提供稳定 Streamable HTTP MCP；
2. 翻译、代理或编排上游；
3. 管理认证、会话、超时、大小和并发；
4. 把大型 API 收敛为模型容易选对的工具面。

## 三种模式

- A 翻译：REST 端点变为少量任务型 MCP 工具。
- B 代理：已有 MCP 流式透传，注入上游认证，保留 session。
- C 编排：多个 MCP 建独立会话并缓存目录；不要盲目合并成近千工具，优先目标型工具或 search/execute facade。

## 两条连接路径

- Cloudflare Worker：提供稳定公网 HTTPS；私人自用默认使用带用户名标识和独立随机 Token 的专属能力 URL。每位用户独立部署最安全；同一 Worker 只适合少量人工管理的可信用户，并要求一人一链接和跨用户错配测试。大量用户、分身份/scope 或公开发布使用 OAuth 2.1，其他支持自定义 header 的私人客户端可用 Bearer。
- OpenAI Secure MCP Tunnel：本机/内网私人开发；进程停机即不可用，不恢复 Cloudflare Tunnel。

## 为什么 HTTP 200 仍可能失败

JSON-RPC error 也常装在 HTTP 200 内；工具业务错误可能通过 `isError` 表达。必须解析响应、检查 schema，并真实调用，而不能只验证状态码。

## 为什么元数据就是性能

模型调用前先阅读 server instructions 和工具 schema。工具太多、描述重叠、参数含糊，会提高选错和重试率。减少工具数量、写清使用时机、提供稳定结构化结果，通常比单纯缩短网络延迟更能改善端到端体验。
