# 元数据、结果与工具面设计

## 工具命名

- 使用 `verb_object`：`search_documents`、`fetch_document`、`create_order`。
- 不用 `do_api`、`request`、`tool_17` 等含义不清的名称。
- 名称一旦发布即保持稳定；行为变化用服务器版本和变更记录表达。

## `title` 与 `description`

`title` 供人阅读；`description` 供模型做选择。描述按以下顺序写：

1. 一句话说明工具完成的目标；
2. 何时使用；
3. 明确不要使用的邻近场景；
4. 重要前置条件或副作用；
5. 返回内容。

示例：

> Search documents in all connected knowledge bases. Use before fetch when the document ID is unknown. Do not use for web search. Returns ranked IDs, titles, snippets, and canonical URLs when the source provides them.

## 参数 schema

- 对象根、明确 `required`、尽量 `additionalProperties: false`；
- 时间使用 ISO 8601 并写明时区；
- 数量设置合理 min/max；
- ID 和人类标题分开；
- 枚举优于自由文本开关；
- 不让模型传可由服务端推导的账户 ID、密钥或内部路由。

## 输出 schema

- 对象根，稳定字段优先；
- 分页返回 `next_cursor` 或 `offset`，并写明终止条件；
- 大文档返回 `truncated` 和下一分块位置；
- 结果列表返回可排序的稳定 ID；
- 真实 URL 才能放入 `url`；没有则用空字符串并解释限制。

## 注解判断

| 行为 | readOnly | destructive | openWorld | idempotent |
|---|---:|---:|---:|---:|
| 查询私人数据库 | true | false | false | true |
| 搜索公开互联网 | true | false | true | true |
| 创建记录 | false | false | false | false/按幂等键 |
| 覆盖或删除 | false | true | false | 视实现 |
| 发帖、发信、支付 | false | 视后果 | true | 通常 false |

## 大目录压缩

超过几十个高度相似工具时，优先：

- 合并成少量任务型工具；或
- 暴露 `search_tools(query, platform?, limit?)`，返回精确工具名、用途和参数 schema；
- 暴露 `execute_read_tool(name, arguments)`，只允许经分类器和 allowlist 判定的只读工具；
- 写入工具独立暴露，不能通过通用执行器绕过确认和注解。

目录缓存必须有 TTL；并发有上限；不要每次 `tools/call` 都重新枚举全部上游。

