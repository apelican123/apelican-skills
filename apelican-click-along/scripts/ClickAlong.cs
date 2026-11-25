using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Win32;

namespace ClickAlong
{
    public static class Tool
    {
        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                if (args.Length == 1 && args[0] == "list")
                    Write(Run("list", 0, 0, null));
                else if (args.Length == 1 && (args[0] == "doctor" || args[0] == "selftest"))
                    Write(Run(args[0], 0, 0, null));
                else if (args.Length == 2 && args[0] == "test-window")
                    TestWindow(args[1]);
                else if (args.Length == 4 && (args[0] == "shot" || args[0] == "step"))
                    Write(Run(args[0], Int64.Parse(args[1]), Int32.Parse(args[2]), args[3]));
                else
                    throw new ArgumentException("ClickAlong doctor | selftest | list | shot WINDOW PID PNG | step WINDOW PID JSON");
                return 0;
            }
            catch (Exception error)
            {
                Console.Error.WriteLine(error.Message);
                return 1;
            }
        }

        private static void Write(string json)
        {
            // Keep stdout lossless in both legacy Windows PowerShell and UTF-8 shells.
            var ascii = new System.Text.StringBuilder(json.Length);
            foreach (char value in json)
                if (value <= 127) ascii.Append(value);
                else ascii.AppendFormat("\\u{0:x4}", (int)value);
            Console.WriteLine(ascii.ToString());
        }

        public static string Run(string command, long window, int processId, string file)
        {
            IntPtr perMonitor = new IntPtr(-4);
            Native.SetProcessDpiAwarenessContext(perMonitor);
            IntPtr previous = Native.SetThreadDpiAwarenessContext(perMonitor);
            Require(previous != IntPtr.Zero, "Per-monitor DPI is unavailable.");
            try
            {
                if (command == "list") return ListWindows();
                if (command == "doctor") return Doctor();
                if (command == "selftest") return SelfTest();
                Require(window > 0 && processId > 0 && !String.IsNullOrWhiteSpace(file),
                        "Supply the window handle, process ID and file path.");
                IntPtr target = new IntPtr(window);
                Require(Ready(target, processId), "The target window is unavailable or minimized.");
                if (command == "shot") return Capture(target, processId, file);
                Step step = Json.Deserialize<Step>(File.ReadAllText(file));
                using (var activeStep = new Mutex(false, @"Local\ApelicanClickAlongInput"))
                {
                    bool acquired;
                    try { acquired = activeStep.WaitOne(0); }
                    catch (AbandonedMutexException) { acquired = true; }
                    Require(acquired, "Another Click Along step is already running.");
                    try { return RunStep(target, processId, step); }
                    finally { activeStep.ReleaseMutex(); }
                }
            }
            finally { Native.SetThreadDpiAwarenessContext(previous); }
        }

        private static string Doctor()
        {
            IntPtr focus = Native.GetForegroundWindow();
            Require(focus != IntPtr.Zero && Environment.UserInteractive, "No foreground window in the interactive desktop.");
            Rectangle screen = Screen.FromHandle(focus).Bounds;
            using (var sample = new Bitmap(8, 8))
            using (var graphics = Graphics.FromImage(sample))
                graphics.CopyFromScreen(screen.Location, Point.Empty, sample.Size);
            Native.Pointer();
            using (Process process = Process.GetCurrentProcess())
            using (RegistryKey version = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion"))
                return Json.Serialize(new { status = "preflight_passed",
                    windows_build = version == null ? null : version.GetValue("CurrentBuildNumber"),
                    windows_release = version == null ? null : version.GetValue("DisplayVersion"),
                    architecture = Native.Architecture(),
                    session = process.SessionId, process_bits = IntPtr.Size * 8, screens = Screen.AllScreens.Length,
                    primary_size = Edges(Screen.PrimaryScreen.Bounds), foreground_dpi = Native.GetDpiForWindow(focus),
                    visual_motion = Native.MotionAllowed(), capture = true, input_tested = false });
        }

        private static string SelfTest()
        {
            Doctor();
            string folder = Path.Combine(Path.GetTempPath(), "ClickAlong-check-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            string info = Path.Combine(folder, "window.json");
            string clicked = Path.Combine(folder, "clicked");
            string image = Path.Combine(folder, "capture.png");
            string stage = "window";
            var launch = new ProcessStartInfo(typeof(Tool).Assembly.Location, "test-window \"" + folder + "\"") {
                UseShellExecute = false, CreateNoWindow = true
            };
            using (Process fixture = Process.Start(launch))
            {
                try
                {
                    var clock = Stopwatch.StartNew();
                    while (!File.Exists(info) && !fixture.HasExited && clock.ElapsedMilliseconds < 4500)
                        Wait(60, null);
                    Require(File.Exists(info), "Could not open the temporary test window.");
                    FixtureInfo data = Json.Deserialize<FixtureInfo>(File.ReadAllText(info));
                    var target = new IntPtr(data.hwnd);
                    Require(Native.Pid(target) == fixture.Id, "The test window handle changed.");
                    clock.Restart();
                    while (Native.GetForegroundWindow() != target && !fixture.HasExited && clock.ElapsedMilliseconds < 18000)
                    {
                        Require(!Native.Down(27), "The test was cancelled.");
                        Wait(80, null);
                    }
                    Require(Native.GetForegroundWindow() == target,
                            "Select the Click Along test window title bar and run the test again.");
                    Wait(350, null);
                    stage = "capture";
                    Capture(target, fixture.Id, image);
                    using (var captured = new Bitmap(image))
                        Require(captured.Width >= data.box[2] - data.box[0] && captured.Height >= data.box[3] - data.box[1],
                                "The test window could not be captured.");
                    stage = "click";
                    Rectangle bounds = Native.Bounds(target);
                    string result = RunStep(target, fixture.Id, new Step { focus = data.hwnd,
                        target_bounds = Edges(bounds), focus_bounds = Edges(bounds),
                        titles = new[] { FixtureTitle, FixtureTitle }, mode = "demo", number = 1,
                        action = "click", title = "测试桌面点击", instruction = "看紫色框，技能会点击「测试按钮」。",
                        expected = "测试窗口收到点击后自动关闭。", box = data.box });
                    Require(File.Exists(clicked), "The test button did not receive the click.");
                    return Json.Serialize(new { status = "desktop_test_passed", capture = true,
                                                input_received = true, desktop_automation = Json.DeserializeObject(result) });
                }
                catch (Exception error) { throw new InvalidOperationException("Self-test " + stage + ": " + error.Message, error); }
                finally
                {
                    if (!fixture.HasExited) fixture.CloseMainWindow();
                    if (fixture.WaitForExit(3000))
                    {
                        if (File.Exists(info)) File.Delete(info);
                        if (File.Exists(clicked)) File.Delete(clicked);
                        if (File.Exists(image)) File.Delete(image);
                        Directory.Delete(folder, false);
                    }
                }
            }
        }

        private const string FixtureTitle = "跟着操作 · 首次自检";

        private static void TestWindow(string folder)
        {
            Native.SetProcessDpiAwarenessContext(new IntPtr(-4));
            using (var fixture = new Form())
            using (var description = new Label())
            using (var button = new Button())
            using (var font = new Font("Microsoft YaHei UI", 13))
            using (var lifetime = new System.Windows.Forms.Timer { Interval = 30000 })
            {
                fixture.Text = FixtureTitle;
                fixture.StartPosition = FormStartPosition.CenterScreen;
                fixture.ClientSize = new Size(460, 162);
                fixture.FormBorderStyle = FormBorderStyle.FixedDialog;
                fixture.MaximizeBox = false;
                fixture.MinimizeBox = false;
                fixture.TopMost = true;
                fixture.Font = font;
                description.Text = "先点一下窗口标题栏，把它切到前台。随后自检会点击下方测试按钮。";
                description.SetBounds(20, 20, 420, 48);
                button.Text = "测试按钮";
                button.SetBounds(150, 85, 160, 45);
                button.Click += delegate { File.WriteAllText(Path.Combine(folder, "clicked"), "ok"); };
                fixture.Controls.Add(description);
                fixture.Controls.Add(button);
                fixture.Shown += delegate
                {
                    string pending = Path.Combine(folder, "window.pending");
                    File.WriteAllText(pending, Json.Serialize(new FixtureInfo {
                        hwnd = fixture.Handle.ToInt64(), box = Edges(button.RectangleToScreen(button.ClientRectangle))
                    }));
                    File.Move(pending, Path.Combine(folder, "window.json"));
                };
                lifetime.Tick += delegate { fixture.Close(); };
                lifetime.Start();
                Application.Run(fixture);
            }
        }

        private static string ListWindows()
        {
            var items = new List<object>();
            IntPtr foreground = Native.GetForegroundWindow();
            Native.EnumWindows(delegate(IntPtr window, IntPtr unused)
            {
                if (!Native.IsWindowVisible(window)) return true;
                string title = Native.Title(window);
                if (String.IsNullOrWhiteSpace(title)) return true;
                int pid = Native.Pid(window);
                items.Add(new { hwnd = window.ToInt64(), pid, exe = Native.App(pid), title,
                                foreground = window == foreground, minimized = Native.IsIconic(window) });
                return true;
            }, IntPtr.Zero);
            return Json.Serialize(items);
        }

        private static string Capture(IntPtr target, int pid, string file)
        {
            IntPtr focus = Native.GetForegroundWindow();
            CheckFocus(target, pid, focus);
            Rectangle targetBounds = Native.Bounds(target);
            Rectangle focusBounds = Native.Bounds(focus);
            string[] titles = { Native.Title(target), Native.Title(focus) };
            Rectangle capture = Rectangle.Intersect(Rectangle.Union(targetBounds, focusBounds),
                                                    SystemInformation.VirtualScreen);
            Require(capture.Width > 0 && capture.Height > 0, "The window is outside the visible desktop.");
            using (var bitmap = new Bitmap(capture.Width, capture.Height, PixelFormat.Format32bppRgb))
            {
                using (Graphics graphics = Graphics.FromImage(bitmap))
                    graphics.CopyFromScreen(capture.Location, Point.Empty, capture.Size);
                CheckState(target, pid, focus, targetBounds, focusBounds, titles);
                bitmap.Save(file, ImageFormat.Png);
            }
            return Json.Serialize(new { origin = new[] { capture.Left, capture.Top },
                size = new[] { capture.Width, capture.Height }, focus = focus.ToInt64(),
                target_bounds = Edges(targetBounds), focus_bounds = Edges(focusBounds), titles });
        }

        private static string RunStep(IntPtr target, int pid, Step step)
        {
            Require(step != null && (step.mode == "demo" || step.mode == "follow"), "Use mode demo or follow.");
            Require(step.number >= 1 && step.number <= 999, "Use a valid step number.");
            Require(!String.IsNullOrWhiteSpace(step.title) && step.title.Length <= 26,
                    "Use a short title of 1 to 26 characters.");
            Require(!String.IsNullOrWhiteSpace(step.instruction) && step.instruction.Length <= 68,
                    "Use a concrete instruction of 1 to 68 characters.");
            Require(step.expected == null || step.expected.Length <= 56, "Use up to 56 characters for the expected result.");
            Require(step.action == "click" || step.action == "right-click" || step.action == "type" ||
                    step.action == "key" || step.action == "point" || step.action == "scroll",
                    "Use a supported action.");
            var focus = new IntPtr(step.focus);
            Rectangle targetBounds = FromEdges(step.target_bounds);
            Rectangle focusBounds = FromEdges(step.focus_bounds);
            Rectangle control = FromEdges(step.box);
            CheckState(target, pid, focus, targetBounds, focusBounds, step.titles);
            Point point = new Point(control.Left + control.Width / 2, control.Top + control.Height / 2);
            Require(control.Width > 0 && control.Height > 0 &&
                    Rectangle.Union(targetBounds, focusBounds).Contains(control) &&
                    Screen.FromPoint(point).Bounds.Contains(point), "The control box is outside the visible target.");
            IntPtr hit = HitTarget(point, target, pid);
            Require(hit != IntPtr.Zero, "The control is covered or outside the target window.");
            Native.Input[] inputs = step.mode == "demo" ? MakeInput(step) : new Native.Input[0];
            int dpi = (int)Native.GetDpiForWindow(Native.WindowFromPoint(point));
            float scale = Math.Max(1f, Math.Min(2f, dpi / 96f));
            bool sent = false;
            try
            {
                using (var outline = new Outline(control, scale))
                using (var card = new LessonCard(step, Screen.FromPoint(point).WorkingArea, control, scale))
                using (var halo = new Halo(scale))
                {
                    outline.ShowOverlay();
                    card.ShowOverlay();
                    if (step.mode == "follow")
                    {
                        string observed = Follow(step, target, pid, focus, targetBounds, focusBounds,
                                                 control, card, outline);
                        return Json.Serialize(new { status = observed, input_sent = false, step = step.number });
                    }

                    Point expected = Native.Pointer();
                    Action guard = delegate
                    {
                        CheckState(target, pid, focus, targetBounds, focusBounds, step.titles);
                        Require(Native.Pointer() == expected && !Native.ManualInput(),
                                "Manual input detected; stopped before sending input.");
                    };
                    guard();
                    bool move = step.action != "key" && step.action != "type";
                    bool motion = Native.MotionAllowed();
                    if (move)
                    {
                        Point start = expected;
                        halo.MoveTo(start);
                        halo.ShowOverlay();
                        int frames = motion ? 24 : 1;
                        for (int i = 1; i <= frames; i++)
                        {
                            guard();
                            double t = i / (double)frames;
                            t = t * t * (3 - 2 * t);
                            expected = new Point((int)Math.Round(start.X + (point.X - start.X) * t),
                                                 (int)Math.Round(start.Y + (point.Y - start.Y) * t));
                            Require(Native.SetCursorPos(expected.X, expected.Y), "Could not move the pointer.");
                            halo.MoveTo(expected);
                            Wait(18, null);
                        }
                    }
                    int readingTime = Math.Min(5500, 1500 + (step.instruction.Length + (step.expected ?? "").Length) * 35);
                    card.BeginCountdown(readingTime, motion);
                    Wait(readingTime, guard);
                    guard();
                    Require(HitTarget(point, target, pid) == hit, "The control changed. Take a fresh screenshot.");
                    if (inputs.Length > 0)
                    {
                        uint count = Native.SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(Native.Input)));
                        sent = count > 0;
                        Require(count == inputs.Length, "Windows accepted " + count + " of " + inputs.Length + " input events.");
                        outline.Complete();
                        halo.Complete();
                        card.ActionSent();
                    }
                    Wait(850, delegate
                    {
                        if (Native.Down(27)) throw new OperationCanceledException("Stopped by the user.");
                    });
                    return Json.Serialize(new { status = sent ? "input_sent" : "pointed", input_sent = sent,
                                                step = step.number });
                }
            }
            catch (Exception error)
            {
                if (sent) throw new InvalidOperationException("Input already sent. Inspect before retrying. " + error.Message, error);
                throw;
            }
        }

        private static string Follow(Step step, IntPtr target, int pid, IntPtr focus, Rectangle targetBounds,
                                     Rectangle focusBounds, Rectangle control, LessonCard card, Outline outline)
        {
            int button = step.action == "right-click" ? 2 : 1;
            bool watch = step.action == "click" || step.action == "right-click";
            bool previouslyDown = Native.Down(button);
            bool observedDown = false;
            var clock = Stopwatch.StartNew();
            while (clock.ElapsedMilliseconds < 45000)
            {
                Application.DoEvents();
                if (Native.Down(27)) return "cancelled";
                if (card.Acknowledged) return "user_acknowledged";
                bool down = Native.Down(button);
                // Check the actual mouse button and point only. The guide never records typed input.
                if (watch && down && !previouslyDown && control.Contains(Native.Pointer()) &&
                    HitTarget(Native.Pointer(), target, pid) != IntPtr.Zero)
                    observedDown = true;
                if (observedDown && !down)
                {
                    outline.Complete();
                    Wait(450, null);
                    return "click_observed";
                }
                if (!observedDown && !Native.AnyMouseButton())
                    CheckState(target, pid, focus, targetBounds, focusBounds, step.titles);
                previouslyDown = down;
                Thread.Sleep(12);
            }
            return "timed_out";
        }

        private static Native.Input[] MakeInput(Step step)
        {
            var list = new List<Native.Input>();
            switch (step.action)
            {
                case "point": break;
                case "click":
                    list.Add(Native.MouseEvent(2, 0)); list.Add(Native.MouseEvent(4, 0)); break;
                case "right-click":
                    list.Add(Native.MouseEvent(8, 0)); list.Add(Native.MouseEvent(16, 0)); break;
                case "scroll":
                    Require(step.amount != 0 && step.amount >= -5 && step.amount <= 5, "Use a scroll amount from -5 to 5, excluding 0.");
                    list.Add(Native.MouseEvent(0x800, unchecked((uint)(step.amount * 120)))); break;
                case "type":
                    Require(!String.IsNullOrEmpty(step.value) && step.value.Length <= 160 &&
                            Array.FindIndex(step.value.ToCharArray(), Char.IsControl) < 0,
                            "Type 1 to 160 characters without control characters.");
                    foreach (char letter in step.value)
                    {
                        list.Add(Native.KeyEvent(0, letter, 4)); list.Add(Native.KeyEvent(0, letter, 6));
                    }
                    break;
                case "key":
                    var shortcuts = new Dictionary<string, ushort[]>
                    {
                        { "CTRL+A", new ushort[] { 17, 65 } }, { "TAB", new ushort[] { 9 } },
                        { "SHIFT+TAB", new ushort[] { 16, 9 } }, { "ENTER", new ushort[] { 13 } },
                        { "BACKSPACE", new ushort[] { 8 } }, { "UP", new ushort[] { 38 } },
                        { "DOWN", new ushort[] { 40 } }, { "LEFT", new ushort[] { 37 } },
                        { "RIGHT", new ushort[] { 39 } }
                    };
                    ushort[] keys;
                    if (!shortcuts.TryGetValue((step.value ?? "").ToUpperInvariant(), out keys))
                        throw new InvalidOperationException("Unsupported shortcut.");
                    foreach (ushort key in keys) list.Add(Native.KeyEvent(key, 0, 0));
                    for (int i = keys.Length - 1; i >= 0; i--) list.Add(Native.KeyEvent(keys[i], 0, 2));
                    break;
            }
            return list.ToArray();
        }

        private static void Wait(int milliseconds, Action guard)
        {
            var clock = Stopwatch.StartNew();
            while (clock.ElapsedMilliseconds < milliseconds)
            {
                if (guard != null) guard();
                Application.DoEvents();
                Thread.Sleep(Math.Min(14, milliseconds));
            }
        }

        private static bool Ready(IntPtr target, int pid)
        {
            return Native.Pid(target) == pid && Native.IsWindowVisible(target) && !Native.IsIconic(target);
        }

        private static bool Related(IntPtr window, IntPtr target, int pid)
        {
            if (window == IntPtr.Zero) return false;
            IntPtr root = Native.GetAncestor(window, 2);
            if (root == target) return true;
            if (Native.GetAncestor(window, 3) != Native.GetAncestor(target, 3)) return false;
            int owner = Native.Pid(root);
            string executable = Native.App(pid);
            return owner == pid || (!String.IsNullOrEmpty(executable) && Native.App(owner) == executable);
        }

        private static IntPtr HitTarget(Point point, IntPtr target, int pid)
        {
            IntPtr window = Native.WindowFromPoint(point);
            if (Related(window, target, pid)) return window;
            // WPS Writer uses ownerless Qt popup windows on the ribbon's GUI thread.
            if (window == IntPtr.Zero || Native.Class(window) != "Qt5QWindowPopupSaveBits" ||
                Native.App(pid) != "wps.exe" || Native.App(Native.Pid(window)) != "wps.exe" ||
                !Native.Bounds(target).Contains(point)) return IntPtr.Zero;
            uint thread = Native.GetWindowThreadProcessId(window, IntPtr.Zero);
            bool matched = false;
            Native.EnumChildWindows(target, delegate(IntPtr child, IntPtr unused)
            {
                matched = Native.IsWindowVisible(child) && Native.GetWindowThreadProcessId(child, IntPtr.Zero) == thread;
                return !matched;
            }, IntPtr.Zero);
            return matched ? window : IntPtr.Zero;
        }

        private static void CheckFocus(IntPtr target, int pid, IntPtr focus)
        {
            Require(Ready(target, pid), "The target window became unavailable or minimized.");
            IntPtr current = Native.GetForegroundWindow();
            Require(focus == current && Related(focus, target, pid),
                    "Foreground changed. Bring the intended window forward and inspect it again." +
                    (Native.Pid(current) == pid ? " Active window class: " + Native.Class(current) : ""));
        }

        private static void CheckState(IntPtr target, int pid, IntPtr focus, Rectangle bounds,
                                       Rectangle foregroundBounds, string[] titles)
        {
            CheckFocus(target, pid, focus);
            Require(titles != null && titles.Length == 2 && Native.Title(target) == titles[0] &&
                    Native.Title(focus) == titles[1] && bounds == Native.Bounds(target) &&
                    foregroundBounds == Native.Bounds(focus), "The target changed. Take a fresh screenshot.");
        }

        private static int[] Edges(Rectangle rect)
        {
            return new[] { rect.Left, rect.Top, rect.Right, rect.Bottom };
        }

        private static Rectangle FromEdges(int[] values)
        {
            Require(values != null && values.Length == 4, "Expected four rectangle edges.");
            return Rectangle.FromLTRB(values[0], values[1], values[2], values[3]);
        }

        private static void Require(bool condition, string message)
        {
            if (!condition) throw new InvalidOperationException(message);
        }
    }

    public sealed class Step
    {
        public string mode { get; set; }
        public int number { get; set; }
        public string title { get; set; }
        public string instruction { get; set; }
        public string expected { get; set; }
        public string action { get; set; }
        public string value { get; set; }
        public int amount { get; set; }
        public long focus { get; set; }
        public int[] target_bounds { get; set; }
        public int[] focus_bounds { get; set; }
        public string[] titles { get; set; }
        public int[] box { get; set; }
    }

    public sealed class FixtureInfo
    {
        public long hwnd { get; set; }
        public int[] box { get; set; }
    }

    internal abstract class Overlay : Form
    {
        protected static readonly Color TransparentArea = Color.Magenta;
        protected static readonly Color Ink = Color.FromArgb(29, 24, 61);
        protected static readonly Color Accent = Color.FromArgb(101, 70, 235);
        protected static readonly Color Confirmed = Color.FromArgb(33, 142, 102);
        protected readonly float ScaleFactor;
        private readonly bool clickThrough;

        protected Overlay(float scale, bool transparent, bool clickThrough)
        {
            this.clickThrough = clickThrough;
            ScaleFactor = scale;
            AutoScaleMode = AutoScaleMode.None;
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.Manual;
            ShowInTaskbar = false;
            TopMost = true;
            DoubleBuffered = true;
            BackColor = transparent ? TransparentArea : Ink;
            if (transparent) TransparencyKey = TransparentArea;
        }

        protected int Px(int value) { return (int)Math.Round(value * ScaleFactor); }
        protected override bool ShowWithoutActivation { get { return true; } }
        internal void ShowOverlay() { Native.ShowWindow(Handle, 4); }

        protected override CreateParams CreateParams
        {
            get
            {
                CreateParams result = base.CreateParams;
                result.ExStyle |= 0x08000080; // WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
                if (clickThrough) result.ExStyle |= 0x00080020; // layered, mouse passes through
                return result;
            }
        }
    }

    internal sealed class Outline : Overlay
    {
        private bool complete;
        internal Outline(Rectangle control, float scale) : base(scale, true, true)
        {
            control.Inflate(Px(8), Px(8));
            Bounds = control;
        }

        internal void Complete() { complete = true; Refresh(); }

        protected override void OnPaint(PaintEventArgs e)
        {
            int margin = Px(4);
            using (var dark = new Pen(Ink, Px(8)))
            using (var color = new Pen(complete ? Confirmed : Accent, Px(4)))
            {
                var box = new Rectangle(margin, margin, Width - 2 * margin - 1, Height - 2 * margin - 1);
                e.Graphics.DrawRectangle(dark, box);
                e.Graphics.DrawRectangle(color, box);
            }
        }
    }

    internal sealed class Halo : Overlay
    {
        private bool complete;
        internal Halo(float scale) : base(scale, true, true) { Size = new Size(Px(48), Px(48)); }
        internal void MoveTo(Point pointer)
        {
            Native.SetWindowPos(Handle, new IntPtr(-1), pointer.X - Width / 2, pointer.Y - Height / 2,
                                Width, Height, 0x0010);
        }
        internal void Complete() { complete = true; Refresh(); }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            int pad = Px(5);
            using (var dark = new Pen(Ink, Px(8)))
            using (var color = new Pen(complete ? Confirmed : Accent, Px(4)))
            {
                var ring = new Rectangle(pad, pad, Width - 2 * pad, Height - 2 * pad);
                e.Graphics.DrawEllipse(dark, ring);
                e.Graphics.DrawEllipse(color, ring);
            }
        }
    }

    internal sealed class LessonCard : Overlay
    {
        private static readonly Color Paper = Color.FromArgb(250, 249, 255);
        private static readonly Color Lavender = Color.FromArgb(234, 229, 255);
        private static readonly Color Muted = Color.FromArgb(79, 71, 109);
        private readonly Step step;
        private readonly Font heading;
        private readonly Font body;
        private readonly Font footer;
        private readonly Rectangle next;
        private readonly Rectangle instruction;
        private readonly Rectangle expected;
        private readonly System.Windows.Forms.Timer animation;
        private readonly Stopwatch countdown = new Stopwatch();
        private int duration;
        private bool actionSent;
        internal bool Acknowledged { get; private set; }

        internal void ActionSent() { actionSent = true; animation.Stop(); Refresh(); }

        internal void BeginCountdown(int milliseconds, bool animate)
        {
            if (!animate) return;
            duration = milliseconds;
            countdown.Restart();
            animation.Start();
        }

        internal LessonCard(Step step, Rectangle screen, Rectangle control, float scale)
            : base(scale, step.mode == "demo", step.mode == "demo")
        {
            this.step = step;
            int width = Math.Min(Px(820), screen.Width - Px(34));
            bool compact = width < Px(590);
            heading = new Font("Microsoft YaHei UI", Px(compact ? 24 : 32), FontStyle.Bold, GraphicsUnit.Pixel);
            body = new Font("Microsoft YaHei UI", Px(compact ? 18 : 23), FontStyle.Regular, GraphicsUnit.Pixel);
            footer = new Font("Microsoft YaHei UI", Px(compact ? 14 : 16), FontStyle.Bold, GraphicsUnit.Pixel);
            int column = Px(82);
            int bodyWidth = width - column - Px(26);
            int expectedHeight = 0;
            int actionHeight;
            using (var graphics = CreateGraphics())
            {
                var maximum = new Size(bodyWidth, Px(400));
                var flags = TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix;
                actionHeight = Math.Max(Px(29), TextRenderer.MeasureText(graphics, step.instruction, body, maximum, flags).Height);
                if (!String.IsNullOrWhiteSpace(step.expected))
                    expectedHeight = Math.Max(Px(25), TextRenderer.MeasureText(graphics, step.expected, footer, maximum, flags).Height);
            }
            instruction = new Rectangle(column, Px(76), bodyWidth, actionHeight);
            expected = new Rectangle(column, instruction.Bottom + Px(11), bodyWidth, expectedHeight);
            int height = (expectedHeight == 0 ? instruction.Bottom : expected.Bottom) + Px(61);
            int y = control.Top - screen.Top >= screen.Bottom - control.Bottom ?
                    screen.Top + Px(18) : screen.Bottom - height - Px(18);
            Bounds = new Rectangle(screen.Left + (screen.Width - width) / 2, y, width, height);
            using (GraphicsPath shape = Round(new Rectangle(0, 0, width, height), Px(24)))
                Region = new Region(shape);
            next = new Rectangle(width - Px(164), height - Px(45), Px(142), Px(32));
            animation = new System.Windows.Forms.Timer { Interval = 32 };
            animation.Tick += delegate { Invalidate(new Rectangle(Px(24), Height - Px(12), Width - Px(48), Px(5))); };
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Paper);
            using (GraphicsPath shape = Round(new Rectangle(1, 1, Width - 2, Height - 2), Px(23)))
            using (var border = new Pen(Color.FromArgb(194, 183, 245), Px(2)))
                g.DrawPath(border, shape);
            var badge = new Rectangle(Px(24), Px(20), Px(76), Px(35));
            PaintPill(g, badge, Lavender);
            TextRenderer.DrawText(g, "第 " + step.number + " 步", footer, badge, Accent,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix);
            TextRenderer.DrawText(g, step.title, heading,
                new Rectangle(Px(112), Px(15), Width - Px(136), Px(48)), Ink,
                TextFormatFlags.NoPrefix | TextFormatFlags.EndEllipsis | TextFormatFlags.SingleLine);
            TextRenderer.DrawText(g, "操作", footer, new Point(Px(24), instruction.Top + Px(4)), Accent);
            TextRenderer.DrawText(g, step.instruction, body, instruction, Ink, TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix);
            if (expected.Height > 0)
            {
                TextRenderer.DrawText(g, "核对", footer, new Point(Px(24), expected.Top), Muted);
                TextRenderer.DrawText(g, step.expected, footer, expected, Muted, TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix);
            }
            string hint = step.mode == "follow" ? "轮到你操作    Esc 退出" :
                (actionSent ? "正在核对界面" : "AI 即将操作    Esc 停止");
            TextRenderer.DrawText(g, hint, footer, new Point(Px(24), Height - Px(38)),
                actionSent ? Confirmed : Muted, TextFormatFlags.NoPrefix);
            if (step.mode == "follow")
            {
                PaintPill(g, next, Accent);
                TextRenderer.DrawText(g, "已完成，继续", footer, next, Color.White,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
            }
            var track = new Rectangle(Px(24), Height - Px(12), Width - Px(48), Px(5));
            PaintPill(g, track, Lavender);
            double progress = actionSent ? 1 : duration == 0 ? 0 : Math.Min(1, countdown.ElapsedMilliseconds / (double)duration);
            track.Width = (int)(track.Width * progress);
            if (track.Width >= track.Height) PaintPill(g, track, actionSent ? Confirmed : Accent);
        }

        private static void PaintPill(Graphics graphics, Rectangle bounds, Color color)
        {
            using (GraphicsPath shape = Round(bounds, bounds.Height / 2))
            using (var fill = new SolidBrush(color)) graphics.FillPath(fill, shape);
        }

        private static GraphicsPath Round(Rectangle rect, int radius)
        {
            int d = 2 * radius;
            var shape = new GraphicsPath();
            shape.AddArc(rect.Left, rect.Top, d, d, 180, 90);
            shape.AddArc(rect.Right - d, rect.Top, d, d, 270, 90);
            shape.AddArc(rect.Right - d, rect.Bottom - d, d, d, 0, 90);
            shape.AddArc(rect.Left, rect.Bottom - d, d, d, 90, 90);
            shape.CloseFigure();
            return shape;
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            if (step.mode == "follow" && e.Button == MouseButtons.Left && next.Contains(e.Location))
                Acknowledged = true;
            base.OnMouseUp(e);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) { animation.Dispose(); heading.Dispose(); body.Dispose(); footer.Dispose(); }
            base.Dispose(disposing);
        }
    }

    internal static class Native
    {
        [StructLayout(LayoutKind.Sequential)] internal struct Rect { internal int L, T, R, B; }
        [StructLayout(LayoutKind.Sequential)] internal struct Mouse
        {
            internal int X, Y;
            internal uint Data, Flags, Time;
            internal UIntPtr Extra;
        }
        [StructLayout(LayoutKind.Sequential)] internal struct Keyboard
        {
            internal ushort Key, Scan;
            internal uint Flags, Time;
            internal UIntPtr Extra;
        }
        [StructLayout(LayoutKind.Explicit)] internal struct Payload
        {
            [FieldOffset(0)] internal Mouse Mouse;
            [FieldOffset(0)] internal Keyboard Keyboard;
        }
        [StructLayout(LayoutKind.Sequential)] internal struct Input
        {
            internal uint Type;
            internal Payload Payload;
        }
        internal delegate bool WindowCallback(IntPtr window, IntPtr arg);

        [DllImport("user32.dll")] internal static extern bool SetProcessDpiAwarenessContext(IntPtr context);
        [DllImport("user32.dll")] internal static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
        [DllImport("user32.dll")] internal static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] internal static extern IntPtr GetAncestor(IntPtr window, uint flags);
        [DllImport("user32.dll")] internal static extern IntPtr WindowFromPoint(Point point);
        [DllImport("user32.dll")] internal static extern bool IsWindowVisible(IntPtr window);
        [DllImport("user32.dll")] internal static extern bool IsIconic(IntPtr window);
        [DllImport("user32.dll")] internal static extern bool ShowWindow(IntPtr window, int command);
        [DllImport("user32.dll")] internal static extern bool GetWindowRect(IntPtr window, out Rect rect);
        [DllImport("user32.dll")] internal static extern bool GetCursorPos(out Point point);
        [DllImport("user32.dll")] internal static extern bool SetCursorPos(int x, int y);
        [DllImport("user32.dll")] internal static extern short GetAsyncKeyState(int key);
        [DllImport("user32.dll")] internal static extern uint GetDpiForWindow(IntPtr window);
        [DllImport("user32.dll")] internal static extern uint SendInput(uint count, Input[] inputs, int size);
        [DllImport("user32.dll")] internal static extern bool EnumWindows(WindowCallback callback, IntPtr arg);
        [DllImport("user32.dll")] internal static extern bool EnumChildWindows(IntPtr root, WindowCallback callback, IntPtr arg);
        [DllImport("user32.dll")] internal static extern uint GetWindowThreadProcessId(IntPtr window, out int pid);
        [DllImport("user32.dll")] internal static extern uint GetWindowThreadProcessId(IntPtr window, IntPtr unused);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowText(IntPtr window, System.Text.StringBuilder buffer, int length);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetClassName(IntPtr window, System.Text.StringBuilder buffer, int length);
        [DllImport("user32.dll")] internal static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);
        [DllImport("user32.dll", EntryPoint = "SystemParametersInfoW")]
        private static extern bool SystemParametersInfo(uint action, uint param, out int value, uint flags);
        [DllImport("kernel32.dll")]
        private static extern bool IsWow64Process2(IntPtr process, out ushort processMachine, out ushort nativeMachine);

        internal static string Architecture()
        {
            using (Process process = Process.GetCurrentProcess())
            {
                ushort emulated, native;
                try
                {
                    if (IsWow64Process2(process.Handle, out emulated, out native))
                    {
                        if (native == 0x8664) return "x64";
                        if (native == 0xaa64) return "arm64";
                        if (native == 0x014c) return "x86";
                    }
                }
                catch (EntryPointNotFoundException) { }
            }
            return "unknown";
        }

        internal static bool MotionAllowed()
        {
            int enabled;
            return SystemParametersInfo(0x1042, 0, out enabled, 0) && enabled != 0;
        }

        internal static int Pid(IntPtr window) { int pid; GetWindowThreadProcessId(window, out pid); return pid; }

        internal static string Title(IntPtr window)
        {
            var text = new System.Text.StringBuilder(1024);
            GetWindowText(window, text, text.Capacity);
            return text.ToString();
        }

        internal static string Class(IntPtr window)
        {
            var text = new System.Text.StringBuilder(128);
            GetClassName(window, text, text.Capacity);
            return text.ToString();
        }

        internal static string App(int pid)
        {
            if (pid <= 0) return "";
            try { using (Process process = Process.GetProcessById(pid)) return process.ProcessName.ToLowerInvariant() + ".exe"; }
            catch (ArgumentException) { return ""; }
            catch (InvalidOperationException) { return ""; }
            catch (System.ComponentModel.Win32Exception) { return ""; }
        }

        internal static Rectangle Bounds(IntPtr window)
        {
            Rect rect;
            if (!GetWindowRect(window, out rect)) throw new InvalidOperationException("Window bounds are unavailable.");
            return Rectangle.FromLTRB(rect.L, rect.T, rect.R, rect.B);
        }

        internal static Point Pointer()
        {
            Point point;
            if (!GetCursorPos(out point)) throw new InvalidOperationException("The interactive desktop is unavailable.");
            return point;
        }

        internal static bool Down(int key) { return (GetAsyncKeyState(key) & 0x8000) != 0; }
        internal static bool AnyMouseButton() { return Down(1) || Down(2) || Down(4); }
        internal static bool ManualInput()
        {
            return AnyMouseButton() || Down(16) || Down(17) || Down(18) || Down(27) || Down(91) || Down(92);
        }

        internal static Input MouseEvent(uint flags, uint data)
        {
            return new Input { Payload = new Payload { Mouse = new Mouse { Flags = flags, Data = data } } };
        }

        internal static Input KeyEvent(ushort vk, ushort scan, uint flags)
        {
            return new Input { Type = 1, Payload = new Payload { Keyboard = new Keyboard {
                Key = vk, Scan = scan, Flags = flags } } };
        }
    }
}
