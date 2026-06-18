<div align="center">

# ⚡ 皮卡丘桌宠 · Pikachu Desktop Pet

```
  (\__/)_/⚡
  (o.o ) /
  (")(")⌐
```

**一只活在你桌面上的皮卡丘 —— 会自己玩、会跟你闹,聊一句就能帮你真·干活。**

它用 ASCII 字符画蹦蹦跳跳,被戳会吓一跳、被拖会乱蹬;
而当你点开对话框跟它说话时,背后跑的是本地 `claude` CLI ——
所以它不只是卖萌,是真能读写文件、跑命令、改代码、定闹钟的 Claude Code。

*极致皮卡丘语气 × Claude Code 全部能力。*

</div>

---

## ✨ 一眼看懂

| | |
|---|---|
| 🎬 **15 种手绘 ASCII 动画** | 待机眨眼 / 走路 / 吃东西 / 睡觉 / 跳跃 / 东张西望 / 哼歌 / 打哈欠 / 开心放电 / 大欢呼 / 沮丧… |
| 🤖 **自主行为** | 没人理它就自己玩:加权随机在桌面上溜达、发呆、啃果子;闲久了先打哈欠再睡着 |
| 🖱️ **互动反馈** | 戳一下 → 缩起来吓一跳再开心放电;拖着走 → 手脚乱蹬挣扎 `\(O_O)/` |
| 🌟 **视觉特效层** | 走路扬尘 `·˙·`、放电时身后淡黄光晕、情绪粒子(✨ 上浮 / 💧 下落) |
| 💬 **唤起 Claude Code** | 点开聊天窗,皮卡丘语气回复,底层执行真实任务(读写文件 / 跑命令 / 改代码) |
| ⏰ **定时陪伴 + MCP 任务** | 内置喝水提醒;还能用自然语言让它「今晚 8 点提醒我」「3 分钟后帮我整理截图」 |
| 🖥️ **全桌面常驻** | 浮在所有 Space / 全屏 App 之上,不进 Dock,右键托盘可退出 |

---

## 🎭 动画图鉴

皮卡丘的每个状态都是一组手绘字符帧,统一对齐后切换不抖动。按触发方式分四类:

<table>
<tr><th>类别</th><th>状态</th><th>什么时候出现</th></tr>
<tr>
<td><b>A · 自主行为</b></td>
<td><code>idle</code> <code>walk</code> <code>eat</code> <code>look</code> <code>jump</code> <code>sing</code> <code>yawn</code> <code>sleep</code></td>
<td>没人互动时,按 <code>PLAY_WEIGHTS</code> 权重随机切换;跳跃配合窗口抛物线上移,闲久了打哈欠→睡着</td>
</tr>
<tr>
<td><b>B · 互动反馈</b></td>
<td><code>surprise</code> <code>struggle</code></td>
<td>被点击 → 缩一下吓一跳再开心;被拖拽 → 乱蹬挣扎,松手后喘口气回归</td>
</tr>
<tr>
<td><b>C · 情境动画</b></td>
<td><code>think</code> <code>cheer</code> <code>sad</code></td>
<td>聊天等回复时挠头思考;定时任务成功 → 大欢呼放电;失败 → 头顶乌云流泪</td>
</tr>
<tr>
<td><b>D · 视觉特效</b></td>
<td>扬尘 / 光晕 / 粒子</td>
<td>叠在字符之上、不改帧;走路扬尘、happy/cheer 边缘光晕、情绪粒子飘动</td>
</tr>
</table>

> 几个示例帧(实际是动起来的):
>
> ```
>   惊讶          挣扎          欢呼            沮丧
>  (\__/)      \(\__/)/     ⚡ ✨ ⚡         ☁☁☁
>  (>_< )!      (O_O )      \(\__/)/        (\__/)
>  (")(")      /(")(")      ⚡(^o^ )⚡       (T_T )
>   pika!       ~wah~        DONE!⚡         uuu..
> ```

---

## 🚀 快速开始

### 前置要求

