"""皮卡丘桌宠的集中配置(高清 + 电影级动效版)。

所有可调参数都放在这里,方便不动主逻辑就能改外观/行为。
"""

import json
import os
import re
import sys
import threading

# config.py 在 core/ 子目录,而 pokedex 是【项目根】下的真包。确保项目根在 sys.path,
# 这样无论谁(pet.py / MCP 子进程 / 控制台 / 测试)import config,都能连带 import 到
# pokedex。pet.py 通常已加过,这里幂等兜底,避免依赖调用方的 path 设置。
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

import pokedex   # 宝可梦数据包(动画帧 / 配色 / 文案)。见文件末尾 _apply_pack()。

# ── 当前生效的宝可梦 ──
# 桌宠的形象/人设/台词/配色全来自一份「数据包」(pokedex/<名字>.py 的 PACK)。
# 换宝可梦 = 改这里(或在控制台在线切),再在 pokedex/ 下放对应数据包文件即可,
# 代码逻辑零改动。空/拼错/文件缺失都会被加载器安全回退到 pikachu(默认包)。
ACTIVE_POKEMON = "pikachu"
# 先按默认值加载一次 PACK,供本文件顶部就要用的路径/URL 等使用;文件末尾在
# load_overrides() 之后会用最终的 ACTIVE_POKEMON 重载 PACK 并刷新所有派生常量。
_PACK = pokedex.load_pack(ACTIVE_POKEMON)

# ─────────────────────────────  路径  ─────────────────────────────
# config.py 在 core/ 子目录;BASE_DIR 须指【项目根】(上一级),这样所有用户数据
# 文件(memory.json / conversation.jsonl / scheduled_tasks.json 等)和 assets/ 仍
# 落在项目根,不会因源码整理进子目录而搬家或散进 core/。两次 dirname:
#   __file__(core/config.py)→ core/ → 项目根
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# 所有【运行时 / 用户数据】文件统一收纳进 data/ 子目录,不再散落项目根:
#   memory*.json / .md / conversation*.jsonl / scheduled_tasks.json / config_overrides.json /
#   call_log.jsonl / danger_ops.jsonl / tool_events.jsonl / guardian_* / pet_settings.json /
#   .web_console_token / .onboarded / .watchdog_pids / mcp_config.json 等。
# data/ 仍在项目根(= CLAUDE_WORKDIR)下,cwd 内路径 auto 模式读取依旧最稳。
# 源码常量(GUARDIAN_PATH/MCP_SERVER_PATH 等)不属数据,仍指各自源码位置,不进 data/。
DATA_DIR = os.path.join(BASE_DIR, "data")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except OSError:
    # data/ 建不出(只读目录/磁盘满)→ 退回项目根,保证仍能跑(老行为)。
    DATA_DIR = BASE_DIR


def _migrate_root_data_once():
    """一次性把老用户散在项目根的数据文件搬进 data/(幂等:目标已存在则跳过)。

    只在 DATA_DIR 真的是子目录(非回退到 BASE_DIR)时执行。搬【本体】文件,不动
    .lock(flock 绑文件描述符,搬路径无意义)和 .<pid>.tmp(残留,各进程退出自清)。
    搬移用 os.replace 原子改名;任一失败静默跳过(不阻塞启动),老文件留在原地仍可被
    下次重试或手动处理。"""
    if DATA_DIR == BASE_DIR:
        return
    import glob
    # 固定名 + 通配两类:固定名直接列;memory_*/conversation_* 用 glob 兜住所有宝可梦。
    names = [
        "memory.json", "memory.md", "conversation.jsonl",
        "scheduled_tasks.json", "config_overrides.json",
        "call_log.jsonl", "danger_ops.jsonl", "tool_events.jsonl",
        "guardian_pending.jsonl", "pet_settings.json", "mcp_config.json",
        ".web_console_token", ".onboarded", ".watchdog_pids",
    ]
    found = set(names)
    for pat in ("memory_*.json", "memory_*.md", "conversation_*.jsonl"):
        for p in glob.glob(os.path.join(BASE_DIR, pat)):
            if p.endswith((".json", ".md", ".jsonl")):
                found.add(os.path.basename(p))
    for nm in found:
        src = os.path.join(BASE_DIR, nm)
        dst = os.path.join(DATA_DIR, nm)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                os.replace(src, dst)
            except OSError:
                pass


