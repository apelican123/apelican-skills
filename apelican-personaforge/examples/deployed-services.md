# 脱敏示例

以下只展示可复用设计，不包含真实域名、账号或凭证。

## REST 知识库

- 模式：A 翻译。
- 工具面：标准 `search(query)`、`fetch(id)`、可选分块 fetch。
- 关键点：跨知识库并发有上限；结果去重；稳定 ID；真实 canonical URL 才用于引用。
- 验证：搜索命中 → 取第一条稳定 ID → fetch 正文 → 检查 outputSchema。

## 健身与饮食记录

- 模式：A 翻译。
- 工具面：读取与写入分开注册。
- 关键点：写工具 `readOnlyHint=false`；支持 dry-run；确认日期、单位和记录；执行后读回。
- 验证：只读列表自动 fixture；写入使用人工确认流程。

## 单个第三方 MCP

- 模式：B 透明代理。
- 关键点：上游 token 只在 Secret；透传 MCP session；未知大响应流式返回；需要改 metadata 时才有界解析。
- 验证：initialize、tools/list、一个无副作用 call，以及 session 失效重建。

## 巨型社交数据目录

- 模式：C 编排。
- 工具面：`search_tools` + `execute_read_tool`，不直接暴露近千工具。
- 关键点：目录缓存、平台过滤、精确评分、只读 allowlist；写/发布/删除/关注/下单/支付工具不能走通用入口。
- 验证：搜索精确命中、零命中为空、只读调用成功、写类名称被拒绝。

## 最小验收表

| 项目 | 期望 |
|---|---|
| 无认证 | 401/403 |
| initialize | serverInfo + instructions |
| tools/list | 完整元数据，无 JSON-RPC error |
| tools/call | 真实数据，无 result.isError |
| 结构化返回 | structuredContent 匹配 outputSchema |
| 日志 | 无凭证、cookie、私人正文 |
| 部署 | 记录新旧 version ID，可单服务回滚 |

