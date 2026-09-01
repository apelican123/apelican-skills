# 个人插件铸造机 · 全自动版

注册一个 Cloudflare，把 Token 交给 AI，拿到一条能接到 ChatGPT 插件的链接。

也覆盖大家常搜的说法：GPT 插件、ChatGPT 插件、ChatGPT 连接器、MCP、铸造、Cloudflare Workers、自动部署。

## 你只做两件事

1. 注册/登录 Cloudflare，创建一个只开了 Workers Scripts 编辑权限的 API Token，复制 Account ID。
2. 告诉 AI 要接什么服务（API 或 MCP 的地址和密钥）。

AI 会在你的 Cloudflare Workers 里完成配置：生成服务、写入密钥、打开公开地址、验证能用，然后给你一条 URL。你打开 ChatGPT 的 Developer mode，到插件页把这条 URL 加上即可。

## 什么时候会用到

- 手里有 API 或 MCP，想在 ChatGPT 里直接问
- 不想自己装 wrangler、不想碰 OAuth
- 多个接口想合成一个入口

## 使用前知道这些

- 需要能写文件、能联网的 AI（Hermes、Codex、Claude Code、Cursor）。纯网页 ChatGPT 没法替你部署。
- 必须先有可调用的接口；只有提示词造不出插件。
- ChatGPT 需要打开 Developer mode；有的账号没有这项。
- 完整链接就是钥匙，不要发到群里。

## 可以这样说

「帮我把这个 API 接进 ChatGPT：地址 …，密钥 …。Cloudflare Account ID 和 Token 是 …，只要查询，自用。」