# 立即执行迁移:必须在下面所有数据文件路径常量定义【之前】跑,这样老用户根目录的
# memory.json 等会先被搬进 data/,常量再指向 data/ 时就能命中已搬好的文件。
_migrate_root_data_once()

# 主素材:Dream World 矢量站立插画(SVG,自然正面站姿,可无限放大不失真)
# 文件名按当前宝可梦取,URL 来自数据包(PokeAPI 按图鉴编号)。换宝可梦自动改素材源。
SVG_PATH = os.path.join(ASSETS_DIR, f"{ACTIVE_POKEMON}_stand.svg")
SVG_URL = _PACK["main_url"]
# 备用:Pokémon HOME 高清 3D 渲染(PNG)
HD_PATH = os.path.join(ASSETS_DIR, f"{ACTIVE_POKEMON}_hd_main.png")
HD_URL = _PACK["avatar_url"]
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
# 提醒文案 / 点击气泡 / 开场白都来自数据包(换宝可梦自动换口吻);
# _apply_pack() 会在文件末尾按最终生效的 PACK 刷新这些常量。先赋默认包的值。
REMIND_MESSAGES = _PACK["remind_messages"]

# 被点击时随机冒的小气泡
POKE_REACTIONS = _PACK["poke_reactions"]
BUBBLE_DURATION_MS = 2600

# 打开对话窗时随机一句开场白(像宠物,不是助手)
CHAT_GREETINGS = _PACK["chat_greetings"]

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
# 皮卡丘气泡配色来自数据包(换宝可梦自动变色);_apply_pack() 会在末尾按最终包刷新。
COL_PIKA_BUBBLE = _PACK["bubble_bg"]          # 淡黄(雷电黄柔化)
COL_PIKA_BUBBLE_BORDER = _PACK["bubble_border"]
COL_PIKA_TEXT = _PACK["bubble_text"]          # 深棕(在淡黄上清晰)

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
# 模型:空串 = 不传 --model,跟随 claude CLI 自身配置(默认行为,零回归)。
# 控制台可在线改成具体模型(如 claude-haiku-4-5 让后台整理/搭话降本);
# 非空时 claude_bridge 给每次调用追加 --model。
CLAUDE_MODEL = ""

# 用户在聊天窗发给皮卡丘的图片/文件副本目录(运行时垃圾,退出清,不入库)。
# claude -p 不能直接收附件二进制,要让皮卡丘"看"图/读文件,得把它存到磁盘、把绝对
# 路径写进 prompt,让 claude 用 Read 工具读取(auto 模式下 Read 无需权限)。
# 放在 BASE_DIR(= 项目根 = CLAUDE_WORKDIR)下:cwd 内的路径 auto 模式读取最稳,
# 免去 --add-dir。整个目录退出时由 cleanup.remove_garbage_files() 用 rmtree 清掉。
# 【按 pid 隔离】:目录名带本进程 pid,这样多个桌宠实例各用各的上传目录,退出时
# 各删各的,绝不会删掉另一个实例正在让 claude Read 的副本(同 .tmp 用 pid 精确匹配
# 的谨慎做法)。
CHAT_UPLOAD_DIR = os.path.join(DATA_DIR, f".chat_uploads_{os.getpid()}")
# 单个上传附件大小上限(字节):超过则拒收并提示。原因:① shutil.copy 大文件会同步
# 卡住 UI;② claude 的 Read 工具对大文件本就会截断,发了也读不全,白占磁盘。20MB
# 对图片/文档/表格够用;真要分析超大数据让用户直接把路径告诉皮卡丘更合适。
CHAT_UPLOAD_MAX_BYTES = 20 * 1024 * 1024

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
CONFIRM_PENDING_PATH = os.path.join(DATA_DIR, "guardian_pending.jsonl")  # hook 写、桌宠轮询
# 决策文件:桌宠用户点确认后写 guardian_decision.<req_id>,内容 "allow"/"deny";hook 轮询它
CONFIRM_DECISION_PREFIX = os.path.join(DATA_DIR, "guardian_decision.")
CONFIRM_HOOK_TIMEOUT_SEC = 280     # hook 阻塞等确认的上限(< CLAUDE_TIMEOUT_SEC=500,留余量)
CONFIRM_POLL_INTERVAL_MS = 800     # 桌宠轮询 pending 文件的间隔
PET_SETTINGS_PATH = os.path.join(DATA_DIR, "pet_settings.json")  # 自动生成,经 --settings 挂 hook
GUARDIAN_PATH = os.path.join(BASE_DIR, "procs", "pika_guardian.py")  # hook 脚本(procs/ 子目录)
# 危险操作流水(用户数据,退出【保留】,和 conversation.jsonl 同等待遇):每次命中留痕,可事后查
DANGER_LOG_PATH = os.path.join(DATA_DIR, "danger_ops.jsonl")

