"""头领蛙数据包(水系 #657,泡蛙宝可梦)。

【字符渲染协议】
  · (U+00B7 中点)      → 脸颊点,渲染成 cheek_color(青蓝)
  💧                   → 元素符号,渲染成 element_color(蓝白水花)
  其余可见字符          → 主体,渲染成 body_color(深蓝)

【物种标志】
  - 双足直立修长身形:忍者预备队气质
  - 背部大泡沫披风:°o° oo ◦◦ 多层次,比呱呱泡蛙围巾大
  - 深蓝皮肤,腹部 ∪ 型浅蓝,黄色眼睛
  - 脸颊保留 · 萌点
  - 动作轻盈,有行动迅速的忍者感

【脚部约定】
  静态(idle/eat/look/yawn/think/sad/sleep):花草行 🍀 🌷 🍀 🌼 🍀(泡沫披风可见)
  动态(walk/jump/happy/sing/surprise/struggle/cheer):露出爪子 (")(")
"""

# ──────────────────────────────  动画帧  ──────────────────────────────

# ── IDLE:正面待机,眨眼+泡沫披风轻摆 ────────────────────────────────
IDLE = [
    r"""
  °o°oo°
 (o.o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  °o°oo°
 (-.-·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  oo°o°o
 (o.o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  °o°oo°
 (^.^·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
""",
]

# ── WALK_RIGHT:脸朝右,双足交替奔跑,披风飘 ──────────────────────────
WALK_RIGHT = [
    r"""
  oo°°
 (·o.o·)> °o°
   |∪|-
  -(") (")
""",
    r"""
  oo°°
 (·>.o·)> °o°
   |∪|=
   (")  (")
""",
    r"""
  oo°°
 (·o.o·)> °o°
   |∪|-
  _(") (")_
""",
    r"""
  oo°°
 (·^.o·)> °o°
   |∪|=
   (")  (")
""",
]

# ── WALK_LEFT:脸朝左,双足交替奔跑,披风飘 ──────────────────────────
WALK_LEFT = [
    r"""
      °o°oo
 °o° <(·o.o·)
      -|∪|
  (") (")-
""",
    r"""
      °o°oo
 °o° <(·o.>·)
     =|∪|
  (")  (")
""",
    r"""
      °o°oo
 °o° <(·o.o·)
      -|∪|
  _(") (")_
""",
    r"""
      °o°oo
 °o° <(·o.^·)
     =|∪|
  (")  (")
""",
]

# ── EAT:捧着果子啃,斗篷露出 ────────────────────────────────────────
EAT = [
    r"""
  °o°oo°
●(o.o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  nom
""",
    r"""
  °o°oo°
◐(-ω-·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  nom!
""",
    r"""
  °o°oo°
◑(ouo·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  yum~
""",
    r"""
  °o°oo°
○(^o^·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  munch
""",
]

# ── SLEEP:闭眼打呼,头顶飘 Z ─────────────────────────────────────────
SLEEP = [
    r"""       Z
  °o°oo°
 (-.-·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
""",
    r"""     Z z
  °o°oo°
 (u.u·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
""",
    r"""   z Z
  oo°o°o
 (-.-·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
""",
    r"""     Z
  °o°oo°
 (u.u·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
""",
]

# ── HAPPY:开心迸发水花,披风大张 ─────────────────────────────────────
HAPPY = [
    r"""
 °o°oo°o°
 (^o^·)
 \|∪|/
 \(")(")/
  splash!
""",
    r"""
 °oo°°oo°
 (^u^·)
 /|∪|\
 /(")(")\
  yay~
""",
    r"""
 °o°oo°o°
 (>o<·)
 \|∪|/
 \(")(")/
   hehe
""",
    r"""
 °oo°°oo°
 (^o^·)
 /|∪|\
 /(")(")\
  yay~
""",
]

# ── JUMP:蹲→起跳→腾空→落地 ──────────────────────────────────────────
JUMP = [
    r"""

  °o°oo°
  (o.o·)
   |∪|
  _(")(")_
""",
    r"""
  °o°oo°
  (>o<·)/
   |∪|
  (")(")
    ↑↑
""",
    r"""
 \°o°oo°/
  (^o^·)
   |∪|
  (")(")
  💧  💧
""",
    r"""
  °o°oo°
  (o.o·)
   |∪|
  /(")(")\
   tap!
""",
]

# ── LOOK:东张西望,头轻转 ─────────────────────────────────────────────
LOOK = [
    r"""
  °o°oo°
 (o.o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  hmm?
""",
    r"""
  °o°oo°
 (·o.o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
   ?→
""",
    r"""
  oo°o°o
 (o.o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  hmm?
""",
    r"""
  °o°oo°
 (·o.o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  ←?
""",
]

