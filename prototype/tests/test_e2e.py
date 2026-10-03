"""End-to-end tests driving the real engine with the scripted mock agent (zero cost).
Run: python tests/test_e2e.py [name-filter ...]   (pytest -q tests also works)"""
import datetime, http.server, json, os, shutil, sqlite3, stat, subprocess, sys, tempfile, threading, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["ORCH_HOME"] = tempfile.mkdtemp(prefix="orch-home-")  # in-process tests never touch the real ~/.orchestra
from orch import agents, pool  # noqa: E402
from orch.core import vault_set  # noqa: E402
from orch.engine import allowed, check_plan, file_map, in_scope  # noqa: E402

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
REPOS = []


def task(id, worker, scope, verify, deps=()):
    return {"id": id, "title": f"task {id}", "assignee": worker, "deps": list(deps), "acceptance": [f"{id} works"],
            "scope_paths": scope, "verify": verify}


class Repo:
    def __init__(self, scenario, files=None, **team):
        self.tmp = Path(tempfile.mkdtemp(prefix="orch-test-"))
        REPOS.append(self)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        for p, text in {"README.md": "demo\n", **(files or {})}.items():
            (self.repo / p).write_text(text, encoding="utf-8")
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
            subprocess.run(GIT + args, cwd=self.repo, check=True, capture_output=True)
        self.base = self.git("rev-parse", "HEAD")
        self.scenario = self.tmp / "scenario.json"
        self.scenario.write_text(json.dumps(scenario), encoding="utf-8")
        mock = lambda m: {"agent": "mock", "model": m}
        cfg = {"lead": mock("mock-strong"), "reviewer": mock("mock-strong"), "skill_architect": mock("mock-fast"),
               "workers": {"w1": {**mock("mock-fast"), "max": 1}, "w2": {**mock("mock-fast"), "max": 1}}, "skills": False, **team}
        (self.repo / ".orch").mkdir()
        (self.repo / ".orch" / "team.json").write_text(json.dumps(cfg), encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items() if k not in ("ORCH_CRASH_AT", "ORCH_WS", "ORCH_NOTIFY_URL")}
        self.env.update(ORCH_HOME=str(self.tmp / "home"), ORCH_MOCK=str(self.scenario))

    def orch(self, *args, **env):
        r = subprocess.run([sys.executable, "-m", "orch", "--ws", str(self.repo), *args], cwd=ROOT, env={**self.env, **env},
                           capture_output=True, encoding="utf-8", errors="replace", timeout=300)
        self.out = r.stdout + r.stderr
        return r.returncode

    def run(self, **env):
        return self.orch("run", "demo goal", "--yes", "--exit-on-wait", **env)

    def git(self, *args):
        return subprocess.run(GIT + list(args), cwd=self.repo, capture_output=True, encoding="utf-8").stdout.strip()

    def q(self, sql, *args):
        db = sqlite3.connect(self.repo / ".orch" / "orch.db")
        try:
            return db.execute(sql, args).fetchall()
        finally:
            db.close()

    def status(self):
        return dict(self.q("SELECT id, status FROM tasks"))

    def calls(self, role, task):
        f = Path(f"{self.scenario}.state") / f"{role}-{task}"
        return int(f.read_text()) if f.exists() else 0

    def outcomes(self, tid):
        return [r[0] for r in self.q("SELECT outcome FROM attempts WHERE task=? AND kind='work' ORDER BY id", tid)]

    def events(self, kind, tid):
        return self.q("SELECT id, body FROM events WHERE kind=? AND task=? ORDER BY id", kind, tid)

    @property
    def main(self):  # the run's integration branch
        return f"orch/{self.q('SELECT v FROM meta WHERE k=?', 'run')[0][0]}/main"

    def show(self, path):
        return self.git("show", f"{self.main}:{path}")


ADD = "def add(a, b):\n    return a + b\n"
OK = [["python", "-c", "print('ok')"]]


def two_tasks():
    """T1 writes app.py (publishes a fact); T2 depends on T1 and tests it."""
    return {"plan": [task("T1", "w1", ["app.py"], [["python", "-c", "import app; assert app.add(2, 3) == 5"]]),
                     task("T2", "w2", ["test_app.py"], [["python", "test_app.py"]], ["T1"])],
            "steps": {"worker:T1": [{"write": {"app.py": ADD}, "reply": {"facts": ["app: add(a, b) returns a + b"]}}],
                      "worker:T2": [{"write": {"test_app.py": "import app\nassert app.add(1, 1) == 2\n"}}]}}


def test_happy_path():
    r = Repo(two_tasks())
    assert r.run() == 0, r.out
    assert r.status() == {"PLAN": "done", "T1": "done", "T2": "done", "REVIEW": "done"}, r.status()
    assert "return a + b" in r.show("app.py") and "assert" in r.show("test_app.py")
    assert r.git("rev-parse", "HEAD") == r.base, "the user's branch must stay untouched"
    assert r.q("SELECT entity, fact FROM facts") == [("app", "app: add(a, b) returns a + b")]
    assert r.orch("kg", "search", "add") == 0 and "returns a + b" in r.out, "a query of only common words must still search"
    assert '-c "import app; assert' in r.events("verify", "T1")[0][1], "commands are shown quoted"
    t2_prompt = Path(r.q("SELECT dir FROM attempts WHERE task='T2' AND kind='work'")[0][0]) / "prompt.md"
    assert "app: add(a, b) returns a + b" in t2_prompt.read_text(encoding="utf-8"), "dependency handoff must reach T2"
    assert (r.repo / ".orch" / "runs" / r.main.split("/")[1] / "report.md").exists()


