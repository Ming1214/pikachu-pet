"""ASCII 动画帧库(薄转发层)。

历史上这里直接放着皮卡丘的所有帧。现在帧数据搬进了「宝可梦数据包」
(pokedex/<名字>.py 的 PACK["states"]),本模块退化成一层薄转发:从当前生效的
数据包取 STATES 暴露出去,保持 `import ascii_pika; ascii_pika.STATES[...]` 这个老
接口不变(pet.py 多处依赖它),换宝可梦时调用方一行都不用改。

要改皮卡丘的形象 / 加新宝可梦,去 pokedex/(见 pokedex/README.md),不要改这里。
"""

# 从 config 取当前生效的数据包(config._PACK 已按 ACTIVE_POKEMON + 控制台覆盖选定)。
# 不直接 `from pokedex import ...`:选哪只宝可梦的决策点统一在 config(它读
# ACTIVE_POKEMON、处理 override 后调 pokedex.load_pack),这里只消费结果,避免两处
# 各自决定用哪个包导致不一致。
import config

# 当前生效宝可梦的动画帧:dict[状态名 → list[已规整的帧]]。
# 15 个状态键见 pokedex/pikachu.py 的 STATES(idle/walk_right/.../sad)。
#
# 注意:不在模块级绑定 config._PACK["states"],否则切换宝可梦后 _PACK 被替换,
# 这里拿到的仍是旧 dict 引用,导致动画帧永远来自最初那只宝可梦。
# 用属性代理,每次访问都从 config._PACK 重读,换宝可梦即时生效。

class _StatesProxy:
    """透明代理:把 ascii_pika.STATES[key] / len(STATES) 等访问转发到当前 _PACK。"""
    def __getitem__(self, key):
        return config._PACK["states"][key]
    def __contains__(self, key):
        return key in config._PACK["states"]
    def __len__(self):
        return len(config._PACK["states"])
    def keys(self):
        return config._PACK["states"].keys()
    def values(self):
        return config._PACK["states"].values()
    def items(self):
        return config._PACK["states"].items()

STATES = _StatesProxy()


def _normalize(frames):
    """把每帧统一成相同行数、相同列宽,便于等宽渲染不抖动。

    历史保留:帧数据现已在数据包内 _normalize 过,这里不再需要。但旧代码/外部脚本
    可能还 `from ascii_pika import _normalize`,保留同名实现以防 import 报错。
    """
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
