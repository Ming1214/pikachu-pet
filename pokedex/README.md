# 🎒 宝可梦数据包(pokedex)

桌宠的**形象、人设、台词、配色、素材**全部从一份「数据包」读取,代码逻辑不掺任何
宝可梦特定内容。所以**换一只宝可梦 = 新建一个数据包文件 + 改一个开关**,不用动代码。

```
pokedex/
├── __init__.py     # 加载器:按 config.ACTIVE_POKEMON 选包,失败安全回退 pikachu
├── pikachu.py      # 皮卡丘数据包(默认,也是参考样板)
├── <16 只>.py      # 已内置 16 只(见下),照样板可继续加
├── ART_SPEC.md     # ASCII 美术规范(画新宝可梦的铁律)
└── _audit.py       # 数据包质检器:python pokedex/_audit.py --all
```

## 已内置宝可梦(17 只,含皮卡丘)

| 进化链 | 成员 |
|---|---|
| ⚡ 电 | 皮卡丘 `pikachu`(默认) |
| 🌿 草 | 妙蛙种子 `bulbasaur` → 妙蛙草 `ivysaur` → 妙蛙花 `venusaur` |
| 🔥 火 | 小火龙 `charmander` → 火恐龙 `charmeleon` → 喷火龙 `charizard` |
| 💧 水 | 杰尼龟 `squirtle` → 卡咪龟 `wartortle` → 水箭龟 `blastoise` |
| 🌀 水/恶 | 呱呱泡蛙 `froakie` → 头领蛙 `frogadier` → 忍者蛙 `greninja` → 小智忍者蛙 `ash_greninja` |
| ✨ 波导 | 利欧路 `riolu` → 路卡利欧 `lucario` → Mega路卡利欧 `mega_lucario` |

每只都有 15 状态 × 4 帧的精致 ASCII、专属配色/元素符号、按物种性格写的人设台词,
以及**各自独立的记忆**(换宝可梦像换了只新宠物,从头熟悉你;能否互看记忆由
`config.MEMORY_SHARED_ACROSS_POKEMON` 开关控制;定时提醒/任务则始终共享)。

---

## 一份数据包长什么样

每个数据包是一个 `.py` 文件,导出一个 `PACK` 字典。字段分三组:

### A. 动画帧(`states`)—— 最花功夫的部分

- `states`: `dict[状态名 → list[帧]]`,**必须包含全部 15 个状态键**(缺一个,切到该
  状态时渲染会 `KeyError`):

  ```
  idle  walk_right  walk_left  eat  sleep  happy
  jump  look  sing  yawn  surprise  struggle  think  cheer  sad
  ```

- 每个状态是一组帧(通常 4 帧,轮播成动画),每帧是一段多行字符画。
- 写完帧后用 `_normalize()` 把同一状态的各帧补齐成等行等列(见 pikachu.py),
  否则切帧会抖动。

### B. 配色 / 元素(让渲染随宝可梦变色)

| 字段 | 含义 | 皮卡丘的值 |
|---|---|---|
| `body_color` | 主体色 `(r,g,b)` | `(255,213,30)` 雷电黄 |
| `cheek_color` | 脸颊点 `·` 的颜色 | `(232,60,60)` 红 |
| `element_char` | 元素符号(一个字符) | `"⚡"` |
| `element_color` | 元素符号的颜色 | `(120,200,255)` 蓝白电花 |
| `glow_color` | 兴奋/放电时的光晕色 | `(255,230,80)` |
| `glow_states` | 哪些状态触发光晕 | `("happy","cheer")` |
| `mood_particles` | 状态→飘动粒子符号 | `{"happy":"✨","cheer":"⚡","sad":"💧"}` |

**字符渲染协议**(画帧时遵守这三条,渲染器就会自动上对色):

- `·`(U+00B7 中点)→ 渲染成 `cheek_color`(脸颊红点)
- `element_char` 设的那个符号 → 渲染成 `element_color`(皮卡丘的 `⚡`)
- 其余所有可见字符 → 渲染成 `body_color`(主体色)

