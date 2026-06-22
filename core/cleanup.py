"""退出清理:把本会话留给系统的"状态"重置干净。

主进程正常退出(aboutToQuit→shutdown)和看门狗(主进程被 kill 后)都调用
这里的 reset_system_state(),所以必须【幂等】:重复调用、目标已不存在,
都不报错、不误伤。

清理的范围(已与用户确认):
  ✓ 杀掉本会话登记过的 claude / MCP 子进程组(.watchdog_pids 里的 pgid)
  ✓ 删运行时垃圾:锁文件、自动生成的 mcp_config.json、tool_events.jsonl、
    原子写残留 *.tmp、pid 登记文件本身
  ✗ 【保留】用户数据:scheduled_tasks.json(定时任务)、.onboarded(引导标记)

为什么登记 pgid 就够杀干净:claude 用 start_new_session=True 起,自成进程组
leader(pgid==pid),MCP 孙进程也在同组,killpg 一次连根拔。
"""

import os
import shutil
import signal
import threading
import time

import config

# 登记文件的进程内写锁:register/deregister 可能被多个 worker 线程并发调用,
# read-modify-write 整个文件要串行,否则会写花/丢行。
_pids_lock = threading.Lock()


def register_pid(pid: int):
    """主进程起一个 claude 子进程后,把它的 pgid(==pid)登记进共享文件。

    看门狗在主进程死后读它来 killpg。失败不致命(大不了那个进程靠主进程自身的
    killpg 兜底;看门狗只是多一层保险)。
    """
    with _pids_lock:
        try:
            with open(config.WATCHDOG_PIDS_PATH, "a", encoding="utf-8") as f:
                f.write(f"{pid}\n")
        except OSError:
            pass


def deregister_pid(pid: int):
    """claude 子进程【正常结束后】把它的 pid 从登记文件移除。

    关键(防误杀):若不移除,该 pid 一直留在文件里;它对应的进程早已结束,
    系统可能把这个 pid 复用给【无关进程】。届时清理时 os.killpg(pid) 就会
    误杀那个无辜进程组。对话越多、留存的死 pid 越多,误杀面越大。
    结束即移除,让文件只保留【当前真正在跑】的 claude 子进程。
    """
    with _pids_lock:
        pgids = _read_registered_pgids()
        pgids.discard(pid)
        try:
            with open(config.WATCHDOG_PIDS_PATH, "w", encoding="utf-8") as f:
                for p in pgids:
                    f.write(f"{p}\n")
        except OSError:
            pass


def _read_registered_pgids():
    """读登记的 pgid 列表(去重)。文件不存在/损坏 → 空列表。"""
    pgids = set()
    try:
        with open(config.WATCHDOG_PIDS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    pgids.add(int(line))
    except OSError:
        pass
    return pgids


def kill_registered_subprocesses():
    """杀掉本会话登记过、且【当前仍存活】的 claude/MCP 进程组。幂等。

    双重防误杀:
      ① 只杀【本会话登记过】的 pgid(register_pid 写入 + 结束时 deregister 移除),
         绝不广撒网杀系统里所有 claude。
      ② 杀之前先 os.killpg(pgid, 0) 探测进程组是否还存在——存在才杀。配合
         deregister 已尽量清掉死 pid,这里再加一道存活探测,最大限度避免 PID
         被复用后误杀无关进程。
    宽限式:先对所有存活组发 SIGTERM,统一 sleep 给它们体面退出的时间,再对仍
    存活的发 SIGKILL(而非每个 TERM 完立刻 KILL,那样 grace 形同虚设)。
    """
    # 持 _pids_lock 读取:否则与同进程内 deregister_pid 的 read-modify-write 并发时,
    # 可能恰好读到它 open("w") 已截断、write 未完成的【空文件】→ 读到空集合 →
    # 漏杀那些其实还在跑的进程组。读完即释放,后续 TERM/sleep/KILL 不必持锁。
    with _pids_lock:
        pgids = _read_registered_pgids()
    if not pgids:
        return

    def _alive(pgid):
        try:
            os.killpg(pgid, 0)   # signal 0:只探测,不真发信号
            return True
        except (ProcessLookupError, OSError):
            return False         # 不存在 / 权限不明 → 当作不该由我们杀

    # ① 对存活组发 SIGTERM(体面退出)
    termed = []
    for pgid in pgids:
        if not _alive(pgid):
            continue
        try:
            os.killpg(pgid, signal.SIGTERM)
            termed.append(pgid)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    if not termed:
        return
    # ② 统一宽限,再对仍存活者 SIGKILL
    time.sleep(1.0)
    for pgid in termed:
        if _alive(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass


def remove_garbage_files():
    """删运行时垃圾文件(不碰用户数据)。幂等:不存在就跳过。"""
    for path in config._cleanup_garbage_paths():
        try:
            os.remove(path)
        except OSError:
            pass
    _remove_chat_upload_dirs()


def _remove_chat_upload_dirs():
    """删聊天窗发图/文件的附件副本目录(整目录,属运行时垃圾,不入库、退出清)。

    上传目录按 pid 隔离命名(.chat_uploads_<pid>)。这里【按 pid 存活探测】删:
      - 本进程自己的目录:直接删。
      - 其它 .chat_uploads_<pid>:仅当该 pid 已不存在(进程已死)才删。
    这样兼顾两个场景:
      ① 看门狗是独立进程(pid 不同),主进程死后它来清——主进程那个 pid 已死,
         其目录会被探测到并删掉,不会因 pid 不匹配而漏清。
      ② 多个桌宠实例并存——另一个仍存活实例的目录(pid 还在)会被保留,绝不误删
         它正让 claude Read 的副本(同 .tmp 用 pid 精确匹配的谨慎做法)。
    用 rmtree + ignore_errors=True 保证幂等。失败不致命(下次启动会重建)。
    """
    import glob
    import re as _re
    # 上传目录现收纳在 DATA_DIR 下(随其它运行时数据)。但【老版本】曾把它写在 BASE_DIR,
    # 迁移到 data/ 后那些旧目录就成了没人扫的孤儿 → 两处都扫(DATA_DIR + 不同的 BASE_DIR)。
    own = os.getpid()
    bases = []
    for attr in ("DATA_DIR", "BASE_DIR"):
        b = getattr(config, attr, "")
        if b and b not in bases:
            bases.append(b)
    if not bases:
        return
    for base in bases:
        for d in glob.glob(os.path.join(base, ".chat_uploads_*")):
            m = _re.search(r"\.chat_uploads_(\d+)$", d)
            if not m:
                continue
            pid = int(m.group(1))
            if pid != own and _pid_alive(pid):
                continue            # 另一个仍存活实例的目录,保留
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass


def _pid_alive(pid: int) -> bool:
    """探测某 pid 是否仍存在(不发真信号)。无法判定时保守当作存活(宁可不删)。"""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True             # 存在但非本用户:存在即视为存活,保守不删
    except OSError:
        return True             # 判定不了 → 保守当存活,绝不误删


def reset_system_state():
    """退出时的总清理入口:杀子进程 + 删垃圾。两边(主进程/看门狗)共用,幂等。"""
    kill_registered_subprocesses()
    remove_garbage_files()