# ── 轻量调用日志(可观测性)──
# 每次调 claude(聊天 / 内部纯文本推理)留一行 JSON,记【元数据】不记正文:
# 时间、类型(chat/raw)、耗时秒、成败、prompt 字数、回复字数。用于事后看
# "皮卡丘忙不忙、慢不慢、有没有失败",排查体验问题。【只记长度不记内容】——
# 既可观测又不泄露聊天隐私。属【用户数据】:退出【保留】、不入版本库。
CALL_LOG_PATH = os.path.join(DATA_DIR, "call_log.jsonl")
CALL_LOG_MAX_LINES = 1000   # 超出按尾部 N 行截断,防无限增长(轮转时机见 claude_bridge)


def is_danger_command(command: str) -> bool:
    """判断一条 shell 命令是否命中危险清单。主程序与 hook 脚本共用,确保判定一致。"""
    if not command:
        return False
    return any(p.search(command) for p in DANGER_PATTERNS)


# ── claude 不可用时的拟声兜底台词 ──
# 没装 Claude Code / claude 不在 PATH 时,聊天窗用这些拟声词代替冷冰冰的错误提示:
# 既给用户即时反馈("宠物出声了"),又不至于吓到人。从池里随机挑一句,每次不同。
# 内容来自数据包;_apply_pack() 末尾按最终 PACK 刷新。先赋默认包的值。
PIKA_BABBLE = _PACK["babble"]
# 拟声词后再拼这句,温和点明"说不了完整的话"的原因,免得用户一头雾水。
PIKA_NO_CLAUDE_HINT = _PACK["no_claude_hint"]

# ── 定时任务 MCP 工具(让 claude 自主判断要不要建/查/删定时任务)──
MCP_SERVER_PATH = os.path.join(BASE_DIR, "procs", "pika_mcp.py")  # MCP server(procs/ 子目录)
MCP_CONFIG_PATH = os.path.join(DATA_DIR, "mcp_config.json")  # 自动生成
# 放行皮卡丘定时任务工具(mcp__<server名>__<工具名>)
MCP_ALLOWED_TOOLS = [
    "mcp__pika__schedule_task",
    "mcp__pika__list_tasks",
    "mcp__pika__delete_task",
]
# 工具事件文件:claude 通过工具建任务时写一行,桌宠轮询它来冒确认气泡
TOOL_EVENTS_PATH = os.path.join(DATA_DIR, "tool_events.jsonl")

