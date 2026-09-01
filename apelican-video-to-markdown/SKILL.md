---
name: apelican-video-to-markdown
description: 丢一条 B站或 YouTube 链接，整理成能存进笔记的 Markdown。看网课、补访谈、写课程笔记、做视频总结时用。有官方字幕就直接抽，没有再语音识别。也用于视频转写、Obsidian 笔记、B站字幕、YouTube transcript。适用于：视频总结/转文字/视频笔记/文字笔记/视频转写/B站字幕
license: Apache-2.0
metadata:
  version: "1.0.3"
  type: workflow
---

# 视频转 Markdown

看完一条长视频，却不想把两小时口播再听一遍时用这个技能。丢链接进去，它先查有没有现成字幕；有就直接抽，没有再只下载音轨做语音识别，最后给你一份带摘要、分章和时间戳的 Markdown，可以丢进 Obsidian 或任何笔记库。

默认一次跑完全程。不要先盘问模式；话里带了模式再切换。

## 运行前提

- Python 3.10+，以及 `yt-dlp`（`pip install -U yt-dlp`）。
- 有官方字幕时不需要 ffmpeg。没有字幕、要语音识别时才需要 ffmpeg。
- 默认识别走必剪云端（音频会上传到 B 站侧服务器）。隐私内容改用本地 Whisper。
- 不绕过付费墙、大会员墙、DRM。需要登录的视频，本机浏览器已登录时脚本会自动尝试读取 Cookie。

**先字幕，后识别。先元数据，后下载。只抽音频，不拉整片。** 有可用字幕时禁止下载音视频、禁止跑 ASR。

脚本目录：`scripts/`。模板：`assets/templates/`。站点/ASR/模式/排错细节见 `references/`。

## 不要做

- 不把弹幕、简介、评论当字幕
- 不绕过付费墙、DRM、验证码、盗链
- 不伪造字幕或把失败说成成功
- 不把整篇 Markdown 贴回对话（用户说「直接发出来」除外）
- 不默认 OpenAI Whisper API，不默认剪映/快手 ASR

## 模式（从用户原话解析，不要弹菜单）

| 用户说法 | 结果 |
|---|---|
| 没说 / 转成文档 / 只要 Markdown | `default` |
| 完整转写 / 原文 / 不要摘要只要原文 | `full` |
| 课程笔记 / 整理成笔记 / 适合 Obsidian | `notes`（再加「Obsidian」则模板用 `obsidian`） |
| 只要摘要 / 太长了先看重点 | `summary` |
| 保留/不要时间戳 | `timestamps=on/off`（默认 on） |
| 用中文整理 / 译成英文 | `output_lang` |
| 强制识别 / 不要用官方字幕 | `force_asr` |
| 用本地 Whisper / 不要上传 | `asr=whisper` |
| 只要关键词 / 只要大纲 | `default` 上裁剪章节 |

默认 `default`：标题 + 元数据 + 摘要 + 按主题分章 + 关键词 + 原始转写附录。

播放列表：默认只处理点名的那一条。用户明确说「整个播放列表」才批量，先报数量和预估耗时。多条 URL 逐条独立产出，失败互不影响。多 P 只处理 URL 里的 `p=`。

## 对用户怎么说

1. 收到链接先说：拿到了，先查有没有现成字幕。
2. 查到字幕：说明用了哪条轨道，开始整理文档。
3. 没有字幕：将抽音频并走必剪 ASR。内容明显私密/内部会议时先确认，或按用户「用本地」走 Whisper。
4. 时长 > 20 分钟：先报时长和步骤，再跑。
5. 结束：给文件路径 + 转写方式 + 一两句内容速览。问要不要存进笔记。不要再问时间戳。
6. 模式已经说清时，不要重复确认。

用 `terminal` 调脚本。Windows 优先 `python`；其他系统 `python3`。工作目录用当前项目目录。输出默认 `transcripts/`。

## 流水线（禁止跳步）

设 `SKILL=skills/media/apelican-video-to-markdown`（以本技能实际目录为准）。`IN` 是 URL / BV / 本地路径。`WORK=transcripts/.work/<id>/`。

1. 复述链接，解析模式。
2. `python SKILL/scripts/check_env.py --json`
   - 缺 Python / yt-dlp：按给出的命令装，再跑。仍缺则停。
   - 缺 ffmpeg：有可用字幕就继续；要抽音频/ASR 时再 `check_env.py --require-ffmpeg`，没有就停并给安装命令。
   - 可尝试：`pip install -U yt-dlp`。ffmpeg 只给安装命令，脚本会扫 winget 安装目录，不要假装已装。
3. `python SKILL/scripts/fetch_meta.py IN --out WORK/meta.json`
   - 直播未结束、DRM、无提取器：按错误码停。
   - 默认自动试 Cookie：无 Cookie → chrome → edge → firefox。不要一上来要 cookies.txt。
   - 付费墙/权限不足：停。不造假。
4. 选轨道（`force_asr` 则跳过）：
   - 有可用字幕：`python SKILL/scripts/fetch_subs.py IN --meta WORK/meta.json --workdir WORK --out WORK/segments.json`
   - 无字幕：`python SKILL/scripts/fetch_audio.py IN --workdir WORK --out WORK/audio.json`
     - 默认 `python SKILL/scripts/asr_bcut.py AUDIO --workdir WORK --out WORK/segments.json`
     - Bcut 失败或用户要求本地：`python SKILL/scripts/asr_whisper.py AUDIO --workdir WORK --out WORK/segments.json`
     - 两个都没有：停，给安装命令。
