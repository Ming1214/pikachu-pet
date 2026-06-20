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
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import claude_bridge
import config
import macos_window
import memory
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

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

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
        # 取消后仍在跑、已被替换的 worker:保活到自己退出,防 QThread 仍运行被 GC。
        self._orphans = []
        self._thinking = None
        # 定宽"正在想"气泡引用:_add_thinking 时赋值、_release_thinking 时清空。
        # 这里先初始化,免得 _render_thinking 在赋值前被调到要靠 getattr 兜底。
        self._thinking_fixed = None
        # "正在想"气泡下方的时间戳 QLabel:回复完成时刷新成回复时刻(而非提问时刻)。
        self._thinking_time = None
        # "正在想"气泡的复制按钮:占位时隐藏,真回复落定(_release_thinking)才 show。
        self._thinking_copy = None
        self._pending_user = ""
        self._history = []
        # claude 不可用降级时,只在【本窗口首次】降级带完整提示(那句很长,解释要装
        # Claude Code);之后只回纯拟声词,免得连发多条被同一句长提示刷屏。
        self._babbled_hint = False
        # 桌宠本体回调:快通道本地建任务后冒"已记下"确认气泡(与 MCP 路径一致)。
        # 由 pet.open_chat 创建本窗口后注入;为 None 时不影响聊天功能。
        self.on_local_schedule = None
        # 桌宠本体回调:窗关着时后台 claude 跑完了,让本体冒"想好了,双击看"气泡,
        # 否则用户收了窗就不知道活干完没。由 pet.open_chat 注入;为 None 不影响功能。
        self.on_background_done = None
        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        macos_window.join_all_spaces(self)
        # 聊天窗 level 显式设为 3(= WindowStaysOnTopHint 在 Cocoa 下本就映射到的
        # NSFloatingWindowLevel):严格说是冗余,但写明白意图——聊天窗浮在普通应用
        # 之上、又比皮卡丘本体(5)低一档,本体的 ASCII 形象始终可见盖不住。
        # 留作显式断言,万一日后 Qt 的映射变了,这行仍把它钉回 3。
        macos_window.set_window_level(self, 3)

    def hideEvent(self, event):
        """收起/关闭聊天窗 = 只把窗藏起来,【不】中断正在跑的 claude。

        设计:收窗 ≠ 喊停。claude 后台继续干活(和定时任务一致),完成后:
        重新打开窗就能看到回复;若关着没看到,_reply/_error 仍把气泡写进(隐藏的)
        消息区,重开即见。真要喊停,点输入栏旁的"✕"取消键(_on_cancel)。

        这里只做一件事:让桌宠本体退出"思考态"(否则窗关了它还在原地一直挠头)。
        worker 本身不动,thinking 转圈气泡也保留——重开窗时还能看到它在转。
        """
        if (self._worker is not None and self._worker.isRunning()
                and self._thinking is not None):
            # 暂时通知本体"不用一直挠头了",但 worker 继续;重开窗会重新进思考态。
            self.thinking_ended.emit()
        super().hideEvent(event)

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
        # 把原始纯文本挂在 label 上,供"复制"按钮取用(label.text() 拿到的是带 HTML
        # 标签的富文本,不能直接复制)。富文本展示走下面的 setText;复制走 _raw_text。
        label._raw_text = text
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

    def _copy_button(self, source_label):
        """生成一个"复制"小按钮,点一下把 source_label 的原始文本写进系统剪贴板。

        只挂在皮卡丘回复气泡下方(用户自己说的话不必加)。复制取 source_label._raw_text
        (_set_html 时存的纯文本),而非 label.text()(那是带 <div>/<br> 标签的富文本)。
        """
        btn = QPushButton("📋 复制")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setStyleSheet(
            "QPushButton{color:#9AA0A6; font-size:10px; background:transparent;"
            f"border:none; padding:2px 4px 0 4px; font-family:{FONT};}}"
            "QPushButton:hover{color:#EE1515;}")   # 悬停变精灵球红,提示可点
        btn.clicked.connect(lambda: self._copy_to_clipboard(source_label, btn))
        return btn

    def _copy_to_clipboard(self, source_label, btn):
        """把气泡原始文本复制到系统剪贴板,并把按钮文案短暂切成"✓ 已复制"反馈。"""
        try:
            text = getattr(source_label, "_raw_text", "") or ""
            QApplication.clipboard().setText(text)
        except Exception:
            return
        btn.setText("✓ 已复制")
        # 1.5s 后恢复成"📋 复制"。用 lambda 守卫:气泡可能已被销毁(理论上不会,
        # 但收窗/重建场景保险些),setText 抛 RuntimeError 就忽略。
        def _restore():
            try:
                btn.setText("📋 复制")
            except RuntimeError:
                pass
        QTimer.singleShot(1500, _restore)

    def _add(self, who, text):
        b = self._bubble(who, text)
        ts = self._time_label(who)
        # 气泡 + 时间戳竖直叠放,再整体左/右对齐
        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(1)
        col.addWidget(b)
        # 皮卡丘回复:时间戳 + 复制按钮并排放在气泡下方左侧;用户气泡只放时间戳。
        if who == "你":
            col.addWidget(ts)
        else:
            meta = QHBoxLayout(); meta.setContentsMargins(0, 0, 0, 0); meta.setSpacing(2)
            meta.addWidget(ts)
            meta.addWidget(self._copy_button(b))
            meta.addStretch()
            col.addLayout(meta)
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
        self._thinking_tier = 0       # 当前安抚文案档位(0/1/2),换档时才调高度防闪
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0)
        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(1)
        col.addWidget(b)
        # 时间戳此刻显示的是"提问时刻",但真正有意义的是【回复完成时刻】——
        # 留个引用,等 _reply/_error 回复落定时刷新成那一刻(见 _stamp_thinking_time)。
        self._thinking_time = self._time_label("皮卡")
        # 复制按钮先建好但隐藏:"正在想…"占位文本不该被复制,等 _release_thinking
        # 把真回复填进这个气泡(b 即真回复 label)后再 show 出来。
        self._thinking_copy = self._copy_button(b)
        self._thinking_copy.hide()
        meta = QHBoxLayout(); meta.setContentsMargins(0, 0, 0, 0); meta.setSpacing(2)
        meta.addWidget(self._thinking_time)
        meta.addWidget(self._thinking_copy)
        meta.addStretch()
        col.addLayout(meta)
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
        # 分级安抚:claude 调用耗时不稳定(冷启动/加载 MCP/后端排队可能拖到几十秒)。
        # 干读秒会让用户分不清"在慢慢想"还是"卡死了"。按时长换文案,让用户安心等、
        # 也知道可以点 ✕ 停。
        s = self._spin_sec
        if s >= 45:
            tier, tip = 2, "(有点久…急的话点 ✕ 停下,换简单点的说法~)"
        elif s >= 20:
            tier, tip = 1, "(还在想,稍等我一下下~)"
        else:
            tier, tip = 0, ""
        label.setText(
            f"<div style='line-height:150%;'>{spin} 皮卡丘正在想… {sec_str} 秒 ⚡"
            f"{('<br>' + tip) if tip else ''}</div>")
        # 仅在【换档】时调整气泡高度(全程最多 2 次),平时不动 → 不闪。气泡宽度
        # 固定 235,安抚文案够短能放下;多出的第二行需要把固定高度放开重算,
        # 否则按单行定的高会把第二行截断(就像之前见过的气泡截断)。
        tier_changed = getattr(self, "_thinking_tier", 0) != tier
        if tier_changed:
            self._thinking_tier = tier
            b = self._thinking_fixed if self._thinking_fixed is not None else self._thinking
            if b is not None:
                b.setWordWrap(tier > 0)            # 有第二行时才允许换行
                b.setMinimumHeight(0)
                b.setMaximumHeight(16777215)
                h = b.heightForWidth(235) if tier > 0 else 0
                if h > 0:
                    b.setFixedHeight(h)
                else:
                    b.adjustSize()
                    b.setFixedWidth(235)

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
        if not text:
            return
        # 当前 worker 仍在跑:
        # - 未取消(用户没点 ✕,只是手快又发一句)→ 维持"一次只发一句",静默忽略。
        # - 已取消(用户点了 ✕,但 claude 子进程还没退干净)→ 不能再卡着用户,
        #   把它"孤儿化"(_orphan_worker)让它自己跑完即弃,放行这次新发送。
        #   迟到的回复靠 _reply/_error 的 sender 身份比对丢弃,不会串台。
        if self._worker and self._worker.isRunning():
            if self._worker.cancelled:
                self._orphan_worker(self._worker)
                self._worker = None
            else:
                return
        self.input.clear()
        self._add("你", text)
        # 先看是不是在管理定时任务(列出/删除/新建),命中就本地处理,不发 claude
        if self._handle_schedule_command(text):
            return
        # claude 不可用(没装 Claude Code / 不在 PATH):不起注定失败的 worker,
        # 皮卡丘改用拟声台词"出声"回应——既给即时反馈,又温和点明原因。复用
        # _say_local(进历史 + 落记忆流水,与正常一轮一致),不进 thinking 态、
        # 无超时等待。放在 schedule 判断【之后】:没装 claude 时本地定时命令仍可用。
        if not claude_bridge.claude_available():
            babble = random.choice(config.PIKA_BABBLE)
            # 首次降级带完整提示(解释要装 Claude Code),之后只回纯拟声词,不刷屏。
            if not self._babbled_hint:
                self._babbled_hint = True
                pika = f"{babble}\n\n{config.PIKA_NO_CLAUDE_HINT}"
            else:
                pika = babble
            self._say_local(text, pika)
            return
        self._thinking = self._add_thinking()
        self._busy(True)
        self._pending_user = text
        self.thinking_started.emit()        # 让桌宠本体进思考态
        recent = self._history[-12:]
        w = ClaudeWorker(text, history=recent)
        # 关键:lambda 捕获【发出信号的这个 worker 实例】,回调里比对 self._worker
        # 是否仍是它。否则——用户取消 A 后立刻发 B,self._worker 已换成 B,
        # A 的迟到 succeeded 会用 B 的 cancelled(False)通过守卫,把 A 的回复
        # 串台写进 B 的对话和历史(污染多轮上下文)。靠身份比对而非 cancelled 旗标。
        w.succeeded.connect(lambda r, _w=w: self._reply(r, _w))
        w.failed.connect(lambda e, _w=w: self._error(e, _w))
        w.tick.connect(self._tick)
        # worker 跑完(正常/取消)→ 释放:断信号 + 从孤儿表移除 + deleteLater。
        # 不接 deleteLater 的话,被取消又被替换的 worker 会被 succeeded/failed/tick
        # 三个 lambda 闭包(各持 _w=w)长期引用,连同其 _ticker 线程一起泄漏。
        w.finished.connect(lambda _w=w: self._cleanup_worker(_w))
        self._worker = w
        w.start()

    def _orphan_worker(self, w):
        """把一个【已取消但还在跑】的 worker 移出主路径,挂进孤儿表保活到它自己退出。

        必须保留一个 Python 引用(_orphans),否则 QThread 对象可能在仍运行时被 GC,
        Qt 会报 'QThread: Destroyed while thread is still running' 甚至崩溃。
        它退出时 finished→_cleanup_worker 会把它从 _orphans 摘掉并 deleteLater。
        """
        if w is None:
            return
        # 立即断开 tick:孤儿的 _ticker 线程会继续每秒 emit tick 打到 self._tick,
        # 与新 worker 的 tick 交替打架,转圈读秒会在两者之间忽大忽小乱跳。
        # succeeded/failed 不必在这里断——它们的回调有 _w 身份守卫(比对 self._worker),
        # 孤儿的迟到结果会被守卫丢弃,不会串台;真正释放在 finished→_cleanup_worker。
        try:
            w.tick.disconnect(self._tick)
        except (TypeError, RuntimeError):
            pass
        if not hasattr(self, "_orphans"):
            self._orphans = []
        if w not in self._orphans:
            self._orphans.append(w)

    def _cleanup_worker(self, w):
        """worker finished 回调:断开它的信号、移出孤儿表、deleteLater 释放。"""
        for sig in (w.succeeded, w.failed, w.tick):
            try:
                sig.disconnect()
            except (TypeError, RuntimeError):
                pass
        if hasattr(self, "_orphans") and w in self._orphans:
            self._orphans.remove(w)
        if self._worker is w:
            self._worker = None
        try:
            w.deleteLater()
        except RuntimeError:
            pass

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
                n = scheduler.remove_all_tasks()      # 锁内原子清空,不漏删并发新建
                if n > 0:
                    self._say_local(text, "*把小本本擦干净* 所有定时任务都清掉啦~")
                elif n < 0:
                    # 存盘失败:任务其实还在,别误报"清掉了/没有任务"
                    self._say_local(text, "*急得冒汗* 呜…小本本擦不掉(存盘出错),任务还在,等会儿再试?")
                else:
                    self._say_local(text, "*翻翻小本本* 本来就没有任务呀~")
                return True
            frag = m.group(1)
            for t in scheduler.load_tasks():
                if t["id"].endswith(frag) or t["id"] == frag:
                    if scheduler.remove_task(t["id"]):
                        self._say_local(text, f"*划掉一行* 删掉啦:{scheduler.describe(t)}")
                    else:
                        self._say_local(text, "*挠头* 想删但小本本卡住了(存盘出错),这条没删掉,等会儿再试?")
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
                # 内容为空(如"每天早上提醒我",剥掉时间词后没剩任务内容)→ 别建
                # desc="提醒"、prompt 含时间词的空壳任务(到点冒"该「提醒」啦"用户
                # 一头雾水)。交给 claude,它会用皮卡丘口吻反问"要提醒你做什么呀?"。
                if not self._strip_time_words(text):
                    return False
                # reminder/action 拿不准(含执行动词的歧义,如"帮我提醒团队")
                # → 不本地硬猜,交给 claude 结合语境判 mode 再建,避免误执行/误漏做。
                mode = scheduler.fast_path_mode(text)
                if mode is None:
                    return False
                self._save_schedule(text, sched, mode)
                return True
            # strict 命中但 parse 没解析出 → 多半是越界时间(如"每天25点")。
            # 不静默转给 claude(体验不一致:正常句秒建任务,这句却没反应),
            # 本地给一句友好澄清,告诉用户时间不合法。
            self._say_local(
                text, "*挠头* 这个时间皮卡丘没看懂诶… 钟点要在 0~23 之间哦,"
                "换个说法?比如「每天9点提醒我喝水」⚡")
            return True
        return False

    def _save_schedule(self, text, sched, mode):
        task = self._build_task(text, sched, mode)
        created = scheduler.add_task(task)
        if created == "duplicate":
            # 已有等价任务:别重复建,免得到点重复提醒。
            self._say_local(text, f"*翻了翻小本本* 这个皮卡丘早就记着啦~「{scheduler.describe(task)}」😆")
            return
        if created == "save_failed":
            # 存盘失败:别假报"记下啦",否则用户以为记住了、重启后任务消失。
            self._say_local(text, "*急得冒汗* 呜…小本本写不进去(存盘出错了),这条没记成,等会儿再试试?")
            return
        # 记进历史时带上 id 末4位,让后续"删掉它/改一下"发给 claude 时
        # 它能从历史里看到刚建了哪条任务、对应哪个 id,正确指代。
        pika = (f"*认真记到小本本上* 好嘞!记下啦:\n「{scheduler.describe(task)}」"
                f"（id:{task['id'][-4:]}）\n到点皮卡丘会帮你搞定的!⚡")
        self._say_local(text, pika)
        # 让桌宠本体也冒"已记下"气泡 + 放电,和走 claude+MCP 建任务的路径体验一致
        # (那条路径靠 tool_events.jsonl 通知本体;快通道是本地直存,这里直接回调)。
        if self.on_local_schedule is not None:
            try:
                self.on_local_schedule(task.get("desc", "提醒"))
            except Exception:
                pass

    def _build_task(self, text, sched, mode):
        cleaned = self._strip_time_words(text)
        return {
            "id": scheduler._new_id(),
            "desc": (cleaned[:30] or "提醒"),
            # prompt 存去掉时间词的纯任务内容:到点执行时不会被"两分钟后"等
            # 残留时间词干扰,claude 才不会误以为还要等/只是记任务。
            "prompt": cleaned or text,
            # mode 由 fast_path_mode 在调用方定好传入(reminder/action);
            # 拿不准的(None)早已在 _handle_schedule_command 放行给 claude,不会到这。
            "mode": mode,
            "enabled": True,
            **sched,
        }

    @staticmethod
    def _strip_time_words(text):
        """从原话里去掉时间词,留下纯任务内容(给 desc 和 action 的 prompt 用)。"""
        import re
        # 先把中文数字归一成阿拉伯数字,时间词正则才能命中"两分钟之后"等
        t = scheduler._normalize_cn_numbers(text)
        # 时间点项尾部补 `半?`:否则"9点半"只剥掉"9点",残留的"半"会粘进
        # desc/prompt(如"每天9点半提醒我运动"→"半运动"),气泡和发给 claude 的
        # 指令都莫名带个"半"。"凌晨"也一并纳入早中晚词表。
        d = re.sub(r"(每天|每周[一二三四五六日天]?|每隔?\s*\d+\s*(秒|分钟|分|小时|个小时)|"
                   r"\d+\s*[:点时]\s*\d*\s*分?半?|早上|中午|下午|晚上|傍晚|凌晨|"
                   r"\d+\s*(秒|分钟|分|小时|个小时)\s*[之以]?后|半小时后|"
                   r"提醒我|记得|准时|到点)", "", t).strip()
        d = d.lstrip("，,。.、 ")
        # 兜底:清掉可能残留在开头的孤立"半"(如"点半"被拆后剩的"半")
        d = re.sub(r"^半(?![小时点])", "", d).strip()
        # 去掉开头的称呼"皮卡丘,"
        d = re.sub(r"^皮卡丘[,，、\s]*", "", d).strip()
        return d

    def inject_pika_opening(self, text):
        """主动搭话:把皮卡丘的一句开场白写进聊天窗(显示气泡 + 进历史 + 落流水),

        让用户点开主动气泡后,聊天窗里已经有皮卡丘先开了口,可直接接着聊,
        且后续多轮上下文连贯(进了 self._history)。供 pet 在主动搭话点击后调用。
        """
        text = (text or "").strip()
        if not text:
            return
        self._add("皮卡", text)
        self._history.append(("皮卡丘", text))
        self._log_convo("pika", text)
        QTimer.singleShot(30, self._scroll_bottom)

    @staticmethod
    def _log_convo(role, text):
        """把一句对话落盘到记忆流水(整理记忆的原料)。失败绝不影响聊天。"""
        if not config.MEMORY_ENABLED:
            return
        try:
            memory.append_convo(role, text)
        except Exception:
            pass

    def _say_local(self, user_text, pika_text):
        """快通道(本地处理,不发 claude)时:显示皮卡丘气泡 + 把这一轮记进历史。

        关键:本地处理的轮次也必须进 self._history,否则后续发给 claude 时
        它看不到"刚才建/删了什么任务",导致"删掉它""改一下"这类指代失效。
        """
        self._add("皮卡", pika_text)
        self._history.append(("我", user_text))
        self._history.append(("皮卡丘", pika_text))
        # 落盘到记忆流水:本地处理的轮次也是真实对话,要进整理原料
        self._log_convo("user", user_text)
        self._log_convo("pika", pika_text)

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
            # 解除安抚换档时可能设过的固定高度,真回复才能按内容自由撑开
            b.setMinimumHeight(0)
            b.setMaximumHeight(16777215)
            b.setWordWrap(True)
            self._thinking_fixed = None
        # 把"正在想"气泡的时间戳刷新成【回复落定的此刻】(原先写死的是提问时刻,
        # 皮卡丘想了几十秒,标提问时间会让人以为秒回 / 时序错乱)。
        if self._thinking_time is not None:
            from datetime import datetime
            try:
                self._thinking_time.setText(datetime.now().strftime("%H:%M"))
            except RuntimeError:
                pass                         # label 已随气泡销毁则忽略
            self._thinking_time = None
        # 真回复(或错误文案)已填进气泡 → 亮出复制按钮(此前在 _add_thinking 里隐藏)。
        if getattr(self, "_thinking_copy", None) is not None:
            try:
                self._thinking_copy.show()
            except RuntimeError:
                pass
            self._thinking_copy = None
        self.thinking_ended.emit()          # 让桌宠本体退出思考态

    def _reply(self, text, sender=None):
        # 身份守卫:只接受【当前 worker】发来的回复。覆盖两种竞态:
        # ① 用户取消后这条信号迟到(sender 已不是 self._worker);
        # ② 取消 A 后立刻发 B,A 的迟到回复(sender 是 A,self._worker 是 B)。
        # 两者都 → sender is not self._worker → 直接丢弃,不污染当前对话/历史。
        if sender is not None and sender is not self._worker:
            return
        if self._worker is not None and self._worker.cancelled:
            return
        if self._thinking is not None:
            self._release_thinking()
            self._set_html(self._thinking, text); self._thinking = None
        else:
            self._add("皮卡", text)
        self._history.append(("我", self._pending_user))
        self._history.append(("皮卡丘", text))
        # 落盘到记忆流水(整理记忆的原料)
        self._log_convo("user", self._pending_user)
        self._log_convo("pika", text)
        self._busy(False)
        QTimer.singleShot(30, self._scroll_bottom)
        self._notify_if_hidden(ok=True)

    def _error(self, msg, sender=None):
        if sender is not None and sender is not self._worker:
            return
        if self._worker is not None and self._worker.cancelled:
            return
        if self._thinking is not None:
            self._release_thinking()
            self._set_html(self._thinking, f"⚠️ {msg}"); self._thinking = None
        else:
            self._add("皮卡", f"⚠️ {msg}")
        # 把失败这一轮也写进历史:否则用户接着说"再试一次/刚才那个"时,发给 claude
        # 的最近 12 轮里没有这次提问的痕迹,claude 不知道"刚才"指什么。用占位回复
        # 记下皮卡丘没答上来,保持多轮上下文连贯。
        if self._pending_user:
            self._history.append(("我", self._pending_user))
            self._history.append(("皮卡丘", "(没能回应,出错了)"))
            # 只落用户这句:皮卡丘没答上来,记下用户说了啥即可(整理时它能看到)
            self._log_convo("user", self._pending_user)
        self._busy(False)
        self._notify_if_hidden(ok=False)

    def _notify_if_hidden(self, ok):
        """后台 claude 跑完时若聊天窗是关着的,让本体冒气泡提示用户回来看,
        否则收了窗就不知道活干完没(claude 后台继续干是新设计:收窗不中断)。
        """
        if self.isVisible():
            return
        if self.on_background_done is not None:
            try:
                self.on_background_done(ok)
            except Exception:
                pass

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        if self._thinking is not None:
            self._release_thinking()
            self._set_html(self._thinking, "（皮卡… 不想了~）"); self._thinking = None
        self._busy(False)

    # ---------- 显示 ----------
    def show_near(self, pet_geo):
        from PyQt6.QtWidgets import QApplication
        # 首次 show 前 self.screen() 可能为 None → 回退主屏,确保 clamp 一定生效,
        # 否则聊天窗可能定位到屏幕外(尤其皮卡丘被拖到边角时)。
        scr = self.screen() or QApplication.primaryScreen()
        screen = scr.availableGeometry() if scr else None
        x = pet_geo.x() - self.width() - 4              # 优先放皮卡丘左侧
        y = pet_geo.y() + pet_geo.height() // 2 - self.height() // 2
        if screen is not None:
            if x < screen.left():
                x = pet_geo.right() + 4                 # 左侧放不下 → 试右侧
            if x + self.width() > screen.right():
                # 左右都放不下 → 皮卡丘正上方居中
                x = pet_geo.x() + pet_geo.width() // 2 - self.width() // 2
                y = pet_geo.y() - self.height() - 4
            x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
            y = max(screen.top() + 4, min(y, screen.bottom() - self.height() - 4))
        self.move(int(x), int(y))
        self.setWindowOpacity(1.0)   # 不做淡入,避免每次 toggle 闪烁
        self.show()
        self.raise_()
        self.activateWindow()
        # 重开窗时若上次的 claude 还在后台跑(收窗没中断它):让桌宠本体重新进
        # 思考态接续(hideEvent 时让它退出过),并滚到底看到那条还在转圈的气泡。
        if self._worker is not None and self._worker.isRunning():
            self.thinking_started.emit()
            QTimer.singleShot(30, self._scroll_bottom)
        # 延迟聚焦输入框(立即 setFocus 在无边框 Tool 窗上会触发输入法噪音日志)
        QTimer.singleShot(120, self.input.setFocus)
