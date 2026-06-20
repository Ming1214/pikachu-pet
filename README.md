<div align="center">

# ⚡ PIKA-PET

```
 (\~~/) _/⚡
 (o.o·) ) /
 zz zz zz ⌐
```

### 一只住在你菜单栏下方的皮卡丘 · 会卖萌,更会干活

跟它聊天 = 调用本地 **Claude Code**。
它用奶里奶气的皮卡丘腔回你,背地里却真能读写文件、跑命令、改代码、定闹钟。

<br>

![platform](https://img.shields.io/badge/macOS-000?style=for-the-badge&logo=apple&logoColor=white)
![python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pyqt](https://img.shields.io/badge/PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![claude](https://img.shields.io/badge/Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)

<br>

*萌系皮囊 · 硬核内核 · pika pika ⚡*

</div>

---

## 🌩️ 为什么是它

> 桌宠很多,**能帮你干活的桌宠**只有一只。

它不是一张会动的贴纸,而是一个**披着皮卡丘皮的 Claude Code 终端**。你以「逗宠物」的心态丢一句话,它先 `*跳起来* 交给皮卡丘!⚡`,然后把活漂漂亮亮干完,再 `*翘尾巴* 搞定啦~`。

```
你:「帮我把桌面的截图按日期分类」
皮卡丘:*耳朵竖起来* 皮卡!这就去~ ⚡
        └─→ (后台真的在 mkdir / mv 整理你的文件)
皮卡丘:*得意翘尾巴* 搞定啦!整理好 23 张啦~
```

---

## ✨ 能耐一览

<table>
<tr>
<td width="50%" valign="top">

#### 🎬 15 种手绘 ASCII 动画
待机 · 走路 · 张嘴吃 · 趴睡 · 跳跃 · 东张西望 · 哼歌 · 打哈欠 · 开心放电 · 大欢呼 · 沮丧…
每只都有 **毛茸茸波浪耳 `(\~~/)`、红脸颊 `·`、闪电尾 `_/⚡`、z 形小爪 `zz`**。

#### 🤖 会自己生活
没人理就自顾自玩:加权随机溜达、发呆、啃果子;闲久了打个哈欠,趴下睡着。

#### 🖱️ 有脾气的互动
戳它 → `(>_<)` 缩一下再开心放电;
拖它走 → `\(O_O)/` 手脚乱蹬挣扎。

</td>
<td width="50%" valign="top">

#### 💬 唤起 Claude Code
点开精灵球红白主题聊天窗,一句话驱动真实任务 —— 读写文件、跑命令、改代码,全在后台线程,界面不卡。

#### ⏰ 自然语言定时
「今晚 8 点提醒我喝水」「3 分钟后帮我整理截图」——
皮卡丘自己听懂时间,到点**提醒**你或**真去执行**。

#### 🌟 电影级特效层
走路扬尘 `·˙·`、放电边缘光晕、情绪粒子 ✨/💧 飘动 —— 全部可一键开关。

#### 🧩 记忆碎片 · 越处越熟
后台每隔半小时悄悄整理你们的对话,把「你在学黄金 ETF」「那个脚本还没写」这类有价值的事记成长期记忆,聊天时自然带出来 —— 处得越久越懂你。

#### 🗨️ 主动搭话
**独立轮询**(每 45 分钟、不依赖新对话),直接读整个记忆库,发现值得聊的(没做完的事 / 作息关怀 / 兴趣延续 / 纯陪伴)就主动冒泡找你;点一下接着开聊。

#### 🖥️ 全桌面常驻
浮在所有 Space / 全屏 App 之上,不进 Dock,托盘随时召唤或退出。

</td>
</tr>
</table>

---

## 🎭 动画图鉴

四类驱动,15 个状态,切换不抖、宽度统一:

| 类别 | 状态 | 触发 |
|:--|:--|:--|
| **🧘 自主** | idle · walk · eat · look · jump · sing · yawn · sleep | 没人互动时按权重随机切换;闲久打哈欠→趴睡 |
| **💢 反馈** | surprise · struggle | 被戳缩一下再开心;被拖乱蹬挣扎 |
| **🎯 情境** | think · cheer · sad | 等回复时挠头;任务成功大欢呼、失败头顶乌云 |
| **🪄 特效** | dust · glow · particles | 叠在字符之上,不改帧,可单独开关 |

<div align="center">

```
   惊讶          挣扎          欢呼            沮丧
 (\~~/)      \(\~~/)/     ⚡ ✨ ⚡         ☁☁☁
 (>_<·)!      (O_O·)      \(\~~/)/       (\~~/)
 (")(")      /(")(")      ⚡(^o^·)⚡       (T_T·)
  pika!       ~wah~        DONE!⚡         uuu..
```

</div>

---

## 🚀 上手三步

```bash
# 1. 装依赖(PyQt6 + mcp)
pip install -r requirements.txt

# 2. 确认 claude 已就位
which claude          # 没有?先装并登录 Claude Code

# 3. 召唤皮卡丘
python pet.py
```

桌面立刻多一只皮卡丘 👇

| 操作 | 反应 |
|:--|:--|
| **单击** | 缩一下卖萌 + 打开聊天窗 |
| **拖拽** | 拖到任意角落(会挣扎) |
| **晾着不管** | 自己玩 → 打哈欠 → 趴睡 |
| **右键托盘** | 打开对话 / 立即提醒 / 退出 |

---

## 🧠 干活原理

```
单击皮卡丘 ─→ 聊天窗 ─→ 后台 QThread(不阻塞 UI)
                          │
                          └─→ claude -p "<你的话 + 多轮历史>"
                                --append-system-prompt "<皮卡丘人设>"
                                --permission-mode auto          ← 安全放行/危险拦截
                                --mcp-config <定时任务工具>
                                --allowedTools mcp__pika__*
                          │
                          └─→ 回复 ─→ 皮卡丘语气显示
```

- **`auto` 权限** — 智能判断安全性,适合无人值守的桌宠,能真正创建/修改文件、跑命令。
- **拒绝 `--continue`** — 实测它与多参数组合会卡死;多轮记忆改为**把历史拼进 prompt**,每次都是独立稳定的单轮调用。
- **轻人设重内核** — 人设只点缀语气(「皮卡~」),代码与说明始终准确清晰。

---

## ⏰ 定时任务(MCP)

不靠正则猜时间,而是让 **Claude 自己读懂自然语言**再下任务:

> 「**每周三早上 9 点**提醒我开周会」 · 「**3 分钟后**帮我整理桌面」

- `reminder` — 到点冒气泡提醒你
- `action` — 到点皮卡丘**真去执行**,完成大欢呼 🎉、失败则沮丧 ☁️

任务存于 `scheduled_tasks.json`,工具定义在 `pika_mcp.py`(`schedule` / `list` / `delete`)。

---

## 🧩 记忆碎片 & 主动搭话

让皮卡丘**慢慢越来越熟悉你**,而不是每次都当陌生人。

```
每轮对话 ─→ conversation.jsonl(流水)
                  │  整理线:每 30 分钟轮询,无新对话则跳过(零开销)
                  ↓
            claude 整理提炼 ─→ memory.json(机器主存)+ memory.md(人类可读)
                                记忆带时间锚点、权重老化、超量淘汰、近似去重
                                      │
        ┌─────────────────────────────┴─────────────────────────────┐
        ↓                                                            ↓
  聊天时注入高权重记忆                            主动搭话线(独立!每 45 分钟):
  → 皮卡丘「记得」你                       本地频率门全过 → claude 读【整个记忆库】判断
                                          → 该关心就本体冒气泡主动找你(不依赖新对话)
```

- **整理** — 后台 QThread 调 claude **纯文本推理**,不阻塞界面;**这段时间没新对话就整段跳过**,不空跑。
- **记忆会老化** — 每条记忆按天衰减权重,长期没提及的低权重记忆自动淘汰,防无限膨胀;再被提到则权重回升。
- **主动搭话独立于整理** — 它**不看「有没有新对话」,而是直接读整个记忆库**:哪怕你聊完就晾着,久搁的待办、该关心的作息点,每 45 分钟都有机会被重新翻出来找你。(旧版搭话寄生在整理流程里,没新对话就永远不搭话,错过一次就再不提——已修。)
- **主动搭话有分寸** — 五重本地频率门:静默时段(默认 23:00–08:00)不打扰、你刚操作过不打断、两次间隔/每日上限都受限,**门全过才真去调 claude**(绝大多数轮次零开销)。claude 只「提议」话题,要不要真打扰由本地把关。
- **四类搭话依据** — ① 没做完的事 ② 时间/作息关怀 ③ 兴趣话题延续 ④ 纯陪伴。

记忆数据(`memory.json` / `memory.md` / `conversation.jsonl`)都是**你的私人数据**,不入库、退出保留。整套存储引擎在 [`memory.py`](memory.py),沿用定时任务同款 flock 跨进程锁 + 原子写。

> **没装 Claude Code 也不崩** — 此时皮卡丘聊天会用拟声词回你(「皮卡皮卡~⚡」)并温和提示去装 Claude Code,后台整理/主动搭话自动跳过、不空转。装好重启即恢复全部能力。

---

## 🎛️ 调教手册

全在 **[`config.py`](config.py)**,挑几个常用的:

```python
ASCII_FONT_PX        = 22       # 字号(皮卡丘大小)
ASCII_FRAME_MS       = 420      # 动画速度(越大越慢)
SLEEP_AFTER_MS       = 180000   # 闲多久自动睡(默认 3 分钟)
REMIND_INTERVAL_MIN  = 45       # 喝水/休息提醒间隔
PLAY_WEIGHTS         = {...}    # 自主玩耍各动作权重

FX_DUST_ENABLED      = True     # 走路扬尘
FX_GLOW_ENABLED      = True     # 放电光晕
FX_MOOD_ENABLED      = True     # 情绪粒子 ✨/💧

MEMORY_ENABLED       = True     # 记忆碎片总开关
DIGEST_INTERVAL_MS   = 1800000  # 后台整理间隔(默认 30 分钟)
PROACTIVE_ENABLED    = True     # 主动搭话总开关
PROACTIVE_CHECK_INTERVAL_MS = 2700000  # 主动搭话独立轮询间隔(默认 45 分钟)
PROACTIVE_MAX_PER_DAY = 6       # 主动搭话每日上限(活泼;想克制调小)
PROACTIVE_QUIET_HOURS = (23, 8) # 静默时段,夜里不主动打扰

CLAUDE_WORKDIR       = "~/Desktop/Claude-Code"   # 干活目录
CLAUDE_PERMISSION_MODE = "auto"                  # 权限模式
```

---

## 🗂️ 项目结构

```
pikachu-pet/
├── pet.py            # 主程序:窗口 / 状态机 / 动画 / 特效 / 拖拽 / 托盘
├── ascii_pika.py     # 帧库:15 状态 × 4 帧,统一对齐
├── chat_window.py    # 聊天窗(精灵球主题)+ 后台 claude 线程
├── claude_bridge.py  # claude CLI 封装 + 人设注入 + 多轮历史
├── macos_window.py   # macOS 全 Space 常驻窗口层级
├── scheduler.py      # 定时任务存储 / 触发 / 自然语言后备解析
├── pika_mcp.py       # MCP server:schedule / list / delete 工具
├── memory.py         # 记忆碎片引擎:对话流水 / 记忆库 / 老化淘汰 / md 导出
├── config.py         # 集中配置
└── requirements.txt  # PyQt6 + mcp
```

---

## 🩺 卡住了?

| 症状 | 解法 |
|:--|:--|
| 皮卡丘不出现 | `pip install -r requirements.txt`,看终端报错 |
| 皮卡丘只会「皮卡皮卡」不好好说话 | 没装 / 没登录 Claude Code,`which claude` 确认后装好重启 |
| 回复很慢 | 复杂任务本就耗时,皮卡丘会同步挠头思考 |
| 字符/特效错位 | `⚡✨ω♪☁💧` 等宽字符可能略溢格,调 `ASCII_FONT_PX` |
| 想换干活目录 | 改 `config.py` 的 `CLAUDE_WORKDIR` |

---

<div align="center">

#### ⚡ Pokémon、皮卡丘形象版权归 任天堂 / Game Freak / The Pokémon Company

个人学习娱乐用途 · ASCII 字符画为原创二次演绎

<br>

**`(\~~/)` ⚡ pika pika~**

</div>
