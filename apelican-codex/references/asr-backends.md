# ASR 后端

默认路径：**云端必剪 Bcut → 失败再本地 faster-whisper**。不是反过来。

不要默认 OpenAI Whisper API（要 Key）。不要默认必剪桌面 GUI。剪映 / 快手 ASR 可作以后增强，不进默认路径。

## Bcut（默认）

社区实现走必剪网页/客户端同源接口：

`https://member.bilibili.com/x/bcut/rubick-interface`

参考 MIT 实现：`SocialSisterYi/bcut-asr`。本技能把调用封在 `scripts/asr_bcut.py`：

```python
from asr_bcut import transcribe
segments = transcribe(audio_path)  # [{start, end, text}] 单位秒
```

事实约束：

- 无官方 SLA，随时改字段、加校验、限流、限文件大小
- 等于把用户音频上传到 B 站侧服务器
- 隐私视频、内部会议、未公开内容默认不要走 Bcut，改用本地 Whisper
- 音频 > 20 分钟或文件 > 80MB：切 10–15 分钟一段，重叠 1–2 秒，识别后按时间拼接去重叠
- 轮询任务，超时 + 最多 3 次指数退避
- 返回空文本 = 失败，不是成功
- 原始 JSON/SRT 旁路写在 workdir，便于排错
- Markdown 里必须写：`转写方式：Bcut ASR（云端，音频已上传）`

支持容器：flac / aac / m4a / mp3 / wav。其他格式先转 mp3。

常见失败：

| 现象 | 码 | 下一步 |
|---|---|---|
| HTTP 412 resource/create | `E_BCUT` | 稍后重试；或改 Whisper |
| 空 utterances | `E_NO_SPEECH` | 不硬转 |
| 轮询超过 timeout | `E_TIMEOUT` | 切片后重试或 Whisper |
| 限流 / 5xx | `E_BCUT` | 退避后重试，再失败切 Whisper |

包 `bcut_asr` 未发布到 PyPI 也没关系，脚本自带客户端。

## faster-whisper（兜底）

仅当：Bcut 不可用 / 限流 / 超时；用户明确要求本地、不要上传；内容不适合上传。

- 默认模型：中文或中英混合 → `small`；纯英文短视频 → `base`；用户点名再用 `medium` / `large-v3`
- 有 CUDA 用 GPU，没有就 CPU，并提前告知「CPU 会很慢」
- 长音频同样切片，避免一次载入打爆内存
- 没装时禁止假装完成：

```text
pip install -U faster-whisper
```

不要把安装 large-v3 写成默认步骤。

## 失败码（ASR 相关）

`E_BCUT` `E_WHISPER` `E_NO_SPEECH` `E_TIMEOUT` `E_FFMPEG`

任一情况都不得渲染成「已完成转写」。
