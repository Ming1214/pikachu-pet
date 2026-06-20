"""看门狗:在主进程死亡(含 kill -9)后兜底清理系统状态。

为什么需要它:主进程被 `kill -9`(SIGKILL)时,它自己的 aboutToQuit/信号处理
【都不会执行】(SIGKILL 不可捕获),残留的 claude/MCP 子进程、锁文件、tmp 全留
在系统里。看门狗是个独立进程,专门盯着主进程,主进程一消失就替它做清理。

存活检测用【管道 EOF】而非轮询 PID:
  - 主进程建一对管道,自己持写端,把读端交给看门狗子进程。
  - 看门狗阻塞在 os.read(读端);只要主进程活着、写端开着,read 一直阻塞。
  - 主进程一旦消失(正常退出/崩溃/被 kill -9),内核关闭其所有 fd → 写端关闭
    → 看门狗的 read 立刻返回 EOF(b"")。比轮询及时,且不受 PID 复用影响。

⚠️ 为什么用 subprocess 而不是 os.fork():
  主进程在调用本模块前已 import PyQt6,Qt 在 import/初始化时会建立 CoreFoundation/
  Cocoa/libdispatch 状态。在 macOS 上 fork 一个带这些状态的进程(即使不 exec)
  可能触发
  「__THE_PROCESS_HAS_FORKED_AND_YOU_CANNOT_USE_THIS_COREFOUNDATION_FUNCTIONALITY」
  类崩溃。改用 subprocess 起一个【全新、干净】的 python 解释器跑本文件的 __main__,
  它从不加载 Qt,彻底绕开 fork-safety 问题。读端 fd 经 pass_fds 传给子进程。
"""

import os
import subprocess
import sys


def _watchdog_loop(read_fd: int):
    """看门狗主体:在 read_fd 上等 EOF,然后清理并退出。"""
    # 脱离父会话:否则终端关闭/Ctrl-C 的信号会把看门狗一起带走,失去兜底意义。
    try:
        os.setsid()
    except OSError:
        pass

    # 阻塞等主进程消失。主进程持有写端;它一死,内核关闭写端 → read 返回 b""。
    # 用循环防御 EINTR(被信号打断的 read 应重试,而不是误当 EOF)。
    while True:
        try:
            data = os.read(read_fd, 1)
        except InterruptedError:
            continue
        except OSError:
            break  # 读端出错,视同主进程已不可达,执行清理
        if not data:
            break  # EOF:主进程已退出
        # 正常情况主进程不会往管道写东西;万一写了,忽略继续等。

    # 主进程已死 → 兜底清理。
    try:
        import cleanup
        cleanup.reset_system_state()
    except Exception:
        # 看门狗清理失败不应留下任何异常痕迹,静默退出
        pass

    os._exit(0)


def spawn_watchdog() -> int | None:
    """在主进程里调用:起一个独立的看门狗子进程,返回主进程应持有的【写端 fd】。

    主进程必须一直持有这个 fd(直到进程结束),不要 close —— close 会让看门狗
    误以为主进程死了而提前清理。返回 None 表示启动失败(降级:无看门狗,
    仍有主进程 shutdown + 下次启动自愈兜底)。
    """
    try:
        read_fd, write_fd = os.pipe()
    except OSError:
        return None

    # 读端要能被子进程继承:清掉它的 CLOEXEC 标志(os.pipe 默认带 CLOEXEC,
    # 会在 exec 时自动关闭)。同时确保写端【保留】CLOEXEC——否则它会泄漏进
    # 看门狗子进程,看门狗自己撑住写端导致永远等不到 EOF。
    try:
        os.set_inheritable(read_fd, True)
    except OSError:
        os.close(read_fd); os.close(write_fd)
        return None

    here = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.Popen(
            [sys.executable, os.path.join(here, "watchdog.py"), str(read_fd)],
            pass_fds=(read_fd,),        # 把读端 fd 传给子进程
            cwd=here,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,     # 脱离会话,终端信号带不走它
            close_fds=True,             # 除 pass_fds 外不继承其它 fd(尤其不继承写端)
        )
    except Exception:
        os.close(read_fd); os.close(write_fd)
        return None

    # 父进程关掉读端(只有子进程需要它);保留写端,生命周期到主进程退出。
    os.close(read_fd)
    return write_fd


if __name__ == "__main__":
    # 子进程入口:argv[1] 是继承来的读端 fd。在它上面等 EOF 后清理。
    # 本脚本在 procs/,cleanup/config 在 core/。把【项目根】及源码子目录加入
    # sys.path,确保 _watchdog_loop 内 `import cleanup`(它再 import config)可达。
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _sub in ("core", "agent", "ui", "web"):
        sys.path.insert(0, os.path.join(_ROOT, _sub))
    sys.path.insert(0, _ROOT)
    try:
        _fd = int(sys.argv[1])
    except (IndexError, ValueError):
        # 无参数时退化为读 stdin EOF(调试用)
        _fd = sys.stdin.fileno()
    _watchdog_loop(_fd)
