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
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time

import config


class ClaudeError(Exception):
    """claude 调用失败时抛出,聊天窗据此显示友好兜底文案。"""


# claude CLI 是否在 PATH 的进程内缓存:None=未检测,True/False=已知结果。
# 缓存避免每次发消息都走一遍 shutil.which(查 PATH 是系统调用);代价是用户
# 运行期间才装好 claude 需重启(或调 invalidate_claude_cache)才生效——可接受。
_claude_ok_cache = None

# 危险操作确认:hook 拦截后会阻塞等用户点确认气泡,这段"等人"时间不该计入硬超时。
# 用【计数器】而非单个 Event:可能同时有多条危险操作在等确认(或并发的多个 claude
# 调用各自在等),计数 >0 表示"还有人在等人类",ask_pikachu 的超时循环据此暂停 deadline。
# 计数器(而非 bool/Event)保证:A 调用的确认解决后递减,不会误把 B 调用仍在等的暂停态
# 一并清掉——只有所有等待都结束(归零)才真正恢复倒计时。pet.py 轮询到 pending 时
# begin_await(),确认/拒绝/超时回收时 end_await()。与 ask_pikachu 同进程,跨线程可见。
_await_lock = threading.Lock()
_await_count = 0


def begin_await() -> None:
    """登记一条"正在等用户确认"。桌宠轮询到新 pending 时调。"""
    global _await_count
    with _await_lock:
        _await_count += 1


def end_await() -> None:
    """注销一条等待(确认/拒绝/超时回收时调)。下限 0,重复调不会变负。"""
    global _await_count
    with _await_lock:
        if _await_count > 0:
            _await_count -= 1


def reset_await() -> None:
    """清零等待计数(shutdown 用:退出时不再等任何人)。"""
    global _await_count
    with _await_lock:
        _await_count = 0


def _is_awaiting() -> bool:
    with _await_lock:
        return _await_count > 0


def claude_available() -> bool:
    """检测 claude CLI 是否可用(只查 PATH 是否存在该命令,轻量、带缓存)。

    故意【不】实际跑 `claude --version`:那会起子进程、慢,且本函数会在聊天
    热路径(每次发消息前)被调用,必须廉价。只判断"命令存不存在"已足够区分
    "没装 Claude Code"这一最常见的不可用场景;真正运行期报错仍由 ask_* 内部
    的 ClaudeError 兜底。任何异常都按"可用"处理,绝不因探测本身挡住聊天。
    """
    global _claude_ok_cache
    if _claude_ok_cache is None:
        try:
            _claude_ok_cache = shutil.which(config.CLAUDE_BIN) is not None
        except Exception:
            _claude_ok_cache = True      # 探测失败不该误判为不可用,放行给后续调用
    return _claude_ok_cache


def invalidate_claude_cache() -> None:
    """清掉可用性缓存:用户中途装好 claude 后可据此复检(暂留作手动/重启复检用)。"""
    global _claude_ok_cache
    _claude_ok_cache = None


def _register_proc(proc: subprocess.Popen):
    """把 claude 子进程的 pid 登记给退出清理/看门狗(失败不致命)。"""
    try:
        import cleanup
        cleanup.register_pid(proc.pid)
    except Exception:
        pass


def _deregister_proc(proc: subprocess.Popen):
    """claude 子进程结束后从登记移除,防止其 pid 被系统复用后被误杀。"""
    try:
        import cleanup
        cleanup.deregister_pid(proc.pid)
    except Exception:
        pass


