"""聊天窗(宝可梦球 红白卡通主题)。

致敬精灵球:上半红色标题栏 + 黑色腰带 + 中央白色"按钮"头像 + 下半白色主体。
卡通粗黑描边、实色填充,不用模糊玻璃。
"""

import os
import random
import re
import shutil
import threading
import time
import uuid

from PyQt6.QtCore import (
    Qt, QThread, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QRectF,
)
from PyQt6.QtGui import (
    QBrush, QColor, QImage, QPainter, QPainterPath, QPixmap, QPen,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout,
    QWidget,
)

import claude_bridge
import config
import macos_window
import memory
import scheduler

FONT = config.FONT_STACK

# 可识别为"图片"的扩展名(拖拽/粘贴文件 URL 时据此判定要不要当图片收下)
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".heic"}


class ClaudeWorker(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)
    tick = pyqtSignal(int)

    def __init__(self, prompt, history=None, segments=None):
        super().__init__()
        self._prompt = prompt
        self._history = history or []
        self._segments = segments      # 图文混排消息(None=纯文本走旧路径)
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
                self._prompt, history=self._history, cancel_event=self._cancel,
                segments=self._segments)
            if not self._cancel.is_set():
                self.succeeded.emit(reply)
        except claude_bridge.ClaudeError as exc:
            if not self._cancel.is_set():
                self.failed.emit(str(exc))
        except Exception as exc:
            if not self._cancel.is_set():
                self.failed.emit(f"{config.PET_NAME}短路了:{exc}")
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
        # 存引用:切宝可梦后由 refresh_identity() 重读 config 刷新文字(否则一直是建窗时的旧名)。
        self.title = QLabel(config.PET_NAME)
        self.title.setStyleSheet(
            f"font-size:17px; font-weight:900; color:#FFFFFF; background:transparent; font-family:{FONT};")
        self.sub = QLabel(config.PET_SPECIES)
        self.sub.setStyleSheet(
            f"font-size:11px; color:rgba(255,255,255,210); background:transparent; font-family:{FONT};")
        box.addWidget(self.title); box.addWidget(self.sub)
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

    def refresh_identity(self):
        """切宝可梦后刷新标题/副标题为当前 PET_NAME/PET_SPECIES(热生效)。"""
        try:
            self.title.setText(config.PET_NAME)
            self.sub.setText(config.PET_SPECIES)
        except Exception:
            pass

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


