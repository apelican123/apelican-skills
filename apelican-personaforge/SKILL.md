---
name: apelican-personaforge
description: 把用户已有的 REST API 或 MCP 铸造成 ChatGPT 可直接使用的插件：AI 获取用户的 Cloudflare API Token 后，自动设计工具面、生成 Worker、部署到 Cloudflare、输出可粘贴进 ChatGPT 的链接。用户提到铸造、GPT 插件、MCP、Cloudflare、自动生成链接、部署时使用。默认铸造模式。只有提示词没有可调用接口时先说明缺口。
---

# Plugin Forge 4.0 / 全自动铸造机

用户只需要做两件事：**准备一个 Cloudflare 账号，说出要接什么服务**。剩下的——设计工具、写 Worker、部署、生成链接、验证——全部由你自动完成。最终交付一条形如 `https://<你的Worker>.workers.dev/u/<随机令牌>/mcp` 的链接，用户把它粘进 ChatGPT 的 Add MCP server 就能开始用。

本技能的规范基线日期是 **2026-08-29**。实现前核对 OpenAI、MCP 和 Cloudflare 当前官方文档；官方契约优先于本技能的旧审计规则、旧截图和历史经验。

## 默认铸造模式

本技能默认就是铸造模式：用户报出服务后，直接按下面的流程走到「输出链接」为止，不先出方案等确认。设计决策（工具数量、认证方式、读写边界）由你按本技能规则自动做出，只在真正需要用户拍板时（公开发布、写操作、OAuth、删除类工具）停下来问。

只有用户明确只要方案、不要部署时，才退回到「设计模式」只输出交付说明。

## 用户唯一的两个手动步骤

1. **注册/登录 Cloudflare**，生成一个 API Token（权限仅勾 Workers Scripts: Edit），并复制 Account ID。账号注册和登录必须由用户本人完成——你无法也不会替用户注册账号或输入密码。
2. **把上游接口交给你**：MCP 服务地址 + 密钥，或 REST API 地址 + 密钥，或直接说清你有哪些接口。

其余全部自动：你负责生成 Worker 代码、调用 Cloudflare Workers API 上传、写入密钥、启用 workers.dev、拼出链接、验证链接可用、给出 ChatGPT 配置步骤。

## 工作流

### 1. 确认目标与边界

收集（能推断的不重复问）：

- 要在 ChatGPT 完成什么任务；
- 当前是 REST API、单个 MCP、多个 MCP，还是只有想法；
- 只读、写入、删除、付款或对外发送等副作用；
- 自用、小圈子，还是准备公开发布。

只有提示词或 Markdown 流程、没有可调用接口时，明确说明还缺 API/MCP，不制造「上传文档就会自动变成插件」的假象。

### 2. 引导 Cloudflare 准备（用户手动）

按 [cloudflare-deploy.md](references/cloudflare-deploy.md) 的「准备 Cloudflare」章节逐步引导：

1. 打开 https://dash.cloudflare.com 注册或登录；
2. 若首次使用 Workers，完成 workers.dev 子域首启；
3. 创建 API Token：My Profile → API Tokens → Create Token → 自定义，仅授予 `Workers Scripts` 的 `Edit` 权限；
4. 复制 Account ID（dashboard 首页右侧或 Workers 概览页）。

收集到 `CF_API_TOKEN` 与 `CF_ACCOUNT_ID` 后，进入下一步。Token 仅用于本次部署的 API 调用，不回显、不落盘；交付出链接后建议用户删除该 Token。

### 3. 收集上游凭据并设计

按 [tool-design.md](references/tool-design.md) 自动设计工具面：先最小化、按副作用分层、写操作单独注册。同时按 [auth-and-secrets.md](references/auth-and-secrets.md) 确定认证方式：

- **默认**：`noauth` + 路径随机令牌（用户数据不隔离、无写操作、自用或小圈子时），ChatGPT 端选 No authentication；
- 仅当多用户各自数据、scope 化工具、公开产品、必须撤销/审计时才选 OAuth 2.1，并明确告知更麻烦、ChatGPT 端可能验证失败。

上游 API Key / Bearer 只作为运行时 Secret 使用，由你写入 Cloudflare Worker Secret，不进入代码、回复或日志。

### 4. 生成 Worker 代码

按 [templates.md](references/templates.md) 生成 Worker：

