# 工具元数据与结果设计

## 让 GPT 选对工具

使用 `verb_object` 命名：`search_documents`、`fetch_document`、`create_order`。避免 `request`、`do_api`、`tool_17`。

description 按以下顺序写：

1. 这个工具完成什么目标；
2. 什么时候应该使用；
3. 什么时候不要使用；
4. 重要前置条件或副作用；
5. 返回什么。

示例：

> Search documents in connected knowledge bases. Use before fetch when the document ID is unknown. Do not use for web search. Returns ranked IDs, titles, snippets, and canonical URLs when available.

## 参数

- 对象根，明确 required，尽量关闭未知属性；
- 时间使用 ISO 8601 并写明时区；
- 数量设置 min/max；
- ID 与人类标题分开；
- 枚举优于自由文本开关；
- 不让模型填写可由服务端推导的账户 ID、密钥和内部路由。

## 结果

- 列表返回稳定 ID、分页 cursor 和终止条件；
- 大文档返回 truncated 与 next_offset，并提供分块工具；
- 真实 URL 才放进 url 字段；
- 媒体不要塞入巨大 base64 文本，使用资源/媒体块或授权 URL；
- 同时提供 structuredContent 与简洁文本兼容层。

## 注解判断

| 行为 | readOnly | destructive | openWorld | idempotent |
|---|---:|---:|---:|---:|
| 查询私人数据库 | true | false | false | true |
| 搜索互联网 | true | false | true | true |
| 创建记录 | false | false | 视情况 | 通常 false |
| 覆盖或删除 | false | true | 视情况 | 视实现 |
| 发帖、发信、支付 | false | 视后果 | true | 通常 false |

## 大型 API

数百个相似工具会降低选择准确率。优先合并为任务型工具；或使用：

- `search_tools(query, platform?, limit?)` 返回精确名称、描述和 input schema；
- `execute_read_tool(name, arguments)` 只执行经过 allowlist 判定的只读工具；
- 写工具独立注册，不能借通用执行器绕过确认。

目录设置 TTL，并限制枚举并发；每次调用前重新扫描全部上游通常既慢又浪费额度。

