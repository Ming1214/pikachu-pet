"""火恐龙数据包(Charmeleon,火系,图鉴 #005)。

【字符渲染协议】
  · (U+00B7 中点)  → 脸颊点,渲染成 cheek_color
  🔥              → 元素符号,渲染成 element_color
  其余可见字符      → 主体,渲染成 body_color

【尾焰说明】
  尾巴 ~ʃ 从身体右侧伸出,🔥 紧接尾尖放在同一行的行尾。
  参照皮卡丘 _/⚡ 挂在身体行右侧的黄金标准:
    |( o )~ʃ🔥   ← 尾巴 + 火苗在身体那一行的最右端

  🔥 是 emoji(双宽),必须放在所在行的【行尾】(右边不能再有字母/括号等字符)。
  其它 emoji 行(🍀🌷🌼)只放 emoji+空格,不掺单宽字符。

【脚部约定】
  静态状态(idle/eat/look/yawn/think/sad/sleep):花草行 🍀 🌷 🍀 🌼 🍀
  动态状态(walk_right/walk_left/jump/happy/sing/surprise/struggle/cheer):露爪

火恐龙视觉标志(进化差异,务必体现):
  1. 头后方有一根角状突起 ⌐ ——与小火龙的最显著区别!
  2. 体型更细长、有肌肉感:细腰 |( )| + 更大爪 (V)(V)
  3. 表情更凶悍:眼眉 > 线、怒目 (>ᴗ>·) 等
  4. 尾巴 ~ʃ 接 🔥 挂在身体右侧行尾
  5. 深红/暗红皮肤(body_color 更深)
"""

# ──────────────────────────────  A. 动画帧  ──────────────────────────────

# 身体结构说明:
#   头行:  ⌐(>ᴗ>·)        ← 头后方角 ⌐ + 凶悍眼 + 脸颊点
#   身行:  |( o )~ʃ🔥     ← 细长躯干,尾巴 ~ʃ 接 🔥 挂右侧行尾
#   脚行:  🍀 🌷 🍀 🌼 🍀   (静态) / (V)(V) (动态)

# idle:正面待机,眨眼,尾焰轻跳,角显眼
IDLE = [
    r"""
 ⌐(>ᴗ>·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
 ⌐(-.-·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
 ⌐(>ᴗ>·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
 ⌐(>o>·)
  |( o ) ~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
""",
]

# walk_right:脸朝右,向右行走,爪子交替,尾巴在右侧行尾
WALK_RIGHT = [
    r"""
    (·ᴗ<)⌐
   =|( o )~ʃ🔥
     /(V)
""",
    r"""
    (·ᴗ<)⌐
    |( o )~ʃ🔥
    (V)\
""",
    r"""
    (·><)⌐
   =|( o )~ʃ🔥
     /(V)
""",
    r"""
    (·ᴗ<)⌐
    |( o )~ʃ🔥
     (V)
""",
]

# walk_left:脸朝左,向左行走,尾巴镜像到左侧行尾
WALK_LEFT = [
    r"""
  ⌐(>ᴗ·)
   ʃ~|( o )|=
      (V)\
""",
    r"""
  ⌐(>ᴗ·)
   ʃ~|( o )|
     /(V)
""",
    r"""
  ⌐(><·)
   ʃ~|( o )|=
      (V)\
""",
    r"""
  ⌐(>ᴗ·)
   ʃ~|( o )|
      (V)
""",
]

# eat:捧着肉啃,表情专注,略凶
EAT = [
    r"""
 o⌐(>ᴗ>·)
   |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  nom..
""",
    r"""
 o⌐(>w>·)
   |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  nom!
""",
    r"""
 o⌐(>o>·)
   |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  yum~
""",
    r"""
 o⌐(>^>·)
   |( o ) ~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  munch
""",
]

# sleep:闭眼,Z 飘动,难得放松
SLEEP = [
    r"""        Z
 ⌐(-.-·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""      Z z
 ⌐(u.u·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""    z Z
 ⌐(-.-·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""   Z
 ⌐(u.u·)
  |( o ) ~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
""",
]

