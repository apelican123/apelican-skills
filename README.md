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
| **apelican-personaforge** | 1.2.0 | 把已有的 MCP、技能接口和 API 转成 ChatGPT 个人插件，让你在日常聊天中直接调用 | [查看介绍](#apelican-personaforge) |

## 怎么安装

最简单的方式，是把技能链接直接交给支持 Skills 的 Agent：

```text
请帮我安装这个 Skill：
https://github.com/apelican123/apelican-skills/tree/main/apelican-personaforge
```

Agent 会把技能放到它实际使用的 skills 目录。如果你的客户端不支持自动安装，也可以手动复制。

<details>
<summary><strong>展开手动安装方式</strong></summary>

### Windows PowerShell

```powershell
git clone https://github.com/apelican123/apelican-skills.git
Copy-Item ".\apelican-skills\apelican-personaforge" "$env:USERPROFILE\.codex\skills\apelican-personaforge" -Recurse
```

### macOS / Linux

```bash
git clone https://github.com/apelican123/apelican-skills.git
cp -R ./apelican-skills/apelican-personaforge ~/.codex/skills/apelican-personaforge
```

如果你使用的不是 Codex，请把目标路径换成对应客户端的 skills 目录。

</details>

## 技能介绍

### apelican-personaforge

> 把已有能力带进 ChatGPT 对话：不必再回到 WorkBuddy、Codex 或开发环境，也能在聊天中直接调用自己的工具和服务。

这个技能主要用于把你已经拥有的 MCP 服务、技能背后的可调用接口和 REST API，转化为 ChatGPT 可以连接的个人插件。它的重点不是单纯优化 MCP 的“可发现性”，而是让原本只能在 WorkBuddy、Codex 或开发环境中使用的能力，可以直接进入日常 ChatGPT 对话。

它适合这些场景：

- 把已有的 REST API 封装成 ChatGPT 个人插件。
- 把单个或多个 MCP 服务接入日常 ChatGPT 对话。
- 把技能背后的可调用接口变成 ChatGPT 可以使用的工具。
- 让原本依赖 WorkBuddy、Codex 或开发环境的能力，在普通聊天中也能直接调用。
- 检查工具元数据、`search` / `fetch`、OAuth 2.1 和公开插件边界。
- 使用 Cloudflare Workers 或 OpenAI Secure MCP Tunnel 完成部署与验证。

如果某个 Skill 只有提示词或 Markdown 流程、没有可调用接口，需要先把对应能力实现成 API 或 MCP，不能直接把技能文件本身当作插件。技能会先确认上游类型、使用目标和部署位置，再继续实现；凭证只确认名称和获取方式，不要求把密钥贴进聊天。

[查看完整 SKILL.md](./apelican-personaforge/SKILL.md) · [查看使用说明](./apelican-personaforge/skill-card.md)

## 反馈与建议

如果你在使用时遇到问题，或者觉得某个地方还可以继续改，可以在 [Issues](https://github.com/apelican123/apelican-skills/issues) 里告诉我。我会根据自己的实际使用和需要，慢慢把这些技能补得更好一些。

---

<div align="center">

让AI为你所用

</div>
