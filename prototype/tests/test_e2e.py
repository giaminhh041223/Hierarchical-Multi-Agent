"""End-to-end tests driving the real engine with the scripted mock agent (zero cost).
Run: python tests/test_e2e.py [name-filter ...]   (pytest -q tests also works)"""
import contextlib, datetime, http.server, json, os, re, shutil, sqlite3, stat, subprocess, sys, tempfile, threading, time, traceback
import unittest.mock, urllib.error, urllib.request
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

    def show_file(self, pattern):  # a file under the project, by glob
        return next(self.repo.glob(pattern)).read_text(encoding="utf-8")

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
    sc = two_tasks()
    sc["steps"]["worker:T1"][0]["write"]["build/gen.txt"] = "generated\n"  # git-ignored: verify sees it, the commit does not
    r = Repo(sc, files={".gitignore": "build/\n"})
    assert r.run() == 0, r.out
    assert [b for _, b in r.events("warn", "T1")] == ["verify ran with 1 git-ignored path(s) that are not committed: build/"]
    assert not r.events("warn", "T2") and "build/" not in r.git("ls-tree", "-r", "--name-only", r.main)
    assert r.status() == {"PLAN": "done", "T1": "done", "T2": "done", "REVIEW": "done"}, r.status()
    assert "return a + b" in r.show("app.py") and "assert" in r.show("test_app.py")
    assert r.git("rev-parse", "HEAD") == r.base, "the user's branch must stay untouched"
    assert r.q("SELECT entity, fact FROM facts") == [("app", "app: add(a, b) returns a + b")]
    assert r.orch("kg", "search", "add") == 0 and "returns a + b" in r.out, "a query of only common words must still search"
    assert '-c "import app; assert' in r.events("verify", "T1")[0][1], "commands are shown quoted"
    t2_prompt = Path(r.q("SELECT dir FROM attempts WHERE task='T2' AND kind='work'")[0][0]) / "prompt.md"
    assert "app: add(a, b) returns a + b" in t2_prompt.read_text(encoding="utf-8"), "dependency handoff must reach T2"
    report = (r.repo / ".orch" / "runs" / r.main.split("/")[1] / "report.md").read_text(encoding="utf-8")
    calls = [l for l in report.split("## Calls")[1].splitlines() if l.startswith("| ") and l[2].isdigit()]
    assert len(calls) == 5 and all("mock / mock-" in l and "1,000 | 100 |" in l for l in calls), report  # plan, review, T1, T2, final review
    assert all(float(l.rstrip(" |").rsplit("|", 1)[1]) > 0.5 for l in calls), "prompt sizes show where the tokens go"


def test_report_estimates_cost_at_list_price():
    """No CLI-reported cost: the report estimates it from the model DB's list price (models refresh), marked ~."""
    from orch import models
    r = Repo(two_tasks())
    (r.tmp / "home").mkdir(exist_ok=True)
    db = {"as_of": "2026-10-05", "models": {models.norm(m): {"price_in": 2.0, "price_out": 10.0} for m in ("mock-fast", "mock-strong")}}
    (r.tmp / "home" / "models.json").write_text(json.dumps(db), encoding="utf-8")
    assert r.run() == 0, r.out
    report = r.show_file(".orch/runs/*/report.md")
    usage = report.split("## Usage")[1].split("## Calls")[0]
    # mock-fast ran T1 and T2: 2 x (1,000 in x $2 + 100 out x $10) per Mtok = $0.006
    assert "| mock | mock-fast | 2 | 2,000 | 200 | ~0.0060 |" in usage and "~" in usage, usage


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
          "steps": {"worker:T1": [{"write": {"a.txt": "draft\n"}, "sleep": 60}, {"write": {"a.txt": "a\n"}}],
                    "lead:T1": [{"reply": {"action": "reassign", "assignee": "w2", "note": "w1 timed out; w2 takes over"}}]}}
    r = Repo(sc, timeout=3)
    t0 = time.time()
    assert r.run() == 0, r.out
    assert time.time() - t0 < 45, "the stuck agent must be killed at the timeout"
    assert r.outcomes("T1") == ["timeout", "integrated"], r.outcomes("T1")
    assert r.q("SELECT assignee FROM tasks WHERE id='T1'")[0][0] == "w2"
    patch = next((r.repo / ".orch" / "runs").glob("*/attempts/T1-abandoned-*.patch"))  # evidence of the reset, as git wrote it
    assert subprocess.run(GIT + ["apply", "--check", str(patch)], cwd=r.repo, capture_output=True).returncode == 0
    assert b"+draft" in patch.read_bytes() and b"\r\n" not in patch.read_bytes()


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
        cfg = agents.router_config(a, "kr/claude-sonnet-4.5")["provider"]["router"]
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
    blocker = lambda msg, tid=None: {"reply": {"verdict": "revise", "issues": [{"task_id": tid, "severity": "blocker", "message": msg,
                                                                               "evidence": f"acceptance not met: {msg}"}]}}
    readme = [["python", "-c", "assert 'usage' in open('README.md').read()"]]
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK)], "amend": [task("T3", "w2", ["README.md"], OK + readme, ["T1"])],
          "steps": {"reviewer:PLAN": [blocker("T1 lacks a test", "T1"), {}], "reviewer:REVIEW": [blocker("README not updated")],
                    "worker:T1": [{"write": {"a.txt": "a\n"}}], "worker:T3": [{"write": {"README.md": "demo\nusage\n"}}]}}
    r = Repo(sc)
    assert r.orch("run", "demo goal", "--exit-on-wait") == 3, r.out
    assert r.status() == {"PLAN": "pending_user"} and r.calls("lead", "PLAN") == 2 and r.calls("reviewer", "PLAN") == 2
    assert "revision=1" in (Path(f"{r.scenario}.state") / "calls.log").read_text(encoding="utf-8")
    assert "commands added later by an amendment are asked" in r.show_file(".orch/runs/*/plan.md")
    assert r.orch("answer", "PLAN", "yes") == 0 and r.orch("resume", "--exit-on-wait") == 3, r.out
    # the approval covered the plan's commands only: the amendment's new one waits, before any worker call
    assert r.status()["T3"] == "pending_user" and r.calls("worker", "T3") == 0, r.status()
    q = r.q("SELECT question FROM tasks WHERE id='T3'")[0][0]
    assert "amendment" in q and "README.md" in q and "print('ok')" not in q, q
    assert r.orch("answer", "T3", "yes") == 0 and r.orch("resume", "--exit-on-wait") == 0, r.out
    assert r.status() == {"PLAN": "done", "T1": "done", "REVIEW": "done", "T3": "done", "REVIEW2": "done"}, r.status()
    assert r.show("README.md") == "demo\nusage"