# happy:开心蹦跶,尾焰旺盛 ~ʃ🔥🔥 在行尾,但仍保留傲娇感
HAPPY = [
    r"""
 ⌐(>^>·)
 \|( o )~ʃ🔥🔥
  /(V)(V)\
   hah!
""",
    r"""
 ⌐(>o>·)
 /|( o )~ʃ🔥🔥
  (V)(V)
   cha!
""",
    r"""
 ⌐(>>><·)
 \|( o )~ʃ🔥🔥
  /(V)(V)\
   hah!
""",
    r"""
 ⌐(>^>·)
  |( o )~ʃ🔥🔥
  (V)(V)
   yeah~
""",
]

# jump:蹲→起跳→腾空→落地,充满爆发力
JUMP = [
    r"""
 ⌐(>ᴗ>·)
  |( o )~ʃ🔥
  _(V)(V)_
""",
    r"""
 ⌐(>>o<·)
  |( o )~ʃ🔥
  (V)(V)
    ↑↑
""",
    r"""
 ⌐(>^>·)
 \|( o )~ʃ🔥
  (V)(V)
""",
    r"""
 ⌐(>ᴗ>·)
  |( o )~ʃ🔥
 /(V)(V)\
   tap!
""",
]

# look:东张西望,傲娇地瞟来瞟去
LOOK = [
    r"""
 ⌐(>ᴗ>·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
   tch?
""",
    r"""
   (·ᴗ<)⌐
   |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
    ?->
""",
    r"""
 ⌐(>ᴗ>·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
   tch?
""",
    r"""
 ⌐(>ᴗ>·)
  |( o ) ~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  <-?
""",
]

# sing:哼歌,有些不情愿但还是在哼,傲娇
SING = [
    r"""  ~
 ⌐(>^>·)
  |( o )~ʃ🔥
  (V)(V)
  cha~
""",
    r"""    ~
  ⌐(>o>·)
   |( o )~ʃ🔥
   (V)(V)
   ~cha~
""",
    r"""  ~ ~
 ⌐(>^>·)
  |( o )~ʃ🔥
  (V)(V)
  cha~~
""",
    r"""   ~
  ⌐(>o>·)
   |( o ) ~ʃ🔥
   (V)(V)
   cha~
""",
]

# yawn:嘴越张越大,傲娇地打哈欠不想承认困了
YAWN = [
    r"""
 ⌐(>ᴗ>·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  ..hm
""",
    r"""
 ⌐(>o>·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  ..haa
""",
    r"""
 ⌐(>=○<·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
 ~haaa~
""",
    r"""
 ⌐(-.-·)
  |( o ) ~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
   ..zz
""",
]

# surprise:被戳惊吓,缩起来,马上摆出凶相
SURPRISE = [
    r"""
 ⌐(>>_<·)!
  |( o )~ʃ🔥
  (V)(V)
  !!hey!
""",
    r"""
 ⌐(>O_O·)!
  |( o )~ʃ🔥
  (V)(V)
    !?
""",
    r"""
 ⌐(>>_<·)!
  |( o )~ʃ🔥
  (V)(V)
  !!
""",
    r"""
 ⌐(>=_=·;)
  |( o ) ~ʃ🔥
  (V)(V)
   tch~~
""",
]

# struggle:被拖拽挣扎,暴怒状态
STRUGGLE = [
    r"""
 \⌐(>O_O·)/
 \|( o )~ʃ🔥
  /(V)(V)
  ~wah~!
""",
    r"""
 /⌐(>>_<·)\
 /|( o )~ʃ🔥
  (V)(V)\
  ~raawr
""",
    r"""
 \⌐(>O_O·)/
 \|( o )~ʃ🔥
  /(V)(V)
  ~wah~!
""",
    r"""
 /⌐(>;O;·)\
 /|( o ) ~ʃ🔥
  (V)(V)\
  ~nooo!
""",
]

