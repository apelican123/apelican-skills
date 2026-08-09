# 工作原理

```text
ChatGPT -> 标准 MCP -> Worker 或 OpenAI Tunnel -> REST/MCP 上游
```

Plugin Forge 负责：提供标准 Streamable HTTP、翻译/代理/编排上游、管理认证和 session、限制超时/大小/并发、把巨大 API 收敛成模型容易选择的工具面。

桥接层同时解决三件事：

1. **传输**：让 ChatGPT 看到标准 `/mcp`，正确处理 JSON、SSE、notification 与 session；
2. **认证**：把客户端到 Worker 和 Worker 到上游分成两层，不泄露或串用凭证；
3. **语义**：把原始接口改造成模型能选对的工具、参数和结构化结果。

## 三种模式

- A 翻译：REST 端点变为任务型 MCP 工具。
- B 代理：已有 MCP 流式透传并注入上游认证。
- C 编排：多个 MCP 独立会话与缓存；大型目录压缩为少量高价值入口。

| 差异 | A 翻译 | B 代理 | C 编排 |
|---|---|---|---|
| 上游 | REST | 一个 MCP | 多个/巨大 MCP |
| 工具定义 | 本服务注册 | 默认透传 | 搜索、映射或任务化收敛 |
| session | 通常无 | 透传客户端 session | 各上游独立维护 |
| 最大风险 | schema 与上游不一致 | 凭证/header 泄漏、SSE 被缓冲 | 同名覆盖、无界并发、误执行写工具 |
| 核心验证 | REST 与工具结果对照 | 上游与代理结果对照 | 每个上游＋聚合结果对照 |

## 两条部署路径

- Cloudflare Worker：24 小时公网 HTTPS；私人可 Bearer，公开需 OAuth 2.1。
- OpenAI Secure MCP Tunnel：本机/内网私人开发；进程停机即不可用，不作为公开生产入口。

Worker 适合多设备共享稳定 URL；Tunnel 可以被同一工作区的其他设备使用，但数据源主机、
Tunnel client 和本地 MCP 必须保持在线。

## 会话为何容易出错

无状态 Worker 可以在每次请求创建 MCP server；但“上游 MCP”仍可能返回
`mcp-session-id`。模式 B 要透传该 header，模式 C 要为每个上游单独保存、回带和重建。
不能把 Worker 内存 Map 当永久存储；冷启动后应重新 initialize。session 错误最多自动重建一次，
避免把认证失败或协议错误变成无限重试。

## 两层认证

```text
客户端 --MCP_AUTH_TOKEN/OAuth--> Worker --API_KEY/UPSTREAM_TOKEN/OAuth/签名--> 上游
```

入口支持什么载体不决定上游使用什么认证。透明代理要先移除客户端 Authorization、cookie、
X-API-Key 等凭证，再注入上游要求的凭证；否则既不安全，也会造成兼容性冲突。

## 为什么元数据影响性能

模型调用前先读 instructions 和工具 schema。工具太多、描述重叠、参数含糊会增加误选与重试。减少工具数量、写清使用条件、返回稳定结构，通常比只优化几百毫秒网络延迟更重要。
