"""macOS 原生窗口行为助手(用 ctypes 调 AppKit,无需 pyobjc)。

抽成独立模块,供 pet.py 和 chat_window.py 共用,避免循环导入。
"""

import ctypes
import sys

from PyQt6.QtWidgets import QApplication

# ── 窗口层级档位(NSWindow level)────────────────────────────────────────────
# 固定档,供本体 + 聊天窗共用,避免魔法数散落。期望栈序:普通 App(0) < 聊天窗 < 本体。
# 【红线】本体必须 < 8(NSModalPanelWindowLevel):>=8 会浮到系统模态弹窗(文件选择
# sheet、NSAlert)之上,把皮卡丘盖在系统对话框上、用户没法先关掉它 → 卡死;>=24 还会
# 盖住菜单栏。7 是 <8 区间内的最高安全档,给"本体压住聊天窗"留出空间。
# 注意:WindowStaysOnTopHint 默认映射出的 level 因 Qt/macOS 版本而异(实测可能是 8),
# 所以必须显式 setLevel 把两者钉到这里的固定档,不能依赖默认值。
CHAT_WINDOW_LEVEL = 5   # 聊天窗:floating 之上、稳压普通 App(0)
PET_WINDOW_LEVEL = 7    # 本体:压住聊天窗(5),仍 < 8 不盖系统弹窗/菜单栏

# setup_app_policy 只需生效一次。重复调用会反复调 setActivationPolicy:——在某些
# macOS 版本上会触发 Dock/菜单栏状态重算(图标闪烁),且每次都重写 objc_msgSend
# 的全局 argtypes,纯属多余。用模块级 flag 保证只跑一次。
_app_policy_done = False


def setup_app_policy():
    """Accessory 策略:不显示 Dock 图标 / 菜单栏,但窗口可见可交互。幂等。"""
    global _app_policy_done
    if sys.platform != "darwin" or _app_policy_done:
        return
    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.dylib")
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        ns_app = objc.objc_msgSend(
            objc.objc_getClass(b"NSApplication"),
            objc.sel_registerName(b"sharedApplication"),
        )
        send_int = objc.objc_msgSend
        send_int.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        send_int(ns_app, objc.sel_registerName(b"setActivationPolicy:"), 1)
        _app_policy_done = True   # 成功才置位:失败时下次启动逻辑可再试
    except Exception as exc:
        print(f"[macOS policy] 设置失败(非致命):{exc}")


# NSWindowCollectionBehavior 行为位(值取自 AppKit 官方定义,别凭印象写)。
# 易错点:FullScreenAuxiliary 是 1<<17,不是 1<<8——历史代码写错过,导致它从没真生效。
_COLL_CAN_JOIN_ALL_SPACES = 1 << 0    # 同时出现在所有 Space(本体 + 聊天窗都用)
_COLL_STATIONARY = 1 << 4             # Mission Control/Exposé 时不动位
_COLL_FULLSCREEN_AUX = 1 << 17        # 可浮在全屏 App 的 Space 之上


def _set_collection_behavior(widget, behavior, tag):
    """把某 widget 的 NSWindow.collectionBehavior 设成给定位掩码。失败不致命。

    抽出公共骨架:平台守卫 + winId→NSView→window→setCollectionBehavior:。
    """
    if sys.platform != "darwin":
        return
    app = QApplication.instance()
    if app is None or app.platformName() != "cocoa":
        return  # offscreen/test 平台下 winId 不是 NSView,跳过避免崩溃
    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p

        view = ctypes.c_void_p(int(widget.winId()))
        msg_p = objc.objc_msgSend
        msg_p.restype = ctypes.c_void_p
        msg_p.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        ns_window = msg_p(view, objc.sel_registerName(b"window"))
        if not ns_window:
            # 首次 showEvent 同步触发于 show() 内部,此刻 NSView 可能尚未挂进 NSWindow,
            # [view window] 返回 nil → 这次设不上。调用方(聊天窗)用 singleShot(0) 在
            # 事件循环下一轮 NSWindow 就绪后补设;这里打一行日志便于诊断,不改控制流。
            print(f"[macOS {tag}] NSWindow 未就绪,跳过(将由延迟重试补设)")
            return

        msg_set = objc.objc_msgSend
        msg_set.restype = None
        msg_set.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        msg_set(ns_window, objc.sel_registerName(b"setCollectionBehavior:"),
                ctypes.c_ulong(behavior))
    except Exception as exc:
        print(f"[macOS {tag}] 设置失败(非致命):{exc}")


