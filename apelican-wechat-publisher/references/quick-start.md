# 从 0 到第一篇草稿

按顺序做。每一步结束都有一个能看见的结果，做不到就先停，不要跳到发布脚本。

## 0. 你需要提前有的东西

- 一台能上网的电脑（Windows / macOS / Linux 都可以）
- 一个微信账号
- 一个你自己的**微信公众号**（订阅号或服务号都可以）
- Node.js 18 或更高。打开 https://nodejs.org/ 下载 **LTS**。Windows 安装时勾选 **Add to PATH**，装完关掉终端再开一次，运行 `node -v` 能出号码才算成功。

还没有公众号：打开 https://mp.weixin.qq.com/ 用微信扫码，按页面注册。个人能注册订阅号。注册完成后继续。

## 1. 确认你是管理员或开发者

只有公众号的**管理员**或已绑定的**开发者**才能看到 AppID 和 AppSecret。

「运营者」在开发者平台里看不到这些。如果登录后「我的业务」里公众号数量是 0，去公众号后台让管理员把你加成开发者，或换管理员的微信扫码。

## 2. 取出 AppID、启用 AppSecret、加入 IP 白名单

完整点击路径、实名要求和常见弹窗，见 [wechat-credentials.md](wechat-credentials.md)。

做完这一步，你手里应该有：

- 一串以 `wx` 开头的 AppID
- 一串只显示过一次的 AppSecret（自己存好）
- 当前电脑的公网 IPv4 已经写进白名单

## 3. 安装排版命令

bash（macOS / Linux / Windows Git Bash）：

```bash
node -v
npm install -g @wenyan-md/cli
wenyan --help
```

PowerShell：

```powershell
node -v
npm install -g @wenyan-md/cli
wenyan --help
```

`wenyan --help` 能出来用法，这一步才算过。

## 4. 填凭据

在本技能根目录：

```bash
cp .env.example .env
```

```powershell
Copy-Item .env.example .env
```

用文本编辑器打开 `.env`，只改这两行：

```text
WECHAT_APP_ID=你的AppID
WECHAT_APP_SECRET=你的AppSecret
```

等号两边不要加引号。Windows 记事本「另存为」时，文件类型选「所有文件」，文件名只写 `.env`，不要变成 `.env.txt`。不要把这个文件发到聊天、截图或 GitHub。

启用 AppSecret 之前先把记事本打开等着：密钥只出现一次。

加载一次，确认脚本能读到（不会打印密钥）：

```bash
source ./scripts/setup.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

## 5. 准备一篇最小文章

复制一套模板。以人文为例：

```bash
cp templates/humanities.md ~/Desktop/my-first-wechat.md
```

```powershell
Copy-Item templates\humanities.md $env:USERPROFILE\Desktop\my-first-wechat.md
```

然后：

1. 按 [image-direction.md](image-direction.md) 生成 900×383 封面（先生图，没有生图再用 HTML 卡）。
2. 把封面放到和 Markdown **同一个文件夹**。
3. 改 Markdown 顶部的 `title` 和 `cover`。
4. 把示例正文换成你的内容；大段处按规范补配图和图注。

## 6. 先渲染，不上传

```bash
wenyan render -f ~/Desktop/my-first-wechat.md -c templates/humanities.css -h github
```

```powershell
wenyan render -f "$env:USERPROFILE\Desktop\my-first-wechat.md" -c templates\humanities.css -h github
```

能出 HTML 就说明 Markdown 和主题没问题。

## 7. 保存到草稿箱

先进入技能根目录，再运行：

```bash
./scripts/publish.sh ~/Desktop/my-first-wechat.md templates/humanities.css github
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\publish.ps1 "$env:USERPROFILE\Desktop\my-first-wechat.md" templates\humanities.css github
```

成功后打开 https://mp.weixin.qq.com/ ，进入草稿箱，核对标题、封面、正文开头和图片。**这时粉丝还看不见。** 预览和发表的点击路径见 [mp-publish.md](mp-publish.md)。

科技文把 `humanities` 换成 `tech`，社会热点换成 `social`。

不会命令行的人从 [beginner.md](beginner.md) 开始，让 AI 代跑命令。