def test_crash_during_integration():
    """Codex test 1: crash after the git merge, before SQLite commits. One integration, evidence kept, dependent once."""
    r = Repo(two_tasks())
    assert r.run(ORCH_CRASH_AT="after_merge") == 17, r.out
    assert r.status()["T1"] == "integrating"
    assert r.orch("resume", "--exit-on-wait") == 0, r.out
    assert r.status()["T1"] == "done" and r.status()["T2"] == "done", r.status()
    assert len(r.events("integrated", "T1")) == 1 and len(r.events("reconcile", "T1")) == 1
    assert r.q("SELECT count(*) FROM facts")[0][0] == 1
    assert r.calls("worker", "T1") == 1 and r.calls("worker", "T2") == 1
    assert (Path(r.q("SELECT dir FROM attempts WHERE task='T1' AND kind='work'")[0][0]) / "stdout.txt").exists()


def test_untrustworthy_completion():
    """Codex test 2: valid JSON says done, but the diff leaves scope / verify fails: no merge, no facts, no dependent."""
    sc = two_tasks()
    sc["steps"]["worker:T1"] = [
        {"write": {"app.py": ADD, "secret.txt": "x"}, "reply": {"facts": ["bad: out-of-scope attempt"]}},
        {"delete": ["secret.txt"], "write": {"app.py": "def add(a, b):\n    return a - b\n"}, "reply": {"facts": ["bad: broken attempt"]}},
        {"write": {"app.py": ADD}, "reply": {"facts": ["app: add(a, b) returns a + b"]}}]
    r = Repo(sc)
    assert r.run() == 0, r.out
    assert r.outcomes("T1") == ["scope", "verify", "integrated"], r.outcomes("T1")
    assert [f for (f,) in r.q("SELECT fact FROM facts")] == ["app: add(a, b) returns a + b"]
    integrated = r.events("integrated", "T1")[0][0]
    assert r.calls("worker", "T2") == 1 and all(i > integrated for i, _ in r.events("start", "T2"))
    assert "secret.txt" not in r.git("log", "--name-only", "--format=", r.main), "rejected files must not reach the history"


def test_blocked_branch_live_sibling():
    """Codex test 3: auth failure on T1 while T2 completes; the answer requeues T1 once, T2 is not rerun."""
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK), task("T2", "w2", ["b.txt"], OK)],
          "steps": {"worker:T1": [{"exit": 1, "stderr": "Error: Not logged in. Please run /login"}, {"write": {"a.txt": "a\n"}}],
                    "worker:T2": [{"write": {"b.txt": "b\n"}}]}}
    r = Repo(sc)
    assert r.run() == 3, r.out
    assert r.status()["T1"] == "pending_user" and r.status()["T2"] == "done", r.status()
    assert "login" in r.q("SELECT question FROM tasks WHERE id='T1'")[0][0]
    assert r.orch("answer", "T1", "retry") == 0, r.out
    assert r.orch("resume", "--exit-on-wait") == 0, r.out
    assert set(r.status().values()) == {"done"}, r.status()
    assert r.calls("worker", "T1") == 2 and r.calls("worker", "T2") == 1
    assert r.outcomes("T1") == ["auth", "integrated"]


def test_malformed_handoff_is_repaired():
    sc = two_tasks()
    sc["steps"]["worker:T1"] = [{"write": {"app.py": ADD}, "raw": "All done! I changed app.py."}, {}]
    r = Repo(sc)
    assert r.run() == 0, r.out
    assert r.outcomes("T1") == ["integrated"] and r.calls("worker", "T1") == 2
    log = (Path(f"{r.scenario}.state") / "calls.log").read_text(encoding="utf-8")
    assert "worker T1 2 resume" in log and "repair=1" in log, log


def test_timeout_then_lead_reassigns():
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK)],
          "steps": {"worker:T1": [{"sleep": 60}, {"write": {"a.txt": "a\n"}}],
                    "lead:T1": [{"reply": {"action": "reassign", "assignee": "w2", "note": "w1 timed out; w2 takes over"}}]}}
    r = Repo(sc, timeout=3)
    t0 = time.time()
    assert r.run() == 0, r.out
    assert time.time() - t0 < 45, "the stuck agent must be killed at the timeout"
    assert r.outcomes("T1") == ["timeout", "integrated"], r.outcomes("T1")
    assert r.q("SELECT assignee FROM tasks WHERE id='T1'")[0][0] == "w2"


