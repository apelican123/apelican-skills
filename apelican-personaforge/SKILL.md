---
name: apelican-personaforge
description: 将已有的 REST API、单个或多个 MCP 服务，以及技能背后的可调用接口转化为 ChatGPT 个人插件，让原本位于 WorkBuddy、Codex 或开发环境中的能力可以在日常聊天中直接使用；覆盖 Cloudflare Workers、公网 OAuth 2.1、OpenAI Secure MCP Tunnel、工具元数据、search/fetch 知识检索、跨平台部署、验证与回滚。用户要求把现有 API、MCP 或技能接口接入 ChatGPT 对话时使用。
---

# Plugin Forge 1.2.0

把已有的 MCP、技能背后的可调用接口和 REST API 转化为 ChatGPT 个人插件，让这些能力不再局限于 WorkBuddy、Codex 或开发环境，而能在日常 ChatGPT 对话中直接使用。

这里的“技能接口”指技能背后已经可以通过程序调用的能力。只有提示词或 Markdown 流程、没有可调用接口的 Skill，需要先实现为 API 或 MCP，不能直接把技能文件本身当作插件。

本技能不依赖其他 Codex 插件。只使用用户机器上可获得的 Node.js、npm、Cloudflare Wrangler、标准 HTTP 工具，以及用户主动选择时使用的 OpenAI Secure MCP Tunnel。

升级或改写本技能时先执行 [兼容性与回归门禁](references/compatibility-and-regression.md)：
保留旧版仍有效的目标能力，不用“主文件更短”掩盖功能丢失。每个操作步骤必须同时给出
验证方法、预期结果和停止条件；没有证据时报告缺口。

## 先确认三个问题

1. 上游是什么：REST API、单个 MCP，还是多个/超大 MCP？
2. 目标是什么：私人 Developer mode，还是准备公开发布？
3. 服务跑在哪里：Cloudflare Workers，还是本地/内网的 OpenAI Secure MCP Tunnel？

用户已给出答案时直接继续，不重复询问。凭证只确认名称和获取方式，不要求用户把密钥贴进聊天。

## 两类发布目标

| 目标 | 连接方式 | 认证基线 |
|---|---|---|
| 私人/开发 | 公网 HTTPS 或 OpenAI Tunnel | Tunnel 自身认证，或 fail-closed Bearer |
| 公开插件 | 稳定公网 HTTPS MCP | OAuth 2.1、工具级 securitySchemes、OpenAI 审核材料 |

`?token=` 只作为旧私人连接兼容。新私人连接优先 `Authorization: Bearer`；
可按需显式兼容 `X-API-Key`，公开插件不得把共享 URL token 当正式认证。
入口 token 必须统一保护整个 MCP 路由；上游服务的 Bearer、API-Key、Basic、
query、OAuth 或专有签名是另一层认证，逐服务适配，不能一律改写成 Bearer。

## 标准工作流

### 1. 盘点上游

记录端点、认证方式、工具/REST 路由、读写副作用、分页、速率限制、响应大小和是否返回 `mcp-session-id`。至少实测 initialize、tools/list 和一个无副作用调用；不从宣传页或聊天记录猜协议。

验证：产出不含密钥值的盘点表和原始响应证据；上游未实测则停止实现。

### 2. 选择实现模式

| 上游 | 模式 | 做法 |
|---|---|---|
| REST API | A 翻译 | 注册少量任务型 MCP 工具 |
| 单个 MCP | B 代理 | 流式透传、注入上游认证、保留 session |
| 多个/巨大 MCP | C 编排 | 缓存目录、限制并发、压缩工具面 |

零基础完整流程读 [quick-start.md](references/quick-start.md)。代码结构和三种模式读 [templates.md](references/templates.md)。

验证：只能选出一个主模式并解释原因；混合模式要逐段标注 A/B/C，不把 REST 误当 MCP。

### 3. 按 OpenAI 规范设计工具

执行 [openai-plugin-contract.md](references/openai-plugin-contract.md) 和 [metadata-and-results.md](references/metadata-and-results.md)：

