"""控制台可编辑配置项的声明(单一真相)。

web_console 据此渲染表单、校验输入、决定哪些项改了需重启。只收录【真正被代码
消费】的配置项——config.py 里那些定义了但全项目没读的"预留坑位"(REMIND_ENABLED /
FOLLOW_ENABLED / BREATH_ENABLED / FLOAT_ENABLED / SPARK_ENABLED 等)不放进来,
免得用户改了发现没效果。

每项字段:
  key          : config.py 里的常量名(必须真实存在)
  label        : 控制台显示的中文名
  group        : 分组(控制台按组折叠)
  type         : "bool" / "int" / "float" / "enum" / "text"
  needs_restart: True = 改了要重启桌宠才生效(timer 间隔类、决定 timer 是否创建的开关)
  choices      : enum 专用,候选值列表
  min/max      : int/float 专用,范围(控制台和 server 双重校验)
  help         : 可选,一句话说明
"""

# 可选宝可梦清单(供 ACTIVE_POKEMON 下拉)。从 pokedex/ 目录实际有哪些数据包动态取,
# 不手维护名单。import 失败兜底只给 pikachu(永远存在的默认包)。
try:
    import pokedex
    _POKEMON_CHOICES = pokedex.available_packs() or ["pikachu"]
    # 下拉【显示中文名、值用英文模块名】:choice_labels 是 {模块名: 中文名}。
    _POKEMON_LABELS = pokedex.pack_labels() or {"pikachu": "皮卡丘"}
except Exception:
    _POKEMON_CHOICES = ["pikachu"]
    _POKEMON_LABELS = {"pikachu": "皮卡丘"}

