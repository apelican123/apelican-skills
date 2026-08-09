# 安全检查清单

## 认证

- [ ] 私人入口鉴权位于整个 `/mcp` handler 之前，覆盖 POST、GET/SSE、notification 与会话 DELETE。
- [ ] 私人公网连接优先 Bearer；URL token 和 API-Key Header 仅通过显式开关兼容旧连接。
- [ ] 入口 token 与上游 token 分离；上游认证按 Bearer、API-Key、Basic、query、OAuth 或专有签名逐项确认。
- [ ] 公开插件实现 OAuth 2.1、PKCE、scope 和工具级 securitySchemes。
- [ ] 缺少认证配置时 fail closed；无凭证和错误凭证均被拒绝。
- [ ] 令牌来自安全随机生成器，比较时使用摘要后常量时间比较。
- [ ] 密钥只在 Secrets/安全环境，不在源码、配置、日志、截图和 Git。

## 工具权限

- [ ] readOnly/destructive/openWorld/idempotent 与真实行为一致。
- [ ] 写入、删除、支付、发帖、发信有明确确认与执行后读回。
- [ ] 通用执行器不能绕过 allowlist 执行写工具。
- [ ] 工具只访问当前授权用户与 scope 允许的数据。

## 资源边界

- [ ] 上游请求有超时、并发上限和有限重试。
- [ ] 请求体、响应体、分页和文档分块有硬上限。
- [ ] 未知大响应使用流式转发；需要解析时先做有界读取。
- [ ] 非幂等写入不自动重试，或使用幂等键。
- [ ] 日志脱敏，不含 Authorization、cookie、token 或私人正文。

## 部署

- [ ] compatibility_date 不是未来日期。
- [ ] 需要 Node API 时启用 nodejs_compat。
- [ ] 无持久状态时使用 stateless handler，不新建旧 McpAgent。
- [ ] dry-run 成功；保存旧 version ID。
- [ ] 生产 auth/init/list/call 回归成功。
- [ ] 已测试客户端实际使用的认证载体；启用兼容开关时同时测试 Header 与旧 query 路径。

## 公开前

- [ ] OAuth 全流程、隐私政策、支持链接和审核说明齐全。
- [ ] 生产入口为稳定 HTTPS，不依赖本机 Tunnel。
- [ ] 重新核对 OpenAI 最新 auth、metadata 和 app review 文档。