def test_modes_solo_auto_and_evidence_for_blockers():
    """mode solo: no planner, one task with the user's own checks, no approval, no reviewer call. mode auto: the lead returns
    one task, so the plan review and the final reviewer call are skipped. A reviewer blocker without evidence is advisory."""
    check = [["python", "-c", "import app; assert app.add(2, 3) == 5"]]
    sc = {"plan": [], "steps": {"worker:T1": [{"write": {"app.py": ADD}}]}}
    r = Repo(sc, mode="solo", solo="w2", verify=check)
    assert r.orch("run", "make add() work", "--exit-on-wait") == 0, r.out  # no --yes: solo has nothing to approve
    assert r.status() == {"PLAN": "done", "T1": "done", "REVIEW": "done"}, r.status()
    assert r.q("SELECT assignee FROM tasks WHERE id='T1'")[0][0] == "w2" and "return a + b" in r.show("app.py")
    assert r.calls("lead", "PLAN") == 0 and r.calls("reviewer", "PLAN") == 0 and r.calls("reviewer", "REVIEW") == 0, "only the worker is called"
    assert json.loads(r.q("SELECT spec FROM tasks WHERE id='T1'")[0][0]) == {"acceptance": ["make add() work"], "scope_paths": ["."], "verify": check}
    r2 = Repo({"plan": []}, mode="solo")
    assert r2.orch("run", "x", "--exit-on-wait") == 3 and 'team.json "verify"' in r2.q("SELECT question FROM tasks WHERE id='PLAN'")[0][0]

    sc = {"plan": [task("T1", "w1", ["app.py"], check[:1])], "steps": {"worker:T1": [{"write": {"app.py": ADD}}]}}
    r3 = Repo(sc, mode="auto", verify=check, skills=True)
    assert r3.run() == 0, r3.out
    assert r3.calls("lead", "PLAN") == 1 and r3.calls("reviewer", "PLAN") == 0 and r3.calls("reviewer", "REVIEW") == 0, r3.out
    assert "SKILLS" not in r3.status() and r3.calls("skill_architect", "SKILLS") == 0, "a one-task light run skips the skill architect"
    prompt = Path(r3.q("SELECT dir FROM attempts WHERE task='PLAN' AND kind='plan'")[0][0]) / "prompt.md"
    text = prompt.read_text(encoding="utf-8")
    assert "Size the plan to the goal" in text and "Project checks (from the user" in text, text[-800:]

    hunch = {"reply": {"verdict": "revise", "issues": [{"task_id": "T1", "severity": "blocker", "message": "feels incomplete", "evidence": None}]}}
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK)], "steps": {"reviewer:PLAN": [hunch], "reviewer:REVIEW": [hunch], "worker:T1": [{"write": {"a.txt": "a\n"}}]}}
    r4 = Repo(sc)  # team mode: both reviews run, but a blocker without evidence stops nothing and asks nobody
    assert r4.run() == 0 and set(r4.status().values()) == {"done"} and r4.calls("lead", "PLAN") == 1, r4.out
    assert "blocker without evidence: counted as advisory" in r4.show_file(".orch/runs/*/plan.md")
    assert not r4.q("SELECT 1 FROM tasks WHERE id LIKE 'REVIEW2'")


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


@contextlib.contextmanager
def ui_server(project):
    """The web UI in process on a free port; yields call(path, body=None, token=<its token>, **headers) -> (status, text)."""
    from orch import core, server
    srv = server.make_server(core.Workspace(project), 0)
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
    call.base = base
    try:
        yield call
    finally:
        srv.shutdown()
        srv.server_close()
        srv.ws.db.close()  # an open handle would keep orch.db (and the temp dir) undeletable on Windows