class _ChatInput(QTextEdit):
    """多行聊天输入框(替代单行 QLineEdit):

    - Enter 发送(发 submit 信号);Option/Alt+Enter、Shift+Enter 插入换行。
    - 高度随内容在 [单行, 5 行] 间自适应,超出则内部滚动。
    - 拖拽/粘贴本地文件(任意类型)→ 发 path_received(str 路径,窗口侧按扩展名
      分流图片/文件);Ctrl+V 粘贴剪贴板里的位图(如截图)→ 发 image_received(QImage)。
    """

    submit = pyqtSignal()
    image_received = pyqtSignal(object)   # QImage(剪贴板位图,如截图)
    path_received = pyqtSignal(str)       # 本地文件路径(任意类型,窗口侧分流)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAcceptRichText(False)        # 只收纯文本,避免粘进富文本格式
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 垂直滚动条一律隐藏:AsNeeded 时 Qt 会画出原生上下步进箭头(那对小箭头很丑,
        # 见反馈截图)。高度已在 [42,130] 自适应封顶,封顶后靠滚轮/方向键滚动即可,
        # 不需要可见滚动条。设 Off 既去掉箭头,也省出右侧空间给文字。
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._min_h = 42                     # 约单行(含 padding)
        self._max_h = 130                    # 约 5 行后转为内部滚动
        self.setFixedHeight(self._min_h)
        self.textChanged.connect(self._autosize)

    def _autosize(self):
        """随文档内容增高,封顶后保持固定高度由内部滚动。"""
        doc_h = self.document().size().height()
        h = int(doc_h) + 14                  # 上下 padding 余量
        h = max(self._min_h, min(h, self._max_h))
        if h != self.height():
            self.setFixedHeight(h)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # IME(中文输入法)组字时按 Enter 确认候选词:这种 Enter 的 e.text()
            # 为空(真正的字符走 inputMethodEvent),交回基类处理,别误当成"发送"——
            # 否则第三方输入法选词时会把半成品消息提前发出去。
            if not e.text():
                super().keyPressEvent(e)
                return
            mods = e.modifiers()
            # Option(macOS Alt)/ Shift + Enter → 换行;纯 Enter → 发送
            if mods & (Qt.KeyboardModifier.AltModifier
                       | Qt.KeyboardModifier.ShiftModifier):
                self.insertPlainText("\n")
                return
            self.submit.emit()
            return
        super().keyPressEvent(e)

    # ── 粘贴(Ctrl/Cmd+V):剪贴板有本地文件就当附件收,有位图就当图收,否则纯文本粘 ──
    def insertFromMimeData(self, source):
        if source.hasUrls():
            handled = False
            for url in source.urls():
                p = url.toLocalFile()
                if p and os.path.isfile(p):
                    self.path_received.emit(p)
                    handled = True
            if handled:
                return
        if source.hasImage():
            img = source.imageData()
            if isinstance(img, QImage) and not img.isNull():
                self.image_received.emit(img)
                return
        super().insertFromMimeData(source)

    # ── 拖拽:含本地文件(任意类型)或位图就接收 ──
    def _has_file_drop(self, e):
        md = e.mimeData()
        if md.hasImage():
            return True
        if md.hasUrls():
            return any(u.toLocalFile() and os.path.isfile(u.toLocalFile())
                       for u in md.urls())
        return False

    def dragEnterEvent(self, e):
        if self._has_file_drop(e):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if self._has_file_drop(e):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        md = e.mimeData()
        took = False
        if md.hasUrls():
            for url in md.urls():
                p = url.toLocalFile()
                if p and os.path.isfile(p):
                    self.path_received.emit(p)
                    took = True
        if not took and md.hasImage():
            img = md.imageData()
            if isinstance(img, QImage) and not img.isNull():
                self.image_received.emit(img)
                took = True
        if took:
            e.acceptProposedAction()
        else:
            super().dropEvent(e)


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
        # 本条待发消息里已挂账的附件:序号 → {"type":"image"|"file","path":...,"name":...}。
        # 图片和文件【共用同一套序号】(_attach_counter),所以 [图片 #1] 与 [文件 #2]
        # 不会撞号。发送/清空时重置;序号只增不减,删占位符也不复用,避免歧义。
        self._pending_attachments = {}
        self._attach_counter = 0
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
        # 切宝可梦后标题/副标题/输入框占位符是建窗时固化的旧名,每次显示前按当前
        # PET_NAME 刷新一次(开销极小),保证换了宝可梦再打开聊天窗身份就对得上。
        try:
            if hasattr(self, "_titlebar"):
                self._titlebar.refresh_identity()
            self.input.setPlaceholderText(
                f"和{config.PET_NAME}说点什么…(Enter 发送 / Option+Enter 换行)")
        except Exception:
            pass
        # 聊天窗【常驻所有桌面】+ 钉层级,收成单一入口 _apply_macos_window_behavior()。
        # 同步先设一次(本体早已 mapped 的常态可即刻生效),再用 singleShot(0) 在事件循环
        # 下一轮补设一次:聊天窗【首次】显示时,showEvent 同步触发于 show() 内部,此刻
        # NSView 还没挂进 NSWindow,join_all_spaces 里 [view window] 返回 nil → CanJoinAllSpaces
        # 设不上、聊天窗完全不跟随桌面(本次 BUG)。回到事件循环后 NSWindow 已就绪,补设必成。
        self._apply_macos_window_behavior()
        QTimer.singleShot(0, self._apply_macos_window_behavior)

    def _apply_macos_window_behavior(self):
        """常驻所有 Space(CanJoinAllSpaces)+ 钉固定层级。幂等、可重入。

        统一入口:showEvent 同步调一次 + singleShot(0) 补一次,确保首次显示 NSWindow
        就绪后 collectionBehavior 一定设上。窗不可见时跳过(此时无需占 Space/层)。
        不用 MoveToActiveSpace:那只在显示那一刻把窗拉到当前桌面,之后切走不跟随。
        """
        if not self.isVisible():
            return
        macos_window.join_all_spaces(self)
        # 把聊天窗 level 钉到固定档(CHAT_WINDOW_LEVEL=5):浮在普通 App 之上、又比
        # 本体(7)低一档。单一来源走 reassert_top(),切桌面/失活后由 pet 侧重断言复用。
        self.reassert_top()

    def reassert_top(self):
        """把聊天窗钉回固定层级(>普通 App)并抬到最上。幂等、可重入,不闪烁。

        与本体的 _reassert_pet_top 配套:本体只负责"压在聊天窗之上",聊天窗自己负责
        "压在普通 App 之上"。切桌面/App 失活后,Qt 可能把 Tool 窗 level 打回默认 →
        聊天窗掉到别的 App 后面(用户反馈的"切过去先被盖一下"),靠重断言拉回。
        窗不可见时跳过(此时无需占层)。
        """
        if not self.isVisible():
            return
        try:
            macos_window.set_window_level(self, macos_window.CHAT_WINDOW_LEVEL)
            self.raise_()
        except Exception:
            pass

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
        self._titlebar = _TitleBar(self)   # 存引用:showEvent 时刷新身份(切宝可梦热生效)
        col.addWidget(self._titlebar)

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

        # 输入栏(白底 + 黑描边圆角输入框 + 📎图片钮 + 红色发送圆钮)
        bar = QWidget(); bar.setStyleSheet(f"background:{config.COL_CARD_BG};")
        bar_col = QVBoxLayout(bar)
        bar_col.setContentsMargins(0, 0, 0, 0); bar_col.setSpacing(0)

        # 附件失败/提示行(平时隐藏,失败时在输入框上方临时显示,不打断聊天消息流)
        self.attach_tip = QLabel("")
        self.attach_tip.setVisible(False)
        self.attach_tip.setWordWrap(True)
        self.attach_tip.setStyleSheet(
            "QLabel{color:#C40D0D; background:#FFF0F0; border:1px solid #F2C0C0;"
            f"border-radius:10px; padding:5px 12px; font-size:12px; font-family:{FONT};}}")
        tip_wrap = QWidget(); tip_wrap.setStyleSheet(f"background:{config.COL_CARD_BG};")
        tip_l = QHBoxLayout(tip_wrap)
        tip_l.setContentsMargins(12, 8, 12, 0); tip_l.setSpacing(0)
        tip_l.addWidget(self.attach_tip)
        bar_col.addWidget(tip_wrap)

        row_wrap = QWidget(); row_wrap.setStyleSheet(f"background:{config.COL_CARD_BG};")
        row = QHBoxLayout(row_wrap)
        row.setContentsMargins(12, 10, 12, 14); row.setSpacing(8)
        # 输入栏底部对齐:输入框多行变高时,📎/发送钮贴着底边,不被拉伸居中
        row.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # 📎 图片按钮(白底黑描边圆钮,与发送钮同风格)→ 多选图片文件
        self.attach = QPushButton("📎")
        self.attach.setFixedSize(42, 42)
        self.attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach.setToolTip("发送图片或文件(也可拖入或粘贴)")
        self.attach.clicked.connect(self._pick_files)
        self.attach.setStyleSheet(
            "QPushButton{background:#FFFFFF; border:2px solid #2B2B2B; border-radius:21px;"
            "font-size:16px; color:#2B2B2B;}"
            "QPushButton:hover{background:#FFF4C2;}")
        row.addWidget(self.attach)

        self.input = _ChatInput()
        self.input.setPlaceholderText(
            f"和{config.PET_NAME}说点什么…(Enter 发送 / Option+Enter 换行)")
        self.input.submit.connect(self._send)
        self.input.image_received.connect(self._attach_image)
        self.input.path_received.connect(self._attach_path)
        self.input.setStyleSheet(
            "QTextEdit{background:#F4F4F4; border:2px solid #2B2B2B; border-radius:20px;"
            f"padding:7px 14px; font-size:14px; color:#2B2B2B; font-family:{FONT};}}"
            "QTextEdit:focus{border-color:#EE1515; background:#FFFFFF;}"
            # 双保险:把垂直滚动条画成 0 宽、无步进箭头(配合 ScrollBarAlwaysOff,
            # 杜绝个别平台仍渲染原生上下箭头)。封顶后滚轮/方向键照常可滚。
            "QTextEdit QScrollBar:vertical{width:0px;}"
            "QTextEdit QScrollBar::add-line:vertical,"
            "QTextEdit QScrollBar::sub-line:vertical{height:0px;}")
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
        bar_col.addWidget(row_wrap)
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

    # ---------- 发附件(图片/任意文件):挂账 / 落盘 / 占位符 ----------
    def _pick_files(self):
        """📎 按钮:弹系统文件多选(任意类型),逐个挂账(落盘 + 插占位符)。

        按扩展名分流:图片走「[图片 #n]」+ 缩略图,其余走「[文件 #n]」+ 文件卡片。
        """
        paths, _ = QFileDialog.getOpenFileNames(
            self, f"选择图片或文件发给{config.PET_NAME}", os.path.expanduser("~"),
            "所有文件 (*)")
        for p in paths:
            self._attach_path(p)

    def _too_big(self, path):
        """文件超过上限返回其大小(字节),否则返回 0。读不到大小当作 0(放行)。"""
        try:
            cap = getattr(config, "CHAT_UPLOAD_MAX_BYTES", 0)
            if cap and os.path.getsize(path) > cap:
                return os.path.getsize(path)
        except OSError:
            pass
        return 0

    def _attach_fail(self, msg):
        """附件失败的轻提示:放在【输入框上方】临时显示,不插进聊天消息流——
        否则失败气泡会夹在用户还没发出的消息之前,时序错乱。3.5s 后自动消失。
        """
        self.attach_tip.setText(msg)
        self.attach_tip.setVisible(True)
        # 守卫:仅当这条提示仍是当前显示的那条才隐藏(期间又来新提示则由新的接管计时)
        def _hide(expected=msg):
            try:
                if self.attach_tip.text() == expected:
                    self.attach_tip.clear()
                    self.attach_tip.setVisible(False)
            except RuntimeError:
                pass
        QTimer.singleShot(3500, _hide)

    def _insert_placeholder(self, tag_text):
        """在光标处插入占位符,智能补空格:若前一个字符不是空白/换行,先补一个空格,
        避免和前面的文字粘成「你好[图片 #1]」难读、难在中间插字。
        """
        cur = self.input.textCursor()
        pos = cur.position()
        full = self.input.toPlainText()
        prefix = ""
        if pos > 0 and pos <= len(full) and full[pos - 1] not in (" ", "\n", "\t"):
            prefix = " "
        self.input.insertPlainText(prefix + tag_text + " ")

    def _attach_image(self, src):
        """收一张图(src 为文件路径 str,或剪贴板 QImage 位图)。落盘 + 挂账 + 插占位。"""
        # 来源是磁盘文件时先查大小(QImage 是内存位图,不查)
        if isinstance(src, str) and self._too_big(src):
            self._attach_fail(f"这张图太大啦(超过 20MB),{config.PET_NAME}看不动~换张小点的?")
            return
        n = None
        try:
            up_dir = config.CHAT_UPLOAD_DIR
            os.makedirs(up_dir, exist_ok=True)
            self._attach_counter += 1
            n = self._attach_counter
            # 唯一文件名:uuid 防撞;序号入名便于人肉对应「[图片 #n]」。
            tag = uuid.uuid4().hex[:8]
            if isinstance(src, QImage):
                dst = os.path.join(up_dir, f"paste_{n}_{tag}.png")
                name = os.path.basename(dst)
                if not src.save(dst, "PNG"):
                    raise OSError("QImage.save 失败")
            else:
                ext = os.path.splitext(src)[1].lower() or ".png"
                dst = os.path.join(up_dir, f"img_{n}_{tag}{ext}")
                name = os.path.basename(src)
                shutil.copy(src, dst)
        except Exception as exc:
            if n is not None:
                self._attach_counter -= 1     # 落盘失败,序号回退保持连续
            self._attach_fail(self._attach_err_msg(exc, "这张图"))
            return
        self._pending_attachments[n] = {"type": "image", "path": dst, "name": name}
        self._insert_placeholder(f"[图片 #{n}]")

    def _attach_file(self, src):
        """收一个任意文件(src 为文件路径 str)。落盘 + 挂账 + 插「[文件 #n]」占位。"""
        if self._too_big(src):
            self._attach_fail(f"这个文件太大啦(超过 20MB),{config.PET_NAME}读不动~"
                              f"要不直接把路径发给{config.PET_NAME}让它自己去看?")
            return
        n = None
        try:
            up_dir = config.CHAT_UPLOAD_DIR
            os.makedirs(up_dir, exist_ok=True)
            self._attach_counter += 1
            n = self._attach_counter
            tag = uuid.uuid4().hex[:8]
            base = os.path.basename(src) or f"file_{n}"
            # 落盘名带序号 + uuid 防撞,保留原扩展名(claude Read 据扩展名识别格式更准)。
            # 无扩展名文件(Makefile/LICENSE 等)落盘名也无扩展名,但卡片/prompt 用
            # name 字段显示原名,claude 仍按纯文本读得了。
            ext = os.path.splitext(base)[1]
            dst = os.path.join(up_dir, f"file_{n}_{tag}{ext}")
            shutil.copy(src, dst)
        except Exception as exc:
            if n is not None:
                self._attach_counter -= 1
            self._attach_fail(self._attach_err_msg(exc, "这个文件"))
            return
        self._pending_attachments[n] = {"type": "file", "path": dst, "name": base}
        self._insert_placeholder(f"[文件 #{n}]")

    @staticmethod
    def _attach_err_msg(exc, what):
        """按异常类型给具体提示:磁盘满单独点明,其余给通用文案。"""
        if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:
            return f"磁盘空间不足啦,{config.PET_NAME}存不下这个附件了…清点空间再试?"
        return f"*歪头* {what}{config.PET_NAME}没接住诶…换一个试试?"

    def _attach_path(self, path):
        """按扩展名把一个本地文件路径分流到 _attach_image / _attach_file。"""
        ext = os.path.splitext(path)[1].lower()
        if ext in _IMG_EXTS:
            self._attach_image(path)
        else:
            self._attach_file(path)

    def _parse_segments(self, raw_text):
        """把输入框纯文本(含「[图片 #n]」「[文件 #n]」占位)切成有序 segment 列表。

        返回 [{"type":"text"|"image"|"file", ...}, ...]。已被用户手删占位符的附件
        自然不出现;占位符引用了不存在/已删的序号则跳过该占位。
        """
        segments = []
        last = 0
        used = set()                         # 已消费的序号,防同一占位符被复制多份重复发
        for m in re.finditer(r"\[(图片|文件) #(\d+)\]", raw_text):
            pre = raw_text[last:m.start()]
            if pre.strip():
                segments.append({"type": "text", "text": pre})
            n = int(m.group(2))
            att = self._pending_attachments.get(n)
            if att and n not in used:
                used.add(n)
                segments.append(dict(att))   # 拷一份,含 type/path/name
            last = m.end()
        tail = raw_text[last:]
        if tail.strip():
            segments.append({"type": "text", "text": tail})
        return segments

    @staticmethod
    def _segments_plain(segments):
        """把 segments 折叠成纯文本表示(图 → 「[图片]」,文件 → 「[文件:名]」),
        用于历史/流水/复制。【不含绝对路径】:既保上下文连贯,又不泄露本地路径、
        不诱发多轮里反复 Read 旧附件。
        """
        parts = []
        for seg in segments:
            if seg["type"] == "image":
                parts.append("[图片]")
            elif seg["type"] == "file":
                parts.append(f"[文件:{seg.get('name', '') or '附件'}]")
            else:
                parts.append(seg["text"])
        return "".join(parts).strip()

    def _reset_pending(self):
        """一条消息发出/清空后,重置待发附件挂账(序号计数不回退,避免复用歧义)。"""
        self._pending_attachments = {}

    def _add(self, who, text):
        b = self._bubble(who, text)
        ts = self._time_label(who)
        # 气泡 + 时间戳竖直叠放,再整体左/右对齐
        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(1)
        col.addWidget(b)
        # 时间戳 + 复制按钮并排在气泡下方:用户靠右、皮卡丘靠左。两侧都带复制按钮。
        meta = QHBoxLayout(); meta.setContentsMargins(0, 0, 0, 0); meta.setSpacing(2)
        if who == "你":
            meta.addStretch()
            meta.addWidget(self._copy_button(b))
            meta.addWidget(ts)
        else:
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

    def _img_thumb(self, path):
        """把一张图渲染成气泡里的缩略图 QLabel(限宽,保持比例,黑描边圆角)。"""
        lab = QLabel()
        pm = QPixmap(path)
        if pm.isNull():
            lab.setText("🖼️(图片读不出来了)")
            lab.setStyleSheet(
                f"color:{config.COL_USER_TEXT}; background:transparent;"
                f"font-size:13px; font-family:{FONT};")
            return lab
        if pm.width() > 220:
            pm = pm.scaledToWidth(220, Qt.TransformationMode.SmoothTransformation)
        lab.setPixmap(pm)
        lab.setStyleSheet(
            "QLabel{border:2px solid #2B2B2B; border-radius:10px; background:transparent;}")
        lab.setScaledContents(False)
        return lab

    @staticmethod
    def _file_icon(name):
        """按扩展名挑一个表情图标(纯装饰,缺省用 📄)。"""
        ext = os.path.splitext(name or "")[1].lower()
        return {
            ".pdf": "📕", ".doc": "📘", ".docx": "📘",
            ".xls": "📗", ".xlsx": "📗", ".csv": "📗",
            ".ppt": "📙", ".pptx": "📙",
            ".zip": "🗜️", ".tar": "🗜️", ".gz": "🗜️", ".7z": "🗜️", ".rar": "🗜️",
            ".json": "🧾", ".jsonl": "🧾", ".parquet": "🧾",
            ".md": "📝", ".txt": "📄", ".py": "🐍",
        }.get(ext, "📄")

    def _file_card(self, name):
        """把一个文件渲染成气泡里的卡片(图标 + 文件名,白底黑描边圆角)。
        长文件名按卡片宽度中部省略(…),不撑破气泡也不被硬截。
        """
        card = QLabel()
        card.setWordWrap(False)
        card.setStyleSheet(
            "QLabel{background:#FFFFFF; color:#2B2B2B; border:2px solid #2B2B2B;"
            f"border-radius:10px; padding:8px 12px; font-size:13px; font-family:{FONT};}}")
        card.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        from PyQt6.QtGui import QFontMetrics
        icon = self._file_icon(name)
        # 卡片最大可用文字宽度 ≈ 气泡内宽(280-2*11 边距)再留图标/padding 余量
        avail = 230
        fm = QFontMetrics(card.font())
        elided = fm.elidedText(name, Qt.TextElideMode.ElideMiddle, avail)
        card.setText(f"{icon}  {elided}")
        # 完整名挂 tooltip,鼠标悬停可看全名
        if elided != name:
            card.setToolTip(name)
        return card

    def _add_user_segments(self, segments):
        """渲染【用户】的图文混排气泡:按段顺序竖排文本 QLabel + 缩略图,
        下方一行时间戳 + 复制按钮(复制本条折叠纯文本)。返回容器载体。
        """
        plain = self._segments_plain(segments)
        # 气泡容器(沿用用户气泡的蓝底黑描边圆角风;承载多段子部件)
        bub = QFrame()
        bub.setStyleSheet(
            f"QFrame{{background:{config.COL_USER_BUBBLE};"
            "border:2px solid #2B2B2B; border-radius:16px; border-top-right-radius:5px;}")
        bub.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        bub.setMaximumWidth(280)
        inner = QVBoxLayout(bub)
        inner.setContentsMargins(11, 10, 11, 10); inner.setSpacing(7)
        for seg in segments:
            if seg["type"] == "image":
                inner.addWidget(self._img_thumb(seg["path"]))
            elif seg["type"] == "file":
                inner.addWidget(self._file_card(seg.get("name", "") or "附件"))
            else:
                t = QLabel()
                t.setWordWrap(True)
                t.setTextFormat(Qt.TextFormat.RichText)
                import html as _h
                safe = _h.escape(seg["text"].strip()).replace("\n", "<br>")
                t.setText(f"<div style='line-height:150%;'>{safe}</div>")
                t.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                t.setStyleSheet(
                    f"QLabel{{color:{config.COL_USER_TEXT}; background:transparent;"
                    f"border:none; font-size:14px; font-family:{FONT};}}")
                inner.addWidget(t)
        # 复制按钮取这条消息的折叠纯文本(_copy_button 读 source._raw_text)
        bub._raw_text = plain

        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(1)
        col.addWidget(bub)
        meta = QHBoxLayout(); meta.setContentsMargins(0, 0, 0, 0); meta.setSpacing(2)
        meta.addStretch()
        meta.addWidget(self._copy_button(bub))
        meta.addWidget(self._time_label("你"))
        col.addLayout(meta)
        col.setAlignment(bub, Qt.AlignmentFlag.AlignRight)
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(); row.addLayout(col)
        self.msgs.insertLayout(self.msgs.count() - 1, row)
        QTimer.singleShot(30, self._scroll_bottom)
        return bub

    def _add_thinking(self):
        """加一个【固定尺寸】的"正在想"气泡:转圈动画/读秒都不改变它的尺寸,

        所以不会触发布局重排 → 不会闪。普通回复来了会替换掉它的内容
        (替换时由 _reply 解除定宽,恢复成自适应气泡)。
        转圈用独立的快速定时器驱动(每帧 120ms,流畅);读秒走每秒的 tick 信号。
        """
        # 发言者 ID 固定用 "皮卡"(内部角色标识,写入记忆流水,不随宝可梦变);
        # 气泡显示文字用数据包的"思考中"文案。
        b = self._bubble("皮卡", f"{config.PET_THINKING_TEXT} ⚡")
        # 关键:定死宽,内容怎么变都不重排。宽度取够放最长文案("⠋ 思考文案 120 秒 ⚡"),
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
            f"<div style='line-height:150%;'>{spin} {config.PET_THINKING_TEXT} {sec_str} 秒 ⚡"
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
        self.attach.setEnabled(not on)      # 等回复时也别让用户继续挂附件(下条再发)
        self.send.setVisible(not on)
        self.cancel.setVisible(on)
        if not on:
            self._thinking = None
            self.input.setFocus()

    # ---------- 发送 ----------
    def _send(self):
        raw = self.input.toPlainText()
        # 把输入框内容(可能含「[图片 #n]」「[文件 #n]」占位)切成有序段
        segments = self._parse_segments(raw)
        has_attach = any(s["type"] in ("image", "file") for s in segments)
        # 折叠纯文本表示:用于历史/流水/定时命令识别/降级回应(附件 → 占位文字)
        plain = self._segments_plain(segments)
        if not plain and not has_attach:
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
        self._reset_pending()
        # 渲染用户气泡:有附件走混排(缩略图/文件卡片),纯文本走原气泡(都带复制按钮)
        if has_attach:
            self._add_user_segments(segments)
        else:
            self._add("你", plain)
        # 先看是不是在管理定时任务(列出/删除/新建)。【仅纯文本消息】参与快通道:
        # 带附件的消息一律交给 claude 主对话,避免占位串进时间解析(定时命令几乎不带附件)。
        if not has_attach and self._handle_schedule_command(plain):
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
            # 带附件时额外点明"现在看不了":否则用户看到缩略图却得到拟声词,
            # 会误以为皮卡丘看了图(其实没装 claude,根本没读)。
            if has_attach:
                pika += f"\n\n(*盯着你发的东西* {config.PET_NAME}现在还看不了图片/文件呢,"
                pika += "得先装好 Claude Code 才行哦~)"
            # 用户气泡已渲染,_say_local 只加皮卡丘气泡 + 把这一轮(plain)进历史/流水
            self._say_local(plain, pika)
            return
        self._thinking = self._add_thinking()
        self._busy(True)
        # _pending_user 存折叠纯文本(_reply 写历史/流水用),worker 收完整 segments
        self._pending_user = plain
        self.thinking_started.emit()        # 让桌宠本体进思考态
        recent = self._history[-12:]
        w = ClaudeWorker(plain, history=recent,
                         segments=segments if has_attach else None)
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
                self._say_local(text, f"*掏出小本本* {config.PET_NAME}帮你记着这些啦:\n{lines}\n\n（想删的话说「删除任务 xxxx」)")
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
                text, f"*挠头* 这个时间{config.PET_NAME}没看懂诶… 钟点要在 0~23 之间哦,"
                "换个说法?比如「每天9点提醒我喝水」⚡")
            return True
        return False

    def _save_schedule(self, text, sched, mode):
        task = self._build_task(text, sched, mode)
        created = scheduler.add_task(task)
        if created == "duplicate":
            # 已有等价任务:别重复建,免得到点重复提醒。
            self._say_local(text, f"*翻了翻小本本* 这个{config.PET_NAME}早就记着啦~「{scheduler.describe(task)}」😆")
            return
        if created == "save_failed":
            # 存盘失败:别假报"记下啦",否则用户以为记住了、重启后任务消失。
            self._say_local(text, "*急得冒汗* 呜…小本本写不进去(存盘出错了),这条没记成,等会儿再试试?")
            return
        # 记进历史时带上 id 末4位,让后续"删掉它/改一下"发给 claude 时
        # 它能从历史里看到刚建了哪条任务、对应哪个 id,正确指代。
        pika = (f"*认真记到小本本上* 好嘞!记下啦:\n「{scheduler.describe(task)}」"
                f"（id:{task['id'][-4:]}）\n到点{config.PET_NAME}会帮你搞定的!⚡")
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
        # 去掉开头的称呼(当前宝可梦名,如"皮卡丘,""小火龙、"):用户常这样喊它建提醒
        d = re.sub(rf"^{re.escape(config.PET_NAME)}[,，、\s]*", "", d).strip()
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
        self._history.append((config.PET_NAME,text))
        self._log_convo("pika", text)
        QTimer.singleShot(30, self._scroll_bottom)

    def record_scheduled(self, bubble_text, history_text=None):
        """把一条定时任务/提醒的结果写进聊天窗:显示气泡 + 进多轮历史 + 落记忆流水。

        和 inject_pika_opening 同款"渲染 + 记历史 + 落流水"三件套,区别是允许
        bubble_text(给用户看的措辞)与 history_text(进 self._history 给 claude
        的措辞)不同:history_text 里带【绝对日期+时间】锚点,这样后续多轮对话时
        claude 能知道"这条定时任务是哪天几点跑的",上下文才连贯;不传则与气泡同文。

        历史角色用 '皮卡丘',与 _build_prompt 里其它皮卡丘发言一致。失败不影响 UI。
        """
        bubble_text = (bubble_text or "").strip()
        if not bubble_text:
            return
        self._add("皮卡", bubble_text)
        hist = (history_text or bubble_text).strip()
        self._history.append((config.PET_NAME,hist))
        self._log_convo("pika", hist)
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
        self._history.append((config.PET_NAME,pika_text))
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
        self._history.append((config.PET_NAME,text))
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
            self._history.append((config.PET_NAME,"(没能回应,出错了)"))
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
            self._set_html(self._thinking, f"（{config.PET_NAME}… 不想了~）"); self._thinking = None
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
