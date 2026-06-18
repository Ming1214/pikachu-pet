"""皮卡丘定时任务 MCP server(stdio)。

让 claude-code 自主判断用户的话要不要建/查/删定时任务,而不是靠 Python 正则猜。
claude 理解完自然语言时间(今晚、下周三、等会儿…)后,调用这里的工具,
工具复用 scheduler.py 把任务写进同一个 scheduled_tasks.json。

工具调用时还会往事件文件追加一行,桌宠主进程据此冒"✅ 已记下"确认气泡。

工具:
  schedule_task(kind, desc, mode, ...)  创建定时任务
  list_tasks()                          列出现有任务
  delete_task(id_fragment)              删除任务(可用 id 末几位)
"""

import json
import os
import sys
import time

# 让本文件能 import 同目录的 scheduler/config(MCP 由 claude 以任意 cwd 拉起)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scheduler  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("pika")

# 工具事件文件:桌宠轮询它来感知"claude 刚通过工具建了任务",冒确认气泡
EVENTS_PATH = os.path.join(scheduler.config.BASE_DIR, "tool_events.jsonl")


def _emit_event(kind: str, desc: str):
    """追加一条工具事件,供桌宠主进程感知(失败不致命)。"""
    try:
        with open(EVENTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"event": kind, "desc": desc, "ts": time.time()},
                ensure_ascii=False) + "\n")
    except Exception:
        pass


@mcp.tool()
def schedule_task(
    kind: str,
    desc: str,
    mode: str = "reminder",
    hour: int = 0,
    minute: int = 0,
    weekday: int = 0,
    after_sec: int = 0,
    every_sec: int = 0,
) -> str:
    """创建一个定时任务(到点提醒用户,或到点真去执行)。

    当用户表达了"到某个时间提醒我做某事"或"定时帮我做某事"时调用本工具。
    你需要先把用户口语化的时间理解成下面的结构化字段。

    Args:
        kind: 任务类型,必须是以下之一:
            "daily"    每天定点 —— 用 hour/minute
            "weekly"   每周定点 —— 用 weekday(0=周一…6=周日) + hour/minute
            "once"     一次性 —— 用 after_sec(从现在起多少秒后触发)
            "interval" 周期重复 —— 用 every_sec(每隔多少秒)
        desc: 任务的简短描述,给用户看(如"订火锅店""喝水""整理截图")。
        mode: "reminder"=只提醒用户(喝水/开会/起床这类,皮卡丘只冒气泡提醒);
              "action"=到点要皮卡丘真去执行(写文件/整理/提交代码这类)。
              拿不准就用 "reminder"。
        hour: 小时 0-23(daily/weekly 用)。
        minute: 分钟 0-59(daily/weekly 用)。
        weekday: 周几 0-6,0=周一(weekly 用)。
        after_sec: 多少秒后触发(once 用,如"3分钟后"=180)。
        every_sec: 每隔多少秒(interval 用,如"每2小时"=7200)。

    Returns:
        给用户看的确认文案(人话描述这条任务)。
    """
    now = time.time()
    task = {
        "id": scheduler._new_id(),
        "desc": (desc or "提醒").strip()[:40],
        "prompt": desc,        # action 模式到点会把它发给 claude 执行
        "mode": mode if mode in ("reminder", "action") else "reminder",
        "enabled": True,
        "kind": kind,
    }
    if kind == "daily":
        task["hour"] = int(hour); task["minute"] = int(minute)
    elif kind == "weekly":
        task["weekday"] = int(weekday)
        task["hour"] = int(hour); task["minute"] = int(minute)
    elif kind == "once":
        task["fire_at"] = now + int(after_sec)
    elif kind == "interval":
        task["every_sec"] = int(every_sec)
        task["next_at"] = now + int(every_sec)
    else:
        return f"ERROR: 未知的 kind「{kind}」,必须是 daily/weekly/once/interval。"

    scheduler.add_task(task)
    human = scheduler.describe(task)
    _emit_event("schedule", task["desc"])
    return f"已创建定时任务:{human}"


@mcp.tool()
def list_tasks() -> str:
    """列出定时任务(用户问"我有哪些任务/提醒""你提醒我了吗"时调用)。

    会区分【待触发】和【已提醒过】两类:
    - 已提醒过的一次性任务会保留一段时间,这样用户事后问"你提醒我了吗"时,
      你能据此回答"提醒过啦",而不是误以为任务从没建过。
    """
    tasks = scheduler.load_tasks()
    if not tasks:
        return "当前没有任何定时任务(也没有最近已完成的提醒记录)。"
    active = [t for t in tasks if not t.get("done")]
    done = [t for t in tasks if t.get("done")]
    parts = []
    if active:
        parts.append("【待触发】\n" + "\n".join(
            f"- [{t['id'][-4:]}] {scheduler.describe(t)}" for t in active))
    if done:
        parts.append("【已提醒过(最近)】\n" + "\n".join(
            f"- [{t['id'][-4:]}] {scheduler.describe(t)}" for t in done))
    return "\n\n".join(parts)


@mcp.tool()
def delete_task(id_fragment: str) -> str:
    """删除一个定时任务。

    Args:
        id_fragment: 任务 id 或其末尾几位(从 list_tasks 的 [xxxx] 里取)。
            传 "all" 或 "全部" 删除所有任务。
    """
    frag = (id_fragment or "").strip()
    tasks = scheduler.load_tasks()
    if frag in ("all", "全部", "所有"):
        for t in tasks:
            scheduler.remove_task(t["id"])
        return f"已删除全部 {len(tasks)} 个任务。"
    for t in tasks:
        if t["id"] == frag or t["id"].endswith(frag):
            scheduler.remove_task(t["id"])
            return f"已删除任务:{scheduler.describe(t)}"
    return f"没找到匹配「{frag}」的任务。"


if __name__ == "__main__":
    mcp.run()
