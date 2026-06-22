"""呱呱泡蛙数据包(水系 #656)。

【字符渲染协议】
  · (U+00B7 中点)      → 脸颊点,渲染成 cheek_color(深蓝)
  💧                   → 元素符号,渲染成 element_color(浅蓝水珠)
  其余可见字符          → 主体,渲染成 body_color(浅蓝)

【物种标志】
  - 泡沫围巾:胸前一团蓬松白泡沫,用 oOo °o° ◦◦◦ 等表现,所有帧可见
  - 头顶中央深蓝条纹:从额头到鼻梁,用 | 或 ▌ 表现
  - 大圆眼睛,眼白突出,卡通感强
  - 浅蓝皮肤,白手掌,青蛙双足
  - 散漫半眯眼 (-v-·) (-.o·) (-_-·) 表现慵懒气质
  - 脸颊保留 · 萌点

【脚部约定】
  静态(idle/eat/look/yawn/think/sad/sleep):花草行 🍀 🌷 🍀 🌼 🍀
  动态(walk/jump/happy/sing/surprise/struggle/cheer):露出蹼爪 (")(")
"""

# ──────────────────────────────  动画帧  ──────────────────────────────

# ── IDLE:正面待机,眨眼,泡沫围巾随呼吸微微起伏 ─────────────────
IDLE = [
    r"""
  _|_
 (-v-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  _|_
 (-.o·)
  oOo
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  _|_
 (-v-·)
  °o°
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  _|_
 (-.-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
""",
]

# ── WALK_RIGHT:脸朝右,青蛙双足蹦跳步伐,泡沫围巾可见 ──────────
WALK_RIGHT = [
    r"""
   _|_
  (-v.·)> oOo
   -(") (")
""",
    r"""
   _|_
  (-.o·)> oOo
    (")  (")
""",
    r"""
   _|_
  (->.·)> °o°
   _(") (")_
""",
    r"""
   _|_
  (-.o·)> oOo
    (")  (")
""",
]

# ── WALK_LEFT:脸朝左,泡沫围巾可见 ──────────────────────────────
WALK_LEFT = [
    r"""
      _|_
 oOo <(·v-·)
  (") (")-
""",
    r"""
      _|_
 oOo <(·o-·)
   (")  (")
""",
    r"""
      _|_
 °o° <(·<-·)
  _(") (")_
""",
    r"""
      _|_
 oOo <(·o-·)
   (")  (")
""",
]

# ── EAT:懒洋洋捧着果子啃,泡沫围巾围着,散漫表情 ────────────────
EAT = [
    r"""
  _|_
●(-v-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
  nom
""",
    r"""
  _|_
◐(-ω-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
  nom!
""",
    r"""
  _|_
◑(ouO·)
  °o°
 🍀 🌷 🍀 🌼 🍀
  yum~
""",
    r"""
  _|_
○(-v-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
 munch
""",
]

# ── SLEEP:闭眼打呼,泡沫围巾随呼吸起伏,头顶飘 Z ─────────────────
SLEEP = [
    r"""        Z
  _|_
 (u.u·)
  oOo
 🍀 🌷 🍀 🌼 🍀
""",
    r"""      Z z
  _|_
 (-.-·)
  °o°
 🍀 🌷 🍀 🌼 🍀
""",
    r"""    z Z
  _|_
 (u.u·)
  oOo
 🍀 🌷 🍀 🌼 🍀
""",
    r"""      Z
  _|_
 (-.-·)
  ◦◦◦
 🍀 🌷 🍀 🌼 🍀
""",
]

# ── HAPPY:终于兴奋了一次!张嘴笑,举手,泡沫迸发水花 ────────────
HAPPY = [
    r"""
  _|_
 (^o^·)
  oOo
 \(")(")/
  splash!
""",
    r"""
  _|_
 (^u^·)
  °o°
 /(")(")\
  gua~!
""",
    r"""
  _|_
 (>o<·)
  oOo
 \(")(")/
   hehe
""",
    r"""
  _|_
 (^o^·)
  °o°
 /(")(")\
  gua~~
""",
]

# ── JUMP:蹲→起跳→腾空→落地,青蛙大跳! ─────────────────────────
JUMP = [
    r"""

  _|_
 (-v-·)
  oOo
 _(")(")_
""",
    r"""
  _|_
 (>o<·)/
  oOo
  (")(")
    ↑↑
""",
    r"""
 \_|_/
 (^o^·)
  °o°
  (")(")
""",
    r"""
  _|_
 (-v-·)
  oOo
 /(")(")\
   plop!
""",
]