def test_usage_limit_rotates_and_switches_back():
    """w1's account runs out mid-task: backup w2 continues the partial work; after the reset T1 returns to w1.
    The reviewer's account runs out too: another role stands in. Backups never appear in the lead's roster."""
    quota = lambda wait: {"exit": 1, "stderr": f"You've hit your usage limit. Try again in {wait}."}
    sc = {"plan": [task("T1", "w1", ["a.txt"], [["python", "-c", "assert open('a.txt').read() == 'part\\nrest\\n'"]])],
          "steps": {"worker:T1": [{"write": {"a.txt": "part\n"}, **quota("3s")}, {"sleep": 3}, {"write": {"a.txt": "part\nrest\n"}}],
                    "reviewer:REVIEW": [quota("2h"), {}]}}
    r = Repo(sc, reviewer={"agent": "mock@c", "model": "mock-strong"}, wait_reset=1,
             workers={"w1": {"agent": "mock", "model": "mock-fast"}, "w2": {"agent": "mock@b", "model": "mock-fast", "backup": True}})
    assert r.run() == 0, r.out
    assert r.outcomes("T1") == ["quota", "verify", "integrated"], r.outcomes("T1")
    moves = [b.split(":")[0] for _, b in r.events("todo", "T1") if b.startswith("reassigned")]
    assert moves == ["reassigned w1 -> w2", "reassigned w2 -> w1"], moves
    assert r.show("a.txt").splitlines() == ["part", "rest"]
    w2_prompt = Path(r.q("SELECT dir FROM attempts WHERE task='T1' AND agent='mock@b'")[0][0]) / "prompt.md"
    assert "unfinished changes" in w2_prompt.read_text(encoding="utf-8")
    assert r.q("SELECT agent, outcome FROM attempts WHERE task='REVIEW' ORDER BY id") == [("mock@c", "quota"), ("mock", "ok")]
    assert r.events("stand_in", "REVIEW") and r.q("SELECT count(*) FROM meta WHERE k='cool:mock@c'")[0][0] == 1
    plan_prompt = Path(r.q("SELECT dir FROM attempts WHERE task='PLAN' AND kind='plan'")[0][0]) / "prompt.md"
    assert "- w1:" in plan_prompt.read_text(encoding="utf-8") and "- w2:" not in plan_prompt.read_text(encoding="utf-8")


QUOTA = {"exit": 1, "stderr": "You've hit your usage limit. Try again in 2h."}


def test_pre_rotation_skips_an_exhausted_worker():
    """w1's account runs out on T1: T2, still queued for w1, moves to the backup without spending a failing call first, and
    its new worker is not told about unfinished changes that do not exist."""
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK), task("T2", "w1", ["b.txt"], OK)],
          "steps": {"worker:T1": [QUOTA, {"write": {"a.txt": "a\n"}}], "worker:T2": [{"write": {"b.txt": "b\n"}}]}}
    r = Repo(sc, workers={"w1": {"agent": "mock", "model": "mock-fast"}, "w2": {"agent": "mock@b", "model": "mock-fast", "backup": True}})
    assert r.run() == 0, r.out
    assert (r.outcomes("T1"), r.outcomes("T2")) == (["quota", "integrated"], ["integrated"]), (r.outcomes("T1"), r.outcomes("T2"))
    assert r.q("SELECT agent FROM attempts WHERE task='T2'") == [("mock@b",)]
    prompt = (Path(r.q("SELECT dir FROM attempts WHERE task='T2'")[0][0]) / "prompt.md").read_text(encoding="utf-8")
    assert "reassigned from w1" in prompt and "unfinished changes" not in prompt


def test_quota_outlook_from_codex_rollouts():
    """codex's own rate-limit snapshots give used %, pace and reset time (conversation lines are never parsed); an account
    at 100% is out until its reset."""
    home, old = Path(tempfile.mkdtemp(prefix="orch-codex-")), os.environ.get("CODEX_HOME")
    f = home / "sessions" / "2026" / "10" / "03" / "rollout-x.jsonl"
    f.parent.mkdir(parents=True)
    t0 = int(time.time()) - 3600
    iso = lambda ts: datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    snap = lambda dt, used, weekly: json.dumps({"timestamp": iso(t0 + dt), "type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "primary": {"used_percent": used, "window_minutes": 300, "resets_at": t0 + 7200},
        "secondary": {"used_percent": weekly, "window_minutes": 10080, "resets_at": t0 + 500000}}}})
    chat = json.dumps({"timestamp": iso(t0), "type": "response_item", "payload": {"content": "private"}})
    f.write_text("\n".join([chat, snap(0, 40, 6), snap(1800, 60, 6)]) + "\n", encoding="utf-8")
    os.environ["CODEX_HOME"] = str(home)
    try:
        five, week = agents.usage("codex", now=t0 + 1800)
        assert (five["minutes"], five["used"], five["burn"], week["burn"]) == (300, 60, 40, 0), (five, week)
        o = pool.outlook("codex", now=t0 + 1800)  # 40 %/h with 40 % left: out in 1 h, the reset is 1.5 h away
        assert o["text"].startswith("5h 60%") and "runs out ~" in o["text"] and o["risk"] and not o["out_until"], o
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(snap(1900, 100, 7) + "\n")
        assert agents.usage_reset("codex") == t0 + 7200 and pool.outlook("codex")["out_until"] == t0 + 7200
    finally:
        os.environ.pop("CODEX_HOME") if old is None else os.environ.update(CODEX_HOME=old)
        shutil.rmtree(home, ignore_errors=True)


