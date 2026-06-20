"""本地 Web 控制台:与桌宠同进程的后台 HTTP 线程。

浏览器里实时看皮卡丘状态(动作/思考/各 worker/定时任务/记忆/调用日志/危险操作),
并在线改配置(模型/权限/开关/数值/人设)和增删改记忆。

安全边界:
  - 只绑 127.0.0.1(config.WEB_CONSOLE_HOST),绝不监听公网。
  - 启动随机生成 token 写 .web_console_token(0600);所有 /api/* 校验 ?token= 或
    X-Token 头,不符返回 403。挡住同机其它程序/网页跳转乱改配置。
  - 写配置只认 config_schema 白名单 + coerce 校验;写记忆走 memory 现成持锁读写。

线程模型:ThreadingHTTPServer 每请求一线程。读 pet 内存态走 pet.snapshot_state()
(只读、GIL 安全)。需要碰 Qt 主线程对象的操作(如重设 timer)经 QTimer.singleShot
跳回主线程——本版配置项里 needs_restart=True 的就不热改 timer(标注让用户重启),
故 server 线程不直接碰任何 Qt 对象,最稳。
"""

import hmac
import json
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# /api/* 请求体大小上限(防同机程序发超大 Content-Length 占满内存)。配置/记忆都很小。
_MAX_BODY = 1 * 1024 * 1024
# 日志尾部读的最大字节(大文件不全量进内存,只读末尾这么多再切行)。
_MAX_TAIL_BYTES = 512 * 1024

import config
import config_schema

# 模块级共享给 Handler(handler 实例由 server 构造,无法用闭包传参)
_PET = None          # PikachuPet 实例(读内存态)
_TOKEN = ""          # 本次会话的访问令牌


# ───────────────────────────  启动 / 停止  ───────────────────────────
def start(pet):
    """起 daemon HTTP 线程,返回 server 句柄(供 stop)。失败抛异常由调用方兜底。"""
    global _PET, _TOKEN
    _PET = pet
    _TOKEN = secrets.token_urlsafe(16)
    token_written = _write_token(_TOKEN)

    host = getattr(config, "WEB_CONSOLE_HOST", "127.0.0.1")
    port = getattr(config, "WEB_CONSOLE_PORT", 0)
    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    real_port = server.server_address[1]
    url = f"http://{host}:{real_port}/?token={_TOKEN}"
    t = threading.Thread(target=server.serve_forever, name="web-console", daemon=True)
    t.start()
    print(f"⚡ 皮卡丘控制台已启动:{url}")
    if not token_written:
        # 令牌文件没写成(只读目录/磁盘满):再显式提示一次,免得用户进不去又不知为何。
        print("[web console] 提示:令牌文件写入失败,请用上面这条带 token 的链接访问。")
    return server


def stop(server):
    """停 server(关闭监听 + 退出 serve_forever)。幂等,失败静默。"""
    try:
        server.shutdown()
        server.server_close()
    except Exception:
        pass


def _write_token(token: str) -> bool:
    """把 token 写入文件(0600)。返回是否成功(失败由 start 显式提示用户用终端链接)。"""
    try:
        path = config.WEB_CONSOLE_TOKEN_PATH
        with open(path, "w", encoding="utf-8") as f:
            f.write(token)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except Exception:
        return False


