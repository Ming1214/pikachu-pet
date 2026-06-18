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
 (\__/) _/⚡
 (o.o·) ) /
 zz zz zz ⌐
""",
    r"""
 (\__/) _ ⚡
 (-.-·)_) /
 zz zz zz ⌐
""",
    r"""
 (\__/) _/⚡
 (o.o·) ) /
 zz zz zz ⌐
""",
    r"""
 (\__/) /⚡
 (o.o·)_) /
 zz zz zz ⌐
""",
]

# 四足奔跑(朝右,向右跑):脸朝右,前爪在右、尾巴在左后
WALK_RIGHT = [
    r"""
  ⚡\_ (\__/)
    \ (·o.o·)
       -_(")(")
""",
    r"""
  ⚡\_ (\__/)
     \_(·o.o·)=
      (")  (")
""",
    r"""
  ⚡\_ (\__/)
      \(·>.<·)
      _(")(")_
""",
    r"""
  ⚡\_ (\__/)
     \_(·o.o·)=
      (")  (")
""",
]

# 四足奔跑(朝左,向左跑):脸朝左,前爪在左、尾巴在右后
WALK_LEFT = [
    r"""
   (\__/) _/⚡
  (·o.o·) /
  (")(")_-
""",
    r"""
    (\__/) _/⚡
 =(·o.o·)_/
    (")  (")
""",
    r"""
   (\__/) _/⚡
  (·>.<·)/
  _(")(")_
""",
    r"""
    (\__/) _/⚡
 =(·o.o·)_/
    (")  (")
""",
]

EAT = [
    r"""
  (\__/) _/⚡
 ●(o o·) ) /
 zz zz zz ⌐
   nom
""",
    r"""
  (\__/) _/⚡
 ◐(-ω-·) ) /
 zz zz zz ⌐
   nom!
""",
    r"""
  (\__/) _/⚡
 ◑(ouo·) ) /
 zz zz zz ⌐
   yum~
""",
    r"""
  (\__/) _/⚡
 ○(^o^·) ) /
 zz zz zz ⌐
   munch
""",
]

SLEEP = [
    r"""        Z
 (\__/) _/⚡
 (-.-·) ) /
 zz zz zz ⌐
""",
    r"""      Z z
 (\__/) _/⚡
 (u.u·) ) /
 zz zz zz ⌐
""",
    r"""    z Z
 (\__/) _/⚡
 (-.-·) ) /
 zz zz zz ⌐
""",
    r"""   Z
 (\__/) _/⚡
 (u.u·) ) /
 zz zz zz ⌐
""",
]

HAPPY = [
    r"""
 ⚡(\__/)_/⚡
  (^o^·)
 \(")(")/
   yay!
""",
    r"""
  (\__/)_/⚡
 ⚡(^o^·)⚡
 /(")(")\
  pika!⚡
""",
    r"""
 ⚡(\__/)_/⚡
  (>o<·)
 \(")(")/
   ⚡✨⚡
""",
    r"""
  (\__/)_/⚡
 ⚡(^o^·)⚡
 \(")(")/
   yay!
""",
]

# ── A. 新自主行为 ──────────────────────────────────────────

# 跳跃:蹲 → 起跳 → 腾空 → 落地(配合窗口短促上移,见 pet.py)
JUMP = [
    r"""

 (\__/)_/⚡
 (o.o·)
 _(")(")_
""",
    r"""
 (\__/)_/⚡
 (>o<·)/
 (")(")
   ↑↑
""",
    r"""
 \(\__/)_/⚡
 (^o^·)
 (")(")
  ⚡  ⚡
""",
    r"""
 (\__/)_/⚡
 (o.o·)
 /(")(")\
   tap!
""",
]

# 东张西望:眼睛/脸左右瞟,好奇转头
LOOK = [
    r"""
 (\__/) _/⚡
 (o.o·) ) /
 zz zz zz ⌐
   hmm?
""",
    r"""
 (\__/) _/⚡
 (·o.o·) /
 zz zz zz ⌐
    ?→
""",
    r"""
 (\__/) _/⚡
 (o.o·) ) /
 zz zz zz ⌐
   hmm?
""",
    r"""
 (\__/) _/⚡
 (·o.o·) /
 zz zz zz ⌐
  ←?
