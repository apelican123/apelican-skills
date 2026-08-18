---
name: apelican-personaforge
description: 把已有的 REST API、单个或多个 MCP 服务，以及技能背后的可调用接口做成 ChatGPT 个人插件；默认用 Cloudflare 生成一人一条的专属能力链接，让普通用户在 ChatGPT 选择“无身份验证”并粘贴链接即可接入，同时覆盖 OAuth 2.1、OpenAI Secure MCP Tunnel、工具设计、验证、部署和回滚。用户提到插件铸造、GPT 个人插件、MCP 网关、Cloudflare MCP、插件审核或 Secure MCP Tunnel 时使用。
---

# Plugin Forge 2.0 / 插件铸造器

把已经能通过程序调用的能力带进 ChatGPT 日常对话。用户不需要先懂“隧道、MCP、OAuth、GPT 链接”这些术语；先弄清他手里有什么、最后想在 ChatGPT 里做什么，再一步一步带到可用。

只有提示词或 Markdown 流程、没有 API 或 MCP 接口的 Skill，不能直接变成插件。此时先用普通话说明“还缺一个可调用接口”，再帮助确定是否需要新建 API/MCP。

本技能的规范基线日期是 **2026-08-18**。开始实现前核对 OpenAI、MCP 与 Cloudflare 官方文档；ChatGPT 页面名称、审核规则和 SDK 可能变化。

## 2.0 交互原则

1. **先说结果，不先上课**：用“把你的某项能力放进 ChatGPT”解释目标；只有当前步骤需要时才解释术语。
2. **一次只推进一个可检查动作**：能从本机文件、项目配置或官方文档得到的信息直接读取，不反复问用户。
3. **每一步都有回应**：按 [新手引导与进度反馈](references/onboarding-and-progress.md) 回报“已完成、你会看到、下一步、异常分支”。
4. **默认走最短私人路径**：单人自用优先“专属能力链接”；ChatGPT 端选择“无身份验证”，只粘贴完整链接。
5. **链接不是公开地址**：完整链接同时就是访问密钥。任何拿到它的人都可能使用对应能力；不得截图、公开、转发或写入日志。
6. **安全要求不能用简化体验换掉**：上游密钥只放 Cloudflare Secrets；缺少认证配置时 fail closed；部署、写操作和公开发布仍遵守确认边界。

## 默认安全模型：一人一条专属能力链接

私人自用默认生成：

```text
https://<你的-worker-域名>/u/<用户名标识>/<高强度随机Token>/mcp
```

- “用户名标识”只负责区分用户，必须经过规范化并附加短哈希；**不能把用户名本身当密码，也不能从用户名推算 Token**。
- 每位用户生成独立的至少 256 bit 随机 Token；Cloudflare 只保存 Token 的 SHA-256 摘要，逐次做常量时间比较。
- 最稳妥的默认是每位使用者在自己的 Cloudflare 账号中部署自己的 Worker。一个 Worker 管理少量可信用户时，也必须一人一摘要 Secret、一人一 URL，并验证 A 用户的 Token 放到 B 用户路径后会被拒绝。
- 链接隔离只保护“谁能调用这个入口”。如果上游数据本身分用户，还必须使用各自的上游凭据/scope；不能让所有链接共用一个能读取全部用户数据的上游管理员密钥。
- 链接泄露时只撤销和轮换该用户的摘要 Secret，不影响其他用户。

这在 ChatGPT 表单里属于“无身份验证”，因为 ChatGPT 不再单独保存认证字段；**验证仍由 Cloudflare 完成，并不是 Worker 匿名开放**。固定 `/mcp` 不得直接对私人数据匿名开放。

专属链接适合单人自用或少量、人工管理的可信用户。大量用户、独立账号/scope、组织级权限或公开插件使用 OAuth 2.1；公开发布还需要 OpenAI 审核。Secure MCP Tunnel 只用于本机/内网私人开发连接。

## 两层密钥不要混在一起

- **上游凭据**：IMA、SiYuan 或其他服务的 API Key/Client ID，只放 Cloudflare Secrets 或受保护运行时，绝不填进 ChatGPT。
- **入口凭据**：专属能力链接中的随机 Token，或 OAuth access token，用来保护公网 MCP 入口。

## 从零到可用的主流程

### 1. 用普通话确认目标

先确认三件事：

- 想把什么能力带进 ChatGPT；
- 目前有 REST API、MCP 地址，还是只有一个 Skill/想法；
- 是自己用、少量可信用户用，还是准备公开发布。

不要一开始要求用户自己选择“翻译、代理、编排”等工程模式。由技能根据材料判断并解释结果。完整提问顺序见 [新手引导与进度反馈](references/onboarding-and-progress.md)。

### 2. 读取现有材料并实测上游

读取最近的项目说明、`AGENTS.md`、Worker 源码和 `wrangler` 配置；只记录 Secret 名称，不读取或打印值。对上游至少实测：

1. `initialize`；
2. `tools/list`；
3. 一个无副作用的 `tools/call`；
4. 错误认证；
5. 超时、非 JSON、SSE 与过大响应。

若上游返回 `mcp-session-id`，后续请求必须回带；会话失效最多自动重建一次。