def test_router_profile_lists_models_and_routes_opencode():
    """opencode@9router against a stand-in OpenAI-compatible router: its model list, the vault key sent as a Bearer header and
    never written into the generated config; with opencode installed, one real call routed through it. Also: spawned CLIs get
    PWD = their cwd (opencode trusts PWD over the real cwd)."""
    d = Path(tempfile.mkdtemp(prefix="orch-pwd-"))
    agents.spawn([sys.executable, "-c", "import os; print(os.environ['PWD'])"], d, agents.clean_env(), out=d / "o.txt", err=d / "e.txt")
    assert (d / "o.txt").read_text(encoding="utf-8").strip() == str(d.resolve()), (d / "o.txt").read_text(encoding="utf-8")
    shutil.rmtree(d, ignore_errors=True)
    seen = []

    class Router(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body, ctype="application/json"):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body.encode())))
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            seen.append((self.path, {k.lower(): v for k, v in self.headers.items()}))
            self.send(json.dumps({"object": "list", "data": [{"id": "kr/claude-sonnet-4.5"}, {"id": "glm/glm-4.6"}]}))

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or "{}")
            seen.append((self.path, {k.lower(): v for k, v in self.headers.items()}))
            base, usage = {"id": "c1", "created": int(time.time()), "model": req.get("model", "")}, {"prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10}
            if not req.get("stream"):
                return self.send(json.dumps({**base, "object": "chat.completion", "usage": usage, "choices": [
                    {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}]}))
            chunks = [{**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "finish_reason": None, "delta": {"role": "assistant", "content": "OK"}}]},
                      {**base, "object": "chat.completion.chunk", "usage": usage, "choices": [{"index": 0, "finish_reason": "stop", "delta": {}}]}]
            self.send("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n", "text/event-stream")

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Router)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    real, url, key = agents.catalog, f"http://127.0.0.1:{srv.server_address[1]}/v1", "router-test-key"
    agents.catalog = lambda: {k: {**a, "router": url} if k == "opencode@9router" else a for k, a in real().items()}
    try:
        vault_set("NINEROUTER_API_KEY", key)
        a = agents.catalog()["opencode@9router"]
        assert agents.list_models(a, None) == ["kr/claude-sonnet-4.5", "glm/glm-4.6"]
        assert seen[-1][0] == "/v1/models" and seen[-1][1]["authorization"] == f"Bearer {key}", seen
        cfg = json.loads(agents.router_config(a, "kr/claude-sonnet-4.5"))["provider"]["router"]
        assert cfg["options"]["baseURL"] == url and cfg["options"]["headers"] == {"X-9Router-Token-Saver": "off"}
        assert key not in json.dumps(cfg) and list(cfg["models"]) == ["kr/claude-sonnet-4.5"]
        if agents.resolve_bin("opencode"):
            d = Path(tempfile.mkdtemp(prefix="orch-router-"))
            r = agents.run_agent("opencode@9router", "kr/claude-sonnet-4.5", "Reply with exactly the word OK and nothing else.",
                                 d, d / "out", readonly=True, timeout=180)
            shutil.rmtree(d, ignore_errors=True)
            assert r["ok"] and "OK" in r["text"], r
            posts = [h for p, h in seen if p.endswith("/chat/completions")]
            assert posts and posts[0]["authorization"] == f"Bearer {key}" and posts[0]["x-9router-token-saver"] == "off", seen
    finally:
        agents.catalog = real
        srv.shutdown()


def test_router_accounts_per_provider_and_shared():
    """~/.orchestra/agents.json changes a profile on this machine only. A router is one account per provider prefix, and a
    prefix that is a CLI's subscription too (9router cx/ = codex) runs out with that CLI: when w1's account (mock@b) runs out,
    the backup on the router's b/ provider is skipped; when the x/ provider runs out, y/ on the same router takes over."""
    agents.OVERRIDES.write_text(json.dumps({"opencode@9router": {"router": "http://127.0.0.1:20127/v1"}}), encoding="utf-8")
    try:
        a = agents.catalog()["opencode@9router"]
        assert a["router"] == "http://127.0.0.1:20127/v1" and a["bin"] == "opencode" and a["models_from"] == "router"
        assert [agents.account("opencode@9router", m) for m in ("cx/gpt-5.5", "if/kimi-k2", "my-combo")] == [
            "codex", "opencode@9router/if", "opencode@9router"]
        assert agents.account("opencode@free", "opencode/big-pickle") == "opencode@free"
    finally:
        agents.OVERRIDES.unlink()
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK)], "steps": {"worker:T1": [QUOTA, QUOTA, {"write": {"a.txt": "a\n"}}]}}
    r = Repo(sc, workers={"w1": {"agent": "mock@b", "model": "mock-fast"},
                          **{f"r{p}": {"agent": "mock@r", "model": f"{p}/mock-fast", "backup": True} for p in "bxy"}})
    (r.tmp / "home").mkdir()
    (r.tmp / "home" / "agents.json").write_text(json.dumps(
        {"mock@r": {"base": "mock", "router": "http://127.0.0.1:9/v1", "shares": {"b": "mock@b"}}}), encoding="utf-8")
    assert r.run() == 0, r.out
    assert r.q("SELECT agent, model, outcome FROM attempts WHERE task='T1' ORDER BY id") == [
        ("mock@b", "mock-fast", "quota"), ("mock@r", "x/mock-fast", "quota"), ("mock@r", "y/mock-fast", "integrated")], r.out
    assert {k for (k,) in r.q("SELECT k FROM meta WHERE k LIKE 'cool:%'")} == {"cool:mock@b", "cool:mock@r/x"}
    assert r.orch("pool") == 0 and any(ln.startswith("| mock@b |") and ln.endswith("| w1, rb |") for ln in r.out.splitlines()), r.out


