"""聊天窗(宝可梦球 红白卡通主题)。

致敬精灵球:上半红色标题栏 + 黑色腰带 + 中央白色"按钮"头像 + 下半白色主体。
卡通粗黑描边、实色填充,不用模糊玻璃。
"""

import os
import random
import threading
import time

from PyQt6.QtCore import (
    Qt, QThread, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QRectF,
)
from PyQt6.QtGui import (
    QBrush, QColor, QPainter, QPainterPath, QPixmap, QPen,
)
from PyQt6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import claude_bridge
import config
import macos_window
import scheduler

FONT = config.FONT_STACK


class ClaudeWorker(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)
    tick = pyqtSignal(int)

    def __init__(self, prompt, history=None):
        super().__init__()
        self._prompt = prompt
        self._history = history or []
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        start = time.monotonic()
        stop = threading.Event()

        def _ticker():
            while not stop.wait(1.0):
                self.tick.emit(int(time.monotonic() - start))

        threading.Thread(target=_ticker, daemon=True).start()
        try:
            reply = claude_bridge.ask_pikachu(
                self._prompt, history=self._history, cancel_event=self._cancel)
            if not self._cancel.is_set():
                self.succeeded.emit(reply)
        except claude_bridge.ClaudeError as exc:
            if not self._cancel.is_set():
                self.failed.emit(str(exc))
        except Exception as exc:
            if not self._cancel.is_set():
                self.failed.emit(f"皮卡丘短路了:{exc}")
        finally:
            stop.set()


