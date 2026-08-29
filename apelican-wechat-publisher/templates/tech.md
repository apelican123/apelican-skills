---
title: 一份能复现的公众号排版清单
cover: ./cover.jpg
author: 你的名字
digest: 科技文要好看，先把步骤写成别人今晚能照着做的清单。
---

这是科技模板的骨架。保留小标题和代码块，把内容换成你的教程。

> 读者不是来看你有多会写形容词的。他们要的是：下一步点哪里。

## 你要先准备什么

- 已注册的微信公众号
- Node.js 18 或更高
- 一张 900×383 的封面

## 最短命令

安装排版命令：

```bash
npm install -g @wenyan-md/cli
wenyan --help
```

渲染但不上传：

```bash
wenyan render -f article.md -c templates/tech.css -h solarized-light
```

保存到草稿箱时，用技能包里的 `scripts/publish.sh` 或 `scripts/publish.ps1`。脚本不会替你群发。

## 常见失败怎么看

| 现象 | 先检查 |
| --- | --- |
| 40164 | IP 白名单 |
| 40001 | AppID / AppSecret 是否来自公众号 |
| 找不到封面 | frontmatter 的 `cover` |

## 写代码时

代码块前后各留一段人话。解释「为什么要跑」比解释「这是代码」更有用。不需要的 Mac 窗口圆点，发布时加上 `--no-mac-style`。