5. `python SKILL/scripts/clean_transcript.py WORK/segments.json --out WORK/cleaned.json`
6. **你来结构化**（脚本不做脑补）：
   - 按主题变化分章，不要每 2 分钟切一刀
   - 标题来自内容，禁止「第一部分」
   - 有可靠时间戳则章节开头写 `[hh:mm:ss]`
   - 有平台章节信息时当骨架，再按语义微调
   - 摘要 120–250 字，只写视频实际讲了什么
   - 不确定写 `[听不清]` / `[不确定]`，不编论文、数据、出处
   - 口语转书面，不改变原意；广告口播不要扩成评测
7. `python SKILL/scripts/render_markdown.py --meta WORK/meta.json --segments WORK/cleaned.json --mode MODE --transcript-source SOURCE --summary SUMMARY.txt --body BODY.md --out-dir transcripts/`
   - 用户说「不要原文」时加 `--no-raw`
8. 对话里给：文件路径 + 标题 + 一两句内容速览 + 转写方式。然后问要不要存进笔记或放到别处。不要问时间戳。成功后可删 `WORK` 里的音频；用户说「保留音频」才留。

文件名：`YYYY/MM/DD-视频标题.md`（例 `2026/09/01-我们的少年时代2品鉴.md`）。Windows/POSIX 文件名都不能含 ASCII `/`，落盘用全角斜杠 `／`，看起来一样。不要再把 BV/YouTube id 拼进文件名。

本地 `mp4/mkv/webm/mp3/m4a/wav/flac`：跳过下载，直接字幕探测或 ASR。

## 字幕优先级

B 站：`ai-zh` → `zh-Hans` / `zh-CN` / `zh` → 其他真人轨道（按目标语言）→ 音频+Bcut。永远忽略 `danmaku`。

YouTube：人工字幕 → 自动字幕 → 音频+ASR。自动字幕必清洗重复行。

其他站点：yt-dlp 能列出的字幕优先；列不出再抽音频；无提取器则 `E_UNSUPPORTED`。

可用字幕 = 带时间轴、对应口播/对白的轨道。简介、章节、标签只进元数据。评论默认不抓。

## 转写方式取值

写入 frontmatter `transcript_source`：

- `official-ai-sub` / `official-cc` / `yt-auto-sub` / `bcut-asr` / `faster-whisper`

Bcut 成功时对用户写明：转写方式：Bcut ASR（云端，音频已上传）。

## 错误码

脚本非 0 退出时 stderr 带 `E_*`。禁止把下列任一情况渲染成「已完成转写」。

| 码 | 对用户说 |
|---|---|
| `E_BAD_URL` | 链接不对或不是单视频 |
| `E_UNSUPPORTED` | 站点暂不支持（yt-dlp 无提取器）或直播未结束 |
| `E_PRIVACY` | 私密/未发布，需要登录或权限 |
| `E_MEMBER` | 会员/充电/付费，需要对应身份 Cookie |
| `E_AGE` | 年龄限制，需要登录 Cookie |
| `E_GEO` | 地区限制，需要对应地区网络或 Cookie |
| `E_COOKIE` | 412/风控/Cookie 库锁死/DPAPI。脚本已自动 none→chrome→edge→firefox。仍失败再给 cookies.txt |
| `E_NO_MEDIA` | 无可用音视频流，可能下架或 DRM |
| `E_NO_SPEECH` | 几乎无对白（音乐/纯画面），不硬转 |
| `E_YTDLP` | 未安装或过旧。更新：`pip install -U yt-dlp` |
| `E_FFMPEG` | 缺 ffmpeg。Windows：`winget install Gyan.FFmpeg`；macOS：`brew install ffmpeg`；Debian：`sudo apt install ffmpeg` |
| `E_BCUT` | 必剪失败。说明原因，问是否改本地 Whisper（隐私内容直接改） |
| `E_WHISPER` | Whisper 不可用。`pip install -U faster-whisper`。不要默认装 large-v3 |
| `E_TIMEOUT` | 超时，可重试；长视频应已切片 |

完整排错见 `references/troubleshooting.md`。

## 结构化与清洗边界

`clean_transcript.py` 只做机械清洗：去连续语气词、合并自动字幕重复行、合并过碎 cue。不改正专业术语（明显同音且上下文唯一除外）。

你负责分章、摘要、关键词。禁止发明视频没有的考点。

## 安全

- 只整理用户有权访问的内容，个人学习笔记
- 明显私密内容默认不要上传 Bcut；用户已说「用本地」则不上传
- 不在输出里保存 Cookie、Session、完整环境变量
- Bcut 是非官方消费级接口，无 SLA，等于把音频传到 B 站侧服务器。风险见 `references/asr-backends.md`

## 环境边界（写明做不到的）

能做：探测依赖、尽量 `pip install yt-dlp`、给出一条可复制的安装命令。

做不到：不能保证宿主有联网/pip/管理员权限；不能自动导出浏览器 Cookie；不能在无 GPU 机器上默默跑 large-v3；不能把付费墙视频变免费。

Whisper 默认：中文或中英混合用 `small`；纯英文短视频可用 `base`；用户点名再用 `medium` / `large-v3`。有 CUDA 用 GPU；CPU 要提前说会很慢。

## 验收（每次跑完自检）

- B 站有 `ai-zh`：不下音频、不跑 ASR
- B 站无字幕：只下音频 → Bcut
- YouTube 仅自动字幕：抽自动字幕并去重
- Bcut 超时：切 Whisper 或诚实失败
- `b23.tv` 能展开；`p=3` 只处理第 3 P
- 本地音频跳过 yt-dlp 下载
- 缺 ffmpeg 停并给命令
- 大会员无 Cookie → `E_MEMBER`，不造假
- 「整理成 Obsidian 课程笔记，不要原文」→ notes/obsidian 模板，无原始转写附录
- 对话里出现了成品绝对路径
