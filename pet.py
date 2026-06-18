"""皮卡丘桌宠主程序(ASCII 自主玩耍版)。

运行:  python pet.py

桌面上是一只 ASCII 字符画皮卡丘,它会自己玩耍:
  - 待机眨眼、走来走去(真在桌面移动)、吃东西、开心放电
  - 你不理它,过一会儿它会自己睡觉(ZZZ)
点击它 → 开心放电 + 弹出聊天窗(底层 claude CLI,执行真实任务)。
窗口常驻所有桌面/全屏 App 之上,不进 Dock。
"""

import os
import random
import ssl
import subprocess
import sys
import urllib.request

from PyQt6.QtCore import Qt, QTimer, QPoint, QElapsedTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction, QColor, QCursor, QFont, QFontMetrics, QIcon, QPainter, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMenu, QSystemTrayIcon, QWidget,
)


class _ClickBubble(QLabel):
    """可点击的气泡 QLabel(点击发 clicked 信号)。"""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

import ascii_pika
import config
import macos_window
import scheduler
from chat_window import ChatWindow, ClaudeWorker


# ════════════════════════  素材(仅头像,给聊天窗用)  ════════════════════════
def _download(url, dest):
    try:
        subprocess.run(["curl", "-fsSL", "-o", dest, url],
                       check=True, capture_output=True, timeout=60)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception:
        pass
    try:
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
        with urllib.request.urlopen(url, context=ctx, timeout=60) as r, open(dest, "wb") as f:
            f.write(r.read())
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception:
        return False


def ensure_avatar():
    """聊天窗头像(高清 PNG),失败不致命。"""
    os.makedirs(config.ASSETS_DIR, exist_ok=True)
    if not os.path.exists(config.HD_PATH):
        _download(config.HD_URL, config.HD_PATH)