def contrast(a, b):
    """WCAG 2.x contrast ratio of two #RRGGBB colors."""
    def lum(c):
        r, g, b = (x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_ui_server_security():
    from orch import core
    r = Repo(two_tasks())
    with ui_server(r.repo) as call, unittest.mock.patch.object(core, "VAULT", r.tmp / "vault.test"):  # never the user's real vault
        code, page = call("/", token="")
        assert code == 200 and '<script nonce="' in page and "innerHTML" not in page
        assert not re.search(r"https?://(?!www\.w3\.org/2000/svg\b)", page), "nothing may load from outside (CSP, docs/UIUX.md §3)"
        light = page.split(":root", 1)[1].split("}", 1)[0]  # the color tokens (docs/UIUX.md §5), then their dark values
        dark = page.split("prefers-color-scheme: dark", 1)[1].split("}", 1)[0]
        for theme in (dict(re.findall(r"--(\w+):\s*(#[0-9A-Fa-f]{6})", t)) for t in (light, dark)):
            for bg in ("paper", "surface"):  # text 4.5:1, control borders 3:1 (WCAG 2.2 AA)
                assert all(contrast(theme[fg], theme[bg]) >= 4.5 for fg in ("ink", "muted", "running", "done", "waiting", "failed")), theme
                assert contrast(theme["control"], theme[bg]) >= 3, theme
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
        code, body = call("/api/answer", {"task": "PLAN", "text": "  "})
        assert code == 400 and "empty" in body, "an empty answer must never count as 'yes'"
        code, body = call("/api/state")
        assert code == 200 and json.loads(body)["has_team"] and json.loads(body)["run"] is None, body


def test_plan_edit_from_the_ui():
    """The plan editor (web UI): deps and workers of the plan waiting for approval, saved as its next version. Cycles, unknown
    workers, partial edits, stale versions and a plan with an answer on its way are refused; the run then follows the edit."""
    from orch import core, engine
    exists_a = [["python", "-c", "import os; assert os.path.exists('a.txt')"]]  # passes only once T1 is integrated
    sc = {"plan": [task("T1", "w1", ["a.txt"], OK), task("T2", "w2", ["b.txt"], exists_a)],
          "steps": {"worker:T1": [{"write": {"a.txt": "a\n"}}], "worker:T2": [{"write": {"b.txt": "b\n"}}]}}
    r = Repo(sc)
    assert r.orch("run", "demo goal", "--exit-on-wait") == 3 and r.status() == {"PLAN": "pending_user"}, r.out
    edit = lambda v, **t: {"version": v, "tasks": [{"id": "T1", "deps": [], "assignee": "w1"}, {"id": "T2", "deps": [], "assignee": "w2", **t}]}
    with ui_server(r.repo) as call:
        state = lambda: json.loads(call("/api/state")[1])
        assert state()["edit"] == {"version": 1, "workers": ["w1", "w2"], "tasks": [
            {"id": "T1", "title": "task T1", "assignee": "w1", "deps": []}, {"id": "T2", "title": "task T2", "assignee": "w2", "deps": []}]}
        cycle = edit(1, deps=["T1"])
        cycle["tasks"][0]["deps"] = ["T2"]
        for bad, why in ((cycle, "dependency cycle"), (edit(1, assignee="w9"), "unknown assignee"),
                         ({"version": 1, "tasks": edit(1)["tasks"][:1]}, "every task"), ({"version": 1, "tasks": "T1"}, "expected")):
            code, body = call("/api/plan", bad)
            assert code == 400 and why in body, (code, body)
        code, body = call("/api/plan", edit(1, deps=["T1"], assignee="w1"))
        assert code == 200 and "plan v2" in body, body
        assert state()["edit"]["version"] == 2 and "your edit of v1" in r.q("SELECT question FROM tasks WHERE id='PLAN'")[0][0]
        assert "| T2 | w1 | T1 |" in state()["plan"], state()["plan"]
        assert call("/api/plan", edit(1))[0] == 400, "a stale version must be refused"
        ws = core.Workspace(r.repo)  # the engine approved v1 just before the edit landed: v1 must not become the run
        engine.Engine(ws).materialize(sc["plan"], "pending_user", 1)
        ws.db.close()
        assert r.status() == {"PLAN": "pending_user"}
        assert call("/api/answer", {"task": "PLAN", "text": "yes"})[0] == 200
        assert state()["edit"] is None and call("/api/plan", edit(2))[0] == 400, "an answer is already on its way"
    assert r.orch("resume", "--exit-on-wait") == 0, r.out
    assert r.status() == {"PLAN": "done", "T1": "done", "T2": "done", "REVIEW": "done"}, r.status()
    assert r.q("SELECT assignee, deps FROM tasks WHERE id='T2'") == [("w1", '["T1"]')] and r.outcomes("T2") == ["integrated"]
    with ui_server(r.repo) as call:  # the task panel and the score read the attempts: no session ids, no pids
        st = json.loads(call("/api/state")[1])
    att = st["attempts"]
    assert {"T1", "T2"} <= {a["task"] for a in att} and not {"session", "pid"} & set(att[0]), att
    assert {"w1", "w2"} <= set(st["workers"]) and st["budget"] == 0, st  # quick answers: reassign <worker>, budget gate


def test_mcp_server_read_only_tools():
    """`python -m orch mcp`: the board and the knowledge graph as read-only MCP tools. With "mcp": true each agent call gets the
    server through its CLI's per-call config; here T2's agent starts it from that config and finds the fact T1 published."""
    import io, tomllib
    from orch import mcp
    sc = two_tasks()
    sc["steps"]["worker:T2"][0]["mcp"] = ["kg_search", {"query": "add"}]
    r = Repo(sc, mcp=True)
    assert r.run() == 0, r.out
    summary = json.loads(r.q("SELECT handoff FROM tasks WHERE id='T2'")[0][0])["summary"]
    assert "returns a + b  [T1]" in summary, summary
    # protocol edges, in process: version echo, a notification gets no reply, read-only tools only, JSON-RPC errors
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "board", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "kg_links", "arguments": {"node": "T2"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "write_file", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 6, "method": "resources/list"}]
    out = io.BytesIO()
    mcp.serve(r.repo, io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in msgs) + b"{not json\n"), out)
    rep = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [x["id"] for x in rep] == [1, 2, 3, 4, 5, 6, None], rep
    tools = rep[1]["result"]["tools"]
    assert rep[0]["result"]["protocolVersion"] == "2024-11-05" and all(t["annotations"]["readOnlyHint"] for t in tools)
    assert sorted(t["name"] for t in tools) == ["board", "kg_links", "kg_search"], tools
    text = [x["result"]["content"][0]["text"] for x in rep[2:4]]
    assert "goal: demo goal" in text[0] and "T2" in text[0] and "T2 -after-> T1" in text[1] and "test_app.py" in text[1], text
    assert [x["error"]["code"] for x in rep[4:]] == [-32602, -32601, -32700], rep
    # per CLI: codex -c TOML, claude --mcp-config JSON plus its allow-list, opencode config env; without mcp nothing changes
    srv, seen, real = agents.mcp_server(r.repo), [], (agents.spawn, agents.resolve_bin)
    agents.spawn, agents.resolve_bin = lambda cmd, cwd, env, *a: seen.append((cmd, env)), lambda b: [b]
    try:
        for aid in ("codex", "claude", "opencode"):
            for on in (None, r.repo):
                agents.run_agent(aid, "m", "hi", r.tmp, r.tmp / "out", schema="handoff", mcp=on)
    finally:
        agents.spawn, agents.resolve_bin = real
    (codex, codex_on), (claude, claude_on), (oc, oc_on) = [(seen[i][0], seen[i + 1][0]) for i in (0, 2)] + [(seen[4][1], seen[5][1])]
    assert codex_on[:3] == ["codex", "-c", f"mcp_servers.orch={agents.toml(srv)}"] and codex_on[3:] == codex[1:], codex_on
    assert tomllib.loads("s = " + agents.toml(srv))["s"] == srv
    assert claude[claude.index("--allowedTools") + 1] == "Bash,Read,Edit,Write,Glob,Grep", claude
    assert claude_on[1] == "--mcp-config" and json.loads(claude_on[2]) == {"mcpServers": {"orch": srv}}
    assert claude_on[claude_on.index("--allowedTools") + 1] == "Bash,Read,Edit,Write,Glob,Grep,mcp__orch"
    assert "OPENCODE_CONFIG_CONTENT" not in oc
    assert json.loads(oc_on["OPENCODE_CONFIG_CONTENT"])["mcp"]["orch"]["command"] == [srv["command"], *srv["args"]]