def test_account_limits_parallelism_and_risk_lowers_rank():
    """account_max: two workers on one subscription take turns. pool.rank: an account at risk of running out before its reset
    ranks below an equal candidate on a safe account."""
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK), task("T2", "w2", ["b.txt"], OK)],
          "steps": {"worker:T1": [{"write": {"a.txt": "a\n"}, "sleep": 2}], "worker:T2": [{"write": {"b.txt": "b\n"}, "sleep": 2}]}}
    r = Repo(sc, account_max={"mock": 1})  # w1 and w2 both run mock: one account
    assert r.run() == 0, r.out
    (_, end1), (start2, _) = r.q("SELECT started, ended FROM attempts WHERE kind='work' ORDER BY started")
    assert end1 <= start2, "the second task must wait for the account"
    real, ws = pool.outlook, type("WS", (), {"meta": lambda self, k: None})()
    pool.outlook = lambda ac, cool=0.0: {"text": "", "used": 50.0, "out_until": None, "risk": ac == "mock@b"}
    try:
        rows = pool.rank({"workers": {"w1": {"agent": "mock", "model": "m0"}}}, [("mock@b", "m1"), ("mock@c", "m1")], {"s": 1}, ws,
                         {"models": {}})["w1"]
    finally:
        pool.outlook = real
    assert [(x["pair"][0], x["risk"]) for x in rows] == [("mock@c", False), ("mock@b", True)] and rows[1]["score"] < rows[0]["score"], rows


def test_suggest_shrinks_benchmarks_toward_history():
    """suggest: the benchmark prior is worth k=5 calls of the pair's own record. A router pair on a provider that shares a
    worker's subscription is no second worker; a strong model whose "done" keeps failing verification loses the lead to a
    weaker one that keeps delivering; quota errors say nothing about the model."""
    from orch import models
    from orch.core import record
    db = {"models": {"mock-strong": {"eci": 150, "org": "A"}, "mock-mid": {"eci": 140, "org": "B"}, "mock-fast": {"eci": 120, "org": "C"}}}
    cands = [("mock", "mock-strong"), ("mock@b", "mock-mid"), ("mock@c", "mock-fast"), ("mock@r", "c/mock-fast")]
    agents.OVERRIDES.write_text(json.dumps({"mock@r": {"base": "mock", "router": "http://127.0.0.1:9/v1", "shares": {"c": "mock@c"}}}),
                                encoding="utf-8")
    try:
        s = models.suggest(cands, db)
        assert (s["lead"], s["reviewer"], s["workers"]) == (cands[0], cands[1], [cands[2]]), s
        for pair, outcome, n in ((cands[0], "verify", 5), (cands[2], "integrated", 10), (cands[1], "quota", 5)):
            for _ in range(n):
                record("t", "T1", *pair, "work", outcome, 1)
        s = models.suggest(cands, db)  # strong (5*1 + 0) / 10 = 0.5; fast (5/3 + 10) / 15 = 0.78; mid keeps 2/3
        assert (s["lead"], s["reviewer"]) == (cands[2], cands[1]), s
    finally:
        agents.OVERRIDES.unlink()


ROMAN = ("V = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), "
         "(9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]\n"
         "def to_roman(n):\n    out = ''\n    for v, s in V:\n        out, n = out + s * (n // v), n % v\n    return out\n"
         "def from_roman(s):\n    n, i = 0, 0\n    for v, sym in V:\n        while s.startswith(sym, i):\n            n, i = n + v, i + len(sym)\n"
         "    if not s or i < len(s) or not 0 < n < 4000 or to_roman(n) != s:\n        raise ValueError(s)\n    return n\n")


