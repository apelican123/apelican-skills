# 验证与发布

## 自动审计

脚本包使用页面明确支持的 `.js` 文件，不需要把所有代码压进 Markdown。新文档统一使用 `audit-mcp.js`。

### 专属能力链接

把真实 URL 只放入当前终端进程。`MCP_INVALID_URL` 使用同一用户路径但错误 Token；多人 Worker 再提供 `MCP_CROSS_USER_URL`，把 A 的 Token 拼到 B 的用户路径，预期也被拒绝。

```powershell
$env:MCP_URL="https://service.example.com/u/<用户A>/<真实随机TokenA>/mcp"
$env:MCP_INVALID_URL="https://service.example.com/u/<用户A>/<错误随机Token>/mcp"
$env:MCP_CROSS_USER_URL="https://service.example.com/u/<用户B>/<真实随机TokenA>/mcp"
$env:MCP_AUTH_MODE="capability"
$env:MCP_EXPECT_AUTH="none"
node <skill-dir>/scripts/audit-mcp.js
```

macOS / Linux：

```bash
MCP_URL="https://service.example.com/u/<用户A>/<真实随机TokenA>/mcp" \
MCP_INVALID_URL="https://service.example.com/u/<用户A>/<错误随机Token>/mcp" \
MCP_CROSS_USER_URL="https://service.example.com/u/<用户B>/<真实随机TokenA>/mcp" \
MCP_AUTH_MODE="capability" \
MCP_EXPECT_AUTH="none" \
node <skill-dir>/scripts/audit-mcp.js
```

单人独立 Worker 可省略 `MCP_CROSS_USER_URL`；错误 Token 测试仍必做。审计输出不得回显任何 URL。

### OAuth

```powershell
$env:MCP_URL="https://service.example.com/mcp"
$env:MCP_TOKEN="仅在当前进程中设置"
$env:MCP_AUTH_MODE="bearer"
$env:MCP_EXPECT_AUTH="oauth2"
node <skill-dir>/scripts/audit-mcp.js
```

### 真实只读 fixture

可设置 `MCP_FIXTURES` 指向 JSON 文件：

```json
{
  "search": { "query": "test" },
  "fetch": { "id": "known-safe-id" }
}
```

fixture 只能包含无副作用调用。写操作单独走 dry-run、确认、执行和读回；fixture 文件不得包含真实 URL、Token 或私人数据。

## 审计通过条件

- 错误 Token、未知用户和跨用户错配均被拒绝；正确用户链接成功；
- OAuth 模式的 protected-resource 与 authorization-server metadata 可发现，PKCE 包含 `S256`；专属链接模式跳过 OAuth 发现；
- `initialize` 有稳定 `serverInfo` 和非空 `instructions`；
- `tools/list` 无 JSON-RPC error；
- 每个工具有 name/title/description/inputSchema/annotations；
- `securitySchemes` 与专属链接/no-auth/OAuth 模式及 scope 一致；
- 有 `outputSchema` 的工具返回匹配的 `structuredContent`；
- fixture 无 JSON-RPC error、无 `isError`；
- `search`/`fetch` 存在时符合当前 OpenAI 公司知识约定。

## 部署门槛

1. 记录当前生产 version ID；
2. `node --check`、测试或 `tsc --noEmit`；
3. `wrangler deploy --dry-run`；
4. 单服务部署，不同时批量改多个 Worker；
5. 等待边缘传播；
6. 用生产 URL 运行审计、错误链接、跨用户错配和真实只读 fixture；
7. 在 ChatGPT 验证：专属链接使用“无身份验证”，OAuth 服务使用 OAuth，Tunnel 使用对应 Tunnel 入口；
8. 做一条自然语言的真实只读调用，而不只确认工具列表；
9. 检查日志没有密钥、完整专属 URL、堆栈和私人数据；
10. 交付每位用户独立的撤销/轮换方法；
11. 失败只回滚当前 Worker。

## 公开发布的额外门槛

- OAuth 2.1 全流程与用户/scope 隔离；
- 隐私政策、支持链接、品牌素材和准确权限说明；
- 稳定公网 HTTPS 服务，不依赖本机 Tunnel 或私人能力链接；
- 工具副作用、开放网络访问和确认体验与真实行为一致；
- 测试账号、审核说明和代表性提示可复现；
- 按最新 OpenAI plugin submission/review 清单重新核对。

“私人链接可用”“少量用户隔离通过”和“公开审核通过”是三个不同结论，必须分别报告。
