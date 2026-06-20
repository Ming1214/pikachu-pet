"""macOS 原生窗口行为助手(用 ctypes 调 AppKit,无需 pyobjc)。

抽成独立模块,供 pet.py 和 chat_window.py 共用,避免循环导入。
"""

import ctypes
import sys

from PyQt6.QtWidgets import QApplication

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


def join_all_spaces(widget):
    """让窗口出现在所有 Space / 全屏 App 之上,且不随焦点消失。

    CanJoinAllSpaces(1<<0) | Stationary(1<<4) | FullScreenAuxiliary(1<<8)
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
            return

        behavior = (1 << 0) | (1 << 4) | (1 << 8)
        msg_set = objc.objc_msgSend
        msg_set.restype = None
        msg_set.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        msg_set(ns_window, objc.sel_registerName(b"setCollectionBehavior:"),
                ctypes.c_ulong(behavior))
    except Exception as exc:
        print(f"[macOS spaces] 设置失败(非致命):{exc}")


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