def test_pool_plan_ranks_pretests_and_backs_up():
    """pool plan: candidates from discovery minus each primary's own account; one pre-test each (the hard one for a ranking
    led by honesty), where a model that claims done with wrong code ranks lower (honest); the best saved as each primary's
    designated backup. When w2's account runs out, w2's own backup takes over, not w1's backup that lives on the same
    exhausted account. `pool test` uses the easy task by default."""
    sc = {"plan": [task("T1", "w2", ["a.txt"], OK)],
          "steps": {"worker:POOL-HARD@mock-strong": [{"write": {"roman.py": ROMAN}}],
                    "worker:POOL-HARD@mock-fast": [{"write": {"roman.py": ROMAN.replace(" or to_roman(n) != s", "")}}],  # takes IIII
                    "worker:POOL@mock-fast": [{"write": {"fizz.py": "def fizz(n):\n    return str(n)\n"}}],
                    "worker:T1": [QUOTA, {"write": {"a.txt": "a\n"}}]}}
    r = Repo(sc, workers={"w1": {"agent": "mock", "model": "mock-strong"}, "w2": {"agent": "mock@b", "model": "mock-fast"}})
    home, found = r.tmp / "home", {"installed": True, "auth": "ok?", "models": ["mock-fast", "mock-strong"]}
    home.mkdir()
    (home / "resources.json").write_text(json.dumps({"mock@b": found, "mock@c": found}), encoding="utf-8")
    # precise without the t filter: a benchmark DB from `models refresh` would filter out the mock models
    assert r.orch("pool", "plan", "--preset", "precise", "--criteria", "t", "--yes") == 0, r.out
    db = sqlite3.connect(home / "history.db")
    tests = db.execute("SELECT agent, model, task, outcome FROM runs WHERE role='pool' ORDER BY agent, model").fetchall()
    db.close()
    assert tests == [("mock@b", "mock-strong", "POOL-HARD", "ok"), ("mock@c", "mock-fast", "POOL-HARD", "verify"),
                     ("mock@c", "mock-strong", "POOL-HARD", "ok")], r.out
    team = json.loads((r.repo / ".orch" / "team.json").read_text(encoding="utf-8"))
    backups = {n: (w["agent"], w["model"], w["for"]) for n, w in team["workers"].items() if w.get("backup")}
    assert backups == {"mock-b-b1": ("mock@b", "mock-strong", ["w1"]), "mock-c-b1": ("mock@c", "mock-strong", ["w2"])}, r.out
    assert team["pool"]["preset"] == "custom" and team["pool"]["criteria"] == {"h": 3, "r": 3, "s": 1, "c": 1}
    assert r.orch("pool") == 0 and "- w2 (mock@b/mock-fast) backups: mock-c-b1 (mock@c/mock-strong)" in r.out, r.out
    assert r.orch("pool", "test", "mock@c/mock-fast") == 0 and "mock@c/mock-fast: verify" in r.out, r.out
    assert r.run() == 0, r.out
    assert r.q("SELECT agent, model, outcome FROM attempts WHERE task='T1' AND kind='work' ORDER BY id") == [
        ("mock@b", "mock-fast", "quota"), ("mock@c", "mock-strong", "integrated")], r.out


def test_merge_conflict_is_resolved_by_the_worker():
    sc = {"plan": [task("T1", "w1", ["shared.txt"], OK), task("T2", "w2", ["shared.txt"], OK)],
          "steps": {"worker:T1": [{"write": {"shared.txt": "T1\n"}}],
                    "worker:T2": [{"write": {"shared.txt": "T2\n"}, "sleep": 5}, {"write": {"shared.txt": "T1\nT2\n"}}]}}
    r = Repo(sc, files={"shared.txt": "base\n"})
    assert r.run() == 0, r.out
    assert r.outcomes("T2") == ["conflict", "integrated"], r.outcomes("T2")
    assert r.show("shared.txt").splitlines() == ["T1", "T2"]


def test_plan_review_user_approval_and_amendment():
    """Reviewer blocks plan v1 -> lead revises; user approves; final review blocks -> recorded amendment -> REVIEW2."""
    blocker = lambda msg, tid=None: {"reply": {"verdict": "revise", "issues": [{"task_id": tid, "severity": "blocker", "message": msg}]}}
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK)], "amend": [task("T3", "w2", ["README.md"], OK, ["T1"])],
          "steps": {"reviewer:PLAN": [blocker("T1 lacks a test", "T1"), {}], "reviewer:REVIEW": [blocker("README not updated")],
                    "worker:T1": [{"write": {"a.txt": "a\n"}}], "worker:T3": [{"write": {"README.md": "demo\nusage\n"}}]}}
    r = Repo(sc)
    assert r.orch("run", "demo goal", "--exit-on-wait") == 3, r.out
    assert r.status() == {"PLAN": "pending_user"} and r.calls("lead", "PLAN") == 2 and r.calls("reviewer", "PLAN") == 2
    assert "revision=1" in (Path(f"{r.scenario}.state") / "calls.log").read_text(encoding="utf-8")
    assert r.orch("answer", "PLAN", "yes") == 0 and r.orch("resume", "--exit-on-wait") == 0, r.out
    assert r.status() == {"PLAN": "done", "T1": "done", "REVIEW": "done", "T3": "done", "REVIEW2": "done"}, r.status()
    assert r.show("README.md") == "demo\nusage"


def test_budget_gate_then_stop():
    r = Repo(two_tasks(), budget_tokens=1000)
    assert r.run() == 3, r.out
    gate = [t for t in r.status() if t.startswith("BUDGET")]
    assert gate and r.status()[gate[0]] == "pending_user", r.status()
    assert r.orch("answer", gate[0], "stop") == 0 and r.orch("resume", "--exit-on-wait") == 1, r.out
    assert "cancelled" in r.out and r.calls("worker", "T2") == 0