# ── 退出清理 / 看门狗(状态重置)──
# 登记本会话起过的 claude 子进程 pgid(每行一个 int)。主进程起 claude 时追加;
# 退出清理(主进程 shutdown 或看门狗)读它逐个 killpg,连 MCP 孙进程一起杀干净。
# 因 claude 用 start_new_session=True,其 pgid == pid,登记 pid 即登记整组。
WATCHDOG_PIDS_PATH = os.path.join(DATA_DIR, ".watchdog_pids")
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
        # Web 控制台访问令牌:启动随机生成的一次性信令,退出清(下次启动重新生成)。
        # 注意【不删】CONFIG_OVERRIDES_PATH(用户配置,退出保留)。
        WEB_CONSOLE_TOKEN_PATH,
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
    paths += glob.glob(os.path.join(DATA_DIR, f"scheduled_tasks.json.{own}.tmp"))
    paths += glob.glob(os.path.join(DATA_DIR, f"mcp_config.json.{own}.tmp"))
    # 记忆/对话流水的原子写残留临时文件:同理只清【自己这个进程】留下的
    # (用本进程 pid 精确匹配),不碰别的实例正在写的 .tmp。注意【不删】
    # memory.json / memory.md / conversation.jsonl 本身——那是用户数据,退出保留;
    # 也【不删】它们的 .lock 文件(理由同 scheduled_tasks.json.lock,见上)。
    # 皮卡丘用固定名(memory.json…),其余宝可梦用 memory_<名>.json…——两类都要清,
    # 用通配 memory*.json / conversation*.jsonl 一并兜住(覆盖所有宝可梦的 .tmp 残留)。
    paths += glob.glob(os.path.join(DATA_DIR, f"memory*.json.{own}.tmp"))
    paths += glob.glob(os.path.join(DATA_DIR, f"memory*.md.{own}.tmp"))
    paths += glob.glob(os.path.join(DATA_DIR, f"conversation*.jsonl.{own}.tmp"))
    # 调用日志的轮转原子写残留:只清自己 pid 的 .tmp,不删 call_log.jsonl 本体
    # (用户数据,退出保留;理由同上 danger_ops / conversation)。
    paths += glob.glob(os.path.join(DATA_DIR, f"call_log.jsonl.{own}.tmp"))
    # 配置覆盖文件的原子写残留:只清自己 pid 的 .tmp,不删 config_overrides.json 本体
    # (用户配置,退出保留;理由同 scheduled_tasks.json)。
    paths += glob.glob(os.path.join(DATA_DIR, f"config_overrides.json.{own}.tmp"))
    # pet_settings.json 的原子写残留(_ensure_pet_settings 同样走 <path>.<pid>.tmp):
    # 只清自己 pid 的 .tmp,不删 pet_settings.json 本体。补齐——之前漏了这一条,
    # 崩溃在 write→replace 之间会留下 pet_settings.json.<pid>.tmp 永不回收。
    paths += glob.glob(os.path.join(DATA_DIR, f"pet_settings.json.{own}.tmp"))
    return paths

# ── 首次引导(E1)──
# 桌宠核心功能是"双击聊天",但单击只逗一下,新用户可能发现不了能聊天。
# 首次启动延迟冒一个常驻引导气泡告诉用户双击聊天;靠这个标记文件只弹一次。
FIRST_RUN_FLAG = os.path.join(DATA_DIR, ".onboarded")
ONBOARD_DELAY_MS = 4000   # 启动后多久冒引导气泡(让本体先稳定显示出来)
# 引导文案来自数据包;_apply_pack() 末尾按最终 PACK 刷新。先赋默认包的值。
ONBOARD_HINT = _PACK["onboard_hint"]

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

# ── 记忆按宝可梦隔离 ──
# 不同宝可梦各有各的记忆:换了宝可梦就像换了一只新宠物,从头熟悉你。每只一套独立的
# 记忆文件(memory_<名>.json / .md / conversation_<名>.jsonl)。皮卡丘是默认宝可梦,
# 为平滑兼容【沿用旧文件名】memory.json(老用户的记忆不丢、不用迁移)。
#
# 共享开关 MEMORY_SHARED_ACROSS_POKEMON:
#   True(默认)= 注入聊天/搭话时【合并读所有宝可梦的记忆库】——你跟任何一只说过的事,
#                别的宝可梦也"知道"(更连贯)。但每只仍把【新提炼的记忆写进自己的库】,
#                对话流水也各记各的——隔离的是"归属",共享的是"可见"。
#   False      = 每只只看自己那一份记忆,互不相通(每只独立人格,从零熟悉你)。
# 注意:定时提醒 / 定时任务【始终共享】(存在 scheduled_tasks.json,与记忆无关),
#       不受本开关影响——换哪只宝可梦,闹钟和待办都还在。
MEMORY_SHARED_ACROSS_POKEMON = True


def _mem_basenames(pokemon: str) -> tuple[str, str, str]:
    """按宝可梦名给出 (记忆库, md 导出, 对话流水) 三个【文件名】(不含目录)。

    皮卡丘 → 沿用历史文件名(memory.json / memory.md / conversation.jsonl),
    其余宝可梦 → 带名字后缀(memory_<名>.json 等),互不覆盖。
    """
    name = (pokemon or "pikachu").strip() or "pikachu"
    if name == "pikachu":
        return "memory.json", "memory.md", "conversation.jsonl"
    return f"memory_{name}.json", f"memory_{name}.md", f"conversation_{name}.jsonl"


