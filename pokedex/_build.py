"""数据包组装器(内部工具)。

把 ① 画师产出的 15 组帧(存为 pokedex/_frames_<名>.py,内含大写帧常量)
   ② _meta.py 里该只的元数据(配色/属性/性格/图鉴号/口头禅)
拼成完整的 pokedex/<名>.py 数据包(PACK dict),含按性格生成的人设 + 台词。

用法:python pokedex/_build.py <module_name>
例:  python pokedex/_build.py charmander
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

import _meta  # noqa: E402

_STATE_CONSTS = [
    "IDLE", "WALK_RIGHT", "WALK_LEFT", "EAT", "SLEEP", "HAPPY", "JUMP",
    "LOOK", "SING", "YAWN", "SURPRISE", "STRUGGLE", "THINK", "CHEER", "SAD",
]


def _persona(m: dict) -> str:
    """按性格生成人设 system prompt(沿用皮卡丘人设骨架,替换物种/性格/口吻)。"""
    name, species, traits = m["name"], m["species"], m["traits"]
    return (
        f"你就是一只活生生的{name}({species}),是用户养在桌面上的宝可梦宠物。"
        f"你不是助手、不是 AI、不是工具——你是一只有自己小情绪的小动物,"
        f"性格{traits}。\n"
        "\n说话风格(很重要,务必自然):\n"
        "1. 回复要短!像宠物一样,大多数时候一两句话就够了,不要长篇大论、不要分点列清单"
        "(除非用户明确要你写代码或详细说明)。\n"
        "2. 适度用动作和状态描写,用星号括起来,比如 *歪头* *蹭蹭你* *耳朵竖起来* "
        "*打个小哈欠* *凑到你面前*,让人感觉到你是只真的小动物——但一条回复里别堆一串动作,"
        "通常一个就够,自然最重要。\n"
        f"3. 口语化、奶声奶气,适当用'~'和少量 emoji(别堆太多)。"
        f"偶尔蹦'{m['babble_word']}'之类的拟声词点缀,但绝不每句都喊,否则像复读机。\n"
        f"4. 要有这只宝可梦的性格({traits}):该撒娇撒娇、该卖萌卖萌、该闹脾气闹脾气,"
        "有自己的喜怒。换着花样说话,别老一个套路。\n"
        "5. 千万不要说'有什么任务尽管说''有代码要写/文件要读尽管说'这种助手腔!"
        "一只真宝可梦不会这样说话。\n"
        "\n隐藏能力(底线):虽然你表现得像只宠物,但你其实有 Claude Code 的全部能力,"
        "可以读写文件、执行命令、写代码。当用户真的需要你帮忙做事时,你照样能漂亮完成——"
        f"只是用{name}的方式:先用宠物口吻应一声,然后给出准确、完整、可用的结果。"
        "技术内容绝不能因为扮可爱而出错或含糊。干完活也用宠物口吻邀功。\n"
        "\n【危险操作要先问】涉及删除文件(rm -rf)、强制推送(git push --force)、"
        "重置丢改动(git reset --hard)、提权(sudo)、格式化/写裸盘、关机重启这类"
        "【不可逆操作】时,你【先别执行】——用宠物口吻把你打算跑的【具体命令】说出来"
        "问主人'要这么做吗?',等主人这一轮明确说同意了,下一轮再真去做。"
        "普通操作(读文件、写文件、git commit、安装依赖、跑测试等)正常做,不用问。"
    )


def _texts(m: dict) -> dict:
    """按口头禅生成台词组(拟声/点击/开场/提醒等)。"""
    w = m["babble_word"]
    el = m["element"]
    name = m["name"]
    return {
        "babble": [
            f"{w}{w}~{el}",
            f"{w}?(歪头){w}…{w}…",
            f"{w}{w}!(指了指你){w}——!",
            f"(蹭蹭你){w}~ {w}…",
        ],
        "no_claude_hint": (
            f"{w}{w}…{el}({name}只会冒泡泡了——好像还没装好 Claude Code,"
            f"装好它{name}才能好好和你说话哦~)"),
        "poke_reactions": [
            f"{w}?{el}", f"{w}{w}!", f"{w}~", f"{w}{w}!✨", f"{w}~{el}"],
        "chat_greetings": [
            f"*耳朵竖起来* {w}?{el}",
            "*凑到你面前* 你来啦~ 嘿嘿",
            f"*歪头看你* {w}?",
            "*尾巴翘了翘* 嗯哼?找我玩吗~",
            f"*精神一振* {w}~!",
            f"*打了个小哈欠* ……{w}?你叫我?",
        ],
        "remind_messages": [
            f"{w}{w}!{el} 坐太久啦,起来动一动吧!",
            f"{w}~ 该喝水啦!咕嘟咕嘟💧",
            f"{w}!👀 眼睛累不累?看看远处休息一下嘛!",
            f"{w}~ 深呼吸,放松肩膀,你超棒的!✨",
        ],
        "onboard_hint": f"*凑到你面前* 嗨~ 双击我就能和我聊天、让我帮你干活哦!{el}",
        "thinking_text": f"{name}正在想…",
        "tray_tooltip": f"{name}桌宠 {el}(右键我也能退出)",
    }


def build(module_name: str) -> str:
    """生成 pokedex/<module_name>.py 的完整源码字符串。"""
    m = _meta.META[module_name]
    frames_path = os.path.join(_HERE, f"_frames_{module_name}.py")
    if not os.path.exists(frames_path):
        raise SystemExit(f"缺少帧文件:{frames_path}(先把画师产出存到这里)")
    frames_src = open(frames_path, encoding="utf-8").read()
    texts = _texts(m)
    persona = _persona(m)
    dex = m["dex"]
    main_url = (f"https://raw.githubusercontent.com/PokeAPI/sprites/master/"
                f"sprites/pokemon/other/dream-world/{dex}.svg")
    avatar_url = (f"https://raw.githubusercontent.com/PokeAPI/sprites/master/"
                  f"sprites/pokemon/other/home/{dex}.png")

    out = []
    out.append(f'"""{m["name"]}数据包(自动组装:画师帧 + _meta 元数据)。\n\n')
    out.append("字符渲染协议:· → 脸颊色、元素符号 → 元素色、其余 → 主体色。\n")
    out.append('详见 pokedex/ART_SPEC.md 与 pokedex/pikachu.py。\n"""\n\n')
    out.append("# ── 动画帧(画师产出)──\n")
    out.append(frames_src.rstrip() + "\n\n\n")
    out.append("def _normalize(frames):\n")
    out.append('    """把每帧统一成相同行数、相同列宽,便于等宽渲染不抖动。"""\n')
    out.append("    grids = [f.strip(\"\\n\").split(\"\\n\") for f in frames]\n")
    out.append("    max_rows = max(len(g) for g in grids)\n")
    out.append("    max_cols = max((max((len(l) for l in g), default=0)) for g in grids)\n")
    out.append("    out = []\n")
    out.append("    for g in grids:\n")
    out.append("        rows = [\"\"] * (max_rows - len(g)) + g\n")
    out.append("        out.append(\"\\n\".join(r.ljust(max_cols) for r in rows))\n")
    out.append("    return out\n\n\n")
    out.append("STATES = {\n")
    keymap = [
        ("idle", "IDLE"), ("walk_right", "WALK_RIGHT"), ("walk_left", "WALK_LEFT"),
        ("eat", "EAT"), ("sleep", "SLEEP"), ("happy", "HAPPY"), ("jump", "JUMP"),
        ("look", "LOOK"), ("sing", "SING"), ("yawn", "YAWN"),
        ("surprise", "SURPRISE"), ("struggle", "STRUGGLE"), ("think", "THINK"),
        ("cheer", "CHEER"), ("sad", "SAD"),
    ]
    for k, c in keymap:
        out.append(f'    "{k}": _normalize({c}),\n')
    out.append("}\n\n\n")

    # PACK
    out.append("PACK = {\n")
    out.append(f'    "name": {m["name"]!r},\n')
    out.append(f'    "species": {m["species"]!r},\n')
    out.append(f'    "persona": {persona!r},\n')
    out.append(f'    "babble": {texts["babble"]!r},\n')
    out.append(f'    "no_claude_hint": {texts["no_claude_hint"]!r},\n')
    out.append(f'    "poke_reactions": {texts["poke_reactions"]!r},\n')
    out.append(f'    "chat_greetings": {texts["chat_greetings"]!r},\n')
    out.append(f'    "remind_messages": {texts["remind_messages"]!r},\n')
    out.append(f'    "onboard_hint": {texts["onboard_hint"]!r},\n')
    out.append(f'    "thinking_text": {texts["thinking_text"]!r},\n')
    out.append(f'    "tray_tooltip": {texts["tray_tooltip"]!r},\n')
    out.append('    "states": STATES,\n')
    out.append(f'    "body_color": {m["body"]!r},\n')
    out.append(f'    "cheek_color": {m["cheek"]!r},\n')
    out.append(f'    "element_char": {m["element"]!r},\n')
    out.append(f'    "element_color": {m["element_color"]!r},\n')
    out.append(f'    "glow_color": {m["glow"]!r},\n')
    out.append('    "glow_states": ("happy", "cheer"),\n')
    out.append(f'    "mood_particles": {{"happy": "✨", "cheer": {m["element"]!r}, "sad": "💧"}},\n')
    out.append(f'    "bubble_bg": {m["bubble"][0]!r},\n')
    out.append(f'    "bubble_border": {m["bubble"][1]!r},\n')
    out.append(f'    "bubble_text": {m["bubble"][2]!r},\n')
    out.append(f'    "main_url": {main_url!r},\n')
    out.append(f'    "avatar_url": {avatar_url!r},\n')
    out.append("}\n")
    return "".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: python pokedex/_build.py <module_name>")
    name = sys.argv[1]
    src = build(name)
    dest = os.path.join(_HERE, f"{name}.py")
    open(dest, "w", encoding="utf-8").write(src)
    print(f"✅ 已生成 {dest}")
