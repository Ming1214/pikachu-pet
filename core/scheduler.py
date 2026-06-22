"""皮卡丘的定时任务系统。

桌宠是一直运行的进程,可以用定时器管理"到点干活"。
任务存到本地 JSON,重启不丢。

支持的时间表达(中文为主):
  - 每天 9 点 / 每天早上 9 点 / 每天 21:30          → 每天定点
  - 5 分钟后 / 半小时后 / 1 小时后 / 30 秒后        → 一次性延迟
  - 每隔 2 小时 / 每 30 分钟                          → 周期重复
  - 每周一 9 点 / 每周三 18:00                        → 每周定点

任务结构(dict):
  {
    "id": "t1718...",          # 唯一 id
    "kind": "daily"|"once"|"interval"|"weekly",
    "desc": "整理截图",         # 给用户看的描述
    "prompt": "把桌面截图...",   # 到点发给 claude 的指令
    "enabled": True,
    # daily/weekly: "hour", "minute" (weekly 还有 "weekday" 0=周一)
    # once: "fire_at" (epoch 秒)
    # interval: "every_sec", "next_at" (epoch 秒)
  }
"""

import json
import os
import re
import time
from contextlib import contextmanager
from datetime import date, datetime

import config

try:
    import fcntl                       # macOS/Linux 有;Windows 没有(本项目仅 macOS)
except ImportError:                    # pragma: no cover
    fcntl = None

TASKS_PATH = os.path.join(config.DATA_DIR, "scheduled_tasks.json")
LOCK_PATH = TASKS_PATH + ".lock"       # 跨进程排他锁文件(flock 用)

_WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
_CN_NUM = {"零": 0, "两": 2, "半": 0}  # 特殊;普通数字走正则

# 中文数字 → 阿拉伯数字(支持 0~99,够定时场景:几点/几分/几小时后)
_CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn2num(s: str) -> int | None:
    """把一段纯中文数字转成 int(支持 十/二十/二十三/十五 等 0~99)。失败返回 None。"""
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if "十" not in s:
        # 纯个位数字串,如 "三" "九";多位如 "二三" 不规范,取首位即可
        return _CN_DIGIT.get(s[0]) if s[0] in _CN_DIGIT else None
    # 含"十":如 十=10, 十五=15, 二十=20, 二十三=23
    left, _, right = s.partition("十")
    tens = _CN_DIGIT.get(left, 1) if left else 1   # "十五"→十位是1
    ones = _CN_DIGIT.get(right, 0) if right else 0
    return tens * 10 + ones


def _normalize_cn_numbers(text: str) -> str:
    """把句子里成段的中文数字替换成阿拉伯数字,让后续正则(只认 \\d)能命中。

    例:"三分钟后" → "3分钟后","每天九点半" → "每天9点半","二十分钟" → "20分钟"。
    """
    def repl(m):
        n = _cn2num(m.group(0))
        return str(n) if n is not None else m.group(0)
    # 匹配连续的中文数字片段(含"十"),但跳过紧跟"周/星期/礼拜"后的星期几
    # (如"每周三""礼拜三"的"三"是星期,不能转成 3),用负向后顾排除。
    # "期/拜"分别兜住"星期X""礼拜X"的前一字。
    return re.sub(r"(?<![周期拜])[零〇一二两三四五六七八九十]+", repl, text)


# ───────────────────────────  跨进程锁  ───────────────────────────
@contextmanager
def _file_lock():
    """跨进程排他锁(flock),保护 load→修改→save 这一整段不被另一进程穿插。

    为什么必须有:主进程(pet.py 每 20s 轮询)与 MCP 子进程(pika_mcp.py 建/删任务)
    都做「load_tasks()→改→save_tasks()」。os.replace 只保证单次写原子,挡不住
    read-modify-write 竞态——两边各读到旧快照、各改各的、后写者覆盖先写者,
    会导致 MCP 刚建的任务被 pet 的 after_fire/purge 静默覆盖丢失。
    flock 让这段序列化:同一时刻只有一个进程能进入,另一个阻塞等待。

    fcntl 不可用(理论上的非 Unix)时退化为无锁,功能不变(仅失去跨进程保护)。
    """
    if fcntl is None:
        yield
        return
    # 关键:整个函数体只能有【一处】会执行到的 yield。若像旧版那样在 try 里 yield、
    # except 里再 yield,当 with 块体内部抛异常时,异常会被 throw 回 try 的 yield 处、
    # 被 except 捕获、再撞上第二个 yield → Python 抛 "generator didn't stop after
    # throw()" 的 RuntimeError,把【原始异常吞掉换成 RuntimeError】,且向上传到无
    # try/except 的调度循环 → 每 20s 崩一次。故拆成:先尝试拿锁(失败则降级无锁
    # 单独 yield 后 return),拿到锁后只在一个 try/finally 里 yield 一次。
    lf = None
    try:
        lf = open(LOCK_PATH, "w")
        fcntl.flock(lf, fcntl.LOCK_EX)
    except Exception:
        # 拿锁失败(磁盘/权限/文件系统不支持 flock)也不能让任务功能崩溃:
        # 退化成无锁继续(极端情况,失去跨进程保护但功能可用)。
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
        lf.close()