- 单个 REST API：翻译为任务型 MCP 工具（每个端点一个工具，按最小工具面原则合并）；
- 单个 MCP：透传代理，注入上游密钥，加路径令牌校验；
- 多 MCP：聚合目录 + 静态只读 allowlist，压缩为目录搜索与受控只读执行入口；
- 本机/内网服务：建议 OpenAI Secure MCP Tunnel，不走 Cloudflare。

代码必须是**零依赖**（不引入 npm 包、不需要构建步骤），保证任何用户上传即可运行。

### 5. 部署到 Cloudflare

按 [cloudflare-deploy.md](references/cloudflare-deploy.md) 的「自动部署」章节调用 Cloudflare Workers API：

1. 查询 workers.dev 子域（`GET /accounts/{account_id}/workers/subdomain`）；
2. 上传脚本（`PUT /accounts/{account_id}/workers/scripts/{script_name}`，multipart：worker 代码 + metadata，`workers_dev: true`）；
3. 写入 Secret（上游 API Key、路径令牌、其他密钥，逐个 `PUT .../secrets`）；
4. 组装链接：`https://<script_name>.<subdomain>.workers.dev/u/<令牌>/mcp`（无令牌需求时也至少校验随机路径，不停留在裸 `/mcp` 匿名暴露私人数据）。

所有命令同时提供 bash 与 PowerShell 版本（见 cloudflare-deploy.md）。不要在命令参数里带真实密钥；Secret 通过 API 的 JSON 请求体或交互式输入传递，用完即清。

### 6. 验证并交付

按 [verification.md](references/verification.md) 在部署后立即验证：

- `POST /mcp` 的 `initialize` 返回正确 protocolVersion 与 serverInfo；
- `tools/list` 返回预期工具清单（数量、名称与设计一致）；
- 错误令牌访问返回 401/403；
- 需要时执行一次获准的只读 `tools/call`，确认上游能通。

验证通过后交付：

- 完整链接（放入对话；同时提示用户妥善保管，链接即凭据）；
- ChatGPT 配置三步：Add MCP server → 粘贴链接 → 认证选 No authentication；
- 验收状态按 [acceptance-checklist.md](references/acceptance-checklist.md) 分层说明；
- 若用户曾把上游密钥粘贴进对话，交付时附一句「建议在上游后台轮换」。

## OAuth 何时才考虑

见 [auth-and-secrets.md](references/auth-and-secrets.md)。默认不选 OAuth。只有「大量用户／独立账户数据／复杂 scope／公开发布」四者之一成立且用户确认后才走 OAuth，且必须单独核对官方文档、明示验证失败风险。

## 权限边界

- 可以：读取用户主动提供的凭据并仅用于本次部署调用；调用 Cloudflare Workers API；生成本地临时文件（部署后清理）；生成并交付链接；执行获准的只读验证。
- 不可以：把任何 API Key / Token / Secret 写入技能文件、GitHub、日志、审计输出或回复正文；用命令参数明文传递密钥；替用户注册账号或输入密码；超出用户授权部署或删除服务；把「能访问」「能连接」说成「插件已可用、全部测试通过」。
- 链接按凭据处理：完整能力 URL 不回显到公开位置；推测泄露或用户要求时指导轮换（新 URL 生成后旧 URL 必须失效）。

## 表述要求

- 「建议」「待实施」「用户确认」「未验证」必须与事实一致。
- 不能把 HTTP 200、找到工具列表或写出代码方案说成插件已可用。
- `noauth` 描述 ChatGPT 是否需要 OAuth，不等于服务器可以匿名暴露私人数据。
- 平台未给具体驳回原因时，只能陈述风险推断，不能宣称找到唯一原因。
- 官方文档可能更新；部署前按 [official-sources.md](references/official-sources.md) 重新核对。

## 参考路由

- 新手最短路径：[quick-start.md](references/quick-start.md)
- Cloudflare 部署与 API：[cloudflare-deploy.md](references/cloudflare-deploy.md)
- Worker 代码模板：[templates.md](references/templates.md)
- 工具面设计：[tool-design.md](references/tool-design.md)
- 认证与 Secret：[auth-and-secrets.md](references/auth-and-secrets.md)
- 部署后验证：[verification.md](references/verification.md)
- 验收清单：[acceptance-checklist.md](references/acceptance-checklist.md)
- 故障排查：[troubleshooting.md](references/troubleshooting.md)
- 历史踩坑：[pitfall-log.md](references/pitfall-log.md)
- 官方来源：[official-sources.md](references/official-sources.md)