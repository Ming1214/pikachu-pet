"""ASCII 皮卡丘动画帧库。

每个状态是一组帧(list[str]),每帧是多行字符画。
一只 Q 版小皮卡丘:( o.o ) 眼睛、脸颊(渲染时叠红点)、尾巴 ~/。
所有帧统一为同样的行数/列宽,切换时不抖动。

状态:
  idle   待机(尾巴轻摆 + 眨眼)
  walk   走路(腿交替 + 身体起伏)
  eat    吃东西(捧着果子啃)
  sleep  睡觉(闭眼 + ZZZ)
  happy  开心放电(脸颊冒电花)
walk 提供左右两套(脸朝行进方向);其余状态正面朝前。
"""

IDLE = [
    r"""
 |z\/z| _/⚡
 (o.o·) ) /
 zz zz zz ⌐
""",
    r"""
 |z\/z| _ ⚡
 (-.-·)_) /
 zz zz zz ⌐
""",
    r"""
 |z\/z| _/⚡
 (o.o·) ) /
 zz zz zz ⌐
""",
    r"""
 |z\/z| /⚡
 (o.o·)_) /
 zz zz zz ⌐
""",
]

# 四足奔跑(朝右,向右跑):脸朝右,前爪在右、尾巴在左后
WALK_RIGHT = [
    r"""
  ⚡\_ |z\/z|
    \ (·o.o·)
       -_(")(")
""",
    r"""
  ⚡\_ |z\/z|
     \_(·o.o·)=
      (")  (")
""",
    r"""
  ⚡\_ |z\/z|
      \(·>.<·)
      _(")(")_
""",
    r"""
  ⚡\_ |z\/z|
     \_(·o.o·)=
      (")  (")
""",
]

# 四足奔跑(朝左,向左跑):脸朝左,前爪在左、尾巴在右后
WALK_LEFT = [
    r"""
   |z\/z| _/⚡
  (·o.o·) /
  (")(")_-
""",
    r"""
    |z\/z| _/⚡
 =(·o.o·)_/
    (")  (")
""",
    r"""
   |z\/z| _/⚡
  (·>.<·)/
  _(")(")_
""",
    r"""
    |z\/z| _/⚡
 =(·o.o·)_/
    (")  (")
""",
]

EAT = [
    r"""
  |z\/z| _/⚡
 ●(o o·) ) /
 zz zz zz ⌐
   nom
""",
    r"""
  |z\/z| _/⚡
 ◐(-ω-·) ) /
 zz zz zz ⌐
   nom!
""",
    r"""
  |z\/z| _/⚡
 ◑(ouo·) ) /
 zz zz zz ⌐
   yum~
""",
    r"""
  |z\/z| _/⚡
 ○(^o^·) ) /
 zz zz zz ⌐
   munch
""",
]

SLEEP = [
    r"""        Z
 |z\/z| _/⚡
 (-.-·) ) /
 zz zz zz ⌐
""",
    r"""      Z z
 |z\/z| _/⚡
 (u.u·) ) /
 zz zz zz ⌐
""",
    r"""    z Z
 |z\/z| _/⚡
 (-.-·) ) /
 zz zz zz ⌐
""",
    r"""   Z
 |z\/z| _/⚡
 (u.u·) ) /
 zz zz zz ⌐
""",
]

HAPPY = [
    r"""
 ⚡|z\/z|_/⚡
  (^o^·)
 \(")(")/
   yay!
""",
    r"""
  |z\/z|_/⚡
 ⚡(^o^·)⚡
 /(")(")\
  pika!⚡
""",
    r"""
 ⚡|z\/z|_/⚡
  (>o<·)
 \(")(")/
   ⚡✨⚡
""",
    r"""
  |z\/z|_/⚡
 ⚡(^o^·)⚡
 \(")(")/
   yay!
""",
]

# ── A. 新自主行为 ──────────────────────────────────────────

# 跳跃:蹲 → 起跳 → 腾空 → 落地(配合窗口短促上移,见 pet.py)
JUMP = [
    r"""

 |z\/z|_/⚡
 (o.o·)
 _(")(")_
""",
    r"""
 |z\/z|_/⚡
 (>o<·)/
 (")(")
   ↑↑
""",
    r"""
 \|z\/z|_/⚡
 (^o^·)
 (")(")
  ⚡  ⚡
""",
    r"""
 |z\/z|_/⚡
 (o.o·)
 /(")(")\
   tap!
""",
]

# 东张西望:眼睛/脸左右瞟,好奇转头
LOOK = [
    r"""
 |z\/z| _/⚡
 (o.o·) ) /
 zz zz zz ⌐
   hmm?
""",
    r"""
 |z\/z| _/⚡
 (·o.o·) /
 zz zz zz ⌐
    ?→
""",
    r"""
 |z\/z| _/⚡
 (o.o·) ) /
 zz zz zz ⌐
   hmm?
""",
    r"""
 |z\/z| _/⚡
 (·o.o·) /
 zz zz zz ⌐
  ←?
""",
]

