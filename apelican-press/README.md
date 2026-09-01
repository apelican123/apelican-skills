# apelican-press

把 Markdown 排成微信公众号样式，并保存到草稿箱。

这是一份给人和 AI 一起用的技能包：人按文档完成公众号开发配置，AI 按 `SKILL.md` 选模板、生成封面和配图、渲染、创建草稿。它**不会**自动发表或群发。

## 你能少做什么

以前常见的路径是：写 Markdown → 复制到在线编辑器 → 手动传图 → 再贴回公众号后台。这里改成：写好 Markdown → 按文风生封面和配图 → 选一套模板 → 保存到草稿箱 → 你自己预览后发表。

## 不做什么

- 不代替你注册公众号
- 不保存或传播你的 AppSecret
- 不自动群发、定时发表、删除草稿、改权限
- 不把「微信开放平台」的移动应用 / 网站应用 AppID 当成公众号密钥

## 选择了哪条技术路径

| 方案 | 适合谁 | 代价 |
| --- | --- | --- |
| **微信开发者平台 + 公众号 AppID/AppSecret + wenyan-cli**（本技能采用） | 自己有公众号、想用 Markdown 出草稿 | 要实名/认证、要加 IP 白名单、要装 Node.js |
| 只去微信开放平台注册移动应用 | 做 App 登录、分享 | **不能**调公众号草稿接口 |
| 自己直接调 `draft/add` | 要完全自研排版 | 图片上传、HTML 白名单、主题都得自己做 |
| 只在 mp.weixin.qq.com 手工排 | 偶尔发一两篇 | 没法让 AI 稳定复现版式 |

采用理由：官方已经把公众号开发配置迁到[微信开发者平台](https://developers.weixin.qq.com/platform/)；草稿接口 `draft/add` 对公众号和服务号都开放；[wenyan-cli](https://github.com/caol64/wenyan-cli) 负责 Markdown 转微信 HTML、传图和建草稿，Apache-2.0，npm 周下载量约 1k，足够作为排版层，不必再手写一套微信 HTML。

## 最短路径

1. 若还没有公众号：先在 [微信公众平台](https://mp.weixin.qq.com/) 注册。
2. 用管理员微信扫码登录 [微信开发者平台](https://developers.weixin.qq.com/platform/)。
3. 按 [references/wechat-credentials.md](references/wechat-credentials.md) 取出 AppID、启用 AppSecret、加入 IP 白名单。
4. 安装 Node.js 后执行：

   ```bash
   npm install -g @wenyan-md/cli
   ```

   ```powershell
   npm install -g @wenyan-md/cli
   ```

5. 按 [references/env-example.md](references/env-example.md) 在本机新建 `.env`，填入自己的两个值，不要发给任何人。
6. 用 `templates/` 里对应主题的 Markdown 骨架写文章。封面和正文配图按 [references/image-direction.md](references/image-direction.md) 生成：先生图模型，没有生图能力再用 HTML 卡片。标题和作者按 [references/title-and-author.md](references/title-and-author.md) 从正文识别。
7. 运行：

   ```bash
   wenyan publish -f article.md -c templates/humanities.css -h github --no-mac-style --env-file .env
   ```

   完整脚本见 [references/scripts.md](references/scripts.md)。
8. 打开 https://mp.weixin.qq.com/ 草稿箱检查，再决定是否发表。

完整逐步说明：[references/quick-start.md](references/quick-start.md)。不会命令行、只想把第一篇发出去：[references/beginner.md](references/beginner.md)。草稿进后台之后怎么点：[references/mp-publish.md](references/mp-publish.md)。

## 三套模板

| 文件 | 适合 | 阅读感觉 |
| --- | --- | --- |
| `templates/humanities.css` | 人文、随笔、书评 | 纸墨、宋体标题、宽行距 |
| `templates/tech.css` | 科技、教程 | 青简、无衬线、代码友好 |
| `templates/social.css` | 社会热点、时评 | 港闻、重标题、朱红点缀 |

它们借鉴的是港式印刷品的**阅读节奏**（留白、行距、标题克制、少色块），不是某个媒体的品牌复制。

## 安装到 AI 技能目录

把本文件夹整份复制到你使用的 Agent 的 skills 目录，保证根目录有 `SKILL.md`。Windows / macOS / Linux 都可以。复制后只提交你自己的 `.env`，不要把别人的密钥带过去。

## 许可证

本技能文档与脚本：Apache License 2.0，见 `LICENSE`。

排版与上传依赖 [wenyan-cli](https://github.com/caol64/wenyan-cli)（Apache-2.0）。本包不捆绑它的源码；使用时请自行安装，并保留其版权与许可声明。
