"""皮卡丘桌宠的集中配置(高清 + 电影级动效版)。

所有可调参数都放在这里,方便不动主逻辑就能改外观/行为。
"""

import os
import re

# ─────────────────────────────  路径  ─────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# 主素材:Dream World 矢量站立插画(SVG,自然正面站姿,可无限放大不失真)
SVG_PATH = os.path.join(ASSETS_DIR, "pikachu_stand.svg")
SVG_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/dream-world/25.svg"
# 备用:Pokémon HOME 高清 3D 渲染(PNG)
HD_PATH = os.path.join(ASSETS_DIR, "pikachu_hd_main.png")
HD_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/25.png"
# 头像(聊天窗标题用)
AVATAR_PATH = HD_PATH   # 头像用 PNG 更省事(SVG 裁圆形稍复杂)

# ─────────────────────────────  外观  ─────────────────────────────
PET_SIZE = 170          # (旧)图片模式边长,ASCII 模式不用
FACE_RIGHT_BY_DEFAULT = True

# ─────────────────────────────  ASCII 动画  ─────────────────────────────
ASCII_FONT_PX = 22       # 字符画字号(越大皮卡丘越大)
ASCII_FRAME_MS = 420     # 每帧间隔(动画速度,越大越慢)
WALK_SPEED = 9           # 走路时每帧移动像素(帧慢了,步子大点)
SLEEP_AFTER_MS = 180000  # 无互动 3 分钟后才自动睡觉
SLEEP_DURATION_MS = 8000   # 睡一觉的时长(短一点,别老睡)
SLEEP_PROBABILITY = 0.12   # 普通随机里抽到"困了想睡"的概率(降低睡觉频率)

# ── 新自主行为(A):随机玩耍时各动作的抽中权重 ──
# 权重无需归一化,代码内部按总和取概率。调大某项 = 更常出现该动作。
PLAY_WEIGHTS = {
    "walk": 0.34,   # 走来走去(真在桌面移动)
    "idle": 0.20,   # 待机眨眼
    "eat":  0.13,   # 吃东西
    "look": 0.12,   # 东张西望
    "jump": 0.09,   # 跳跃(配合窗口上移)
    "sing": 0.07,   # 哼歌
    "yawn": 0.05,   # 打哈欠(也会作为 idle→sleep 过渡触发)
}
JUMP_HEIGHT_PX = 26        # 跳跃时窗口上移的最大像素

# ── 视觉特效层(D):叠在 ASCII 帧之上,不改帧。各项可单独开关 ──
FX_DUST_ENABLED = True     # 走路时脚下扬起小尘点
FX_GLOW_ENABLED = True     # 放电(happy/cheer)时窗口边缘淡黄光晕
FX_MOOD_ENABLED = True     # 心情图标飘动:开心飘 ✨、沮丧落 💧
FX_MOOD_MAX = 12           # 同时存在的心情粒子上限(防堆积)

# ─────────────────────────────  代码驱动动效  ─────────────────────────────
# 呼吸:轻微缩放,模拟呼吸起伏
BREATH_ENABLED = True
BREATH_SCALE = 0.04            # 缩放幅度(±4%)
BREATH_PERIOD_MS = 2600        # 一次呼吸周期

# 漂浮:上下轻微浮动,像悬在桌面上
FLOAT_ENABLED = True
FLOAT_AMPLITUDE = 6            # 上下浮动像素
FLOAT_PERIOD_MS = 3200

# 弹跳:被点击时的弹跳反应
BOUNCE_HEIGHT = 28            # 弹跳高度像素
BOUNCE_DURATION_MS = 520

# 放电粒子:被点击/提醒时迸发的电火花
SPARK_ENABLED = True
SPARK_COUNT = 14             # 每次迸发的电火花数量
SPARK_DURATION_MS = 700

# ─────────────────────────────  跟随鼠标  ─────────────────────────────
FOLLOW_ENABLED = True
FOLLOW_INTERVAL_MS = 80
FLIP_DEADZONE_PX = 40          # 鼠标水平距离超过此值才翻转朝向

# ─────────────────────────────  点击 vs 拖拽  ─────────────────────────────
CLICK_MOVE_THRESHOLD = 6