- serverInfo 的 name/version 稳定；instructions 的关键规则放在前 512 字符；
- 工具名动作导向，title 面向人，description 说明何时用和何时不用；
- inputSchema 写清格式、单位、约束与默认值；
- 结构化返回提供对象根 outputSchema；
- 同时返回 structuredContent 与兼容文本 content；
- annotations 必须真实反映只读、破坏性、开放世界与幂等性；
- 大型 API 不直接暴露数百工具，优先任务型工具或受控 search_tools/execute_read_tool；
- 知识检索需要标准 search(query) 与 fetch(id)；没有真实 canonical URL 时不伪造引用。

验证：扫描全部工具元数据，并各用一个“应调用/不应调用”提示测试选择；schema 与真实结果互验。

### 4. 实现 Cloudflare Worker

- 使用当前 Cloudflare/MCP SDK 与无状态 handler；不要复制旧 McpAgent 架构；
- compatibility_date 使用部署日或最近已发布日期，不能写未来日期；
- Secret 不写入源码或配置；缺少认证时拒绝全部请求；
- 请求体、响应体、并发、分页、超时和重试均有界；
- 有状态上游为每个端点独立维护 session，失效最多自动重建一次。

验证：当前官方导入路径通过类型检查和 Wrangler dry-run；占位符扫描无生产遗漏。

### 5. 本地验证

依次执行：

1. 安装依赖；
2. 类型/语法检查；
3. Wrangler dry-run；
4. 本地 initialize、tools/list；
5. 每个工具的安全 fixture；
6. 无认证和错误认证；
7. JSON-RPC error 与工具 isError；
8. structuredContent 是否符合 outputSchema。

详细门槛见 [validation-and-release.md](references/validation-and-release.md)。

验证：八项均有命令输出或 fixture 结果；任一缺失只报告具体缺口。

### 6. 分服务部署

记录旧 version ID，单个 Worker 部署，等待边缘传播，再对生产 URL 重跑验证。失败只回滚该 Worker。写工具先 dry-run，经用户确认后执行，并读回结果。

验证：保存新旧 version ID、生产 auth/init/list/call 和回滚后读回证据；其他 Worker 版本不变。

### 7. 接入 ChatGPT

- 公网私人连接：[chatgpt-setup.md](references/chatgpt-setup.md)
- 本地/内网：[local-tunnel-deploy.md](references/local-tunnel-deploy.md)
- 公开发布：[openai-plugin-contract.md](references/openai-plugin-contract.md) 的 OAuth 与审核部分

界面、套餐、SDK 和审核规则可能变化；涉及“最新”时先核对官方文档。

验证：ChatGPT 工具数量与 Inspector 一致，真实只读调用成功，反向提示不误调用；多设备目标再做第二客户端回归。

## 完成标准

交付必须说明：生成/修改的文件、部署 URL、生产 version ID、工具数量、initialize/list/call/auth 的实际结果、未满足的公开审核条件以及回滚方法。HTTP 200 本身不代表 MCP 成功。

## 参考路由

- 零基础部署：[quick-start.md](references/quick-start.md)
- OpenAI 规范：[openai-plugin-contract.md](references/openai-plugin-contract.md)
- 元数据与结果：[metadata-and-results.md](references/metadata-and-results.md)
- 实现模板：[templates.md](references/templates.md)
- 验证发布：[validation-and-release.md](references/validation-and-release.md)
- 安全检查：[security-checklist.md](references/security-checklist.md)
- 协议速查：[mcp-protocol-basics.md](references/mcp-protocol-basics.md)
- 故障排查：[troubleshooting.md](references/troubleshooting.md)
- 历史踩坑：[pitfall-log.md](references/pitfall-log.md)（历史证据不覆盖当前规范）
- 兼容性回归：[compatibility-and-regression.md](references/compatibility-and-regression.md)
- 跨设备使用：[cross-device-use.md](references/cross-device-use.md)
- 工作原理：[how-it-works.md](references/how-it-works.md)
- 脱敏设计示例：[deployed-services.md](examples/deployed-services.md)