# ════════════════════════  桌宠窗口  ════════════════════════
class PikachuPet(QWidget):
    PAD = 24  # 窗口内边距(给气泡/电花留空间)

    def __init__(self):
        super().__init__()
        self._chat = None
        self._drag_offset = None
        self._press_pos = None
        self._moved = False
        # 区分单击/双击:单击后延迟一会儿执行,期间来双击则取消
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._do_single_click)

        # 行为状态
        self._state = "idle"
        self._frame = 0
        self._state_until = 0      # 当前状态结束时刻(ms)
        self._walk_dir = 1          # 1=右 -1=左
        self._jump_base_y = 0       # 跳跃起跳基准 y(落回用)
        self._after_state = None    # 动作链:当前状态到期后强制接入的 (state,dur)
        self._thinking_active = False  # 聊天等 claude 回复中(本体维持 think 态)
        self._drag_started = False  # 是否已切入拖拽挣扎态
        self._particles = []        # D特效:心情图标粒子 [{x,y,vy,ch,life,max,color}]
        self._mood_prev_state = "idle"  # 上一帧状态(用于检测进入 happy/cheer/sad)
        self._last_interact = 0     # 最近一次互动时刻
        self._t = QElapsedTimer()
        self._t.start()

        self._init_font()
        self._init_window()
        self._init_bubble()
        self._init_tray()
        self._init_timers()
        self._pick_new_state(first=True)

    # ---------- 字体/尺寸 ----------
    def _init_font(self):
        # 等宽字体,保证 ASCII 对齐
        self.font = QFont("Menlo")
        self.font.setStyleHint(QFont.StyleHint.Monospace)
        self.font.setPixelSize(config.ASCII_FONT_PX)
        self.font.setBold(True)
        fm = QFontMetrics(self.font)
        self._char_w = fm.horizontalAdvance("M")
        self._line_h = fm.height()
        # 以最大帧尺寸定窗口大小
        max_cols = max(
            max(len(line) for line in frame.split("\n"))
            for frames in ascii_pika.STATES.values() for frame in frames
        )
        max_rows = max(
            len(frame.split("\n"))
            for frames in ascii_pika.STATES.values() for frame in frames
        )
        self._content_w = self._char_w * max_cols
        self._content_h = self._line_h * max_rows

    # ---------- 窗口 ----------
    def _init_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self._win_w = self._content_w + self.PAD * 2
        self._win_h = self._content_h + self.PAD * 2 + 30  # 顶部给气泡
        self.resize(int(self._win_w), int(self._win_h))
        sg = QApplication.primaryScreen().availableGeometry()
        self._screen = sg
        self.move(sg.width() - self._win_w - 80, sg.height() - self._win_h - 80)

    def showEvent(self, event):
        super().showEvent(event)
        macos_window.join_all_spaces(self)

    # ---------- 绘制 ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # D特效①:放电边缘微光(画在角色下层,作为背景光晕)
        if config.FX_GLOW_ENABLED and self._state in ("happy", "cheer"):
            self._paint_glow(p)

        p.setFont(self.font)

        frames = ascii_pika.STATES[self._state]
        frame = frames[self._frame % len(frames)]
        lines = frame.split("\n")

        x0 = self.PAD
        y0 = self.PAD + 30 + self._line_h  # baseline of first line
        cw, lh = self._char_w, self._line_h

        YELLOW = QColor(255, 213, 30)
        BLACK = QColor(40, 30, 0)
        GLOW = QColor(40, 30, 0, 150)
        RED = QColor(232, 60, 60)

        # 逐字符绘制(发光描边 + 上色:电花偏蓝白,其余=雷电黄)
        for line_i, line in enumerate(lines):
            y = y0 + line_i * lh
            for col_i, ch in enumerate(line):
                if ch == " ":
                    continue
                x = x0 + col_i * cw
                # 颜色规则
                if False:
                    color = BLACK      # (此版不区分耳尖)
                elif ch in "⚡":
                    color = QColor(120, 200, 255)  # 电花偏蓝白
                else:
                    color = YELLOW
                # 描边
                p.setPen(GLOW)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    p.drawText(int(x + dx), int(y + dy), ch)
                # 主体
                p.setPen(color)
                p.drawText(int(x), int(y), ch)

        # D特效②:走路扬尘(脚下淡灰小点,跟随帧相位左右交替)
        if config.FX_DUST_ENABLED and self._state in ("walk_right", "walk_left"):
            self._paint_dust(p, x0, y0, len(lines))

        # D特效③:心情图标粒子(✨/⚡/💧 飘动,画在最上层)
        if config.FX_MOOD_ENABLED and self._particles:
            self._paint_particles(p)

        p.end()

    def _paint_glow(self, p):
        """放电时:窗口中心一圈淡黄径向光晕。"""
        from PyQt6.QtGui import QRadialGradient
        cx, cy = self._win_w / 2, self._win_h / 2 + 15
        radius = max(self._content_w, self._content_h) * 0.75
        g = QRadialGradient(cx, cy, radius)
        g.setColorAt(0.0, QColor(255, 230, 80, 70))
        g.setColorAt(0.6, QColor(255, 220, 60, 30))
        g.setColorAt(1.0, QColor(255, 220, 60, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(int(cx - radius), int(cy - radius),
                      int(radius * 2), int(radius * 2))

    def _paint_dust(self, p, x0, y0, n_lines):
        """走路扬尘:在脚下(最后一行下方)画几个淡灰小点,随帧相位偏移。"""
        foot_y = y0 + n_lines * self._line_h - self._line_h * 0.3
        phase = self._frame % 4
        p.setFont(self.font)
        p.setPen(QColor(180, 175, 150, 130))
        # 朝行进反方向扬尘(向右走 → 尘在左后)
        base_x = x0 + (self._content_w * (0.25 if self._walk_dir > 0 else 0.6))
        dots = ["·", "˙", "·"]
        for i, d in enumerate(dots):
            if (phase + i) % 2 == 0:
                continue   # 交替闪现,显得在扬
            dx = -self._walk_dir * (i * self._char_w * 0.8 + phase * 2)
            p.drawText(int(base_x + dx), int(foot_y - i * 3), d)

    def _paint_particles(self, p):
        """画心情粒子,按剩余寿命淡出。"""
        p.setFont(self.font)
        for pt in self._particles:
            alpha = int(255 * max(0.0, pt["life"] / pt["max"]))
            ch = pt["ch"]
            if ch == "✨":
                col = QColor(255, 240, 150, alpha)
            elif ch == "⚡":
                col = QColor(120, 200, 255, alpha)
            else:  # 💧
                col = QColor(120, 180, 255, alpha)
            p.setPen(col)
            p.drawText(int(pt["x"]), int(pt["y"]), ch)

    # ---------- 行为状态机 ----------
    def _pick_new_state(self, first=False):
        now = self._t.elapsed()
        idle_for = now - self._last_interact

        # 长时间没互动 → 犯困:先打哈欠过渡,再睡觉
        if idle_for > config.SLEEP_AFTER_MS and self._state not in ("sleep", "yawn"):
            self._set_state("yawn", 2400)        # 哈欠完 → 下次 tick 进 sleep
            return
        if self._state == "yawn" and idle_for > config.SLEEP_AFTER_MS:
            self._set_state("sleep", config.SLEEP_DURATION_MS)
            return

        if self._state == "sleep":
            # 睡醒后伸个懒腰(idle)
            self._set_state("idle", random.randint(2000, 4000))
            return

        # 普通随机玩耍:按 config.PLAY_WEIGHTS 加权抽一个动作
        choice = self._weighted_play()
        if choice == "walk":
            self._walk_dir = random.choice([-1, 1])
            self._set_state("walk_right" if self._walk_dir > 0 else "walk_left",
                            random.randint(2500, 5000))
        elif choice == "idle":
            self._set_state("idle", random.randint(2000, 4000))
        elif choice == "eat":
            self._set_state("eat", random.randint(2500, 4000))
        elif choice == "look":
            self._set_state("look", random.randint(2400, 4000))
        elif choice == "jump":
            self._start_jump()
        elif choice == "sing":
            self._set_state("sing", random.randint(3000, 5000))
        elif choice == "yawn":
            self._set_state("yawn", random.randint(2000, 2800))
        else:
            self._set_state("idle", random.randint(2000, 4000))

    def _weighted_play(self):
        """按 config.PLAY_WEIGHTS 加权随机选一个玩耍动作。"""
        weights = config.PLAY_WEIGHTS
        items = list(weights.items())
        total = sum(w for _, w in items)
        r = random.random() * total
        upto = 0.0
        for name, w in items:
            upto += w
            if r <= upto:
                return name
        return items[-1][0]

    def _start_jump(self):
        """开始一次跳跃:记录起跳基准 y,tick 里按抛物线上移再落回。"""
        self._jump_base_y = self.y()
        self._set_state("jump", 900)   # 一次跳跃约 0.9s

    def _set_state(self, state, duration_ms, then=None):
        """切到 state,持续 duration_ms。then 指定到期后强制接入的下一个状态
        (用于动作链,如 surprise→happy);为 None 则到期后走随机玩耍。"""
        self._state = state
        self._frame = 0
        self._state_until = self._t.elapsed() + duration_ms
        self._after_state = then   # (state, duration) 元组或 None

    def _tick_behavior(self):
        now = self._t.elapsed()
        # 走路时移动窗口
        if self._state in ("walk_right", "walk_left"):
            dx = config.WALK_SPEED * self._walk_dir
            nx = self.x() + dx
            # 撞到屏幕边缘就掉头
            if nx < self._screen.left():
                nx = self._screen.left(); self._flip_walk()
            elif nx > self._screen.right() - self._win_w:
                nx = self._screen.right() - self._win_w; self._flip_walk()
            self.move(int(nx), self.y())
        # 跳跃时按抛物线上移再落回(0→顶→0)
        elif self._state == "jump":
            # 用已过比例 p∈[0,1] 算抛物线高度:4p(1-p) 在 p=0.5 时最高
            total = 900.0
            elapsed = total - max(0, self._state_until - now)
            p = min(1.0, max(0.0, elapsed / total))
            lift = int(config.JUMP_HEIGHT_PX * 4 * p * (1 - p))
            self.move(self.x(), self._jump_base_y - lift)
        # 状态到期 → 换新状态
        if now >= self._state_until:
            if self._state == "jump":
                self.move(self.x(), self._jump_base_y)   # 确保落地归位
            # 有指定后续状态(动作链,如 surprise→happy)则优先接入
            if self._after_state is not None:
                nxt, dur = self._after_state
                self._set_state(nxt, dur)
            else:
                self._pick_new_state()

    def _flip_walk(self):
        self._walk_dir *= -1
        self._state = "walk_right" if self._walk_dir > 0 else "walk_left"

    # ---------- 气泡 ----------
    def _init_bubble(self):
        self.bubble = _ClickBubble(self)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.clicked.connect(self._on_bubble_clicked)
        self._style_bubble(sticky=False)
        self.bubble.hide()
        self._bubble_sticky = False    # 当前气泡是否常驻(提醒类任务)
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.bubble.hide)

    def _style_bubble(self, sticky):
        """sticky 提醒气泡用更醒目的样式(红边),普通气泡黄边。"""
        if sticky:
            self.bubble.setStyleSheet(
                "background: rgba(238,21,21,240); color:#FFFFFF;"
                "border:2px solid #FFE259; border-radius:12px;"
                f"padding:8px 12px; font-size:13px; font-weight:bold; font-family:{config.FONT_STACK};")
        else:
            self.bubble.setStyleSheet(
                "background: rgba(28,30,44,235); color:#FFE259;"
                "border:1.5px solid rgba(255,220,60,160); border-radius:12px;"
                f"padding:6px 10px; font-size:12px; font-weight:bold; font-family:{config.FONT_STACK};")

    def show_bubble(self, text, sticky=False):
        """sticky=True:常驻不自动消失,点击气泡才消失(用于定时提醒,点击=确认)。"""
        self._bubble_sticky = sticky
        self._style_bubble(sticky)
        display = (text + "  (点我确认 ✓)") if sticky else text
        self.bubble.setText(display)
        self.bubble.adjustSize()
        if self.bubble.width() > 220:
            self.bubble.setFixedWidth(220)
            self.bubble.adjustSize()
        else:
            self.bubble.setMaximumWidth(16777215)  # 解除上次可能设的定宽
        bx = (self.width() - self.bubble.width()) // 2
        self.bubble.move(max(2, bx), 2)
        self.bubble.show()
        self.bubble.raise_()
        self._bubble_timer.stop()
        if not sticky:
            self._bubble_timer.start(config.BUBBLE_DURATION_MS)

    def _on_bubble_clicked(self):
        # 点击气泡:常驻提醒被点 = 确认完成 → 消失
        if self._bubble_sticky:
            self.bubble.hide()
            self._bubble_sticky = False

    # ---------- 托盘 ----------
    def _init_tray(self):
        icon = QIcon(config.HD_PATH) if os.path.exists(config.HD_PATH) else QIcon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("皮卡丘桌宠 ⚡")
        menu = QMenu()
        a1 = QAction("打开对话", self); a1.triggered.connect(self.open_chat); menu.addAction(a1)
        a2 = QAction("陪它玩(逗一下)", self); a2.triggered.connect(self._poke); menu.addAction(a2)
        menu.addSeparator()
        a3 = QAction("退出", self); a3.triggered.connect(QApplication.quit); menu.addAction(a3)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.open_chat() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    # ---------- 定时器 ----------
    def _init_timers(self):
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._on_anim)
        self._anim.start(config.ASCII_FRAME_MS)

        # 定时任务调度:每 20 秒检查一次有没有到点的任务
        self._sched_last_fired = {}     # {task_id: 'YYYYmmddHHMM'} 分钟级去重
        self._sched_workers = []        # 保存运行中的 worker 防 GC
        self._sched_timer = QTimer(self)
        self._sched_timer.timeout.connect(self._check_scheduled)
        self._sched_timer.start(20_000)

        # 工具事件:claude 通过 MCP 工具建任务时会往 tool_events.jsonl 追加一行,
        # 桌宠轮询它 → 冒"✅ 已记下"确认气泡。只处理启动后新增的行。
        self._tool_evt_offset = os.path.getsize(config.TOOL_EVENTS_PATH) \
            if os.path.exists(config.TOOL_EVENTS_PATH) else 0
        self._tool_evt_timer = QTimer(self)
        self._tool_evt_timer.timeout.connect(self._check_tool_events)
        self._tool_evt_timer.start(1500)

    def _on_anim(self):
        self._frame += 1
        self._tick_behavior()
        self._tick_particles()
        self.update()

    # ---------- D特效:心情图标粒子 ----------
    def _tick_particles(self):
        """每帧更新粒子(上浮/下落 + 淡出),并在进入 happy/cheer/sad 时生成。"""
        if config.FX_MOOD_ENABLED:
            # 检测"刚进入"某情绪态(状态变化沿),生成一批粒子
            if self._state != self._mood_prev_state:
                if self._state in ("happy", "cheer"):
                    n = 6 if self._state == "cheer" else 4
                    self._spawn_mood("✨", n, rising=True)
                    if self._state == "cheer":
                        self._spawn_mood("⚡", 3, rising=True)
                elif self._state == "sad":
                    self._spawn_mood("💧", 4, rising=False)
        self._mood_prev_state = self._state

        # 推进现有粒子
        if self._particles:
            alive = []
            for pt in self._particles:
                pt["y"] += pt["vy"]
                pt["x"] += pt["vx"]
                pt["life"] -= 1
                if pt["life"] > 0:
                    alive.append(pt)
            self._particles = alive

    def _spawn_mood(self, ch, count, rising):
        """在皮卡丘头顶/周身生成 count 个 ch 粒子。rising=True 上浮,否则下落。"""
        if len(self._particles) >= config.FX_MOOD_MAX:
            return
        cx = self._win_w / 2
        top = self.PAD + 30
        for _ in range(count):
            self._particles.append({
                "x": cx + random.uniform(-self._content_w / 2, self._content_w / 2),
                "y": top + random.uniform(0, 20),
                "vx": random.uniform(-0.4, 0.4),
                "vy": random.uniform(-1.6, -0.8) if rising else random.uniform(0.8, 1.6),
                "ch": ch,
                "life": random.randint(14, 22),
                "max": 22,
            })

    # ---------- 定时任务调度 ----------
    def _check_scheduled(self):
        from datetime import datetime
        scheduler.purge_old_done()      # 清理触发已久的"已完成"一次性任务
        tasks = scheduler.load_tasks()
        if not tasks:
            return
        now = datetime.now()
        for task in tasks:
            if scheduler.is_due(task, now, self._sched_last_fired):
                self._sched_last_fired[task["id"]] = now.strftime("%Y%m%d%H%M")
                scheduler.after_fire(task, tasks)   # once标记done/interval顺延
                self._run_scheduled_task(task)

    def _check_tool_events(self):
        """读取 claude 通过 MCP 工具产生的新事件,冒确认气泡。"""
        path = config.TOOL_EVENTS_PATH
        try:
            if not os.path.exists(path):
                return
            size = os.path.getsize(path)
            if size < self._tool_evt_offset:
                self._tool_evt_offset = 0      # 文件被清空/重建,从头读
            if size == self._tool_evt_offset:
                return
            with open(path, encoding="utf-8") as f:
                f.seek(self._tool_evt_offset)
                new_lines = f.readlines()
                self._tool_evt_offset = f.tell()
        except Exception:
            return

        import json as _json
        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                evt = _json.loads(line)
            except Exception:
                continue
            if evt.get("event") == "schedule":
                desc = evt.get("desc", "提醒")
                self._set_state("happy", 1800)
                self.show_bubble(f"✅ 已记下「{desc[:14]}」", sticky=True)

    def _run_scheduled_task(self, task):
        """到点了:提醒类→常驻气泡提醒(点击确认);执行类→调 claude 干活。"""
        self._set_state("happy", 2200)
        desc = task.get("desc", "任务")
        mode = task.get("mode", "reminder")

        if mode == "reminder":
            # 纯提醒:冒一个常驻、醒目的气泡,点击才消失(=你确认了)
            self.show_bubble(f"⚡ 该「{desc[:16]}」啦!", sticky=True)
            return

        # 执行类:调 claude 真去干活
        self.show_bubble(f"⚡ 皮卡丘开工:{desc[:12]}")
        raw = task.get("prompt", "").strip()
        if not raw:
            return
        # 关键:到点 = 现在就执行,必须给 claude 明确的"立刻做"指令。
        # 否则原句里残留的时间词(如"两分钟之后")会让 claude 误以为还要等、
        # 或只是"记个定时任务",而不真去干活。
        prompt = (
            "【这是一个定时任务,现在已经到点,请立刻执行,不要再等待、"
            "不要把它当成新的定时任务来记录】\n"
            f"任务内容:{raw}\n"
            "请现在就用你的实际能力(读写文件、运行命令等)真正完成它,"
            "完成后用皮卡丘口吻简短汇报结果。"
        )
        worker = ClaudeWorker(prompt, history=None)
        worker.succeeded.connect(lambda r, t=task: self._on_sched_done(t, r))
        worker.failed.connect(lambda e, t=task: self._on_sched_fail(t, e))
        worker.finished.connect(lambda w=worker: self._sched_workers.remove(w)
                                if w in self._sched_workers else None)
        self._sched_workers.append(worker)
        worker.start()

    def _on_sched_done(self, task, reply):
        self._set_state("cheer", 2600)   # 任务成功:大放电庆祝
        # 完成也用常驻气泡,点击确认才消失(免得你没看到)
        self.show_bubble(f"✅ 完成「{task.get('desc','任务')[:14]}」", sticky=True)
        if self._chat is not None and self._chat.isVisible():
            self._chat._add("皮卡", f"*得意地翘尾巴* 定时任务「{task.get('desc','')}」搞定啦!⚡\n{reply}")

    def _on_sched_fail(self, task, err):
        self._set_state("sad", 2600)     # 任务失败:耷拉耳朵沮丧
        self.show_bubble(f"⚠️ 没做成「{task.get('desc','')[:10]}」", sticky=True)
        if self._chat is not None and self._chat.isVisible():
            self._chat._add("皮卡", f"*耷拉耳朵* 「{task.get('desc','')}」没做成…{err[:80]}")

    # ---------- 互动 ----------
    def _poke(self):
        self._last_interact = self._t.elapsed()
        self.show_bubble(random.choice(config.POKE_REACTIONS))
        # 先吓一跳缩一下(surprise),再开心放电(happy)
        self._set_state("surprise", 500, then=("happy", 1400))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._moved = False

    def mouseMoveEvent(self, event):
        if self._drag_offset is None:
            return
        pos = event.globalPosition().toPoint()
        if (pos - self._press_pos).manhattanLength() > config.CLICK_MOVE_THRESHOLD:
            self._moved = True
            # 真正开始拖动 → 手脚乱蹬挣扎(只切一次,持续到松手)
            if not self._drag_started:
                self._drag_started = True
                self._set_state("struggle", 600000)  # 长时长,松手时收回
        self.move(pos - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        was_click = not self._moved
        self._drag_offset = None
        # 松手:若刚才在挣扎,松开后喘口气(idle)再回随机玩耍
        if self._drag_started:
            self._drag_started = False
            self._last_interact = self._t.elapsed()
            self._set_state("idle", 1200)
        if was_click:
            # 先不立即动作:等系统双击间隔,看是否会有第二击
            interval = QApplication.doubleClickInterval()
            self._click_timer.start(interval + 20)

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # 双击:取消待执行的单击,开关对话窗
        self._click_timer.stop()
        self._last_interact = self._t.elapsed()
        self.toggle_chat()

    def _do_single_click(self):
        # 单击(确认不是双击后):只逗一下,不开对话窗
        self._poke()

    # ---------- 聊天窗 ----------
    def toggle_chat(self):
        """点击切换:开着就关,关着就开。"""
        self._last_interact = self._t.elapsed()
        if self._chat is not None and self._chat.isVisible():
            self._chat.hide()
        else:
            self.open_chat()

    def open_chat(self):
        self._last_interact = self._t.elapsed()
        if self._chat is None:
            self._chat = ChatWindow()
            # 聊天等 claude 回复时,桌宠本体也进/退思考态呼应
            self._chat.thinking_started.connect(self._enter_thinking)
            self._chat.thinking_ended.connect(self._exit_thinking)
        self._chat.show_near(self.frameGeometry())

    # ---------- 情境:思考态 ----------
    def _enter_thinking(self):
        """聊天等待 claude 时,本体持续挠头思考(给个很长的时长,靠 _exit 收回)。"""
        self._set_state("think", 600000)   # 足够长,实际由 _exit_thinking 结束
        self._thinking_active = True

    def _exit_thinking(self):
        """claude 回复完:退出思考态,回到自主玩耍。"""
        self._thinking_active = False
        if self._state == "think":
            self._set_state("idle", 1500)   # 短暂 idle 后自然进入随机玩耍


def _filter_macos_noise():
    """过滤 macOS 输入法框架打到 stderr 的无害噪音(TSM/IMK FAILED 等)。

    这些日志不影响功能,只是聊天窗聚焦时输入法系统的抱怨。
    """
    if sys.platform != "darwin":
        return
    import io
    real = sys.stderr
    noise = ("TSMSendMessageToUIServer", "IMKCFRunLoopWakeUpReliable",
             "CFMessagePortSendRequest", "com.apple.tsm")

    class _Filter(io.TextIOBase):
        def write(self, s):
            if any(n in s for n in noise):
                return len(s)
            return real.write(s)

        def flush(self):
            return real.flush()

    sys.stderr = _Filter()


def main():
    _filter_macos_noise()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if sys.platform == "darwin":
        macos_window.setup_app_policy()
    ensure_avatar()
    pet = PikachuPet()
    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