def memory_paths(pokemon: str | None = None) -> tuple[str, str, str]:
    """按宝可梦名给出 (记忆库, md, 对话流水) 三个【绝对路径】。

    pokemon 省略时用当前 ACTIVE_POKEMON。memory.py 在【每次读写时】调用本函数解析
    路径(而非模块加载时固化),所以控制台在线切换宝可梦后,记忆读写会立刻跟着切到
    对应文件——无需重启。
    """
    if pokemon is None:
        pokemon = ACTIVE_POKEMON
    mem, md, convo = _mem_basenames(pokemon)
    return (os.path.join(DATA_DIR, mem),
            os.path.join(DATA_DIR, md),
            os.path.join(DATA_DIR, convo))


def all_memory_json_paths() -> list[str]:
    """列出磁盘上所有宝可梦的记忆库 json 路径(供"共享读"合并用)。

    扫 DATA_DIR 下的 memory.json(皮卡丘)+ memory_*.json(其余)。退出清理的
    .tmp 残留按 .json.<pid>.tmp 命名,不会被 memory_*.json 通配命中(它要求紧跟 .json
    结尾),所以这里不会误收临时文件。
    """
    import glob
    paths = []
    pika = os.path.join(DATA_DIR, "memory.json")
    if os.path.exists(pika):
        paths.append(pika)
    for p in glob.glob(os.path.join(DATA_DIR, "memory_*.json")):
        # 排除原子写临时文件 memory_x.json.<pid>.tmp(glob 的 * 不跨 . 但保险起见)
        if p.endswith(".json"):
            paths.append(p)
    return paths


# 兼容旧引用:这三个模块级常量保留(memory.py 历史上直接 import 它们)。它们指向
# 【当前 ACTIVE_POKEMON】的记忆文件,在文件末尾 _apply_pack/load_overrides 之后由
# _refresh_memory_paths() 刷新到最终的宝可梦。但 memory.py 已改为运行时调 memory_paths(),
# 不再依赖这几个常量随时正确——它们只作向后兼容的"当前快照"。
MEMORY_PATH, MEMORY_MD_PATH, CONVO_LOG_PATH = memory_paths("pikachu")


def _refresh_memory_paths() -> None:
    """把 MEMORY_PATH 等三个兼容常量刷新到当前 ACTIVE_POKEMON。末尾启动时调用。"""
    global MEMORY_PATH, MEMORY_MD_PATH, CONVO_LOG_PATH
    MEMORY_PATH, MEMORY_MD_PATH, CONVO_LOG_PATH = memory_paths()

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
# 两次主动搭话最小间隔(克制版:60 分钟)。配合更保守的搭话 prompt,真正不骚扰。
PROACTIVE_MIN_GAP_MS = 60 * 60 * 1000
# 用户至少空闲这么久才搭话(不打断正在操作的人)。
PROACTIVE_IDLE_MIN_MS = 3 * 60 * 1000
# 每天主动搭话次数上限(克制版:3。配合保守 prompt + 60 分钟间隔,不打扰)。
PROACTIVE_MAX_PER_DAY = 3
# 静默时段 [start, end):这段钟点内不主动打扰(夜里)。23 点到次日 8 点。
PROACTIVE_QUIET_HOURS = (23, 8)

# ─────────────────────────  本地 Web 控制台  ─────────────────────────
# 一个跟桌宠【同进程】的后台 HTTP 线程:浏览器里实时看状态(动作/思考/各 worker/
# 定时任务/记忆/调用日志/危险操作流水),并在线改配置(模型/开关/数值/人设/记忆)。
# 只绑 127.0.0.1(仅本机)+ 随机 token,不对外暴露。默认开,可在此关。
WEB_CONSOLE_ENABLED = True
WEB_CONSOLE_HOST = "127.0.0.1"     # 死绑本机回环,绝不监听公网
WEB_CONSOLE_PORT = 0               # 0 = 由系统分配空闲端口,启动后打印真实 url
# 访问令牌文件:启动时随机生成写入(0600),浏览器访问需带 ?token=。运行时信令,退出清。
WEB_CONSOLE_TOKEN_PATH = os.path.join(DATA_DIR, ".web_console_token")
# 配置覆盖文件(用户数据,退出【保留】、不入库):控制台改的配置存这里,启动时
# load_overrides() 覆盖回 config 模块属性。和 scheduled_tasks.json 同等待遇。
CONFIG_OVERRIDES_PATH = os.path.join(DATA_DIR, "config_overrides.json")


