"""数据包严审器(总美术把关用)。

对一只宝可梦数据包跑统一质检:契约完整性 + ASCII 质量。用法:
    python pokedex/_audit.py <module_name> [<module_name> ...]
    python pokedex/_audit.py --all      # 审所有 pokedex/*.py(除内部文件)

检查项(对照皮卡丘黄金样板标准):
  1) 能 import、PACK 字段齐全、states 15 键
  2) 每个状态正好 4 帧、4 帧有动画差异(非全同)
  3) 每帧有脸颊点 ·
  4) 无"方块 emoji 与 ascii 字符同行"(真顶歪;⚡✨💫 等符号 emoji 豁免,与皮卡丘一致)
  5) walk_right 含朝右记号(> 或 face-right)、walk_left 含朝左记号(<)— 软警告
  6) 每帧含该只的"元素符号"(软警告,提示辨识度)
"""

import importlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

REQUIRED_KEYS = {
    "name", "species", "persona", "babble", "no_claude_hint", "poke_reactions",
    "chat_greetings", "remind_messages", "onboard_hint", "thinking_text",
    "tray_tooltip", "states", "body_color", "cheek_color", "element_char",
    "element_color", "glow_color", "glow_states", "mood_particles",
    "bubble_bg", "bubble_border", "bubble_text", "main_url", "avatar_url",
}
STATE_KEYS = {
    "idle", "walk_right", "walk_left", "eat", "sleep", "happy", "jump", "look",
    "sing", "yawn", "surprise", "struggle", "think", "cheer", "sad",
}
# 真·双宽方块 emoji(必须独立成行,和 ascii 同行=顶歪)。符号类 emoji(⚡✨💫💥
# 等)在 mac 等宽字体近单宽、可混排(皮卡丘黄金样板就这么用),不算顶歪。
BLOCK_EMOJI = set("🍀🌷🌼💧🔥🌿🌸🌺🐢☁🌀")
_NARROW = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
              "()[]<>{}\\/_=-!?;.,:")


def audit(name: str) -> list[str]:
    """审一只,返回错误列表(空=通过)。软警告以 'WARN:' 前缀。"""
    errs = []
    try:
        mod = importlib.import_module(f"pokedex.{name}")
    except Exception as exc:
        return [f"FATAL: import 失败:{exc}"]
    pack = getattr(mod, "PACK", None)
    if not isinstance(pack, dict):
        return ["FATAL: 缺 PACK dict"]
    missing = REQUIRED_KEYS - set(pack.keys())
    if missing:
        errs.append(f"PACK 缺字段:{sorted(missing)}")
    states = pack.get("states", {})
    if set(states.keys()) != STATE_KEYS:
        errs.append(f"states 键不对:多 {set(states)-STATE_KEYS} 少 {STATE_KEYS-set(states)}")
    el = pack.get("element_char", "")
    for st, frames in states.items():
        if not isinstance(frames, list) or len(frames) != 4:
            errs.append(f"{st}: 帧数不是 4(={len(frames) if isinstance(frames,list) else '非list'})")
            continue
        if len(set(frames)) == 1:
            errs.append(f"{st}: 4 帧完全相同(无动画)")
        cheek_frames = sum(1 for fr in frames if "·" in fr)
        # 脸颊点:皮卡丘 sad 也有个别帧不放(沮丧),放宽为"多数帧有"即可(≥半数)。
        if cheek_frames < 2:
            errs.append(f"{st}: 仅 {cheek_frames}/4 帧有脸颊点 ·(应多数帧有)")
        for i, fr in enumerate(frames):
            for ln in fr.split("\n"):
                # 真顶歪:方块 emoji【后面】还跟着 ascii 可见字符,会把后续整体右移。
                # emoji 在行尾(后面只有空格)只影响它自己那格,皮卡丘 (._.·)💧/ 这种
                # 行尾近似可接受(用户认可)→ 仅当 emoji 后还有非空格 ascii 才算硬伤。
                for idx, c in enumerate(ln):
                    if c in BLOCK_EMOJI:
                        rest = ln[idx + 1:]
                        # 后接 ascii 可见字符的【数量】:皮卡丘 (._.·)💧/ 这种 emoji 后
                        # 只跟 1 个手臂符号是认可的惯用法(只轻微挤 1 格),≥2 个才算
                        # 真把后续顶歪 → 硬伤。
                        n_trail = sum(1 for r in rest if r in _NARROW)
                        if n_trail >= 2:
                            errs.append(
                                f"{st}帧{i}: 方块emoji后接多个ascii(顶歪)→ |{ln}|")
                            break
            if el and el not in fr and st in ("happy", "cheer"):
                errs.append(f"WARN: {st}帧{i}: 未见元素符号 {el}(辨识度)")
    # 方向记号(软)
    if states.get("walk_right") and not any(">" in f for f in states["walk_right"]):
        errs.append("WARN: walk_right 未见朝右记号 >")
    if states.get("walk_left") and not any("<" in f for f in states["walk_left"]):
        errs.append("WARN: walk_left 未见朝左记号 <")
    return errs


def main(argv):
    if not argv:
        print("用法: python pokedex/_audit.py <name> ... | --all")
        return 1
    if argv == ["--all"]:
        names = [f[:-3] for f in os.listdir(_HERE)
                 if f.endswith(".py") and not f.startswith("_")
                 and f != "__init__.py"]
        names.sort()
    else:
        names = argv
    total_hard = 0
    for n in names:
        errs = audit(n)
        hard = [e for e in errs if not e.startswith("WARN:")]
        warn = [e for e in errs if e.startswith("WARN:")]
        total_hard += len(hard)
        status = "✅ 通过" if not hard else f"❌ {len(hard)} 个硬伤"
        print(f"\n=== {n} === {status}" + (f"({len(warn)} 警告)" if warn else ""))
        for e in hard:
            print("  ❌", e)
        for e in warn:
            print("  ⚠️ ", e[5:])
    print(f"\n{'='*40}\n总计硬伤:{total_hard}")
    return 1 if total_hard else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