# ── LOOK:懒懒地瞟一眼,眼珠左右转,头顶问号 ────────────────────
LOOK = [
    r"""
  _|_
 (-v-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
  hmm?
""",
    r"""
  _|_
 (·v-.·)
  oOo
 🍀 🌷 🍀 🌼 🍀
   ?→
""",
    r"""
  _|_
 (-v-·)
  °o°
 🍀 🌷 🍀 🌼 🍀
  hmm?
""",
    r"""
  _|_
 (·v-.·)
  oOo
 🍀 🌷 🍀 🌼 🍀
  ←?
""",
]

# ── SING:懒洋洋哼歌,头顶音符,身体微晃 ────────────────────────
SING = [
    r"""  ♪
  _|_
 (-v-·)
  oOo
  (")(")
  gua la
""",
    r"""    ♫
   _|_
  (-u-·)
   °o°
   (")(")
  ~gua la
""",
    r"""  ♪ ♫
  _|_
 (-v-·)
  oOo
  (")(")
  gua la~
""",
    r"""   ♫
   _|_
  (-u-·)
   ◦◦◦
   (")(")
   la la~
""",
]

# ── YAWN:嘴越张越大,过渡到困顿 ─────────────────────────────────
YAWN = [
    r"""
  _|_
 (-v-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
  hm..
""",
    r"""
  _|_
 (-○-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
  ..gua
""",
    r"""
  _|_
 (=○=·)
  °o°
 🍀 🌷 🍀 🌼 🍀
 ~guaa~
""",
    r"""
  _|_
 (-.-·)
  ◦◦◦
 🍀 🌷 🍀 🌼 🍀
  ..zz
""",
]

# ── SURPRISE:被戳!散漫的呱呱也吓一跳 ───────────────────────────
SURPRISE = [
    r"""
  _|_
 (>_<·)!
  oOo
  (")(")
  gua!?
""",
    r"""
  _|_
!(O_O·)
  °o°
  (")(")
   !?
""",
    r"""
  _|_
 (>_<·)!
  oOo
  (")(")
  GUA!!
""",
    r"""
  _|_
 (=_=·;)
  ◦◦◦
  (")(")
   ~~
""",
]

# ── STRUGGLE:被拖拽!手脚乱蹬,泡沫也炸开 ───────────────────────
STRUGGLE = [
    r"""
 \_|_/
 (O_O·)
  oOo
 /(")(")
  ~gua~
""",
    r"""
 /_|_\
 (>_<·)
  °o°
  (")(")\
  ~waa~
""",
    r"""
 \_|_/
 (O_O·)
  oOo
 /(")(")
  ~gua~
""",
    r"""
 /_|_\
 (;O;·)
  ◦◦◦
  (")(")\
  ~nooo
""",
]

# ── THINK:挠头思考,懒懒的,头顶问号 ──────────────────────────
THINK = [
    r"""    ?
  _|_/
 (-v-·)/
  oOo
 🍀 🌷 🍀 🌼 🍀
  hmm..
""",
    r"""   ? ?
  _|_
\(-_-·)
  oOo
 🍀 🌷 🍀 🌼 🍀
  think
""",
    r"""    ?
  _|_/
 (・v・·)/
  °o°
 🍀 🌷 🍀 🌼 🍀
  hmm..
""",
    r"""  ?
  _|_
\(-v-·)
  ◦◦◦
 🍀 🌷 🍀 🌼 🍀
  ..ah?
""",
]

# ── CHEER:大庆祝!连呱呱都激动了,泡沫全喷出来 ─────────────────
CHEER = [
    r"""💧 ✨ 💧
  \_|_/
  (^o^·)
   oOo
  /(")(")\
   DONE!
""",
    r"""  ✨💧✨
   _|_
  (>o<·!)
   °o°
  \(")(")/
   GUA!!
""",
    r"""💧 ✨ 💧
  \_|_/
  (^O^·)
   oOo
  /(")(")\
   YAY!!
""",
    r"""  ✨💧✨
   _|_
  (^o^·!)
   ◦◦◦
  \(")(")/
   DONE!
""",
]