EDITABLE = [
    # ─────────── 宝可梦 ───────────
    {"key": "ACTIVE_POKEMON", "label": "当前宝可梦", "group": "宝可梦",
     "type": "enum", "choices": _POKEMON_CHOICES, "choice_labels": _POKEMON_LABELS,
     "needs_restart": True, "restart_label": "形象重启生效",
     "help": "换一只宝可梦(人设/台词/配色立刻热生效;形象动画在重启后生效)。"
             "每只有各自独立的记忆。"},
    {"key": "MEMORY_SHARED_ACROSS_POKEMON", "label": "宝可梦共享记忆", "group": "宝可梦",
     "type": "bool", "needs_restart": False,
     "help": "开:所有宝可梦都能读到你和任何一只说过的事(更连贯)。"
             "关:每只只记得自己和你的事(各自独立人格)。定时提醒/任务始终共享,不受此开关影响。"},

    # ─────────── 模型与权限 ───────────
    {"key": "CLAUDE_MODEL", "label": "模型", "group": "模型与权限",
     "type": "enum",
     "choices": ["", "claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"],
     "needs_restart": False,
     "help": "空 = 跟随 Claude Code 自身配置;选具体型号可给桌宠换脑(便宜型号省钱)。"},
    {"key": "CLAUDE_PERMISSION_MODE", "label": "权限模式", "group": "模型与权限",
     "type": "enum", "choices": ["auto", "acceptEdits", "bypassPermissions"],
     "needs_restart": False,
     "help": "auto=智能放行/危险拦截(推荐);bypassPermissions=全放行;acceptEdits=易卡。"},
    {"key": "CLAUDE_TIMEOUT_SEC", "label": "硬超时(秒)", "group": "模型与权限",
     "type": "int", "min": 60, "max": 1200, "needs_restart": False,
     "help": "单次 claude 调用最长等待。等危险操作确认期间会自动暂停,不计入。"},
    {"key": "ALLOW_INTERVAL_ACTION", "label": "周期任务可自动执行", "group": "模型与权限",
     "type": "bool", "needs_restart": False,
     "help": "默认关:周期 action 任务降级为到点提醒你手动确认(更安全)。"},

    # ─────────── 危险操作确认 ───────────
    {"key": "CONFIRM_HOOK_TIMEOUT_SEC", "label": "确认等待上限(秒)", "group": "危险操作确认",
     "type": "int", "min": 30, "max": 600, "needs_restart": False,
     "help": "危险命令拦下后等你点确认的最长时间;到点自动按拒绝处理。应小于硬超时。"},
    {"key": "CONFIRM_POLL_INTERVAL_MS", "label": "确认轮询间隔(ms)", "group": "危险操作确认",
     "type": "int", "min": 200, "max": 5000, "needs_restart": True,
     "help": "桌宠多久查一次有没有新的待确认危险操作。改了需重启(定时器启动时设一次)。"},

    # ─────────── 功能开关 ───────────
    {"key": "MEMORY_ENABLED", "label": "记忆系统", "group": "功能开关",
     "type": "bool", "needs_restart": True,
     "help": "总开关。决定记忆整理定时器是否创建,改了需重启生效。"},
    {"key": "PROACTIVE_ENABLED", "label": "主动搭话", "group": "功能开关",
     "type": "bool", "needs_restart": True,
     "help": "皮卡丘是否会主动找你聊。决定搭话定时器是否创建,从关到开需重启生效。"},

    # ─────────── 视觉特效 ───────────
    {"key": "FX_DUST_ENABLED", "label": "走路扬尘", "group": "视觉特效",
     "type": "bool", "needs_restart": False},
    {"key": "FX_GLOW_ENABLED", "label": "放电光晕", "group": "视觉特效",
     "type": "bool", "needs_restart": False},
    {"key": "FX_MOOD_ENABLED", "label": "心情粒子", "group": "视觉特效",
     "type": "bool", "needs_restart": False},
    {"key": "FX_MOOD_MAX", "label": "心情粒子上限", "group": "视觉特效",
     "type": "int", "min": 1, "max": 40, "needs_restart": False},

    # ─────────── 主动搭话调参 ───────────
    {"key": "PROACTIVE_MAX_PER_DAY", "label": "每日搭话上限", "group": "主动搭话",
     "type": "int", "min": 0, "max": 30, "needs_restart": False},
    {"key": "PROACTIVE_MIN_GAP_MS", "label": "两次搭话最小间隔(ms)", "group": "主动搭话",
     "type": "int", "min": 60000, "max": 7200000, "needs_restart": False},
    {"key": "PROACTIVE_IDLE_MIN_MS", "label": "触发所需空闲(ms)", "group": "主动搭话",
     "type": "int", "min": 30000, "max": 3600000, "needs_restart": False},
    {"key": "PROACTIVE_CHECK_INTERVAL_MS", "label": "搭话轮询间隔(ms)", "group": "主动搭话",
     "type": "int", "min": 300000, "max": 7200000, "needs_restart": True,
     "help": "多久检查一次该不该主动找你。改了需重启(定时器启动时设一次)。"},
    {"key": "PROACTIVE_QUIET_HOURS", "label": "静默时段(起→止 钟点)", "group": "主动搭话",
     "type": "hours_range", "needs_restart": False,
     "help": "这段钟点内不主动打扰(支持跨零点,如 23→8)。取值 0-23。"},
    {"key": "PROACTIVE_MEMORY_TOP_N", "label": "搭话参考记忆条数", "group": "主动搭话",
     "type": "int", "min": 5, "max": 60, "needs_restart": False,
     "help": "判断该不该搭话时,从记忆库里取多少条最值得关心的喂给 claude。"},

    # ─────────── 行为/动画 ───────────
    # 注:SLEEP_PROBABILITY 虽在 config.py 定义,但全项目无代码消费(睡眠由 PLAY_WEIGHTS
    # 的 yawn 权重 + SLEEP_AFTER_MS 控制),故【不收录】——免得用户改了没效果。
    {"key": "WALK_SPEED", "label": "走路速度(px/帧)", "group": "行为",
     "type": "int", "min": 1, "max": 40, "needs_restart": False},
    {"key": "ASCII_FRAME_MS", "label": "动画帧间隔(ms)", "group": "行为",
     "type": "int", "min": 100, "max": 1500, "needs_restart": True,
     "help": "改了需重启:动画定时器启动时设一次间隔。"},
    {"key": "SLEEP_AFTER_MS", "label": "多久没互动才睡(ms)", "group": "行为",
     "type": "int", "min": 10000, "max": 1800000, "needs_restart": False},
    {"key": "SLEEP_DURATION_MS", "label": "一觉睡多久(ms)", "group": "行为",
     "type": "int", "min": 1000, "max": 60000, "needs_restart": False},
    {"key": "JUMP_HEIGHT_PX", "label": "跳跃高度(px)", "group": "行为",
     "type": "int", "min": 0, "max": 120, "needs_restart": False},
    {"key": "CLICK_MOVE_THRESHOLD", "label": "点击/拖拽判定阈值(px)", "group": "行为",
     "type": "int", "min": 1, "max": 30, "needs_restart": False,
     "help": "鼠标移动超过这个距离算拖拽,否则算点击。"},
    {"key": "BUBBLE_DURATION_MS", "label": "气泡停留(ms)", "group": "行为",
     "type": "int", "min": 800, "max": 10000, "needs_restart": False},
    {"key": "ONBOARD_DELAY_MS", "label": "首次引导延时(ms)", "group": "行为",
     "type": "int", "min": 0, "max": 30000, "needs_restart": True,
     "help": "首次启动多久后冒引导气泡。改了需重启(只在启动时调度一次)。"},

    # ─────────── 记忆调参 ───────────
    {"key": "MEMORY_MAX_ITEMS", "label": "记忆条数上限", "group": "记忆",
     "type": "int", "min": 10, "max": 300, "needs_restart": False},
    {"key": "MEMORY_DECAY_PER_DAY", "label": "记忆每日衰减系数", "group": "记忆",
     "type": "float", "min": 0.5, "max": 1.0, "needs_restart": False,
     "help": "越小衰减越快(越容易忘);1.0=不衰减。"},
    {"key": "DIGEST_INTERVAL_MS", "label": "记忆整理轮询间隔(ms)", "group": "记忆",
     "type": "int", "min": 300000, "max": 7200000, "needs_restart": True,
     "help": "多久整理一次对话成记忆(无新对话则跳过)。改了需重启(定时器启动时设一次)。"},
    {"key": "MEMORY_INJECT_TOP_N", "label": "聊天注入记忆条数", "group": "记忆",
     "type": "int", "min": 0, "max": 30, "needs_restart": False,
     "help": "每次聊天把多少条高权重记忆注入 prompt(越多越「记得你」,但 prompt 越长)。"},
    {"key": "DIGEST_MAX_CONVO_LINES", "label": "每次整理最多读对话行", "group": "记忆",
     "type": "int", "min": 10, "max": 300, "needs_restart": False},
    {"key": "CONVO_LOG_MAX_LINES", "label": "对话流水上限(行)", "group": "记忆",
     "type": "int", "min": 100, "max": 5000, "needs_restart": False},

    # ─────────── 后台 / 资源 ───────────
    {"key": "MAX_CONCURRENT_SCHED_WORKERS", "label": "定时任务并发上限", "group": "后台/资源",
     "type": "int", "min": 1, "max": 8, "needs_restart": False,
     "help": "同时最多几个定时任务在跑(防多任务同时到点拖垮机器)。"},
    {"key": "STICKY_QUEUE_MAX", "label": "常驻提醒队列上限", "group": "后台/资源",
     "type": "int", "min": 1, "max": 50, "needs_restart": False},
    {"key": "CALL_LOG_MAX_LINES", "label": "调用日志上限(行)", "group": "后台/资源",
     "type": "int", "min": 100, "max": 10000, "needs_restart": False,
     "help": "超出按尾部轮转保留。"},

    # ─────────── 人设(大文本) ───────────
    {"key": "PIKACHU_PERSONA", "label": "皮卡丘人设(system prompt)", "group": "人设",
     "type": "text", "needs_restart": False,
     "help": "皮卡丘的性格与底线。改了下一条聊天即生效。清空恢复默认请用「恢复默认」。"},
]