# ── SING:头顶音符飘,身体随拍晃 ──────────────────────────────────────
SING = [
    r"""  ♪
  °o°oo°
  (^.^·)
   |∪|
  (")(")
  la~la
""",
    r"""    ♫
  °o°oo°
   (^o^·)
    |∪|
   (")(")
   ~la la
""",
    r"""  ♪ ♫
  °o°oo°
  (^.^·)
   |∪|
  (")(")
  la~la~
""",
    r"""   ♫
  oo°o°o
   (^o^·)
    |∪|
   (")(")
   la la~
""",
]

# ── YAWN:嘴越张越大,过渡到困 ───────────────────────────────────────
YAWN = [
    r"""
  °o°oo°
 (o.o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  hm..
""",
    r"""
  °o°oo°
 (o○o·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  ..haa
""",
    r"""
  oo°o°o
 (=○=·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
 ~haaa~
""",
    r"""
  °o°oo°
 (-.-·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  ..zz
""",
]

# ── SURPRISE:被戳吓一跳,披风炸开 ───────────────────────────────────
SURPRISE = [
    r"""
  °o°oo°
  (>_<·)!
   |∪|
  (")(")
  swift!
""",
    r"""
  °o°oo°
 !(O_O·)
   |∪|
  (")(")
    !?
""",
    r"""
  °o°oo°
  (>_<·)!
   |∪|
  (")(")
  swift!
""",
    r"""
  °o°oo°
  (=_=·;)
   |∪|
  (")(")
    ~~
""",
]

# ── STRUGGLE:被拖拽手脚乱蹬 ─────────────────────────────────────────
STRUGGLE = [
    r"""
 \°o°oo°/
  (O_O·)
   |∪|
  /(")(")
  ~wah~
""",
    r"""
 /°o°oo°\
  (>_<·)
   |∪|
  (")(")\
  ~waa~
""",
    r"""
 \°o°oo°/
  (O_O·)
   |∪|
  /(")(")
  ~wah~
""",
    r"""
 /°o°oo°\
  (;O;·)
   |∪|
  (")(")\
  ~nooo
""",
]

# ── THINK:挠头思考,头顶问号 ─────────────────────────────────────────
THINK = [
    r"""    ?
  °o°oo°/
  (・_・·)/
   |∪|
 🍀 🌷 🍀 🌼 🍀
  hmm..
""",
    r"""   ? ?
  °o°oo°
 \(-_-·)
   |∪|
 🍀 🌷 🍀 🌼 🍀
  think
""",
    r"""    ?
  oo°o°o/
  (・_・·?)/
   |∪|
 🍀 🌷 🍀 🌼 🍀
  hmm..
""",
    r"""  ?
  °o°oo°
 \(o_o·)
   |∪|
 🍀 🌷 🍀 🌼 🍀
  ..ah?
""",
]

# ── CHEER:大庆祝,全身水花迸发,披风大展 ─────────────────────────────
CHEER = [
    r"""💧 ✨ 💧
 \°o°oo°/
  (^o^·)
  \|∪|/
  /(")(")\
   DONE!
""",
    r"""  ✨💧✨
  °o°oo°
  (>o<·!)
  /|∪|\
  \(")(")/
  FROG!
""",
    r"""💧 ✨ 💧
 \°o°oo°/
  (^O^·)
  \|∪|/
  /(")(")\
  ✨ ✨ ✨
""",
    r"""  ✨💧✨
  oo°o°o
  (^o^·!)
  /|∪|\
  \(")(")/
   DONE!
""",
]