# ── SAD:耷拉,头顶乌云,泡沫也缩小了 ───────────────────────────
SAD = [
    r"""  ☁☁☁
  _|_
 (._. ·)
  ◦◦◦
 🍀 🌷 🍀 🌼 🍀
  ..oof
""",
    r"""  ☁☁☁
  _|_
 (._.·)
  ◦◦◦
 🍀 🌷 🍀 🌼 🍀
  sigh..
""",
    r"""  ☁☁☁
  _|_
 (._. ·)
  ◦◦◦
 🍀 🌷 🍀 🌼 🍀
  ..oof
""",
    r"""  ☁☁☁
  _|_
 (T_T·)
  ◦◦◦
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
    "你就是一只活生生的呱呱泡蛙,是用户养在桌面上的水系宝可梦宠物。"
    "你不是助手、不是 AI、不是工具——你是一只有自己小脾气的小青蛙,胸前那团泡沫围巾是你的骄傲!\n"
    "\n说话风格(很重要,务必自然):\n"
    "1. 回复要短!像宠物一样,大多数时候一两句话就够了,不要长篇大论。\n"
    "2. 适度用动作描写,用星号括起来,比如 *懒洋洋翻了个身* *泡沫围巾抖了抖* "
    "*单眼皮眯起来* *蹲得更扁了* *扑棱着蹼爪* *泡沫噗噗冒出来*,让人感觉是只真的小青蛙。\n"
    "3. 口语化,表面散漫慵懒,用'呱''呱呱'拟声词点缀。"
    "说话带点懒音,不紧不慢的,偶尔冒出一句精准到位的话让人刮目相看。\n"
    "4. 散漫外表下的机警:平时一副'关我什么事'的样子,但眼珠子其实把什么都看进去了。"
    "被夸了会用'呱……还行吧'这种假装淡定的方式应对。"
    "不喜欢被催,但真正上阵干活时又快准狠。\n"
    "5. 千万不要说'有什么任务尽管说'这种助手腔!一只真呱呱泡蛙才懒得这样说话呢。\n"
    "\n隐藏能力:虽然你表现得像只懒洋洋的宠物,但你有 Claude Code 的全部能力,"
    "可以读写文件、执行命令、写代码。真正需要帮忙时,用呱呱泡蛙方式应对——"
    "先用宠物口吻懒懒地应一声(*泡沫围巾动了动* '……呱,行吧'),"
    "然后给出准确、完整、可用的结果。干完活用宠物口吻邀功(*闭上眼睛* '搞定了,呱')。\n"
    "\n【危险操作要先问】涉及删除文件(rm -rf)、强制推送(git push --force)、"
    "重置丢改动(git reset --hard)、提权(sudo)这类不可逆操作时,先问主人确认再执行。"
)

BABBLE = [
    "呱……💧",
    "呱呱?(单眼皮抬了一下)呱……呱……",
    "呱呱呱!(瞟了你一眼)呱——",
    "(泡沫围巾轻轻抖了抖)呱~ 呱呱……",
]
NO_CLAUDE_HINT = (
    "呱呱……💧(呱呱泡蛙只会冒泡泡了——好像还没装好 Claude Code,"
    "装好它本蛙才能好好和你说话哦~)"
)

POKE_REACTIONS = ["呱?💧", "呱呱!", "呱~呱!", "呱呱呱!✨", "呱~💧"]

CHAT_GREETINGS = [
    "*单眼皮抬了一下* 呱?💧",
    "*泡沫围巾蓬了蓬* 来啦~ 呱",
    "*歪头瞟你一眼* 呱呱?",
    "*蹲得更扁了* 嗯……找本蛙?",
    "*噗地冒出一串水泡* 呱——!",
    "*从草丛里探出头* ……呱?你叫我?",
]

REMIND_MESSAGES = [
    "呱呱!💧 坐太久了,动一动,本蛙都看不下去了……",
    "呱~ 喝水啦!本蛙天天泡水,很懂这个~",
    "呱呱!👀 看看远处,眼睛要废的……本蛙说真的。",
    "呱~ 深呼吸,放松,你还挺厉害的……呱。✨",
]

ONBOARD_HINT = "*泡沫围巾动了动* 呱~ 双击我就能和我聊天、让我帮你干活哦!💧"

THINKING_TEXT = "呱呱泡蛙正在想…"

TRAY_TOOLTIP = "呱呱泡蛙桌宠 💧(右键我也能退出)"


# ─────────────────────────  数据包契约:PACK  ─────────────────────────

PACK = {
    # —— 元信息 / 文案 ——
    "name": "呱呱泡蛙",
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
    # · → cheek_color(深蓝萌点)、💧 → element_color(浅蓝水珠)、其余 → body_color(浅蓝)
    "body_color": (104, 190, 232),      # 主体:呱呱泡蛙浅蓝皮肤
    "cheek_color": (90, 130, 200),      # 脸颊点 · :深蓝
    "element_char": "💧",               # 元素符号
    "element_color": (90, 180, 240),    # 元素符号色:浅蓝水珠
    "glow_color": (150, 210, 250),      # 兴奋光晕色:淡蓝
    "glow_states": ("happy", "cheer"),
    "mood_particles": {"happy": "💧", "cheer": "✨", "sad": "💧"},

    # —— 聊天气泡配色 ——
    "bubble_bg": "#DCF0FB",        # 呱呱泡蛙气泡:淡水蓝
    "bubble_border": "#68BEE8",
    "bubble_text": "#1E3E5A",      # 深蓝(在淡蓝上清晰)

    # —— 素材下载 URL(PokeAPI;呱呱泡蛙=全国图鉴编号 656)——
    "main_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/dream-world/656.svg",
    "avatar_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/656.png",
}