# ───────────────────────────  存储  ───────────────────────────
def load_tasks() -> list[dict]:
    if not os.path.exists(TASKS_PATH):
        return []
    try:
        with open(TASKS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        # 文件损坏时静默返回 [] 会让下一次 save 把空列表写回去 → 永久清空所有任务。
        # 至少打个日志留痕,方便排查"任务怎么突然没了"。
        print(f"[scheduler] 任务文件损坏无法读取(将按空处理):{exc}")
        return []


def save_tasks(tasks: list[dict]) -> bool:
    """原子写:先写临时文件再 os.replace 替换。

    主进程(pet.py 轮询)与 MCP 子进程(pika_mcp.py)会同时读写本文件,
    直接覆写存在「读到半截 JSON」和「并发写互相截断」的风险。
    os.replace 在同一目录内是原子操作,读方要么看到旧文件、要么看到新文件,
    不会读到中间态;并发写也只会整体覆盖,不会写出损坏文件。

    Returns:
        True  = 成功落盘。
        False = 写盘失败(磁盘满/权限等)。调用方(after_fire)据此知道
                本次状态变更没持久化,once 的 done 标记可能没写进去 →
                重启后有重触发风险,需打醒目警告留痕。
    """
    tmp = f"{TASKS_PATH}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, TASKS_PATH)
        return True
    except Exception as exc:
        print(f"[scheduler] 保存任务失败:{exc}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def _is_duplicate(a: dict, b: dict) -> bool:
    """两个任务是否算"同一个"(用于去重):kind + 时间字段 + desc 都相同。

    once 的 fire_at 是绝对秒,"5分钟后"连说两遍会差几秒,故用 60s 容差。
    只比未触发任务(done 的不参与,见 add_task)。
    """
    if a.get("kind") != b.get("kind"):
        return False
    if (a.get("desc") or "").strip() != (b.get("desc") or "").strip():
        return False
    kind = a.get("kind")
    if kind == "daily":
        return a.get("hour") == b.get("hour") and a.get("minute") == b.get("minute")
    if kind == "weekly":
        return (a.get("weekday") == b.get("weekday")
                and a.get("hour") == b.get("hour") and a.get("minute") == b.get("minute"))
    if kind == "interval":
        return a.get("every_sec") == b.get("every_sec")
    if kind == "once":
        return abs(a.get("fire_at", 0) - b.get("fire_at", 0)) <= 60
    return False


def add_task(task: dict) -> bool:
    """添加任务。已存在等价的未触发任务则跳过(去重)。

    Returns:
        "added"     = 实际新建并成功落盘
        "duplicate" = 已有等价任务,未重复创建(调用方告诉用户"早就记着啦")
        "save_failed" = 新建了但存盘失败(磁盘满/权限),没真正记住,调用方要告诉
                        用户没记成,别假报成功——否则用户以为记下了、重启后任务消失。
    """
    # 锁内做完整的 load→去重检查→append→save,避免与另一进程的写互相覆盖
    with _file_lock():
        tasks = load_tasks()
        for t in tasks:
            if not t.get("done") and _is_duplicate(t, task):
                return "duplicate"
        tasks.append(task)
        ok = save_tasks(tasks)
    return "added" if ok else "save_failed"


def remove_task(task_id: str) -> bool:
    """删除任务。Returns True 仅当确实删到了【且成功落盘】。
    save 失败返回 False:盘上其实没删掉,别假报"已删除"误导用户。"""
    with _file_lock():
        tasks = load_tasks()
        new = [t for t in tasks if t.get("id") != task_id]
        if len(new) != len(tasks):
            return save_tasks(new)
    return False


def remove_all_tasks() -> int:
    """清空全部任务。返回实际删除条数;0=本来就没有;-1=存盘失败(任务还在)。

    必须【锁内】一次性 load→清空→save:若像旧版那样在锁外读快照、再逐条
    remove_task,期间另一进程(MCP/快通道)新建的任务不在快照里 → 被漏删,
    用户却被告知"全清了"。这里在单个锁段内取最新盘内容并整体清空。

    返回值区分三态(与 add_task/remove_task 的 save_failed 语义对齐):旧版
    存盘失败也返回 0,与"本来就没有任务"无法区分 → 用户被误告知"没有任务",
    其实任务都还在盘上。现用 -1 表示存盘失败,让调用方如实提示。
    """
    with _file_lock():
        tasks = load_tasks()
        n = len(tasks)
        if n == 0:
            return 0
        return n if save_tasks([]) else -1


def _new_id() -> str:
    return "t" + str(int(time.time() * 1000))


# ───────────────────────────  时间解析  ───────────────────────────
def _to_24h(hour: int, text: str) -> int:
    """根据'下午/晚上/傍晚'等把 12 小时转 24 小时。"""
    # "晚上/夜里"的 12 点、0 点口语里都指午夜 0 点(不是中午 12 点);
    # 但"下午12点"指的是中午 12 点,不能归零,故午夜词单列。
    if any(k in text for k in ("晚上", "夜里", "夜晚", "凌晨", "半夜")) and hour in (0, 12):
        return 0
    is_pm = any(k in text for k in (
        "下午", "晚上", "傍晚", "夜里", "夜晚",
        "今晚", "今夜", "明晚", "晚间", "午后"))
    if is_pm and hour < 12:
        return hour + 12
    return hour


def parse_schedule(text: str) -> dict | None:
    """从一句话解析出定时任务的时间部分(不含 prompt)。解析不出返回 None。"""
    t = _normalize_cn_numbers(text.strip())
    now = time.time()

    # --- 一次性延迟:X 秒/分钟/小时 后 ---
    m = re.search(r"(\d+)\s*(秒|分钟|分|小时|钟头|个小时)\s*[后之]?后?", t)
    if m and ("后" in t):
        n = int(m.group(1))
        unit = m.group(2)
        if "秒" in unit:
            sec = n
        elif "小时" in unit or "钟头" in unit or "个小时" in unit:
            sec = n * 3600
        else:
            sec = n * 60
        # 与 interval 的 0 间隔保护对称:"0分钟后"会建出 fire_at≈now 的任务,
        # 下一轮(20s 内)立刻触发,不符用户预期(多半是误输入)。返回 None 交 claude。
        if sec <= 0:
            return None
        return {"kind": "once", "fire_at": now + sec}
    # "半小时后"
    if "半小时后" in t or "半个小时后" in t:
        return {"kind": "once", "fire_at": now + 1800}

    # --- 每隔 X / 每 X(周期)---
    m = re.search(r"每\s*隔?\s*(\d+)\s*(秒|分钟|分|小时|个小时)", t)
    if m:
        n = int(m.group(1)); unit = m.group(2)
        if "秒" in unit:
            every = n
        elif "小时" in unit:
            every = n * 3600
        else:
            every = n * 60
        # 拒绝 0 间隔:否则 next_at==now 会立即触发,且 after_fire 里 `or 3600`
        # 兜底会让它悄悄变成每小时一次,行为完全不符用户预期。返回 None 交给
        # claude 反问/澄清,而不是建一个混乱任务。
        if every <= 0:
            return None
        return {"kind": "interval", "every_sec": every, "next_at": now + every}

    # --- 每周 X 点(支持 每周三 / 每星期三 / 每礼拜三 / 礼拜三)---
    m = re.search(r"每?\s*(?:周|星期|礼拜)\s*([一二三四五六日天])\s*.*?(\d{1,2})\s*[:点时]\s*(\d{1,2})?", t)
    if m:
        wd = _WEEKDAYS.get(m.group(1), 0)
        hour = _to_24h(int(m.group(2)), t)
        minute = int(m.group(3)) if m.group(3) else (30 if "点半" in t else 0)
        # 与 daily 一致地校验越界(如"每周三25点"),否则会建出 hour=25 的任务
        # 静默永不触发。越界则返回 None 交给 claude 处理。
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {"kind": "weekly", "weekday": wd, "hour": hour, "minute": minute}
        return None

    # --- 每天 X 点[Y分] / 每天 HH:MM ---
    m = re.search(r"每?\s*天?.*?(\d{1,2})\s*[:点时]\s*(\d{1,2})?\s*分?", t)
    if m and ("每天" in t or "点" in t or ":" in t or "时" in t):
        hour = _to_24h(int(m.group(1)), t)
        minute = int(m.group(2)) if m.group(2) else (30 if "点半" in t else 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {"kind": "daily", "hour": hour, "minute": minute}

    return None


def parse_schedule_with_claude(text: str, cancel_event=None) -> dict | None:
    """规则解析不出时,交给 claude 理解自然语言时间(如"明天下午三点半")。

    返回和 parse_schedule 一样的内部格式 dict,失败返回 None。
    注意:会调用 claude,需在后台线程执行(耗时几秒)。
    """
    import claude_bridge
    now = datetime.now()
    prompt = (
        "你是一个时间解析器。"
        f"当前时间是 {now.strftime('%Y-%m-%d')} {'一二三四五六日'[now.weekday()]} "
        f"{now.strftime('%H:%M')}。\n"
        "请把下面这句话里的定时需求解析成 JSON,只输出 JSON,不要任何其他文字、不要代码块标记。\n\n"
        f'句子:"{text}"\n\n'
        "从这几种 kind 里选一个输出:\n"
        '- 每天定点: {"kind":"daily","hour":0-23,"minute":0-59}\n'
        '- 每周定点: {"kind":"weekly","weekday":0-6(0=周一),"hour":,"minute":}\n'
        '- 一次性(相对现在多少秒后): {"kind":"once","after_sec":整数}\n'
        '- 周期重复(每隔多少秒): {"kind":"interval","every_sec":整数}\n'
        '- 无法解析出明确时间: {"kind":null}\n'
    )
    try:
        reply = claude_bridge.ask_raw(prompt, timeout_sec=45, cancel_event=cancel_event)
    except Exception:
        return None

    # 剥掉可能的 ```json ``` 代码块,提取第一个 {...}
    m = re.search(r"\{.*\}", reply, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None

    kind = data.get("kind")
    nowf = time.time()

    def _hm(d):
        """从模型返回里取并【范围校验】hour/minute,越界抛 ValueError。
        不校验会让 hour=25 一路存进任务,等 is_due 里 datetime.replace(hour=25)
        才崩 → 拖垮整轮调度。在解析处就拦下,越界直接当解析失败返回 None。"""
        h = int(d["hour"])
        m = int(d.get("minute", 0))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"hour/minute 越界: {h}:{m}")
        return h, m

    try:
        if kind == "daily":
            h, m = _hm(data)
            return {"kind": "daily", "hour": h, "minute": m}
        if kind == "weekly":
            wd = data["weekday"]
            # claude 可能对"工作日"等返回一个列表(多天),本模型只支持单天:
            # 降级成每天(daily)更贴近用户意图,免得漏触发。
            if isinstance(wd, list):
                h, m = _hm(data)
                return {"kind": "daily", "hour": h, "minute": m}
            wd = int(wd)
            if not (0 <= wd <= 6):
                return None
            h, m = _hm(data)
            return {"kind": "weekly", "weekday": wd, "hour": h, "minute": m}
        if kind == "once":
            after = int(data["after_sec"])
            # 负/零秒数 → fire_at 落在过去 → 要么立即误触发、要么永不触发。
            # 模型把"早上9点"在已过9点时算成负秒就会这样。当解析失败处理。
            if after <= 0:
                return None
            return {"kind": "once", "fire_at": nowf + after}
        if kind == "interval":
            every = int(data["every_sec"])
            if every <= 0:                       # 0/负周期会变成 fire-storm
                return None
            return {"kind": "interval", "every_sec": every, "next_at": nowf + every}
    except (KeyError, ValueError, TypeError):
        return None
    return None


# ── reminder/action 判定的四个 pattern 库(带方向性,见 task_mode)──
# 设计目标:关键词法只在【有把握】时自己定;一旦冲突或无信号,就返回
# "ambiguous" 交给 claude 判断,而不是硬猜一个默认值。这样既不会
# "只想被提醒却被擅自执行"(危险),也不会"想让它干活却只冒了气泡"(活没干)。

# R+ 提醒触发前缀:一旦出现,后面的动词都归"提醒我【自己】去做",不是皮卡丘做。
_REMINDER_POS = (
    "提醒我", "提醒一下", "提醒下", "提醒你", "叫我", "喊我", "记得", "别忘",
    "到点提醒", "到时候提醒", "记着提醒", "提醒",
)
# A+ 执行触发动词:让皮卡丘真去干活。在原表基础上补全了大量冷门执行动词
# (拉取/归档/同步/清理/统计/爬/导出/部署…),减少"该 action 却漏判成 reminder"。
_ACTION_POS = (
    "帮我", "替我", "给我写", "写", "整理", "生成", "创建", "保存", "提交",
    "运行", "执行", "下载", "发送", "备份", "汇总", "统计",
    "建", "做一个", "做个", "查一下", "搜",
    "拉取", "归档", "同步", "清理", "爬", "导出", "导入", "部署",
    "推送", "上传", "压缩", "解压", "扫描", "监控", "抓取", "收集",
)
# A强:强执行意图前缀。"帮我/替我"明确指向"皮卡丘替我做",即使句中也有
# 提醒词("帮我提醒团队"),也说不清到底要做还是要提醒 → 真冲突,交 claude。
_ACTION_STRONG = ("帮我", "替我")

# A可信:用于【快通道本地直存 action】的高置信信号。比 _ACTION_POS 严格——
# 只收"几乎不可能误命中无关词"的明确执行表达。原因:_ACTION_POS 含
# "写/建/搜/爬/整理/清理…"等单字或易撞词,靠 `k in text` 子串匹配会把
# "整理一下心情""清理思绪""建议自己休息"误判成 action,到点真去调 claude 干活。
# 快通道一旦判 action 就【本地直存、到点真执行】,代价高,故只认可信信号;
# 其余弱 action 信号交给 claude 结合语境判(见 fast_path_mode)。
# 注意:task_mode 仍用全量 _ACTION_POS(claude 路径有上下文,判得准),这里只收紧快通道。
_ACTION_TRUSTED = (
    "帮我", "替我", "给我写", "给我做", "给我整理", "给我生成", "给我查",
    "帮忙写", "帮忙整理", "帮忙生成",
)


def task_mode(text: str) -> str:
    """判断定时任务是'提醒类'/'执行类'/'拿不准(交 claude)'。

    返回:
      "reminder"  只到点提醒你(喝水、运动、开会…),皮卡丘冒气泡,不真干活。
      "action"    到点皮卡丘真去执行(写文件、整理、提交…),调 claude。
      "ambiguous" 关键词法拿不准(信号冲突或没有信号)→ 调用方应 fallback
                  给 claude 判断,别让关键词法硬猜出错。

    判定用四个 pattern 库带方向性地裁决,而非"提醒优先 + 默认提醒":
      1. 强执行前缀(帮我/替我) + 提醒词 同现 → 真冲突 → ambiguous
         (如"帮我提醒团队站会":到底要你做、还是提醒我?说不清)
      2. 有提醒前缀(提醒我/叫我/记得…)→ 它管辖后面所有动词 → reminder
         (如"提醒我写日报"="提醒我【自己去】写",不是让皮卡丘写)
      3. 无提醒前缀但有执行动词 → action
      4. 四库都不命中(纯事件/状态:开会/吃药/起床/喝水)→ 无信号 → ambiguous
         (旧逻辑这里默认 reminder 硬猜,现在交 claude 结合语境判更准)
    """
    def _has(kws):
        return any(k in text for k in kws)

    r = _has(_REMINDER_POS)
    a = _has(_ACTION_POS)
    a_strong = _has(_ACTION_STRONG)

    if a_strong and r:
        return "ambiguous"   # 强执行前缀与提醒词冲突
    if r:
        return "reminder"    # 提醒前缀管辖全句
    if a:
        return "action"      # 纯执行动词
    return "ambiguous"       # 无任何信号,别瞎猜


def fast_path_mode(text: str) -> str | None:
    """快通道(本地直存)对这条句子该怎么定 mode。返回 None 表示【别本地存,
    交给 claude】。

    快通道追求"快且安全":只在能安全确定 mode 时本地存,沾上执行意图的歧义
    一律上交 claude(它结合语境判得准,避免误执行/误提醒)。

      task_mode 结果      细分              快通道决定
      reminder            -                "reminder"(本地存)
      action              含可信执行信号    "action"(本地存)
      action              仅含弱执行信号    None(交 claude——弱信号如"整理/清理/写"
                                            可能误命中"整理心情/清理思绪",
                                            本地直存会误执行,交 claude 凭语境判)
      ambiguous           含执行动词        None(有执行意图却拿不准 → 交 claude)
      ambiguous           无执行动词        "reminder"(纯事件/状态:喝水/开会/吃药,
                                            无执行动词 → 当提醒安全,只冒气泡无副作用)
    """
    mode = task_mode(text)
    if mode == "reminder":
        return "reminder"
    if mode == "action":
        # 只有命中【可信执行信号】(帮我/替我/给我写…)才敢本地直存 action;
        # 仅靠弱信号(整理/清理/写/建…单字短词)判出的 action 不可信,交 claude。
        if any(k in text for k in _ACTION_TRUSTED):
            return "action"
        return None
    # ambiguous:有执行动词的歧义最危险(可能误执行/误漏做)→ 交 claude
    if any(k in text for k in _ACTION_POS):
        return None
    # 无执行动词的纯事件/状态(开会/喝水/吃药/起床)→ 当提醒,安全且快
    return "reminder"


def _is_question(text: str) -> bool:
    """粗判一句话是不是提问/反问(用于把"每天9点开市了吗"挡在快通道外)。

    句尾问号、或含明显疑问词(吗/呢/吧/是不是/几点/几天/多久…)即视为问句。
    宁可漏判(让真问句偶尔走 claude 也无妨),不可误判把建任务句当问句。
    """
    t = text.strip()
    if t.endswith(("?", "?")):
        return True
    # "几点/几天/几分/几个"是问数量,不是设定具体时间
    if re.search(r"几\s*(点|天|分|小时|个|秒)", t):
        return True
    q_kw = ("吗", "呢", "是不是", "是否", "对吧", "对不对", "多久", "多长时间", "几号")
    return any(k in t for k in q_kw)


def looks_like_schedule_strict(text: str) -> bool:
    """快通道判定:只认【最明确无歧义】的定时句式,其余一律交给 claude 工具。

    比 looks_like_schedule 更严:必须规则能稳稳解析出时间的句式才走快通道,
    这样既快又不会误拦边界情况(模糊时间、自然语言时间交给 claude 更聪明)。
    """
    t = _normalize_cn_numbers(text)
    # 疑问/反问句先排除:"每天9点开市了吗""每天都是9点上班吗""每隔几天浇水?"
    # 这类含时间词但其实是提问,不是设任务。命中快通道会误建莫名任务,
    # 一律交给 claude 判断(它能区分问句和真要建任务)。
    if _is_question(t):
        return False
    # 每天/每周(含星期/礼拜同义词)+ 明确钟点
    if (("每天" in t or "每周" in t or "星期" in t or "礼拜" in t)
            and re.search(r"\d{1,2}\s*[:点时]", t)):
        return True
    # 每隔 X / 每 X 周期
    if re.search(r"每\s*隔?\s*\d+\s*(秒|分钟|分|小时|个小时)", t):
        return True
    # X 分钟/小时/秒 后
    if re.search(r"\d+\s*(秒|分钟|分|小时|个小时)\s*[后之]后?", t) or "半小时后" in t:
        return True
    return False


def looks_like_schedule(text: str) -> bool:
    """判断这句话是不是在【设定时任务】。要保守精准,别误伤普通对话。

    判定:必须同时具备「明确的时间安排」+「提醒/定时意图」,
    或者本身就是无歧义的定时句式(每天/每隔/X分钟后…)。
    像"我今晚想吃火锅""明天是我生日"这种只含时间词的闲聊不算。
    """
    text = _normalize_cn_numbers(text)
    # 1) 无歧义的定时句式:直接算任务(这些词组合起来只可能是定时)
    strong = ("每天", "每周", "每隔", "每个工作日")
    if any(k in text for k in strong):
        return True
    # "X分钟后/X小时后/X秒后" + 有动作意图(后面跟着要做的事)
    if re.search(r"\d+\s*(秒|分钟|分|小时|个小时)\s*[后之]后?", text) or "半小时后" in text:
        return True

    # 2) 时间点 + 明确的提醒/指派意图,才算任务
    has_time = bool(re.search(r"\d+\s*[点:时]", text)) or any(
        k in text for k in ("明天", "后天", "大后天"))
    has_intent = any(k in text for k in (
        "提醒我", "提醒一下", "叫我", "喊我", "记得提醒", "到点", "准时",
        "定时", "闹钟", "别忘了提醒", "到时候提醒"))
    if has_time and has_intent:
        return True

    return False


# ───────────────────────────  到点判断  ───────────────────────────
# daily/weekly 一次性任务一旦错过目标分钟太久(默认 30 分钟)就不再补触发:
# 比如"每天9点提醒",电脑11点才开机,补冒一个早已过时的9点提醒没意义反而困扰。
# 但 30 分钟内的小延迟(睡眠刚醒/卡顿/轮询间隙)仍补,保证"那一刻不在线也不漏"。
DAILY_CATCHUP_SEC = 30 * 60
# 一次性任务同理:错过触发时刻超过此阈值(默认 30 分钟)就不再补——
# 睡醒看到 2 小时前该"看微波炉"的提醒已无意义。超时的 once 由 purge 标记 done。
ONCE_CATCHUP_SEC = 30 * 60


def dedup_key(task: dict, now: datetime) -> str:
    """本次触发的去重键。daily 按【日期】、weekly 按【年+ISO周】、其余按分钟。

    关键:daily/weekly 用"日期/周"而非"分钟"做键,这样同一天/同一周内
    只会触发一次——既支持错过分钟窗口后的补触发(见 is_due),又不会因为
    目标时刻已过、补触发条件持续为真而每次轮询都重复触发。
    """
    kind = task.get("kind")
    if kind == "daily":
        return now.strftime("%Y%m%d")
    if kind == "weekly":
        iso = now.isocalendar()       # (year, week, weekday)
        return f"{iso[0]}W{iso[1]:02d}"
    return now.strftime("%Y%m%d%H%M")


def is_due(task: dict, now: datetime, last_fired: dict) -> bool:
    """判断 task 此刻是否该触发。last_fired: {id: dedup_key} 防重复。

    daily/weekly 采用「错过补触发」语义:不要求精确落在目标分钟,而是判断
    "今天/本周该触发的时刻是否已到/已过、且今天/本周还没触发过"。这样电脑在
    目标那一分钟睡眠/关机/卡顿,稍后醒来仍能补提醒,不会整周期静默漏掉
    (DAILY_CATCHUP_SEC 之外的过期则放弃,避免补一个早已无意义的提醒)。
    """
    if not task.get("enabled", True):
        return False
    if task.get("done"):          # 已触发过的一次性任务,不再触发
        return False
    kind = task.get("kind")
    tid = task.get("id")

    # 整体包 try/except:任何一条任务字段被外部编辑成非法值(hour=25、fire_at=null、
    # next_at 是字符串…)都只让【这一条】当作"未到点",绝不能把异常抛给调用方
    # (pet._check_scheduled 的 for 循环无 try/except,一条崩会拖垮整轮、且每 20s
    # 重复崩)。当解析失败/不触发处理是最安全的降级。
    try:
        if kind == "once":
            fire_at = task.get("fire_at", 0)
            # 到点 → 触发;但错过太久(过期)就不补,留给 purge 标记 done。
            return 0 <= (now.timestamp() - fire_at) <= ONCE_CATCHUP_SEC

        if kind == "interval":
            return now.timestamp() >= task.get("next_at", 0)

        if kind in ("daily", "weekly"):
            if kind == "weekly" and now.weekday() != task.get("weekday"):
                return False
            # 今天还没触发过?(内存键 + 持久化键任一命中即视为已触发)
            key = dedup_key(task, now)
            if last_fired.get(tid) == key or task.get("last_fired_stamp") == key:
                return False
            # 今天的目标时刻(本地时间)
            target = now.replace(hour=task.get("hour", 0), minute=task.get("minute", 0),
                                 second=0, microsecond=0)
            delta = (now - target).total_seconds()
            # 已到/已过目标时刻,且未过补触发窗口 → 触发(含错过那一分钟后的补触发)
            return 0 <= delta <= DAILY_CATCHUP_SEC
    except (ValueError, TypeError):
        return False

    return False


def after_fire(task: dict, tasks: list[dict], stamp: str | None = None):
    """触发后更新任务状态。

    once:不直接删除,而是标记 done(保留一段历史),否则用户事后问
      "你提醒我了吗?"时 claude 查不到任务,会误以为"从没建过/没做好"而自责瞎编。
      done 任务过段时间(见 purge_old_done)再清理。
    interval:顺延 next_at(基于上一个预定时刻递增,消除轮询延迟的累积漂移)。
    daily/weekly:持久化本次触发的 dedup_key,防止进程重启后同一天/同一周重复触发。

    Args:
        tasks: 调用方(pet 轮询)读到的任务快照,仅作兼容保留;实际更新在锁内
            重新 load 最新磁盘内容进行,不会覆写这个可能已过时的快照。
        stamp: 本次触发的 dedup_key(daily=日期'YYYYMMDD'、weekly=年周'YYYYWww'),
            供 daily/weekly 持久化去重用——必须与 is_due 比较的 dedup_key 同格式。
            调用方(pet._check_scheduled)传入的就是 scheduler.dedup_key(task, now)。

    Returns:
        True  = 状态变更已落盘(或本就无需变更)。
        False = 写盘失败,变更没持久化。对 once 尤其要紧:done 没写进盘,
                进程若在 ONCE_CATCHUP_SEC(30min)窗口内重启,该任务会重触发
                (reminder 重复提醒 / action 重复执行)。调用方据此打醒目警告。
    """
    kind = task.get("kind")
    if kind not in ("once", "interval", "daily", "weekly"):
        return True

    # 关键:全程持锁,且锁内【重新 load】最新磁盘内容再改再写,
    # 不直接 save 调用方传进来的 tasks 快照——那个快照可能在 load 之后、
    # 这里之前被 MCP 进程追加过新任务,直接覆写会把新任务丢掉。
    with _file_lock():
        fresh = load_tasks()
        now = time.time()
        changed = False
        for t in fresh:
            if t.get("id") != task.get("id"):
                continue
            if kind == "once":
                t["done"] = True
                t["done_at"] = now
                changed = True
            elif kind == "interval":
                every = t.get("every_sec", 3600) or 3600
                # 从上一个预定 next_at 递增(而非从"现在"),否则每次轮询延迟
                # 都会被计入,周期越跑越晚。落后多个周期则快进到下一个未来时刻,
                # 避免补偿性连续触发。
                base = t.get("next_at", now)
                nxt = base + every
                if nxt <= now:
                    missed = int((now - base) // every) + 1
                    nxt = base + missed * every
                t["next_at"] = nxt
                changed = True
            elif kind in ("daily", "weekly") and stamp is not None:
                t["last_fired_stamp"] = stamp
                changed = True
        if changed:
            ok = save_tasks(fresh)
            if not ok and kind == "once":
                # once 的 done 没落盘:30min 内重启会重触发。无法在此撤销(任务
                # 即将执行),只能醒目留痕,便于排查"为什么提醒/执行了两次"。
                print(f"[scheduler] ⚠️ once 任务 done 标记写盘失败,"
                      f"重启后可能重复触发:{task.get('desc', task.get('id'))}")
            return ok
    return True


def purge_old_done(max_age_sec: int = 6 * 3600):
    """清理触发已久(默认6小时)的 once 完成任务,避免无限堆积。

    同时把【过期未触发】的 once 任务标记 done(错过触发时刻超过 ONCE_CATCHUP_SEC、
    电脑当时不在线没补成):否则它们 is_due 永远 False 却一直挂在"待触发"列表里
    误导用户。标记后正常进入 done 清理流程。
    """
    now = time.time()
    # 持锁内 load→过滤→save:这是每 20s 都跑的高频写,最容易撞上 MCP 建任务,
    # 不加锁会把 MCP 刚追加的新任务连带删掉。
    with _file_lock():
        tasks = load_tasks()
        changed = False
        for t in tasks:
            if (t.get("kind") == "once" and not t.get("done")
                    and now - t.get("fire_at", 0) > ONCE_CATCHUP_SEC):
                t["done"] = True
                t["done_at"] = now
                t["expired"] = True   # 标记是"过期没做"而非"已提醒过"
                changed = True
        kept = [t for t in tasks
                if not (t.get("done") and now - t.get("done_at", 0) > max_age_sec)]
        if len(kept) != len(tasks) or changed:
            if not save_tasks(kept):
                # 写盘失败:本轮的过期标记/清理只在内存,下轮 load 又是旧状态会重做。
                # 无害(幂等),但留痕便于排查磁盘满/权限问题(与 after_fire 一致)。
                print("[scheduler] ⚠️ purge_old_done 写盘失败,本轮清理未持久化")


def describe(task: dict) -> str:
    """把任务转成人话(给用户看)。"""
    k = task.get("kind")
    d = task.get("desc", "任务")
    if k == "daily":
        # 用 .get 兜底:即便外部编辑的 JSON 缺 hour/minute,也只是显示 00:00,
        # 不会 KeyError 崩掉 list_tasks/delete_task 的反馈。
        return f"每天 {task.get('hour', 0):02d}:{task.get('minute', 0):02d} — {d}"
    if k == "weekly":
        # %7 兜底:即便 weekday 越界(如 claude 误传 7),也不会 IndexError 崩溃。
        wd = "一二三四五六日"[task.get("weekday", 0) % 7]
        return f"每周{wd} {task.get('hour', 0):02d}:{task.get('minute', 0):02d} — {d}"
    if k == "interval":
        s = task.get("every_sec", 0)
        unit = f"{s}秒" if s < 60 else (f"{s//60}分钟" if s < 3600 else f"{s//3600}小时")
        return f"每隔{unit} — {d}"
    if k == "once":
        dt = datetime.fromtimestamp(task.get("fire_at", 0))
        # 跨天的一次性任务只显示时分会误导(分不清哪天),非今天则带上日期。
        when = dt.strftime("%H:%M") if dt.date() == date.today() else dt.strftime("%m-%d %H:%M")
        if task.get("done"):
            # 区分两种"已结束":正常触发过(✓),还是错过窗口没能执行(✗)。
            # purge_old_done 给"过期没补成"的 once 打了 expired 标记——若仍说
            # "已提醒过",用户事后查会误以为做了/提醒了,其实那一刻不在线漏掉了。
            if task.get("expired"):
                return f"{when} 一次 — {d}(✗ 错过了,当时没能执行)"
            return f"{when} 一次 — {d}(✓ 已提醒过)"
        return f"{when} 一次 — {d}"
    return d