# 哼歌:头顶音符飘动,身体随拍左右晃
SING = [
    r"""  ♪
 |z\/z|_/⚡
 (^.^·)
 (")(")
  la~la
""",
    r"""    ♫
  |z\/z|_/⚡
  (^o^·)
  (")(")
   ~la la
""",
    r"""  ♪ ♫
 |z\/z|_/⚡
 (^.^·)
 (")(")
  la~la~
""",
    r"""   ♫
  |z\/z|_/⚡
  (^o^·)
  (")(")
   la la~
""",
]

# 打哈欠:嘴越张越大,作为 idle → sleep 的过渡
YAWN = [
    r"""
 |z\/z| _/⚡
 (o.o·) ) /
 zz zz zz ⌐
   hm..
""",
    r"""
 |z\/z| _/⚡
 (o○o·) ) /
 zz zz zz ⌐
   ..haa
""",
    r"""
 |z\/z| _/⚡
 (=○=·) ) /
 zz zz zz ⌐
  ~haaa~
""",
    r"""
 |z\/z| _/⚡
 (-.-·) ) /
 zz zz zz ⌐
   ..zz
""",
]

# ── B. 互动反馈 ────────────────────────────────────────────

# 被戳一下:吓一跳缩起来 (>_<),抖一抖
SURPRISE = [
    r"""
 |z\/z|_/⚡
 (>_<·)!
 (")(")
   pika!
""",
    r"""
 |z\/z|_/⚡
!(O_O·)
 (")(")
   !?
""",
    r"""
 |z\/z|_/⚡
 (>_<·)!
 (")(")
   pika!
""",
    r"""
 |z\/z|_/⚡
 (=_=·;)
 (")(")
   ~~
""",
]

# 被拖拽:手脚乱蹬挣扎 (O_O)
STRUGGLE = [
    r"""
 \|z\/z|/⚡
 (O_O·)
 /(")(")
  ~wah~
""",
    r"""
 /|z\/z|\⚡
 (>_<·)
 (")(")\
  ~waa~
""",
    r"""
 \|z\/z|/⚡
 (O_O·)
 /(")(")
  ~wah~
""",
    r"""
 /|z\/z|\⚡
 (;O;·)
 (")(")\
  ~nooo
""",
]

# ── C. 情境化动画 ──────────────────────────────────────────

# 思考:挠头、头顶问号(聊天等 claude 回复时本体呼应)
THINK = [
    r"""    ?
 |z\/z|/⚡
 (・_・·) /
 zz zz zz ⌐
  hmm..
""",
    r"""   ? ?
 |z\/z| _/⚡
\(-_-·) /
 zz zz zz ⌐
  think
""",
    r"""    ?
 |z\/z|/⚡
 (・_・·?)/
 zz zz zz ⌐
  hmm..
""",
    r"""  ?
 |z\/z| _/⚡
\(o_o·) /
 zz zz zz ⌐
  ..ah?
""",
]

# 大放电(任务成功):比 happy 更夸张,全身电花
CHEER = [
    r"""⚡ ✨ ⚡
 \|z\/z|/⚡
 ⚡(^o^·)⚡
 /(")(")\
  DONE!⚡
""",
    r""" ✨⚡✨
 ⚡|z\/z|⚡
  (>o<·!)
 \(")(")/
 ⚡PIKA⚡
""",
    r"""⚡ ✨ ⚡
 \|z\/z|/⚡
 ⚡(^O^·)⚡
 /(")(")\
  ✨YAY✨
""",
    r""" ✨⚡✨
 ⚡|z\/z|⚡
  (^o^·!)
 \(")(")/
 ⚡DONE⚡
""",
]

# 沮丧(任务失败):耳朵耷拉、头顶乌云、流汗
SAD = [
    r"""  ☁☁☁
 |z\/z| _/⚡
 (´._.) ) /
 zz zz zz ⌐
  ..oof
""",
    r"""  ☁☁☁
 |z\/z| _/⚡
 (._.·)💧/
 zz zz zz ⌐
  sigh..
""",
    r"""  ☁☁☁
 |z\/z| _/⚡
 (´._.) ) /
 zz zz zz ⌐
  ..oof
""",
    r"""  ☁☁☁
 |z\/z| _/⚡
 (T_T·) /
 zz zz zz ⌐
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
    # A. 新自主行为
    "jump": _normalize(JUMP),
    "look": _normalize(LOOK),
    "sing": _normalize(SING),
    "yawn": _normalize(YAWN),
    # B. 互动反馈
    "surprise": _normalize(SURPRISE),
    "struggle": _normalize(STRUGGLE),
    # C. 情境化动画
    "think": _normalize(THINK),
    "cheer": _normalize(CHEER),
    "sad": _normalize(SAD),
}