# 宝可梦人设(像一只真的宠物,不是 AI 助手):来自数据包。
# 注意:控制台可在线改人设并写进 config_overrides.json。_apply_pack() 刷新时会
# 【避让】用户已 override 的常量(见该函数),所以这里赋默认包值不会盖掉用户自定义。
PIKACHU_PERSONA = _PACK["persona"]
# 宝可梦显示名 / 种族名(聊天窗标题、副标题、tooltip、转圈气泡等界面文字用)。
PET_NAME = _PACK["name"]
PET_SPECIES = _PACK["species"]
PET_THINKING_TEXT = _PACK["thinking_text"]
PET_TRAY_TOOLTIP = _PACK["tray_tooltip"]

# ── 渲染:配色 / 元素符号(供 pet.paintEvent 给 ASCII 字符上色)──
# 字符渲染协议:· → 脸颊色、元素符号 → 元素色、其余可见字符 → 主体色。
# 全来自数据包,换宝可梦即换配色(火宝可梦=橙+🔥 等)。
PET_BODY_COLOR = _PACK["body_color"]
PET_CHEEK_COLOR = _PACK["cheek_color"]
PET_ELEMENT_CHAR = _PACK["element_char"]
PET_ELEMENT_COLOR = _PACK["element_color"]
PET_GLOW_COLOR = _PACK["glow_color"]
PET_GLOW_STATES = tuple(_PACK["glow_states"])
PET_MOOD_PARTICLES = dict(_PACK["mood_particles"])


# ─────────────────────  配置覆盖(持久化 / 控制台改配置)  ─────────────────────
# 控制台改的配置存进 config_overrides.json,启动时覆盖回本模块的常量。设计要点:
#  - 只覆盖【本模块已存在】的大写常量(白名单式),杜绝注入任意属性。
#  - tuple 类型常量(如 PROACTIVE_QUIET_HOURS)经 JSON 往返会变 list,这里转回 tuple,
#    保持类型一致(下游 in_quiet_hours 解包 start,end 才不出错)。
#  - 全程 try/except 静默:覆盖文件损坏/缺失都降级用源码默认,绝不让配置问题挡住启动。

# 进程内锁:控制台可能从多个 HTTP 线程并发写配置。save_overrides 是"读全量→合并→
# 写盘",两个线程各读旧 dict 各自合并会互相覆盖。控制台侧的 read-modify-write 用本锁
# 包住(见 web_console._apply_config),保证同进程内配置写串行。供 web_console 持有。
OVERRIDES_LOCK = threading.Lock()


def load_overrides() -> None:
    """把 config_overrides.json 覆盖到本模块属性。【必须在所有常量定义之后调用】。"""
    try:
        if not os.path.exists(CONFIG_OVERRIDES_PATH):
            return
        with open(CONFIG_OVERRIDES_PATH, encoding="utf-8") as f:
            ov = json.load(f)
        if not isinstance(ov, dict):
            return
        g = globals()
        for k, v in ov.items():
            if not (isinstance(k, str) and k.isupper() and k in g):
                continue   # 只认已存在的大写常量,挡住任意键注入
            # 原值是 tuple 而覆盖值是 list → 转回 tuple,保持类型
            if isinstance(g[k], tuple) and isinstance(v, list):
                v = tuple(v)
            g[k] = v
    except Exception:
        pass