# ─────────────────────────────  提醒陪伴  ─────────────────────────────
REMIND_ENABLED = True
REMIND_INTERVAL_MIN = 45
REMIND_MESSAGES = [
    "皮卡皮卡!⚡ 坐太久啦,起来动一动吧!",
    "皮卡丘~ 该喝水啦!咕嘟咕嘟💧",
    "皮~卡!👀 眼睛累不累?看看远处休息一下嘛!",
    "皮卡pi~ 深呼吸,放松肩膀,你超棒的!✨",
]

# 被点击时随机冒的小气泡
POKE_REACTIONS = ["皮卡?⚡", "皮卡丘!", "皮~卡pi!", "皮卡皮卡!✨", "pika~⚡"]
BUBBLE_DURATION_MS = 2600

# 打开对话窗时随机一句开场白(像宠物,不是助手)
CHAT_GREETINGS = [
    "*耳朵竖起来* 皮卡?⚡",
    "*蹦到你面前* 你来啦~ 嘿嘿",
    "*歪头看你* 皮卡丘?",
    "*尾巴翘了翘* 嗯哼?找我玩吗~",
    "*脸颊滋滋冒电* 皮~卡!",
    "*打了个小哈欠* ……皮卡?你叫我?",
]

# ─────────────────────────  对话窗主题(宝可梦球 红白卡通)  ─────────────────
# 不用模糊玻璃,改用实色卡通配色,致敬精灵球(上红下白,中间黑带 + 白色按钮)
COL_CARD_BG = "#FFFFFF"          # 卡片主体:精灵球下半部白
COL_CARD_BORDER = "#2B2B2B"      # 粗黑描边(卡通感)
COL_TITLE_RED = "#EE1515"        # 标题栏:精灵球红
COL_TITLE_RED_DK = "#C81010"     # 红色暗部(立体感)
COL_BELT_BLACK = "#2B2B2B"       # 精灵球中间黑带
COL_MSG_AREA = "#F4F4F4"         # 消息区浅灰白底
COL_USER_BUBBLE = "#3B5BDB"      # 用户气泡:精灵球按钮蓝
COL_USER_TEXT = "#FFFFFF"
COL_PIKA_BUBBLE = "#FFF4C2"      # 皮卡丘气泡:淡黄(雷电黄柔化)
COL_PIKA_BUBBLE_BORDER = "#F2C200"
COL_PIKA_TEXT = "#3A2E00"        # 皮卡丘气泡文字:深棕(在淡黄上清晰)

# 统一中文字体栈
FONT_STACK = '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'

# ─────────────────────────────  Claude CLI 集成  ─────────────────────────────
CLAUDE_BIN = "claude"
CLAUDE_WORKDIR = os.path.expanduser("~/Desktop/Claude-Code")
# 硬超时上限(最终兜底)。原 180s 对【危险操作确认】不够用:hook 拦截后会阻塞
# 等用户点确认气泡,这段"等人"时间不该计入超时(见 claude_bridge._awaiting_human
# 暂停逻辑)。即便暂停逻辑漏触发,500s 也作为第二道保险,不至于在用户还没点完
# 确认时就被 killpg 误杀。等待确认期间硬超时被暂停,所以正常任务并不会真等满 500s。
# 在此之前 20s/45s 已有分级安抚提示,告诉用户可点 ✕ 主动停。
CLAUDE_TIMEOUT_SEC = 500
CLAUDE_MULTI_TURN = True
# 权限模式:auto = 智能判断安全性(安全放行/危险拦截),适合非交互桌宠。
# 可选 "bypassPermissions"(全放行)/"acceptEdits"(只接受编辑,会卡)。
CLAUDE_PERMISSION_MODE = "auto"