# ───────────────────────────  落盘文件尾部读  ───────────────────────────
def _tail_lines(path: str, n: int) -> list:
    """读 jsonl 文件尾部 n 行,逐行 json.loads(坏行跳过)。文件不存在返回 []。

    只读文件末尾最多 _MAX_TAIL_BYTES 字节再切行,避免对超大日志(如未轮转的
    danger_ops.jsonl)全量 readlines 进内存——高频轮询下会反复分配大内存。
    """
    try:
        if not os.path.exists(path):
            return []
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _MAX_TAIL_BYTES))
            chunk = f.read()
        # 若从中间截断,丢弃第一段不完整行(rfind 第一个换行之后才是完整行起点)
        if size > _MAX_TAIL_BYTES:
            nl = chunk.find(b"\n")
            if nl != -1:
                chunk = chunk[nl + 1:]
        text = chunk.decode("utf-8", "replace")
        out = []
        for ln in text.splitlines()[-n:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out
    except Exception:
        return []


def _count_lines(path: str) -> int:
    try:
        if not os.path.exists(path):
            return 0
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


# ───────────────────────────  各 API 的数据组装  ───────────────────────────
def _build_status() -> dict:
    """实时快照:内存态(来自 pet)+ 落盘态摘要(直接读文件)。"""
    mem = _PET.snapshot_state() if _PET is not None else {}
    # 落盘摘要
    try:
        import scheduler
        tasks = scheduler.load_tasks()
        task_active = sum(1 for t in tasks if not t.get("done"))
    except Exception:
        tasks, task_active = [], 0
    files = {
        "calls": _count_lines(config.CALL_LOG_PATH),
        "danger": _count_lines(config.DANGER_LOG_PATH),
        "convo": _count_lines(config.CONVO_LOG_PATH),
        "guardian_pending": _count_lines(config.CONFIRM_PENDING_PATH),
        "tool_events": _count_lines(config.TOOL_EVENTS_PATH),
    }
    mem_count = today_proactive = 0
    try:
        import memory
        data = memory.load_memory()
        mem_count = len(data.get("memories", []))
        today_proactive = memory.proactive_count_today(data)
    except Exception:
        pass
    last_call = _tail_lines(config.CALL_LOG_PATH, 1)
    return {
        "runtime": mem,
        "tasks_total": len(tasks),
        "tasks_active": task_active,
        "memory_count": mem_count,
        "proactive_today": today_proactive,
        "log_counts": files,
        "last_call": last_call[0] if last_call else None,
        "model": getattr(config, "CLAUDE_MODEL", "") or "(CLI 默认)",
        "permission_mode": getattr(config, "CLAUDE_PERMISSION_MODE", ""),
    }


def _build_config() -> dict:
    """当前可编辑项的值 + schema(前端据此渲染表单),附当前 overrides 集。"""
    ov = config.load_overrides_dict()
    items = []
    for it in config_schema.EDITABLE:
        items.append({
            **it,
            "value": getattr(config, it["key"], None),
            "overridden": it["key"] in ov,   # 是否已被用户覆盖(非默认值)
        })
    return {"items": items}


def _apply_config(payload: dict) -> dict:
    """改配置:逐项 coerce 校验→setattr 热生效→把全量覆盖集落盘。返回结果摘要。

    payload: {"KEY": value, ...}(可一次改多项)。任一项校验失败则整批拒绝(不半改)。
    """
    if not isinstance(payload, dict) or not payload:
        raise ValueError("空请求")
    # 先全部校验(原子:有错就整批拒,不留半套)
    coerced = {}
    for k, v in payload.items():
        coerced[k] = config_schema.coerce(k, v)   # 抛 ValueError 由上层转 400
    # 进程内锁:read-modify-write overrides 全量,防并发 POST 互相覆盖。
    with config.OVERRIDES_LOCK:
        ov = config.load_overrides_dict()
        # 先记下旧值,落盘失败时回滚 setattr(避免热生效了但没持久化 → 重启静默回退)
        original = {k: getattr(config, k, None) for k in coerced}
        restart_keys = []
        for k, v in coerced.items():
            setattr(config, k, v)
            ov[k] = v
            if config_schema.BY_KEY[k].get("needs_restart"):
                restart_keys.append(k)
        ok = config.save_overrides(ov)
        if not ok:
            # 落盘失败 → 回滚内存态,保持"内存与磁盘一致"
            for k, old in original.items():
                setattr(config, k, old)
            raise ValueError("配置写盘失败,改动已撤销(请检查磁盘空间/权限)")
    return {"ok": True, "changed": list(coerced.keys()),
            "needs_restart": restart_keys}


def _reset_config(payload: dict) -> dict:
    """恢复默认:删 overrides 里指定 key(payload={"keys":[...]});keys 为空=清全部。

    注意:reset 只是从 overrides 文件移除该项;【运行中的 config 模块属性仍是改后的值】,
    要彻底回默认需重启(重启时 load_overrides 不再覆盖它)。所以 reset 一律提示重启。
    """
    keys = payload.get("keys") if isinstance(payload, dict) else None
    with config.OVERRIDES_LOCK:
        ov = config.load_overrides_dict()
        if keys:
            for k in keys:
                ov.pop(k, None)
        else:
            ov = {}
        ok = config.save_overrides(ov)
    return {"ok": ok, "reset": keys or "all", "needs_restart": True}


# ───────────────────────────  记忆 CRUD  ───────────────────────────
def _memory_get() -> dict:
    import memory
    data = memory.load_memory()
    return {"memories": data.get("memories", []),
            "types": list(getattr(memory, "MEM_TYPES", ()))}


# 记忆写操作的并发安全:必须在【单个 _file_lock 临界区】内 read-modify-write,
# 不能用 load_memory()+save_memory() 两段独立持锁(中间窗口会被主线程 apply_digest
# 穿插 → 丢数据/游标回退)。_file_lock 现已叠加进程内锁(见 memory._file_lock),
# 与主线程整理真正互斥。这里直接用 memory 的 unlocked 版,自己包一层锁。
def _memory_add(payload: dict) -> dict:
    """手动加一条记忆。payload: {type, text, weight?}。"""
    import time
    import memory
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("记忆内容不能为空")
    mtype = payload.get("type") or "fact"
    if mtype not in getattr(memory, "MEM_TYPES", ("fact",)):
        mtype = "fact"
    try:
        weight = float(payload.get("weight", 1.0))
    except (TypeError, ValueError):
        weight = 1.0
    now = time.time()
    item = {"id": _gen_mem_id(), "type": mtype, "text": text[:500],
            "created_at": now, "last_seen": now, "last_decay_at": now,
            "weight": max(0.1, min(3.0, weight)), "done": False}
    with memory._file_lock(memory.MEMORY_LOCK_PATH):
        data = memory._load_memory_unlocked()
        data.setdefault("memories", []).append(item)
        ok = memory._save_memory_unlocked(data)
        if ok:
            try:
                memory.export_md(data)
            except Exception:
                pass
    return {"ok": ok, "item": item}


def _memory_update(payload: dict) -> dict:
    """改一条记忆。payload: {id, text?, type?, weight?}。"""
    import memory
    mid = payload.get("id")
    if not mid:
        raise ValueError("缺少记忆 id")
    with memory._file_lock(memory.MEMORY_LOCK_PATH):
        data = memory._load_memory_unlocked()
        found = None
        for m in data.get("memories", []):
            if m.get("id") == mid:
                found = m
                break
        if found is None:
            raise ValueError("找不到该记忆")
        if "text" in payload:
            t = (payload.get("text") or "").strip()
            if not t:
                raise ValueError("记忆内容不能为空")
            found["text"] = t[:500]
        if payload.get("type") in getattr(memory, "MEM_TYPES", ()):
            found["type"] = payload["type"]
        if "weight" in payload:
            try:
                found["weight"] = max(0.1, min(3.0, float(payload["weight"])))
            except (TypeError, ValueError):
                pass
        ok = memory._save_memory_unlocked(data)
        if ok:
            try:
                memory.export_md(data)
            except Exception:
                pass
    return {"ok": ok, "item": found}


def _memory_delete(payload: dict) -> dict:
    """删一条记忆。payload: {id}。"""
    import memory
    mid = payload.get("id")
    if not mid:
        raise ValueError("缺少记忆 id")
    with memory._file_lock(memory.MEMORY_LOCK_PATH):
        data = memory._load_memory_unlocked()
        before = len(data.get("memories", []))
        data["memories"] = [m for m in data.get("memories", []) if m.get("id") != mid]
        removed = before - len(data["memories"])
        ok = memory._save_memory_unlocked(data)
        if ok:
            try:
                memory.export_md(data)
            except Exception:
                pass
    return {"ok": ok, "removed": removed}


def _gen_mem_id() -> str:
    """生成记忆 id(仿 memory._new_id,这里不依赖其内部实现)。"""
    return secrets.token_hex(6)


# ───────────────────────────  定时任务  ───────────────────────────
def _tasks_get() -> dict:
    import scheduler
    return {"tasks": scheduler.load_tasks()}


def _task_delete(task_id: str) -> dict:
    import scheduler
    ok = scheduler.remove_task(task_id)
    return {"ok": ok}


# ───────────────────────────  HTTP Handler  ───────────────────────────
class _Handler(BaseHTTPRequestHandler):
    # 关掉默认的 stderr 访问日志(否则桌宠终端被刷屏)
    def log_message(self, fmt, *args):
        pass

    def handle_error(self, request, client_address):
        # 客户端在响应写完前断开(快速刷新/断网)会让 wfile.write 抛 BrokenPipe/
        # ConnectionReset——这是正常现象,静默忽略,别把 traceback 刷到桌宠终端。
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)

    # ---- 工具 ----
    def _check_token(self) -> bool:
        q = parse_qs(urlparse(self.path).query)
        tok = (q.get("token", [""])[0]) or self.headers.get("X-Token", "")
        # compare_digest 防时序侧信道(同机本地攻击);_TOKEN 为空时一律拒。
        return bool(_TOKEN) and hmac.compare_digest(tok, _TOKEN)

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            return {}
        # 上限保护:超大 Content-Length 不分配大内存,只读上限那么多(超出的视为非法)。
        raw = self.rfile.read(min(n, _MAX_BODY))
        try:
            d = json.loads(raw.decode("utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    # ---- GET ----
    def do_GET(self):
        path = urlparse(self.path).path
        # 页面本体:也要 token(防直接访问)。token 不符给一个友好提示页。
        if path == "/" or path == "/index.html":
            if not self._check_token():
                self._send_html(_DENIED_HTML, status=403)
                return
            self._send_html(_PAGE_HTML)
            return
        # API 一律校验 token
        if not self._check_token():
            self._send_json({"error": "forbidden"}, status=403)
            return
        try:
            if path == "/api/status":
                self._send_json(_build_status())
            elif path == "/api/config":
                self._send_json(_build_config())
            elif path == "/api/tasks":
                self._send_json(_tasks_get())
            elif path == "/api/memory":
                self._send_json(_memory_get())
            elif path == "/api/logs/calls":
                self._send_json({"lines": _tail_lines(config.CALL_LOG_PATH, 100)})
            elif path == "/api/logs/danger":
                self._send_json({"lines": _tail_lines(config.DANGER_LOG_PATH, 100)})
            elif path == "/api/logs/convo":
                self._send_json({"lines": _tail_lines(config.CONVO_LOG_PATH, 100)})
            else:
                self._send_json({"error": "not found"}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    # ---- POST (config 改 / config reset / memory 增) ----
    def do_POST(self):
        if not self._check_token():
            self._send_json({"error": "forbidden"}, status=403)
            return
        path = urlparse(self.path).path
        body = self._read_body()
        try:
            if path == "/api/config":
                self._send_json(_apply_config(body))
            elif path == "/api/config/reset":
                self._send_json(_reset_config(body))
            elif path == "/api/memory":
                self._send_json(_memory_add(body))
            else:
                self._send_json({"error": "not found"}, status=404)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    # ---- PUT (memory 改) ----
    def do_PUT(self):
        if not self._check_token():
            self._send_json({"error": "forbidden"}, status=403)
            return
        path = urlparse(self.path).path
        body = self._read_body()
        try:
            if path == "/api/memory":
                self._send_json(_memory_update(body))
            else:
                self._send_json({"error": "not found"}, status=404)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    # ---- DELETE (memory 删 / task 删) ----
    def do_DELETE(self):
        if not self._check_token():
            self._send_json({"error": "forbidden"}, status=403)
            return
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/memory":
                self._send_json(_memory_delete(self._read_body()))
            elif path.startswith("/api/tasks/"):
                from urllib.parse import unquote
                task_id = unquote(path[len("/api/tasks/"):])
                if not task_id:
                    self._send_json({"error": "缺少 task_id"}, status=400)
                    return
                self._send_json(_task_delete(task_id))
            else:
                self._send_json({"error": "not found"}, status=404)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)


# 内嵌前端在 web_console_page.py 同目录字符串(放文件末尾,见下)
from web_console_page import PAGE_HTML as _PAGE_HTML, DENIED_HTML as _DENIED_HTML
