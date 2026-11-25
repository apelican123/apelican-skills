# Windows 快速开始

需要 WorkBuddy 的「这台电脑」运行模式、当前登录的 Windows 交互桌面、本地终端和图片读取工具。目标环境是 Windows 10 22H2 或 Windows 11，且存在系统自带的 .NET Framework C# 编译器。技能只带 C# 源码，无需另装 Python、Node、MCP 或字体。

## 1. 首次使用时由 WorkBuddy 配置

将 `$source` 设为本技能目录下 `scripts/ClickAlong.cs` 的绝对路径。使用本机 PowerShell 执行下列命令。使用当前会话的临时目录或用户允许的工作目录。示例输出路径可以保留至本次任务结束，后续步骤复用同一可执行文件。

```powershell
$source = (Resolve-Path -LiteralPath $source).Path
$build = Join-Path $env:TEMP ('ClickAlong-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $build | Out-Null
$exe = Join-Path $build 'ClickAlong.exe'
$compiler = @(
    (Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    (Join-Path $env:WINDIR 'Microsoft.NET/Framework/v4.0.30319/csc.exe')
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $compiler) { throw '未找到系统自带的 .NET Framework C# 编译器' }
& $compiler /nologo /target:exe /platform:anycpu /codepage:65001 /r:System.Drawing.dll /r:System.Windows.Forms.dll /r:System.Web.Extensions.dll "/out:$exe" $source
if ($LASTEXITCODE -ne 0) { throw '跟着操作编译失败' }
& $exe doctor
if ($LASTEXITCODE -ne 0) { throw '本机前置检查失败' }
& $exe selftest
```

终端工具如果提供 Bash，可通过系统 `powershell.exe -NoProfile -Command` 执行这一组普通终端命令。给含空格的文件路径正确加引号。本地终端执行或文件访问提示由用户处理。首次自检会打开独立的「跟着操作 · 首次自检」练习窗口，请给用户留足 18 秒切到它的标题栏，终端超时设为 35 秒以上。

- `doctor` 返回 Windows 构建、处理器架构、运行位数、屏幕和截图检查。它只在本进程内读取一个小区域，且不保存屏幕图像，也不注入点击。
- `selftest` 截取自己的练习窗，并按正常流程显示步骤卡、移动鼠标、点击测试按钮。输出 `desktop_test_passed` 和 `input_received=true` 后才说明本机自检通过。练习窗和临时截图会关闭和清理。
- 查不到编译器时，报告系统组件缺失。没有前台交互桌面时，引导用户回本机并解锁。截图不可用或安全策略限制本地运行时，报告具体失败。换到管理员启动的目标程序后，Windows 可能拒绝普通权限进程输入，此时说明限制。

## 2. 截图、框选、执行、核对

```powershell
& $exe list
& $exe shot 12345 23456 $frame
& $exe step 12345 23456 $actionJson
```

- `list` 返回窗口标题、进程名、句柄 `hwnd`、进程号 `pid`、`foreground` 和 `minimized`。确定具体文档。用户使其处于前台后再截图。对话框如果不能随主窗口截图，重新通过列表识别当前目标对话框。
- `shot` 保存实际桌面上可见的窗口区域。读取该 PNG，再确定整块按钮或输入框的边界。输出 JSON 中 `origin` 是截图左上角的物理屏幕坐标，`size` 是原图尺寸。若图片阅读工具缩放了截图，先换算到原图像素，再为横纵坐标加 `origin`，支持负坐标。画框应尽量完整框住目标，避开相邻按钮。
- 从最新截图的 JSON 原样复制 `focus`、`target_bounds`、`focus_bounds` 和 `titles` 到步骤文件，加入动作、说明和 `box`。`box` 用绝对坐标的 `[左, 上, 右, 下]`。每次重新截图确认焦点、菜单和实际值。键盘步骤也提供框的位置，它将标记用户应观察的区域，保持鼠标当前位置。
- 保存动作文件为 UTF-8 JSON，例如 `ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8`。实际值填在 `value`，步骤卡指引写清它的含义和单位。

```json
{
  "focus": 12345,
  "target_bounds": [0, 0, 1920, 1040],
  "focus_bounds": [0, 0, 1920, 1040],
  "titles": ["练习文档 - WPS Office", "练习文档 - WPS Office"],
  "mode": "demo",
  "number": 5,
  "title": "输入字号",
  "instruction": "在「字号」输入框输入 16 磅。",
  "expected": "字号框出现 16，正文还没有应用新字号。",
  "box": [525, 170, 564, 200],
  "action": "type",
  "value": "16"
}
```

| 动作 | 说明 |
| --- | --- |
| `click` / `right-click` | 以控件框中心为点击目标。陪练时等用户点进框内。 |
| `type` | 使用 `value`。先确认当前输入框已聚焦、原值已选中或者插入位置正确。 |
| `key` | `value` 可用 CTRL+A、TAB、SHIFT+TAB、ENTER、BACKSPACE、UP、DOWN、LEFT、RIGHT。 |
| `scroll` | `amount` 是滚轮格数，向上为正，范围 −5 至 5，排除 0。 |
| `point` | 提示与高亮控件，用于解释现状。 |

## 3. 处理中断和录屏

演示模式按住 Esc、移动鼠标或切换窗口会在发送下一动作前停止。陪练模式按住 Esc 或等待 45 秒会结束当前提示。手动点中后如果菜单变化或值未生效，用新截图定位，再继续。确认按钮用于告知 AI 用户已做完，结果仍要截图核对。

大字步骤卡优先放在离目标控件较远的一侧。红色细框圈出按钮或输入框，并可穿透鼠标。自动演示的紫色进度条对应读提示的等待时间，关闭 Windows 动画效果时使用静态显示。录屏优先选择桌面捕获，软件如有「捕获光标」可开启。仅捕获 WPS 应用窗口时，录制工具可能遗漏独立教学浮层。

## 已验证的环境

| 环境 | 验证状态 |
| --- | --- |
| Windows 11 x64，构建 26300，单屏 2520 × 1680 | 编译、前置检查、独立窗口截图和真实点击已通过。用 WPS 临时文档验证了目标高亮、步骤卡、计时进度和行距菜单。 |
| 其他 Windows 11 构建、Windows 10 22H2、ARM64、多屏与企业受管环境 | 尚无实机结果。首次使用请执行 `doctor` 和 `selftest`，教具体软件时再验证第一步。 |

桌面自检验证本机截图和输入能力。具体应用的不同版本、运行权限，以及 WorkBuddy 当前会话是否有终端与图片工具，仍会影响实际使用。
