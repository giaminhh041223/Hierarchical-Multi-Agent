"""Local web UI (python -m orch ui): run / inbox / board, events, agents + logins, API-key vault, team, knowledge graph,
skills, models. Binds 127.0.0.1 only. Every /api call needs the per-launch token (kept in the URL fragment, sent as
X-Orch-Token) and a local Host / Origin: other web pages and DNS-rebinding sites cannot drive it. The page renders all
data as text (no innerHTML) under a nonce CSP; vault values never leave the process unmasked."""
import hmac, json, os, secrets, subprocess, sys, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import agents, models, remote, skills
from .core import ROOT, EngineLock, mask, redact, vault, vault_set
from .engine import Engine, load_team, save_team

UI = Path(__file__).with_name("ui.html")
MAX_BODY = 100_000
MAX_PATCH = 50_000_000  # a remote runner's result: the binary patch, base64


def _file(path, limit=60_000):
    return path.read_text(encoding="utf-8", errors="replace")[-limit:] if path.exists() else ""


def spawn_engine(ws, *args):
    """The engine runs as its own process (survives the UI); its console output goes to .orch/engine.log."""
    load_team(ws)
    if EngineLock(ws).held_elsewhere():
        raise ValueError("an engine is already running on this workspace")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with open(ws.dir / "engine.log", "a", encoding="utf-8") as log:
        subprocess.Popen([sys.executable, "-m", "orch", "--ws", str(ws.project), *args], cwd=ROOT, stdin=subprocess.DEVNULL,
                         stdout=log, stderr=subprocess.STDOUT, creationflags=flags, start_new_session=os.name != "nt")
    return {"ok": f"engine started: {args[0]}"}


def api_state(ws, b, q):
    run, team = ws.run, ws.read_json("team.json") or {}
    rdir, tasks, edit = ws.dir / "runs" / str(run), ws.tasks() if run else [], None
    if team and any(t["id"] == "PLAN" and t["status"] == "pending_user" and t["answer"] is None for t in tasks):
        e = Engine(ws)  # the plan waiting for approval, for the editor (api_plan)
        if p := e.latest_plan():
            edit = {"version": p["version"], "workers": [*e.primaries()],
                    "tasks": [{k: t[k] for k in ("id", "title", "assignee", "deps")} for t in p["plan"]["tasks"]]}
    return {"project": str(ws.project), "run": run, "goal": run and ws.meta(f"{run}:goal"), "status": run and ws.meta(f"{run}:status"),
            "engine": EngineLock(ws).held_elsewhere(), "has_team": bool(team), "tasks": tasks, "edit": edit,
            "workers": [*team.get("workers", {})], "budget": int(float(run and ws.meta(f"{run}:budget") or 0)),  # 0 = no budget
            "attempts": ws.q("SELECT task, kind, agent, model, started, ended, outcome, failure, tokens_in, tokens_out, cost, dir"
                             " FROM attempts WHERE run=? ORDER BY id", run) if run else [],  # task panel and the score (UIUX §9)
            "plan": _file(rdir / "plan.md"), "report": _file(rdir / "report.md"), "log": _file(ws.dir / "engine.log", 4000)}


def api_events(ws, b, q):
    return ws.q("SELECT ts, task, actor, kind, body FROM events WHERE run=? ORDER BY id DESC LIMIT 300", ws.run)


def api_run(ws, b, q):
    goal = str(b.get("goal") or "").strip()
    if not goal or len(goal) > 8000:  # passed on a command line (Windows tops out at 32767 chars)
        raise ValueError("the goal must be 1-8000 characters")
    return spawn_engine(ws, "run", goal, *(["--yes"] if b.get("yes") else []))


def api_resume(ws, b, q):
    return spawn_engine(ws, "resume")