def test_mcp_control_drives_a_run():
    """`mcp --control` for the user's own Claude Code / Codex session: start a run, follow it, relay the user's plan approval,
    read the final report. The server that agents in a run get stays read-only."""
    import io
    from orch import mcp
    r = Repo(two_tasks())

    def call(name, args=None, control=True):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}
        out = io.BytesIO()
        mcp.serve(r.repo, io.BytesIO(json.dumps(msg).encode() + b"\n"), out, control=control)
        rep = json.loads(out.getvalue())
        return (rep["result"]["content"][0]["text"], rep["result"]["isError"]) if "result" in rep else (rep["error"]["message"], True)

    def until(cond, seconds=90):
        end = time.time() + seconds
        while time.time() < end:
            text = call("status")[0]
            if cond(text):
                return text
            time.sleep(0.5)
        raise AssertionError(f"timed out; status:\n{text}\nengine.log:\n{(r.repo / '.orch' / 'engine.log').read_text(encoding='utf-8')[-2000:]}")
    with unittest.mock.patch.dict(os.environ, r.env):  # the engine processes it starts use the test's ORCH_HOME and mock agent
        assert "[ok  ] git" in call("doctor")[0]
        assert call("status")[0].startswith("no run yet")
        text, bad = call("run", {"goal": "demo goal"})
        assert not bad and "started" in text, text
        text = until(lambda t: "WAITING FOR THE USER: PLAN" in t and "engine: stopped" in t)
        assert "Only answer 'yes' to a plan when the user approved it" in text, text
        assert call("answer", {"task": "PLAN", "text": " "})[1], "an empty answer is refused"
        text, bad = call("run", {"goal": "another"})
        assert bad and "still open" in text, text
        text, bad = call("answer", {"task": "PLAN", "text": "yes"})
        assert not bad and "answer recorded" in text, text
        text = until(lambda t: ": done |" in t.splitlines()[0] and "engine: stopped" in t)  # "done" comes before its cleanup; Windows
        # cannot delete history.db while that engine process still has it open
        assert "# Orctram run" in text and "| T2 | done |" in text, text
    assert r.git("rev-parse", "HEAD") == r.base and "return a + b" in r.show("app.py")
    ro = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, r.repo)["result"]["tools"]
    full = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, r.repo, control=True)["result"]["tools"]
    assert sorted(t["name"] for t in ro) == ["board", "kg_links", "kg_search"]
    assert {"run", "status", "answer", "resume", "cancel", "doctor"} <= {t["name"] for t in full}
    assert [t["annotations"] for t in full if t["name"] == "cancel"] == [{"readOnlyHint": False, "destructiveHint": True}]
    assert call("run", {"goal": "x"}, control=False)[1], "without --control there is no run tool"
    assert "--control" not in agents.mcp_server(r.repo)["args"], "agents in a run never get the control tools"