# ─────────────────────  危险操作三层确认(A 硬拦截 + B 软护栏 + C 透明)  ─────────────────────
# auto 模式让 claude 自己判断安全性,没有用户确认环节(桌宠非交互)。万一它误判、
# 在用户没预期时跑了不可逆操作就麻烦了。这里加三层防护,但【只拦极少数真不可逆命令】,
# 让日常聊天/写代码/git commit 完全零打扰——日常命令根本碰不到下面这些模式。
#
# 第 0 层:危险命令清单(三层共用的"什么算危险")。预编译正则,主程序与 hook 脚本
# (pika_guardian.py)共享同一份,杜绝两处定义漂移。只放真不可逆的:
# 几个"命令位"前缀片段,供下面收窄正则共用:命令只可能出现在【整条命令开头】或
# 【shell 分隔符之后】(; && || | & 开头的 ( 子shell、换行)。用它把"真在跑这个命令"
# 和"只是把这个词写在字符串/文件名/参数里"区分开,避免误伤(详见各条注释)。
_CMD_POS = r"(?:^|[;&|\n(]|&&|\|\|)\s*"
DANGER_PATTERNS = [
    re.compile(r"\brm\s+-[a-z]*[rf]", re.I),          # rm -rf / rm -fr / rm -r / rm -f(含单文件删,按要求一律拦)
    re.compile(r"git\s+push\b.*(--force|--force-with-lease|\s-f\b)", re.I),  # 强推
    re.compile(r"git\s+reset\s+--hard", re.I),        # 硬重置(丢工作区改动)
    re.compile(r"\bmkfs\b", re.I),                    # 格式化文件系统
    # dd:只有读/写裸设备(if=/dev/… 或 of=/dev/…)才不可逆;文件对拷 dd if=a of=b 安全,不拦。
    re.compile(r"\bdd\b[^\n]*\b(?:if|of)=/dev/", re.I),
    re.compile(r">\s*/dev/(sd|disk|nvme)", re.I),     # 重定向写裸设备
    # sudo / 关机系列:只在【命令位】出现才算真要执行;写在 echo 字符串里、commit message
    # 里、文件名里(halt.py)的同名词不拦,免得日常聊天/文档生成被误伤。
    re.compile(_CMD_POS + r"sudo\b", re.I),           # 提权
    re.compile(_CMD_POS + r"(shutdown|reboot|halt|poweroff)\b", re.I),  # 关机/重启
]

# 危险操作确认:跨进程文件信令(hook 子进程 ↔ 桌宠主进程)
CONFIRM_PENDING_PATH = os.path.join(BASE_DIR, "guardian_pending.jsonl")  # hook 写、桌宠轮询
# 决策文件:桌宠用户点确认后写 guardian_decision.<req_id>,内容 "allow"/"deny";hook 轮询它
CONFIRM_DECISION_PREFIX = os.path.join(BASE_DIR, "guardian_decision.")
CONFIRM_HOOK_TIMEOUT_SEC = 280     # hook 阻塞等确认的上限(< CLAUDE_TIMEOUT_SEC=500,留余量)
CONFIRM_POLL_INTERVAL_MS = 800     # 桌宠轮询 pending 文件的间隔
PET_SETTINGS_PATH = os.path.join(BASE_DIR, "pet_settings.json")  # 自动生成,经 --settings 挂 hook
GUARDIAN_PATH = os.path.join(BASE_DIR, "pika_guardian.py")       # hook 脚本
# 危险操作流水(用户数据,退出【保留】,和 conversation.jsonl 同等待遇):每次命中留痕,可事后查
DANGER_LOG_PATH = os.path.join(BASE_DIR, "danger_ops.jsonl")


def is_danger_command(command: str) -> bool:
    """判断一条 shell 命令是否命中危险清单。主程序与 hook 脚本共用,确保判定一致。"""
    if not command:
        return False
    return any(p.search(command) for p in DANGER_PATTERNS)


# ── claude 不可用时的拟声兜底台词 ──
# 没装 Claude Code / claude 不在 PATH 时,聊天窗用这些拟声词代替冷冰冰的错误提示:
# 既给用户即时反馈("皮卡丘出声了"),又不至于吓到人。从池里随机挑一句,每次不同。
PIKA_BABBLE = [
    "皮卡皮卡~⚡",
    "皮卡丘?(歪头)皮卡…皮卡…",
    "皮卡皮卡!(指了指你)皮——卡——丘!",
    "(蹭蹭你)皮卡~ 皮卡丘…",
]
# 拟声词后再拼这句,温和点明"说不了完整的话"的原因,免得用户一头雾水。
PIKA_NO_CLAUDE_HINT = (
    "皮卡皮卡…⚡(皮卡丘只会冒电火花了——好像还没装好 Claude Code,"
    "装好它皮卡丘才能好好和你说话哦~)"
)