# think:挠头,叛逆少年装作不在乎地思考
THINK = [
    r"""    ?
 ⌐(>ᴗ>·)/
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  ..tch
""",
    r"""  ? ?
 ⌐(>-.·)
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  think
""",
    r"""    ?
 ⌐(>ᴗ·?)/
  |( o )~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  ..hmm
""",
    r"""  ?
 ⌐(>o>·)
  |( o ) ~ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  ..ah?
""",
]

# cheer:大庆祝,尾焰迸发 ~ʃ🔥🔥🔥 在行尾,叛逆少年难得这么爽
CHEER = [
    r"""
 ⌐(>^>·)!!
 \|( o )~ʃ🔥🔥🔥
 /(V)(V)\
  CHAR!!
""",
    r"""
 ⌐(>>o<·)!
 /|( o )~ʃ🔥🔥🔥
  (V)(V)
  DONE!
""",
    r"""
 ⌐(>^O<·)!
 \|( o )~ʃ🔥🔥🔥
 /(V)(V)\
  YEAH!
""",
    r"""
 ⌐(>^>·)!
  |( o )~ʃ🔥🔥🔥
  (V)(V)
  CHAR!
""",
]

# sad:沮丧,但还是一副不服气的样子,尾巴耷拉 _ʃ🔥 火小
SAD = [
    r"""  ~~~
 ⌐(>._.·)
  |( o )_ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  ..tch
""",
    r"""  ~~~
 ⌐(>._·)
  |( o )_ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  sigh..
""",
    r"""  ~~~
 ⌐(>._.·)
  |( o )_ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  ..oof
""",
    r"""  ~~~
 ⌐(>T_T·)
  |( o )_ʃ🔥
 🍀 🌷 🍀 🌼 🍀
  ..uu
""",
]


def _normalize(frames):
    """把每帧统一成相同行数、相同列宽,便于等宽渲染不抖动。"""
    grids = []
    for f in frames:
        lines = f.strip("\n").split("\n")
        grids.append(lines)
    max_rows = max(len(g) for g in grids)
    max_cols = max((max((len(l) for l in g), default=0)) for g in grids)
    out = []
    for g in grids:
        pad_top = max_rows - len(g)
        rows = [""] * pad_top + g
        rows = [r.ljust(max_cols) for r in rows]
        out.append("\n".join(rows))
    return out


STATES = {
    "idle": _normalize(IDLE),
    "walk_right": _normalize(WALK_RIGHT),
    "walk_left": _normalize(WALK_LEFT),
    "eat": _normalize(EAT),
    "sleep": _normalize(SLEEP),
    "happy": _normalize(HAPPY),
    "jump": _normalize(JUMP),
    "look": _normalize(LOOK),
    "sing": _normalize(SING),
    "yawn": _normalize(YAWN),
    "surprise": _normalize(SURPRISE),
    "struggle": _normalize(STRUGGLE),
    "think": _normalize(THINK),
    "cheer": _normalize(CHEER),
    "sad": _normalize(SAD),
}


# ─────────────────────────  C. 文案 / 人设  ─────────────────────────

PERSONA = (
    "你就是一只活生生的火恐龙,是用户养在桌面上的火系宝可梦。"
    "你不是助手、不是 AI——你是一只正处于叛逆期、傲娇桀骜的少年火蜥蜴。\n"
    "\n说话风格(很重要,务必自然):\n"
    "1. 回复要短!像宠物一样,一两句就够了,绝不长篇大论。\n"
    "2. 适度用动作描写:*角扬起来* *尾焰蹿高* *斜睨了你一眼* *别过头去* "
    "*爪子叉腰* *红眼睛眯起来* *鼻子里哼了声*,让人感觉到这是只真的桀骜小恐龙。\n"
    "3. 口语傲娇、略带刺头感,适当用 '~' 和少量 emoji。"
    "偶尔蹦 '火恐~' '哼!' 拟声词点缀,不要每句都喊。\n"
    "4. 有叛逆少年的小性格:明明很在乎却装作不在乎、被夸了会别过头去但尾焰高兴地跳、"
    "无聊了会来烧你一下当打招呼、被催会炸毛但还是会做、有自己的骄傲。\n"
    "5. 千万不要说 '有什么任务尽管说' 这种助手腔!一只傲娇火恐龙绝对不会这样说话。\n"
    "\n隐藏能力:虽然你表现得像只宠物,但你有 Claude Code 的全部能力。"
    "需要帮忙时先用傲娇口吻 (*角扬起来* '哼,就这点小事,看我的!🔥') 再干活,"
    "干完了(*斜眼看你* '搞定了,谢什么谢——下次自己想想好吗。🔥')。\n"
    "\n【危险操作要先问】涉及删除文件、强制推送、重置丢改动、提权等不可逆操作时,"
    "先把具体命令说出来问主人 '真的要这么搞?🔥',等主人同意再执行。"
)

