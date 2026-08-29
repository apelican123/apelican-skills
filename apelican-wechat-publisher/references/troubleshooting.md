# 故障排查

先看报错原文，再对号入座。改完只重试一次。

## wenyan: command not found

还没装，或当前终端找不到全局 npm 目录。

```bash
npm install -g @wenyan-md/cli
wenyan --help
```

```powershell
npm install -g @wenyan-md/cli
wenyan --help
```

若 `node -v` 也失败，先安装 Node.js 18+。

## WECHAT_APP_ID is required / 凭证未设置

`.env` 不在技能根目录，或当前环境变量是空的。

- 文件名必须是 `.env`，不要保存成 `.env.txt`
- 每行 `KEY=value`，不要加引号
- 先 `setup` 再 `publish`
- 也可以：`wenyan publish -f article.md --env-file=.env`

## 40164 invalid ip / ip not in whitelist / 45166

当前出口 IP 不在白名单。

1. 再查一次公网 IPv4。
2. 把微信返回的那个 IP（如果有）加进开发密钥页。
3. 不要填 `127.0.0.1`。
4. 开了代理就以实际出口为准。
5. 用户自己改白名单后，再重试一次。

## 40001 invalid credential

AppID 或 AppSecret 不对，或用了开放平台移动应用的 ID，或密钥已被重置。

回到开发者平台核对公众号 AppID；AppSecret 只能重置后重新保存。

## 48001 api unauthorized

这个公众号没有该接口权限。去「接口管理 → 接口权限与额度」看草稿和素材接口。不要靠反复跑脚本解决。

## 未能找到文章封面 / title is required

Markdown 顶部缺少完整 frontmatter。必须同时有 `title` 和 `cover`。`cover` 指向真实存在的本地文件或可访问的图片 URL。

## Failed to upload image

- 路径写错，文件不在 Markdown 旁边
- 格式不是 jpg/png/gif 等常见类型
- 单张超过约 10MB
- 网络图片打不开
- 正文图片不是相对路径、绝对路径或 http(s) URL

## connect ETIMEDOUT

本机到 `https://api.weixin.qq.com` 不通。先在同一终端测试：

```bash
curl -I https://api.weixin.qq.com
```

```powershell
Invoke-WebRequest -Method Head -Uri https://api.weixin.qq.com
```

终端走的代理必须和查 IP 时一致。

## 发布成功但后台看不到

去 https://mp.weixin.qq.com/ 的**草稿箱**，不是已发表列表。创建草稿不会出现在粉丝时间线。

## 标题被截断或接口抱怨标题过长

接口要求标题不超过 32 个字。后台编辑器有时显得更宽，以接口为准。

## 中文变成乱码

保存 Markdown 为 UTF-8（不要 UTF-16）。Windows 记事本「带 BOM 的 UTF-8」一般可用；若 wenyan 报解析问题，改成无 BOM 的 UTF-8。

## 点了发布脚本两次，出现两篇一样的草稿

接口成功后不要立刻重试。先去后台数草稿数量。本技能要求单次请求只创建一份。

## 调试

```bash
export DEBUG=wenyan:*
./scripts/publish.sh article.md templates/humanities.css github
```

```powershell
$env:DEBUG = "wenyan:*"
.\scripts\publish.ps1 article.md templates\humanities.css github
```

不要在调试输出里把 AppSecret 贴给任何人。

## PowerShell 无法运行脚本

报错类似 `running scripts is disabled`。不要改系统策略。改用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\publish.ps1 article.md templates\humanities.css github
```

或让 AI 用 Git Bash 跑 `.sh`。

## npm / wenyan 提示权限不够

Windows 不要用「管理员」乱装。关掉终端再开一次；若仍失败，把 Node 安装程序重跑并勾选 Add to PATH。不要把技能文件夹放进需要管理员才能写的目录。

## 后台找不到草稿

先到 https://mp.weixin.qq.com/ ，左侧找「内容与互动」「草稿箱」或「图文」。标题对不上就用创建时间排序。详细点击见 [mp-publish.md](mp-publish.md)。

## wenyan 显示「发布成功」但粉丝没收到

这是进了草稿箱，不是群发。到后台预览，再自己点发表。技能不会替你群发。
