# OpenAI Secure MCP Tunnel

适合本机/内网的私人开发连接；不依赖 Cloudflare，不作为公开插件生产入口。

## 前提

- 一个能在本机运行的 stdio MCP 或 loopback HTTP MCP；
- OpenAI 当前 Tunnel 文档要求的账号、权限、tunnel_id 与控制面凭证；
- 最新 tunnel-client；
- 机器能出站访问 OpenAI。

界面与 CLI 参数会变化，执行前查看：

- https://platform.openai.com/docs/guides/secure-mcp-tunnels
- https://github.com/openai/tunnel-client/releases/latest
- `tunnel-client help quickstart`

## 步骤

1. 在 OpenAI Platform 创建 tunnel，并关联目标 ChatGPT 工作区。
   - **验证**：记录非敏感 `tunnel_id` 占位标识和目标工作区；刷新页面后 tunnel 仍存在。
   - **停止条件**：账号没有 Tunnel 权限或目标工作区不正确。
2. 按当前文档把控制面凭证放进当前进程环境或安全存储，绝不写进脚本/Git。
   - **验证**：当前版本要求的环境变量“名称”齐全；运行日志不显示值；仓库扫描无凭证。
   - **停止条件**：只能通过硬编码或把 key 发到聊天里才能继续。
3. 下载最新 tunnel-client，确认命令可运行。
   - **验证**：运行 `tunnel-client --version` 和 `tunnel-client help quickstart`；两者状态码为 0。
   - **停止条件**：实际 help 与本文示意参数不同且尚未按当前 help 调整。
4. 独立启动并测试本地 MCP。
   - **HTTP 验证**：只监听 `127.0.0.1`；直接完成 init/initialized/list/call。
   - **stdio 验证**：用 MCP Inspector 或当前 SDK 客户端启动命令，完成 init/list/call。
   - **停止条件**：本地直连失败；Tunnel 不能用来掩盖本地 MCP 错误。
5. 初始化 profile。
   - **验证**：查看 profile 状态或配置摘要，只核对 tunnel、传输类型和本地目标，不输出凭证。
   - **停止条件**：HTTP URL 指向 `0.0.0.0`、公网地址或错误端口；stdio 命令无法独立运行。
6. 运行 doctor，全部通过才启动 client。
   - **验证**：`doctor --explain` 中控制面连接、目标工作区、本地 MCP 和凭证检查均通过。
   - **停止条件**：任何必需检查失败；不要只因 tunnel-client 进程存在就算成功。
7. 在 ChatGPT Developer mode 中选择 Tunnel。
   - **验证**：目标工作区看到正确 Tunnel，工具数量与本地 tools/list 一致。
   - **停止条件**：出现同名旧 Tunnel、工具数为 0 或工具来自错误 profile。
8. 枚举工具并真实调用一个只读工具。
   - **验证**：结果与本地直连的关键字段一致；检查 JSON-RPC error 与 `result.isError`。
   - **停止条件**：只看到连接成功但没有真实调用，或调用了写工具做自动测试。

HTTP 模式示意（以本机 help 为准）：

```powershell
tunnel-client init --profile local-mcp --tunnel-id tunnel_xxx --mcp-server-url http://127.0.0.1:3000/mcp
tunnel-client doctor --profile local-mcp --explain
tunnel-client run --profile local-mcp
```

stdio 模式改用当前版本提供的 MCP command 参数。

不要从旧文章猜 stdio 参数。先运行：

```powershell
tunnel-client help quickstart
tunnel-client init --help
```

```bash
tunnel-client help quickstart
tunnel-client init --help
```

把本地 MCP 的可执行程序、参数和工作目录分别传入当前 CLI 支持的字段；包含空格的路径必须
按当前 shell 规则引用。初始化后再次运行 doctor，而不是直接常驻。

## 安全

- HTTP MCP 监听 `127.0.0.1`，不监听 `0.0.0.0`；
- 管理 UI、metrics 和 health 端点保持 loopback；
- 本地 MCP 不要求 ChatGPT 无法携带的额外 query token；
- 不把控制面 key、profile 或 tunnel 配置提交 Git；
- tunnel-client 与 MCP 进程都必须常驻。

## 验收

- doctor 全部通过；
- 本地 init/list/call 正常；
- Tunnel 在目标工作区可见；
- ChatGPT 工具数量与本地一致；
- 断开 tunnel-client 后不可用，重启后恢复；
- 没有多余公网监听端口。

## 多设备边界

Cloudflare Worker 的 HTTPS 地址可被多设备客户端使用；Tunnel 则绑定持续运行的主机。
在手机或第二台电脑使用 Tunnel 时，原主机、Tunnel client 和本地 MCP 都必须在线。
迁移到新主机要重新安装客户端、重新取得凭证并重做 1–8 步验证，不复制旧机器的明文凭证。