> 想做「火属性」宝可梦?把帧里的 `⚡` 全换成 `🔥`、`element_char` 设成 `"🔥"`、
> `element_color` 设成橙红、`body_color` 设成橙色即可——渲染器会自动跟着变。

### C. 文案 / 人设(纯字符串)

| 字段 | 用途 |
|---|---|
| `name` | 显示名(聊天窗标题、tooltip) |
| `species` | 种族名(聊天窗副标题) |
| `persona` | 喂给 claude 的人设 system prompt(决定它的说话性格) |
| `babble` | 没装 Claude Code 时的拟声兜底台词(list) |
| `no_claude_hint` | 没装 Claude Code 时附带的温和提示 |
| `poke_reactions` | 被点击时随机冒的小气泡(list) |
| `chat_greetings` | 打开聊天窗的开场白(list) |
| `remind_messages` | 定时陪伴提醒文案(list) |
| `onboard_hint` | 首次启动的引导气泡 |
| `thinking_text` | 等 claude 回复时转圈气泡的文字(如「皮卡丘正在想…」) |
| `tray_tooltip` | 托盘图标的悬停提示 |
| `bubble_bg` / `bubble_border` / `bubble_text` | 聊天气泡的配色(十六进制色串) |
| `main_url` / `avatar_url` | 主形象 / 头像的下载 URL(PokeAPI 按图鉴编号) |

---

## 怎么新增一只宝可梦(填表三步)

### 1. 复制样板
把 `pikachu.py` 复制成 `<你的宝可梦>.py`(文件名建议用小写英文,如 `bulbasaur.py`)。

### 2. 改 PACK 各字段
- **重画 15×4 帧**:这是主要工作量。保持上面的「字符渲染协议」,脸颊用 `·`、元素位
  用你的 `element_char`。可以先把皮卡丘的帧拿来改造(换耳朵/尾巴/元素符号)。
- **改配色 / 元素**:`body_color` / `element_char` / `element_color` 等。
- **改文案 / 人设**:尤其 `persona`——它决定 claude 扮演的性格(把"皮卡丘""电气鼠"
  "放电"换成你这只的设定)。
- **改素材 URL**:PokeAPI 的 URL 里把皮卡丘的图鉴编号 `25` 换成你这只的编号
  (如妙蛙种子=1、小火龙=4、杰尼龟=7)。

> 素材文件名由 `config.py` 自动按 `ACTIVE_POKEMON` 拼成 `assets/<名字>_stand.svg` /
> `assets/<名字>_hd_main.png`,首次运行会照 URL 下载到 `assets/`。

### 3. 切换开关
在 `core/config.py` 把
```python
ACTIVE_POKEMON = "pikachu"
```
改成你的文件名(不带 `.py`),例如 `ACTIVE_POKEMON = "bulbasaur"`。
也可以在**本地控制台**在线切换(改动写进 `config_overrides.json`,下次启动自动恢复)。

重启 `python pet.py`,桌面上就是新宝可梦了。

---

## 安全网

- **拼错名 / 文件缺失 / `PACK` 缺字段** → 加载器自动**回退到 pikachu**,绝不崩。
- **用户在控制台自定义过的项**(如改过人设)→ 换包时**不会被盖掉**(`_apply_pack`
  会避让用户显式覆盖过的常量)。
- **内部标识符不随数据包变**:对话角色 ID、MCP server 名、类名等是代码内部用的,
  与显示无关,数据包不涉及它们(所以换包不影响历史记忆/对话流水的兼容)。

---

## 一句话原理

`config.py` 读 `ACTIVE_POKEMON` → 调 `pokedex.load_pack()` 拿到 `PACK` →
把 `PACK` 里的值绑到一批同名常量(`config.PIKACHU_PERSONA`、`config.PET_BODY_COLOR`…)→
`pet.py` / `chat_window.py` / `ascii_pika.py` 读这些常量。
**调用方读的常量名没变,只是值的来源变成了数据包**——所以换宝可梦零代码改动。
