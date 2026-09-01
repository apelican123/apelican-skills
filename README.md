<div align="center">

# Apelican Skills

### 一些我根据自己的需要，慢慢做出来的 AI Skills

[目前收录](#目前收录) · [怎么安装](#怎么安装) · [技能介绍](#技能介绍) · [反馈与建议](#反馈与建议)

</div>

---

## 关于这个仓库

这里放的是一些我根据自己的需要，慢慢做出来的 Skills。

它们大多从我自己遇到的问题开始，所以有些技能可能还没有那么完善。我会继续使用，也会随着自己的需要，一点点调整和优化。

如果你对其中某个技能感兴趣，希望你能先看看它的介绍和使用说明，确认它是不是适合你的使用场景。使用前请读该技能自己的前提条件和权限说明。如果这些技能刚好也能帮到你，我会很高兴。

## 目前收录

| Skill | 当前版本 | 适合解决什么 | 入口 |
|---|---:|---|---|
| **apelican-ark** | 3.2.3 | 给 Codex、WorkBuddy 和 Hermes 做本地备份；换电脑或重装前先预览，确认后再备份和恢复 | [查看介绍](#apelican-ark) |
| **apelican-personaforge** | 4.0.1 | 注册 Cloudflare 后，AI 自动在 Workers 部署并给出可接到 ChatGPT 插件的链接 | [查看介绍](#apelican-personaforge) |
| **apelican-wechat-publisher** | 1.3.5 | 付梓：稿成即付梓。写好 Markdown，自动排版进草稿箱 | [查看介绍](#apelican-wechat-publisher) |
| **apelican-video-to-markdown** | 1.0.4 | 影札：丢一条 B站或 YouTube 链接，整理成能存进笔记的 Markdown | [查看介绍](#apelican-video-to-markdown) |

## 怎么安装

最简单的方式，是把技能链接直接交给支持 Skills 的 Agent：

```text
请帮我安装这个 Skill：
https://github.com/apelican123/apelican-skills/tree/main/apelican-wechat-publisher
```

把最后的技能目录换成你想安装的那个即可。Agent 会把技能放到它实际使用的 skills 目录。如果你的客户端不支持自动安装，也可以手动复制。

<details>
<summary><strong>展开手动安装方式</strong></summary>

### Windows PowerShell

```powershell
git clone https://github.com/apelican123/apelican-skills.git
$skill = "apelican-wechat-publisher"
Copy-Item ".\apelican-skills\$skill" "$env:USERPROFILE\.codex\skills\$skill" -Recurse
```

### macOS / Linux

```bash
git clone https://github.com/apelican123/apelican-skills.git
skill="apelican-wechat-publisher"
cp -R "./apelican-skills/$skill" "$HOME/.codex/skills/$skill"
```

如果你使用的不是 Codex，请把目标路径换成对应客户端的 skills 目录。

</details>

## 技能介绍

### apelican-ark

> **方舟**：给 Codex、WorkBuddy 和 Hermes 做一份看得懂、能检查的本地备份，换电脑或重装后再安全恢复。适用于：AI备份/助手搬家/技能迁移/记忆备份/方舟

我做方舟，是因为 AI 工具真正用顺手以后，值得留下来的不只是一个软件，还有自己装过的技能、调好的设置、积累的记忆和自动化。真到换电脑时，如果这些东西都要从头再来，会很麻烦。

方舟会先把准备带走的内容列清楚，不会一上来就改文件。你确认范围后，它才在本机生成备份；恢复时也会先告诉你准备写入什么，遇到同名文件会先保留新设备上的原文件。

你可以按需要选择五种范围：

- 基础备份：Codex、WorkBuddy、Hermes 的身份、技能、设置、记忆和自动化。
- 中等备份：再加入连接器、Hermes 扩展状态和项目索引。
- 全量备份：再尽力保存本地能找到的会话文件与索引。
- 完整迁移包：Hermes 全 profiles、桌面可迁移偏好、外部技能源、cron/projects 索引与本地 MCP 依赖闭包。
- 凭据舱：单独的小型 AES 加密包，只装静态密钥与可迁移 OAuth，不含记忆、会话和项目。

普通备份只需要 Python 3.10 或更高版本。确实需要迁移用户自己管理的敏感配置时，可以单独确认并放进 AES 加密包（需要 `pyzipper`）；**这一步请一定记住方舟总密码——密码丢失后，加密包里的凭据将永远无法恢复**。

有几个限制需要提前知道：

- 方舟只在本机工作，不联网，也不会上传备份内容。
- 账号登录文件、浏览器 Cookie 和设备绑定授权始终不备份，到了新电脑仍要重新登录。
- 会话文件能被保存，不等于旧聊天一定会在新版客户端里完整出现；这会受到客户端版本、索引和服务端数据影响。
- WorkBuddy 自动化不会通过复制数据库强行恢复；技能只生成计划，再通过产品提供的正式方式执行和检查。

[查看完整 SKILL.md](./apelican-ark/SKILL.md)

### apelican-personaforge

> **GPT插件铸造器**：把你已经有的 API 或 MCP 铸成 ChatGPT 插件。登录 Cloudflare 之后，AI 自动部署，最后给你一条能直接粘进 ChatGPT 的链接。适用于：GPT插件/ChatGPT连接器/MCP/铸造

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

### apelican-wechat-publisher

> **付梓**：稿成即付梓。写好 Markdown，自动排版、配封面，存进公众号草稿箱。粉丝此时还看不见。适用于：公众号排版/公众号推文/一键排版/封面配图/公众号/排版/推文/草稿箱/Markdown/封面/wenyan/公众号文章/公众号发布

我做这个技能，是因为写完 Markdown 之后，还要进编辑器调行距、一张张传图、再去好几个长得很像的后台找 AppID。真正劝退的往往不是写作，是「贴」。

技能会按页面带你拿到公众号自己的 AppID 和 AppSecret，选人文、科技或社会热点三种版式，生成封面和配图，然后把稿子存进草稿箱。wenyan 打印的「发布成功」只表示草稿创建成功，不是已经群发。

最短可以这样开始：

1. 在微信公众平台注册公众号，再用管理员微信登录微信开发者平台。
2. 取出公众号 AppID，启用 AppSecret，把电脑的公网 IP 加进白名单。
3. 安装 Node.js 和 `@wenyan-md/cli`，在技能目录写入自己的 `.env`。
4. 把文章交给 AI，或直接运行 `wenyan publish`。然后到 https://mp.weixin.qq.com/ 草稿箱自己预览、再点发表。

有几个边界需要提前知道：

- 它不群发、不定时发表、不改账号权限，也不会替你点「发表」。
- 密钥必须来自微信开发者平台里的公众号，不是开放平台的移动应用或网站应用。
- 标题和作者会尽量从正文里识别并填进稿件头部；认不准会问你，不会编一个名字。
- 封面按规范生成；配图不是证据，不能拿 AI 图冒充现场或截图。
- 需要你自己的公众号，并且本机装得了 Node.js。

排版层使用开源工具 [wenyan-cli](https://github.com/caol64/wenyan-cli)（Apache-2.0）。本仓库不捆绑它的源码，需要你自行用 npm 安装。

[查看完整 SKILL.md](./apelican-wechat-publisher/SKILL.md) · [查看简明介绍](./apelican-wechat-publisher/skill-card.md)

### apelican-video-to-markdown

> **影札**：丢一条 B站或 YouTube 链接，整理成能存进笔记的 Markdown。适用于：视频总结/转文字/视频笔记/文字笔记/视频转写/B站字幕/视频/markdown/YouTube/字幕/转录

我做这个技能，是因为收藏夹里堆着很多视频，真要回头用时，却不想把整段口播再听一遍。网课、访谈、长吐槽都一样：需要一份能检索、能进笔记的文稿，而不是又一次打开播放器。

它会先查有没有现成字幕。有就只抽字幕，不下载画面；没有再只下载音轨做语音识别，最后写成带摘要、分章和时间戳的 Markdown。默认走必剪云端识别，你也可以改成完全本地的 Whisper。

最短可以这样开始：

1. 安装 Python 3.10+ 和 `yt-dlp`。没有字幕时再装 ffmpeg。
2. 把技能交给你的 AI，丢一条视频链接，说「整理成笔记」。
3. 到输出目录拿走 `.md` 文件。

有几个边界需要提前知道：

- 有官方字幕就不下载视频，也不跑识别。
- 必剪不是官方稳定接口，音频会上传到 B 站。内部会议、未公开内容不要走它。
- 不绕过大会员、付费墙或 DRM。
- 语音识别会写错人名和黑话，摘要能用，当引文要自己核对。

[查看完整 SKILL.md](./apelican-video-to-markdown/SKILL.md) · [查看简明介绍](./apelican-video-to-markdown/skill-card.md)

## 反馈与建议

如果你在使用时遇到问题，或者觉得某个地方还可以继续改，可以在 [Issues](https://github.com/apelican123/apelican-skills/issues) 里告诉我。我会根据自己的实际使用和需要，慢慢把这些技能补得更好一些。

---

<div align="center">

让AI为你所用

</div>
