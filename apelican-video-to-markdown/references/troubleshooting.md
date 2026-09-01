# 排错

脚本非 0 退出时 stderr 带 `E_*`，stdout 仍是 JSON `{ok:false,error:{code,message,hint}}`。

| 码 | 含义 | 对用户怎么说 |
|---|---|---|
| E_BAD_URL | 解析不出视频 | 链接不对或不是单视频 |
| E_UNSUPPORTED | yt-dlp 无提取器 / 直播未结束 | 站点暂不支持，或等直播结束 |
| E_PRIVACY | 私密 / 未发布 | 需要登录或权限 |
| E_MEMBER | 会员 / 充电 / 付费 | 需要对应身份 Cookie |
| E_AGE | 年龄限制 | 需要登录 Cookie |
| E_GEO | 地区限制 | 需要对应地区网络或 Cookie |
| E_COOKIE | 412 / 风控 / Cookie 库被锁 / DPAPI | 脚本会自动 none→chrome→edge→firefox。仍失败：关掉浏览器再试，或 `--cookies cookies.txt` |
| E_NO_MEDIA | 无可用音视频流 | 可能下架或 DRM |
| E_NO_SPEECH | 几乎无对白 | 音乐/纯画面，不硬转 |
| E_YTDLP | yt-dlp 未安装或过旧 | `pip install -U yt-dlp` |
| E_FFMPEG | 缺 ffmpeg | Windows：`winget install Gyan.FFmpeg`；macOS：`brew install ffmpeg`；Debian：`sudo apt install ffmpeg` |
| E_BCUT | Bcut 失败 | 原因 + 是否改 Whisper。隐私内容直接改本地 |
| E_WHISPER | Whisper 不可用 | `pip install -U faster-whisper`。不要装模作样，不要默认 large-v3 |
| E_TIMEOUT | 超时 | 可重试；长视频应切片 |

禁止把以上任何一种渲染成「已完成转写」。

## Cookie

不要自动导出用户浏览器 Cookie。Agent 也不能凭空变出登录态。

推荐顺序（`fetch_meta` / `fetch_subs` / `fetch_audio` 默认自动走完，不必手填）：

1. 无 Cookie
2. `--cookies-from-browser chrome`
3. edge
4. firefox（Chrome 锁库、Edge DPAPI 失败时常常只有它能过）
5. 用户自己导出的 `cookies.txt`

Netscape cookies.txt 即可。不要把 Cookie 写入 Markdown 或日志。

## 环境

`check_env.py` 能探测：Python ≥ 3.10、yt-dlp、ffmpeg、ffprobe、可选 faster-whisper、可选 CUDA。

缺 ffmpeg **不是**整条流水线的死刑：有官方字幕可以继续。抽音频 / ASR 才需要，那时用 `--require-ffmpeg`。脚本会扫 winget 的 Gyan.FFmpeg 安装目录，不依赖 PATH。

`--fix` 只会尝试 `pip install -U yt-dlp`。ffmpeg 是系统包，给命令不要假装已装。

做不到的事：不能保证宿主有联网、pip、管理员权限；不能在无 GPU 机器上默默跑 large-v3；不能把付费墙变免费。

## 长视频

音频 > 20 分钟或文件 > 80MB：先报时长，再切片识别。避免用户以为卡死。
