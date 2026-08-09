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
| **apelican-personaforge** | 1.1.0 | 把 REST API、单个或多个 MCP 服务整理成 ChatGPT 更容易发现和正确调用的 MCP 插件 | [查看介绍](#apelican-personaforge) |

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

> 把“接口能返回数据”继续往前做一步：让模型知道什么时候该调用、参数应该怎么填、结果应该怎么读。

这个技能用于把 REST API、单个 MCP 或多个 MCP 服务，整理成 ChatGPT 更容易发现、正确调用并且便于验证的 MCP 插件。

它适合这些场景：

- 把一个 REST API 接入 ChatGPT。
- 代理或部署一个已有的 MCP 服务。
- 把大量 MCP 工具整理成更容易选择的一组工具。
- 检查工具元数据、`search` / `fetch`、OAuth 2.1 和公开插件边界。
- 使用 Cloudflare Workers 或 OpenAI Secure MCP Tunnel 完成部署与验证。

技能会先确认上游类型、使用目标和部署位置，再继续实现。凭证只确认名称和获取方式，不要求把密钥贴进聊天。

[查看完整 SKILL.md](./apelican-personaforge/SKILL.md) · [查看使用说明](./apelican-personaforge/skill-card.md)

## 反馈与建议

如果你在使用时遇到问题，或者觉得某个地方还可以继续改，可以在 [Issues](https://github.com/apelican123/apelican-skills/issues) 里告诉我。我会根据自己的实际使用和需要，慢慢把这些技能补得更好一些。

---

<div align="center">

让AI为你所用

</div>
