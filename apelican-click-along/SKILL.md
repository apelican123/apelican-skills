---
name: apelican-click-along
display_name: 跟着操作
display_name_en: Click Along
description: 把 WorkBuddy 的 Windows 桌面操作变成逐步教学。框出要点的按钮或输入框，在大字卡上写清点哪里、输什么、怎么确认。适用于 WPS 等软件的操作演示、陪练和录屏。
description_zh: AI 每点一步，屏幕上就出现一张教学卡。看清按钮、输入值和核对方法，也能自己跟着点。
description_en: Watch each WorkBuddy desktop action on Windows, with a highlighted control and clear instructions for what to click, type, and verify. Or follow along yourself.
version: 1.1.1
author: Apelican
examples_zh:
  - 用跟着操作演示 WPS 把行距改成 1.5 倍，字号改成 16 磅。
  - 用跟着操作教我调段前和段后间距，我自己点击和输入。
examples_en:
  - Use Click Along to show me how to change line spacing in WPS.
  - Walk me through the settings and let me click each highlighted button.
---

# 跟着操作 · Click Along

复用用户当前的 WorkBuddy 和模型。由当前 AI 观察目标应用、选下一步和写教学提示。技能负责在 Windows 主桌面画出提示和控件框，以及按用户选择执行或等待动作。配置和指令见 [Windows 快速开始](references/windows.md)。

## 选择模式

- 用户说「帮我演示」「你来操作」时用 `demo`。预先显示本步说明、框出真实控件，移动并突出标记系统鼠标，然后执行这一个动作。
- 用户说「我自己点」「带我做」时用 `follow`。显示同样的指引，用户点目标控件后观察结果。输入、按键和滚动等操作由用户完成，随后点击步骤卡上的「已完成，继续」。
- 若仅说「用跟着操作演示」，默认 `demo`。用户可在后续步骤改变模式。示范文档可留在编辑态，按用户指示决定是否保存。

## 逐步教学

1. 初次使用在本机编译后运行 `doctor`。通过后，在首次教学前运行 `selftest` 核对专用练习窗口能收到真实点击。需要时请用户把自检窗口切到前台，成功后再开始教学。前置检查通过只代表能取图，`desktop_test_passed` 才表示本机练习点击通过。完整用法和故障提示见 [Windows 快速开始](references/windows.md)。
2. 截取当前窗口，逐个确定可见控件及其边界。用户在桌面上看到的每个有意义的动作都要有编号和介绍，包括展开菜单、选择选项、点进输入框、替换旧值、输入、按键确认及需要展示的滚动或导航。不要在步骤之间悄悄批量操作。一个菜单完全展开后再框它的下一项。
3. 每一步写三个字段。标题用动词短语，如「填写段后间距」。`instruction` 只写本步动作，如「在『段后』输入 6 磅」。`expected` 写可见结果，如「输入框显示 6 磅，对话框仍打开」。点进输入框、录入和点击「确定」分别提示。保持目标窗口在前台，控件名称、选项、数值和单位以截图为准。
4. 仅发送一个 `step`，完成后看新截图再决定下一步。凭控件、对话框、菜单选中值和应用后的实际画面判断结果。用户中止、切换窗口、点击未生效或窗口发生意外变化时，停下来重新观察。不重放旧坐标，不把“已发送输入”当成“设置已经生效”。
5. 最后指出实际生效的值和入口。可为用户总结自己重做时要走的路径。临时截图与动作文件仅用于当前任务，按环境权限清理本次产生的临时文件。

此技能适用于前台教学。当前模型通过本地终端和图片读取工具逐步运行，用真实屏幕辨认每个控件。为了让用户看到全过程，演示期间避免用文档 API、宏、编辑文件或隔离桌面的整段代办来完成中间动作。遇到系统权限或安全弹窗，由用户处理；无需改系统执行策略或提高权限。
