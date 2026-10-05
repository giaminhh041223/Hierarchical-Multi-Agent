"""MCP server on stdio (python -m orch [--ws P] mcp): the task board and the knowledge graph as read-only tools. Agents in a
run get it per call when team.json has "mcp": true (agents.mcp_server); you can register the same command in your own Claude
Code or Codex session. JSON-RPC 2.0, one message per line; stdout carries protocol messages only.

`mcp --control` adds tools that drive runs (run, status, answer, resume, cancel, doctor): your own Claude Code or Codex session
delegates a goal to the team and relays your answers. Agents inside a run never get it (agents.mcp_server has no --control)."""
import json, sqlite3, sys, time, types
from pathlib import Path

from . import __version__
from .core import TERMINAL, EngineLock, Workspace

VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")  # newest first; a client's own version is echoed back


def kg_search(ws, a):
    rows = ws.kg_search(str(a.get("query") or ""), max(1, min(int(a.get("k") or 8), 30)))
    return "\n".join(f"- {r['entity']}: {r['fact']}  [{r['task']}]" for r in rows) or "no matching facts"


def kg_links(ws, a):
    rows = ws.kg_neighbors(str(a.get("node") or ""))
    return "\n".join(f"- {r['src']} -{r['rel']}-> {r['dst']}" for r in rows) or "no links"


def board(ws, a):
    return ws.board()


TOOLS = {  # name: (function, description, input properties, required)
    "kg_search": (kg_search, "Search the facts that integrated tasks published (only work that passed verification). "
                             "One line per fact: entity: fact [task].",
                  {"query": {"type": "string", "description": "free text, e.g. auth token refresh"},
                   "k": {"type": "integer", "minimum": 1, "maximum": 30, "description": "how many facts, default 8"}}, ["query"]),
    "kg_links": (kg_links, "Relations of a node. For a task id: the files it changed and the tasks it ran after. "
                           "For a file path: the tasks that changed it.",
                 {"node": {"type": "string", "description": "a task id or a repository-relative file path"}}, ["node"]),
    "board": (board, "The current run: goal, status, and every task with its status, worker, attempts and dependencies.", {}, []),
}


# --- control tools (--control only) ----------------------------------------------------------------------------------------
def _engine_running(ws):
    return EngineLock(ws).held_elsewhere()


def status(ws, a):
    run = ws.run
    if not run:
        return "no run yet: start one with the run tool"
    st, engine, lines = ws.meta(f"{run}:status") or "open", _engine_running(ws), [ws.board()]
    pend = ws.tasks("pending_user")
    lines.append(f"engine: {'running' if engine else 'stopped'}")
    for t in pend:
        lines.append(f"\nWAITING FOR THE USER: {t['id']}" + (" (answer received, not applied yet)" if t["answer"] is not None else "")
                     + f"\n{t['question']}")
    report = ws.dir / "runs" / run / "report.md"
    if st in TERMINAL and report.exists():
        lines.append(f"\n{report.read_text(encoding='utf-8')[:6000]}")
    elif pend:
        lines.append("\nAsk the user, then relay their words with the answer tool. Only answer 'yes' to a plan when the user approved it:"
                     " approving a plan also allows its verify commands.")
    elif not engine and st not in TERMINAL:
        lines.append("\nThe engine stopped with work left (a crash or a restart): call the resume tool.")
    return "\n".join(lines)


def _wait_meta(ws, key, old, seconds=15):
    end = time.time() + seconds
    while time.time() < end and ws.meta(key) == old:
        time.sleep(0.2)
    return ws.meta(key)


def run(ws, a):
    from .engine import git_ok, spawn_engine
    goal = str(a.get("goal") or "").strip()
    if not goal or len(goal) > 8000:
        raise ValueError("goal: 1-8000 characters")
    if not git_ok(ws.project, "rev-parse", "--verify", "HEAD"):
        raise ValueError(f"{ws.project} needs a git repository with at least one commit")
    old = ws.run
    if old and (ws.meta(f"{old}:status") or "open") not in TERMINAL:
        raise ValueError(f"run {old} is still open (see the status tool): finish or cancel it first")
    # --exit-on-wait: the engine exits while the run waits for the user; the answer tool starts it again
    spawn_engine(ws, "run", goal, *(["--yes"] if a.get("auto_approve") else []), "--exit-on-wait")
    new = _wait_meta(ws, "run", old)
    return (f"run {new} started. The lead plans first; poll the status tool (every 20-60 s is plenty)." if new != old else
            "the engine was started but has not opened a run yet: check the status tool, or .orch/engine.log")


def resume(ws, a):
    from .engine import spawn_engine
    if not ws.run or (ws.meta(f"{ws.run}:status") or "open") in TERMINAL:
        raise ValueError("no open run to resume")
    if _engine_running(ws):
        return "the engine is already running"
    spawn_engine(ws, "resume", "--exit-on-wait")
    return "engine resumed: poll the status tool"


def answer(ws, a):
    from .engine import spawn_engine
    tid, text = str(a.get("task") or ""), str(a.get("text") or "").strip()
    if not text:
        raise ValueError("text: the user's answer, e.g. yes, retry, cancel, reassign <worker>, or instructions")
    if not ws.update(tid, _expect="pending_user", answer=text):
        raise ValueError(f"{tid} is not waiting for an answer (see the status tool)")
    end = time.time() + 10  # an engine about to pause still holds its lock: wait until it takes the answer or exits
    while time.time() < end:
        t = ws.task(tid)
        if not t or t["status"] != "pending_user" or t["answer"] is None:
            return f"answer recorded; the engine picked it up ({tid} is now {t and t['status']})"
        if not _engine_running(ws):
            spawn_engine(ws, "resume", "--exit-on-wait")
            return "answer recorded; engine resumed to apply it: poll the status tool"
        time.sleep(0.25)
    return "answer recorded; the running engine applies it on its next step"