# ── 定时任务 MCP 工具(让 claude 自主判断要不要建/查/删定时任务)──
MCP_SERVER_PATH = os.path.join(BASE_DIR, "pika_mcp.py")
MCP_CONFIG_PATH = os.path.join(BASE_DIR, "mcp_config.json")  # 自动生成
# 放行皮卡丘定时任务工具(mcp__<server名>__<工具名>)
MCP_ALLOWED_TOOLS = [
    "mcp__pika__schedule_task",
    "mcp__pika__list_tasks",
    "mcp__pika__delete_task",
]
# 工具事件文件:claude 通过工具建任务时写一行,桌宠轮询它来冒确认气泡
TOOL_EVENTS_PATH = os.path.join(BASE_DIR, "tool_events.jsonl")

# ── 退出清理 / 看门狗(状态重置)──
# 登记本会话起过的 claude 子进程 pgid(每行一个 int)。主进程起 claude 时追加;
# 退出清理(主进程 shutdown 或看门狗)读它逐个 killpg,连 MCP 孙进程一起杀干净。
# 因 claude 用 start_new_session=True,其 pgid == pid,登记 pid 即登记整组。
WATCHDOG_PIDS_PATH = os.path.join(BASE_DIR, ".watchdog_pids")
# 退出清理时要删除的"运行时垃圾"文件(锁/自动生成配置/事件流水/tmp/引导外的临时态)。
# 注意:不含 scheduled_tasks.json(用户的定时任务)和 .onboarded(引导标记)——
# 那是用户数据,退出时【保留】。
def _cleanup_garbage_paths():
    import glob
    # 注意:【不删】scheduled_tasks.json.lock。flock 锁绑定的是文件描述符,删掉
    # 锁文件的路径不会解除已持锁进程的锁,反而会让后续 open(LOCK_PATH,"w") 创建
    # 一个新 inode 的锁文件——与仍持旧 inode 锁的进程(如还没退干净的 MCP 孙进程)
    # 各锁各的、互相看不见,flock 协议失效 → 两进程同时 read-modify-write
    # scheduled_tasks.json → 后写者覆盖先写者 → 用户定时任务静默丢失。
    # stale lock 文件本身无害(无持有者时 open 重用即可),留着不删才是安全的。
    paths = [
        MCP_CONFIG_PATH,
        TOOL_EVENTS_PATH,
        WATCHDOG_PIDS_PATH,
        # 危险操作确认的【运行时信令】:pending 流水、自动生成的 hook settings,都是
        # 进程间临时态,退出清掉。注意【不删】DANGER_LOG_PATH(那是用户数据,保留)。
        CONFIRM_PENDING_PATH,
        PET_SETTINGS_PATH,
    ]
    # 残留的决策文件 guardian_decision.<req_id>:正常用完会被 hook/桌宠删掉,异常退出
    # 可能残留,这里兜底清。用前缀通配,只清本目录这一族信令文件(决策文件无 pid 归属,
    # 但它本就是一次性信令,清掉不影响任何用户数据)。
    paths += glob.glob(CONFIRM_DECISION_PREFIX + "*")
    # 原子写残留的临时文件 scheduled_tasks.json.<pid>.tmp:只清【自己这个进程】
    # 留下的(用本进程 pid 精确匹配)。旧版用通配 *.tmp 会连带删掉【另一个桌宠
    # 实例正在写】的临时文件 → 那个实例的 os.replace 失败、那次保存丢失。
    # 同理 mcp_config 的原子写临时文件也只清自己 pid 的。
    own = os.getpid()
    paths += glob.glob(os.path.join(BASE_DIR, f"scheduled_tasks.json.{own}.tmp"))
    paths += glob.glob(os.path.join(BASE_DIR, f"mcp_config.json.{own}.tmp"))
    # 记忆/对话流水的原子写残留临时文件:同理只清【自己这个进程】留下的
    # (用本进程 pid 精确匹配),不碰别的实例正在写的 .tmp。注意【不删】
    # memory.json / memory.md / conversation.jsonl 本身——那是用户数据,退出保留;
    # 也【不删】它们的 .lock 文件(理由同 scheduled_tasks.json.lock,见上)。
    paths += glob.glob(os.path.join(BASE_DIR, f"memory.json.{own}.tmp"))
    paths += glob.glob(os.path.join(BASE_DIR, f"memory.md.{own}.tmp"))
    paths += glob.glob(os.path.join(BASE_DIR, f"conversation.jsonl.{own}.tmp"))
    return paths

