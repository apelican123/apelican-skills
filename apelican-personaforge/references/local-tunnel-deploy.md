# OpenAI Secure MCP Tunnel

只用于本机/内网的私人开发连接。本机制与 Cloudflare Tunnel 无关；用户已经删除 Cloudflare Tunnel 时不要恢复。

## 适用边界

- MCP 服务和数据留在本机/内网；
- `tunnel-client` 发起出站连接，不开放公网入站端口；
- 客户端进程和本地 MCP 必须常驻；
- 不作为公开插件生产入口。

## 执行前实时核对

界面、RBAC、环境变量和 CLI 参数可能变化，先查看：

- https://platform.openai.com/docs/guides/secure-mcp-tunnels
- https://github.com/openai/tunnel-client/releases/latest
- `tunnel-client help quickstart`

## 最小流程

1. 在 OpenAI Platform 创建并关联 tunnel，获得 `tunnel_id`。
2. 为运行机器配置当前文档要求的控制面凭证；只放在进程环境/安全存储。
3. 下载最新 `tunnel-client`。
4. 准备 stdio MCP 或 loopback HTTP MCP。
5. 初始化 profile，运行 doctor，再启动 client。
6. 在 ChatGPT Developer mode 中选择 Tunnel。
7. 实际调用一个无副作用工具。

示意命令（以本机 `help quickstart` 为准）：

```powershell
tunnel-client init --profile local-mcp --tunnel-id tunnel_xxx --mcp-server-url http://127.0.0.1:3000/mcp
tunnel-client doctor --profile local-mcp --explain
tunnel-client run --profile local-mcp
```

stdio 模式使用当前版本提供的 MCP command 参数，让 tunnel-client 启动服务器进程。

## 本地安全

- HTTP MCP 监听 `127.0.0.1`，不监听 `0.0.0.0`；
- 不把控制面 API key、profile 密钥或 tunnel 配置提交 Git；
- 本地 MCP 不额外要求 ChatGPT 无法提供的自定义 query token；
- 管理 UI、metrics、health 端点保持 loopback；
- 定时检查 tunnel-client 与 MCP 进程，不用 Cloudflare Tunnel 补救。

## 验证

- doctor 全部通过；
- 本地 MCP 独立 initialize/list/call 正常；
- Tunnel 在目标 ChatGPT 工作区可见；
- ChatGPT 端工具枚举与本地一致；
- 停止 tunnel-client 后不可用，重启后恢复；
- 本机没有多余公网监听端口。
