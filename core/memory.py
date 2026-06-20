"""皮卡丘的"记忆碎片"系统。

桌宠一直运行,后台每隔一段时间(config.DIGEST_INTERVAL_MS)让 claude 读最近对话、
提炼出有价值的信息,存成长期"记忆"。正常聊天时把记忆注入 prompt——于是皮卡丘
会越来越熟悉主人;发现值得聊的话题时,本体还会主动冒气泡搭话。

本模块只管【存储与读写】,不调 claude(那部分在 pet.py 的后台 worker 里)。
设计严格参照 scheduler.py 的健壮性范式:跨进程 flock + 原子写 + tristate 返回 +
损坏降级,确保多进程/多实例并发与磁盘异常都不丢数据、不崩主流程。

两份文件:
  conversation.jsonl  对话流水(整理的原料),每轮一行 {ts, role, text}
  memory.json         记忆库(机器主存):
    {
      "memories": [
        {"id","type","text","created_at","last_seen","weight","done"}
      ],
      "convo_cursor": <int 已整理到的字节 offset>,
      "last_digest_at": <float>,
      "last_proactive_at": <float>,
      "proactive_day": "YYYYMMDD",   # 当天主动搭话计数所属日期
      "proactive_count": <int>       # 当天已主动搭话次数
    }
  memory.md           上面 memories 的人类可读导出(按 type 分组),每次写库时同步
"""

import json
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime

import config

try:
    import fcntl                       # macOS/Linux 有;Windows 没有(本项目仅 macOS)
except ImportError:                    # pragma: no cover
    fcntl = None

MEMORY_PATH = config.MEMORY_PATH
MEMORY_MD_PATH = config.MEMORY_MD_PATH
CONVO_LOG_PATH = config.CONVO_LOG_PATH
# 记忆库与对话流水各自独立的跨进程锁文件(与 scheduler 的锁互不干扰)。
MEMORY_LOCK_PATH = MEMORY_PATH + ".lock"
CONVO_LOCK_PATH = CONVO_LOG_PATH + ".lock"

# 记忆类型(给 claude 提示用,也用于 md 分组)。
MEM_TYPES = ("fact", "preference", "todo", "routine", "topic")
_TYPE_TITLE = {
    "fact": "事实",
    "preference": "喜好",
    "todo": "未完成的事",
    "routine": "作息/习惯",
    "topic": "聊过的话题",
}


# ───────────────────────────  跨进程锁  ───────────────────────────
# 按 lock_path 复用的进程内锁:同进程内同一文件的临界区串行化(flock 在同进程
# 多线程间不互斥,见 _file_lock 文档)。用 dict 缓存,_registry_lock 保护其创建。
_proc_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def _proc_lock_for(lock_path: str) -> threading.Lock:
    with _registry_lock:
        lk = _proc_locks.get(lock_path)
        if lk is None:
            lk = threading.Lock()
            _proc_locks[lock_path] = lk
        return lk


