"""MCP server on stdio (python -m orch [--ws P] mcp): the task board and the knowledge graph as read-only tools. Agents in a
run get it per call when team.json has "mcp": true (agents.mcp_server); you can register the same command in your own Claude
Code or Codex session. JSON-RPC 2.0, one message per line; stdout carries protocol messages only."""
import json, sqlite3, sys

from .core import Workspace

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


def handle(msg, project):
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
               "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "orchestra", "version": "0.1"},
               "instructions": f"Read-only view of the Hoatau run in {project}: the task board and the knowledge graph."}
    elif method == "ping":
        res = {}
    elif method == "tools/list":
        res = {"tools": [{"name": n, "description": d, "annotations": {"readOnlyHint": True},
                          "inputSchema": {"type": "object", "properties": props, **({"required": req} if req else {})}}
                         for n, (_, d, props, req) in TOOLS.items()]}
    elif method == "tools/call":
        tool, args = TOOLS.get(p.get("name")), p.get("arguments") or {}
        if not tool or not isinstance(args, dict):
            return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32602, "message": f"unknown tool or bad arguments: {p.get('name')}"}}
        try:  # a fresh read-only connection per call: always the latest board, nothing held between calls
            ws = Workspace(project, readonly=True)
            try:
                text, bad = tool[0](ws, args), False
            finally:
                ws.db.close()
        except (sqlite3.Error, ValueError, TypeError) as e:
            text, bad = f"error: {e}" + (" (no orchestra workspace here?)" if isinstance(e, sqlite3.OperationalError) else ""), True
        res = {"content": [{"type": "text", "text": text}], "isError": bad}
    else:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": msg["id"], "result": res}


def serve(project, inp=None, out=None):
    inp, out = inp or sys.stdin.buffer, out or sys.stdout.buffer
    for line in inp:
        if not line.strip():
            continue
        msg = None
        try:
            msg = json.loads(line)
            reply = handle(msg, project)
        except ValueError:  # undecodable line (handle() turns tool errors into results itself)
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        except Exception as e:  # one bad message must not end the agent's session with this server
            reply = {"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None, "error": {"code": -32603, "message": str(e)}}
        if reply is not None:
            out.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
            out.flush()