# 快速索引:key -> schema 项
BY_KEY = {item["key"]: item for item in EDITABLE}


def coerce(key: str, value):
    """把控制台传来的原始值按 schema 类型转换 + 校验,返回规范化后的值。

    校验失败抛 ValueError(server 捕获后返回 400)。未知 key 也抛 ValueError。
    """
    item = BY_KEY.get(key)
    if item is None:
        raise ValueError(f"未知配置项:{key}")
    t = item["type"]

    if t == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    if t == "int":
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} 需要整数")
        lo, hi = item.get("min"), item.get("max")
        if lo is not None and v < lo:
            raise ValueError(f"{key} 不能小于 {lo}")
        if hi is not None and v > hi:
            raise ValueError(f"{key} 不能大于 {hi}")
        return v

    if t == "float":
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} 需要数字")
        lo, hi = item.get("min"), item.get("max")
        if lo is not None and v < lo:
            raise ValueError(f"{key} 不能小于 {lo}")
        if hi is not None and v > hi:
            raise ValueError(f"{key} 不能大于 {hi}")
        return v

    if t == "enum":
        s = "" if value is None else str(value)
        if s not in item["choices"]:
            raise ValueError(f"{key} 取值非法,须是 {item['choices']} 之一")
        return s

    if t == "text":
        if not isinstance(value, str):
            raise ValueError(f"{key} 需要文本")
        # 人设防呆:别让空字符串把皮卡丘变哑巴。要恢复默认走 reset 接口。
        if not value.strip():
            raise ValueError(f"{key} 不能为空(要恢复默认请用「恢复默认」)")
        return value

    if t == "hours_range":
        # 收 [起, 止] 两个 0-23 整数,返回 tuple(下游 PROACTIVE_QUIET_HOURS 解包用)。
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"{key} 需要 [起始钟点, 结束钟点] 两个值")
        try:
            a, b = int(value[0]), int(value[1])
        except (TypeError, ValueError):
            raise ValueError(f"{key} 钟点需为整数")
        if not (0 <= a <= 23 and 0 <= b <= 23):
            raise ValueError(f"{key} 钟点须在 0-23 之间")
        return (a, b)

    raise ValueError(f"{key} 类型未知:{t}")