@contextmanager
def _file_lock(lock_path: str):
    """跨进程排他锁(flock),保护 load→改→save 整段不被另一进程穿插。

    与 scheduler._file_lock 同款实现,但【接受路径参数】,这样记忆库和对话流水
    能各用各的锁。fcntl 不可用时退化为无锁(功能不变,仅失去跨进程保护)。

    关键:整个函数只能有【一处】会执行到的 yield(拿锁失败时单独 yield 后 return,
    拿到锁后只在一个 try/finally 里 yield 一次),否则 with 块体抛异常会撞上第二个
    yield → "generator didn't stop after throw()" RuntimeError 把原异常吞掉。

    【同进程线程互斥】flock 是进程级锁,同一进程内多线程(Qt 主线程的 apply_digest
    ↔ Web 控制台线程的记忆 CRUD)对同一文件再次 flock 不会阻塞 → 仍可能同时进临界区、
    read-modify-write 互相覆盖。所以在 flock 之外【先持一把按 lock_path 区分的进程内
    threading.Lock】:同进程内同一路径的临界区被串行化,跨进程靠 flock,两层叠加才真正
    安全。对所有走 _file_lock 的调用点透明,无需各自改。
    """
    proc_lock = _proc_lock_for(lock_path)
    proc_lock.acquire()
    try:
        if fcntl is None:
            yield
            return
        lf = None
        try:
            lf = open(lock_path, "w")
            fcntl.flock(lf, fcntl.LOCK_EX)
        except Exception:
            if lf is not None:
                try:
                    lf.close()
                except OSError:
                    pass
            yield
            return
        try:
            yield
        finally:
            try:
                fcntl.flock(lf, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                lf.close()
            except OSError:
                pass
    finally:
        proc_lock.release()
        lf.close()


def _atomic_write(path: str, text: str) -> bool:
    """原子写:先写 <path>.<pid>.tmp 再 os.replace 替换。失败返回 False。

    tmp 名带本进程 pid:多实例并发写时各写各的 tmp,不会互相截断、也不会被
    退出清理误删别的实例正在写的 tmp(与 scheduler.save_tasks 一致)。
    """
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except Exception as exc:
        print(f"[memory] 写入失败({os.path.basename(path)}):{exc}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def _new_id() -> str:
    return "m" + str(int(time.time() * 1000))


# ───────────────────────────  对话流水  ───────────────────────────
def append_convo(role: str, text: str) -> None:
    """追加一行对话到 conversation.jsonl(整理的原料)。失败不致命。

    role: "user" / "pika"。text 会去首尾空白;空文本不写。
    追加是 append 模式单行写,自带原子性(一次 write < PIPE_BUF 不会交错);
    超限截断走单独的 _truncate_convo(持锁),不在热路径每次都做。
    """
    text = (text or "").strip()
    if not text:
        return
    line = json.dumps(
        {"ts": time.time(), "role": role, "text": text[:2000]},
        ensure_ascii=False) + "\n"
    try:
        with open(CONVO_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as exc:
        print(f"[memory] 对话流水追加失败:{exc}")


def read_new_convo(cursor: int, max_lines: int | None = None) -> tuple[list[dict], int]:
    """读 cursor(字节 offset)之后的新对话行。返回 (解析出的行列表, 新cursor)。

    二进制按字节读、只消费到最后一个 \\n(半行保护,照搬 pet._check_tool_events):
    若另一进程正写到一半(没有末尾 \\n),不把半行当完整行,留到下次它写完再读。
    cursor 超出当前文件大小(被截断/重建)时从 0 重读。

    max_lines:限制本次最多返回多少【完整行】。超出时只返回【最早的】 max_lines 行,
    且 new_cursor 精确指向这些行的末尾字节(按原始字节长度累加,不靠重新序列化估算)。
    这样剩余行下一轮还能被读到——绝不丢对话。None=不限制。
    """
    try:
        size = os.path.getsize(CONVO_LOG_PATH)
    except OSError:
        return [], cursor
    if cursor > size:           # 文件被截断/重建 → 从头读
        cursor = 0
    if cursor == size:
        return [], cursor
    try:
        with open(CONVO_LOG_PATH, "rb") as f:
            f.seek(cursor)
            chunk = f.read()
    except OSError:
        return [], cursor
    nl = chunk.rfind(b"\n")
    if nl == -1:
        return [], cursor       # 还没有任何完整行
    complete = chunk[:nl + 1]
    # 按原始字节切分成"含 \\n 的整行",这样能精确累加字节长度算游标(中文多字节也准)。
    raw_lines = complete.split(b"\n")
    # split 后最后一个元素是 \\n 之后的空串(complete 以 \\n 结尾),丢弃。
    if raw_lines and raw_lines[-1] == b"":
        raw_lines = raw_lines[:-1]

    rows = []
    consumed_bytes = 0
    for i, rb in enumerate(raw_lines):
        if max_lines is not None and len(rows) >= max_lines:
            break               # 已够 max_lines 行,剩下的留到下一轮
        line_bytes = len(rb) + 1            # +1 = 切掉的那个 \\n
        text = rb.decode("utf-8", "replace").strip()
        consumed_bytes += line_bytes        # 无论能否解析,这一行都算"已消费"
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except Exception:
            continue            # 损坏行跳过,但游标照常前进(不卡在坏行上)
    new_cursor = cursor + consumed_bytes
    return rows, new_cursor


def _truncate_convo(max_lines: int) -> None:
    """对话流水超过 max_lines 时只保留尾部 max_lines 行(防无限增长)。持锁原子写。

    注意:截断会改变字节 offset,使 memory.json 里的 convo_cursor 失效。为此把
    cursor 也重置为新文件大小(认为旧内容已整理过/可弃),在锁内一并完成,避免
    截断后 cursor 仍指向旧大字节数 → read_new_convo 永远读不到东西。
    """
    with _file_lock(CONVO_LOCK_PATH):
        try:
            with open(CONVO_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return
        if len(lines) <= max_lines:
            return
        kept = lines[-max_lines:]
        if _atomic_write(CONVO_LOG_PATH, "".join(kept)):
            # cursor 重置为截断后文件大小:旧内容(含未整理的)被丢弃,认账。
            new_size = sum(len(s.encode("utf-8")) for s in kept)
            with _file_lock(MEMORY_LOCK_PATH):
                data = _load_memory_unlocked()
                data["convo_cursor"] = new_size
                _save_memory_unlocked(data)


def maybe_truncate_convo() -> None:
    """便于 pet 轮询时顺手调用:超限才截断,平时几乎零开销(只数行数)。"""
    try:
        with open(CONVO_LOG_PATH, "r", encoding="utf-8") as f:
            n = sum(1 for _ in f)
    except OSError:
        return
    if n > config.CONVO_LOG_MAX_LINES:
        _truncate_convo(config.CONVO_LOG_MAX_LINES)


# ───────────────────────────  记忆库读写  ───────────────────────────
def _default_memory() -> dict:
    return {
        "memories": [],
        "convo_cursor": 0,
        "last_digest_at": 0.0,
        "last_proactive_at": 0.0,
        "proactive_day": "",
        "proactive_count": 0,
    }


def _load_memory_unlocked() -> dict:
    """读 memory.json(不加锁,内部用)。不存在/损坏 → 默认空结构。

    损坏时【不】静默当空返回后又被 save 覆写清空——返回默认结构但调用方应谨慎;
    这里至少打日志留痕(与 scheduler.load_tasks 一致)。补全缺失字段以兼容旧档。
    """
    if not os.path.exists(MEMORY_PATH):
        return _default_memory()
    try:
        with open(MEMORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"[memory] 记忆文件损坏无法读取(按空处理):{exc}")
        return _default_memory()
    if not isinstance(data, dict):
        return _default_memory()
    base = _default_memory()
    base.update({k: v for k, v in data.items() if k in base})
    if not isinstance(base.get("memories"), list):
        base["memories"] = []
    return base


def _save_memory_unlocked(data: dict) -> bool:
    """写 memory.json(不加锁,内部用)+ 同步导出 memory.md。"""
    ok = _atomic_write(MEMORY_PATH, json.dumps(data, ensure_ascii=False, indent=2))
    if ok:
        export_md(data)          # md 导出失败不影响主存(export_md 内部吞错)
    return ok


def load_memory() -> dict:
    """读记忆库(持锁)。"""
    with _file_lock(MEMORY_LOCK_PATH):
        return _load_memory_unlocked()


def save_memory(data: dict) -> bool:
    """写记忆库(持锁)。"""
    with _file_lock(MEMORY_LOCK_PATH):
        return _save_memory_unlocked(data)


# ───────────────────────────  导出 md  ───────────────────────────
def export_md(data: dict) -> None:
    """把 memories 按 type 分组写成 memory.md(人类可读)。失败吞掉不致命。"""
    try:
        mems = data.get("memories", [])
        lines = ["# 皮卡丘的记忆小本本 ⚡\n",
                 f"_(自动生成,共 {len(mems)} 条;最近整理 "
                 f"{_fmt_ts(data.get('last_digest_at'))})_\n"]
        for typ in MEM_TYPES:
            group = [m for m in mems if m.get("type") == typ]
            if not group:
                continue
            lines.append(f"\n## {_TYPE_TITLE.get(typ, typ)}\n")
            # 按权重降序,重要的在前
            for m in sorted(group, key=lambda x: x.get("weight", 0), reverse=True):
                mark = ""
                if typ == "todo":
                    mark = "✅ " if m.get("done") else "⬜ "
                lines.append(f"- {mark}{m.get('text', '')}")
        # 不属于已知 type 的兜底分组
        others = [m for m in mems if m.get("type") not in MEM_TYPES]
        if others:
            lines.append("\n## 其他\n")
            for m in others:
                lines.append(f"- {m.get('text', '')}")
        _atomic_write(MEMORY_MD_PATH, "\n".join(lines) + "\n")
    except Exception as exc:
        print(f"[memory] 导出 md 失败(不影响主存):{exc}")


def _fmt_ts(ts) -> str:
    try:
        if not ts:
            return "还没整理过"
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


# ───────────────────────────  整理结果合并  ───────────────────────────
def _norm(text: str) -> str:
    """归一化文本用于近似去重:去空白、去标点、转小写。"""
    return re.sub(r"[\s，。、!?！？.,~…·:：;；]+", "", (text or "")).lower()


def apply_digest(updates: dict, new_cursor: int) -> bool:
    """把 claude 整理出的结果合并进记忆库,推进游标,落盘 + 导出 md。锁内一次完成。

    updates 结构(全部可选,容错):
      {
        "add":  [{"type","text"}, ...],        # 新增记忆
        "update": [{"text", ...}],             # 语义更新(按近似去重命中则刷新权重/文本)
        "done": ["<todo 文本或 id 片段>", ...]  # 标记完成的未完成事项
      }
    去重:新增前按 _norm(text) 与现有记忆比对,命中则视为"再次提及"→ 刷新
    last_seen、权重回升,不重复添加。返回 True 仅当成功落盘。
    """
    now = time.time()
    with _file_lock(MEMORY_LOCK_PATH):
        data = _load_memory_unlocked()
        mems = data["memories"]
        index = {_norm(m.get("text", "")): m for m in mems}

        # 标记完成:按 text/id 近似匹配 type=todo 的项
        for frag in (updates.get("done") or []):
            key = _norm(str(frag))
            for m in mems:
                if m.get("type") != "todo":
                    continue
                if (key and key in _norm(m.get("text", ""))) or \
                        str(frag) == m.get("id"):
                    m["done"] = True
                    m["last_seen"] = now
                    break

        # 新增 / 再次提及
        for item in (updates.get("add") or []):
            text = (item.get("text") or "").strip()
            if not text:
                continue
            typ = item.get("type") if item.get("type") in MEM_TYPES else "fact"
            nk = _norm(text)
            if nk in index:
                # 已存在等价记忆 → 再次提及:回升权重、刷新时间,不重复加
                ex = index[nk]
                ex["last_seen"] = now
                ex["weight"] = min(3.0, ex.get("weight", 1.0) + 0.5)
                # todo 被重新提及通常意味着还没做完,保持 done 原状(不擅自翻转)
                continue
            mem = {
                "id": _new_id(),
                "type": typ,
                "text": text[:300],
                "created_at": now,
                "last_seen": now,
                "last_decay_at": now,      # 衰减基准:从创建起算,避免首轮就被衰减
                "weight": 1.0,
                "done": False if typ == "todo" else None,
            }
            mems.append(mem)
            index[nk] = mem

        data["convo_cursor"] = new_cursor
        data["last_digest_at"] = now
        purge_memories(data)          # 老化 + 超量淘汰(就地修改 data)
        return _save_memory_unlocked(data)


def purge_memories(data: dict) -> None:
    """老化衰减 + 超量淘汰(就地修改 data["memories"])。

    - 衰减:按【距上次衰减】的天数 weight *= DECAY^天数。关键——必须以 last_decay_at
      为基准、衰减后更新 last_decay_at,而不是每次都按 (now - last_seen) 重算:否则
      digest 高频运行时(活跃用户每 30min 一次,一天几十次)同一段年龄会被反复乘进
      已经衰减过的 weight 上 → 复利式暴跌,记忆几小时就消失,完全偏离"每天 0.92"。
      被再次提及的记忆 last_seen 会更新,但衰减只看 last_decay_at,二者互不干扰。
    - 完成已久的 todo(done=True 且很久没动)优先淘汰。
    - 超过 MEMORY_MAX_ITEMS:按 weight 升序丢最不重要的,直到不超量。
    """
    now = time.time()
    mems = data.get("memories", [])
    decay = config.MEMORY_DECAY_PER_DAY
    for m in mems:
        # 基准:上次衰减时刻;旧档无此字段则用 created_at(首次按"自创建以来"衰减一次)
        base = m.get("last_decay_at", m.get("created_at", now))
        elapsed_days = max(0.0, (now - base) / 86400.0)
        if elapsed_days >= 1.0:
            m["weight"] = round(m.get("weight", 1.0) * (decay ** elapsed_days), 4)
            m["last_decay_at"] = now      # 推进基准,下次只衰减"从现在起"的新增天数
    # 已完成且超过 1 天没动的 todo:权重大幅降低,让它先被淘汰
    for m in mems:
        if m.get("type") == "todo" and m.get("done") and \
                (now - m.get("last_seen", now)) > 86400:
            m["weight"] = min(m.get("weight", 1.0), 0.1)
    # 超量 → 按 weight 升序淘汰
    if len(mems) > config.MEMORY_MAX_ITEMS:
        mems.sort(key=lambda x: x.get("weight", 0.0), reverse=True)
        del mems[config.MEMORY_MAX_ITEMS:]
    data["memories"] = mems


# ───────────────────────────  注入聊天的记忆摘要  ───────────────────────────
def recent_memory_summary(max_items: int | None = None) -> str:
    """取高权重记忆拼成一段文本,注入正常聊天 prompt(让皮卡丘"记得"主人)。

    返回空串表示没有可用记忆(调用方据此不注入)。只取高权重前 N 条,保持简短。
    未完成的 todo 单独点出,便于皮卡丘自然关心进度。
    """
    if max_items is None:
        max_items = config.MEMORY_INJECT_TOP_N
    try:
        data = load_memory()
    except Exception:
        return ""
    mems = data.get("memories", [])
    if not mems:
        return ""
    top = sorted(mems, key=lambda x: x.get("weight", 0.0), reverse=True)[:max_items]
    if not top:
        return ""
    lines = []
    for m in top:
        txt = m.get("text", "").strip()
        if not txt:
            continue
        if m.get("type") == "todo" and not m.get("done"):
            lines.append(f"- (他还没做完){txt}")
        else:
            lines.append(f"- {txt}")
    if not lines:
        return ""
    return "【关于主人,你已经记得这些事(自然地体现在对话里,别生硬罗列)】\n" + \
        "\n".join(lines)


# ───────────────────────────  主动搭话频率状态  ───────────────────────────
def record_proactive() -> None:
    """记一次主动搭话:更新 last_proactive_at 与当天计数。持锁。"""
    now = time.time()
    today = datetime.now().strftime("%Y%m%d")
    with _file_lock(MEMORY_LOCK_PATH):
        data = _load_memory_unlocked()
        data["last_proactive_at"] = now
        if data.get("proactive_day") != today:
            data["proactive_day"] = today
            data["proactive_count"] = 1
        else:
            data["proactive_count"] = int(data.get("proactive_count", 0)) + 1
        _save_memory_unlocked(data)


def proactive_count_today(data: dict | None = None) -> int:
    """当天已主动搭话次数(跨过零点自动归零)。"""
    if data is None:
        data = load_memory()
    today = datetime.now().strftime("%Y%m%d")
    if data.get("proactive_day") != today:
        return 0
    return int(data.get("proactive_count", 0))
