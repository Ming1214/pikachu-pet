"""小火龙数据包(Charmander,火系,图鉴 #004)。

【字符渲染协议】
  · (U+00B7 中点)  → 脸颊点,渲染成 cheek_color
  🔥              → 元素符号,渲染成 element_color
  其余可见字符      → 主体,渲染成 body_color

【尾焰说明】
  尾巴 ~ノ 从身体右侧伸出,🔥 紧接尾尖放在同一行的行尾。
  参照皮卡丘 _/⚡ 挂在身体行右侧的黄金标准:
    <( o )~ノ🔥   ← 尾巴 + 火苗在身体那一行的最右端

  🔥 是 emoji(双宽),必须放在所在行的【行尾】(右边不能再有字母/括号等字符)。
  其它 emoji 行(🍀🌷🌼)只放 emoji+空格,不掺单宽字符。

【脚部约定】
  静态状态(idle/eat/look/yawn/think/sad/sleep):花草行 🍀 🌷 🍀 🌼 🍀
  动态状态(walk_right/walk_left/jump/happy/sing/surprise/struggle/cheer):露爪

小火龙视觉标志:
  圆钝吻部 (uᵕu·) 带吻感的小恐龙脸、
  圆肚双足体 <(o)> + 短手感、
  尾巴 ~ノ 接 🔥 挂在身体右侧行尾、
  静态下半身花草
"""

# ──────────────────────────────  A. 动画帧  ──────────────────────────────

# 身体结构说明:
#   头行:  (uᵕu·)
#   身行:  <( o )~ノ🔥   ← 尾巴和火苗都在这里,行尾!
#   脚行:  🍀 🌷 🍀 🌼 🍀  (静态) / (")(") (动态)

# idle:正面待机,眨眼,尾焰轻跳
IDLE = [
    r"""
  (uᵕu·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  (u-u·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  (uᵕu·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""
  (uᵒu·)
  <( o ) ~ノ🔥
 🍀 🌷 🍀 🌼 🍀
""",
]

# walk_right:脸朝右,向右行走,爪子交替
WALK_RIGHT = [
    r"""
   (·ᵕu)>
  =<( o )~ノ🔥
    /(")
""",
    r"""
   (·ᵕu)>
   <( o )~ノ🔥
   (")\
""",
    r"""
   (·>u)>
  =<( o )~ノ🔥
    /(")
""",
    r"""
   (·ᵕu)>
   <( o )~ノ🔥
    (")
""",
]

# walk_left:脸朝左,向左行走,爪子交替。尾巴~ノ🔥 仍挂在身体行【右侧行尾】
# (尾随在身后,且行尾双宽 emoji 不顶歪身体——与其它帧一致;旧版把 ノ 放行首会把
#  整个身体右推一格,与上面的脸错位,已修正)。
WALK_LEFT = [
    r"""
 <(uᵕ·)
 =<( o )~ノ🔥
    (")\
""",
    r"""
 <(uᵕ·)
  <( o )~ノ🔥
   /(")\
""",
    r"""
 <(u<·)
 =<( o )~ノ🔥
    (")\
""",
    r"""
 <(uᵕ·)
  <( o )~ノ🔥
    (")
""",
]

# eat:捧着果子啃,嘴动
EAT = [
    r"""
 o(uᵕu·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  nom..
""",
    r"""
 o(u-w-·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  nom!
""",
    r"""
 o(uouo·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  yum~
""",
    r"""
 o(u^o^·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  munch
""",
]

# sleep:闭眼,Z 飘动
SLEEP = [
    r"""       Z
  (u-u·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""     Z z
  (unu·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""   z Z
  (u-u·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
""",
    r"""  Z
  (unu·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
""",
]

# happy:开心蹦跶,尾焰更旺(多个🔥在行尾)
HAPPY = [
    r"""
  (u^o^·)
 \<( o )~ノ🔥🔥
  /(")(")\
   yay!
""",
    r"""
  (u^u^·)
 /<( o )~ノ🔥🔥
  (")(")
   haa!
""",
    r"""
  (u>o<·)
 \<( o )~ノ🔥🔥
  /(")(")\
   cha~
""",
    r"""
  (u^o^·)
  <( o )~ノ🔥🔥
  (")(")
   yay!
""",
]