def _pokeball_avatar(size=46):
    """画一个精灵球图标作头像(红白黑)。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = size - 4
    cx = cy = size / 2
    # 外圈黑
    p.setPen(QPen(QColor(config.COL_BELT_BLACK), 2))
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(QRectF(2, 2, r, r))
    # 上半红
    path = QPainterPath()
    path.addEllipse(QRectF(2, 2, r, r))
    p.setClipPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(config.COL_TITLE_RED))
    p.drawRect(QRectF(0, 0, size, size / 2))
    p.setClipping(False)
    # 中间黑带
    p.setPen(QPen(QColor(config.COL_BELT_BLACK), 3))
    p.drawLine(int(2), int(cy), int(2 + r), int(cy))
    # 中央按钮
    br = size * 0.26
    p.setBrush(QColor("#FFFFFF"))
    p.setPen(QPen(QColor(config.COL_BELT_BLACK), 2))
    p.drawEllipse(QRectF(cx - br / 2, cy - br / 2, br, br))
    p.end()
    return pm


class _TitleBar(QWidget):
    """精灵球红标题栏:精灵球头像 + 名字 + 关闭;可拖动整窗。"""

    def __init__(self, parent):
        super().__init__(parent)
        self._win = parent
        self._drag = None
        self.setFixedHeight(60)
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 12, 10)
        lay.setSpacing(11)

        self.avatar = QLabel()
        self.avatar.setFixedSize(46, 46)
        self.avatar.setPixmap(_pokeball_avatar(46))
        lay.addWidget(self.avatar)

        box = QVBoxLayout(); box.setSpacing(0)
        title = QLabel("皮卡丘")
        title.setStyleSheet(
            f"font-size:17px; font-weight:900; color:#FFFFFF; background:transparent; font-family:{FONT};")
        sub = QLabel("电气鼠宝可梦")
        sub.setStyleSheet(
            f"font-size:11px; color:rgba(255,255,255,210); background:transparent; font-family:{FONT};")
        box.addWidget(title); box.addWidget(sub)
        lay.addLayout(box, 1)

        close = QPushButton("✕")
        close.setFixedSize(28, 28)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(
            "QPushButton{background:#FFFFFF; border:2px solid #2B2B2B; border-radius:14px;"
            "font-size:13px; color:#2B2B2B; font-weight:900;}"
            "QPushButton:hover{background:#FFE0E0;}")
        close.clicked.connect(self._win.hide)
        lay.addWidget(close)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = 20.0
        # 红色圆角顶(上半精灵球)
        path = QPainterPath()
        path.moveTo(0, h); path.lineTo(0, r)
        path.arcTo(0, 0, 2 * r, 2 * r, 180, -90)
        path.lineTo(w - r, 0)
        path.arcTo(w - 2 * r, 0, 2 * r, 2 * r, 90, -90)
        path.lineTo(w, h); path.closeSubpath()
        p.fillPath(path, QBrush(QColor(config.COL_TITLE_RED)))
        # 底部黑色腰带
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(config.COL_BELT_BLACK))
        p.drawRect(QRectF(0, h - 5, w, 5))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self._win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None


class ChatWindow(QWidget):
    # 桌宠本体据此呼应:开始等 claude → 进思考态;结束 → 退出
    thinking_started = pyqtSignal()
    thinking_ended = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.resize(440, 580)
        self._worker = None
        self._thinking = None
        self._history = []
        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        macos_window.join_all_spaces(self)

    # ---------- UI ----------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setObjectName("card")
        # 卡通:白底 + 粗黑描边
        card.setStyleSheet(
            f"QFrame#card{{background:{config.COL_CARD_BG};"
            f"border:3px solid {config.COL_CARD_BORDER}; border-radius:22px;}}")
        sh = QGraphicsDropShadowEffect(card)
        sh.setBlurRadius(24); sh.setOffset(0, 6); sh.setColor(QColor(0, 0, 0, 100))
        card.setGraphicsEffect(sh)
        outer.addWidget(card)

        col = QVBoxLayout(card)
        col.setContentsMargins(0, 0, 0, 0); col.setSpacing(0)
        col.addWidget(_TitleBar(self))

        # 消息滚动区(浅灰白底)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            f"QScrollArea{{border:none; background:{config.COL_MSG_AREA};}}"
            "QScrollBar:vertical{width:8px; background:transparent; margin:4px 2px;}"
            "QScrollBar::handle:vertical{background:#E03131; border-radius:4px; min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}")
        self.box = QWidget()
        self.box.setStyleSheet(f"background:{config.COL_MSG_AREA};")
        self.msgs = QVBoxLayout(self.box)
        self.msgs.setContentsMargins(14, 14, 14, 14); self.msgs.setSpacing(12)
        self.msgs.addStretch()
        self.scroll.setWidget(self.box)
        col.addWidget(self.scroll, 1)

        # 输入栏(白底 + 黑描边圆角输入框 + 红色发送圆钮)
        bar = QWidget(); bar.setStyleSheet(f"background:{config.COL_CARD_BG};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 10, 12, 14); row.setSpacing(8)

        self.input = QLineEdit()
        self.input.setPlaceholderText("和皮卡丘说点什么…")
        self.input.returnPressed.connect(self._send)
        self.input.setStyleSheet(
            "QLineEdit{background:#F4F4F4; border:2px solid #2B2B2B; border-radius:20px;"
            f"padding:9px 16px; font-size:14px; color:#2B2B2B; font-family:{FONT};}}"
            "QLineEdit:focus{border-color:#EE1515; background:#FFFFFF;}")
        row.addWidget(self.input, 1)

        self.send = QPushButton("➤")
        self.send.setFixedSize(42, 42)
        self.send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send.clicked.connect(self._send)
        self.send.setStyleSheet(
            "QPushButton{background:#EE1515; border:2px solid #2B2B2B; border-radius:21px;"
            "font-size:16px; color:#FFFFFF; font-weight:900;}"
            "QPushButton:hover{background:#FF3333;}")
        row.addWidget(self.send)

        self.cancel = QPushButton("✕")
        self.cancel.setFixedSize(42, 42)
        self.cancel.setVisible(False)
        self.cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel.clicked.connect(self._on_cancel)
        self.cancel.setStyleSheet(
            "QPushButton{background:#888; border:2px solid #2B2B2B; border-radius:21px;"
            "font-size:14px; color:#FFFFFF; font-weight:900;}"
            "QPushButton:hover{background:#666;}")
        row.addWidget(self.cancel)
        col.addWidget(bar)

        # 随机宠物开场白
        self._add("皮卡", random.choice(config.CHAT_GREETINGS))

    # ---------- 气泡 ----------
    def _bubble(self, who, text):
        b = QLabel()
        b.setWordWrap(True)
        b.setTextFormat(Qt.TextFormat.RichText)
        self._set_html(b, text)
        b.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        b.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        b.setMaximumWidth(360)
        if who == "你":
            b.setStyleSheet(
                f"QLabel{{background:{config.COL_USER_BUBBLE}; color:{config.COL_USER_TEXT};"
                "border:2px solid #2B2B2B; border-radius:16px; border-top-right-radius:5px;"
                f"padding:11px 15px; font-size:14px; font-family:{FONT};}}")
        else:
            b.setStyleSheet(
                f"QLabel{{background:{config.COL_PIKA_BUBBLE}; color:{config.COL_PIKA_TEXT};"
                f"border:2px solid {config.COL_PIKA_BUBBLE_BORDER}; border-radius:16px; border-top-left-radius:5px;"
                f"padding:11px 15px; font-size:14px; font-family:{FONT};}}")
        return b

    @staticmethod
    def _set_html(label, text):
        import html as _h
        safe = _h.escape(text).replace("\n", "<br>")
        label.setText(f"<div style='line-height:150%;'>{safe}</div>")

    def _time_label(self, who):
        """气泡下方的发送时间小字。"""
        from datetime import datetime
        t = QLabel(datetime.now().strftime("%H:%M"))
        align = "right" if who == "你" else "left"
        t.setStyleSheet(
            f"color:#9AA0A6; font-size:10px; background:transparent;"
            f"font-family:{FONT}; padding:2px 4px 0 4px;")
        t.setAlignment(Qt.AlignmentFlag.AlignRight if who == "你"
                       else Qt.AlignmentFlag.AlignLeft)
        return t

    def _add(self, who, text):
        b = self._bubble(who, text)
        ts = self._time_label(who)
        # 气泡 + 时间戳竖直叠放,再整体左/右对齐
        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(1)
        col.addWidget(b)
        col.addWidget(ts)
        col.setAlignment(b, Qt.AlignmentFlag.AlignRight if who == "你"
                         else Qt.AlignmentFlag.AlignLeft)
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0)
        if who == "你":
            row.addStretch(); row.addLayout(col)
        else:
            row.addLayout(col); row.addStretch()
        self.msgs.insertLayout(self.msgs.count() - 1, row)
        QTimer.singleShot(30, self._scroll_bottom)
        return b

    def _add_thinking(self):
        """加一个【固定尺寸】的"正在想"气泡:转圈动画/读秒都不改变它的尺寸,

        所以不会触发布局重排 → 不会闪。普通回复来了会替换掉它的内容
        (替换时由 _reply 解除定宽,恢复成自适应气泡)。
        转圈用独立的快速定时器驱动(每帧 120ms,流畅);读秒走每秒的 tick 信号。
        """
        b = self._bubble("皮卡", "皮卡丘正在想… ⚡")
        # 关键:定死宽,内容怎么变都不重排。宽度取够放最长文案("⠋ 皮卡丘正在想… 120 秒 ⚡"),
        # 否则 WordWrap=False 会把右边的"秒 ⚡"截掉。
        b.setWordWrap(False)
        b.setFixedWidth(235)
        self._thinking_fixed = b      # 记一下,_reply 时解除定宽
        self._spin_idx = 0
        self._spin_sec = 0
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0)
        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(1)
        col.addWidget(b)
        col.addWidget(self._time_label("皮卡"))
        col.setAlignment(b, Qt.AlignmentFlag.AlignLeft)
        row.addLayout(col); row.addStretch()
        self.msgs.insertLayout(self.msgs.count() - 1, row)
        QTimer.singleShot(30, self._scroll_bottom)
        # 快速转圈定时器(120ms/帧)
        if not hasattr(self, "_spin_timer"):
            self._spin_timer = QTimer(self)
            self._spin_timer.timeout.connect(self._spin_step)
        self._spin_timer.start(120)
        self._render_thinking()
        return b

    def _spin_step(self):
        self._spin_idx = (self._spin_idx + 1) % len(self._SPINNER)
        self._render_thinking()

    def _render_thinking(self):
        if self._thinking is None and self._thinking_fixed is None:
            return
        label = self._thinking if self._thinking is not None else self._thinking_fixed
        spin = self._SPINNER[self._spin_idx]
        sec_str = str(self._spin_sec).rjust(3).replace(" ", "&nbsp;")
        label.setText(
            f"<div style='line-height:150%;'>{spin} 皮卡丘正在想… {sec_str} 秒 ⚡</div>")

    def _scroll_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _busy(self, on):
        self.input.setEnabled(not on)
        self.send.setVisible(not on)
        self.cancel.setVisible(on)
        if not on:
            self._thinking = None
            self.input.setFocus()

    # ---------- 发送 ----------
    def _send(self):
        text = self.input.text().strip()
        if not text or (self._worker and self._worker.isRunning()):
            return
        self.input.clear()
        self._add("你", text)
        # 先看是不是在管理定时任务(列出/删除/新建),命中就本地处理,不发 claude
        if self._handle_schedule_command(text):
            return
        self._thinking = self._add_thinking()
        self._busy(True)
        self._pending_user = text
        self.thinking_started.emit()        # 让桌宠本体进思考态
        recent = self._history[-12:]
        self._worker = ClaudeWorker(text, history=recent)
        self._worker.succeeded.connect(self._reply)
        self._worker.failed.connect(self._error)
        self._worker.tick.connect(self._tick)
        self._worker.start()

    # ---------- 定时任务命令 ----------
    def _handle_schedule_command(self, text):
        """识别并处理定时任务相关命令。处理了返回 True,否则 False。"""
        # 列出任务
        if any(k in text for k in ("我的任务", "有哪些任务", "列出任务", "看看任务", "查看任务", "定时任务有")):
            tasks = scheduler.load_tasks()
            if not tasks:
                self._say_local(text, "*翻翻小本本* 现在还没有定时任务哦~ 你可以说「每天9点提醒我喝水」⚡")
            else:
                lines = "\n".join(f"· {scheduler.describe(t)}（id:{t['id'][-4:]}）" for t in tasks)
                self._say_local(text, f"*掏出小本本* 皮卡丘帮你记着这些啦:\n{lines}\n\n（想删的话说「删除任务 xxxx」)")
            return True

        # 删除任务
        import re
        m = re.search(r"删除任务\s*(\w+)", text) or re.search(r"删掉\s*(\w+)\s*任务", text)
        if m or "删除所有任务" in text or "清空任务" in text:
            if "所有" in text or "清空" in text:
                for t in scheduler.load_tasks():
                    scheduler.remove_task(t["id"])
                self._say_local(text, "*把小本本擦干净* 所有定时任务都清掉啦~")
                return True
            frag = m.group(1)
            for t in scheduler.load_tasks():
                if t["id"].endswith(frag) or t["id"] == frag:
                    scheduler.remove_task(t["id"])
                    self._say_local(text, f"*划掉一行* 删掉啦:{scheduler.describe(t)}")
                    return True
            self._say_local(text, "*挠头* 没找到这个任务诶… 说「我的任务」看看有哪些?")
            return True

        # 新建定时任务【快通道】:只拦最明确无歧义的句式(每天X点 / X分钟后 / 每隔X),
        # 规则能稳稳解析 → 本地秒存,不发 claude。
        # 其余(今晚、下周三、没说时间…)一律 return False,
        # 交给带定时工具的主对话 —— claude 自己判断要不要建任务/反问/普通聊。
        if scheduler.looks_like_schedule_strict(text):
            sched = scheduler.parse_schedule(text)
            if sched is not None:
                self._save_schedule(text, sched)
                return True
            # 极少数:strict 命中但 parse 没解析出 → 不强留,交给 claude
        return False

    def _save_schedule(self, text, sched):
        task = self._build_task(text, sched)
        scheduler.add_task(task)
        # 记进历史时带上 id 末4位,让后续"删掉它/改一下"发给 claude 时
        # 它能从历史里看到刚建了哪条任务、对应哪个 id,正确指代。
        pika = (f"*认真记到小本本上* 好嘞!记下啦:\n「{scheduler.describe(task)}」"
                f"（id:{task['id'][-4:]}）\n到点皮卡丘会帮你搞定的!⚡")
        self._say_local(text, pika)

    def _build_task(self, text, sched):
        cleaned = self._strip_time_words(text)
        return {
            "id": scheduler._new_id(),
            "desc": (cleaned[:30] or "提醒"),
            # prompt 存去掉时间词的纯任务内容:到点执行时不会被"两分钟后"等
            # 残留时间词干扰,claude 才不会误以为还要等/只是记任务。
            "prompt": cleaned or text,
            "mode": scheduler.task_mode(text),   # reminder=只提醒 / action=调claude执行
            "enabled": True,
            **sched,
        }

    @staticmethod
    def _strip_time_words(text):
        """从原话里去掉时间词,留下纯任务内容(给 desc 和 action 的 prompt 用)。"""
        import re
        # 先把中文数字归一成阿拉伯数字,时间词正则才能命中"两分钟之后"等
        t = scheduler._normalize_cn_numbers(text)
        d = re.sub(r"(每天|每周[一二三四五六日天]?|每隔?\s*\d+\s*(秒|分钟|分|小时|个小时)|"
                   r"\d+\s*[:点时]\s*\d*\s*分?|早上|中午|下午|晚上|傍晚|"
                   r"\d+\s*(秒|分钟|分|小时|个小时)\s*[之以]?后|半小时后|"
                   r"提醒我|记得|准时|到点)", "", t).strip()
        d = d.lstrip("，,。.、 ")
        # 去掉开头的称呼"皮卡丘,"
        d = re.sub(r"^皮卡丘[,，、\s]*", "", d).strip()
        return d

    def _say_local(self, user_text, pika_text):
        """快通道(本地处理,不发 claude)时:显示皮卡丘气泡 + 把这一轮记进历史。

        关键:本地处理的轮次也必须进 self._history,否则后续发给 claude 时
        它看不到"刚才建/删了什么任务",导致"删掉它""改一下"这类指代失效。
        """
        self._add("皮卡", pika_text)
        self._history.append(("我", user_text))
        self._history.append(("皮卡丘", pika_text))

    # 思考转圈动画帧:盲文旋转点(单字符等宽,旋转不改变气泡尺寸,流畅好看)
    _SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def _tick(self, sec):
        # tick 每秒来一次:只更新读秒,转圈由 _spin_timer(120ms)单独驱动。
        if self._thinking is not None:
            self._spin_sec = sec
            self._render_thinking()

    def _release_thinking(self):
        """把定宽的"正在想"气泡恢复成自适应气泡(真回复来了要能换行/撑开)。

        setFixedWidth 会同时锁死 min/max 宽,这里把两者解开:
        min=0、max=360,再开 WordWrap,气泡就能按内容自适应了。
        """
        if hasattr(self, "_spin_timer"):
            self._spin_timer.stop()
        b = getattr(self, "_thinking_fixed", None)
        if b is not None:
            b.setMinimumWidth(0)
            b.setMaximumWidth(360)
            b.setWordWrap(True)
            self._thinking_fixed = None
        self.thinking_ended.emit()          # 让桌宠本体退出思考态

    def _reply(self, text):
        if self._thinking is not None:
            self._release_thinking()
            self._set_html(self._thinking, text); self._thinking = None
        else:
            self._add("皮卡", text)
        self._history.append(("我", self._pending_user))
        self._history.append(("皮卡丘", text))
        self._busy(False)
        QTimer.singleShot(30, self._scroll_bottom)

    def _error(self, msg):
        if self._thinking is not None:
            self._release_thinking()
            self._set_html(self._thinking, f"⚠️ {msg}"); self._thinking = None
        else:
            self._add("皮卡", f"⚠️ {msg}")
        self._busy(False)

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        if self._thinking is not None:
            self._release_thinking()
            self._set_html(self._thinking, "（皮卡… 不想了~）"); self._thinking = None
        self._busy(False)

    # ---------- 显示 ----------
    def show_near(self, pet_geo):
        screen = self.screen().availableGeometry() if self.screen() else None
        x = pet_geo.x() - self.width() - 4
        y = pet_geo.y() + pet_geo.height() // 2 - self.height() // 2
        if screen is not None:
            if x < screen.left():
                x = pet_geo.x() + pet_geo.width() // 2 - self.width() // 2
                y = pet_geo.y() - self.height() - 4
            x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
            y = max(screen.top() + 4, min(y, screen.bottom() - self.height() - 4))
        self.move(int(x), int(y))
        self.setWindowOpacity(1.0)   # 不做淡入,避免每次 toggle 闪烁
        self.show()
        self.raise_()
        self.activateWindow()
        # 延迟聚焦输入框(立即 setFocus 在无边框 Tool 窗上会触发输入法噪音日志)
        QTimer.singleShot(120, self.input.setFocus)
