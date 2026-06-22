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

# 记忆按宝可梦隔离:文件路径不再在模块加载时固化,而是【每次读写时】按当前
# config.ACTIVE_POKEMON 动态解析(见下面的解析函数)。这样控制台在线切换宝可梦后,
# 记忆立刻读写到对应文件,无需重启。锁路径同步随之而变(每只一套独立锁)。
#
# 兼容:历史上外部代码可能 `from memory import MEMORY_PATH`/`memory.MEMORY_LOCK_PATH`。
# web_console.py 就用了 memory.MEMORY_LOCK_PATH。为不破坏这些引用,保留同名【模块属性】,
# 但通过 __getattr__ 动态返回当前宝可梦的路径(PEP 562 模块级 __getattr__),而非静态固化。


def _mem_path() -> str:
    """当前宝可梦的记忆库 json 绝对路径(运行时解析)。"""
    return config.memory_paths()[0]


def _md_path() -> str:
    """当前宝可梦的 memory.md 绝对路径。"""
    return config.memory_paths()[1]


def _convo_path() -> str:
    """当前宝可梦的对话流水 jsonl 绝对路径。"""
    return config.memory_paths()[2]


def _mem_lock_path() -> str:
    """当前宝可梦记忆库的跨进程锁文件路径。"""
    return _mem_path() + ".lock"


def _convo_lock_path() -> str:
    """当前宝可梦对话流水的跨进程锁文件路径。"""
    return _convo_path() + ".lock"


# PEP 562:模块级 __getattr__ 让 memory.MEMORY_PATH 等老属性仍可用,且【动态】反映
# 当前宝可梦(取代旧的模块加载时固化)。只兜底这几个历史名,其余未知属性照常报错。
_DYNAMIC_ATTRS = {
    "MEMORY_PATH": _mem_path,
    "MEMORY_MD_PATH": _md_path,
    "CONVO_LOG_PATH": _convo_path,
    "MEMORY_LOCK_PATH": _mem_lock_path,
    "CONVO_LOCK_PATH": _convo_lock_path,
}


def __getattr__(name):
    fn = _DYNAMIC_ATTRS.get(name)
    if fn is not None:
        return fn()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
        with open(_convo_path(), "a", encoding="utf-8") as f:
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
        size = os.path.getsize(_convo_path())
    except OSError:
        return [], cursor
    if cursor > size:           # 文件被截断/重建 → 从头读
        cursor = 0
    if cursor == size:
        return [], cursor
    try:
        with open(_convo_path(), "rb") as f:
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
    # 进锁前快照路径:截断的对话流水与随后重置 cursor 的记忆库必须同属一只宝可梦,
    # 否则临界区内 ACTIVE_POKEMON 被切走会"截 A 的对话却把 B 的 cursor 清零"。
    convo_path = _convo_path()
    mem_path = _mem_path(); md_path = _md_path()
    with _file_lock(convo_path + ".lock"):
        try:
            with open(convo_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return
        if len(lines) <= max_lines:
            return
        kept = lines[-max_lines:]
        if _atomic_write(convo_path, "".join(kept)):
            # cursor 重置为截断后文件大小:旧内容(含未整理的)被丢弃,认账。
            new_size = sum(len(s.encode("utf-8")) for s in kept)
            with _file_lock(mem_path + ".lock"):
                data = _load_memory_unlocked(mem_path)
                data["convo_cursor"] = new_size
                _save_memory_unlocked(data, path=mem_path, md_path=md_path)


def maybe_truncate_convo() -> None:
    """便于 pet 轮询时顺手调用:超限才截断,平时几乎零开销(只数行数)。"""
    try:
        with open(_convo_path(), "r", encoding="utf-8") as f:
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


def _load_memory_unlocked(path: str | None = None) -> dict:
    """读记忆库 json(不加锁,内部用)。不存在/损坏 → 默认空结构。

    path 省略时读【当前宝可梦】的库;显式传入时读指定库(供共享读合并别的宝可梦)。
    损坏时【不】静默当空返回后又被 save 覆写清空——返回默认结构但调用方应谨慎;
    这里至少打日志留痕(与 scheduler.load_tasks 一致)。补全缺失字段以兼容旧档。
    """
    if path is None:
        path = _mem_path()
    if not os.path.exists(path):
        return _default_memory()
    try:
        with open(path, encoding="utf-8") as f:
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


def _save_memory_unlocked(data: dict, path: str = None, md_path: str = None) -> bool:
    """写 memory.json(不加锁,内部用)+ 同步导出 memory.md。

    path/md_path 省略时写【当前宝可梦】的库;显式传入时写指定库——供调用方在【进入
    临界区前快照了宝可梦】的场景使用,避免临界区内 ACTIVE_POKEMON 被并发切换导致
    "拿 A 的锁却写 B 的文件"(锁路径与文件路径分裂)。
    """
    if path is None:
        path = _mem_path()
    ok = _atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))
    if ok:
        export_md(data, path=md_path)   # md 导出失败不影响主存(export_md 内部吞错)
    return ok