- **macOS**(在 macOS 开发验证;其他平台 PyQt6 一般也能跑)
- **Python 3.10+**
- 已安装并登录 **[Claude Code](https://claude.com/claude-code)**,`claude` 命令在 PATH 中
  - 验证:`which claude`

### 安装 & 运行

```bash
cd pikachu-pet
pip install -r requirements.txt    # PyQt6 + mcp
python pet.py
```

桌面就会出现一只皮卡丘。

| 操作 | 效果 |
|---|---|
| **单击** | 缩一下卖萌 + 打开/聚焦聊天窗 |
| **拖拽** | 把它拖到屏幕任意角落(会挣扎) |
| **不理它** | 它自己玩;闲久了打哈欠睡觉 |
| **右键托盘图标** | 打开对话 / 立即提醒 / 退出 |

---

## 💬 它是怎么真·干活的

```
点击皮卡丘 ─→ 聊天窗 ─→ 后台 QThread(不阻塞 UI)
                          │
                          └─→ subprocess 调用本地 CLI:
                              claude -p "<你的话(含多轮历史)>"
                                     --append-system-prompt "<皮卡丘人设>"
                                     --permission-mode auto      # 安全放行/危险拦截
                                     --mcp-config <定时任务工具>
                                     --allowedTools mcp__pika__*
                          │
                          └─→ 拿到回复 ─→ 用皮卡丘语气显示在聊天窗
```

几个关键设计:

- **不阻塞 UI** —— claude 调用全在 `QThread` 里,思考时皮卡丘照常动、界面不卡。
- **`auto` 权限模式** —— 靠安全性智能判断(安全的放行、危险的拦截),适合无人值守的桌宠,
  不靠目录白名单。皮卡丘能创建/修改文件、执行命令。
- **故意不用 `--continue`** —— 实测它与 `acceptEdits`/`--mcp-config` 等组合会卡死;
  多轮记忆改为**把历史拼进 prompt** 实现,每次都是独立稳定的单轮调用(详见 `claude_bridge.py` 顶部说明)。
- **轻度人设** —— 通过 `--append-system-prompt` 注入,只在语气上点缀「皮卡~」,
  技术内容(代码、说明)保持准确清晰。

---

## ⏰ 定时任务(MCP)

不靠 Python 正则猜时间,而是让 **claude 自己理解自然语言时间**再调用 MCP 工具下任务:

> 「**今晚 8 点提醒我喝水**」「**每周三早上 9 点提醒我开周会**」「**3 分钟后帮我把桌面截图整理一下**」

- `reminder` 模式:到点只冒气泡提醒你。
- `action` 模式:到点皮卡丘**真去执行**(写文件 / 整理 / 提交代码…),完成大欢呼、失败则沮丧。
- 任务存在 `scheduled_tasks.json`,由 `scheduler.py` 轮询触发;
  工具定义在 `pika_mcp.py`(`schedule_task` / `list_tasks` / `delete_task`)。

---

## 🔧 配置

所有可调项集中在 **[`config.py`](config.py)**。常用的:

#### 行为与节奏
| 配置项 | 含义 | 默认 |
|---|---|---|
| `ASCII_FONT_PX` | 字符画字号(越大皮卡丘越大) | 22 |
| `ASCII_FRAME_MS` | 每帧间隔(动画速度) | 420 |
| `PLAY_WEIGHTS` | 自主玩耍各动作的抽中权重 | walk 最高 |
| `SLEEP_AFTER_MS` | 无互动多久后自动睡 | 180000(3 分钟) |
| `REMIND_INTERVAL_MIN` | 喝水/休息提醒间隔 | 45 |

#### 视觉特效层(D)·均可单独开关
| 配置项 | 含义 | 默认 |
|---|---|---|
| `FX_DUST_ENABLED` | 走路扬尘 | `True` |
| `FX_GLOW_ENABLED` | 放电边缘光晕 | `True` |
| `FX_MOOD_ENABLED` | 情绪粒子(✨/💧) | `True` |
| `FX_MOOD_MAX` | 同屏粒子上限(防堆积) | 12 |

#### Claude 集成
| 配置项 | 含义 | 默认 |
|---|---|---|
| `CLAUDE_WORKDIR` | 皮卡丘干活的工作目录 | `~/Desktop/Claude-Code` |
| `CLAUDE_PERMISSION_MODE` | 权限模式 | `auto` |
| `CLAUDE_TIMEOUT_SEC` | 单次调用超时 | 300 |
| `PIKACHU_PERSONA` | 皮卡丘人设 system prompt | 像真宠物,不像助手 |

---

## 🗂️ 文件结构

```
pikachu-pet/
├── pet.py            # 主程序:窗口 / 状态机 / 动画 / 特效 / 拖拽 / 托盘 / 提醒
├── ascii_pika.py     # ASCII 帧库:15 个状态,每个 4 帧,统一对齐
├── chat_window.py    # 聊天窗(精灵球红白主题)+ 后台调用 claude 的线程
├── claude_bridge.py  # 封装 claude CLI 调用 + 人设注入 + 多轮历史拼接
├── macos_window.py   # macOS 全 Space 常驻的窗口层级处理
├── scheduler.py      # 定时任务存储 / 轮询触发 / 自然语言解析后备
├── pika_mcp.py       # MCP server:暴露 schedule/list/delete 工具给 claude
├── config.py         # 集中配置(外观 / 行为 / 特效 / 人设 / 集成)
├── requirements.txt  # PyQt6 + mcp
└── assets/           # 头像等素材
```

---

## 🧩 动效是怎么实现的(给想改的人)

- **帧库**:`ascii_pika.py` 里每个状态是 4 帧字符串,`_normalize()` 把所有帧补齐到统一行数列宽,
  切换时窗口不抖。新增动作只要往这里加一组帧 + 在 `STATES` 注册即可。
- **状态机**:`pet.py` 的 `_on_anim`(每 `ASCII_FRAME_MS` 一跳)驱动 `_tick_behavior`
  (状态到期 → 选新状态、移动窗口)和 `_tick_particles`(粒子推进)。
- **动作链**:`_set_state(state, dur, then=(下个状态, 时长))` 让「惊讶→开心」这类组合不被随机玩耍打断。
- **跳跃**:抛物线 `lift = JUMP_HEIGHT_PX * 4 * p * (1-p)`(p 为进度,峰值在 p=0.5),配合 `move()` 上移窗口。
- **粒子**:轻量字典列表 `{x, y, vx, vy, ch, life, max}`,进入情绪态的那一帧生成,
  每帧推进并按 `life/max` 淡出,受 `FX_MOOD_MAX` 上限约束。
- **特效叠加**:光晕 / 扬尘 / 粒子都在 `paintEvent` 里叠在字符之上,不改帧 —— 关掉开关即恢复纯字符画。

---

## 🩺 故障排查

| 现象 | 排查 |
|---|---|
| **皮卡丘不出现** | 确认 PyQt6 已装(`pip install -r requirements.txt`);看终端有无报错 |
| **聊天报「找不到 claude」** | 确认 `which claude` 有输出、已登录 Claude Code |
| **回复很慢** | 复杂任务本来就要时间;聊天窗会显示「思考中…」,皮卡丘同步挠头思考 |
| **字符/特效错位** | `⚡✨○♪♫☁💧` 等宽字符可能略微溢出格子;在 `config.py` 调字号或在 `ascii_pika.py` 换纯 ASCII |
| **想让它在别处干活** | 改 `config.py` 的 `CLAUDE_WORKDIR` |
| **想关掉某个特效** | 改 `config.py` 的 `FX_*_ENABLED` |

---

## 📜 版权说明

Pokémon、皮卡丘等名称与形象版权归 **任天堂 / Game Freak / The Pokémon Company** 所有。
本项目为个人学习娱乐用途,ASCII 字符画为原创二次演绎。

<div align="center">

*pika pika~ ⚡*

</div>