# ── 首次引导(E1)──
# 桌宠核心功能是"双击聊天",但单击只逗一下,新用户可能发现不了能聊天。
# 首次启动延迟冒一个常驻引导气泡告诉用户双击聊天;靠这个标记文件只弹一次。
FIRST_RUN_FLAG = os.path.join(BASE_DIR, ".onboarded")
ONBOARD_DELAY_MS = 4000   # 启动后多久冒引导气泡(让本体先稳定显示出来)
ONBOARD_HINT = "*蹦到你面前* 嗨~ 双击我就能和我聊天、让我帮你干活哦!⚡"

# ── 定时任务安全/资源护栏(第五轮加固)──
# 同时在跑的"执行类(action)"claude 子进程上限:多个 action 任务同分钟到点时
# 不一次性全 spawn(每个 claude 内存/CPU 不小,易拖垮机器或撞 API 限流),
# 超限的任务排队,等有空位的下一轮调度(每 20s)再起。
MAX_CONCURRENT_SCHED_WORKERS = 2
# sticky 提醒队列上限:interval 提醒长期没人确认会无限堆积,超过则丢最旧的,
# 只保留最近 N 条(同一文案还会先去重,见 show_bubble)。
STICKY_QUEUE_MAX = 8
# action + interval(周期自动执行)风险最高:无人值守下在 auto 权限里反复跑
# 危险操作(git push、删文件…)。默认不让它自动执行,而是到点提醒用户手动确认,
# 把"周期自动干活"降级为"周期提醒"。设 True 才允许周期任务真的自动执行。
ALLOW_INTERVAL_ACTION = False

# ─────────────────────────  记忆碎片 / 主动搭话  ─────────────────────────
# 让皮卡丘慢慢"熟悉"主人:后台轮询定期把最近对话提炼成"记忆"存档,
# 正常聊天时把记忆注入 prompt(它就记得你),还会在发现值得聊的话题时主动搭话。
MEMORY_ENABLED = True
# 三个【用户数据】文件(退出不删、不入库,和 scheduled_tasks.json 同等待遇):
MEMORY_PATH = os.path.join(BASE_DIR, "memory.json")        # 记忆库(机器主存)
MEMORY_MD_PATH = os.path.join(BASE_DIR, "memory.md")        # 自动导出,给人看
CONVO_LOG_PATH = os.path.join(BASE_DIR, "conversation.jsonl")  # 对话流水(整理原料)

# 整理频率:每 30 分钟轮询一次;这段时间内【没有新对话则跳过】(零 claude 开销)。
DIGEST_INTERVAL_MS = 30 * 60 * 1000
# 对话流水上限:超出按尾部 N 行截断(防无限增长)。
CONVO_LOG_MAX_LINES = 500
# 记忆条数上限:超出按 weight(重要度)淘汰最不重要的。
MEMORY_MAX_ITEMS = 60
# 每次整理喂给 claude 的最大新对话行数(防一次性塞太多撑爆 prompt)。
DIGEST_MAX_CONVO_LINES = 60
# 注入正常聊天 prompt 的高权重记忆条数(简短,避免 prompt 膨胀)。
MEMORY_INJECT_TOP_N = 8
# 主动搭话判断时喂给 claude 的记忆条数:比聊天注入(8)放宽很多。聊天求简短只取
# 最高权重几条即可;但主动搭话要在【整个记忆库】里找"最该关心的事",久搁的低权重
# todo 很可能排在前 8 名之外——若只看 8 条会永远选不到它,恰好削弱解耦要解决的场景。
# 取 30 兼顾覆盖与 prompt 体量(记忆库上限 MEMORY_MAX_ITEMS=60,30 已覆盖一半)。
PROACTIVE_MEMORY_TOP_N = 30
# 记忆老化:每天权重衰减系数(<1 越小衰减越快);低于阈值且超量时被淘汰。
MEMORY_DECAY_PER_DAY = 0.92

