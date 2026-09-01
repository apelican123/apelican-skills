---
name: "apelican-wechat-publisher"
description: "把 Markdown 排成微信公众号样式并保存到草稿箱。适用于公众号排版、封面配图、草稿箱、wenyan、AppID、IP 白名单。不会自动群发或正式发表。"
---

# 公众号全自动排版进草稿箱

把已经写好的文章排成适合手机阅读的公众号正文，并保存到微信公众号**草稿箱**。粉丝此时还看不见。读者之后按 [mp-publish.md](references/mp-publish.md) 自己预览、再点发表。

本技能不群发、不定时发表、不改账号权限。创建草稿不等于推文已经发出。

用户是小白、说「不会发 / 帮我推文」时，先读 [beginner.md](references/beginner.md)，用口语一步一步带，不要一上来丢命令。

排版引擎使用开源工具 [wenyan-cli](https://github.com/caol64/wenyan-cli)（Apache-2.0，npm 包 `@wenyan-md/cli`）。凭据只从用户自己的微信公众号读取，技能包里不含任何密钥。

## 什么时候用

- 用户说「排版到公众号」「推到草稿箱」「用 wenyan 发公众号」「不会推文」「我是小白」
- 已有 Markdown，需要变成公众号能打开的样式
- 用户第一次接公众号 API，需要按页面点到 AppID、AppSecret、IP 白名单

不要用在：自动群发、代发朋友圈、爬别人的公众号、修改已发布文章、或把开放平台移动应用 AppID 拿来发公众号。

## 权限与副作用

执行前用一句话说清：

- **读取**：用户指定的 Markdown、封面图、技能目录 `.env`（只检查键名是否存在，不把值写进对话）
- **联网**：请求 `api.weixin.qq.com` 换 token、上传图片、新建草稿；查公网 IP 时访问 `https://ifconfig.me/ip`；出图时调用当前环境的生图模型
- **写入**：微信公众号草稿箱新增一篇草稿；图片会进入该账号素材库；本地文章目录会写入封面和配图文件
- **安装**：需要用户本机已有 Node.js，并自行安装 `@wenyan-md/cli`。脚本发现未安装时只打印命令，不擅自 `npm install -g`

## 环境变量

| 变量名 | 用途 | 去哪拿 |
| --- | --- | --- |
| `WECHAT_APP_ID` | 公众号开发者 ID | 微信开发者平台 → 我的业务 → 公众号 → 基础信息 |
| `WECHAT_APP_SECRET` | 公众号开发者密钥 | 同上路径 → 开发密钥；平台不回显，启用或重置后立刻保存 |

逐步点击路径见 [wechat-credentials.md](references/wechat-credentials.md)。从 0 跑通见 [quick-start.md](references/quick-start.md)。小白入口见 [beginner.md](references/beginner.md)。草稿进后台后怎么点发表见 [mp-publish.md](references/mp-publish.md)。

不要去「微信开放平台」注册移动应用或网站应用来拿这对密钥。那是另一套 AppID，发给公众号草稿接口会失败。

## 工作流

0. **先判断是不是小白。** 用户不会命令行、问怎么推文、或第一次接公众号时，按 [beginner.md](references/beginner.md) 带，一次只让人在网页上做一件事。
1. **确认目标是草稿箱。** 用户没说群发，就只创建草稿。`wenyan publish` 也只是进草稿箱，粉丝不会因此收到消息。
2. **确认凭据与出口 IP**。`.env` 或当前环境里要有上面两个变量；把当前公网 IPv4 加进开发密钥页的 IP 白名单。
3. **确认标题和作者，再写文章头部。** 按 [title-and-author.md](references/title-and-author.md) 识别；缺了就问，不要编。Markdown 顶部必须有：

   ```markdown
   ---
   title: 不超过32个汉字的标题
   cover: ./cover.jpg
   author: 可选，不超过16个字
   digest: 可选，不超过120个字的分享简介
   ---
   ```

   实测 `title` 和 `cover` 都要写。封面用相对路径；做成 **900×383（2.35:1）**，重要文字放在画面中央，因为列表小图会裁成 1:1。
4. **选模板，不要混用**。
   - 人文、随笔、书评、城市笔记 → `templates/humanities.css` + `templates/humanities.md`
   - 科技、教程、产品说明 → `templates/tech.css` + `templates/tech.md`
   - 社会热点、时评、新闻综述 → `templates/social.css` + `templates/social.md`
   三套都按港式印刷品的阅读节奏来：标题克制、行距拉开、少用色块胶囊。规则见 [themes.md](references/themes.md)。
5. **出图，必须先走生图模型。** 封面 900×383，正文每个大段或关键判断最多一张配图。配图不是证据，假现场、假截图一律禁止。没有生图能力时，用 `templates/cover-fallback.html` / `templates/inline-fallback.html` 做成平面卡片再截 PNG。完整规则见 [image-direction.md](references/image-direction.md)。
6. **先渲染，再上传**。能本地预览时先：

   ```bash
   wenyan render -f article.md -c templates/humanities.css -h github
   ```

   ```powershell
   wenyan render -f article.md -c templates/humanities.css -h github
   ```

7. **保存草稿，只做一次**。接口结果不明确时先核对，禁止盲目重试造成重复草稿。优先直接跑 wenyan（小红书技能包不附带 `.sh` / `.ps1`，避免上传页识别不了）：

   ```bash
   wenyan publish -f article.md -c templates/humanities.css -h github --no-mac-style --env-file .env
   ```

   ```powershell
   wenyan publish -f article.md -c templates/humanities.css -h github --no-mac-style --env-file .env
   ```

   完整可复制脚本见 [scripts.md](references/scripts.md)。

8. **回读边界。** 成功后只报告：用了哪个主题、标题、封面路径、接口是否返回成功。明确说「草稿已在后台，粉丝还看不见」。带用户打开 [mp-publish.md](references/mp-publish.md) 自己预览。若工具不返回草稿详情，就说「只能确认接口创建成功」，不要假装已经看过后台排版，也不要说「已经发布」。

## 给 Agent 的硬规则

- 不把 AppSecret、完整 `.env`、token 写进回复、日志或技能文件。
- 不调用发表 / 群发接口。
- 不把小红书网格、品牌锁或其它渠道的封面母版套到公众号。
- 封面和配图按 [image-direction.md](references/image-direction.md) 走：先生图，再生不成才 HTML 卡；不把 AI 图写成现场或截图。
- 排版只动层级、段落、强调和留白，不改作者立场，不编造经历和数据。
- 正文图片必须随文章一起被 wenyan 上传；外链图片到了微信侧会被丢掉。
- 标题、作者按 [title-and-author.md](references/title-and-author.md) 从正文识别并填进 frontmatter；认不准就问用户，不编名字。
- 标题按接口限制准备：标题 ≤ 32 字，作者 ≤ 16 字，摘要 ≤ 120 字。
- 用户说「发布」时先确认是「进草稿箱」还是「后台正式发表 / 群发」。后两步只口头带点击，不调用接口。
- 对小白不要一次甩出安装、密钥、排版全部命令；卡在哪一步就只解释哪一步。

## 验证

跑通的最低标准：

1. `wenyan --help` 有输出。
2. 凭据已配置，但对话里看不到密钥值。
3. `wenyan render` 能出 HTML。
4. `publish` 成功后，用户能在公众号后台草稿箱看到该标题。
5. 没有触发发表或群发。
6. 封面和配图符合 [image-direction.md](references/image-direction.md)：先生图，图注不把配图写成现场。

常见报错见 [troubleshooting.md](references/troubleshooting.md)。已经踩过的坑见 [pitfall-log.md](references/pitfall-log.md)。