### 3. 选择实现方式

| 用户手里的东西 | 实现方式 | 默认处理 |
|---|---|---|
| REST API | 翻译成 MCP | 用当前 MCP SDK 和 Cloudflare stateless handler 注册任务型工具 |
| 单个 MCP | 安全代理 | 尽量流式透传，只在必要时修正元数据 |
| 多个 MCP / 巨大 API | 编排 | 缓存目录、限制并发、压缩为少量高价值入口 |

代码生成前读 [Cloudflare 实现模板](references/templates.md)。新 stateless 服务优先当前 `createMcpHandler`；不要复制已弃用的 `McpAgent` 新模板。

### 4. 让 ChatGPT 容易正确调用

读 [OpenAI 插件契约](references/openai-plugin-contract.md) 和 [元数据与结果](references/metadata-and-results.md)：

- 工具名稳定、动作开头；
- `title` 给人看，`description` 写清何时用和何时不用；
- 参数说明语义、单位、格式、默认值和限制；
- 准确声明读取、写入、删除、开放网络和幂等性；
- 有结构化结果时同时提供对象根 `outputSchema`、`structuredContent` 和可读 `content`；
- 大型 API 不直接暴露数百工具，优先任务型工具或受控的搜索/执行入口。

公司知识或文档检索需要 OpenAI 标准路径时，实现只读 `search(query)` 与 `fetch(id)`。

### 5. 创建用户专属链接并在 Cloudflare 验证

按 [快速开始](references/quick-start.md) 生成用户标识、随机 Token、摘要 Secret 和专属 URL。一个 Worker 管理多位可信用户时，逐人创建，不复用 Token，不共享摘要 Secret。

执行 [安全检查清单](references/security-checklist.md)。核心门槛：

- 错用户名、错 Token、缺 Secret 一律拒绝；
- 完整 URL 不进入源码、Git、截图、示例、分析工具或完整路径日志；
- 每个链接可独立撤销和轮换；
- 写入、删除、支付、发帖等工具要求明确确认和执行后读回；
- 输入、响应体、并发、超时和日志均有界；
- 不回传堆栈、密钥、上游认证头或内部 URL。

### 6. 本地检查与生产部署

先运行：

```powershell
npm test
npx tsc --noEmit
npx wrangler deploy --dry-run
node <skill-dir>/scripts/audit-mcp.js
```

环境变量、跨用户隔离检查和 fixture 格式见 [验证与发布](references/validation-and-release.md)。不能只看 HTTP 200；必须检查 JSON-RPC error 和工具结果的 `isError`。

部署前记录旧生产 version ID；使用 `wrangler deploy --keep-vars` 单服务部署，完成真实只读回归。写操作先 dry-run，再经用户确认执行并读回；失败只回滚当前 Worker。

### 7. ChatGPT 接入

读 [ChatGPT 接入](references/chatgpt-setup.md)：

- 专属能力链接：ChatGPT 选择“无身份验证”，粘贴完整 URL；Cloudflare 负责验证。
- OAuth 服务：选择 OAuth，并依赖 DCR/CIMD 或当前支持的客户端注册方式；上游 API Key 不填入 ChatGPT。
- Secure MCP Tunnel：按 [本地隧道](references/local-tunnel-deploy.md) 连接本机/内网能力。

接入后核对工具数量和读写提示，调用一个真实只读工具，并再次提示“完整链接就是访问密钥”。

## 完成标准

交付时用普通话报告：

- 最终能在 ChatGPT 里做什么；
- 修改和部署了哪些服务、生产 version ID；
- 使用专属链接、OAuth 还是 Tunnel；
- `initialize`、`tools/list`、真实只读调用和错误认证结果；
- 专属链接的用户名标识、独立撤销/轮换方法和泄露风险（不回显真实链接）；
- 多用户时的错用户/错 Token 隔离结果；
- 工具数量、隐藏的高风险工具及原因；
- 仍不满足的公开审核或权限隔离条件；
- 回滚路径和未触碰的系统。

## 参考路由

- 新人对话、每步反馈与暂停点：[onboarding-and-progress.md](references/onboarding-and-progress.md)
- 从零部署和创建用户链接：[quick-start.md](references/quick-start.md)
- ChatGPT 端怎么填：[chatgpt-setup.md](references/chatgpt-setup.md)
- Cloudflare 三种实现与用户链接校验：[templates.md](references/templates.md)
- 当前 OpenAI/MCP 要求：[openai-plugin-contract.md](references/openai-plugin-contract.md)
- 工具描述、schema、返回和引用：[metadata-and-results.md](references/metadata-and-results.md)
- 自动审计、fixture、发布门槛：[validation-and-release.md](references/validation-and-release.md)
- 安全检查：[security-checklist.md](references/security-checklist.md)
- 常见报错：[troubleshooting.md](references/troubleshooting.md)
- OpenAI 官方隧道：[local-tunnel-deploy.md](references/local-tunnel-deploy.md)
- 协议速查：[mcp-protocol-basics.md](references/mcp-protocol-basics.md)
- 历史踩坑（不能覆盖当前官方规范）：[pitfall-log.md](references/pitfall-log.md)