""",
]

# 哼歌:头顶音符飘动,身体随拍左右晃
SING = [
    r"""  ♪
 (\__/)_/⚡
 (^.^·)
 (")(")
  la~la
""",
    r"""    ♫
  (\__/)_/⚡
  (^o^·)
  (")(")
   ~la la
""",
    r"""  ♪ ♫
 (\__/)_/⚡
 (^.^·)
 (")(")
  la~la~
""",
    r"""   ♫
  (\__/)_/⚡
  (^o^·)
  (")(")
   la la~
""",
]

# 打哈欠:嘴越张越大,作为 idle → sleep 的过渡
YAWN = [
    r"""
 (\__/) _/⚡
 (o.o·) ) /
 zz zz zz ⌐
   hm..
""",
    r"""
 (\__/) _/⚡
 (o○o·) ) /
 zz zz zz ⌐
   ..haa
""",
    r"""
 (\__/) _/⚡
 (=○=·) ) /
 zz zz zz ⌐
  ~haaa~
""",
    r"""
 (\__/) _/⚡
 (-.-·) ) /
 zz zz zz ⌐
   ..zz
""",
]

# ── B. 互动反馈 ────────────────────────────────────────────

# 被戳一下:吓一跳缩起来 (>_<),抖一抖
SURPRISE = [
    r"""
 (\__/)_/⚡
 (>_<·)!
 (")(")
   pika!
""",
    r"""
 (\__/)_/⚡
!(O_O·)
 (")(")
   !?
""",
    r"""
 (\__/)_/⚡
 (>_<·)!
 (")(")
   pika!
""",
    r"""
 (\__/)_/⚡
 (=_=·;)
 (")(")
   ~~
""",
]

# 被拖拽:手脚乱蹬挣扎 (O_O)
STRUGGLE = [
    r"""
 \(\__/)/⚡
 (O_O·)
 /(")(")
  ~wah~
""",
    r"""
 /(\__/)\⚡
 (>_<·)
 (")(")\
  ~waa~
""",
    r"""
 \(\__/)/⚡
 (O_O·)
 /(")(")
  ~wah~
""",
    r"""
 /(\__/)\⚡
 (;O;·)
 (")(")\
  ~nooo
""",
]

# ── C. 情境化动画 ──────────────────────────────────────────

# 思考:挠头、头顶问号(聊天等 claude 回复时本体呼应)
THINK = [
    r"""    ?
 (\__/)/⚡
 (・_・·) /
 zz zz zz ⌐
  hmm..
""",
    r"""   ? ?
 (\__/) _/⚡
\(-_-·) /
 zz zz zz ⌐
  think
""",
    r"""    ?
 (\__/)/⚡
 (・_・·?)/
 zz zz zz ⌐
  hmm..
""",
    r"""  ?
 (\__/) _/⚡
\(o_o·) /
 zz zz zz ⌐
  ..ah?
""",
]

# 大放电(任务成功):比 happy 更夸张,全身电花
CHEER = [
    r"""⚡ ✨ ⚡
 \(\__/)/⚡
 ⚡(^o^·)⚡
 /(")(")\
  DONE!⚡
""",
    r""" ✨⚡✨
 ⚡(\__/)⚡
  (>o<·!)
 \(")(")/
 ⚡PIKA⚡
""",
    r"""⚡ ✨ ⚡
 \(\__/)/⚡
 ⚡(^O^·)⚡
 /(")(")\
  ✨YAY✨
""",
    r""" ✨⚡✨
 ⚡(\__/)⚡
  (^o^·!)
 \(")(")/
 ⚡DONE⚡
""",
]

# 沮丧(任务失败):耳朵耷拉、头顶乌云、流汗
SAD = [
    r"""  ☁☁☁
 (\__/) _/⚡
 (´._.) ) /
 zz zz zz ⌐
  ..oof
""",
    r"""  ☁☁☁
 (\__/) _/⚡
 (._.·)💧/
 zz zz zz ⌐
  sigh..
""",
    r"""  ☁☁☁
 (\__/) _/⚡
 (´._.) ) /
 zz zz zz ⌐
  ..oof
""",
    r"""  ☁☁☁
 (\__/) _/⚡
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