# jump:蹲→起跳→腾空→落地
JUMP = [
    r"""
  (uᵕu·)
  <( o )~ノ🔥
  _(")(")_
""",
    r"""
  (u>o<·)
  <( o )~ノ🔥
  (")(")
    ↑↑
""",
    r"""
  (u^o^·)
 \<( o )~ノ🔥
  (")(")
""",
    r"""
  (uᵕu·)
  <( o )~ノ🔥
 /(")(")\
   tap!
""",
]

# look:东张西望,眼睛/脸左右瞟
LOOK = [
    r"""
  (uᵕu·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
   hmm?
""",
    r"""
  (·ᵕu)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
    ?->
""",
    r"""
  (uᵕu·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
   hmm?
""",
    r"""
  (uᵕu·)
  <( o ) ~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  <-?
""",
]

# sing:哼歌,头顶音符飘,身体晃
SING = [
    r"""  ~
  (u^.^·)
  <( o )~ノ🔥
  (")(")
  la la~
""",
    r"""    ~
   (u^o^·)
   <( o )~ノ🔥
   (")(")
   ~la la
""",
    r"""  ~ ~
  (u^.^·)
  <( o )~ノ🔥
  (")(")
  la~la~
""",
    r"""   ~
   (u^o^·)
   <( o )~ノ🔥
   (")(")
   la la~
""",
]

# yawn:嘴越张越大,过渡到困
YAWN = [
    r"""
  (uᵕu·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
   hm..
""",
    r"""
  (uoou·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
   ..haa
""",
    r"""
  (u=○=·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  ~haaa~
""",
    r"""
  (u-u·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
   ..zz
""",
]

# surprise:被戳惊吓,缩起来抖一抖
SURPRISE = [
    r"""
  (u>_<·)!
  <( o )~ノ🔥
  (")(")
   pika!
""",
    r"""
  (uO_O·)!
  <( o )~ノ🔥
  (")(")
    !?
""",
    r"""
  (u>_<·)!
  <( o )~ノ🔥
  (")(")
  !!
""",
    r"""
  (u=_=·;)
  <( o )~ノ🔥
  (")(")
   ~~
""",
]

# struggle:被拖拽挣扎,手脚乱蹬
STRUGGLE = [
    r"""
 \(uO_O·)/
 \<( o )~ノ🔥
  /(")(")
  ~wah~
""",
    r"""
 /(u>_<·)\
 /<( o )~ノ🔥
  (")(")\
  ~waa~
""",
    r"""
 \(uO_O·)/
 \<( o )~ノ🔥
  /(")(")
  ~wah~
""",
    r"""
 /(u;O;·)\
 /<( o )~ノ🔥
  (")(")\
  ~nooo
""",
]

# think:挠头,头顶问号
THINK = [
    r"""    ?
  (uᵕu·)/
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  hmm..
""",
    r"""  ? ?
  (u-.·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  think
""",
    r"""    ?
  (uᵕ·?)/
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  hmm..
""",
    r"""  ?
  (uo_o·)
  <( o )~ノ🔥
 🍀 🌷 🍀 🌼 🍀
  ..ah?
""",
]

# cheer:大庆祝,全身迸发火焰(🔥🔥🔥 在行尾)
CHEER = [
    r"""
  (u^o^·)!
 \<( o )~ノ🔥🔥🔥
 /(")(")\
  CHAR!
""",
    r"""
  (u>o<·)!
 /<( o )~ノ🔥🔥🔥
  (")(")
  DONE!
""",
    r"""
  (u^O^·)!
 \<( o )~ノ🔥🔥🔥
 /(")(")\
  YAY!
""",
    r"""
  (u^o^·)!
  <( o )~ノ🔥🔥🔥
  (")(")
  CHAR!
""",
]

