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
import re
import ssl
import subprocess
import sys
import time
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
import claude_bridge
import config
import macos_window
import memory
import scheduler
from chat_window import ChatWindow, ClaudeWorker


# ════════════════════════  后台记忆整理 worker  ════════════════════════
class _DigestWorker(ClaudeWorker):
    """后台整理记忆 + 判断要不要主动搭话的 worker(独立 QThread,不阻塞 UI)。

    继承 ClaudeWorker 复用其线程/取消/保活范式,但 run() 改为调 claude_bridge.ask_raw
    做【纯文本推理】(整理记忆不需要 MCP 工具/文件权限),把 claude 返回的原始
    文本通过 succeeded 信号发回主线程,由主线程解析 JSON 并落盘(IO 留在主线程,
    避免在子线程里碰记忆文件与 UI)。new_cursor 随 worker 携带,完成时一并交回。
    """

    def __init__(self, prompt, new_cursor):
        super().__init__(prompt, history=None)
        self.new_cursor = new_cursor

    def run(self):
        try:
            reply = claude_bridge.ask_raw(
                self._prompt, timeout_sec=60, cancel_event=self._cancel)
            if not self._cancel.is_set():
                self.succeeded.emit(reply)
        except claude_bridge.ClaudeError as exc:
            if not self._cancel.is_set():
                self.failed.emit(str(exc))
        except Exception as exc:
            if not self._cancel.is_set():
                self.failed.emit(f"整理出错:{exc}")


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
    # 顶部预留给气泡的高度:多行气泡(首次引导那条 3~4 行)约需 100px。
    # 设为类属性,确保 paintEvent / _spawn_mood 任何时候取到的都一致。
    BUBBLE_TOP_RESERVE = 120

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
        # E2:定时 action 任务跑完时若聊天窗没开,claude 的实际执行结果先存这里,
        # 等用户打开聊天窗再补写进去——否则只冒"✅完成"气泡、结果丢失,
        # 用户永远不知道到底做了啥、做对没。[(desc, reply, ok)]
        self._pending_results = []
        # 记忆整理后台 worker(保活防 GC,类比 _sched_workers)。
        self._memory_workers = []
        # 主动搭话:记录所有【尚未被点开】的主动话题文本(可能多条同时排在 sticky
        # 队列里)。点击某条 sticky 气泡时,据此判断它是不是主动搭话——是则开聊天窗
        # 接话题,否则按普通提醒"确认"。用 set 而非单槽:否则第二条主动话题会覆盖
        # 第一条,导致还排在队首的第一条被点击时认不出、当成普通提醒静默关掉、不开窗。
        self._proactive_topics = set()
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
        # 窗口宽至少要放得下气泡(BUBBLE_MAX_W + 左右各 4px),否则气泡比窗口宽、
        # 右半被窗口边界裁掉。ASCII 画面本身较窄,这里按气泡需求取较大值。
        self._win_w = max(self._content_w + self.PAD * 2, self.BUBBLE_MAX_W + 8)
        # 顶部预留 BUBBLE_TOP_RESERVE 给气泡(原来只留 30px,长气泡上下被截断)
        self._win_h = self._content_h + self.PAD * 2 + self.BUBBLE_TOP_RESERVE
        self.resize(int(self._win_w), int(self._win_h))
        sg = QApplication.primaryScreen().availableGeometry()
        self._screen = sg
        # 用 right()/bottom()(屏幕绝对坐标)而非 width()/height()(尺寸):
        # availableGeometry 的原点可能非 (0,0)(顶部菜单栏让 y>0;多屏时主屏也可能
        # 不在原点)。用尺寸当坐标会把窗口定位偏移,极端情况落到屏幕外。
        self.move(int(sg.right() - self._win_w - 80),
                  int(sg.bottom() - self._win_h - 80))

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

        # 窗口可能因气泡需求被加宽,ASCII 内容在水平方向居中(否则偏左)
        x0 = (self.width() - self._content_w) / 2
        # 皮卡丘从顶部气泡预留区下方开始画,baseline 为首行底部
        y0 = self.PAD + self.BUBBLE_TOP_RESERVE + self._line_h
        cw, lh = self._char_w, self._line_h

        YELLOW = QColor(255, 213, 30)
        GLOW = QColor(40, 30, 0, 150)
        RED = QColor(232, 60, 60)

        # 逐字符绘制(发光描边 + 上色:电花偏蓝白,其余=雷电黄)
        for line_i, line in enumerate(lines):
            y = y0 + line_i * lh
            for col_i, ch in enumerate(line):
                if ch == " ":
                    continue
                x = x0 + col_i * cw
                # 颜色规则:电花偏蓝白,脸颊红点,其余雷电黄
                if ch in "⚡":
                    color = QColor(120, 200, 255)
                elif ch == "·":
                    color = RED
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
    def _chat_open(self):
        """聊天窗当前是否打开着(可见)。"""
        return self._chat is not None and self._chat.isVisible()

    def _pick_new_state(self, first=False):
        now = self._t.elapsed()
        idle_for = now - self._last_interact

        # E4:聊天窗开着时,皮卡丘安静陪在原地——不走路、不跳、不睡觉、不打哈欠,
        # 只在原地做小动作(眨眼/东张西望/吃东西/哼歌),免得你正打字它却走开、
        # 或睡着了,和聊天窗脱节。聊天关掉后自然恢复自主玩耍。
        if self._chat_open():
            self._set_state(random.choice(("idle", "look", "eat", "sing")),
                            random.randint(2200, 4200))
            return

        # 长时间没互动 → 犯困:先打哈欠过渡,再睡觉
        if idle_for > config.SLEEP_AFTER_MS and self._state not in ("sleep", "yawn"):
            self._set_state("yawn", 2400)        # 哈欠完 → 下次 tick 进 sleep
            return
        # 只有【困倦 yawn】(本函数顶部那次,无 after_state)结束才进睡眠;
        # 随机玩耍抽到的 yawn 设了 then=("idle",...),不该因恰好 idle 超时就睡。
        if (self._state == "yawn" and idle_for > config.SLEEP_AFTER_MS
                and self._after_state is None):
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
            # 随机玩耍的哈欠:打完接 idle(用 then 链),区别于困倦 yawn(无 then→进睡眠)。
            self._set_state("yawn", random.randint(2000, 2800), then=("idle", 1500))
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
            # 实时取当前屏幕几何:外接显示器拔插/分辨率变化后边界仍正确,
            # 避免皮卡丘走出屏幕或卡在旧边界。取所在屏幕,取不到则回退主屏。
            scr = self.screen() or QApplication.primaryScreen()
            geo = scr.availableGeometry() if scr else self._screen
            self._screen = geo
            dx = config.WALK_SPEED * self._walk_dir
            nx = self.x() + dx
            # 撞到屏幕边缘就掉头。用实时 self.width() 而非初始 self._win_w:
            # 多屏/外接显示器 DPI 不同会让 Qt 重缩放窗口,实际宽变了,用旧值会
            # 让皮卡丘走出屏幕或够不到最右端。
            win_w = self.width()
            if nx < geo.left():
                nx = geo.left(); self._flip_walk()
            elif nx > geo.right() - win_w:
                nx = geo.right() - win_w; self._flip_walk()
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
        # sticky 提醒队列:同分钟多个定时任务到点时,不能让后一个气泡覆盖前一个
        # (会丢失提醒)。改为排队:当前显示队首,点击确认弹出下一条,直到清空。
        self._sticky_queue = []
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
        """sticky=True:常驻不自动消失,点击气泡才消失(用于定时提醒,点击=确认)。

        sticky 气泡之间不互相覆盖:已有未确认的 sticky 时,新 sticky 入队,
        当前只显示队首并标注"还有 N 条"。非 sticky(走路逗趣气泡)也不会
        顶掉未确认的 sticky 提醒——定时提醒优先级更高。
        """
        if sticky:
            # W3 去重:同一条提醒(如每分钟的"该喝水啦")反复到点,不重复入队,
            # 否则挂机一小时队列里全是同一句、要点几十次才清空。
            # 正在显示的队首也算"已在队列",一并比对。
            if text in self._sticky_queue:
                self._refresh_sticky_text()
                return
            self._sticky_queue.append(text)
            # W3 上限:超过上限丢最旧的未确认提醒,避免无限堆积。保留队首
            # (用户正在看的那条)不被挤掉,从次旧的开始丢。
            if len(self._sticky_queue) > config.STICKY_QUEUE_MAX:
                # 丢掉索引 1(次旧),保住队首[0]
                del self._sticky_queue[1]
            # 当前没在显示 sticky → 立刻弹队首;否则只刷新角标,不覆盖正在看的那条
            if not self._bubble_sticky:
                self._show_next_sticky()
            else:
                self._refresh_sticky_text()
            return
        # 非 sticky:不打断未确认的 sticky 提醒(否则定时提醒会被走路气泡覆盖丢失)
        if self._bubble_sticky:
            return
        self._render_bubble(text, sticky=False)
        self._bubble_timer.start(config.BUBBLE_DURATION_MS)

    BUBBLE_MAX_W = 260   # 气泡最大宽度(超出则换行;放宽些让长引导文案行数更少)

    def _render_bubble(self, display, sticky):
        """实际把文字画到气泡上(尺寸/定位/样式)。

        关键:WordWrap 的 QLabel 在限宽后,adjustSize() 常按单行高算,导致多行
        文本被裁(上下截断)。必须用 heightForWidth 显式把高度撑到换行后的真实
        行数,长气泡(如首次引导那条)才不会被切掉头尾。
        """
        self._bubble_sticky = sticky
        self._style_bubble(sticky)
        self.bubble.setText(display)
        # 先解除上一条可能残留的定宽/定高,再按内容自适应一次拿到自然宽度
        self.bubble.setMinimumWidth(0)
        self.bubble.setMaximumWidth(16777215)
        self.bubble.setMinimumHeight(0)
        self.bubble.setMaximumHeight(16777215)
        self.bubble.adjustSize()
        # 气泡宽度上限取 min(BUBBLE_MAX_W, 窗口宽-8),保证不超出窗口被裁
        max_w = min(self.BUBBLE_MAX_W, self.width() - 8)
        if self.bubble.width() > max_w:
            # 超宽 → 限宽换行,并用 heightForWidth 算出换行后真正需要的高度
            w = max_w
            self.bubble.setFixedWidth(w)
            h = self.bubble.heightForWidth(w)
            if h > 0:
                self.bubble.setFixedHeight(h)
            else:
                self.bubble.adjustSize()
        bx = (self.width() - self.bubble.width()) // 2
        # 顶部对齐到 2px;高度由上面算准,_win_h 顶部预留已加大以容纳多行气泡
        self.bubble.move(max(2, bx), 2)
        self.bubble.show()
        self.bubble.raise_()
        self._bubble_timer.stop()

    def _show_next_sticky(self):
        """弹出 sticky 队列的队首;队列空则收起气泡。"""
        if not self._sticky_queue:
            self.bubble.hide()
            self._bubble_sticky = False
            return
        self._render_bubble(self._sticky_text(), sticky=True)

    def _refresh_sticky_text(self):
        """队列变化时,刷新当前 sticky 气泡的"还有 N 条"角标。"""
        if self._bubble_sticky:
            self._render_bubble(self._sticky_text(), sticky=True)

    def _sticky_text(self):
        """队首文案 + (剩余条数)角标 + 确认提示。"""
        text = self._sticky_queue[0]
        more = len(self._sticky_queue) - 1
        tail = f"(还有 {more} 条,点我看下一条 ✓)" if more > 0 else "(点我确认 ✓)"
        return f"{text}  {tail}"

    def _on_bubble_clicked(self):
        # 点击 sticky 气泡 = 确认当前这条 → 弹出队列里的下一条(没有则收起)
        if self._bubble_sticky:
            # 主动搭话气泡:当前队首正是主动话题 → 点击=展开聊天窗接着聊,
            # 而不是单纯"确认"。先把它出队/收起,再开窗注入开场白。
            head = self._sticky_queue[0] if self._sticky_queue else None
            is_proactive = head is not None and head in self._proactive_topics
            if self._sticky_queue:
                self._sticky_queue.pop(0)
            self._show_next_sticky()
            if is_proactive:
                self._proactive_topics.discard(head)
                self._last_interact = self._t.elapsed()
                self.open_chat()
                if self._chat is not None:
                    try:
                        self._chat.inject_pika_opening(head)
                    except Exception:
                        pass

    # ---------- 托盘 ----------
    def _build_menu(self):
        """构建操作菜单(托盘和本体右键共用,保证总有退出入口)。"""
        menu = QMenu(self)
        a1 = QAction("打开对话", self); a1.triggered.connect(self.open_chat); menu.addAction(a1)
        a2 = QAction("陪它玩(逗一下)", self); a2.triggered.connect(self._poke); menu.addAction(a2)
        menu.addSeparator()
        a3 = QAction("退出", self); a3.triggered.connect(QApplication.quit); menu.addAction(a3)
        return menu

    def _init_tray(self):
        # E 兜底:本体右键菜单【始终】可用,不依赖系统托盘是否显示。
        # 原因:setQuitOnLastWindowClosed(False) + Accessory 策略(无 Dock 图标),
        # 退出全靠托盘菜单。但 QSystemTrayIcon 在某些 macOS 配置下(菜单栏图标被
        # Bartender 等隐藏、隐私/权限限制)可能 show() 成功却看不见,用户就只能
        # kill 进程。给本体加右键菜单作为永不失效的退出入口。
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # 菜单只建【一次】并复用:每次右键都 _build_menu() 会新建 QMenu+3个 QAction,
        # 它们都 parent=self,exec 后不会立即销毁,会作为子对象无限累积(右键几百次
        # 后明显涨内存)。建一个常驻 _ctx_menu,每次 exec 它即可。
        self._ctx_menu = self._build_menu()
        self.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu.exec(self.mapToGlobal(pos)))

        if not QSystemTrayIcon.isSystemTrayAvailable():
            # 系统托盘不可用:不创建托盘,完全靠本体右键菜单退出。
            self.tray = None
            return
        icon = QIcon(config.HD_PATH) if os.path.exists(config.HD_PATH) else QIcon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("皮卡丘桌宠 ⚡(右键我也能退出)")
        self.tray.setContextMenu(self._build_menu())
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
        # 记 (offset, inode):靠 inode 判断文件是否被重建,避免被截断到中间
        # 状态时 seek(0) 把历史事件当新事件重读 → 重复冒气泡。
        self._tool_evt_offset, self._tool_evt_inode = self._tool_evt_stat()
        self._tool_evt_timer = QTimer(self)
        self._tool_evt_timer.timeout.connect(self._check_tool_events)
        self._tool_evt_timer.start(1500)

        # E1 首次引导:第一次运行时,延迟冒一个"双击我聊天"的常驻气泡,
        # 让新用户发现核心功能(单击只逗一下,不开聊天,容易以为没反应)。
        if not os.path.exists(config.FIRST_RUN_FLAG):
            QTimer.singleShot(config.ONBOARD_DELAY_MS, self._maybe_onboard)

        # 记忆整理 + 主动搭话:每 DIGEST_INTERVAL_MS 轮询一次。无新对话则跳过
        # (零 claude 调用)。整理在后台 QThread 跑,完成后回主线程落盘 + 可能搭话。
        if config.MEMORY_ENABLED:
            self._digest_timer = QTimer(self)
            self._digest_timer.timeout.connect(self._check_memory)
            self._digest_timer.start(config.DIGEST_INTERVAL_MS)

    def _maybe_onboard(self):
        """首次引导气泡(只弹一次,靠标记文件去重)。"""
        if os.path.exists(config.FIRST_RUN_FLAG):
            return
        # 写标记:即便这次没看到,也不再反复弹。写失败不致命(大不了下次再弹)。
        try:
            with open(config.FIRST_RUN_FLAG, "w", encoding="utf-8") as f:
                f.write("1")
        except OSError:
            pass
        # 引导时本体开心放电一下,更显眼;sticky 气泡点击才消失,确保用户看到。
        self._flash_state("happy", 2200)
        self.show_bubble(config.ONBOARD_HINT, sticky=True)

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
        # 裁剪到不超上限:旧版只在"已满"时整批跳过,但当前是 MAX-1、又要生成 6 个
        # 时会一次性 append 全部 6 个 → 实际数量冲到 MAX+5。改为只补到上限为止。
        room = config.FX_MOOD_MAX - len(self._particles)
        if room <= 0:
            return
        count = min(count, room)
        cx = self._win_w / 2
        # 角色身体的纵向范围:[body_top, body_top+content_h]。
        body_top = self.PAD + self.BUBBLE_TOP_RESERVE
        # 上浮粒子(✨/⚡)从角色【上半身】冒出:若像旧版从 body_top 起步,会立刻
        # 升进顶部气泡保留区、被气泡控件遮住看不见。从身体 1/4~1/2 处起步,
        # 让它们有一段在角色头顶上方的可见上升轨迹。下落粒子(💧)从身体上沿开始。
        if rising:
            y_lo = body_top + self._content_h * 0.25
            y_hi = body_top + self._content_h * 0.5
        else:
            y_lo = body_top
            y_hi = body_top + 20
        for _ in range(count):
            self._particles.append({
                "x": cx + random.uniform(-self._content_w / 2, self._content_w / 2),
                "y": random.uniform(y_lo, y_hi),
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
            # 单条任务的处理整体包 try/except:某条任务字段损坏(外部编辑/旧版本
            # 残留)导致 is_due/after_fire/dedup_key 抛异常时,只跳过这一条,绝不
            # 让异常冒泡中断整个 for 循环(否则它后面的正常任务全被漏掉,且因定时
            # 器每 20s 再跑又会再崩,永久卡住所有调度)。
            try:
                self._check_one_scheduled(task, now, tasks)
            except Exception as exc:
                print(f"[pet] 跳过一条出错的定时任务({task.get('id')}):{exc}")
        return

    def _check_one_scheduled(self, task, now, tasks):
        """处理单条到点判断与触发(被 _check_scheduled 逐条包 try/except 调用)。"""
        if not scheduler.is_due(task, now, self._sched_last_fired):
            return
        # W2 并发护栏:真正要起 claude 子进程的(执行类、且非降级的周期任务)
        # 才占名额;名额满时【不消耗本次触发】(不写 stamp、不 after_fire),
        # 让它保持 due,下一轮(20s 后)有空位再起 —— 避免任务被静默丢弃。
        if self._will_spawn_worker(task) and \
                self._alive_workers() >= config.MAX_CONCURRENT_SCHED_WORKERS:
            return
        # 去重键随 kind 变化:daily 按日期、weekly 按年+周、其余按分钟。
        # 必须与 scheduler.is_due 内部用的键一致,否则持久化去重失效。
        stamp = scheduler.dedup_key(task, now)
        self._sched_last_fired[task["id"]] = stamp
        # once标记done / interval顺延 / daily-weekly持久化stamp防重启重触发
        persisted = scheduler.after_fire(task, tasks, stamp)
        # H 加固:once + action(到点真执行危险操作)且 done 没落盘时,
        # 【不执行】——宁可这次漏做,也不冒"重启后重复执行"的险(重复 git push
        # /删文件代价高)。内存 _sched_last_fired 已记 stamp,本进程内不会重触发;
        # 真正危险的是重启后盘上 done 缺失。reminder / 其他 kind 不受此限:
        # 重复提醒无害,漏提醒反而更糟,照常触发。
        if (not persisted and task.get("kind") == "once"
                and task.get("mode") == "action"):
            # 撤回内存 stamp,让它下一轮仍 due:期望届时磁盘恢复正常能写成 done
            self._sched_last_fired.pop(task["id"], None)
            self.show_bubble(
                f"*挠头* 「{task.get('desc','任务')[:10]}」存档出错,"
                "皮卡先不动手,等会儿再试~", sticky=True)
            return
        self._run_scheduled_task(task)

    def _will_spawn_worker(self, task) -> bool:
        """这个任务到点是否会真起一个 claude 子进程(用于并发名额判断)。

        只有"执行类(action)"且有非空 prompt、且不是被降级的周期任务,才会起
        worker。纯提醒、空 prompt 兜底、降级的 interval+action 都只冒气泡,不占名额。
        """
        if task.get("mode") != "action":
            return False
        if not (task.get("prompt") or "").strip():
            return False
        if (task.get("kind") == "interval"
                and not config.ALLOW_INTERVAL_ACTION):
            return False
        return True

    def _alive_workers(self):
        """清理已结束的 worker,返回仍在跑的数量(用于并发上限判断)。"""
        self._sched_workers = [w for w in self._sched_workers if w.isRunning()]
        return len(self._sched_workers)

    @staticmethod
    def _tool_evt_stat():
        """返回 (size, inode);文件不存在返回 (0, None)。"""
        try:
            st = os.stat(config.TOOL_EVENTS_PATH)
            return st.st_size, st.st_ino
        except OSError:
            return 0, None

    def _check_tool_events(self):
        """读取 claude 通过 MCP 工具产生的新事件,冒确认气泡。"""
        path = config.TOOL_EVENTS_PATH
        try:
            size, inode = self._tool_evt_stat()
            if inode is None:
                return
            # 文件被重建(inode 变了)或被清空/截断(size 变小)→ 从头读。
            # 用 inode 而非仅靠 size,能可靠区分"截断重写"与"正常追加"。
            if inode != self._tool_evt_inode or size < self._tool_evt_offset:
                self._tool_evt_offset = 0
                self._tool_evt_inode = inode
            if size == self._tool_evt_offset:
                return
            # 用二进制读,offset/size 都是字节单位,避免 text 模式下字符数与字节数
            # 不一致(中文)造成 seek/offset 错位。
            with open(path, "rb") as f:
                f.seek(self._tool_evt_offset)
                chunk = f.read()
            # 只消费到最后一个换行符为止:MCP 写一行时若被轮询撞上写到一半(没有
            # 末尾 \n),旧版用 readlines+tell 会把这半行当完整行解析(失败丢弃),
            # 且 offset 已推过它 → 下次不再读 → 该事件永久丢失。改为只在确实读到
            # 完整行(有 \n)时推进 offset,半行留到下次它写完整了再读。
            nl = chunk.rfind(b"\n")
            if nl == -1:
                return  # 还没有任何完整行,等下一轮
            complete = chunk[:nl + 1]
            self._tool_evt_offset += len(complete)
            new_lines = complete.decode("utf-8", "replace").splitlines()
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

    def _flash_state(self, state, dur):
        """到点时短暂切个情绪态;但聊天正在等 claude(思考态)时不打断它。

        与 _poke 一致:思考中只冒气泡、不切动作态,否则本体跳去 happy 而聊天窗
        还在转圈,二者不同步(W4)。
        """
        if self._thinking_active:
            return
        self._set_state(state, dur)

    def _run_scheduled_task(self, task):
        """到点了:提醒类→常驻气泡提醒(点击确认);执行类→调 claude 干活。"""
        desc = task.get("desc", "任务")
        mode = task.get("mode", "reminder")
        kind = task.get("kind")

        # W1 安全护栏:周期(interval)的"执行类"任务最危险——无人值守下会在 auto
        # 权限里反复自动跑危险操作(git push、删文件…)。默认降级成"周期提醒",
        # 让用户每次手动确认要不要做,而不是放它自动连环执行。
        if (mode == "action" and kind == "interval"
                and not config.ALLOW_INTERVAL_ACTION):
            self._flash_state("happy", 2200)
            self.show_bubble(
                f"⏰ 又到「{desc[:14]}」时间啦~ 要做的话点我,在对话里说一声哦",
                sticky=True)
            return

        if mode == "reminder":
            # 纯提醒:冒一个常驻、醒目的气泡,点击才消失(=你确认了)
            self._flash_state("happy", 2200)
            self.show_bubble(f"⚡ 该「{desc[:16]}」啦!", sticky=True)
            return

        # 执行类:调 claude 真去干活
        raw = task.get("prompt", "").strip()
        # W6:任务没写要做什么(prompt 空),别冒"开工"后无下文,给一句兜底
        if not raw:
            self._flash_state("sad", 1800)
            self.show_bubble(f"*挠头* 「{desc[:12]}」要做啥呀?皮卡没记清…", sticky=True)
            return

        # W2 资源护栏:并发名额已在 _check_scheduled 把关(满额则不消耗触发、
        # 下一轮重试)。这里再做一次防御性兜底:万一被直接调用且已满,不超额起,
        # 冒提示而非硬起一个超限子进程。
        if self._alive_workers() >= config.MAX_CONCURRENT_SCHED_WORKERS:
            self.show_bubble(f"⚡ 皮卡丘忙不过来,稍等下再做「{desc[:10]}」", sticky=True)
            return

        self.show_bubble(f"⚡ 皮卡丘开工:{desc[:12]}")
        # W5:执行期间维持"think(挠头干活)"态,worker 完成才退出 ——
        # 让用户看出后台真的在忙,而不是 happy 2.2s 后就回去随机玩耍。
        self._flash_state("think", 600000)
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
        self._flash_state("cheer", 2600)   # 任务成功:大放电庆祝(思考中不打断)
        desc = task.get("desc", "任务")
        # 完成也用常驻气泡,点击确认才消失(免得你没看到)。提示可去聊天窗看详情。
        self.show_bubble(f"✅ 完成「{desc[:14]}」(双击我看皮卡丘做了啥)", sticky=True)
        full = f"*得意地翘尾巴* 定时任务「{desc}」搞定啦!⚡\n{reply}"
        # E2:聊天窗开着直接写入;没开则存起来,等用户打开聊天窗补看,不丢结果。
        if self._chat is not None and self._chat.isVisible():
            self._chat._add("皮卡", full)
        else:
            self._stash_result(full)

    def _on_sched_fail(self, task, err):
        self._flash_state("sad", 2600)     # 任务失败:耷拉耳朵沮丧(思考中不打断)
        desc = task.get("desc", "")
        self.show_bubble(f"⚠️ 没做成「{desc[:10]}」(双击我看详情)", sticky=True)
        full = f"*耷拉耳朵* 「{desc}」没做成…{err[:80]}"
        if self._chat is not None and self._chat.isVisible():
            self._chat._add("皮卡", full)
        else:
            self._stash_result(full)

    def _stash_result(self, text):
        """暂存一条定时任务结果,等聊天窗打开时补写。上限 10 条,超出丢最旧。"""
        self._pending_results.append(text)
        if len(self._pending_results) > 10:
            del self._pending_results[0]

    # ---------- 互动 ----------
    def _poke(self):
        self._last_interact = self._t.elapsed()
        self.show_bubble(random.choice(config.POKE_REACTIONS))
        # 思考中(等 claude 回复)时只冒气泡,不切动作态,
        # 否则会打断 think 动画,本体与聊天窗"正在想"不同步。
        if self._thinking_active:
            return
        # 先吓一跳缩一下(surprise),再开心放电(happy)
        self._set_state("surprise", 500, then=("happy", 1400))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 第二次 press 来了即停掉待执行的单击 timer:双击序列的第二击一按下
            # 就已知是双击意图,不必等 mouseDoubleClickEvent 才停。否则高负载下
            # 第一个 timer 可能在第二次 press 前就到期,单击气泡与双击开窗同触发。
            self._click_timer.stop()
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
        # E4:打开聊天前若本体正走路/跳跃,先立刻停下归位(跳跃落地),再切安静态。
        # 否则:① 走到一半的位置去定位聊天窗会偏;② 要等当前 walk 到期(最长5s)
        # 本体才停,这期间它还在移动、和刚弹出的聊天窗脱节。
        if self._state == "jump":
            self.move(self.x(), self._jump_base_y)
        if self._state in ("walk_right", "walk_left", "jump", "sleep", "yawn"):
            self._set_state("look", 2600)   # 抬头看向你,安静下来
        if self._chat is None:
            self._chat = ChatWindow()
            # 聊天等 claude 回复时,桌宠本体也进/退思考态呼应
            self._chat.thinking_started.connect(self._enter_thinking)
            self._chat.thinking_ended.connect(self._exit_thinking)
            # 快通道(本地直存)建任务时,本体也冒"已记下"气泡,
            # 和走 claude+MCP(tool_events.jsonl)的路径体验一致。
            self._chat.on_local_schedule = self._on_local_schedule
            # 收窗不中断 claude:后台跑完时若窗关着,本体冒气泡提醒回来看。
            self._chat.on_background_done = self._on_chat_background_done
        self._chat.show_near(self.frameGeometry())
        # E2:把聊天窗没开时积压的定时任务结果补写进去,让用户看到到底做了啥。
        if self._pending_results:
            pending, self._pending_results = self._pending_results, []
            for text in pending:
                self._chat._add("皮卡", text)

    def _on_local_schedule(self, desc):
        """聊天窗快通道本地建任务后回调:本体放电 + 冒确认气泡。"""
        self._set_state("happy", 1800)
        self.show_bubble(f"✅ 已记下「{str(desc)[:14]}」", sticky=True)

    def _on_chat_background_done(self, ok):
        """收起聊天窗后,后台 claude 跑完的回调:冒常驻气泡提醒回来看回复。

        收窗不再中断 claude(它后台继续干),所以干完得有个提示,否则用户
        收了窗就不知道活干完没。点击/双击本体即可重开窗看完整回复。
        """
        if ok:
            self._flash_state("cheer", 2400)
            self.show_bubble("💡 皮卡丘想好啦!双击我看回复~", sticky=True)
        else:
            self._flash_state("sad", 2000)
            self.show_bubble("⚠️ 皮卡丘卡住了…双击我看看", sticky=True)

    # ---------- 情境:思考态 ----------
    def _enter_thinking(self):
        """聊天等待 claude 时,本体持续挠头思考(给个很长的时长,靠 _exit 收回)。"""
        self._set_state("think", 600000)   # 足够长,实际由 _exit_thinking 结束
        self._thinking_active = True

    def _exit_thinking(self):
        """claude 回复完:退出思考态。

        但若此刻还有定时 action worker 在后台跑(聊天期间到点的任务),不要直接
        回玩耍——本体接续维持 think 态,让用户看出后台还在忙(D 修复:否则聊天
        一结束本体就切 idle,定时任务在跑却毫无视觉指示)。
        """
        self._thinking_active = False
        if self._alive_workers() > 0:
            # 后台定时任务仍在跑 → 接续思考态(它完成时 _on_sched_done 会收尾)
            self._set_state("think", 600000)
            return
        if self._state == "think":
            self._set_state("idle", 1500)   # 短暂 idle 后自然进入随机玩耍

    # ---------- 记忆整理 + 主动搭话 ----------
    def _alive_memory_workers(self):
        """清理已结束的整理 worker,返回仍在跑的数量(并发护栏用)。"""
        self._memory_workers = [w for w in self._memory_workers if w.isRunning()]
        return len(self._memory_workers)

    def _check_memory(self):
        """轮询入口:有新对话才整理(否则零开销);整理在后台线程跑。"""
        if not config.MEMORY_ENABLED:
            return
        # 并发护栏:同一时刻只允许 1 个整理 worker,避免轮询叠加起多个 claude。
        if self._alive_memory_workers() > 0:
            return
        # 注意:【不】在这里调 maybe_truncate_convo —— 它持 flock + fsync(还嵌套
        # 取 MEMORY 锁),在 UI 线程同步执行会卡顿。截断放到 worker 完成后(见
        # _on_digest_done),那时游标已推进,截断丢弃的都是整理过的旧对话,安全。
        try:
            data = memory.load_memory()
            cursor = int(data.get("convo_cursor", 0))
            # 限制每轮最多整理 N 行:read_new_convo 只返回最早的 N 行,且 new_cursor
            # 精确指向这 N 行的末尾——剩余行下一轮继续读,绝不被游标跳过而丢失。
            rows, new_cursor = memory.read_new_convo(
                cursor, max_lines=config.DIGEST_MAX_CONVO_LINES)
        except Exception as exc:
            print(f"[pet] 读取对话流水失败,跳过本轮整理:{exc}")
            return
        if not rows:
            return                                # 无新对话 → 跳过,不调 claude
        prompt = self._build_digest_prompt(rows, data.get("memories", []))
        worker = _DigestWorker(prompt, new_cursor)
        worker.succeeded.connect(lambda r, w=worker: self._on_digest_done(w, r))
        worker.failed.connect(lambda e, w=worker: self._on_digest_fail(w, e))
        worker.finished.connect(
            lambda w=worker: self._memory_workers.remove(w)
            if w in self._memory_workers else None)
        self._memory_workers.append(worker)
        worker.start()

    @staticmethod
    def _build_digest_prompt(rows, existing):
        """拼出"整理记忆 + 判断要不要主动搭话"的 prompt,要求 claude 只输出 JSON。

        每行对话前缀【发生时刻】(从流水的 ts 还原):没有时间锚点,claude 无法
        判断"凌晨还在聊→熬夜""几天前说要做的事→该催进度""刚说过的事→别重复关心"。
        时间对作息/未完成事项/主动搭话时机的判断至关重要,必须喂给它。
        """
        from datetime import datetime
        convo = "\n".join(
            f"[{PikachuPet._fmt_convo_ts(r.get('ts'))}] "
            f"{'主人' if r.get('role') == 'user' else '皮卡丘'}：{r.get('text', '')}"
            for r in rows)
        existing_txt = "\n".join(
            f"- [{m.get('type')}] {m.get('text')}"
            f"{'(未完成)' if m.get('type') == 'todo' and not m.get('done') else ''}"
            for m in existing) or "(还没有任何记忆)"
        now = datetime.now()
        wd = "一二三四五六日"[now.weekday()]
        return (
            "你在帮一只桌面宠物皮卡丘【整理它对主人的记忆】,并判断此刻要不要主动找主人搭话。\n"
            f"当前时间:{now.strftime('%Y-%m-%d %H:%M')} 星期{wd}。\n"
            "下面每行对话前的方括号是这句话【实际发生的时刻】,请据此理解时间。\n\n"
            "【已有的记忆】\n" + existing_txt + "\n\n"
            "【最近这段新对话】\n" + convo + "\n\n"
            "请从新对话里提炼出【值得长期记住】的信息,并和已有记忆对照。"
            "只输出一个 JSON 对象,不要任何解释、不要代码块标记。结构:\n"
            "{\n"
            '  "add": [ {"type":"fact|preference|todo|routine|topic", "text":"一句话记忆"} ],\n'
            '  "done": ["已经完成的未完成事项的关键词"],\n'
            '  "proactive": {"should": true/false, "topic":"皮卡丘主动找主人说的一句话(口语、简短、像宠物撒娇/关心,可带⚡)"}\n'
            "}\n\n"
            "规则:\n"
            "- type 含义:fact=客观事实(身份/背景);preference=喜好;todo=主人提过要做但还没做完的事;"
            "routine=作息/习惯;topic=聊过、可延续的兴趣话题。\n"
            "- 善用每句话的时刻:涉及时间/作息/进度的记忆,请把时间写进 text"
            "(如「6-19 凌晨4点还在聊天,似乎熬夜」「6-19 说要写量化脚本,当时还没写」),"
            "这样以后能判断过了多久、该不该关心进度。routine 类尤其要带时间规律。\n"
            "- 只记真正有长期价值的,别把寒暄/一次性闲聊也记下。没有就给空数组。\n"
            "- 重复或已存在的别重复 add(系统会自动去重,但你也别刻意重复)。\n"
            "- proactive.should:仅当确实有【值得主动说的事】才 true,依据这四类——"
            "①主人没做完的事(关心进度,结合它是多久前说的)②到了作息该关心的点"
            "(久坐/休息/吃饭/睡觉,结合当前时刻)③之前的兴趣话题有延续点 ④单纯想主人了想陪他。"
            "拿不准/没什么可说就 false。topic 要短、要像一只活的皮卡丘说的话。\n"
        )

    @staticmethod
    def _fmt_convo_ts(ts):
        """把流水里的 epoch 秒还原成 'MM-DD HH:MM'(给整理 prompt 用)。"""
        from datetime import datetime
        try:
            return datetime.fromtimestamp(float(ts)).strftime("%m-%d %H:%M")
        except Exception:
            return "时间未知"

    def _on_digest_done(self, worker, reply):
        """整理 worker 完成:解析 JSON → 落盘记忆 → 视情况触发主动搭话。"""
        import json as _json
        updates = {}
        proactive = None
        try:
            m = re.search(r"\{.*\}", reply, re.DOTALL)
            if m:
                data = _json.loads(m.group(0))
                updates = {
                    "add": data.get("add") or [],
                    "done": data.get("done") or [],
                }
                proactive = data.get("proactive") or None
        except Exception as exc:
            print(f"[pet] 整理结果解析失败(本轮不更新):{exc}")
            updates = {}
        # 落盘:即使 updates 为空也要推进游标(这批对话已"看过",无价值也别重看)。
        try:
            memory.apply_digest(updates, worker.new_cursor)
        except Exception as exc:
            print(f"[pet] 写入记忆失败:{exc}")
            return
        # 整理完顺手截断流水(超限才动)。放在游标已推进之后做:被截断丢弃的都是
        # 已整理过的旧对话,安全。注意这里仍在 UI 线程,但只有【超过上限】才会真正
        # 持锁+fsync——常态零开销(只数行数);真要截断时一次性代价可接受(罕见)。
        try:
            memory.maybe_truncate_convo()
        except Exception:
            pass
        # 主动搭话:claude 提议 + 本地频率门双重把关
        if config.PROACTIVE_ENABLED and isinstance(proactive, dict) \
                and proactive.get("should"):
            topic = (proactive.get("topic") or "").strip()
            if topic:
                self._maybe_proactive_chat(topic)

    def _on_digest_fail(self, worker, err):
        """整理失败:推进游标(避免下轮拿同一批失败对话反复重试),不打扰用户。"""
        try:
            memory.apply_digest({}, worker.new_cursor)
        except Exception:
            pass
        print(f"[pet] 后台整理失败(已跳过本批对话):{err[:120]}")

    def _maybe_proactive_chat(self, topic):
        """主动搭话频率门:全部条件满足才真的冒气泡,任一不满足就静默跳过。

        门(本地把关,防 claude 活泼过头变骚扰):
          ① 聊天窗没开、本体不在 thinking 态(别和正进行的事抢)
          ② 用户已空闲 ≥ PROACTIVE_IDLE_MIN_MS(不打断正在操作的人)
          ③ 距上次主动搭话 ≥ PROACTIVE_MIN_GAP_MS
          ④ 当天次数 < PROACTIVE_MAX_PER_DAY
          ⑤ 当前不在 PROACTIVE_QUIET_HOURS 静默时段(夜里不打扰)
        """
        if self._chat_open() or self._thinking_active:
            return
        # ② 空闲门
        idle_for = self._t.elapsed() - self._last_interact
        if idle_for < config.PROACTIVE_IDLE_MIN_MS:
            return
        # ⑤ 静默时段
        if self._in_quiet_hours():
            return
        try:
            data = memory.load_memory()
            last = float(data.get("last_proactive_at", 0.0))
            count = memory.proactive_count_today(data)
        except Exception:
            return
        # ③ 间隔门(用 wall-clock:last_proactive_at 是 epoch 秒)
        if (time.time() - last) * 1000 < config.PROACTIVE_MIN_GAP_MS:
            return
        # ④ 每日上限
        if count >= config.PROACTIVE_MAX_PER_DAY:
            return
        # 通过 → 冒主动搭话气泡(sticky,点击展开聊天窗)。记进 set,点击时认得出它。
        self._proactive_topics.add(topic)
        self._flash_state("happy", 2200)
        self.show_bubble(topic, sticky=True)
        try:
            memory.record_proactive()
        except Exception:
            pass

    @staticmethod
    def _in_quiet_hours():
        """当前是否在静默时段 [start, end)(支持跨零点,如 (23, 8))。"""
        from datetime import datetime
        start, end = config.PROACTIVE_QUIET_HOURS
        h = datetime.now().hour
        if start <= end:
            return start <= h < end
        return h >= start or h < end      # 跨零点

    # ---------- 退出清理 ----------
    def shutdown(self):
        """退出前 cancel + join 所有在跑的 ClaudeWorker(QThread)。

        否则进程退出时 QThread 仍在运行,Qt 会报
        「QThread: Destroyed while thread is still running」甚至 abort,
        且底层 claude 子进程会变成孤儿。cancel 会 kill 子进程,wait 等线程收尾。
        """
        workers = list(self._sched_workers)
        # 后台记忆整理 worker 也要一并 cancel + join:否则退出时它仍在跑 →
        # 「QThread: Destroyed while thread is still running」+ claude 子进程变孤儿。
        workers += list(self._memory_workers)
        if self._chat is not None:
            if self._chat._worker is not None:
                workers.append(self._chat._worker)
            # 取消后被孤儿化、仍在跑的 chat worker 也要 join,否则退出时它仍运行 →
            # 「QThread: Destroyed while thread is still running」+ claude 子进程变孤儿。
            workers += list(getattr(self._chat, "_orphans", []))
        # 去重(同一 worker 可能既是 _worker 又在某个表里),保持顺序
        seen = set()
        workers = [w for w in workers if not (id(w) in seen or seen.add(id(w)))]
        for w in workers:
            try:
                # I 加固:先断开所有信号再 wait。QThread.wait 会 pump 事件循环,
                # 期间 worker 残留的 succeeded/failed/finished 回调可能被派发到
                # 正在析构的窗口(_reply 访问已销毁的 _thinking、_on_sched_done
                # 写已关闭的聊天窗)→ use-after-free / 崩溃。退出阶段这些回调毫无
                # 意义,统一断开。disconnect 无连接时会抛 TypeError,逐个 try 吞掉。
                # finished 也要断:它连了 _sched_workers.remove,wait() 返回后
                # 线程收尾阶段若仍发 finished,会访问可能正在析构的 self,
                # 造成 use-after-free。退出阶段这些回调都没意义,一并断开。
                for sig in (w.succeeded, w.failed, w.tick, w.finished):
                    try:
                        sig.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                if w.isRunning():
                    w.cancel()
            except Exception:
                pass
        for w in workers:
            try:
                # cancel 已置位 → ask_pikachu 很快 kill 子进程返回;给 5s 上限兜底
                w.wait(5000)
            except Exception:
                pass
        # 状态重置:杀残留 claude/MCP 进程组 + 删运行时垃圾(锁/tmp/mcp_config/
        # 事件流水/pid登记)。保留用户数据(定时任务、引导标记)。与看门狗共用
        # 同一幂等清理,双方各跑一次也无害。
        try:
            import cleanup
            cleanup.reset_system_state()
        except Exception:
            pass


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

    # 启动看门狗(最先做,趁还没起任何子进程/没建任何状态)。它通过管道 EOF
    # 感知主进程死亡——包括被 kill -9 这种 shutdown 跑不到的情况——然后兜底
    # 清理 claude/MCP 残留进程与垃圾文件。_wd_fd 必须【全程持有不 close】,
    # 否则看门狗会误判主进程已死而提前清理。绑到 app 上防止被 GC。
    import watchdog
    _wd_fd = watchdog.spawn_watchdog()
    # 把裸写端 fd 包成文件对象:① 防 fd 号被后续 open 意外复用(裸 int 无保护,
    # 若别处 close 了同号 fd 再 open,会悄无声息触发看门狗);② 由对象生命周期
    # 统一管理。closefd=True 让对象销毁时关闭底层 fd。绑到 app 上保活(见下)。
    _wd_keepalive = None
    if _wd_fd is not None:
        try:
            _wd_keepalive = os.fdopen(_wd_fd, "wb", buffering=0)
        except OSError:
            _wd_keepalive = None

    # 启动即自愈:清掉上次会话(尤其上次被 kill -9、看门狗也异常没跑成)残留的
    # 锁/tmp/旧 pid 登记,避免脏锁让本次任务读写卡住。只删垃圾,不杀进程
    # (上次的 pid 登记此刻已无意义,且可能 PID 复用,不能照杀)。
    try:
        import cleanup
        cleanup.remove_garbage_files()
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    # 持有写端文件对象,生命周期 = app。绝不在主进程存活期间 close 它,
    # 否则看门狗会立刻误判主进程已死而提前清理。
    app._wd_keepalive = _wd_keepalive
    if sys.platform == "darwin":
        macos_window.setup_app_policy()
    # 头像下载放后台线程:网络差时 curl(60s)+urllib(60s)串行最长阻塞 120s,
    # 同步调用会让启动白屏。异步下载,皮卡丘本体立刻显示;头像只用于聊天窗标题/
    # 托盘图标,_init_tray 已做 os.path.exists 判断,下载未完成也不影响功能。
    import threading
    threading.Thread(target=ensure_avatar, daemon=True).start()
    pet = PikachuPet()
    # 退出前清理在跑的 claude 线程/子进程,避免 QThread 崩溃与孤儿进程
    app.aboutToQuit.connect(pet.shutdown)

    # 捕获 kill(SIGTERM)/ Ctrl-C(SIGINT):转成 Qt 的优雅退出(→aboutToQuit
    # →shutdown→清理)。SIGKILL(kill -9)无法捕获,由看门狗兜底。
    import signal as _signal

    def _graceful(signum, frame):
        app.quit()

    _signal.signal(_signal.SIGTERM, _graceful)
    _signal.signal(_signal.SIGINT, _graceful)
    # Qt 阻塞在 C++ 事件循环时,Python 信号处理器不会被及时调用。用一个空转的
    # QTimer 定期把控制权交回解释器,让上面的信号处理函数有机会执行。
    _sig_timer = QTimer()
    _sig_timer.timeout.connect(lambda: None)
    _sig_timer.start(300)

    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