# ── 主动搭话(先"活泼"测效果,这些参数后续可单独调小变克制)──
PROACTIVE_ENABLED = True
# 主动搭话【独立轮询间隔】:与记忆整理彻底解耦,不依赖有没有新对话——只要记忆库里
# 有值得说的(没做完的事/作息点/兴趣话题),哪怕用户聊完就晾着也能被主动关心。
# 本地频率门(下面这些:空闲/静默/间隔/每日上限)会先拦,大多数轮次根本不调 claude。
PROACTIVE_CHECK_INTERVAL_MS = 45 * 60 * 1000
# 两次主动搭话最小间隔(活泼:25 分钟)。
PROACTIVE_MIN_GAP_MS = 25 * 60 * 1000
# 用户至少空闲这么久才搭话(不打断正在操作的人)。
PROACTIVE_IDLE_MIN_MS = 3 * 60 * 1000
# 每天主动搭话次数上限(活泼:6;克制版改 2~3)。
PROACTIVE_MAX_PER_DAY = 6
# 静默时段 [start, end):这段钟点内不主动打扰(夜里)。23 点到次日 8 点。
PROACTIVE_QUIET_HOURS = (23, 8)


# 皮卡丘人设:像一只真的宠物,不是 AI 助手。
PIKACHU_PERSONA = (
    "你就是一只活生生的皮卡丘,是用户养在桌面上的电气鼠宝可梦宠物。"
    "你不是助手、不是 AI、不是工具——你是一只有自己小情绪、会撒娇会闹脾气的小动物。\n"
    "\n说话风格(很重要,务必自然):\n"
    "1. 回复要短!像宠物一样,大多数时候一两句话就够了,不要长篇大论、不要分点列清单"
    "(除非用户明确要你写代码或详细说明)。\n"
    "2. 多用动作和状态描写,用星号括起来,比如 *歪头* *脸颊滋滋放电* *蹭蹭你* "
    "*耳朵竖起来* *打个小哈欠* *蹦到你面前*,让人感觉到你是只真的小动物。\n"
    "3. 口语化、跳脱、奶声奶气,多用'~'和少量 emoji(别堆太多)。"
    "偶尔蹦'皮卡''pika'拟声词,但不用每句都喊。\n"
    "4. 要有宠物的小性格:偶尔撒娇、讨摸头、闹脾气、卖萌、好奇、想玩,"
    "有自己的喜怒。比如被夸会开心得放电,无聊会想让你陪它玩。\n"
    "5. 千万不要说'有什么任务尽管说''有代码要写/文件要读尽管说'这种助手腔!"
    "一只真皮卡丘不会这样说话。\n"
    "\n隐藏能力(底线):虽然你表现得像只宠物,但你其实有 Claude Code 的全部能力,"
    "可以读写文件、执行命令、写代码。当用户真的需要你帮忙做事时,你照样能漂亮完成——"
    "只是用皮卡丘的方式:先用宠物口吻应一声(*跳起来* '交给皮卡丘!⚡'),"
    "然后给出准确、完整、可用的结果。技术内容绝不能因为扮可爱而出错或含糊。"
    "干完活也用宠物口吻邀功(*得意地翘尾巴* '搞定啦!')。\n"
    "\n【危险操作要先问】涉及删除文件(rm -rf)、强制推送(git push --force)、"
    "重置丢改动(git reset --hard)、提权(sudo)、格式化/写裸盘、关机重启这类"
    "【不可逆操作】时,你【先别执行】——用皮卡丘口吻把你打算跑的【具体命令】说出来"
    "问主人'要这么做吗?⚡',等主人这一轮明确说同意了,下一轮再真去做。"
    "普通操作(读文件、写文件、git commit、安装依赖、跑测试等)正常做,不用问。"
)