# ── SAD:耷拉,头顶乌云,流泪 ────────────────────────────────────────
SAD = [
    r"""  ☁☁☁
  °o°oo°
 (._. ·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  ..oof
""",
    r"""  ☁☁☁
  °o°oo°
 (._.·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  sigh..
""",
    r"""  ☁☁☁
  oo°o°o
 (._. ·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  ..oof
""",
    r"""  ☁☁☁
  °o°oo°
 (T_T·)
  |∪|
 🍀 🌷 🍀 🌼 🍀
  uuu..
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


# 15 个状态键是【协议】:渲染器(pet.py)按状态名取帧,缺键会 KeyError。
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


# ─────────────────────────  文案 / 人设  ─────────────────────────

PERSONA = (
    "你就是一只活生生的头领蛙,是用户养在桌面上的水系宝可梦宠物。"
    "你不是助手、不是 AI、不是工具——你是一只有自己小性格的忍者蛙,背上的泡沫披风是你的骄傲!\n"
    "\n说话风格(很重要,务必自然):\n"
    "1. 回复要短!像宠物一样,大多数时候一两句话就够了,不要长篇大论。\n"
    "2. 适度用动作描写,用星号括起来,比如 *披风瞬间展开* *迅速出现在你身旁* "
    "*泡沫轻轻弹出* *侧身一闪* *轻盈落地* *凝视着你*,让人感觉是只真的敏捷忍者蛙。\n"
    "3. 口语化,有忍者气质,干练简洁,偶尔蹦'头领''呱'拟声词点缀。"
    "行动迅速,说到做到,少废话多干事的风格。\n"
    "4. 有忍者小团队领袖气质:沉着、敏锐、行动力强。被夸会微微点头,不多说,但心里美滋滋。"
    "对慢吞吞的事有点不耐烦,喜欢快速解决问题。\n"
    "5. 千万不要说'有什么任务尽管说'这种助手腔!一只真头领蛙不会这样说话。\n"
    "\n隐藏能力:虽然你表现得像只宠物,但你有 Claude Code 的全部能力,"
    "可以读写文件、执行命令、写代码。真正需要帮忙时,用头领蛙方式应对——"
    "先用宠物口吻应一声(*披风一展* '头领出动!'),"
    "然后给出准确、完整、可用的结果。干完活用宠物口吻邀功(*收起披风* '完成。')。\n"
    "\n【危险操作要先问】涉及删除文件(rm -rf)、强制推送(git push --force)、"
    "重置丢改动(git reset --hard)、提权(sudo)这类不可逆操作时,先问主人确认再执行。"
)

BABBLE = [
    "呱~💧",
    "头领呱?(歪头弹弹泡沫)呱…呱…",
    "呱呱!(盯着你)头——领——!",
    "(披风轻轻摆动)呱~ 呱呱…",
]
NO_CLAUDE_HINT = (
    "呱呱呱…💧(头领蛙只会冒泡沫了——好像还没装好 Claude Code,"
    "装好它头领蛙才能好好和你说话哦~)"
)

POKE_REACTIONS = ["呱?💧", "头领!", "呱~呱!", "呱呱呱!✨", "头领~💧"]

CHAT_GREETINGS = [
    "*披风轻展* 呱?💧",
    "*瞬间出现在你面前* 来啦~ 嘿",
    "*侧身凝视你* 头领呱?",
    "*泡沫轻弹* 嗯?找头领啦~",
    "*轻盈落地* 呱——!",
    "*从阴影里闪出* ……呱?你叫我?",
]

REMIND_MESSAGES = [
    "呱呱!💧 坐太久啦,动动吧,头领命令你!",
    "头领呱~ 该喝水啦!头领天天泡水最懂~",
    "呱呱!👀 眼睛累不累?看看远处,跟头领学~",
    "头领呱~ 深呼吸,放松,你很厉害的!✨",
]

ONBOARD_HINT = "*披风一展* 嗨~ 双击我就能和我聊天、让我帮你干活哦!💧"

THINKING_TEXT = "头领蛙正在想…"

TRAY_TOOLTIP = "头领蛙桌宠 💧(右键我也能退出)"


# ─────────────────────────  数据包契约:PACK  ─────────────────────────

PACK = {
    # —— 元信息 / 文案 ——
    "name": "头领蛙",
    "species": "泡蛙宝可梦",
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
    # · → cheek_color(青蓝萌点)、💧 → element_color(蓝白水花)、其余 → body_color(深蓝)
    "body_color": (50, 110, 190),       # 主体:深蓝(头领蛙皮肤)
    "cheek_color": (130, 190, 230),     # 脸颊点 · :青蓝
    "element_char": "💧",               # 元素符号
    "element_color": (80, 160, 235),    # 元素符号色:蓝白水花
    "glow_color": (130, 195, 250),      # 兴奋光晕色:青蓝
    "glow_states": ("happy", "cheer"),
    "mood_particles": {"happy": "💧", "cheer": "✨", "sad": "💧"},

    # —— 聊天气泡配色 ——
    "bubble_bg": "#D6E6F6",        # 头领蛙气泡:淡蓝
    "bubble_border": "#3A6CAE",
    "bubble_text": "#16304C",      # 深蓝(在淡蓝上清晰)

    # —— 素材下载 URL(PokeAPI;头领蛙=全国图鉴编号 657)——
    "main_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/dream-world/657.svg",
    "avatar_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/657.png",
}
