# 踩坑记录

这些是真实跑过之后留下的，不是理论清单。

## Windows 上 ffmpeg「装了但找不到」

`winget install Gyan.FFmpeg` 成功后，当前终端的 `PATH` 往往还没有刷新；原生 Python 的 `shutil.which("ffmpeg")` 会返回空。

处理：脚本会额外扫描 WinGet Packages 里的 `Gyan.FFmpeg*` 目录，并在调用 yt-dlp 时传 `--ffmpeg-location`。不要只看 `where ffmpeg`。

## 缺 ffmpeg 不该一票否决

有官方字幕时，整条流水线用不到 ffmpeg。把 ffmpeg 当成核心硬依赖，会让「只抽字幕」的任务直接停。

处理：`check_env.py` 默认只要求 Python 和 yt-dlp。抽音频 / ASR 时再加 `--require-ffmpeg`。

## B站 412 不一定是没权限

无 Cookie 时 yt-dlp 拉网页常 412。Chrome 正在运行会锁 Cookie 数据库；Edge 可能 DPAPI 解不开。Firefox 有时是唯一能过的。

处理：脚本默认 none → chrome → edge → firefox。不要把「无法复制 Cookie 数据库」标成「视频下架」。

## 清洗脚本会把必剪整句粘成一坨

YouTube 自动字幕是 0.3 秒碎词，需要合并。必剪返回的是已经成句的口播，间隙经常小于 0.35 秒。同一套合并规则会把 157 句糊成 9 段。

处理：只合并「又短又碎」的 cue，不合并已经成句的识别结果。

## 文件名里的日期斜杠

规范写法是 `2026/09/01-标题.md`。Windows 和 POSIX 都不能在单个文件名里写 ASCII `/`，否则会变成多层目录。

处理：落盘用全角斜杠 `／`，看起来一样。

## 必剪不是官方 API

能用、免费、够写摘要。人名、谐音、黑话经常错。内部会议不要上传。接口随时会 412。