def test_github_action_runs_and_opens_a_pull_request():
    """action/run.py as the composite action runs it: team from a file, an auto-approved run, outputs and the step summary,
    then the integration branch pushed as orctram/<run> and a pull request (a fake gh on POSIX; Windows stops before the PR)."""
    r = Repo(two_tasks())
    team = json.loads((r.repo / ".orch" / "team.json").read_text(encoding="utf-8"))
    shutil.rmtree(r.repo / ".orch")  # CI starts from a clean checkout: the team comes from a file in the repository
    (r.repo / "ci-team.json").write_text(json.dumps(team), encoding="utf-8")
    remote = r.tmp / "origin.git"
    subprocess.run(GIT + ["init", "-q", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(GIT + ["remote", "add", "origin", str(remote)], cwd=r.repo, check=True)
    bin_dir, out, summary = r.tmp / "bin", r.tmp / "gh_output", r.tmp / "gh_summary"
    bin_dir.mkdir()
    fake_gh = bin_dir / "gh"  # records its arguments, prints a PR URL like the real one
    fake_gh.write_text(f"#!{sys.executable}\nimport json, sys\nopen({str(r.tmp / 'gh_args')!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
                       "print('https://github.com/o/r/pull/7')\n", encoding="utf-8")
    fake_gh.chmod(0o755)
    posix = os.name != "nt"
    env = {**r.env, "PYTHONPATH": str(ROOT), "PATH": str(bin_dir) + os.pathsep + r.env["PATH"], "GITHUB_OUTPUT": str(out),
           "GITHUB_STEP_SUMMARY": str(summary), "ORCTRAM_GOAL": "demo goal\nsecond line", "ORCTRAM_TEAM": "ci-team.json",
           "ORCTRAM_OPEN_PR": "true" if posix else "false", "ORCTRAM_BASE": "main", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    p = subprocess.run([sys.executable, str(ROOT / "action" / "run.py")], cwd=r.repo, env=env, capture_output=True, encoding="utf-8",
                       errors="replace", timeout=300)
    assert p.returncode == 0, p.stdout + p.stderr
    outputs = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
    run = outputs["run"]
    assert outputs["status"] == "done" and f"# Orctram run {run}: done" in summary.read_text(encoding="utf-8"), outputs
    if posix:
        assert outputs["branch"] == f"orctram/{run}" and outputs["pr-url"] == "https://github.com/o/r/pull/7", outputs
        pushed = subprocess.run(GIT + ["show", f"orctram/{run}:app.py"], cwd=remote, capture_output=True, encoding="utf-8").stdout
        assert "return a + b" in pushed, pushed
        args = json.loads((r.tmp / "gh_args").read_text(encoding="utf-8"))
        assert args[:6] == ["pr", "create", "--base", "main", "--head", f"orctram/{run}"] and args[7] == "Orctram: demo goal", args
        assert args[9].endswith("report.md"), args
    action = (ROOT / "action" / "action.yml").read_text(encoding="utf-8")
    assert "${{ inputs.goal }}" not in action.split("run:")[-1], "inputs must reach the script as env, never inside the shell line"


def test_kg_search_vectors():
    """kg_search fuses FTS5 keywords with vectors. Local trigrams find near spellings and words typed without accents; with
    team.json "embeddings" an OpenAI-compatible endpoint ranks by meaning: vault key as Bearer, each fact sent once, read-only
    workspaces still search. A dead endpoint falls back to the local vectors."""
    import io, re
    from orch import core
    d = Path(tempfile.mkdtemp(prefix="orch-test-"))
    ws = core.Workspace(d)
    for e, f in [("parser", "Parser handles nested parentheses"), ("auth", "Đăng nhập dùng JWT trong cookie httpOnly"),
                 ("db", "migrations live in db/migrations, run with make migrate"), ("app", "add(a, b) returns a + b")]:
        ws.kg_add(e, f, "T1")
    top = lambda q, w=ws: [r["entity"] for r in w.kg_search(q)]
    assert not ws.q("SELECT 1 FROM facts WHERE facts MATCH ?", '"parsing" OR "brackets" OR "dang" OR "nhap"'), "FTS5 alone misses"
    assert top("parsing brackets")[0] == "parser" and top("dang nhap")[0] == "auth"
    concepts = [{"login", "sign", "jwt", "đăng", "nhập", "session"}, {"database", "migrations", "schema", "db"},
                {"parser", "parentheses", "brackets", "parsing"}, {"add", "sum", "plus"}]
    seen = []

    class Embeddings(http.server.BaseHTTPRequestHandler):  # one dimension per concept; replies out of order
        def log_message(self, *a):
            pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.path, self.headers.get("Authorization"), req["model"], len(req["input"])))
            vec = lambda t: [float(bool(c & set(re.findall(r"\w+", t.lower())))) for c in concepts]
            body = json.dumps({"data": [{"index": i, "embedding": vec(t)} for i, t in enumerate(req["input"])][::-1]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Embeddings)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert "auth" not in top("users sign in"), "no shared word or trigram: only a model links them"
        ws.write_json("team.json", {"embeddings": {"url": f"http://127.0.0.1:{srv.server_address[1]}/v1", "model": "m", "key": "EMBED_KEY"}})
        vault_set("EMBED_KEY", "embed-test-key")
        assert top("users sign in") == ["auth"], seen
        assert seen == [("/v1/embeddings", "Bearer embed-test-key", "m", n) for n in (4, 1)], seen
        top("users sign in")
        assert [s[3] for s in seen[2:]] == [1], "the facts' vectors are stored"
        ws.kg_add("session", "session cookies expire after 30 minutes", "T2")
        ro, n = core.Workspace(d, readonly=True), len(seen)
        assert set(top("login", ro)) == set(top("login", ro)) == {"auth", "session"}, seen
        top("login"), top("login")
        assert [s[3] for s in seen[n:]] == [1, 1, 1, 1, 1, 1, 1], "read-only: the new fact is sent each time; writable: once"
    finally:
        srv.shutdown()
        srv.server_close()
        vault_set("EMBED_KEY")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert top("dang nhap")[0] == "auth"
    assert "embeddings:" in err.getvalue() and "ranking locally" in err.getvalue(), err.getvalue()
    ws.db.close()
    ro.db.close()
    shutil.rmtree(d, ignore_errors=True)


def test_remote_worker():
    """A worker on another machine: a runner that claims the attempt and goes silent is detected (heartbeat), the retry is
    served by a real runner process, its patch goes through scope and verify here. The two tokens open disjoint routes."""
    import secrets
    tok = secrets.token_urlsafe(24)  # generated here, written nowhere
    sc = {"plan": [task("T1", "far", ["far.txt"], [["python", "-c", "assert open('far.txt').read().strip() == 'far'"]])],
          "steps": {"worker:T1": [{"write": {"far.txt": "far\n"}}]}}
    r = Repo(sc, workers={"far": {"agent": "remote", "model": "mock:mock-fast", "max": 1}})
    with unittest.mock.patch.dict(os.environ, ORCH_REMOTE_TOKEN=tok), ui_server(r.repo) as call:
        out = open(r.tmp / "engine.out", "w")  # a file, not a pipe: a full pipe hangs the child on Windows
        eng = subprocess.Popen([sys.executable, "-m", "orch", "--ws", str(r.repo), "run", "demo goal", "--yes", "--exit-on-wait"],
                               cwd=ROOT, env={**r.env, "ORCH_REMOTE_STALE": "2", "ORCH_REMOTE_WAIT": "60"},
                               stdout=out, stderr=subprocess.STDOUT)
        try:
            deadline, got = time.time() + 60, None
            while time.time() < deadline and not got:  # a "ghost" runner takes the attempt, then never beats
                code, body = call("/api/lease", {"agents": ["mock"], "runner": "ghost"}, token=tok)
                assert code == 200, body
                got = json.loads(body)["lease"] and json.loads(body)
                time.sleep(0.3)
            assert got, "the engine never opened a lease"
            lease = got["lease"]
            assert (lease["agent"], lease["model"], lease["schema"], lease["readonly"]) == ("mock", "mock-fast", "handoff", 0), lease
            assert lease["prompt"].startswith("ORCH-CALL role=worker task=T1") and got["bundle"], lease
            while time.time() < deadline and r.q("SELECT 1 FROM leases WHERE id=?", lease["id"]):
                time.sleep(0.3)  # the proxy gives up after 2s without a heartbeat and removes its lease
            assert call("/api/lease/beat", {"id": lease["id"], "runner": "ghost"}, token=tok) == (200, '{"cancel": true}')
            code, body = call("/api/lease/done", {"id": lease["id"], "runner": "ghost", "ok": True, "patch": ""}, token=tok)
            assert code == 400 and "gone" in body, body
            assert call("/api/lease", {"agents": ["mock"], "runner": "x"})[0] == 403, "the UI token must not open runner routes"
            assert call("/api/state", token=tok)[0] == 403, "the runner token must not open the UI"
            run = subprocess.run([sys.executable, "-m", "orch", "remote", "run", "--url", call.base, "--name", "box1", "--agents", "mock",
                                  "--once"], cwd=ROOT, env={**r.env, "ORCH_REMOTE_TOKEN": tok, "ORCH_HOME": str(r.tmp / "remote-home")},
                                 capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            assert run.returncode == 0 and "serving mock" in run.stdout and ": ok" in run.stdout, run.stdout + run.stderr
            assert eng.wait(timeout=120) == 0, (r.tmp / "engine.out").read_text(encoding="utf-8", errors="replace")
        finally:
            if eng.poll() is None:
                eng.kill()
            out.close()
    assert r.status() == {"PLAN": "done", "T1": "done", "REVIEW": "done"}, r.status()
    assert r.show("far.txt").strip() == "far"
    assert r.outcomes("T1") == ["error", "integrated"], r.outcomes("T1")
    first = r.q("SELECT failure FROM attempts WHERE task='T1' AND kind='work' ORDER BY id")[0][0]
    assert "remote runner ghost stopped responding" in first, first
    assert any("box1 took" in b for _, b in r.q("SELECT id, body FROM events WHERE kind='remote'"))
    assert r.q("SELECT count(*) FROM leases") == [(0,)] and not list((r.repo / ".orch" / "leases").iterdir())
    assert agents.account("remote", "codex:gpt-5.5") == "remote/codex"


def test_cli_parsers_failure_classes_and_env():
    """Parsers on real CLI output (docs/probes), failure classes that ignore project text, the verify allowlist env."""
    probes, tmp = ROOT / "docs" / "probes", Path(tempfile.mkdtemp(prefix="orch-parse-"))
    agy = agents._agy((probes / "agy.json").read_text(encoding="utf-8"), None)
    assert agy["text"].strip() == "OK" and agy["error"] is None and agy["tokens_in"] == 16627, agy
    claude = agents._claude((probes / "claude.json").read_text(encoding="utf-8"), None)
    assert agents.classify(claude["error"]) == "auth" and claude["session"], claude
    oc = agents._opencode((probes / "opencode.jsonl").read_text(encoding="utf-8"), None)  # opencode's own sqlite crash
    assert oc["session"] and oc["error"].startswith("Unexpected server error") and agents.classify(oc["error"]) == "error", oc
    ev = [{"type": "thread.started", "thread_id": "th-1"},
          {"type": "item.completed", "item": {"type": "agent_message", "text": '{"status": "done"}'}},
          {"type": "turn.completed", "usage": {"input_tokens": 120, "output_tokens": 30}}]
    cx = agents._codex("\n".join(map(json.dumps, ev)), tmp / "missing.txt")
    assert (cx["text"], cx["session"], cx["tokens_in"], cx["tokens_out"], cx["error"]) == ('{"status": "done"}', "th-1", 120, 30, None)
    err = agents._codex(json.dumps({"type": "error", "message": "You've hit your usage limit. Try again at Oct 4th, 2026 8:58 AM."}), tmp / "x")
    assert agents.classify(err["error"]) == "quota" and agents.reset_at(err["error"]), err
    for text, kind in [("Error: Not logged in. Please run /login", "auth"), ("HTTP 401 Unauthorized", "auth"),
                       ("status: 429 Too Many Requests", "rate_limit"), ("Quota exceeded for quota metric", "quota"),
                       ("RESOURCE_EXHAUSTED", "quota"), ('{"type": "authentication_error"}', "auth"), ("code: invalid_api_key", "auth"),
                       ("You exceeded your current quota", "quota"), ("insufficient_quota", "quota"), ("model gpt-x is not supported when using ChatGPT", "model"),
                       # project text an agent prints: none of these is about the account
                       ("FAILED test_login_returns_401 (route /login)", "error"), ('File "app.py", line 429, in handler', "error"),
                       ("tests for quota.py failed", "error"), ("def authenticate(user):", "error")]:
        assert agents.classify(text) == kind, (text, agents.classify(text), kind)
    # run_agent: a reply that is not the CLI's JSON is classified on stderr only, never on the transcript it quotes
    scen = tmp / "scenario.json"
    scen.write_text(json.dumps({"steps": {"worker:T1": [{"exit": 1, "stderr": "Traceback: line 429 in test_quota_401"}]}}), encoding="utf-8")
    with unittest.mock.patch.dict(os.environ, ORCH_MOCK=str(scen)):
        r = agents.run_agent("mock", "mock-fast", "ORCH-CALL role=worker task=T1\nwork", tmp, tmp / "out", schema="handoff")
    assert not r["ok"] and r["failure"] == "error", r
    secrets_env = {"SSH_AUTH_SOCK": "/tmp/agent.sock", "DATABASE_URL": "postgres://u:pw@db/x", "GH_PAT": "x", "MY_FLAG": "1",
                   "SESSION_COOKIE": "c", "PLAIN_SETTING": "kept for agents"}
    with unittest.mock.patch.dict(os.environ, secrets_env):
        agent_env, ver, more = agents.clean_env(), agents.verify_env(), agents.verify_env(["my_flag", "GH_PAT"])
    assert agent_env["PLAIN_SETTING"] and not {"SSH_AUTH_SOCK", "DATABASE_URL", "GH_PAT", "SESSION_COOKIE"} & set(agent_env)
    assert "PATH" in ver and "PLAIN_SETTING" not in ver and "MY_FLAG" not in ver and ver["PYTHONDONTWRITEBYTECODE"] == "1"
    assert more["MY_FLAG"] == "1" and "GH_PAT" not in more, "team verify_env adds names, never secret-looking ones"
    shutil.rmtree(tmp, ignore_errors=True)


def test_bench_solo_versus_team():
    """`bench`: one agent alone and the team on the same goal from the same commit, both judged by the user's check (not by
    the agents' own verify): here the solo agent writes a wrong add() and replies nothing (as a real agy denied a command),
    not even on its repair turn; the team writes a right one."""
    sc = two_tasks()
    sc["steps"]["worker:SOLO"] = [{"write": {"app.py": "def add(a, b):\n    return a - b\n"}, "raw": ""}, {"raw": "Done!"}]
    r = Repo(sc)
    (r.tmp / "home").mkdir(exist_ok=True)
    (r.tmp / "home" / "agents.json").write_text(json.dumps({"mock": {"note": "## This CLI cannot run commands"}}), encoding="utf-8")
    assert r.orch("bench", "demo goal", "--check", 'python -c "import app; assert app.add(2, 3) == 5"', "--solo", "mock/mock-fast") == 0, r.out
    prompt = next((r.repo / ".orch" / "bench").glob("*/solo-1/agent/prompt.md")).read_text(encoding="utf-8")
    assert "This CLI cannot run commands" in prompt, "the CLI's quirks reach the solo agent too (a real agy returned nothing without it)"
    report = next((r.repo / ".orch" / "bench").glob("*/report.md")).read_text(encoding="utf-8")
    solo_row = next(l for l in report.splitlines() if l.startswith("| 1 | solo mock/mock-fast"))
    team_row = next(l for l in report.splitlines() if l.startswith("| 1 | team (lead mock, 2 worker(s), mode team)"))
    assert "| no valid handoff | 0/1 | 2,000 | 200 |" in solo_row and "| 1 | 0 |" in solo_row, solo_row  # one call (+ its repair), no question
    log = (Path(f"{r.scenario}.state") / "calls.log").read_text(encoding="utf-8")
    assert "worker SOLO 2 resume" in log and "repair=1" in log, "the solo agent gets the repair turn every engine call gets"
    assert "| done | 1/1 |" in team_row and "| 0 |" in team_row, team_row
    assert "failed `python -c" in report and "AssertionError" in report, report
    bid = next((r.repo / ".orch" / "bench").glob("*")).name
    assert "return a - b" in r.git("show", f"orch/bench-{bid}/solo-1:app.py") and r.git("rev-parse", "HEAD") == r.base
    assert not [w for w in r.git("worktree", "list").splitlines()[1:] if "bench-" in w], "no worktree is left behind"
    assert not list((r.tmp / "home" / "wt").rglob("*")), "nor their empty directories (the team run's and the bench's)"
    assert r.orch("bench", "demo goal") == 1 and "--check" in r.out, "without a check there is nothing to judge by"


def test_bench_repeats_modes_and_team_files():
    """--repeat N with medians, the workspace team in another mode, a team file as one more arm; dollars at list price."""
    from orch import models
    check = [["python", "-c", "import app; assert app.add(2, 3) == 5"]]
    sc = two_tasks()
    sc["steps"]["worker:SOLO"] = [{"write": {"app.py": ADD}}]
    sc["steps"]["worker:T1"] = [{"write": {"app.py": ADD}}]
    r = Repo(sc, verify=check)
    home = r.tmp / "home"
    home.mkdir(exist_ok=True)
    (home / "models.json").write_text(json.dumps({"models": {models.norm("mock-fast"): {"price_in": 1.0, "price_out": 2.0},
                                                            models.norm("mock-strong"): {"price_in": 3.0, "price_out": 15.0}}}), encoding="utf-8")
    other = json.loads((r.repo / ".orch" / "team.json").read_text(encoding="utf-8"))
    other["workers"] = {"w1": other["workers"]["w1"]}  # a one-worker team: the plan's T2 goes to w1 too
    (r.tmp / "one.json").write_text(json.dumps(other), encoding="utf-8")
    sc["plan"] = [dict(t, assignee="w1") for t in sc["plan"]]
    r.scenario.write_text(json.dumps(sc), encoding="utf-8")
    assert r.orch("bench", "demo goal", "--check", 'python -c "import app; assert app.add(2, 3) == 5"', "--solo", "mock/mock-fast", "--repeat", "2", "--mode", "solo", "--team-file", str(r.tmp / "one.json")) == 0, r.out
    report = r.show_file(".orch/bench/*/report.md")
    summary = report.split("## Summary: medians of 2 runs per arm")[1].split("## Every run")[0]
    rows = [l for l in summary.splitlines() if l.startswith("| ") and not l.startswith("| arm") and not l.startswith("|---")]
    assert [l.split(" | ")[0][2:] for l in rows] == ["solo mock/mock-fast", "team (lead mock, 2 worker(s), mode team)", "team mode solo", "team one.json"], rows
    assert all("| 2/2 | 1/1 |" in l for l in rows), rows
    solo, full, light = rows[0], rows[1], rows[2]
    assert "| ~0.0012 | 1 | 0 |" in solo, solo  # 1,000 in x $1 + 100 out x $2 per Mtok (one call, no repair needed)
    assert "| 1 | 0 |" in light and "| 5 | 0 |" in full, (light, full)  # solo mode: the worker only; team: plan, review, T1, T2, review
    every = report.split("## Every run")[1]
    assert sum(l.startswith("| 1 |") for l in every.splitlines()) == 4 and sum(l.startswith("| 2 |") for l in every.splitlines()) == 4, every
    assert len({l.split("`")[-2] for l in every.splitlines() if l.startswith("| ") and "`orch/" in l}) == 8, "every run has its own branch"
    assert not [w for w in r.git("worktree", "list").splitlines()[1:] if "bench-" in w]


def test_doctor():
    """Local readiness report: machine, project, team, workspace DB; a team agent missing here fails; secrets never printed."""
    r = Repo(two_tasks())
    home = r.tmp / "home"
    home.mkdir(exist_ok=True)
    (home / "vault.json").write_text("{}", encoding="utf-8")
    assert r.orch("doctor") == 0, r.out
    for frag in ("[ok  ] git", "with FTS5", "[ok  ] team             lead mock", "Ready."):
        assert frag in r.out, (frag, r.out)
    assert r.run() == 0 and r.orch("doctor") == 0 and "workspace db     schema 1" in r.out and "engine           not running" in r.out, r.out
    (home / "agents.json").write_text(json.dumps({"ghost": {"name": "ghost", "bin": "no-such-agent-cli-xyz", "mode": {}, "run": [],
                                                           "prompt": "stdin", "parse": "agy"}}), encoding="utf-8")
    team = json.loads((r.repo / ".orch" / "team.json").read_text(encoding="utf-8"))
    team["workers"]["w2"] = {"agent": "ghost", "model": "m"}
    team["workers"]["far"] = {"agent": "remote", "model": "codex:x"}
    (r.repo / ".orch" / "team.json").write_text(json.dumps(team), encoding="utf-8")
    secret = "doctor-test-secret-0123456789"
    assert r.orch("doctor", ORCH_REMOTE_TOKEN="short", DEMO_API_KEY=secret) == 1, r.out
    assert "w2 uses ghost, which is not installed here" in r.out and "ORCH_REMOTE_TOKEN is missing or shorter" in r.out, r.out
    assert secret not in r.out and "short" not in r.out.replace("shorter", ""), "doctor must never print a secret"
    if os.name != "nt":  # an unreadable vault is a reported problem, not a crash
        (home / "vault.json").write_text("not json", encoding="utf-8")
        assert r.orch("doctor") == 1 and "cannot be read (JSONDecodeError)" in r.out and "Traceback" not in r.out, r.out


def test_db_schema_versions():
    """A workspace from before versioning becomes version 1 with any missing table; a later migration runs once; a database
    from a newer Orctram is refused instead of being misread."""
    from orch import core
    d = Path(tempfile.mkdtemp(prefix="orch-db-"))
    ws = core.Workspace(d)
    ws.db.executescript("DROP TABLE leases; PRAGMA user_version=0;")  # what a 0.0 workspace looks like
    ws.db.close()
    ws = core.Workspace(d)
    assert ws.q("PRAGMA user_version") == [{"user_version": 1}] and ws.q("SELECT count(*) n FROM leases") == [{"n": 0}]
    ws.db.close()
    with unittest.mock.patch.object(core, "WS_MIGRATIONS", [(2, ["ALTER TABLE tasks ADD COLUMN extra TEXT"])]):
        for _ in range(2):  # the second open must not run the ALTER again (it would fail: duplicate column)
            ws = core.Workspace(d)
            assert ws.q("PRAGMA user_version") == [{"user_version": 2}]
            assert any(r["name"] == "extra" for r in ws.q("PRAGMA table_info(tasks)"))
            ws.db.close()
    try:  # back on code that only knows version 1: refuse, never misread
        core.Workspace(d)
        raise AssertionError("a newer database was opened")
    except RuntimeError as e:
        assert "newer Orctram" in str(e), e
    shutil.rmtree(d, ignore_errors=True)


def test_package_ships_its_data():
    """pip install orctram: every catalog file and the UI are package data, the version and the command resolve."""
    import fnmatch, tomllib, orch, orch.__main__
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    globs = cfg["tool"]["setuptools"]["package-data"]["orch"]
    data = [p.relative_to(ROOT / "orch").as_posix() for p in (ROOT / "orch").rglob("*")
            if p.is_file() and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts]
    missing = [d for d in data if not any(fnmatch.fnmatchcase(d, g) for g in globs)]
    assert not missing and "catalog/agents.json" in data and "ui.html" in data, f"not shipped by pip install: {missing}"
    assert cfg["project"]["scripts"]["orctram"] == "orch.__main__:main" and callable(orch.__main__.main)
    assert cfg["project"]["dependencies"] == [] and re.fullmatch(r"\d+\.\d+\.\d+", orch.__version__)
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").lstrip().startswith("Apache License")


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
