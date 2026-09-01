---
name: apelican-personaforge
description: 把已有 API 或 MCP 铸成 ChatGPT 私人插件。登录 Cloudflare 后自动在 Workers 部署，给出可粘贴的链接。用于 GPT 插件、ChatGPT 插件、ChatGPT 连接器、MCP、铸造、Cloudflare Workers、自动部署。只有提示词没有可调用接口时先说明缺口。
---

# Plugin Forge 4.0.1 / 全自动铸造机

小白路径只有三步：

1. 用户自己注册/登录 Cloudflare，创建一个 API Token，把 Account ID 和 Token 交给你。
2. 用户说出要接的 API 或 MCP（地址 + 密钥）。
3. 你自动部署，交出一条 `https://<脚本名>.<子域>.workers.dev/u/<令牌>/mcp`，再按官方步骤让用户接到 ChatGPT 插件。

账号注册、登录、创建 Token 必须由用户本人完成。其余（写 Worker、调 Cloudflare API、打开 workers.dev、验证、给 ChatGPT 配置步骤）全部由你做。

规范基线日期 **2026-08-29**。部署前核对 OpenAI / MCP / Cloudflare 当前官方文档；官方契约优先于本技能旧示例。

## 运行前提（先说清楚）

本技能要在**能写文件、能发 HTTPS 请求**的 AI 里跑（Hermes、Codex、Claude Code、Cursor 等）。纯网页版 ChatGPT 没有部署能力，不能假装已经自动上线。

默认铸造模式：用户报出服务后直接走到「输出链接」，不先出方案等确认。只在公开发布、写操作、OAuth、删除类工具时停下来问。用户明确只要方案时，才退回设计模式。

## 工作流

### 1. 确认目标

收集（能推断的不重复问）：要在 ChatGPT 完成什么；REST / 单 MCP / 多 MCP / 只有想法；读写副作用；自用还是公开发布。

只有提示词、没有可调用接口时，说明还缺 API/MCP，不制造「上传文档就会变成插件」的假象。本机/内网服务改走 OpenAI Secure MCP Tunnel，不走 Cloudflare。

### 2. 引导 Cloudflare（用户手动）

按 [cloudflare-deploy.md](references/cloudflare-deploy.md) 逐步引导，直到你拿到两样东西：`CF_ACCOUNT_ID`、`CF_API_TOKEN`。

Token 权限：控制台勾 `Account` → `Workers Scripts` → `Edit`（API 名是 `Workers Scripts Write`）。不要给 Global Key。

首次用 Workers 必须先在控制台启用 `workers.dev` 子域，否则后面没有公开 URL。

Token 只用于本次部署，不回显、不落盘；交付后建议用户删除该 Token。

### 3. 设计并生成 Worker

按 [tool-design.md](references/tool-design.md) 压缩工具面。按 [auth-and-secrets.md](references/auth-and-secrets.md) 默认用 **noauth + 路径令牌**；OAuth 只在多用户各自数据 / 公开产品 / 必须撤销审计时才考虑，并明示更麻烦、ChatGPT 端可能验证失败。

按 [templates.md](references/templates.md) 生成**零依赖** `worker.js`：

- REST → `REST_TOOLS`（必须改成用户的真实 URL，禁止留下 `api.example.com`）
- 单 MCP → `MCP_UPSTREAM`，上游密钥走 Secret，不写进代码
- 多 MCP → 来源路由 + 静态 allowlist

用 `secrets.token_hex(32)` 生成 `LINK_TOKEN`。Secret 和 URL 使用**同一段明文**，不要哈希后再比较。

### 4. 部署（你执行，用户不碰命令）

按 [cloudflare-deploy.md](references/cloudflare-deploy.md) 用 Python 调 Cloudflare API，不要让用户复制 curl：

1. `GET /accounts/{id}/workers/subdomain` 取账号子域
2. `PUT /accounts/{id}/workers/scripts/{name}` 上传模块（`main_module` + `application/javascript+module`）
3. `PUT .../secrets` 写入 `LINK_TOKEN`、`UPSTREAM_KEY`
4. `POST .../scripts/{name}/subdomain` `{"enabled": true}` —— **这一步不能省**，metadata 里的 `workers_dev` 官方不认
5. 组装 `https://{name}.{subdomain}.workers.dev/u/{LINK_TOKEN}/mcp`

### 5. 验证后交付

按 [verification.md](references/verification.md)：

- 错误令牌 → 401
- GET → **405**（本模板不提供 SSE）
- `notifications/initialized` → **202 空 body**
- initialize 回显客户端 `protocolVersion`，带 `serverInfo`
- tools/list 与设计一致

通过后交付完整链接，再按 [chatgpt-setup.md](references/chatgpt-setup.md) 引导 ChatGPT：

1. Settings → Security and login → 打开 Developer mode
2. 打开 https://chatgpt.com/plugins → 点 +
3. 填名称，Connection 粘贴完整 URL（含 `/mcp`），认证选 No authentication
4. 新开对话，从工具菜单启用这个连接

不要写「Add MCP server」这种已经对不上界面的句子。Developer mode 可能因账号/工作区关闭；打不开就如实说，不要说插件已经接好。

## 权限边界

- 可以：使用用户主动给的 Token 调 Cloudflare API；写临时文件（用完删）；交付链接；做获准的只读验证。
- 不可以：把密钥写入技能/Git/日志/回复正文；替用户注册或输入密码；把「能访问」说成「ChatGPT 已可用」。
- 链接即凭据。泄露则重写 `LINK_TOKEN` Secret，旧 URL 必须失效。

## 参考

- 最短路径：[quick-start.md](references/quick-start.md)
- 部署 API：[cloudflare-deploy.md](references/cloudflare-deploy.md)
- Worker 模板：[templates.md](references/templates.md)
- ChatGPT 接入：[chatgpt-setup.md](references/chatgpt-setup.md)
- 工具面：[tool-design.md](references/tool-design.md)
- 认证：[auth-and-secrets.md](references/auth-and-secrets.md)
- 验证：[verification.md](references/verification.md)
- 验收：[acceptance-checklist.md](references/acceptance-checklist.md)
- 排障：[troubleshooting.md](references/troubleshooting.md)
- 踩坑：[pitfall-log.md](references/pitfall-log.md)
- 官方来源：[official-sources.md](references/official-sources.md)