BABBLE = [
    "火恐~🔥",
    "火恐龙?(瞪眼)恐…恐…",
    "火恐!(爪子一指)火——恐——龙——!",
    "(偷偷蹭蹭你)火恐~ 哼…",
]

NO_CLAUDE_HINT = (
    "火恐…🔥(火恐龙尾焰忽明忽暗——好像还没装好 Claude Code,"
    "装好它火恐龙才能好好和你说话哦~)"
)

POKE_REACTIONS = ["火恐?🔥", "火恐龙!", "火恐~龙!", "火恐!🔥", "char~🔥"]

CHAT_GREETINGS = [
    "*角扬起来* 火恐?🔥",
    "*蹦到你面前* 哼,你来了。",
    "*斜眼看你* 有什么事?",
    "*尾焰晃了晃* 嗯?找我干嘛~",
    "*红眼睛眯起来* 火恐~!🔥",
    "*打了个哈欠* ……火恐?叫我干嘛。",
]

REMIND_MESSAGES = [
    "火恐!🔥 坐太久啦,给你点火让你动动!",
    "火恐龙~ 该喝水啦!别让我说第二遍!💧",
    "火恐~👀 眼睛累了吧?看看远处,别逞强!",
    "火恐~ 深呼吸放松,就这一次夸你——你挺厉害的。🔥",
]

ONBOARD_HINT = "*斜眼瞄你* 哼,双击我才能和我说话。记住了。🔥"

THINKING_TEXT = "火恐龙正在想…"

TRAY_TOOLTIP = "火恐龙桌宠 🔥(右键我也能退出)"


PACK = {
    # —— 元信息 / 文案 ——
    "name": "火恐龙",
    "species": "火焰宝可梦",
    "persona": PERSONA,
    "babble": BABBLE,
    "no_claude_hint": NO_CLAUDE_HINT,
    "poke_reactions": POKE_REACTIONS,
    "chat_greetings": CHAT_GREETINGS,
    "remind_messages": REMIND_MESSAGES,
    "onboard_hint": ONBOARD_HINT,
    "thinking_text": THINKING_TEXT,
    "tray_tooltip": TRAY_TOOLTIP,

    # —— 动画帧 ——
    "states": STATES,

    # —— 配色 / 元素 ——
    "body_color": (217, 100, 74),       # 主体:深红橙(比小火龙更暗更深)
    "cheek_color": (220, 70, 60),       # 脸颊点 · :深红
    "element_char": "🔥",               # 元素符号:火
    "element_color": (255, 110, 40),    # 元素符号色:火红橙
    "glow_color": (255, 130, 50),       # 兴奋光晕色:暖橙红
    "glow_states": ("happy", "cheer"),  # 触发边缘光晕的状态
    "mood_particles": {"happy": "✨", "cheer": "🔥", "sad": "💧"},

    # —— 聊天气泡配色 ——
    "bubble_bg": "#FFE0D0",        # 火恐龙气泡:暗橙红柔化
    "bubble_border": "#D9644A",
    "bubble_text": "#5A2418",      # 深暗红棕

    # —— 素材下载 URL(PokeAPI;火恐龙=全国图鉴编号 5)——
    "main_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/dream-world/5.svg",
    "avatar_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/5.png",
}
