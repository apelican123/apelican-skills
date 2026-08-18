# 兼容性与回归门禁

升级本技能时，只能新增能力、修正错误或用可证明更可靠的实现替换旧实现。不能因为主文件变短，
就丢失部署模式、认证载体、操作系统、协议生命周期、排障路径或验证证据。

## 不得倒退的能力

| 能力面 | 最低保留范围 | 验证证据 |
|---|---|---|
| 上游类型 | REST、单 MCP、多 MCP/巨大目录 | A/B/C 各有实现路径与专属门禁 |
| 私人入口认证 | 默认一人一条用户名标识 + 256 bit 随机 Token 专属链接；旧 Bearer/query 只作明确兼容；每人可独立轮换 | 正确链接、错误 Token、未知用户和跨用户错配矩阵通过 |
| 上游认证 | Bearer、自定义 Header、Basic、query、OAuth access token、无认证；专有签名有适配边界 | 上游无副作用实测，不用入口 token 冒充上游 token |
| MCP 传输 | JSON、SSE、notification、ping、session header | init/initialized/ping/list/call 与 session 失效测试 |
| 部署路径 | Cloudflare Workers、OpenAI Secure MCP Tunnel | 两条路径各自有逐步验证；不要求同时运行 |
| 平台 | Windows PowerShell、macOS/Linux bash | 关键创建、验证、Secret 与诊断命令双平台可执行 |
| 模型易用性 | instructions、title/description、schema、structuredContent、annotations、search/fetch | 元数据扫描与正反向工具选择提示 |
| 运维 | dry-run、生产回归、日志脱敏、version ID、单服务回滚 | 发布记录可读回 |
| 新手可用性 | 不要求先懂术语；一次一个动作；每步含已完成、预期、下一步和异常分支 | [onboarding-and-progress.md](onboarding-and-progress.md) 与 [quick-start.md](quick-start.md) 完整 |
| 多设备 | Markdown + 页面已支持的 JavaScript 工具、每用户专属 URL、Tunnel 主机边界、第二设备只读回归 | [cross-device-use.md](cross-device-use.md) 清单通过 |

## 对抗性场景

发布前逐一尝试证明实现会失败：

1. 同一用户名重复生成链接时 `userId` 漂移，导致无法只轮换 Token；
2. A 用户 Token 放进 B 用户路径仍能通过，或不同链接共用同一个全局 Token；
3. 上游使用自定义 Header、Basic 或 query，却被强制改成 Bearer；
4. initialize 成功，但 initialized、ping、list 或 call 失败；
5. HTTP 200 包含 JSON-RPC error 或 `result.isError=true`；
6. SSE 被 `response.text()` 缓冲，长请求超时；
7. 有状态上游的 session 在多个服务间串用；
8. 多 MCP 同名工具静默覆盖或通用执行器调用写工具；
9. Windows 命令能用，bash 不可用，或反过来；
10. 第二设备缺少本机绝对路径、隐含插件或私人 MCP 后无法使用，或公开包丢失 `.js` 工具；
11. 文档仍含占位 URL、未来 compatibility date、真实 Secret 或私人路径；
12. 旧版的排障能力被删除，只剩“查看日志”；
13. 公开 OAuth 要求被私人共享 token 冒充；
14. 为追求“完整模板”复制手写残缺 MCP 协议或无界聚合器；
15. 生成 ZIP 后目录层级错误、文件缺失、扩展名未被目标平台支持或哈希与审计时不一致；
16. 专属链接隔离成功，但上游仍使用共享管理员凭据读取所有用户数据。

## 替换不等于倒退

只有同时满足下列条件，才可把旧实现判为“被替换”而非“被删除”：

- 新路径仍完成同一用户目标；
- 旧实现的具体缺陷有证据，例如旧 SDK 导入、无界缓冲或不安全兜底执行；
- 新路径有等价或更强的逐步验证；
- 迁移说明告诉旧用户如何继续使用；
- 无法自动验证的部分明确标成缺口，不用文档篇幅代替可用性证据。

## 发布判定

只有以下全部成立才可写“无已知功能倒退”：

1. 上表所有能力都有当前文件和验证证据；
2. 对抗性场景逐项通过或有明确、不影响发布目标的边界；
3. 模板使用当前官方导入路径并通过类型检查与 Wrangler dry-run；
4. 所有相对链接、Markdown 与已支持 JavaScript 文件、脱敏和跨平台扫描通过；
5. 发布 ZIP 解压后再次运行技能结构、文件清单和哈希验证。

“未发现倒退”不等于证明所有第三方 API 都兼容。专有认证、私有协议和真实生产行为必须在
用户提供目标服务后端到端验证。
