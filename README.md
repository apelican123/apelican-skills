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
| **apelican-personaforge** | 2.0.0 | 把已有的 API 或 MCP 接进 ChatGPT；不用先懂术语，技能会一步一步带你完成 | [查看介绍](#apelican-personaforge) |

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

> 把你已经有的 API、MCP 或技能接口接进 ChatGPT，变成平时聊天时就能直接使用的个人插件。

我最开始做这个技能，是因为有些能力已经能在 Codex、WorkBuddy 或开发环境里调用，但回到普通 ChatGPT 对话时又用不上。现在只要它背后确实有 API 或 MCP 接口，这个技能就可以带你把它接进来。

2.0 主要把使用过程重新做了一遍。你不需要先弄懂“隧道、MCP、OAuth”这些词，也不用一开始自己选择技术方案。技能会先问你想在 ChatGPT 里完成什么，再一次推进一个可以检查的步骤：刚做了什么、应该看到什么、下一步是什么，出现不同结果时又该怎么处理。

私人使用时，默认会为每个人生成一条不同的专属能力链接。你在 ChatGPT 里选择“无身份验证”，粘贴完整链接就可以继续；真正的验证在 Cloudflare 完成。用户名只用来生成可识别的标签，访问密钥来自独立的高强度随机数，不会用用户名直接当密码。

它适合这些情况：

- 把已有的 REST API 做成 ChatGPT 可以调用的工具。
- 把一个或多个 MCP 服务接进日常 ChatGPT 对话。
- 把 Skill 背后已经存在的可调用接口变成个人插件。
- 给自己或少量可信用户创建彼此独立的能力链接。
- 检查工具说明、参数、读写权限和返回结果是否容易被 ChatGPT 正确使用。
- 需要更多用户或准备公开上架时，继续完成 OAuth 2.1 和公开审核准备。
- 本机或内网能力需要接入时，使用 OpenAI Secure MCP Tunnel。

有几个边界需要提前知道：

- 完整专属链接本身就是访问密钥，不能截图、公开或转发；泄露后要立即撤销和轮换。
- 一人一链接只保护入口。如果底层数据本来按用户区分，还需要每个人自己的上游身份或权限，不能让所有人共用一个能读取全部数据的管理员密钥。
- 只有提示词或 Markdown 流程、没有可调用接口的 Skill，不能直接变成远程插件；要先把对应能力实现成 API 或 MCP。
- 私人链接在 Developer mode 里能用，不代表已经通过 OpenAI 的公开审核。

公开包里保留了两个 JavaScript 小工具：一个生成用户专属链接，一个检查 MCP 握手、工具信息、错误链接和跨用户隔离。现在小红书技能上传已经支持 JavaScript 等多种文件，所以没有再把这些可执行工具强行改成纯 Markdown。

[查看完整 SKILL.md](./apelican-personaforge/SKILL.md) · [查看使用说明](./apelican-personaforge/skill-card.md)

## 反馈与建议

如果你在使用时遇到问题，或者觉得某个地方还可以继续改，可以在 [Issues](https://github.com/apelican123/apelican-skills/issues) 里告诉我。我会根据自己的实际使用和需要，慢慢把这些技能补得更好一些。

---

<div align="center">

让AI为你所用

</div>