def join_all_spaces(widget):
    """让窗口【常驻所有 Space】、浮在全屏 App 之上、不随焦点消失(本体 + 聊天窗都用)。

    CanJoinAllSpaces | Stationary | FullScreenAuxiliary。
    用 CanJoinAllSpaces(同时存在于所有桌面)而非 MoveToActiveSpace(仅显示那一刻
    拉到当前桌面、之后切走不跟随):本体和聊天窗都要"你切到哪个桌面它都在",
    所以两者用同一行为。Stationary 与 CanJoinAllSpaces 正交(只管 Mission Control
    时不被卷走),不影响"常驻所有 Space"。
    """
    _set_collection_behavior(
        widget,
        _COLL_CAN_JOIN_ALL_SPACES | _COLL_STATIONARY | _COLL_FULLSCREEN_AUX,
        "spaces",
    )


def set_window_level(widget, level):
    """给窗口设原生 NSWindow level(数值越大越靠上层)。

    背景:皮卡丘本体和聊天窗都用 Qt 的 WindowStaysOnTopHint,Qt 把两者映射到
    同一个 NSWindow level → 同层时谁后 raise_/activate 谁在上。聊天窗 show_near
    每次都 raise_()+activateWindow(),于是总把本体盖住。让本体的 level 比聊天窗
    高一档,就能在系统层面保证本体永远浮在聊天窗之上,与 raise 顺序无关。

    常用 level 参考:NSNormalWindowLevel=0、NSFloatingWindowLevel=3、
    NSModalPanelWindowLevel=8、NSMainMenuWindowLevel=24、NSStatusWindowLevel=25。
    本体传一个比聊天窗大的值即可(本项目用 pet=5, chat=3)。
    【上限红线】传给本体的值【必须 < 8】:>=8 会浮到原生模态弹窗(文件选择 sheet、
    NSAlert 确认框)之上,把皮卡丘盖在系统对话框上、用户没法先关掉它 → 卡死交互。
    更不能 >=24,否则盖住菜单栏。pet=5 落在 floating(3)与 modal(8)之间,既压住
    聊天窗、又乖乖低于所有系统弹窗/菜单栏,是安全档位。
    失败不致命(非 cocoa 平台 / winId 不是 NSView 时静默跳过)。
    """
    if sys.platform != "darwin":
        return
    app = QApplication.instance()
    if app is None or app.platformName() != "cocoa":
        return
    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p

        view = ctypes.c_void_p(int(widget.winId()))
        msg_p = objc.objc_msgSend
        msg_p.restype = ctypes.c_void_p
        msg_p.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        ns_window = msg_p(view, objc.sel_registerName(b"window"))
        if not ns_window:
            return

        msg_set = objc.objc_msgSend
        msg_set.restype = None
        msg_set.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        msg_set(ns_window, objc.sel_registerName(b"setLevel:"),
                ctypes.c_long(int(level)))
    except Exception as exc:
        print(f"[macOS level] 设置失败(非致命):{exc}")


def get_window_level(widget):
    """读窗口当前的 NSWindow level(整数)。读不到 / 非 cocoa 返回 None。

    用途:WindowStaysOnTopHint 在不同 Qt/macOS 版本下映射到的 level 不一定(可能是
    3,也可能是 25 等)。要保证 A 永远压住 B,不能写死数值,而要读出 B 的【真实】
    level、把 A 设到它之上(见 pet._reassert_pet_top)。
    """
    if sys.platform != "darwin":
        return None
    app = QApplication.instance()
    if app is None or app.platformName() != "cocoa":
        return None
    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p

        view = ctypes.c_void_p(int(widget.winId()))
        msg_p = objc.objc_msgSend
        msg_p.restype = ctypes.c_void_p
        msg_p.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        ns_window = msg_p(view, objc.sel_registerName(b"window"))
        if not ns_window:
            return None

        msg_get = objc.objc_msgSend
        msg_get.restype = ctypes.c_long
        msg_get.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        return msg_get(ns_window, objc.sel_registerName(b"level"))
    except Exception as exc:
        print(f"[macOS level get] 读取失败(非致命):{exc}")
        return None
