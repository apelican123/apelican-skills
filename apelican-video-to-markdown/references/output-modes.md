# 输出模式与模板

模板在 `assets/templates/`。`render_markdown.py` 负责填元数据和原始转写；摘要、分章、关键词由 Agent 写好再传入。

文件名：`YYYY/MM/DD-视频标题.md`（落盘为 `2026／09／01-标题.md`，全角斜杠）。不要拼视频 id。  
默认目录：当前工作目录 `transcripts/`。

对话里不要把整篇再贴一遍，除非用户说「直接发出来」。

## 开关

- `timestamps=on/off`（默认 on）。开则章节开头和原始转写带 `[hh:mm:ss]`
- `output_lang`：用中文整理 / 译成英文。翻译是整理，不是发明
- `force_asr`：跳过官方字幕
- `asr=whisper`：不上传

## default

`assets/templates/default.md`

标题 + 元数据 + 摘要 + 按主题分章正文 + 关键词 + 原始转写附录。

摘要 120–250 字，只概括视频实际讲了什么。

## full

`assets/templates/full-transcript.md`

摘要可极短或省略。原始转写是主体，最大保留原句。

## notes

`assets/templates/notes.md`

课程笔记：结论、步骤、定义、可执行清单。仍不得发明视频没有的考点。默认无原始转写附录。

用户说「整理成 Obsidian 课程笔记，不要原文」→ `notes` 或 `obsidian`，不要附录。

## summary

沿用 default 模板，渲染时丢掉「原始转写」。只留摘要 + 大纲 + 关键词。

## obsidian

`assets/templates/obsidian.md`

在 default 上加 `aliases`、短标题、callout。双向链接友好。

## Agent 结构化规则

- 按主题变化分章，不要每 2 分钟切一刀
- 章节标题来自内容，禁止「第一部分」
- 有可靠时间戳就在章节开头写 `[hh:mm:ss]`
- 平台章节信息优先当骨架，再按语义微调
- 口语转书面，不改变原意
- 听不清标 `[听不清]` / `[不确定]`
- 禁止把没有的数据、论文、出处编进去
- 禁止把广告口播扩成产品评测

`render_markdown.py` 在没收到 `--body` 时会按平台章节或约 90 秒窗口做机械骨架，那只是垫底。Agent 必须覆盖成真正的主题分章。