def cancel(ws, a):
    from .engine import spawn_engine
    n = ws.cancel(str(a.get("task") or ""))
    if not n:
        return "no such live task (see the status tool)"
    if not _engine_running(ws):
        spawn_engine(ws, "resume", "--exit-on-wait")  # the engine applies cancellations (kills agents, cascades to dependents)
    return f"{n} task(s) flagged for cancellation; the engine applies it: poll the status tool"


def doctor(ws, a):
    from . import doctor as d
    return d.report(ws.project)[0]  # ws is just the project here: the check must work before any workspace exists


CONTROL = {  # name: (function, description, input properties, required, writes)
    "run": (run, "Start a run: the lead plans the goal with the reviewer, then workers implement it in parallel git worktrees and "
                 "the engine verifies and merges into branch orch/<run>/main (never the user's branch). Returns at once; poll status.",
            {"goal": {"type": "string", "description": "what the team should build or fix, in the user's words"},
             "auto_approve": {"type": "boolean", "description": "skip the user's plan approval (default false; only if the user asked)"}},
            ["goal"], True),
    "status": (status, "The current run: task board, engine state, questions waiting for the user, and the final report when done.",
               {}, [], False),
    "answer": (answer, "Relay the user's answer to a task waiting for them (status lists them): yes / retry / cancel / "
                       "reassign <worker> / free-text instructions. Never approve a plan on your own: approval also allows its "
                       "verify commands.",
               {"task": {"type": "string", "description": "task id, e.g. PLAN, T2, REVIEW"},
                "text": {"type": "string", "description": "the user's answer"}}, ["task", "text"], True),
    "resume": (resume, "Start the engine again for the open run (after a crash, a restart, or an answer given elsewhere).", {}, [], True),
    "cancel": (cancel, "Cancel one live task (its dependents follow) or 'all' to stop the run.",
               {"task": {"type": "string", "description": "a task id, or all"}}, ["task"], True),
    "doctor": (doctor, "Local readiness check of this machine and project (no network, no agent calls).", {}, [], None),
}


def handle(msg, project, control=False):
    """One JSON-RPC message -> its response, or None for a notification (those are never answered)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return {"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None,
                "error": {"code": -32600, "message": "invalid request"}}
    if "id" not in msg:
        return None
    method, p, res = msg["method"], msg.get("params"), None
    p = p if isinstance(p, dict) else {}
    if method == "initialize":
        res = {"protocolVersion": p.get("protocolVersion") if p.get("protocolVersion") in VERSIONS else VERSIONS[0],
               "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "hoatau", "version": __version__},
               "instructions": (f"Hoatau team for {project}: start a run, follow it with status, relay the user's answers. "
                                "Questions to the user come back through status; never answer them yourself." if control else
                                f"Read-only view of the Hoatau run in {project}: the task board and the knowledge graph.")}
    elif method == "ping":
        res = {}
    elif method == "tools/list":
        tools = {**{n: (*t, False) for n, t in TOOLS.items()}, **(CONTROL if control else {})}
        res = {"tools": [{"name": n, "description": d,
                          "annotations": {"readOnlyHint": not w, **({"destructiveHint": n == "cancel"} if w else {})},
                          "inputSchema": {"type": "object", "properties": props, **({"required": req} if req else {})}}
                         for n, (_, d, props, req, w) in tools.items()]}
    elif method == "tools/call":
        tool, args = TOOLS.get(p.get("name")) or (CONTROL.get(p.get("name")) if control else None), p.get("arguments") or {}
        if not tool or not isinstance(args, dict):
            return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32602, "message": f"unknown tool or bad arguments: {p.get('name')}"}}
        try:  # a fresh connection per call: always the latest board, nothing held between calls; read-only unless the tool writes
            writes = tool[4] if len(tool) > 4 else False  # None: the tool needs no workspace database
            if writes is False and not (Path(project) / ".orch" / "orch.db").exists():
                return {"jsonrpc": "2.0", "id": msg["id"], "result": {"isError": False, "content": [{"type": "text", "text":
                        f"no run yet: no hoatau workspace in {project} (start one with the run tool, or python -m orch init)"}]}}
            ws = types.SimpleNamespace(project=project) if writes is None else Workspace(project, readonly=not writes)
            ws.quiet = True  # stdout carries protocol messages only
            try:
                text, bad = tool[0](ws, args), False
            finally:
                if writes is not None:
                    ws.db.close()
        except (sqlite3.Error, ValueError, TypeError, RuntimeError, OSError, SystemExit) as e:  # load_team raises SystemExit
            text, bad = f"error: {e}" + (" (no hoatau workspace here?)" if isinstance(e, sqlite3.OperationalError) else ""), True
        res = {"content": [{"type": "text", "text": text}], "isError": bad}
    else:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": msg["id"], "result": res}


def serve(project, inp=None, out=None, control=False):
    inp, out = inp or sys.stdin.buffer, out or sys.stdout.buffer
    for line in inp:
        if not line.strip():
            continue
        msg = None
        try:
            msg = json.loads(line)
            reply = handle(msg, project, control)
        except ValueError:  # undecodable line (handle() turns tool errors into results itself)
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        except Exception as e:  # one bad message must not end the agent's session with this server
            reply = {"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None, "error": {"code": -32603, "message": str(e)}}
        if reply is not None:
            out.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
            out.flush()
