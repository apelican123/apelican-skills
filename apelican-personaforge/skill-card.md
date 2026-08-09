# Plugin Forge / 插件铸造器

**版本：1.2.0**

把已有的 MCP、技能背后的可调用接口和 REST API 转化为 ChatGPT 个人插件，让原本位于 WorkBuddy、Codex 或开发环境中的能力可以在日常聊天中直接使用。

## 1.2.0 更新

- 修正技能定位：核心用途是把已有能力带进 ChatGPT 日常对话，而不是单纯提高 MCP 的工具可发现性。
- 明确技能转换边界：只有提示词或 Markdown 流程、没有可调用接口的 Skill，需要先实现为 API 或 MCP。

## 1.1.0 已有能力

- 增加 OpenAI 插件规范：server instructions、工具 title/description、输入/输出 schema、structuredContent、annotations、标准 search/fetch、OAuth 2.1 与公开审核边界。
- 将主技能缩短为可路由流程，详细内容按需读取，降低上下文占用。
- 重写零基础部署流程，从安装 Node.js、登录 Cloudflare、选择模式、创建项目、设置 Secret，到生产验证和 ChatGPT 接入不跳步。
- 支持 Windows PowerShell、macOS 和 Linux；不依赖任何额外 Codex 插件或私人 MCP。
- 明确私人 Developer mode 与公开发布不是同一安全等级：私人入口默认 Bearer，并可显式兼容旧 query/API-Key Header；公开发布需 OAuth 2.1 与审核。
- 将客户端入口认证与上游服务认证分离，覆盖 Bearer、API-Key Header、Basic、query token、OAuth access token 与专有签名的适配边界。
- 增加逐步验证门、对抗性回归矩阵和第二设备验收；每一步都有预期结果与停止条件。

## 使用方式

把整个 `apelican-personaforge` 文件夹放入支持 Skills 的客户端技能目录，然后提出类似请求：

- “把这个 REST API 部署成 ChatGPT 可调用的 MCP。”
- “代理这个带 Token 的 MCP，并部署到 Cloudflare Workers。”
- “把这个技能背后的 API 接口转成我的 ChatGPT 个人插件。”
- “让我在普通 ChatGPT 对话里直接使用这个原本只能在 Codex 中调用的服务。”
- “把很多 MCP 工具整理成少量 GPT 容易选择的工具。”
- “检查我的 MCP 是否符合 OpenAI 插件规范。”

技能会先确认上游类型、私人/公开目标与部署位置，再生成项目、部署并验证。

## 文件结构

```text
apelican-personaforge/
├── SKILL.md
├── skill-card.md
├── references/
│   ├── openai-plugin-contract.md
│   ├── metadata-and-results.md
│   ├── quick-start.md
│   ├── templates.md
│   ├── validation-and-release.md
│   ├── compatibility-and-regression.md
│   ├── cross-device-use.md
│   ├── security-checklist.md
│   ├── chatgpt-setup.md
│   ├── local-tunnel-deploy.md
│   ├── mcp-protocol-basics.md
│   ├── how-it-works.md
│   ├── troubleshooting.md
│   └── pitfall-log.md
└── examples/
    └── deployed-services.md
```

## 许可证

技能文档采用 MIT。生成的项目通常使用 `@modelcontextprotocol/server`、`agents`、`zod`、
`typescript` 与 `wrangler`；发布者应核对安装时的实际版本和各依赖许可证。本技能不捆绑
这些 npm 包、其他 Codex 插件、私人 MCP 或作者机器配置。

使用者仍需遵守 Cloudflare、OpenAI、上游 API/MCP 及数据来源的条款。
