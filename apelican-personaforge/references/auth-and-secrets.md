# 认证与 Secret 边界（4.0.1：默认非 OAuth）

## 三个问题，全「否」就走默认路径

| 问题 | 全否 | 任一为是 |
|---|---|---|
| 公开发布、用户很多？ | 默认 **noauth + URL 路径令牌** | 才考虑 OAuth 2.1 |
| 不同用户访问各自数据？ | | |
| 必须独立撤销 / 刷新 / 审计？ | | |

默认：

```text
ChatGPT 端：No authentication
服务端：    /u/<token_hex(32)>/mcp ，Secret LINK_TOKEN 存同一段明文
```

- ChatGPT 不填认证头，只有拿着完整 URL 的人能调用
- **不要把 Secret 存成哈希再和路径明文比较**——4.0.0 文档这么写会导致正确链接 401
- 泄露：覆盖 `LINK_TOKEN`，旧 URL 立刻失效

OAuth 更麻烦，ChatGPT 端验证失败常见。只在「多人各自数据 / 公开产品 / 必须撤销」成立且用户确认后才走。

## 三类信息分开

1. 上游凭据 → Worker Secret `UPSTREAM_KEY`
2. 插件入口 → 路径令牌
3. 普通配置 → 可写进代码

## 铸造模式收到真实凭据

只用在本次 Cloudflare API 调用，用完清掉。不写进技能文件、Git、日志、回复。`CF_API_TOKEN` 交付后建议用户删除。上游密钥进过对话，交付时提醒轮换。
