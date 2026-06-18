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
from datetime import datetime

import config

TASKS_PATH = os.path.join(config.BASE_DIR, "scheduled_tasks.json")

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
    # 匹配连续的中文数字片段(含"十"),但跳过紧跟"周/星期"后的星期几
    # (如"每周三"的"三"是星期,不能转成 3),用负向后顾排除。
    return re.sub(r"(?<![周期])[零〇一二两三四五六七八九十]+", repl, text)


# ───────────────────────────  存储  ───────────────────────────
def load_tasks() -> list[dict]:
    if not os.path.exists(TASKS_PATH):
        return []
    try:
        with open(TASKS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_tasks(tasks: list[dict]):
    try:
        with open(TASKS_PATH, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[scheduler] 保存任务失败:{exc}")


def add_task(task: dict):
    tasks = load_tasks()
    tasks.append(task)
    save_tasks(tasks)


def remove_task(task_id: str) -> bool:
    tasks = load_tasks()
    new = [t for t in tasks if t.get("id") != task_id]
    if len(new) != len(tasks):
        save_tasks(new)
        return True
    return False


def _new_id() -> str:
    return "t" + str(int(time.time() * 1000))


# ───────────────────────────  时间解析  ───────────────────────────
def _to_24h(hour: int, text: str, near_kw: str) -> int:
    """根据'下午/晚上/中午'等把 12 小时转 24 小时。"""
    if any(k in text for k in ("下午", "晚上", "傍晚", "夜里", "夜晚")) and hour < 12:
        return hour + 12
    if "中午" in text and hour < 12:
        return 12 if hour == 12 else hour
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
        return {"kind": "interval", "every_sec": every, "next_at": now + every}

    # --- 每周 X 点 ---
    m = re.search(r"每\s*周\s*([一二三四五六日天])\s*.*?(\d{1,2})\s*[:点时]\s*(\d{1,2})?", t)
    if m:
        wd = _WEEKDAYS.get(m.group(1), 0)
        hour = _to_24h(int(m.group(2)), t, "")
        minute = int(m.group(3)) if m.group(3) else (30 if "点半" in t else 0)
        return {"kind": "weekly", "weekday": wd, "hour": hour, "minute": minute}

    # --- 每天 X 点[Y分] / 每天 HH:MM ---
    m = re.search(r"每?\s*天?.*?(\d{1,2})\s*[:点时]\s*(\d{1,2})?\s*分?", t)
    if m and ("每天" in t or "点" in t or ":" in t or "时" in t):
        hour = _to_24h(int(m.group(1)), t, "")
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
    try:
        if kind == "daily":
            return {"kind": "daily", "hour": int(data["hour"]),
                    "minute": int(data.get("minute", 0))}
        if kind == "weekly":
            wd = data["weekday"]
            # claude 可能对"工作日"等返回一个列表(多天),本模型只支持单天:
            # 降级成每天(daily)更贴近用户意图,免得漏触发。
            if isinstance(wd, list):
                return {"kind": "daily", "hour": int(data["hour"]),
                        "minute": int(data.get("minute", 0))}
            return {"kind": "weekly", "weekday": int(wd),
                    "hour": int(data["hour"]), "minute": int(data.get("minute", 0))}
        if kind == "once":
            return {"kind": "once", "fire_at": nowf + int(data["after_sec"])}
        if kind == "interval":
            every = int(data["every_sec"])
            return {"kind": "interval", "every_sec": every, "next_at": nowf + every}
    except (KeyError, ValueError, TypeError):
        return None
    return None


def task_mode(text: str) -> str:
    """判断定时任务是'提醒类'还是'执行类'。

    reminder(提醒类):只是到点提醒你做某事(喝水、运动、开会、早起…),
      皮卡丘不需要真去干活,冒个常驻气泡提醒即可。
    action(执行类):到点要皮卡丘真去干活(写文件、整理、提交代码…),
      调 claude 执行。
    """
    action_kw = ("帮我", "写", "整理", "生成", "创建", "保存", "提交",
                 "运行", "执行", "下载", "发送", "备份", "检查", "汇总",
                 "建", "做一个", "做个", "查一下", "搜")
    # 含明确"帮我做X"动作词 → 执行类
    if any(k in text for k in action_kw):
        return "action"
    # 默认提醒类(提醒我X / 叫我X / 记得X)
    return "reminder"


def looks_like_schedule_strict(text: str) -> bool:
    """快通道判定:只认【最明确无歧义】的定时句式,其余一律交给 claude 工具。

    比 looks_like_schedule 更严:必须规则能稳稳解析出时间的句式才走快通道,
    这样既快又不会误拦边界情况(模糊时间、自然语言时间交给 claude 更聪明)。
    """
    t = _normalize_cn_numbers(text)
    # 每天/每周 + 明确钟点
    if ("每天" in t or "每周" in t) and re.search(r"\d{1,2}\s*[:点时]", t):
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
def is_due(task: dict, now: datetime, last_fired: dict) -> bool:
    """判断 task 此刻是否该触发。last_fired: {id: 'YYYYmmddHHMM'} 防重复。"""
    if not task.get("enabled", True):
        return False
    if task.get("done"):          # 已触发过的一次性任务,不再触发
        return False
    kind = task.get("kind")
    tid = task.get("id")
    stamp = now.strftime("%Y%m%d%H%M")  # 分钟级去重 key

    if kind == "once":
        return now.timestamp() >= task.get("fire_at", 0)

    if kind == "interval":
        return now.timestamp() >= task.get("next_at", 0)

    if kind == "daily":
        if now.hour == task.get("hour") and now.minute == task.get("minute"):
            if last_fired.get(tid) != stamp:
                return True
        return False

    if kind == "weekly":
        if (now.weekday() == task.get("weekday")
                and now.hour == task.get("hour")
                and now.minute == task.get("minute")):
            if last_fired.get(tid) != stamp:
                return True
        return False

    return False


def after_fire(task: dict, tasks: list[dict]):
    """触发后更新任务状态。

    once:不直接删除,而是标记 done(保留一段历史),否则用户事后问
      "你提醒我了吗?"时 claude 查不到任务,会误以为"从没建过/没做好"而自责瞎编。
      done 任务过段时间(见 purge_old_done)再清理。
    interval:顺延 next_at。daily/weekly:不变。
    """
    kind = task.get("kind")
    if kind == "once":
        for t in tasks:
            if t.get("id") == task["id"]:
                t["done"] = True
                t["done_at"] = time.time()
        save_tasks(tasks)
    elif kind == "interval":
        for t in tasks:
            if t.get("id") == task["id"]:
                t["next_at"] = time.time() + t.get("every_sec", 3600)
        save_tasks(tasks)


def purge_old_done(max_age_sec: int = 6 * 3600):
    """清理触发已久(默认6小时)的 once 完成任务,避免无限堆积。"""
    now = time.time()
    tasks = load_tasks()
    kept = [t for t in tasks
            if not (t.get("done") and now - t.get("done_at", 0) > max_age_sec)]
    if len(kept) != len(tasks):
        save_tasks(kept)


def describe(task: dict) -> str:
    """把任务转成人话(给用户看)。"""
    k = task.get("kind")
    d = task.get("desc", "任务")
    if k == "daily":
        return f"每天 {task['hour']:02d}:{task['minute']:02d} — {d}"
    if k == "weekly":
        wd = "一二三四五六日"[task.get("weekday", 0)]
        return f"每周{wd} {task['hour']:02d}:{task['minute']:02d} — {d}"
    if k == "interval":
        s = task.get("every_sec", 0)
        unit = f"{s}秒" if s < 60 else (f"{s//60}分钟" if s < 3600 else f"{s//3600}小时")
        return f"每隔{unit} — {d}"
    if k == "once":
        when = datetime.fromtimestamp(task.get("fire_at", 0)).strftime("%H:%M")
        if task.get("done"):
            return f"{when} 一次 — {d}(✓ 已提醒过)"
        return f"{when} 一次 — {d}"
    return d
