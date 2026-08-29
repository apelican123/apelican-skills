# 部署后验证

链接交出前必须验证，不能把「能访问」说成「已可用」。以下命令以 `MCP_URL` 表示最终链接（`https://<脚本名>.<subdomain>.workers.dev/u/<令牌>/mcp`）。

## 1. 错误令牌应被拒绝（先验证安全层）

```bash
# bash：用一个错误令牌路径访问
curl -s -o /dev/null -w "%{http_code}\n" "https://<脚本名>.<subdomain>.workers.dev/u/错误令牌/mcp" -X POST \
  -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
# 预期：401
```

```powershell
# PowerShell
curl.exe -s -o NUL -w "%{http_code}`n" "https://<脚本名>.<subdomain>.workers.dev/u/错误令牌/mcp" -X POST -H "Content-Type: application/json" -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\"}'
# 预期：401
```

## 2. initialize

```bash
# bash
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"1.0"}}}'
```

```powershell
# PowerShell
curl.exe -s -X POST "$env:MCP_URL" -H "Content-Type: application/json" -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-03-26\",\"capabilities\":{},\"clientInfo\":{\"name\":\"verify\",\"version\":\"1.0\"}}}'
```

预期：`result.protocolVersion` 与 `result.serverInfo` 存在，`success` 不适用（直接看 body 结构）。

## 3. tools/list

```bash
# bash
curl -s -X POST "$MCP_URL" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

```powershell
# PowerShell
curl.exe -s -X POST "$env:MCP_URL" -H "Content-Type: application/json" -d '{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\"}'
```

预期：`result.tools` 数组存在，工具名称、数量与设计一致（对照 tool-design 的表格逐项核对）。

## 4. 获准的只读 tools/call（可选，但强烈建议）

取得用户同意后，用一个无副作用工具跑一次真实调用，确认上游连通：

```bash
# bash
curl -s -X POST "$MCP_URL" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"<只读工具名>","arguments":{...}}}'
```

预期：`result.content` 或 `result.structuredContent` 有值；若返回 `error`，查上游连通性（[troubleshooting.md](troubleshooting.md)）。

## 验证通过标准

- [ ] 错误令牌返回 401；
- [ ] initialize 返回协议版本与 serverInfo；
- [ ] tools/list 工具面与设计一致（无多余、无遗漏、无写工具混入只读区）；
- [ ] （用户同意时）至少一次只读真实调用成功；
- [ ] 上游 5xx / 认证失败时返回的差异可被 ChatGPT 理解（错误信息不含密钥）。

全部通过后，才把链接与 ChatGPT 配置步骤交付用户。