# Plugin Forge / 插件铸造器

**版本：2.0.0**

如果你已经有一个 API、MCP 服务，或者某个 Skill 背后已经有可调用接口，这个技能可以带你把它接进 ChatGPT，做成自己日常对话里能直接使用的个人插件。

你不需要先弄懂“隧道、MCP、OAuth”这些词。技能会先问你最终想在 ChatGPT 里完成什么，再一次带你做一个能检查的步骤，直到真正调用出结果。

## 2.0 改了什么

- **从工程说明改成手把手向导**：每一步都会告诉你刚做了什么、应该看到什么、下一步是什么，遇到不同结果该怎样继续。
- **私人使用默认更简单**：在 ChatGPT 端选择“无身份验证”，粘贴一条完整的专属能力链接即可；真正的验证在 Cloudflare 完成。
- **每个人都有不同链接**：用户名只用来生成可识别标签，密钥由高强度随机数生成；一人一链接、一人一摘要 Secret，不从用户名猜密码。
- **补上跨用户隔离**：共用一个 Worker 时，会检查拿 A 的 Token 拼到 B 的用户名路径上也必须失败。
- **保留完整专业路径**：大量用户、独立账号数据或公开上架仍使用 OAuth 2.1；本机/内网能力可以走 OpenAI Secure MCP Tunnel。
- **公开包保留可执行工具**：小红书上传页已支持 JavaScript 等多种文件，2.0 直接附带链接生成和 MCP 审计脚本，不再把所有代码硬塞进 Markdown。

## 什么时候会用到

- 把已有 REST API 做成 ChatGPT 可以调用的工具。
- 把一个或多个 MCP 服务接进日常 ChatGPT 对话。
- 把 Skill 背后已经存在的程序接口变成个人插件。
- 给自己或少量可信用户创建彼此独立的能力链接。
- 检查一个 MCP 的工具说明、权限、返回格式和认证是否适合 ChatGPT。
- 准备 OAuth、公开插件审核，或连接本机 Secure MCP Tunnel。

## 最短怎么开始

安装整个 `apelican-personaforge` 文件夹后，可以直接说：

> 我有一个 REST API，想在 ChatGPT 里直接用。请不要先讲术语，一步一步带我完成，每一步都告诉我怎样判断成功。

或者：

> 我已经有一个 MCP 地址，请帮我把它做成自己的 ChatGPT 个人插件，并给每位用户创建不同的专属链接。

技能会先读你已经提供的材料，再判断是翻译 API、代理 MCP 还是整理多个服务，不要求你自己先选技术方案。

## 使用前知道这些

- 只有提示词或 Markdown 流程、没有可调用接口的 Skill，不能直接变成远程插件；需要先做出 API 或 MCP。
- 完整专属链接就是访问密钥。谁拿到它，谁就可能使用对应能力，所以不能截图、公开或转发；泄露后要立即撤销和轮换。
- 一人一链接只保护入口。如果底层数据分用户，还需要每人的上游凭据、scope 或 OAuth，不能共用一个能读取全部数据的管理员密钥。
- 私人链接能在 Developer mode 使用，不等于通过 OpenAI 公开审核。
- 部署需要用户自己的 Cloudflare 账号、上游接口材料和必要凭据；凭据只放 Cloudflare Secrets，不填进 ChatGPT。

## 文件结构

```text
apelican-personaforge/
├── SKILL.md
├── skill-card.md
├── scripts/
│   ├── create-user-link.js
│   └── audit-mcp.js
├── references/
│   ├── onboarding-and-progress.md
│   ├── quick-start.md
│   ├── chatgpt-setup.md
│   ├── templates.md
│   ├── validation-and-release.md
│   ├── compatibility-and-regression.md
│   ├── cross-device-use.md
│   ├── security-checklist.md
│   ├── troubleshooting.md
│   └── 其他协议与工具说明
└── examples/
    └── deployed-services.md
```

## 许可证与边界

技能文档和随包脚本采用 MIT。生成项目使用哪些 npm 包，应以实际项目锁定的依赖和各自许可证为准；本技能不捆绑作者的私人服务、账号、密钥或机器配置。

使用者仍需遵守 Cloudflare、OpenAI、上游 API/MCP 和数据来源的条款。