def load_memory() -> dict:
    """读记忆库(持锁)。"""
    with _file_lock(_mem_lock_path()):
        return _load_memory_unlocked()


def save_memory(data: dict) -> bool:
    """写记忆库(持锁)。"""
    with _file_lock(_mem_lock_path()):
        return _save_memory_unlocked(data)


# ───────────────────────────  导出 md  ───────────────────────────
def export_md(data: dict, path: str = None) -> None:
    """把 memories 按 type 分组写成 memory.md(人类可读)。失败吞掉不致命。

    path 省略时写【当前宝可梦】的 md;显式传入时写指定路径(与 _save_memory_unlocked
    的快照路径配套,避免锁/文件分裂)。
    """
    try:
        mems = data.get("memories", [])
        # 标题用当前宝可梦名(每只一份 md,各记各的)。取名失败兜底"宠物"。
        try:
            pet = config.PET_NAME
        except Exception:
            pet = "宠物"
        lines = [f"# {pet}的记忆小本本 ⚡\n",
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
        _atomic_write(path or _md_path(), "\n".join(lines) + "\n")
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
        "add":  [{"type","text","importance":1|2|3}, ...],  # 新增记忆;importance 定初始权重
        "update": [{"match","text"}, ...],     # 语义更新:match 关键词模糊命中已有记忆,替换其 text
        "done": ["<todo 文本或 id 片段>", ...]  # 标记完成的未完成事项
      }
    去重:新增前按 _norm(text) 与现有记忆比对,命中则视为"再次提及"→ 刷新
    last_seen、权重回升,不重复添加。importance(1/2/3)只用来定【新增条目的初始
    权重】({1:0.7,2:1.0,3:1.5}),【不存进记忆记录】——旧档零迁移。
    update 在 add 之后执行:确保新增项已进 index,update 重建 index key 不会和 add 打架。
    返回 True 仅当成功落盘。
    """
    now = time.time()
    # 进临界区前快照(锁/json/md)三条路径:整段 read-modify-write 都用这组快照,
    # 避免临界区内 ACTIVE_POKEMON 被控制台另一线程并发切换 → "拿 A 的锁却写 B 的文件"
    # (锁路径与文件路径分裂)。md 路径与 json 配套,一并快照传给 _save_memory_unlocked。
    mem_path = _mem_path(); md_path = _md_path(); lock_path = mem_path + ".lock"
    with _file_lock(lock_path):
        data = _load_memory_unlocked(mem_path)
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
            # importance → 初始权重:3=重要(截止/强调)给 1.5,2=默认 1.0,1=背景 0.7。
            # 重要的事起点更高 → 衰减再久也比普通记忆活得长(解决"几天前提的要紧事被忘")。
            imp = item.get("importance", 2)
            try:
                imp = int(imp)
            except (TypeError, ValueError):
                imp = 2
            init_weight = {1: 0.7, 2: 1.0, 3: 1.5}.get(imp, 1.0)
            mem = {
                "id": _new_id(),
                "type": typ,
                "text": text[:300],
                "created_at": now,
                "last_seen": now,
                "last_decay_at": now,      # 衰减基准:从创建起算,避免首轮就被衰减
                "weight": init_weight,
                "done": False if typ == "todo" else None,
            }
            mems.append(mem)
            index[nk] = mem

        # 语义更新:用 match 关键词模糊命中已有记忆,替换 text、刷新时间、小幅回升权重。
        # 放在 add 之后:此时 index 已含新增项;命中后重建 index key(旧 key 删、新 key 入),
        # 避免后续按旧文本去重时找不到。每个 update 只改第一条命中(避免一次改花多条)。
        for item in (updates.get("update") or []):
            match_frag = _norm(str(item.get("match") or ""))
            new_text = (item.get("text") or "").strip()
            if not match_frag or not new_text:
                continue
            for m in mems:
                if match_frag in _norm(m.get("text", "")):
                    old_nk = _norm(m.get("text", ""))
                    m["text"] = new_text[:300]
                    m["last_seen"] = now
                    m["weight"] = min(3.0, m.get("weight", 1.0) + 0.3)
                    if old_nk in index:
                        del index[old_nk]
                    index[_norm(new_text)] = m
                    break

        data["convo_cursor"] = new_cursor
        data["last_digest_at"] = now
        purge_memories(data)          # 老化 + 超量淘汰(就地修改 data)
        return _save_memory_unlocked(data, path=mem_path, md_path=md_path)


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


# ───────────────────────────  注入用记忆收集(共享 / 隔离)  ───────────────────────────
def _load_memory_file(path: str) -> dict:
    """读指定路径的记忆库 json(持该文件自己的锁)。不存在/损坏 → 默认空结构。

    用于【共享读】合并别的宝可梦的记忆库:每个文件用自己的锁,避免读 A 的库时
    误用 B 的锁。复用 _load_memory_unlocked 的容错(它内部按传入路径读)。
    """
    with _file_lock(path + ".lock"):
        return _load_memory_unlocked(path)


def _collect_injection_memories() -> list[dict]:
    """收集要注入聊天/搭话的记忆条目列表,按共享开关决定范围。

    - MEMORY_SHARED_ACROSS_POKEMON=True:合并【所有宝可梦】的记忆库。同一件事被多只
      记过(_norm 等价)只保留权重最高的那条,避免重复注入。
    - False:只读【当前宝可梦】自己的库。
    任何异常都降级为"只读当前库",绝不让共享逻辑的问题挡住聊天。
    """
    try:
        shared = bool(getattr(config, "MEMORY_SHARED_ACROSS_POKEMON", True))
    except Exception:
        shared = True
    if not shared:
        try:
            return load_memory().get("memories", []) or []
        except Exception:
            return []
    # 共享:合并所有 memory*.json。按 _norm(text) 去重,留 weight 最高的一条。
    merged: dict[str, dict] = {}
    try:
        paths = config.all_memory_json_paths()
    except Exception:
        paths = []
    # 兜底:至少包含当前库(若 all_memory_json_paths 出错或为空)
    if not paths:
        try:
            return load_memory().get("memories", []) or []
        except Exception:
            return []
    for path in paths:
        try:
            data = _load_memory_file(path)
        except Exception:
            continue
        for m in data.get("memories", []) or []:
            key = _norm(m.get("text", ""))
            if not key:
                continue
            cur = merged.get(key)
            if cur is None or m.get("weight", 0.0) > cur.get("weight", 0.0):
                merged[key] = m
    return list(merged.values())


# ───────────────────────────  注入聊天的记忆摘要  ───────────────────────────
def recent_memory_summary(max_items: int | None = None) -> str:
    """取高权重记忆拼成一段文本,注入聊天 / 主动搭话 prompt(让皮卡丘"记得"主人)。

    返回空串表示没有可用记忆(调用方据此不注入)。只取高权重前 N 条,保持简短。
    设计:
      - 按 type 分组成【带标签的自然语句】(基本情况/喜好/作息/没做完的事/聊过的话题),
        而不是扁平的"- xxx"罗列——claude 读到结构化分组,更容易自然地把记忆织进对话,
        而非生硬念清单。
      - 未完成的 todo 追加【多久前提过】的时间信号(今天/昨天/约 N 天前),由 last_seen
        算。这个信号对【主动搭话】尤其关键(久搁的事才值得关心进度);它只在【输出文本】
        里,不进 stored text,故不影响 _norm 去重。
    """
    if max_items is None:
        max_items = config.MEMORY_INJECT_TOP_N
    # 按共享开关收集记忆:共享=合并所有宝可梦的库,隔离=只当前这只(内部已容错)。
    mems = _collect_injection_memories()
    if not mems:
        return ""
    top = sorted(mems, key=lambda x: x.get("weight", 0.0), reverse=True)[:max_items]
    if not top:
        return ""

    now = time.time()
    sections: dict[str, list[str]] = {
        "fact": [], "preference": [], "routine": [], "todo": [], "topic": []}
    for m in top:
        typ = m.get("type", "fact")
        txt = (m.get("text") or "").strip()
        if not txt:
            continue
        if typ == "todo" and not m.get("done"):
            days_ago = max(0.0, (now - m.get("last_seen", now)) / 86400.0)
            if days_ago < 1:
                age = "今天提到过"
            elif days_ago < 2:
                age = "昨天提到过"
            else:
                age = f"约 {int(days_ago)} 天前提到过"
            sections["todo"].append(f"{txt}({age},还没完成)")
        elif typ in sections:
            sections[typ].append(txt)
        else:
            sections["fact"].append(txt)   # 未知 type 兜底归入基本情况

    parts = []
    if sections["fact"]:
        parts.append("主人的基本情况:" + ";".join(sections["fact"]))
    if sections["preference"]:
        parts.append("主人的喜好:" + ";".join(sections["preference"]))
    if sections["routine"]:
        parts.append("主人的作息习惯:" + ";".join(sections["routine"]))
    if sections["todo"]:
        parts.append("主人还没做完的事:" + ";".join(sections["todo"]))
    if sections["topic"]:
        parts.append("聊过、可以延续的话题:" + ";".join(sections["topic"]))
    if not parts:
        return ""
    body = "\n".join(f"- {p}" for p in parts)
    try:
        pet = config.PET_NAME
    except Exception:
        pet = "我"
    return f"【{pet}记得的关于主人的事(聊天时自然地用上,别当清单念出来)】\n" + body


# ───────────────────────────  主动搭话频率状态  ───────────────────────────
def record_proactive() -> None:
    """记一次主动搭话:更新 last_proactive_at 与当天计数。持锁。"""
    now = time.time()
    today = datetime.now().strftime("%Y%m%d")
    # 同 apply_digest:进锁前快照路径,防临界区内 ACTIVE_POKEMON 被切走导致锁/文件分裂。
    mem_path = _mem_path(); md_path = _md_path(); lock_path = mem_path + ".lock"
    with _file_lock(lock_path):
        data = _load_memory_unlocked(mem_path)
        data["last_proactive_at"] = now
        if data.get("proactive_day") != today:
            data["proactive_day"] = today
            data["proactive_count"] = 1
        else:
            data["proactive_count"] = int(data.get("proactive_count", 0)) + 1
        _save_memory_unlocked(data, path=mem_path, md_path=md_path)


def proactive_count_today(data: dict | None = None) -> int:
    """当天已主动搭话次数(跨过零点自动归零)。"""
    if data is None:
        data = load_memory()
    today = datetime.now().strftime("%Y%m%d")
    if data.get("proactive_day") != today:
        return 0
    return int(data.get("proactive_count", 0))