def test_skill_architect_installs_and_places():
    sc = two_tasks()
    sc["steps"]["skill_architect:SKILLS"] = [{"reply": {"skills": [{"id": "local/demo", "tasks": ["T1"], "reason": "T1 needs it"},
                                                                    {"id": "https://github.com/acme/tools", "tasks": [], "reason": "maybe"}]}}]
    r = Repo(sc, skills=True)
    skill, home = r.tmp / "demo", r.tmp / "home" / "skills"
    skill.mkdir()
    home.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill.\n---\nUse it.\n", encoding="utf-8")
    (skill / "fetch.sh").write_text("curl https://example.com\n", encoding="utf-8")
    (home / "index.json").write_text(json.dumps([{"id": "local/demo", "description": "Demo skill.", "local": str(skill)}]), encoding="utf-8")
    assert r.run() == 0, r.out
    rows = {x[0]: x[1:] for x in r.q("SELECT id, status, scan FROM skills")}
    assert rows["local/demo"][0] == "installed" and "fetch.sh" in rows["local/demo"][1], rows
    assert rows["https://github.com/acme/tools"][0] == "proposed", rows
    prompt = lambda tid: (Path(r.q("SELECT dir FROM attempts WHERE task=? AND kind='work'", tid)[0][0]) / "prompt.md").read_text(encoding="utf-8")
    assert ".agents/skills/orch-demo/SKILL.md" in prompt("T1") and "orch-demo" not in prompt("T2")
    assert ".agents" not in r.git("ls-tree", "-r", "--name-only", r.main), "placed skills must never be committed"
    assert r.orch("skills", "approve", "https://github.com/acme/tools") == 0, r.out
    assert "acme/tools" in (home / "sources.json").read_text(encoding="utf-8")


def test_opt_in_gates_verify_allowlist_and_skill_proposals():
    """PLAN §13 opt-ins, both off by default. skills=propose: the curated pick waits for the user and work waits for it.
    verify_allow: a command outside the list stops its task before any worker call, even in an auto-approved run; one 'yes'
    allows that command for the run and releases every task it held."""
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK), task("T2", "w2", ["b.txt"], OK)],
          "steps": {"skill_architect:SKILLS": [{"reply": {"skills": [{"id": "local/demo", "tasks": [], "reason": "useful"}]}}],
                    "worker:T1": [{"write": {"a.txt": "a\n"}}], "worker:T2": [{"write": {"b.txt": "b\n"}}]}}
    r = Repo(sc, skills="propose", verify_allow=[["git"]])
    skill, home = r.tmp / "demo", r.tmp / "home" / "skills"
    skill.mkdir()
    home.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill.\n---\nUse it.\n", encoding="utf-8")
    (home / "index.json").write_text(json.dumps([{"id": "local/demo", "description": "Demo skill.", "local": str(skill)}]), encoding="utf-8")
    assert r.run() == 3, r.out
    assert r.status()["SKILLS"] == "pending_user" and r.q("SELECT status FROM skills") == [("proposed",)], r.out
    assert r.orch("answer", "SKILLS", "yes") == 0 and r.orch("resume", "--exit-on-wait") == 3, r.out
    assert r.q("SELECT status FROM skills") == [("installed",)] and r.calls("worker", "T1") + r.calls("worker", "T2") == 0
    held = dict(r.q("SELECT id, question FROM tasks WHERE status='pending_user'"))
    assert set(held) == {"T1", "T2"} and "python -c" in held["T1"], held
    assert r.orch("answer", "T1", "yes") == 0 and r.orch("resume", "--exit-on-wait") == 0, r.out
    assert r.status() == {"PLAN": "done", "T1": "done", "T2": "done", "SKILLS": "done", "REVIEW": "done"}, r.status()


def test_skills_index_offline():
    from orch import skills
    tmp, sha = Path(tempfile.mkdtemp(prefix="orch-skills-")), "a" * 40
    files = {"skills/pdf/SKILL.md": "---\nname: pdf\ndescription: >\n  Read and\n  merge PDFs.\n---\n", "skills/pdf/x.py": "import subprocess\n",
             "template/SKILL.md": "---\nname: template\n---\n"}
    tree = [{"path": p, "type": "blob", "size": len(t)} for p, t in files.items()]
    fake = lambda url: json.dumps({"tree": tree}).encode() if "/git/trees/" in url else files[url.split(f"/{sha}/", 1)[1]].encode()
    saved = skills._get, skills.sources, skills.CACHE, skills.INDEX, skills.LOCAL_DIRS
    try:
        skills._get, skills.sources = fake, lambda: [{"id": "acme", "repo": "acme/skills", "ref": sha, "prefix": "skills/"}]
        skills.CACHE, skills.INDEX, skills.LOCAL_DIRS = tmp, tmp / "index.json", []
        idx = skills.refresh()
        assert [(s["id"], s["description"]) for s in idx] == [("acme/pdf", "Read and merge PDFs.")], idx
        path, digest, scan = skills.install(idx[0])
        assert (path / "x.py").read_text() == "import subprocess\n" and len(digest) == 64 and "x.py" in scan.split("patterns in:")[1], scan
        assert skills.install(idx[0])[1] == digest, "second install must reuse the cached copy"
    finally:
        skills._get, skills.sources, skills.CACHE, skills.INDEX, skills.LOCAL_DIRS = saved
        shutil.rmtree(tmp, ignore_errors=True)


