"""宝可梦数据包加载器。

一只桌宠 = 一份数据包(pokedex/<名字>.py 里的 PACK dict:动画帧 + 配色/元素 +
文案/人设)。本模块按名字选包,把它的 PACK 作为当前生效的数据包。

换宝可梦只需:① 在 pokedex/ 下新建 <名字>.py(照 pikachu.py 填 PACK),
② 把 config.ACTIVE_POKEMON 设成该名字(或在控制台在线切换)。代码逻辑零改动。

设计:本模块【不】反向 import config——由 config.py 调 load_pack(ACTIVE_POKEMON),
依赖单向(config → pokedex),避免 config 末尾 _apply_pack 与本模块的循环 import。
"""

import importlib
import os


# 进化链顺序(控制台下拉按此排序,比字母序直观)。新增宝可梦时把模块名加进来;
# 不在此列表里的包仍可用(available_packs 会把它们追加在末尾),只是排序靠后。
_PREFERRED_ORDER = [
    "pikachu",
    "bulbasaur", "ivysaur", "venusaur",
    "charmander", "charmeleon", "charizard",
    "squirtle", "wartortle", "blastoise",
    "froakie", "frogadier", "greninja", "ash_greninja",
    "riolu", "lucario", "mega_lucario",
]


def available_packs():
    """列出 pokedex/ 目录下所有可用数据包的模块名(供控制台下拉选)。

    扫本目录的 *.py(排除 __init__),按 _PREFERRED_ORDER 排序、其余追加在后。
    不实际 import(快、且坏包不影响列表);load_pack 时才校验有效性 + 回退。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    names = set()
    try:
        for fn in os.listdir(here):
            # 排除 __init__ 和下划线开头的内部工具(_audit/_build/_meta 等不是数据包)
            if fn.endswith(".py") and not fn.startswith("_"):
                names.add(fn[:-3])
    except OSError:
        pass
    ordered = [n for n in _PREFERRED_ORDER if n in names]
    extras = sorted(names - set(ordered))
    return ordered + extras


def pack_labels():
    """{模块名: 中文显示名} 映射,供控制台下拉【显示中文、值用英文模块名】。

    中文名取各包 PACK["name"](单一真相)。某包读取失败 → 退回用模块名当显示名,
    不影响其它包。顺序同 available_packs(进化链序)。
    """
    out = {}
    for name in available_packs():
        try:
            pack = _try_import_pack(name)
            out[name] = (pack or {}).get("name") or name
        except Exception:
            out[name] = name
    return out


def load_pack(name):
    """按名字加载数据包的 PACK dict;任何失败都回退到 pikachu(默认包),绝不崩。

    Args:
        name: 数据包名(对应 pokedex/<name>.py),如 "pikachu"。空/None/不存在
            /模块缺 PACK 都视为无效 → 回退 pikachu。
    Returns:
        dict: 该宝可梦的 PACK。
    """
    name = (name or "").strip() or "pikachu"
    pack = _try_import_pack(name)
    if pack is not None:
        return pack
    # 回退:指定包加载失败(拼错名/文件缺失/PACK 字段缺失/import 报错)→ 用默认皮卡丘。
    # 默认包再失败就只能让异常冒出来(说明项目损坏,该早暴露而非静默空跑)。
    if name != "pikachu":
        fallback = _try_import_pack("pikachu")
        if fallback is not None:
            return fallback
    # 走到这里说明连 pikachu 都加载不了:直接 import 让真实错误暴露(不吞)。
    return importlib.import_module("pokedex.pikachu").PACK


def _try_import_pack(name):
    """尝试 import pokedex.<name> 并取其 PACK;任何异常/缺字段返回 None。

    兼容两种运行方式:正常 `import pokedex`(项目根在 sys.path,pet.py 已保证),
    以及 pet.py 把子目录扁平加进 sys.path 的环境——后者 `pokedex.<name>` 仍可达,
    因为 pokedex 是项目根下的真包。万一带包名失败,再退一步按裸模块名试一次。
    """
    for modname in (f"pokedex.{name}", name):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        pack = getattr(mod, "PACK", None)
        # 数据包必须有动画帧(states)才算有效——缺了渲染没法跑,视为无效包。
        if isinstance(pack, dict) and pack.get("states"):
            return pack
    return None