def api_answer(ws, b, q):
    text = str(b.get("text") or "").strip()
    if not text:  # never approve by default: 'yes' starts a plan and allows its commands
        raise ValueError("the answer is empty: type it, or use a button")
    if not ws.update(str(b.get("task")), _expect="pending_user", answer=text):
        raise ValueError("that task is not waiting for an answer any more")
    return {"ok": "recorded" + ("" if EngineLock(ws).held_elsewhere() else "; press Resume to continue")}


def api_plan(ws, b, q):
    """Save the user's edit of the plan waiting for approval (deps and workers) as its next version."""
    if not isinstance(b.get("version"), int) or not isinstance(b.get("tasks"), list):
        raise ValueError("expected {version, tasks: [{id, deps, assignee}]}")
    return {"ok": f"saved as plan v{Engine(ws).edit_plan(b['version'], b['tasks'])}: reply yes to start it"}


def api_cancel(ws, b, q):
    return {"ok": f"{ws.cancel(str(b.get('task')))} task(s) flagged"}


def api_agents(ws, b, q):
    cat = {k: a for k, a in agents.catalog().items() if not a.get("hidden")}
    return {"agents": {k: v for k, v in agents.load_resources().items() if k in cat},
            "keys": {k: sorted(set(a.get("auth_env", []) + a.get("needs_vault", []))) for k, a in cat.items()}}


def api_discover(ws, b, q):
    agents.discover(bool(b.get("probe")))
    return api_agents(ws, b, q)


def api_login(ws, b, q):
    if b.get("agent") not in agents.catalog():
        raise ValueError("unknown agent")
    return {"ok": agents.launch_login(b["agent"])}


def api_vault(ws, b, q):
    if b:
        vault_set(b.get("name"), b.get("value") or None)
    return {k: mask(v) for k, v in vault().items()}


def api_team(ws, b, q):
    cands = agents.candidates(agents.load_resources())
    s = models.suggest(cands)
    return {"team": ws.read_json("team.json"), "suggested": s and models.team_of(s),
            "candidates": [[a, m, models.card(m)] for a, m in cands]}


def api_save_team(ws, b, q):
    return {"ok": "team saved", "team": save_team(ws, b.get("team"))}


def api_kg(ws, b, q):
    text = q.get("q", "")
    return {"facts": ws.kg_search(text, 30), "links": ws.kg_neighbors(text)} if text.strip() else {"facts": [], "links": []}


def api_skills(ws, b, q):
    return {"index": skills.load_index(), "sources": [s["repo"] for s in skills.sources()],
            "run": ws.q("SELECT id, status, tasks, reason, scan FROM skills WHERE run=?", ws.run) if ws.run else []}


def api_skill(ws, b, q):
    if b.get("action") == "refresh":
        return {"ok": f"{len(skills.refresh())} skills indexed"}
    return {"ok": skills.decide(ws, str(b.get("id")), b.get("action"))}


def api_models(ws, b, q):
    if b.get("refresh"):
        models.refresh()
    db, ids = models.load(), sorted({m for _, m in agents.candidates(agents.load_resources())})
    return {"as_of": db.get("as_of"), "cards": {m: models.card(m, db) for m in ids}, "info": {m: models.info(m, db) for m in ids}}


GET = {"state": api_state, "events": api_events, "agents": api_agents, "vault": api_vault, "team": api_team, "kg": api_kg,
       "skills": api_skills, "models": api_models}
POST = {"run": api_run, "resume": api_resume, "answer": api_answer, "plan": api_plan, "cancel": api_cancel, "discover": api_discover,
        "login": api_login, "vault": api_vault, "team": api_save_team, "skill": api_skill, "models": api_models,
        "lease": remote.claim, "lease/beat": remote.beat, "lease/done": remote.done}