def _kill_proc_tree(proc: subprocess.Popen):
    """杀掉 proc 及其整个进程组(含 claude 拉起的 MCP 孙进程)。

    为什么不能只 proc.kill():claude 会通过 --mcp-config 拉起 pika_mcp.py 子进程。
    只 kill claude 父进程,MCP 孙进程会变孤儿,且它可能仍持有 stdout/stderr 管道
    写端的副本 → 父进程的 communicate() 永远等不到 EOF、_reader 线程永久阻塞泄漏
    (fd + 线程)。配合 Popen(start_new_session=True) 把整组进程放进独立会话,
    这里用 killpg 一次性全杀。
    """
    # start_new_session=True 使子进程自成进程组 leader,pgid == pid。直接对 pid
    # 发 killpg,不绕 os.getpgid——后者对刚退出/僵尸进程可能成功返回但语义不稳,
    # 且多一次系统调用多一个失败点。pgid==pid 是 Popen 时就确定的不变式。
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        # 进程已退出或拿不到进程组,退化为直接 kill 父进程
        try:
            proc.kill()
        except Exception:
            pass
    # 关键(F 修复):主动关闭管道读端,强制 communicate() 拿到 EOF 立刻返回。
    # 否则——killpg 回退到只 kill 父进程时,claude 拉起的 MCP 孙进程仍存活并
    # 持有 stdout/stderr 写端副本,communicate() 永远等不到 EOF → _reader daemon
    # 线程永久阻塞、持有 fd 不释放。高频取消会累积僵线程,耗尽 fd 上限(macOS 默认 256)。
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


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
        # 原子写:两条消息几乎同时发出时会有两个线程同时进来写同一文件,直接
        # open("w") 会各自截断,内容可能交错成损坏 JSON → claude 读不了 → MCP
        # 工具整体降级、定时任务功能失效。先写带 pid 的临时文件再 os.replace
        # (同目录内原子),读方永远看到完整的旧版或完整的新版。
        tmp = f"{config.MCP_CONFIG_PATH}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, config.MCP_CONFIG_PATH)
        return config.MCP_CONFIG_PATH
    except Exception:
        return None


