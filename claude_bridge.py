"""封装本地 `claude` CLI 调用,并注入皮卡丘人设(稳定版)。

桌宠的"大脑":把用户输入发给 claude,拿回复。

⚠️ 重要设计决策:**不使用 `--continue`**。
经实测,`claude -p --continue` 在与 acceptEdits / add-dir / json 等参数组合时
会间歇性卡死(读写共享会话历史时阻塞)。为彻底规避,本模块改为:
  - 每次都是独立的单轮 `-p` 调用(稳定,~8 秒返回)
  - 多轮记忆由桌宠端自己维护:把最近若干轮对话拼进 prompt 一起发过去
这样既不卡,又有上下文记忆。
"""

import json
import subprocess
import sys
import threading

import config


class ClaudeError(Exception):
    """claude 调用失败时抛出,聊天窗据此显示友好兜底文案。"""


def _ensure_mcp_config() -> str | None:
    """生成(若不存在)指向本地定时任务 MCP server 的配置文件,返回其路径。

    挂上它后,claude 每次对话都能自主决定要不要建/查/删定时任务。
    生成失败返回 None(降级为不带工具,普通对话仍可用)。
    """
    try:
        cfg = {
            "mcpServers": {
                "pika": {
                    "command": sys.executable or "python3",
                    "args": [config.MCP_SERVER_PATH],
                }
            }
        }
        with open(config.MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return config.MCP_CONFIG_PATH
    except Exception:
        return None


def _scheduling_hint() -> str:
    """告诉 claude 它有定时任务工具,以及当前时间(用于把'今晚''3分钟后'换算成参数)。"""
    from datetime import datetime
    now = datetime.now()
    wd = "一二三四五六日"[now.weekday()]
    return (
        f"【当前时间】{now.strftime('%Y-%m-%d %H:%M')} 星期{wd}。\n"
        "【定时任务能力】你有三个工具:schedule_task(建任务)、list_tasks(查)、"
        "delete_task(删)。当用户表达「到某时提醒我做某事」或「定时帮我做某事」时,"
        "你要自己把口语时间(今晚、下周三、等会儿、半小时后…)理解成结构化参数,"
        "调用 schedule_task。判断要不要执行:只是想让你记着提醒他→mode=reminder;"
        "要你真去干活(写文件/整理/提交)→mode=action。\n"
        "若用户有提醒意图但没说具体时间(如「提醒我订火锅店」),先用皮卡丘口吻反问"
        "「*歪头* 啥时候提醒你呀?」,等他给了时间再建任务,别瞎猜时间。\n"
        "如果用户只是普通聊天或让你做一次性的事(不涉及定时),就正常回应/执行,"
        "不要调用定时工具。建完任务用皮卡丘口吻自然告诉用户记下了。\n"
        "【重要】当用户说「删掉它/取消那个/改一下提醒/把刚才那个删了」这类指令时,"
        "不要凭空说'没有任务'——先调用 list_tasks 看看实际有哪些任务,"
        "结合上文对话判断'它'指哪条,再调 delete_task 删除。"
        "对话历史里若出现过'记下啦…(id:xxxx)',那就是刚建的任务,'它'多半指它。"
    )


def _build_prompt(user_text: str, history: list[tuple[str, str]] | None) -> str:
    """把历史对话 + 当前输入拼成一个 prompt。

    history: [(role, text), ...],role 为 '我' 或 '皮卡丘'。
    """
    if not history:
        return user_text
    lines = ["以下是我们之前的对话记录,供你参考上下文:\n"]
    for role, text in history:
        lines.append(f"{role}：{text}")
    lines.append("\n现在请回应我最新的这句话：")
    lines.append(user_text)
    return "\n".join(lines)


def ask_pikachu(
    prompt: str,
    *,
    history: list[tuple[str, str]] | None = None,
    cancel_event: threading.Event | None = None,
) -> str:
    """把一句话发给皮卡丘(claude),返回回复文本。

    Args:
        prompt: 用户当前输入。
        history: 之前的对话(用于多轮记忆),(role, text) 列表。
        cancel_event: 外部可置位以取消本次调用。

    Raises:
        ClaudeError: claude 不可用、超时、被取消或返回错误时。
    """
    full_prompt = _build_prompt(prompt, history)
    persona = config.PIKACHU_PERSONA + "\n\n" + _scheduling_hint()

    cmd = [
        config.CLAUDE_BIN,
        "-p", full_prompt,
        "--append-system-prompt", persona,
        # auto 模式:智能判断每个操作的安全性,安全的(读/写常规文件、查询)
        # 自动放行,危险的(rm -rf、外发数据等)才拦截。桌宠非交互,无法手动点
        # "允许",auto 模式既能干活又有安全兜底,比 acceptEdits 更顺手。
        "--permission-mode", config.CLAUDE_PERMISSION_MODE,
        # 不再用 --add-dir 限制目录:auto 模式靠安全性判断,不靠目录白名单,
        # 否则写到白名单外(如 ~/Desktop)又会被卡。
        "--output-format", "json",
        # 注意:故意不加 --continue(会卡死)
    ]

    # 挂载定时任务 MCP 工具:让 claude 自主判断要不要建/查/删定时任务
    mcp_cfg = _ensure_mcp_config()
    if mcp_cfg:
        cmd += ["--mcp-config", mcp_cfg,
                "--allowedTools", ",".join(config.MCP_ALLOWED_TOOLS)]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=config.CLAUDE_WORKDIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ClaudeError(
            f"找不到 `{config.CLAUDE_BIN}` 命令,确认 Claude Code 已安装并在 PATH 中。"
        ) from exc

    done = threading.Event()
    holder: dict[str, str] = {}

    def _reader():
        out, err = proc.communicate()
        holder["out"], holder["err"] = out, err
        done.set()

    threading.Thread(target=_reader, daemon=True).start()

    waited = 0.0
    step = 0.3
    while waited < config.CLAUDE_TIMEOUT_SEC:
        if cancel_event is not None and cancel_event.is_set():
            proc.kill()
            done.wait(timeout=3)
            raise ClaudeError("已取消~")
        if done.wait(timeout=step):
            break
        waited += step
    else:
        proc.kill()
        done.wait(timeout=3)
        raise ClaudeError(
            f"皮卡丘想了太久(超过 {config.CLAUDE_TIMEOUT_SEC} 秒)…可以让它做小一点的任务。"
        )

    stdout = holder.get("out", "") or ""
    stderr = holder.get("err", "") or ""

    if proc.returncode != 0:
        detail = (stderr or stdout or "未知错误").strip()
        raise ClaudeError(f"皮卡丘卡住了:{detail[:300]}")

    reply = ""
    try:
        data = json.loads(stdout)
        if data.get("is_error"):
            raise ClaudeError(f"皮卡丘报错了:{str(data.get('result', '未知错误'))[:300]}")
        reply = (data.get("result") or "").strip()
    except json.JSONDecodeError:
        reply = stdout.strip()

    if not reply:
        raise ClaudeError("皮卡丘张了张嘴,但什么也没说出来(空回复)。")
    return reply


def ask_raw(prompt: str, *, timeout_sec: int = 45,
            cancel_event: threading.Event | None = None) -> str:
    """轻量纯文本调用(不带皮卡丘人设,用于内部解析任务如时间解析)。

    返回 claude 的纯文本回复。失败抛 ClaudeError。
    不需要文件/命令权限,纯推理。
    """
    cmd = [
        config.CLAUDE_BIN,
        "-p", prompt,
        "--output-format", "json",
        # 不带人设、不需要工具权限,就是让它做一次文本推理
    ]
    try:
        proc = subprocess.Popen(
            cmd, cwd=config.CLAUDE_WORKDIR, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError as exc:
        raise ClaudeError("找不到 claude 命令") from exc

    done = threading.Event()
    holder: dict[str, str] = {}

    def _reader():
        out, err = proc.communicate()
        holder["out"], holder["err"] = out, err
        done.set()

    threading.Thread(target=_reader, daemon=True).start()
    waited = 0.0
    while waited < timeout_sec:
        if cancel_event is not None and cancel_event.is_set():
            proc.kill(); done.wait(timeout=3)
            raise ClaudeError("已取消")
        if done.wait(timeout=0.3):
            break
        waited += 0.3
    else:
        proc.kill(); done.wait(timeout=3)
        raise ClaudeError("解析超时")

    stdout = holder.get("out", "") or ""
    if proc.returncode != 0:
        raise ClaudeError((holder.get("err") or stdout or "未知错误").strip()[:200])
    try:
        data = json.loads(stdout)
        return (data.get("result") or "").strip()
    except json.JSONDecodeError:
        return stdout.strip()
