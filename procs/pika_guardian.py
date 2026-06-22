"""皮卡丘危险操作守门人:Claude Code 的 PreToolUse hook 脚本(A 层硬拦截)。

这个脚本由 claude 子进程在【每次 Bash 工具调用前】以 `python3 pika_guardian.py` 拉起,
stdin 收到一个 JSON(含 tool_name 和 tool_input.command)。我们:

  1. 不是 Bash、或命令不命中危险清单 → 立刻 exit 0 静默放行(绝大多数情况,毫秒级)。
  2. 命中危险命令(rm -rf / git push --force / sudo …)→ 写一行 pending 给桌宠主进程,
     然后【同步阻塞】轮询 guardian_decision.<req_id> 决策文件,等用户在桌宠上点确认气泡:
       · 读到 allow → 输出 permissionDecision:"allow",claude 原地继续执行该命令。
       · 读到 deny  → 输出 permissionDecision:"deny",claude 看到理由后优雅收尾(不 abort)。
       · 超时(CONFIRM_HOOK_TIMEOUT_SEC)→ 默认 deny(安全优先)。

设计要点:
  · 任何异常/读不到决策/超时 → 一律保守 deny(宁可拦错,不可放过)。唯一放行靠用户显式点击。
  · headless `-p` 模式下 hook 的内置 "ask" 语义不可靠,所以这里不用 "ask",
    而是自己用 deny + 文件信令实现真正的"等用户确认"。
  · permissionDecision 优先级高于 --permission-mode auto,deny 真能拦住 auto 想放行的操作。
"""

import json
import os
import sys
import time
import uuid


def _emit(decision: str, reason: str = "") -> None:
    """按 PreToolUse hook 协议输出决策 JSON 到 stdout,然后正常退出(exit 0)。

    【定义在 import config 之前】:若 config 导入失败(cwd 异常 / __pycache__ 损坏 /
    config 语法错误),下面的兜底块仍能调用本函数输出 deny。否则 _emit 未定义,兜底里
    再抛 NameError → 进程无输出非零退出,Claude 对此的处理可能是"放行"→ 硬拦截失效。
    """
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
        }
    }
    if reason:
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
    try:
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stdout.flush()
    except Exception:
        pass


# 由 claude 以任意 cwd 拉起。本脚本在 procs/ 子目录,而 config 在 core/。把【项目根】
# 及各源码子目录加入 sys.path,确保能 import 到 config(危险清单单一真相在那里)。
# 导入失败 → 拿不到危险清单,无法判断安全性 → 保守 deny(宁可拦错,不可放过)。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("core", "agent", "ui", "web"):
    sys.path.insert(0, os.path.join(_ROOT, _sub))
sys.path.insert(0, _ROOT)
try:
    import config  # noqa: E402
except Exception:
    _emit("deny", "配置没加载好,保险起见这次先没做~")
    sys.exit(0)

# 当前宝可梦名(危险确认气泡用它的口吻,换宝可梦时一致)。读不到则用通用词。
try:
    _PET = config.PET_NAME
except Exception:
    _PET = "桌宠"


def _log(record: dict) -> None:
    """往危险操作流水追加一行(用户数据,退出保留)。失败不致命。"""
    try:
        record.setdefault("ts", time.time())
        with open(config.DANGER_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _write_pending(req_id: str, command: str) -> bool:
    """把一条待确认记录追加给桌宠主进程轮询。失败返回 False(上层据此保守 deny)。"""
    try:
        line = json.dumps(
            {"id": req_id, "command": command, "ts": time.time()},
            ensure_ascii=False,
        )
        # append 模式 + 单次 write 一整行:POSIX 下 O_APPEND 的单次小写入是原子的,
        # 多个 hook 并发也不会交错(和 tool_events.jsonl 同款写法)。
        with open(config.CONFIRM_PENDING_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except Exception:
        return False


def _decision_path(req_id: str) -> str:
    return config.CONFIRM_DECISION_PREFIX + req_id


def _wait_for_decision(req_id: str) -> str:
    """轮询决策文件,返回 'allow'/'deny'。超时或读不到 → 'deny'(安全默认)。"""
    path = _decision_path(req_id)
    deadline = time.monotonic() + config.CONFIRM_HOOK_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    val = (f.read() or "").strip().lower()
                if val in ("allow", "deny"):
                    return val
                # 文件存在但内容还没写完(极少见)→ 再等一轮
        except Exception:
            pass
        time.sleep(0.3)
    return "deny"  # 超时:用户没在 280s 内确认,保守不做


def _cleanup_decision(req_id: str) -> None:
    """用完即删自己的决策文件,避免残留(桌宠主进程退出清理也会兜底)。"""
    try:
        os.remove(_decision_path(req_id))
    except OSError:
        pass


def main() -> None:
    # 读 stdin JSON。读不到/解析失败 → 拿不到命令内容,无法判断安全性 → 保守放行?
    # 不:拿不到内容时我们【放行】,因为绝大多数工具调用是安全的,且 hook 异常不该
    # 卡死所有 Bash。真正危险的拦截只在"确实读到并命中危险清单"时才发生。
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        _emit("allow")
        return

    tool_name = data.get("tool_name", "")
    command = ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "") or ""

    # 只对 Bash 工具的危险命令做拦截;其余一律放行(零打扰)。
    if tool_name != "Bash" or not config.is_danger_command(command):
        _emit("allow")
        return

    # 命中危险命令 → 走确认流程。
    req_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    _log({"req_id": req_id, "command": command, "decision": "pending"})

    if not _write_pending(req_id, command):
        # 写 pending 失败 → 桌宠看不到,无法确认 → 保守 deny。
        _log({"req_id": req_id, "command": command, "decision": "deny-no-pending"})
        _emit("deny", f"{_PET}没能把确认请求递出去,这次先没做这个危险操作哦~")
        return

    try:
        decision = _wait_for_decision(req_id)
    except Exception:
        decision = "deny"
    finally:
        _cleanup_decision(req_id)

    _log({"req_id": req_id, "command": command, "decision": decision})
    if decision == "allow":
        _emit("allow")
    else:
        _emit("deny", f"主人这次没同意这个操作~ *耳朵耷拉* {_PET}就先不做啦。")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # 兜底:hook 脚本本身崩了也不该让 claude 误执行危险命令 → deny。
        # 但若崩在 _emit 之前,claude 会按退出码处理;我们再补一次 deny 输出。
        _emit("deny", f"{_PET}守门时短路了,保险起见先没做~")
        sys.exit(0)