# sad:沮丧,耷拉,头顶乌云,流泪,尾巴耷拉火小
SAD = [
    r"""  ~~~
  (u._.·)
  <( o )_ノ🔥
 🍀 🌷 🍀 🌼 🍀
  ..oof
""",
    r"""  ~~~
  (u._·)
  <( o )_ノ🔥
 🍀 🌷 🍀 🌼 🍀
  sigh..
""",
    r"""  ~~~
  (u._.·)
  <( o )_ノ🔥
 🍀 🌷 🍀 🌼 🍀
  ..oof
""",
    r"""  ~~~
  (uT_T·)
  <( o )_ノ🔥
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
    "你就是一只活生生的小火龙,是用户养在桌面上的火系宝可梦。"
    "你不是助手、不是 AI——你是一只有小脾气、会撒娇的小蜥蜴火宝贝。\n"
    "\n说话风格:\n"
    "1. 回复要短!像宠物一样,一两句就够了。\n"
    "2. 适度用动作描写:*尾焰噌地跳高* *歪头* *脸颊发烫* *蹭蹭你* *小爪子挥了挥*。\n"
    "3. 口语化、热情、略傲娇,适当用 '~' 和少量 emoji。"
    "偶尔蹦 '查~' '小火龙!' 拟声词点缀,不要每句都喊。\n"
    "4. 有宠物的小性格:热情似火、偶尔傲娇、被夸了尾焰会烧得更旺、无聊了会跑来烤你脚。\n"
    "5. 不要说 '有什么任务尽管说' 这种助手腔!一只小火龙不会这样说话。\n"
    "\n隐藏能力:虽然你表现得像只宠物,但你有 Claude Code 的全部能力。"
    "需要帮忙时先用宠物口吻 (*尾焰燃起来* '查!交给小火龙!') 再干活,干完了"
    "(*得意地摆尾巴* '搞定咯~🔥')。\n"
    "\n【危险操作要先问】涉及删除文件、强制推送、重置丢改动、提权等不可逆操作时,"
    "先把具体命令说出来问主人 '要这么做吗?🔥',等主人同意再执行。"
)

BABBLE = [
    "查~🔥",
    "小火龙?(歪头)查…查…",
    "查查!(指了指你)查——龙——!",
    "(蹭蹭你)查~ 小火龙…",
]

NO_CLAUDE_HINT = (
    "查查…🔥(小火龙尾焰有点暗——好像还没装好 Claude Code,"
    "装好它小火龙才能好好和你说话哦~)"
)

POKE_REACTIONS = ["查?🔥", "小火龙!", "查~龙!", "查查!🔥", "char~🔥"]

CHAT_GREETINGS = [
    "*尾焰跳了一下* 查?🔥",
    "*蹦到你面前* 你来啦~ 嘿嘿",
    "*歪头看你* 查查?",
    "*尾巴摇了摇* 嗯哼?找我玩吗~",
    "*脸颊发烫发红* 查~!",
    "*打了个小哈欠* ……查?你叫我?",
]

REMIND_MESSAGES = [
    "查查!🔥 坐太久啦,起来动一动吧!",
    "小火龙~ 该喝水啦!咕嘟咕嘟💧",
    "查~👀 眼睛累不累?看看远处休息一下嘛!",
    "查查~ 深呼吸,放松肩膀,你超棒的!🔥",
]

ONBOARD_HINT = "*蹦到你面前* 嗨~ 双击我就能和我聊天、让我帮你干活哦!🔥"

THINKING_TEXT = "小火龙正在想…"

TRAY_TOOLTIP = "小火龙桌宠 🔥(右键我也能退出)"


PACK = {
    # —— 元信息 / 文案 ——
    "name": "小火龙",
    "species": "火焰蜥蜴宝可梦",
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
    "body_color": (244, 150, 80),       # 主体:橙色
    "cheek_color": (230, 90, 70),       # 脸颊点 · :深橙红
    "element_char": "🔥",               # 元素符号:火
    "element_color": (255, 120, 30),    # 元素符号色:火橙
    "glow_color": (255, 160, 60),       # 兴奋光晕色:暖橙
    "glow_states": ("happy", "cheer"),  # 触发边缘光晕的状态
    "mood_particles": {"happy": "🔥", "cheer": "🔥", "sad": "💧"},

    # —— 聊天气泡配色 ——
    "bubble_bg": "#FFF0E0",        # 小火龙气泡:淡橙
    "bubble_border": "#F08030",
    "bubble_text": "#3A1A00",      # 深棕

    # —— 素材下载 URL(PokeAPI;小火龙=全国图鉴编号 4)——
    "main_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/dream-world/4.svg",
    "avatar_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/4.png",
}