def test_ui_server_security():
    import threading, urllib.error, urllib.request
    from orch import core, server
    r, saved = Repo(two_tasks()), core.VAULT
    core.VAULT = r.tmp / "vault.test"  # never the user's real vault
    srv = server.make_server(core.Workspace(r.repo), 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = srv.url.split("#")[0].rstrip("/")

    def call(path, body=None, token=srv.token, **hdr):
        req = urllib.request.Request(base + path, data=body and json.dumps(body).encode(),
                                     headers={"X-Orch-Token": token, "Content-Type": "application/json", **hdr})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
    try:
        code, page = call("/", token="")
        assert code == 200 and '<script nonce="' in page and "innerHTML" not in page
        assert call("/api/state", token="wrong")[0] == 403
        assert call("/api/state", Host="evil.example")[0] == 403, "DNS rebinding: foreign Host must be refused"
        secret = "sk-test-1234567890abcdef"
        assert call("/api/vault", {"name": "DEMO_KEY", "value": secret}, Origin="http://evil.example")[0] == 403
        code, body = call("/api/vault", {"name": "DEMO_KEY", "value": secret})
        assert code == 200 and "DEMO_KEY" in body and secret not in body, body
        assert core.vault()["DEMO_KEY"] == secret
        if os.name == "nt":  # DPAPI: never plaintext at rest
            assert secret.encode() not in core.VAULT.read_bytes()
        else:  # a chmod-600 JSON
            assert core.VAULT.stat().st_mode & 0o777 == 0o600
        assert call("/api/vault", {"name": "bad name", "value": "x"})[0] == 400
        team = json.loads((r.repo / ".orch" / "team.json").read_text(encoding="utf-8"))
        assert call("/api/team", {"team": {**team, "workers": {"../evil": {"agent": "mock", "model": "m"}}}})[0] == 400
        code, body = call("/api/state")
        assert code == 200 and json.loads(body)["has_team"] and json.loads(body)["run"] is None, body
    finally:
        srv.shutdown()
        srv.server_close()
        srv.ws.db.close()  # an open handle would keep orch.db (and the temp dir) undeletable on Windows
        core.VAULT = saved


def test_scope_and_plan_checks():
    assert in_scope("src/a.py", ["src/"]) and in_scope("src/a.py", ["src"]) and not in_scope("srcx/a.py", ["src"])
    assert in_scope("a/b/c.py", ["**/*.py"]) and in_scope("src/a.py", ["src/**/*.py"]) and in_scope("any/x", ["."])
    assert not in_scope("docs/a.md", ["src/**"]) and not in_scope("app.py", ["test_app.py"])
    good = {"tasks": [task("T1", "w1", ["./src\\a.py"], [["python", "-V"]]), task("T2", "w1", ["b"], [["x"]], ["T1"])]}
    assert check_plan(good, {"w1": {}}) == [] and good["tasks"][0]["scope_paths"] == ["src/a.py"]
    bad = {"tasks": [task("PLAN", "w9", ["../x", ".git/config"], [[]], ["T9"]), task("T1", "w1", ["a"], [["x"]], ["T1"])]}
    errs = " | ".join(check_plan(bad, {"w1": {}}))
    for frag in ("reserved", "unknown assignee", "..", "engine territory", "verify", "unknown dependency", "cycle"):
        assert frag in errs, (frag, errs)
    assert check_plan({"tasks": [task("T2", "w1", ["a"], [["x"]], ["T1"])]}, {"w1": {}}, {"T1": "done"}) == []
    assert check_plan({"tasks": [task("T1", "w1", ["a"], [["x"]])]}, {"w1": {}}, {"T1": "done"}), "ids are never reused"
    assert allowed(["python", "-m", "unittest", "x"], [["python", "-m", "unittest"]]) and allowed(["x"], None)
    assert not allowed(["python", "x.py"], [["python", "-m"]]) and not allowed(["python"], [["python", "-m"]])
    big = ["README.md", "src/main.py"] + [f"src/m{i}/f{j}.py" for i in range(5) for j in range(100)]
    assert file_map(big[:3]).splitlines() == ["README.md", "src/m0/f0.py", "src/main.py"], "a small repo lists every file"
    assert file_map(big, 10).splitlines() == ["README.md", *[f"src/m{i}/ (100 files)" for i in range(5)], "src/main.py"]


if __name__ == "__main__":
    failed = 0
    for name, fn in [(n, f) for n, f in list(globals().items()) if n.startswith("test_")]:
        if sys.argv[1:] and not any(a in name for a in sys.argv[1:]):
            continue
        t0, REPOS[:] = time.time(), []
        try:
            fn()
            print(f"PASS {name} ({time.time() - t0:.1f}s)", flush=True)
            for r in REPOS:  # git object files are read-only: Windows refuses to delete them until the bit is cleared
                shutil.rmtree(r.tmp, **{"onexc" if sys.version_info >= (3, 12) else "onerror":
                                        lambda fn, p, _: (os.chmod(p, stat.S_IWRITE), fn(p))})
        except Exception:
            failed += 1
            print(f"FAIL {name} ({time.time() - t0:.1f}s), kept: {[str(r.tmp) for r in REPOS]}", flush=True)
            traceback.print_exc()
    shutil.rmtree(os.environ["ORCH_HOME"], ignore_errors=True)
    sys.exit(1 if failed else 0)
