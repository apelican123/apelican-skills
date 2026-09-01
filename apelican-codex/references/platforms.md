# 站点差异

字幕定义：带时间轴、对应口播/对白的轨道。简介、章节、标签只进元数据。评论默认不抓。弹幕永远不是转写正文。

## Bilibili

输入：`bilibili.com/video/BVxxxx`、`b23.tv/xxx`（先展开短链）、纯 BV、`av` 号、多 P（`?p=2` 只处理该 P）。

字幕优先级：

1. `ai-zh`（官方 AI 字幕）
2. `zh-Hans` / `zh-CN` / `zh` 等人打 CC
3. 其他真人轨道（按用户目标语言）
4. 都没有 → 只抽音频 + Bcut
5. 忽略一切 `danmaku`

很多 `ai-zh` 接口要登录态。流程：先无 Cookie 试；412 / 登录限制再 `--cookies-from-browser chrome`（或 edge / firefox），或 `--cookies cookies.txt`。不要一上来要求导出 Cookie。

大会员、充电、定时发布、地区限制、风控 412 映射到 `E_MEMBER` / `E_PRIVACY` / `E_GEO` / `E_COOKIE`，不要说「转写失败」了事。

元数据：

```text
yt-dlp --dump-json --no-download --no-playlist URL
yt-dlp --list-subs URL
yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "ai-zh,zh-Hans,zh-CN,zh.*" --convert-subs srt URL
```

## YouTube

输入：`watch?v=`、`youtu.be/`、Shorts、11 位 video id。

优先级：人工字幕 → 自动字幕 → 音频 + ASR。

自动字幕常有重复行、缺标点。必须经过 `clean_transcript.py`。

## 其他 yt-dlp 站点

能列出字幕就用字幕；列不出再抽音频。站点不在提取器里 → `E_UNSUPPORTED`，禁止假写内容。

明确不承诺：未结束直播、DRM / 宽频限制、必须验证码人机的页面。

## 本地文件

`mp4/mkv/webm/mp3/m4a/wav/flac`：跳过下载。有同名 `.srt/.vtt` 当字幕；没有就 ASR。

## 音频规则

仅当无可用字幕或 `force_asr` 时：

```text
yt-dlp -f ba/bestaudio -x --no-playlist --no-warnings URL
```

优先保留 `m4a` / `webm` / `opus` / `aac`。仅当 ASR 后端不认该容器才 ffmpeg 转一次。Bcut 兼容：`mp3 / m4a / aac / wav / flac`。禁止无意义二次有损转码。

临时文件放 `transcripts/.work/<id>/`。成功后可删音频；用户说「保留音频」才留。

播放列表默认只处理点名的那一条。用户明确说整表才批量，先报数量和预估耗时。