def _ensure_pet_settings() -> str | None:
    """生成(若不存在则写)挂载危险操作守门 hook 的 settings 文件,返回其路径。

    经 `--settings <path>` 注入,只对本次 claude 调用生效,【不污染】用户全局
    ~/.claude/settings.json。matcher=Bash 让 hook 只在 Bash 工具调用前触发(其余工具
    零开销)。timeout=300 > CONFIRM_HOOK_TIMEOUT_SEC(280),给 hook 留足阻塞等确认的时间。
    生成失败返回 None(降级为不挂 hook;此时 A 层硬拦截失效,靠 B 层软护栏兜底)。
    """
    try:
        cfg = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                # Claude Code 把 command 字段交给 shell 执行,会按空格分词。
                                # macOS 用户名常含空格/中文(如 /Users/John Smith/…),不 quote
                                # 会被拆错 → hook 启动失败、A 层硬拦截静默失效。用 shlex.quote
                                # 把解释器路径和脚本路径各自包好,空格路径也能正确启动。
                                "command": (
                                    f"{shlex.quote(sys.executable or 'python3')} "
                                    f"{shlex.quote(config.GUARDIAN_PATH)}"
                                ),
                                "timeout": 300,
                            }
                        ],
                    }
                ]
            }
        }
        # 原子写,理由同 _ensure_mcp_config:并发两条消息同时进来不会写出损坏 JSON。
        tmp = f"{config.PET_SETTINGS_PATH}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, config.PET_SETTINGS_PATH)
        return config.PET_SETTINGS_PATH
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
    # 注入长期记忆:让皮卡丘"记得"主人(在学什么、喜好、没做完的事…),
    # 自然体现在对话里。失败/无记忆则不注入,绝不影响聊天。
    if getattr(config, "MEMORY_ENABLED", False):
        try:
            import memory
            mem_summary = memory.recent_memory_summary()
            if mem_summary:
                persona += "\n\n" + mem_summary
        except Exception:
            pass

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

    # 挂载危险操作守门 hook(A 层硬拦截):rm -rf / git push --force / sudo 等不可逆
    # 命令在执行前被 hook 拦下,阻塞等用户在桌宠上点确认气泡。只对本次调用生效,不污染
    # 全局配置。生成失败则降级为不挂(靠 B 层软护栏兜底)。
    pet_settings = _ensure_pet_settings()
    if pet_settings:
        cmd += ["--settings", pet_settings]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=config.CLAUDE_WORKDIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # 显式钉死 UTF-8:claude 输出含中文/emoji,text=True 默认跟随系统 locale,
            # LANG=C 等非 UTF-8 环境会 UnicodeDecodeError → 被兜底成"皮卡丘短路了"。
            encoding="utf-8",
            errors="replace",
            # 独立会话/进程组:取消或超时时可用 killpg 连同 MCP 孙进程一起杀干净
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise ClaudeError(
            f"找不到 `{config.CLAUDE_BIN}` 命令,确认 Claude Code 已安装并在 PATH 中。"
        ) from exc

    # 登记本子进程的 pgid(==pid,因 start_new_session=True),供退出清理/看门狗
    # 在主进程死后 killpg 兜底,避免 kill -9 主进程时 claude/MCP 变孤儿。
    _register_proc(proc)

    done = threading.Event()
    holder: dict[str, str] = {}

    def _reader():
        # try/finally:communicate() 可能抛(如管道被 _kill_proc_tree 提前 close
        # 后再读)。若不兜底,_deregister_proc 漏调(stale pid 残留→PID 复用误杀)、
        # done.set() 漏调(主线程在 done.wait(3) 上白等满 3 秒才超时返回)。
        try:
            out, err = proc.communicate()
            holder["out"], holder["err"] = out, err
        except Exception:
            holder.setdefault("out", "")
            holder.setdefault("err", "")
        finally:
            # communicate 返回 = 子进程已退出(或已被杀)→ 从登记移除,防 pid 复用误杀
            _deregister_proc(proc)
            done.set()

    threading.Thread(target=_reader, daemon=True).start()

    # 用单调时钟算 deadline,而非累加 step:系统繁忙时 done.wait(step) 实际阻塞
    # 可能远超 step,若按 waited+=step 计数会严重低估真实耗时,导致硬超时翻倍。
    deadline = time.monotonic() + config.CLAUDE_TIMEOUT_SEC
    step = 0.3
    timed_out = True
    while time.monotonic() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            _kill_proc_tree(proc)        # killpg 连 hook 子进程一起杀,不残留阻塞
            done.wait(timeout=3)
            raise ClaudeError("已取消~")
        # 危险操作确认暂停:hook 拦截后桌宠会 begin_await(),此刻 claude 子进程正阻塞在
        # hook 里等用户点确认。把 deadline 持续后移,使这段"等人"时间不计入硬超时——
        # 否则用户慢慢考虑要不要删,500s 到点会误杀正等确认的调用。计数归零(所有等待
        # 都结束:确认/拒绝/桌宠侧超时回收)后,deadline 不再被后移,恢复正常倒计时。
        if _is_awaiting():
            deadline = time.monotonic() + config.CLAUDE_TIMEOUT_SEC
        if done.wait(timeout=step):
            timed_out = False
            break
    if timed_out:
        _kill_proc_tree(proc)
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
            encoding="utf-8", errors="replace",  # 同上:钉死 UTF-8,防非 UTF-8 locale 解码崩
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise ClaudeError("找不到 claude 命令") from exc

    _register_proc(proc)

    done = threading.Event()
    holder: dict[str, str] = {}

    def _reader():
        try:
            out, err = proc.communicate()
            holder["out"], holder["err"] = out, err
        except Exception:
            holder.setdefault("out", "")
            holder.setdefault("err", "")
        finally:
            _deregister_proc(proc)
            done.set()

    threading.Thread(target=_reader, daemon=True).start()
    deadline = time.monotonic() + timeout_sec
    timed_out = True
    while time.monotonic() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            _kill_proc_tree(proc); done.wait(timeout=3)
            raise ClaudeError("已取消")
        if done.wait(timeout=0.3):
            timed_out = False
            break
    if timed_out:
        _kill_proc_tree(proc); done.wait(timeout=3)
        raise ClaudeError("解析超时")

    stdout = holder.get("out", "") or ""
    if proc.returncode != 0:
        raise ClaudeError((holder.get("err") or stdout or "未知错误").strip()[:200])
    try:
        data = json.loads(stdout)
        return (data.get("result") or "").strip()
    except json.JSONDecodeError:
        return stdout.strip()
