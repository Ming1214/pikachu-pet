"""macOS 原生窗口行为助手(用 ctypes 调 AppKit,无需 pyobjc)。

抽成独立模块,供 pet.py 和 chat_window.py 共用,避免循环导入。
"""

import ctypes
import sys

from PyQt6.QtWidgets import QApplication


def setup_app_policy():
    """Accessory 策略:不显示 Dock 图标 / 菜单栏,但窗口可见可交互。"""
    if sys.platform != "darwin":
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