def save_overrides(ov: dict) -> bool:
    """原子写 config_overrides.json(pid tmp + os.replace),仿 _ensure_mcp_config。

    ov 是【完整的当前覆盖集】(控制台每次提交都传全量),不是增量。失败返回 False。
    """
    try:
        tmp = f"{CONFIG_OVERRIDES_PATH}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ov, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONFIG_OVERRIDES_PATH)
        return True
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def load_overrides_dict() -> dict:
    """读出当前 config_overrides.json 的原始字典(控制台改某项前先读全量再合并)。"""
    try:
        if os.path.exists(CONFIG_OVERRIDES_PATH):
            with open(CONFIG_OVERRIDES_PATH, encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    return d
    except Exception:
        pass
    return {}


# ── 数据包 → 派生常量的映射 ──
# 键 = 本模块常量名,值 = 从 PACK 里取值的函数。_apply_pack() 据此把当前 PACK
# 刷进这些常量。新增"随宝可梦变"的常量时,在这里加一行即可,集中、不漏。
_PACK_DERIVED = {
    "PIKACHU_PERSONA": lambda p: p["persona"],
    "PET_NAME": lambda p: p["name"],
    "PET_SPECIES": lambda p: p["species"],
    "PET_THINKING_TEXT": lambda p: p["thinking_text"],
    "PET_TRAY_TOOLTIP": lambda p: p["tray_tooltip"],
    "PIKA_BABBLE": lambda p: p["babble"],
    "PIKA_NO_CLAUDE_HINT": lambda p: p["no_claude_hint"],
    "POKE_REACTIONS": lambda p: p["poke_reactions"],
    "CHAT_GREETINGS": lambda p: p["chat_greetings"],
    "REMIND_MESSAGES": lambda p: p["remind_messages"],
    "ONBOARD_HINT": lambda p: p["onboard_hint"],
    "COL_PIKA_BUBBLE": lambda p: p["bubble_bg"],
    "COL_PIKA_BUBBLE_BORDER": lambda p: p["bubble_border"],
    "COL_PIKA_TEXT": lambda p: p["bubble_text"],
    "PET_BODY_COLOR": lambda p: p["body_color"],
    "PET_CHEEK_COLOR": lambda p: p["cheek_color"],
    "PET_ELEMENT_CHAR": lambda p: p["element_char"],
    "PET_ELEMENT_COLOR": lambda p: p["element_color"],
    "PET_GLOW_COLOR": lambda p: p["glow_color"],
    "PET_GLOW_STATES": lambda p: tuple(p["glow_states"]),
    "PET_MOOD_PARTICLES": lambda p: dict(p["mood_particles"]),
    # 素材路径/URL 随宝可梦变:文件名带名字(assets/<名字>_stand.svg),URL 来自包。
    "SVG_PATH": lambda p: os.path.join(ASSETS_DIR, f"{ACTIVE_POKEMON}_stand.svg"),
    "SVG_URL": lambda p: p["main_url"],
    "HD_PATH": lambda p: os.path.join(ASSETS_DIR, f"{ACTIVE_POKEMON}_hd_main.png"),
    "HD_URL": lambda p: p["avatar_url"],
    "AVATAR_PATH": lambda p: os.path.join(ASSETS_DIR, f"{ACTIVE_POKEMON}_hd_main.png"),
}


def _apply_pack(skip_overridden=None) -> None:
    """按当前 ACTIVE_POKEMON 重载 PACK,刷新所有派生常量(_PACK_DERIVED)。

    skip_overridden: 一个常量名集合,这些常量【不】被本函数刷新——用于避让用户在
        控制台显式改过(写进 config_overrides.json)的常量(如自定义人设/气泡色),
        否则换包刷新会把用户的自定义盖掉。ACTIVE_POKEMON 本身不在派生表里,它由
        load_overrides 正常覆盖。全程 try 静默,任何异常都降级保留现值,不挡启动。
    """
    global _PACK
    skip = skip_overridden or set()
    try:
        _PACK = pokedex.load_pack(ACTIVE_POKEMON)
    except Exception:
        return   # 数据包加载彻底失败:保留顶部已加载的默认 _PACK,不崩
    g = globals()
    for name, getter in _PACK_DERIVED.items():
        if name in skip:
            continue   # 用户显式 override 过,尊重用户值
        try:
            g[name] = getter(_PACK)
        except Exception:
            pass       # 单个字段缺失/出错:跳过该常量,保留现值


# 启动加载顺序(顺序很重要):
#   1) load_overrides():把 config_overrides.json 覆盖回常量。这一步让用户可能改过的
#      ACTIVE_POKEMON 生效,也让用户自定义的人设/配色等覆盖值落位。
#   2) _apply_pack(skip=用户 override 过的键):按最终的 ACTIVE_POKEMON 重载数据包,
#      刷新派生常量——但避让用户在第 1 步显式覆盖过的那些,保住用户自定义。
# 这样三种场景都正确:① 默认(无 override)→ 用 pikachu 包;② 只切了宝可梦 →
# 用新包全套;③ 切了宝可梦又自定义了人设 → 新包的形象/台词 + 用户自定义的人设。
load_overrides()
_apply_pack(skip_overridden=set(load_overrides_dict().keys()))
# 记忆文件路径依赖最终的 ACTIVE_POKEMON(可能被 override 改),在其确定后刷新兼容常量。
_refresh_memory_paths()