class Handler(BaseHTTPRequestHandler):
    timeout = 30  # a stalled client cannot pin a thread
    server_version = "orchestra"

    def reply(self, code, body, ctype="application/json; charset=utf-8", nonce=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        for k, v in (("Content-Type", ctype), ("Content-Length", str(len(data))), ("Cache-Control", "no-store"),
                     ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                     ("Content-Security-Policy", f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                                                 "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
                      if nonce else "default-src 'none'; frame-ancestors 'none'")):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def serve(self, routes):
        srv, url = self.server, urlsplit(self.path)
        lease = url.path.startswith("/api/lease")  # remote runners: their own token, which opens nothing else
        key, limit = (srv.remote_token, MAX_PATCH) if lease else (srv.token, MAX_BODY)
        ok_token = bool(key) and hmac.compare_digest(self.headers.get("X-Orch-Token", "").encode(), key.encode())
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        # read the body before any reply: on Windows a reply sent over an unread body becomes a connection reset (WinError 10053)
        raw = self.rfile.read(n) if routes is POST and 0 < n <= (limit if ok_token else MAX_BODY) else b""
        if self.headers.get("Host") not in srv.hosts:
            return self.reply(403, {"error": "bad Host"})
        if url.path == "/" and routes is GET:
            nonce = secrets.token_urlsafe(16)
            page = UI.read_text(encoding="utf-8").replace("<script>", f'<script nonce="{nonce}">').replace("<style>", f'<style nonce="{nonce}">')
            return self.reply(200, page.encode(), "text/html; charset=utf-8", nonce)
        origin = self.headers.get("Origin")
        if (origin and origin not in srv.origins) or not ok_token:
            return self.reply(403, {"error": "forbidden: remote runners need ORCH_REMOTE_TOKEN (16+ characters, the same value on "
                                             "both machines)" if lease else "forbidden: open the UI from the link printed by `python -m orch ui`"})
        fn = url.path.startswith("/api/") and routes.get(url.path[5:])
        if not fn:
            return self.reply(404, {"error": "not found"})
        try:
            body = {}
            if routes is POST:
                if not 0 <= n <= limit or not (self.headers.get("Content-Type") or "").startswith("application/json"):
                    return self.reply(413, {"error": f"JSON bodies up to {limit} bytes only"})
                body = json.loads(raw or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("a JSON object is expected")
            self.reply(200, fn(srv.ws, body, {k: v[0] for k, v in parse_qs(url.query).items()}))
        except (ValueError, RuntimeError, OSError, KeyError, SystemExit) as e:  # load_team raises SystemExit
            self.reply(400, {"error": redact(str(e))[:2000]})

    def do_GET(self):
        self.serve(GET)

    def do_POST(self):
        self.serve(POST)

    def log_message(self, *args):  # quiet: the console belongs to the user; URLs carry no secrets anyway
        pass


def make_server(ws, port=8765):
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:  # port taken (another app): any free port will do, the printed link carries it
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads, srv.ws, srv.token = True, ws, secrets.token_urlsafe(24)
    rt = os.environ.get("ORCH_REMOTE_TOKEN") or vault().get("ORCH_REMOTE_TOKEN")
    srv.remote_token = rt if rt and len(rt) >= 16 else None  # None: remote runners are refused
    srv.remote_short = bool(rt) and not srv.remote_token
    port = srv.server_address[1]  # port 0 = any free port (tests)
    srv.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    srv.origins = {f"http://{h}" for h in srv.hosts}
    srv.url = f"http://127.0.0.1:{port}/#{srv.token}"
    return srv


def serve(ws, port=8765, browser=True):
    srv = make_server(ws, port)
    print(f"Hoatau UI for {ws.project}:\n  {srv.url}\n(the link holds this session's access token; Ctrl+C stops the UI, not a running engine)")
    if srv.remote_token or srv.remote_short:  # never the token itself
        print("remote runners: on (ORCH_REMOTE_TOKEN)" if srv.remote_token else
              "remote runners: OFF, ORCH_REMOTE_TOKEN is shorter than 16 characters")
    if browser:
        webbrowser.open(srv.url)
    srv.serve_forever()
