"""皮卡丘桌宠的集中配置(高清 + 电影级动效版)。

所有可调参数都放在这里,方便不动主逻辑就能改外观/行为。
"""

import os

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
CLAUDE_TIMEOUT_SEC = 300
CLAUDE_MULTI_TURN = True
# 权限模式:auto = 智能判断安全性(安全放行/危险拦截),适合非交互桌宠。
# 可选 "bypassPermissions"(全放行)/"acceptEdits"(只接受编辑,会卡)。
CLAUDE_PERMISSION_MODE = "auto"

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
    "干完活也用宠物口吻邀功(*得意地翘尾巴* '搞定啦!')。"
)
