# 安全检查清单

## 一人一链接

- [ ] 默认由每位使用者在自己的 Cloudflare 账号部署；共用 Worker 仅用于少量人工管理的可信用户。
- [ ] 用户名只生成可识别标签和短哈希，没有被当作密码或 Token 种子。
- [ ] 每位用户的 Token 独立使用 CSPRNG 生成，至少 256 bit；不同用户没有复用 Token。
- [ ] URL 使用 `/u/<userId>/<token>/mcp` 或等价的用户名标识 + 随机 Token 结构。
- [ ] Cloudflare 只保存每位用户 Token 的 SHA-256 摘要，并做常量时间比较。
- [ ] 缺少用户 Secret、未知用户、错误 Token 和错误路径全部 fail closed，返回 401/403/404。
- [ ] A 用户 Token 放入 B 用户路径会被拒绝；多人 Worker 已实际运行跨用户错配测试。
- [ ] 每位用户可单独撤销和轮换，不影响其他链接。
- [ ] 完整 URL 未进入源码、Git、截图、聊天示例、公开文档、浏览器分析或完整路径日志。
- [ ] 已提示完整链接就是访问密钥；泄露处理是立即撤销和轮换，不只是口头提醒。

## 上游数据隔离

- [ ] 上游 API Key/Client ID 只保存在 Cloudflare Secrets 或受保护运行时，未填入 ChatGPT。
- [ ] 入口链接隔离与上游数据隔离分别设计；没有用共享管理员密钥假装每人数据独立。
- [ ] 需要用户级数据时，每位用户使用对应上游身份、scope 或 OAuth 映射。
- [ ] 大量用户、自动注册/回收、组织权限或公开发布已切换 OAuth 2.1。
- [ ] OAuth 工具声明准确 `securitySchemes` 和 scope，并在生产 `tools/list` 实测可见。
- [ ] OAuth scope 不足的工具错误带 `_meta["mcp/www_authenticate"]` 和可用 challenge。

## ChatGPT 与 Cloudflare 的职责

- [ ] 专属链接在 ChatGPT 端选择“无身份验证”，但固定 `/mcp` 没有匿名开放私人数据。
- [ ] ChatGPT 中没有上游 API Key、Token 摘要、Cloudflare Secret 或 OAuth client secret。
- [ ] 专属链接模式的工具没有错误残留 OAuth scheme；OAuth 模式也没有伪装成 no-auth。
- [ ] Worker 请求日志不记录完整能力路径；invocation logs/traces 按此风险关闭或证明已脱敏。

## 工具与权限

- [ ] 读取、写入、删除、支付、发帖、发信的 annotations 与真实行为一致。
- [ ] 高风险操作有明确参数、用户确认、幂等/重试边界和执行后读回。
- [ ] 通用执行器不能绕过写工具 allowlist/denylist。
- [ ] 错误结果不包含堆栈、内部 URL、认证头、密钥或敏感原文。
- [ ] 每个用户和 scope 只能访问其授权数据。

## 网络、资源和 Cloudflare

- [ ] 所有生产连接使用 HTTPS；本地 Tunnel 只监听 loopback。
- [ ] 上游请求有超时、有限重试和并发上限；写入不盲目自动重试。
- [ ] 请求体、响应体、分页和文档分块都有大小上限。
- [ ] 未知大响应使用流式透传；需要解析时先做有界读取。
- [ ] `compatibility_date` 是已发布日期，需要 Node API 时启用当前要求的兼容配置。
- [ ] 新 stateless 服务使用当前 `createMcpHandler`；不新建已弃用 `McpAgent` 结构。
- [ ] 部署前 dry-run，部署后记录 version ID 和单服务回滚目标。

## 验证

- [ ] `initialize`、`notifications/initialized`、`tools/list`、`ping` 正常。
- [ ] 正确链接成功；错误 Token、未知用户和跨用户错配失败。
- [ ] 每个工具至少用一个有效输入；关键工具另测无效输入和上游失败。
- [ ] JSON-RPC error 与工具 `isError` 都检查，不能只看 HTTP 200。
- [ ] `outputSchema` 与 `structuredContent` 一致。
- [ ] 有状态上游 session 失效时最多重建一次。
- [ ] 公开审核前重新核对 OpenAI 官方 auth、metadata、submission 和 review 文档。
