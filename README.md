<div align="center">

# Apelican Skills

### 一些我根据自己的需要，慢慢做出来的 AI Skills

[目前收录](#目前收录) · [怎么安装](#怎么安装) · [反馈与建议](https://github.com/apelican123/apelican-skills/issues)

</div>

---

## 关于这个仓库

这里放的是一些我根据自己的需要，慢慢做出来的 Skills。

它们大多从我自己遇到的问题开始，所以有些技能可能还没有那么完善。我会继续使用，也会随着自己的需要，一点点调整和优化。

如果你对其中某个技能感兴趣，希望你能先看看它的介绍和使用说明，确认它是不是适合你的使用场景。如果这些技能刚好也能帮到你，我会很高兴。

## 目前收录

| Skill | 当前版本 | 适合解决什么 | 入口 |
|---|---:|---|---|
| **apelican-ark** | 2.2.0 | 给 Codex 和 WorkBuddy 做本地备份；换电脑或重装前先预览，确认后再备份和恢复 | [查看介绍](#apelican-ark) |
| **apelican-personaforge** | 4.0.1 | 注册 Cloudflare 后，AI 自动在 Workers 部署并给出可接到 ChatGPT 插件的链接 | [查看介绍](#apelican-personaforge) |

## 怎么安装

最简单的方式，是把技能链接直接交给支持 Skills 的 Agent：

```text
请帮我安装这个 Skill：
https://github.com/apelican123/apelican-skills/tree/main/apelican-ark
```

把最后的技能目录换成你想安装的那个即可。Agent 会把技能放到它实际使用的 skills 目录。如果你的客户端不支持自动安装，也可以手动复制。

<details>
<summary><strong>展开手动安装方式</strong></summary>

### Windows PowerShell

```powershell
git clone https://github.com/apelican123/apelican-skills.git
$skill = "apelican-ark"
Copy-Item ".\apelican-skills\$skill" "$env:USERPROFILE\.codex\skills\$skill" -Recurse
```

### macOS / Linux

```bash
git clone https://github.com/apelican123/apelican-skills.git
skill="apelican-ark"
cp -R "./apelican-skills/$skill" "$HOME/.codex/skills/$skill"
```

如果你使用的不是 Codex，请把目标路径换成对应客户端的 skills 目录。

</details>

## 技能介绍

### apelican-ark

> 给 Codex 和 WorkBuddy 做一份看得懂、能检查的本地备份，换电脑或重装后再安全恢复。

我做方舟，是因为 AI 工具真正用顺手以后，值得留下来的不只是一个软件，还有自己装过的技能、调好的设置、积累的记忆和自动化。真到换电脑时，如果这些东西都要从头再来，会很麻烦。

方舟会先把准备带走的内容列清楚，不会一上来就改文件。你确认范围后，它才在本机生成备份；恢复时也会先告诉你准备写入什么，遇到同名文件会先保留新设备上的原文件。

你可以按需要选择三种范围：

- 基础备份：身份、技能、设置、记忆和自动化。
- 中等备份：再加入连接器和项目索引。
- 全量备份：再尽力保存本地能找到的会话文件与索引。

普通备份只需要 Python 3.10 或更高版本。确实需要迁移用户自己管理的敏感配置时，可以单独确认并放进 AES 加密包；这个功能还需要安装 `pyzipper`。

有几个限制需要提前知道：

- 方舟只在本机工作，不联网，也不会上传备份内容。
- 账号登录文件、浏览器 Cookie 和设备绑定授权始终不备份，到了新电脑仍要重新登录。
- 会话文件能被保存，不等于旧聊天一定会在新版客户端里完整出现；这会受到客户端版本、索引和服务端数据影响。
- WorkBuddy 自动化不会通过复制数据库强行恢复；技能只生成计划，再通过产品提供的正式方式执行和检查。

[查看完整 SKILL.md](./apelican-ark/SKILL.md) · [查看简明介绍](./apelican-ark/skill-card.md)

### apelican-personaforge

> 把你已经有的 API 或 MCP 铸成 ChatGPT 插件：登录 Cloudflare 之后，AI 自动部署，最后给你一条能直接粘进 ChatGPT 的链接。

我最开始做这个技能，是因为有些能力已经能在开发环境里调用，但回到普通 ChatGPT 对话时又用不上。4.0 把这件事收成最短路径：你准备好 Cloudflare 账号，说出要接什么服务，剩下的设计、写 Worker、部署和验证由技能自动做完。

你只需要做两件事：

1. 注册或登录 Cloudflare，创建一个只开了 `Workers Scripts: Edit` 的 API Token，并复制 Account ID。
2. 把上游接口交给技能：MCP 地址加密钥，或 REST API 地址加密钥。

之后技能会在你的 Cloudflare Workers 里上传服务、写入密钥、打开 workers.dev，并先验证协议再给你链接。你在 ChatGPT 打开 Developer mode，到 https://chatgpt.com/plugins 点 +，粘贴完整 URL（含 `/mcp`），认证选 No authentication；然后新开对话，从工具菜单启用这个连接。

私人使用默认不走 OAuth。OAuth 更麻烦，ChatGPT 端也更容易验证失败。默认是「链接自带随机令牌」：ChatGPT 端选无身份验证，服务端仍然校验路径里的令牌，不是把私人数据裸放到公网。只有用户很多、数据要按人隔离，或必须独立撤销和审计时，才值得改用 OAuth。

它适合这些情况：

- 把已有的 REST API 做成 ChatGPT 可以调用的工具。
- 把一个或多个 MCP 服务合并成一个入口，接到日常 ChatGPT 对话。
- 不想自己装 wrangler 或 Node，只想拿到一条能用的链接。
- 本机或内网能力需要接入时，使用 OpenAI Secure MCP Tunnel。

有几个边界需要提前知道：

- 需要能写文件、能联网的 AI（例如 Codex、Claude Code、Hermes、Cursor）。纯网页版 ChatGPT 没法替你部署。
- 完整链接本身就是访问密钥，不能截图、公开或转发；泄露后要立即作废重生成。
- 账号注册、登录和创建 Token 必须由你本人完成，技能不会也不能替你输入密码。
- 只有提示词或 Markdown 流程、没有可调用接口的 Skill，不能直接变成远程插件。
- 写操作、付款、对外发送会单独设计，不会藏进通用执行器。
- 私人链接能连上，不代表已经通过 OpenAI 的公开审核。

公开包是纯文档加可复制的 Worker 模板。部署由 AI 用 Python 调 Cloudflare API 完成，不要求你安装 wrangler。

[查看完整 SKILL.md](./apelican-personaforge/SKILL.md) · [查看使用说明](./apelican-personaforge/skill-card.md)

## 反馈与建议

如果你在使用时遇到问题，或者觉得某个地方还可以继续改，可以在 [Issues](https://github.com/apelican123/apelican-skills/issues) 里告诉我。我会根据自己的实际使用和需要，慢慢把这些技能补得更好一些。

---

<div align="center">

让AI为你所用

</div>
