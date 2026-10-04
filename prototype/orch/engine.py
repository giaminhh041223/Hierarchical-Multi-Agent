"""Engine: a deterministic scheduler around four LLM decision points (plan, review, triage, skills).

The lead is stateless: every lead prompt is rebuilt from the DB. Workers edit isolated git worktrees; the engine commits,
merges the integration tip in, checks scope, runs the plan's verify commands, records the commit as intent, fast-forwards
the run's integration branch, and only then publishes facts and releases dependents."""
import collections, contextlib, fnmatch, hashlib, json, os, re, shutil, sqlite3, subprocess, threading, time, traceback, urllib.request
from pathlib import Path

from . import agents, models, pool
from .core import ACTIVE, HOME, TERMINAL, EngineLock, contract, extract_json, hm, record, schema, validate

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HOOKS = HOME / "no-hooks"  # never created: engine commits run no git hooks
RESERVED = re.compile(r"^(PLAN|SKILLS|AMEND\d*|REVIEW\d*|BUDGET\d*)$", re.I)
TASK_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,15}$")
YES = {"y", "yes", "ok", "okay", "approve", "approved", "accept", "lgtm", "go", "có", "ok luôn", "đồng ý", "duyệt"}
HARD_CAP = 6  # attempts per task before the user is asked
TEAM_DEFAULTS = {"max_parallel": 4, "timeout": 1800, "verify_timeout": 600, "budget_tokens": 0, "max_amend": 1,
                 "skills": True, "auto_approve": False, "wait_reset": 600, "cooldown": 3600, "account_max": {},
                 "verify_allow": None, "mcp": False, "embeddings": None}

RULES = {
    "common": """You are one agent in Orchestra, a local multi-agent coding team. The engine (a program, not an LLM) owns git, scheduling and integration.
- Never run git commands that write (commit, merge, rebase, reset, checkout, stash, push, branch): the engine commits and merges your work.
- Work only inside your current directory (a git worktree of the project). Never touch .orch/.
- Be economical with context: read only what you need, prefer targeted search over reading whole trees.
- Shared knowledge, read-only: `python -m orch kg search "<words>"` (facts other agents published), `python -m orch board` (task board).
- Your final message is the JSON output contract and nothing else.""",
    "worker": """Role: worker. Implement exactly your task and make every acceptance statement true.
- Run the verify commands yourself before handing off and fix failures: the engine reruns them and rejects the handoff if one fails.
- Change only paths inside your scope; anything else is rejected. If you truly need an out-of-scope change, or a decision that is not yours (secrets, product choices, goal changes), reply status "blocked" with one precise question.
- facts: 0-5 short durable statements other agents need (interfaces, file locations, commands). No narration.
- No global installs or system changes; project-local dependencies are fine when the task needs them.""",
    "lead": """Role: lead (read-only: you plan and decide, workers edit).
Planning:
- Split the goal into the fewest cohesive tasks; tasks without dependencies run in parallel. Add a dependency only when a task needs another's output.
- Each task: precise title, checkable acceptance, tight scope_paths (disjoint between tasks that may run in parallel), and fast verify commands (argv arrays, cross-platform, run from the repo root, exit 0 on success).
- Assign by strength (see the worker cards). Agents with a high per-call overhead get fewer, larger tasks.
- Put tests in scope when a task should add them.
Authority: you may retry, reassign, cancel and re-plan. Only the user may provide secrets or credentials, change the goal or accept scope cuts, approve spending beyond the budget, install non-curated skills, merge into their branch, or approve destructive operations: for those use ask_user with one precise question.""",
    "reviewer": """Role: reviewer (read-only). Find what would make the result wrong, unsafe or unverifiable: missing requirements, wrong dependencies, overlapping scopes between parallel tasks, verify commands that would pass on broken work, security problems.
- blocker = must be fixed before proceeding; advisory = optional. Be specific and brief; no style nitpicks.""",
    "skill_architect": """Role: skill architect. Pick at most 3 skills from the curated index that clearly help specific tasks (e.g. a document-format skill for a task that edits .docx). None is better than marginal ones. You may propose one non-curated GitHub repository URL when it is clearly valuable; the user must approve it before it is installed.""",
}


# --- git -------------------------------------------------------------------------------------------------
def _git(cwd, *args, env=None, text=True):
    """text=False: raw bytes (binary patches)."""
    return subprocess.run(["git", "-c", f"core.hooksPath={HOOKS.as_posix()}", "-c", "core.quotepath=false", "-c", "user.name=orchestra",
                           "-c", "user.email=orchestra@localhost", "-c", "commit.gpgsign=false", *args],
                          cwd=str(cwd), capture_output=True, creationflags=NO_WINDOW, env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
                          **({"encoding": "utf-8", "errors": "replace"} if text else {}))


def git(cwd, *args, codes=(0,)):
    r = _git(cwd, *args)
    if codes is not None and r.returncode not in codes:
        raise RuntimeError(f"git {' '.join(args[:2])}: {(r.stderr or r.stdout).strip()[-600:]}")
    return r.stdout.strip()


def git_ok(cwd, *args):
    return _git(cwd, *args).returncode == 0


def ensure_excluded(project):
    """Engine files never show up in the user's `git status` or in worker commits (info/exclude is shared by all worktrees)."""
    common = Path(git(project, "rev-parse", "--git-common-dir"))
    f = (common if common.is_absolute() else Path(project) / common) / "info" / "exclude"
    f.parent.mkdir(parents=True, exist_ok=True)
    have = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    add = [p for p in (".orch/", ".agents/skills/orch-*/") if p not in have]
    if add:
        f.write_text("\n".join(have + add) + "\n", encoding="utf-8")


# --- pure checks -------------------------------------------------------------------------------------------
def norm_scope(s):
    s = s.strip().replace("\\", "/")
    return s[2:] if s.startswith("./") else s


def scope_error(s):
    if not s or s.startswith("/") or re.match(r"^[A-Za-z]:", s):
        return "must be a relative path"
    if ".." in s.split("/"):
        return "must not contain .."
    if s.split("/")[0] in (".git", ".orch"):
        return "is engine territory"
    return None


def in_scope(path, scopes):
    """files, dirs (with or without trailing /) and globs; '.' or '**' = whole repo. ponytail: fnmatch '*' also crosses '/'."""
    for s in map(norm_scope, scopes):
        if s in (".", "*", "**", "**/*"):
            return True
        if any(c in s for c in "*?["):
            if fnmatch.fnmatchcase(path, s) or fnmatch.fnmatchcase(path, s.replace("**/", "")):
                return True
        elif path == s.rstrip("/") or path.startswith(s.rstrip("/") + "/"):
            return True
    return False


def check_plan(plan, workers, existing=None):
    """Semantics the schema cannot express. existing = {id: status} of tasks already in the run (amendments)."""
    existing, errs, tasks = existing or {}, [], plan["tasks"]
    ids = [t["id"] for t in tasks]
    if not tasks:
        errs.append("plan has no tasks")
    if len(tasks) > 30:
        errs.append("too many tasks (max 30)")
    if len(set(ids)) < len(ids):
        errs.append(f"duplicate ids {sorted({i for i in ids if ids.count(i) > 1})}")
    for t in tasks:
        i = t["id"]
        t["scope_paths"] = [norm_scope(s) for s in t["scope_paths"]]
        if not TASK_ID.match(i) or RESERVED.match(i) or i in existing:
            errs.append(f"{i}: invalid, reserved or already used id")
        if not t["title"].strip():
            errs.append(f"{i}: empty title")
        if t["assignee"] not in workers:
            errs.append(f"{i}: unknown assignee {t['assignee']!r} (workers: {', '.join(workers)})")
        if not any(a.strip() for a in t["acceptance"]):
            errs.append(f"{i}: no acceptance criteria")
        if not t["verify"] or any(not v or not v[0].strip() for v in t["verify"]):
            errs.append(f"{i}: verify needs at least one non-empty argv array")
        if not t["scope_paths"]:
            errs.append(f"{i}: empty scope_paths")
        errs += [f"{i}: scope {s!r} {e}" for s in t["scope_paths"] if (e := scope_error(s))]
        errs += [f"{i}: unknown dependency {d!r}" for d in t["deps"]
                 if d not in ids and existing.get(d, "failed") in ("failed", "cancelled")]
    graph, done = {t["id"]: [d for d in t["deps"] if d in ids] for t in tasks}, set()
    while True:  # Kahn: whatever never becomes ready is on a cycle (self-dependencies included)
        ready = {i for i, ds in graph.items() if i not in done and all(d in done for d in ds)}
        if not ready:
            break
        done |= ready
    if len(done) < len(graph):
        errs.append(f"dependency cycle among {sorted(set(graph) - done)}")
    return errs


ASK_VERIFY = "Verify commands outside team verify_allow:"


def allowed(cmd, allow):
    """team "verify_allow": command prefixes, e.g. [["python", "-m", "unittest"]], that run without asking. None (default) =
    no list: the plan approval covers its commands."""
    return allow is None or any(cmd[:len(a)] == a for a in allow)


def file_map(files, limit=300):
    """Every path when they fit in `limit` lines; else the deepest directory level that fits, deeper ones as "dir/ (n files)".
    ponytail: one cut level for the whole tree; expand small directories further (greedy by size) if plans miss files."""
    rows = {}
    for depth in range(max((f.count("/") for f in files), default=0) + 1, 0, -1):
        rows = collections.Counter("/".join(f.split("/")[:depth]) + ("/" if f.count("/") >= depth else "") for f in files)
        if len(rows) <= limit:
            break
    lines = [r + (f" ({n} files)" if r.endswith("/") else "") for r, n in sorted(rows.items())]
    return ("\n".join(lines[:limit]) + (f"\n... {len(lines) - limit} more" if len(lines) > limit else "")) or "(empty repository)"


def check_handoff(h):
    return ["status blocked needs a non-empty question"] if h["status"] == "blocked" and not (h["question"] or "").strip() else []


def entity(fact, tid):
    head, sep, _ = fact.partition(":")
    return head.strip() if sep and 0 < len(head.strip()) <= 60 else tid


def crash_point(name):
    """Test hook: die like a power cut at a named point (no cleanup, no finally)."""
    if os.environ.get("ORCH_CRASH_AT") == name:
        os._exit(17)


def load_team(ws):
    t = ws.read_json("team.json")
    if not t:
        raise SystemExit("no team yet: run `python -m orch init` first")
    return {**TEAM_DEFAULTS, **t}


def write_rules(ws):
    d = ws.dir / "rules"
    d.mkdir(exist_ok=True)
    for name, text in RULES.items():
        if not (d / f"{name}.md").exists():
            (d / f"{name}.md").write_text(text + "\n", encoding="utf-8")


def save_team(ws, team):
    """Validate, then write team.json and any missing rule file (one per role, one per worker)."""
    roles = ("lead", "reviewer", "skill_architect")
    workers = team.get("workers") if isinstance(team, dict) else None
    if not isinstance(workers, dict) or not workers:
        raise ValueError("team needs lead, reviewer, skill_architect and at least one worker")
    cat = agents.catalog()
    for name, r in [*((n, team.get(n)) for n in roles), *workers.items()]:
        if not isinstance(r, dict) or r.get("agent") not in cat or not r.get("model"):
            raise ValueError(f"{name}: needs {{\"agent\": one of {sorted(cat)}, \"model\": ...}}")
    bad = [n for n in workers if not re.fullmatch(r"[A-Za-z0-9][\w-]{0,31}", n) or n in RULES]  # names become file names
    if bad:
        raise ValueError(f"bad worker names {bad}: use letters, digits, - and _, and not a role name")
    team = {**TEAM_DEFAULTS, **team}
    ws.write_json("team.json", team)
    write_rules(ws)
    for n, w in workers.items():
        f = ws.dir / "rules" / f"{n}.md"
        if not f.exists():
            f.write_text(f"You are worker {n}, running {w['agent']}/{w['model']}.\n", encoding="utf-8")
    return team


def new_run(ws, goal, auto_approve=False):
    team = load_team(ws)
    if EngineLock(ws).held_elsewhere():
        raise SystemExit("an engine is already running on this workspace (see: python -m orch status)")
    if not git_ok(ws.project, "rev-parse", "--verify", "HEAD"):
        raise SystemExit("the project needs a git repository with at least one commit (python -m orch init can create one)")
    base = git(ws.project, "rev-parse", "HEAD")
    dirty = [ln for ln in git(ws.project, "status", "--porcelain").splitlines() if ".orch" not in ln]
    ensure_excluded(ws.project)
    write_rules(ws)
    run = time.strftime("%Y%m%d-%H%M%S")
    ws.meta("run", run)
    e = Engine(ws)
    for k, v in (("goal", goal), ("base", base), ("auto_approve", int(bool(auto_approve or team["auto_approve"]))),
                 ("budget", team["budget_tokens"])):
        e.rmeta(k, v)
    e.wt_dir.mkdir(parents=True, exist_ok=True)
    git(ws.project, "worktree", "add", "-q", "-b", f"orch/{run}/main", str(e.main_wt), base)
    ws.add_task("PLAN", "plan", "Plan: " + goal[:100], assignee="lead")
    ws.event("run", f"run {run} from {base[:10]}: {goal[:200]}")
    if dirty:
        ws.event("warn", f"{len(dirty)} uncommitted change(s) are NOT visible to agents (they start from {base[:10]}); commit first if they matter")
    return e


class Fail(Exception):
    def __init__(self, cls, detail):
        super().__init__(f"{cls}: {detail}")
        self.cls, self.detail = cls, detail or ""


class _Abort(Exception):
    pass


class Engine:
    def __init__(self, ws, exit_on_wait=False):
        self.ws, self.exit_on_wait = ws, exit_on_wait
        self.team, self.run = load_team(ws), ws.run
        if not self.run:
            raise SystemExit('no run yet: python -m orch run "<goal>"')
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", ws.project.name)[:24]
        self.wt_dir = HOME / "wt" / f"{slug}-{hashlib.sha1(str(ws.project).encode()).hexdigest()[:8]}" / self.run
        self.main_wt = self.wt_dir / "_main"
        self.rdir = ws.dir / "runs" / self.run
        self.jobs, self.kills = {}, {}
        self.integrate_lock = threading.Lock()  # ponytail: one integration at a time; optimistic re-verify if verify gets slow
        self.role_locks = {r: threading.Lock() for r in ("lead", "reviewer", "skill_architect")}

    # --- small helpers ------------------------------------------------------------------------------------
    def rmeta(self, k, v=None):
        return self.ws.meta(f"{self.run}:{k}", v)

    @property
    def goal(self):
        return self.rmeta("goal") or ""

    def tip(self):
        return git(self.ws.project, "rev-parse", f"orch/{self.run}/main")

    def header(self, role, task, extra=""):
        return f"ORCH-CALL role={role} task={task} run={self.run}{extra}"

    def rules(self, *names):
        d = self.ws.dir / "rules"
        return "\n\n".join((d / f"{n}.md").read_text(encoding="utf-8").strip() for n in names if (d / f"{n}.md").exists())

    def worker_name(self, name):
        return next((w for w in self.team["workers"] if w.lower() == (name or "").lower()), None)

    def cancelled(self, tid):
        r = self.ws.q("SELECT cancel FROM tasks WHERE run=? AND id=?", self.run, tid)
        return bool(r and r[0]["cancel"])

    def set(self, tid, status, why="", expect=None, **fields):
        if self.ws.update(tid, _expect=expect, status=status, **fields):
            self.ws.event(status, why, tid)
            return True
        return False

    def unapproved(self, cmds):
        """Verify commands outside team verify_allow that the user has not allowed in this run."""
        return [v for v in cmds if not allowed(v, self.team["verify_allow"]) and not self.rmeta(f"allow:{json.dumps(v)}")]

    def approve(self, cmds):
        for v in self.unapproved(cmds):
            self.rmeta(f"allow:{json.dumps(v)}", 1)

    def to_user(self, tid, question, expect=None):
        t = self.ws.task(tid)
        if self.ws.update(tid, _expect=expect or t["status"], status="pending_user", question=question[:4000]):
            self.ws.event("pending_user", question[:300], tid)
            self.notify(f"[{self.ws.project.name}] {tid} needs you: {question[:300]}")

    def notify(self, text):
        """Optional webhook (ntfy / Slack / Discord style), configured by the user: ORCH_NOTIFY_URL or team.notify_url."""
        url = os.environ.get("ORCH_NOTIFY_URL") or self.team.get("notify_url")
        if not url:
            return
        try:
            req = urllib.request.Request(url, data=json.dumps({"text": text, "content": text}).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "orchestra"})
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as e:  # a dead webhook must never stop the run
            self.ws.event("warn", f"notify failed: {e}")

    def start(self, key, fn, *args):
        def guard():
            try:
                fn(*args)
            except Exception:
                tb = traceback.format_exc()
                self.ws.event("error", tb[-1500:], key)
                t = self.ws.task(key)
                if t and t["status"] not in TERMINAL:
                    self.to_user(key, f"Engine error while handling {key}:\n{tb[-800:]}\nReply 'retry' to try again or 'cancel'.")
        th = threading.Thread(target=guard, name=key, daemon=True)
        self.jobs[key] = th
        th.start()

    # --- attempts -----------------------------------------------------------------------------------------
    def new_attempt(self, task, kind, agent, model):
        with self.ws.lock:
            return self.ws.db.execute("INSERT INTO attempts(run, task, kind, agent, model, started) VALUES(?,?,?,?,?,?)",
                                      (self.run, task, kind, agent, model, time.time())).lastrowid

    def open_attempt(self, tid):
        r = self.ws.q("SELECT max(id) id FROM attempts WHERE run=? AND task=? AND ended IS NULL", self.run, tid)
        return r[0]["id"]

    def end_attempt(self, att, outcome, detail=None):
        """Close once and feed the global history (the observed half of the model knowledge base)."""
        now = time.time()
        if not att or not self.ws.x("UPDATE attempts SET ended=?, outcome=?, failure=? WHERE id=? AND ended IS NULL",
                                    now, outcome, (detail or "")[:4000] or None, att):
            return
        a = self.ws.q("SELECT * FROM attempts WHERE id=?", att)[0]
        record(str(self.ws.project), a["task"], a["agent"], a["model"], a["kind"], outcome, round(now - a["started"], 1),
               a["tokens_in"], a["tokens_out"], a["cost"])

    def evidence_dir(self, tid):
        r = self.ws.q("SELECT dir FROM attempts WHERE run=? AND task=? AND kind='work' ORDER BY id DESC LIMIT 1", self.run, tid)
        return Path(r[0]["dir"]) if r and r[0]["dir"] else self.rdir / "attempts" / f"{tid}-x"

    def used_tokens(self):
        return self.ws.q("SELECT coalesce(sum(tokens_in + tokens_out), 0) n FROM attempts WHERE run=?", self.run)[0]["n"]

    # --- one agent call with its output contract ------------------------------------------------------------
    def parse(self, text, contract_name, check):
        try:
            obj = validate(extract_json(text or ""), schema(contract_name))
        except ValueError as e:
            return None, str(e)
        errs = check(obj) if check else []
        return obj, "; ".join(errs) or None

    def ask(self, role, who, prompt, contract_name, task, kind, cwd, readonly=True, session=None, fresh=None, **kw):
        """Workers rotate in route(). The lead, reviewer and skill architect get a stand-in while their account is out of
        usage; fresh = the same request without the session's context, since a stand-in cannot resume that session."""
        me = who
        while True:
            if role != "worker" and self.cooling(self.acct(who)):
                who = self.stand_in(readonly) or who
            if who is not me:
                self.ws.event("stand_in", f"{who['agent']}/{who['model']} stands in for the {role}: {me['agent']} is out of usage", task, role)
            try:
                obj, att, sess = self.call(role, who, prompt if who is me or not session else fresh or prompt, contract_name, task,
                                           kind, cwd, readonly, session if who is me else None, **kw)
                return obj, att, sess if who is me else None
            except Fail as f:
                if role == "worker" or f.cls not in ("quota", "rate_limit"):
                    raise
                self.cool(self.acct(who), f.detail, self.team["cooldown"] if f.cls == "quota" else 300)
                if not self.stand_in(readonly):
                    raise

    def call(self, role, who, prompt, contract_name, task, kind, cwd, readonly=True, session=None, check=None,
             timeout=900, keep_open=False):
        """Run, validate strictly, repair once. Returns (obj, attempt id, session); raises Fail(class, detail).
        keep_open: work attempts are closed later with their real outcome (integrated / verify / scope ...)."""
        aid, model = who["agent"], who["model"]
        note = agents.catalog()[aid].get("note")  # CLI quirks every role must know (e.g. agy denies shell commands)
        prompt += f"\n\n{note}" if note and not session else ""
        with self.role_locks.get(role) or contextlib.nullcontext():
            att = self.new_attempt(task, kind, aid, model)
            d = self.rdir / "attempts" / f"{task}-{att}-{kind}"
            self.ws.x("UPDATE attempts SET dir=? WHERE id=?", str(d), att)

            def started(pid, ctime, kill):
                self.ws.x("UPDATE attempts SET pid=?, pid_ctime=? WHERE id=?", pid, ctime, att)
                self.kills[task] = kill

            run = lambda p, sub, sess: agents.run_agent(aid, model, p, cwd, sub, schema=contract_name, session=sess, timeout=timeout,
                                                        readonly=readonly, on_start=started, env={"ORCH_WS": str(self.ws.project)},
                                                        mcp=self.ws.project if self.team["mcp"] else None)
            r = run(prompt, d, session)
            calls, obj, err = [r], None, None
            if r["ok"]:
                obj, err = self.parse(r["text"], contract_name, check)
                if err and not self.cancelled(task):
                    can = bool(r["session"] and agents.catalog()[aid].get("resume"))
                    fix = (f"{prompt.splitlines()[0]} repair=1\nYour previous reply was rejected by the engine: {err}\n"
                           "Reply again with ONLY the corrected JSON object for the same output contract.")
                    r2 = run(fix if can else f"{prompt}\n\n{fix}\nRejected reply:\n{r['text'][:4000]}", d / "repair", r["session"] if can else None)
                    calls.append(r2)
                    if r2["ok"]:
                        obj, err = self.parse(r2["text"], contract_name, check)
                        r["session"] = r2["session"] or r["session"]
                    else:
                        r = {**r, "ok": False, "failure": r2["failure"], "error": r2["error"]}
            self.kills.pop(task, None)
            costs = [c["cost"] for c in calls if c["cost"] is not None]
            self.ws.x("UPDATE attempts SET tokens_in=?, tokens_out=?, cost=?, session=? WHERE id=?",
                      sum(c["tokens_in"] or 0 for c in calls), sum(c["tokens_out"] or 0 for c in calls),
                      sum(costs) if costs else None, r["session"], att)
            if not r["ok"]:
                self.end_attempt(att, r["failure"] or "error", r["error"])
                raise Fail(r["failure"] or "error", r["error"] or "")
            if err:
                self.end_attempt(att, "invalid", err)
                raise Fail("invalid", f"{err}\nreply: {(calls[-1]['text'] or '')[:1500]}")
            if not keep_open:
                self.end_attempt(att, "ok")
            return obj, att, r["session"]

    # --- main loop ------------------------------------------------------------------------------------------
    def loop(self):
        lock = EngineLock(self.ws)
        if not lock.acquire():
            raise SystemExit("another engine is already running on this workspace")
        try:
            if self.rmeta("status") in TERMINAL:
                return self.rmeta("status")
            self.reconcile()
            self.check_resources()
            while True:
                self.apply_answers()
                self.apply_cancels()
                self.jobs = {k: th for k, th in self.jobs.items() if th.is_alive()}
                self.schedule(self.budget_gate())
                if self.jobs:
                    time.sleep(0.2)
                    continue
                ts = self.ws.tasks()
                live = [t for t in ts if t["status"] not in TERMINAL]
                if not live:
                    return self.finish(self.outcome(ts))
                if any((t["status"] == "pending_user" and t["answer"] is not None) or t["cancel"] for t in live):
                    continue  # applied on the next tick
                if any(t["status"] == "todo" and t["eligible_at"] > time.time() for t in live):
                    time.sleep(1)  # rate-limit backoff
                    continue
                if any(t["status"] == "pending_user" for t in live):
                    if self.exit_on_wait:
                        return self.pause()
                    time.sleep(1)
                    continue
                return self.finish("failed", "stuck: " + ", ".join(f"{t['id']}={t['status']}" for t in live))
        finally:
            lock.release()  # daemon job threads die with the process; their job objects kill the agent trees

    def schedule(self, gate):
        ts = self.ws.tasks()
        by, busy, per = {t["id"]: t for t in ts}, {}, {}  # running work per worker, per account
        for t in ts:
            if t["kind"] == "work" and t["status"] in ACTIVE:
                busy[t["assignee"]] = busy.get(t["assignee"], 0) + 1
                ac = self.acct(self.team["workers"].get(t["assignee"]))
                per[ac] = per.get(ac, 0) + 1
        running = sum(busy.values())
        skills_open = by.get("SKILLS", {}).get("status") not in (None, *TERMINAL)
        for t in ts:
            tid, st = t["id"], t["status"]
            if tid in self.jobs or t["cancel"]:
                continue
            if st == "verifying":  # the engine stopped between a handoff and its integration
                self.start(tid, self.post_process, tid)
                continue
            if gate:
                continue
            if st == "needs_lead":
                self.start(tid, self.job_triage, t)
                continue
            need = TERMINAL if t["kind"] == "review" else {"done"}  # the final review also judges what failed
            if st != "todo" or t["eligible_at"] > time.time() or any(by.get(d, {}).get("status") not in need for d in t["deps"]):
                continue
            if t["kind"] == "work":
                home = self.rmeta(f"home:{tid}")  # set by rotate(): the planned worker, back once its usage limit resets
                if home in self.team["workers"] and not self.cooling(self.acct(self.team["workers"][home])):
                    self.reassign(t, home, f"{home} is available again", keep=True)
                    t = self.ws.task(tid)  # start it in this pass: the loop calls a tick without jobs "stuck"
                elif self.cooling(ag := self.acct(self.team["workers"].get(t["assignee"]))):
                    # out of usage before it even started: move it now instead of spending a failing call first
                    self.rotate(t, f"{ag} is out of usage until {hm(self.cool_until(ag))}", self.cool_until(ag))
                    t = self.ws.task(tid)
                    if t["status"] != "todo" or t["eligible_at"] > time.time():
                        continue
                w = self.team["workers"].get(t["assignee"]) or {}
                ac = self.acct(w)  # account_max: workers sharing one subscription take turns instead of burning it in parallel
                if skills_open or running >= self.team["max_parallel"] or busy.get(t["assignee"], 0) >= w.get("max", 1) \
                        or per.get(ac, 0) >= self.team["account_max"].get(ac, float("inf")):
                    continue
                busy[t["assignee"]] = busy.get(t["assignee"], 0) + 1
                per[ac] = per.get(ac, 0) + 1
                running += 1
            if self.ws.update(tid, _expect="todo", status="running"):
                fn = {"plan": self.job_plan, "skills": self.job_skills, "work": self.job_work, "review": self.job_review}[t["kind"]]
                self.start(tid, fn, {**t, "status": "running"})

    def budget_gate(self):
        """True while new agent calls must wait for the user (running ones finish)."""
        ts = self.ws.tasks()
        if any(t["kind"] == "gate" and t["status"] == "pending_user" for t in ts):
            return True
        budget, used = int(float(self.rmeta("budget") or 0)), self.used_tokens()
        if not budget or used < budget or self.rmeta("cancelled"):
            return False
        gid = f"BUDGET{1 + sum(t['kind'] == 'gate' for t in ts)}"
        self.ws.add_task(gid, "gate", "Token budget reached", status="pending_user")
        self.ws.update(gid, question=f"Token budget reached: {used:,} of {budget:,} tokens used. "
                                     f"Reply with a new budget (e.g. {budget * 2}) to continue, or 'stop'.")
        self.ws.event("pending_user", f"budget reached ({used:,}/{budget:,})", gid)
        self.notify(f"[{self.ws.project.name}] token budget reached ({used:,}/{budget:,})")
        return True

    def outcome(self, ts):
        if self.rmeta("cancelled"):
            return "cancelled"
        reviews = [t for t in ts if t["kind"] == "review"]
        return "done" if reviews and reviews[-1]["status"] == "done" else "failed"

    # --- user input -----------------------------------------------------------------------------------------
    def apply_answers(self):
        for t in self.ws.tasks("pending_user"):
            tid, a = t["id"], (t["answer"] or "").strip()
            if t["answer"] is None or tid in self.jobs or not self.ws.update(tid, _expect="pending_user", answer=None):
                continue
            self.ws.event("answer", a[:300], tid, "user")
            low = a.lower().strip(" .!'\"")
            if t["kind"] == "plan":
                plan = self.latest_plan()
                if low in YES and plan:
                    self.approve([v for p in plan["plan"]["tasks"] for v in p["verify"]])  # shown in plan.md
                    self.materialize(plan["plan"], "pending_user", plan["version"])
                else:
                    self.set(tid, "todo", "re-plan", "pending_user", question=None,
                             note="" if low in YES | {"retry"} else f"User feedback on the previous plan: {a}")
            elif t["kind"] == "review":
                if low in YES:
                    self.set(tid, "done", "accepted by the user", "pending_user", question=None)
                elif low == "retry":
                    self.set(tid, "todo", "review again", "pending_user", question=None)
                else:
                    self.start(tid, self.job_amend, t, [f"User: {a}"])
            elif t["kind"] == "gate":
                self.apply_gate(t, low)
            elif t["kind"] == "skills" and low != "retry":
                from . import skills
                self.set(tid, "done", skills.settle(self, low in YES), "pending_user", question=None)
            elif low in YES and self.unapproved(t["spec"].get("verify", [])):
                self.approve(t["spec"]["verify"])
                for x in self.ws.tasks("pending_user"):  # this task, and others held only by the same commands
                    if x["answer"] is None and (x["question"] or "").startswith(ASK_VERIFY) and not self.unapproved(x["spec"]["verify"]):
                        self.set(x["id"], "todo", "verify commands allowed by the user", "pending_user", question=None, eligible_at=0)
            elif low in ("cancel", "skip", "hủy", "bỏ qua"):
                self.terminate(tid, "cancelled", "cancelled by the user")
            elif (m := re.fullmatch(r"reassign\s+(\S+)", low)) and self.worker_name(m.group(1)):
                self.reassign(t, self.worker_name(m.group(1)), "requested by the user")
            else:
                self.set(tid, "todo", "answered", "pending_user", question=None, eligible_at=0, note=f"Answer from the user: {a}")

    def apply_gate(self, t, low):
        if low in ("stop", "cancel"):
            self.set(t["id"], "done", "stop", "pending_user")
            return self.cancel_all("stopped at the budget gate")
        m = re.fullmatch(r"([\d_,.]+)\s*([km]?)", low)
        if not m:
            return self.ws.event("warn", "budget answer must be a number (e.g. 5000000, 500k, 2m) or 'stop'", t["id"])
        n = int(float(m.group(1).replace(",", "").replace("_", "")) * {"": 1, "k": 1e3, "m": 1e6}[m.group(2)])
        self.rmeta("budget", n)
        self.set(t["id"], "done", f"budget raised to {n:,}", "pending_user", question=None)

    def apply_cancels(self):
        for t in self.ws.tasks():
            if t["cancel"] and t["status"] not in TERMINAL:
                if t["id"] in self.jobs:
                    (self.kills.get(t["id"]) or (lambda: None))()  # its job sees the flag and finishes the cancel
                else:
                    self.terminate(t["id"], "cancelled", "cancelled by the user")

    def cancel_all(self, why):
        self.rmeta("cancelled", 1)
        self.ws.x("UPDATE tasks SET cancel=1 WHERE run=? AND status NOT IN ('done','failed','cancelled')", self.run)
        self.ws.event("cancel", why)

    def terminate(self, tid, status, why):
        """failed / cancelled, cascading to dependents (which can no longer run)."""
        t = self.ws.task(tid)
        if not t or t["status"] in TERMINAL:
            return
        self.end_attempt(self.open_attempt(tid), status, why)
        self.set(tid, status, why, t["status"], question=None)
        for d in self.ws.tasks():
            if tid in d["deps"] and d["status"] not in TERMINAL and d["kind"] != "review":
                self.terminate(d["id"], "cancelled", f"dependency {tid} {status}")

    # --- failure routing --------------------------------------------------------------------------------------
    def route(self, tid, cls, detail):
        """Deterministic routing; every edge records the attempt outcome first. Never more than one identical retry."""
        t = self.ws.task(tid)
        if t["cancel"]:
            return self.terminate(tid, "cancelled", "cancelled by the user")
        prior = self.ws.q("SELECT count(*) n FROM attempts WHERE run=? AND task=? AND outcome=?", self.run, tid, cls)[0]["n"]
        self.end_attempt(self.open_attempt(tid), cls, detail)
        w = self.team["workers"].get(t["assignee"])
        st, agent, ac = t["status"], (w or {}).get("agent", t["assignee"]), self.acct(w) or t["assignee"]
        if t["attempts"] >= HARD_CAP:
            return self.to_user(tid, f"{tid} used {t['attempts']} attempts (last: {cls}: {detail[:500]}). "
                                     "Reply with instructions, 'reassign <worker>' or 'cancel'.", st)
        if cls == "auth":
            return self.to_user(tid, f"{agent} is not authenticated ({detail[:200].strip()}). Log in with `python -m orch login {agent}` "
                                     "(or store its API key: `python -m orch vault set NAME`), then reply 'retry'. "
                                     "Or reply 'reassign <worker>' / 'cancel'.", st)
        if cls == "quota" or (cls == "rate_limit" and prior >= 3):
            return self.rotate(t, f"{ac} is out of usage: {detail[:200].strip()}",
                               self.cool(ac, detail, self.team["cooldown"] if cls == "quota" else 300))
        if cls == "rate_limit":
            wait = min(900, 60 * 2 ** prior)
            return self.set(tid, "todo", f"rate limited: retry in {wait}s", st, eligible_at=time.time() + wait)
        if cls in ("conflict", "crashed") or (cls in ("scope", "verify", "error", "invalid") and prior == 0):
            return self.set(tid, "todo", f"{cls}: automatic retry", st, eligible_at=0,
                            note=f"The engine did not accept attempt {t['attempts']} ({cls}):\n{detail[-3000:]}")
        return self.set(tid, "needs_lead", f"{cls}: {detail[:200]}", st, question=f"{cls}: {detail[-3000:]}")

    def reassign(self, t, worker, why, keep=False):
        """keep: the previous worker stopped for a reason outside the task (usage), so its unfinished edits stay in place."""
        if not keep:
            self.reset_worktree(t["id"])
        self.rmeta(f"home:{t['id']}", "")  # a deliberate reassignment is the new home; rotate() sets it again after this
        note = f"This task was reassigned from {t['assignee']} to you: {why}" + (
            "\nIts unfinished changes are already in this worktree (`git status`, `git diff`): keep what is right and finish the task."
            if keep else "")
        self.set(t["id"], "todo", f"reassigned {t['assignee']} -> {worker}: {why[:150]}", t["status"], assignee=worker,
                 session=None, question=None, eligible_at=0, note=note)

    # --- usage limits: per-account cooldowns, worker rotation, role stand-ins ---------------------------------
    @staticmethod
    def acct(w):
        """The account (quota) a worker or role spends: its agent id, or a router provider (agents.account)."""
        return agents.account(w["agent"], w["model"]) if w else None

    def cool_until(self, aid):
        return float(self.ws.meta(f"cool:{aid}") or 0)

    def cooling(self, aid):
        return self.cool_until(aid) > time.time()

    def cool(self, aid, detail, seconds):
        """Per account (acct), shared by every run of this workspace. The reset time the CLI names (in its message,
        or in its quota record) beats the default: team "cooldown" for usage limits, 5 minutes for repeated rate limits."""
        until = agents.reset_at(detail) or agents.usage_reset(aid) or time.time() + seconds
        self.ws.meta(f"cool:{aid}", until)
        self.ws.event("cooldown", f"{aid} out of usage until {hm(until)}: {detail[:200]}")
        return until

    def primaries(self):
        """Workers the lead plans with; backups only stand in."""
        return {n: w for n, w in self.team["workers"].items() if not w.get("backup")}

    def spare(self, t):
        """Who takes over t: a free slot first; then the pool backup planned for its worker, other backups, primaries; in team
        order; never a cooling account."""
        busy = {}
        for x in self.ws.tasks():
            if x["kind"] == "work" and x["status"] in ACTIVE:
                busy[x["assignee"]] = busy.get(x["assignee"], 0) + 1
        mine = self.rmeta(f"home:{t['id']}") or t["assignee"]
        rank = lambda w: 3 if not w.get("backup") else 0 if mine in w.get("for", []) else 2 if w.get("for") else 1
        ok = [(busy.get(n, 0) >= w.get("max", 1), rank(w), i, n) for i, (n, w) in enumerate(self.team["workers"].items())
              if n != t["assignee"] and not self.cooling(self.acct(w))]
        return min(ok)[-1] if ok else None

    def rotate(self, t, why, until):
        """Out of usage: wait when the reset is near or nobody can take over; otherwise a spare continues the unfinished
        work and schedule() hands the task back to its planned worker after the reset."""
        tid = t["id"]
        w = until - time.time() > self.team["wait_reset"] and self.spare(t)
        if not w:
            return self.set(tid, "todo", f"{why[:200]}; waiting for the reset at {hm(until)}", t["status"], eligible_at=until)
        home = self.rmeta(f"home:{tid}") or t["assignee"]
        self.reassign(t, w, why, keep=t["attempts"] > 0)  # a task moved before it ever ran has no unfinished work to point at
        self.rmeta(f"home:{tid}", home)

    def check_resources(self):
        """At every start: each account's quota outlook. One its CLI reports exhausted cools now, so its tasks go to backups
        without a failing call first; a warning when an account may run out and its workers have no backup."""
        for aid, o in pool.outlooks(self.team, self.ws).items():
            if o["out_until"] and o["out_until"] > self.cool_until(aid):
                self.ws.meta(f"cool:{aid}", o["out_until"])
            bare = [n for n, w in self.primaries().items() if self.acct(w) == aid and not pool.backups_of(self.team, n)]
            self.ws.event("resources", f"{aid}: {o['text']}" + (f"; no backup for {', '.join(bare)}: python -m orch pool plan"
                                                                 if o["risk"] and bare else ""))

    def stand_in(self, readonly):
        """For lead / reviewer / skill architect calls: the first role or worker whose account is not cooling."""
        tm = self.team
        return next((w for w in (tm["lead"], tm["reviewer"], tm.get("skill_architect"), *tm["workers"].values())
                     if w and not self.cooling(self.acct(w)) and (not readonly or agents.supports_readonly(w["agent"]))), None)

    # --- worktrees ------------------------------------------------------------------------------------------
    def worktree(self, tid):
        path = self.wt_dir / tid
        if not (path / ".git").exists():
            shutil.rmtree(path, ignore_errors=True)
            git(self.ws.project, "worktree", "prune", codes=None)
            git(self.ws.project, "worktree", "add", "-q", "-B", f"orch/{self.run}/{tid}", str(path), self.tip())
        return path

    def reset_worktree(self, tid):
        """Back to the integration tip; the abandoned attempt is kept as a patch (evidence before reset)."""
        path = self.wt_dir / tid
        if not (path / ".git").exists():
            return
        git(path, "add", "-A", codes=None)
        d = self.rdir / "attempts"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{tid}-abandoned-{int(time.time())}.patch").write_text(git(path, "diff", "--cached", "--binary", self.tip(), codes=None), encoding="utf-8")
        git(path, "reset", "-q", "--hard", self.tip(), codes=None)
        git(path, "clean", "-fdq", codes=None)

    def drop_worktree(self, tid):
        git(self.ws.project, "worktree", "remove", "--force", str(self.wt_dir / tid), codes=None)
        git(self.ws.project, "branch", "-D", f"orch/{self.run}/{tid}", codes=None)

    def cleanup(self):
        """Run over: unintegrated work is kept as a wip commit on its task branch; worktrees go away."""
        for p in (self.wt_dir.iterdir() if self.wt_dir.exists() else []):
            if p.name != "_main" and (p / ".git").exists():
                git(p, "add", "-A", codes=None)
                git(p, "commit", "-q", "--no-verify", "-m", f"wip {p.name} (not integrated)", codes=None)
                git(self.ws.project, "worktree", "remove", "--force", str(p), codes=None)
        git(self.ws.project, "worktree", "remove", "--force", str(self.main_wt), codes=None)
        git(self.ws.project, "worktree", "prune", codes=None)

    # --- jobs -----------------------------------------------------------------------------------------------
    def job_plan(self, t):
        lead, rev, cwd = self.team["lead"], self.team["reviewer"], self.main_wt
        prev = self.latest_plan()
        check = lambda p: check_plan(p, self.primaries())
        try:
            prompt = self.packet_plan(prev, t["note"])
            plan, _, sess = self.ask("lead", lead, prompt, "plan", "PLAN", "plan", cwd, check=check)
            verdicts, unresolved = [], []
            for rnd in (1, 2):
                v, _, _ = self.ask("reviewer", rev, self.packet_plan_review(plan), "verdict", "PLAN", "review", cwd)
                verdicts.append(v)
                blockers = [i for i in v["issues"] if i["severity"] == "blocker"]
                self.ws.event("review", f"plan round {rnd}: {v['verdict']}, {len(blockers)} blocker(s), "
                                        f"{len(v['issues']) - len(blockers)} advisory", "PLAN", "reviewer")
                if not blockers:
                    break
                if rnd == 2:
                    unresolved = blockers
                    break
                issues = "\n".join(f"- {i['severity']} [{i['task_id'] or 'plan'}] {i['message']}" for i in v["issues"])
                can = bool(sess and agents.catalog()[lead["agent"]].get("resume"))
                full = f"{prompt}\n\n## Your previous plan\n{json.dumps(plan, ensure_ascii=False)}\n\n## Reviewer issues to fix\n{issues}"
                p2 = (f"{self.header('lead', 'PLAN', ' revision=1')}\nThe reviewer raised:\n{issues}\nFix every blocker, apply the advisories you "
                      "agree with, and reply with ONLY the complete revised plan JSON (same contract)." if can else full)
                plan, _, sess = self.ask("lead", lead, p2, "plan", "PLAN", "plan", cwd, session=sess if can else None, fresh=full, check=check)
        except Fail as f:
            return self.to_user("PLAN", f"Planning failed ({f.cls}): {f.detail[:600]}\nFix the cause (e.g. `python -m orch login <agent>` "
                                        "or edit .orch/team.json) and reply 'retry'.", "running")
        version = (prev["version"] if prev else 0) + 1
        self.ws.q("INSERT INTO plans VALUES(?,?,?,?)", self.run, version, json.dumps(plan, ensure_ascii=False), json.dumps(verdicts, ensure_ascii=False))
        md = self.write_plan_md(plan, version, verdicts)
        self.ws.event("plan", f"v{version}: {len(plan['tasks'])} task(s) -> {md}", "PLAN", "lead")
        if unresolved:
            return self.to_user("PLAN", f"Plan v{version} still has reviewer blockers after 2 rounds:\n" +
                                "\n".join(f"- [{i['task_id'] or 'plan'}] {i['message']}" for i in unresolved) +
                                f"\nPlan: {md}\nReply 'yes' to approve anyway, or write what to change.", "running")
        if self.rmeta("auto_approve") == "1":
            return self.materialize(plan, "running")
        self.to_user("PLAN", f"Plan v{version} ({len(plan['tasks'])} tasks) is ready: {md}\nReply 'yes' to start, or write what to change.", "running")

    def materialize(self, plan, expect, version=None):
        """Plan approved: tasks + skills + final review appear atomically, exactly once. version = the one the user approved; if
        they saved an edit meanwhile (edit_plan), nothing happens and the edit's own question waits for a fresh 'yes'."""
        try:
            with self.ws.tx():
                if (version and self.latest_plan()["version"] != version) or not self.ws.update("PLAN", _expect=expect, status="done", question=None):
                    raise _Abort
                for p in plan["tasks"]:
                    self.ws.add_task(p["id"], "work", p["title"], {k: p[k] for k in ("acceptance", "scope_paths", "verify")}, p["assignee"], p["deps"])
                if self.team["skills"]:
                    self.ws.add_task("SKILLS", "skills", "Pick and install skills for this plan", assignee="skill_architect")
                self.ws.add_task("REVIEW", "review", "Final review of the integrated result", assignee="reviewer", deps=[p["id"] for p in plan["tasks"]])
                self.ws.event("done", f"plan approved: {len(plan['tasks'])} task(s)", "PLAN")
        except _Abort:
            pass

    def job_skills(self, t):
        try:
            from . import skills
            summary = skills.architect(self, t)
        except Fail as f:
            summary = f"skill architect unavailable ({f.cls}): {f.detail[:200]}"
        except Exception as e:  # skills are an optimisation: never block the run on them
            summary = f"skills skipped: {e}"
        if self.ws.q("SELECT 1 FROM skills WHERE run=? AND status='proposed' AND curated=1", self.run):
            return self.to_user("SKILLS", f"{summary}. Reply 'yes' to install them (team skills=propose), or 'no' to work without them.", "running")
        self.set("SKILLS", "done", summary, "running")

    def job_work(self, t):
        tid, w = t["id"], self.team["workers"].get(t["assignee"])
        if not w:
            return self.route(tid, "missing", f"worker {t['assignee']!r} is not in the team ({', '.join(self.team['workers'])})")
        if ask := self.unapproved(t["spec"]["verify"]):  # an auto-approved plan or an amendment: nobody has seen these yet
            return self.to_user(tid, ASK_VERIFY + "\n" + "\n".join(f"- {subprocess.list2cmdline(v)}" for v in ask)
                                + "\nReply 'yes' to allow them in this run, or 'cancel'.")
        path = self.worktree(tid)
        try:
            from . import skills
            skills_txt = skills.place(self.ws, self.run, tid, path)
        except Exception as e:
            skills_txt = ""
            self.ws.event("warn", f"skills not placed: {e}", tid)
        resume = bool(t["session"] and agents.catalog().get(w["agent"], {}).get("resume"))
        n = t["attempts"] + 1
        self.ws.update(tid, attempts=n)
        self.ws.event("start", f"attempt {n}: {w['agent']}/{w['model']}{' (resumed session)' if resume else ''}", tid, t["assignee"])
        try:
            h, _, sess = self.ask("worker", w, self.packet_work({**t, "attempts": n}, resume, skills_txt), "handoff", tid, "work", path,
                                  readonly=False, session=t["session"] if resume else None, check=check_handoff,
                                  timeout=self.team["timeout"], keep_open=True)
        except Fail as f:
            if f.cls in ("timeout", "error", "model", "missing"):
                self.ws.update(tid, session=None)  # a broken or stuck session must not poison the next attempt
            return self.route(tid, f.cls, f.detail)
        if self.cancelled(tid):
            return self.terminate(tid, "cancelled", "cancelled by the user")
        self.ws.update(tid, handoff=h, session=sess, note="")
        self.ws.event("handoff", f"{h['status']}: {h['summary'][:200]}", tid, t["assignee"])
        if h["status"] != "done":
            return self.route(tid, h["status"], h["question"] if h["status"] == "blocked" else h["summary"])
        if self.ws.update(tid, _expect="running", status="verifying"):
            self.post_process(tid)

    def post_process(self, tid):
        """Option A: commit -> merge tip in -> scope -> verify combined tree -> record intent -> ff-only -> finalize."""
        t = self.ws.task(tid)
        path, spec = self.wt_dir / tid, t["spec"]
        if not (path / ".git").exists():
            return self.route(tid, "error", "the task worktree is missing")
        with self.integrate_lock:
            git(path, "add", "-A")
            marked = git(path, "grep", "--cached", "-I", "-l", "-E", "-e", "^(<<<<<<<|>>>>>>>)( |$)", codes=(0, 1))
            if marked:
                return self.route(tid, "conflict", "unresolved conflict markers remain in: " + ", ".join(marked.splitlines()))
            if git_ok(path, "rev-parse", "-q", "--verify", "MERGE_HEAD") or not git_ok(path, "diff", "--cached", "--quiet"):
                git(path, "commit", "-q", "--no-verify", "-m", f"wip {tid} attempt {t['attempts']}")  # task branch only
            tip = self.tip()
            if not git_ok(path, "merge-base", "--is-ancestor", tip, "HEAD"):
                r = _git(path, "merge", "--no-edit", "-q", tip)
                if r.returncode:
                    files = git(path, "diff", "--name-only", "--diff-filter=U").splitlines()
                    if not files:
                        git(path, "merge", "--abort", codes=None)
                        return self.route(tid, "error", f"merging the integration tip failed: {(r.stderr or r.stdout)[-800:]}")
                    self.ws.event("conflict", ", ".join(files), tid)
                    return self.route(tid, "conflict", "Work integrated meanwhile conflicts with yours in: " + ", ".join(files) +
                                      ". Those files now contain conflict markers (<<<<<<< ======= >>>>>>>): edit them so both intents "
                                      "survive, remove every marker, rerun verify. Do not run git.")
            # --no-renames: a rename must show its out-of-scope source path too
            changed = [p for p in git(path, "diff", "--name-only", "--no-renames", "-z", tip, "HEAD").split("\0") if p]
            bad = [p for p in changed if not in_scope(p, spec.get("scope_paths", []))]
            if bad:
                self.ws.event("scope", f"outside {spec.get('scope_paths')}: {bad[:10]}", tid)
                return self.route(tid, "scope", f"You changed files outside your scope {spec.get('scope_paths')}: {bad[:20]}. "
                                                "Revert them, or reply blocked with a question if they are truly needed.")
            ok, report = self.verify(spec.get("verify", []), path, self.evidence_dir(tid))
            self.ws.event("verify", ("pass: " if ok else "FAIL: ") + report[:300], tid)
            if not ok:
                return self.route(tid, "verify", f"verification failed:\n{report}")
            if self.cancelled(tid):
                return self.terminate(tid, "cancelled", "cancelled by the user")
            # one squashed commit = exactly the verified tree on top of the tip: rejected attempts never reach the history
            sha = git(path, "-c", f"user.name=orch/{t['assignee']}", "commit-tree", "HEAD^{tree}", "-p", tip,
                      "-m", f"{tid}: {t['title']}"[:200]) if changed else tip
            if not self.ws.update(tid, _expect="verifying", status="integrating", commit_sha=sha):
                return
            git(self.main_wt, "merge", "--ff-only", "-q", sha)
            crash_point("after_merge")
            self.finalize(tid, sha, changed)

    def verify(self, cmds, cwd, d):
        """Plan-declared argv commands, no shell, credential-free env, tree-killed on timeout. Stops at the first failure."""
        d.mkdir(parents=True, exist_ok=True)
        done = []
        for i, argv in enumerate(cmds):
            o, e = d / f"verify{i}.out", d / f"verify{i}.err"
            try:
                code = agents.spawn((agents.resolve_bin(argv[0]) or [argv[0]]) + argv[1:], cwd, agents.clean_env(), out=o, err=e,
                                    timeout=self.team["verify_timeout"])
            except OSError as ex:
                return False, f"$ {subprocess.list2cmdline(argv)}\ncannot run: {ex}"
            if code != 0:
                tail = (o.read_text(encoding="utf-8", errors="replace") + e.read_text(encoding="utf-8", errors="replace"))[-3000:]
                return False, f"$ {subprocess.list2cmdline(argv)}\n{'timeout' if code is None else f'exit {code}'}\n{tail}"
            done.append(f"$ {subprocess.list2cmdline(argv)} ok")
        return True, "; ".join(done) or "no verify commands"

    def finalize(self, tid, sha, changed=None):
        """integrating -> done, facts and links, in one transaction guarded by compare-and-set: exactly once."""
        t = self.ws.task(tid)
        h = t["handoff"] or {}
        try:
            with self.ws.tx():
                if not self.ws.update(tid, _expect="integrating", status="done", note=""):
                    raise _Abort
                for f in h.get("facts", [])[:12]:
                    self.ws.kg_add(entity(f, tid), f[:500], tid, t["assignee"], sha)
                for x in h.get("decisions", [])[:12]:
                    self.ws.kg_add("decision", x[:500], tid, t["assignee"], sha)
                for p in (changed or h.get("files", []))[:200]:
                    self.ws.link(tid, "changed", p, tid)
                for dep in t["deps"]:
                    self.ws.link(tid, "after", dep, tid)
                self.ws.event("integrated", f"{sha[:10]} {h.get('summary', '')[:200]}", tid, t["assignee"])
        except _Abort:
            return False
        self.end_attempt(self.open_attempt(tid), "integrated")
        self.drop_worktree(tid)
        return True

    def job_triage(self, t):
        tid = t["id"]
        try:
            d, _, _ = self.ask("lead", self.team["lead"], self.packet_triage(t), "triage", tid, "triage", self.main_wt,
                               check=lambda d: self.check_triage(d))
        except Fail as f:
            return self.to_user(tid, f"{tid} needs a decision and the lead is unavailable ({f.cls}). Problem: {(t['question'] or '')[:800]}\n"
                                     "Reply with instructions, 'reassign <worker>' or 'cancel'.", "needs_lead")
        self.ws.event("triage", f"{d['action']}: {d['note'][:200]}", tid, "lead")
        if d["action"] == "retry":
            self.set(tid, "todo", "lead: retry", "needs_lead", question=None, eligible_at=0, note=f"Instructions from the lead: {d['note']}")
        elif d["action"] == "reassign":
            self.reassign(t, self.worker_name(d["assignee"]), d["note"])
        elif d["action"] == "ask_user":
            self.to_user(tid, d["question"], "needs_lead")
        else:
            self.terminate(tid, "failed" if d["action"] == "fail" else "cancelled", f"lead: {d['note'][:300]}")

    def check_triage(self, d):
        e = []
        if d["action"] == "reassign" and not self.worker_name(d["assignee"]):
            e.append(f"reassign needs assignee = one of {list(self.team['workers'])}")
        if d["action"] == "ask_user" and not (d["question"] or "").strip():
            e.append("ask_user needs a question")
        return e

    def job_review(self, t):
        """Final review of the combined tree: rerun every verify command, then the reviewer reads the diff."""
        tid = t["id"]
        work = [x for x in self.ws.tasks() if x["kind"] == "work" and x["status"] == "done"]
        problems, seen = [], set()
        for x in work:
            cmds = [c for c in x["spec"].get("verify", []) if json.dumps(c) not in seen]
            seen |= {json.dumps(c) for c in cmds}
            ok, rep = self.verify(cmds, self.main_wt, self.rdir / "attempts" / f"{tid}-verify-{x['id']}")
            if not ok:
                problems.append({"task_id": x["id"], "severity": "blocker", "message": f"verify fails on the combined tree: {rep[-1500:]}"})
        try:
            v, _, _ = self.ask("reviewer", self.team["reviewer"], self.packet_final(tid, work, problems), "verdict", tid, "review", self.main_wt)
        except Fail as f:
            return self.to_user(tid, f"The final review could not run ({f.cls}): {f.detail[:300]}\nReply 'accept' to finish without it, or 'retry'.", "running")
        issues = v["issues"] + problems
        blockers = [i for i in issues if i["severity"] == "blocker"]
        self.ws.update(tid, handoff={**v, "issues": issues})
        self.ws.event("review", f"final: {v['verdict']}, {len(blockers)} blocker(s)", tid, "reviewer")
        if not blockers:
            return self.set(tid, "done", "approved", "running")
        lines = [f"[{i['task_id'] or '-'}] {i['message']}" for i in blockers]
        if sum(x["kind"] == "review" for x in self.ws.tasks()) - 1 < self.team["max_amend"]:
            return self.job_amend(t, lines)
        self.to_user(tid, "Final review blockers remain:\n" + "\n".join(f"- {x}" for x in lines) +
                     "\nReply 'accept' to finish as is, or describe what to do (the lead will add tasks).", "running")

    def job_amend(self, t, issues):
        """Final-review rejection returns to executing through a recorded amendment (new tasks + a new review)."""
        tid, ts = t["id"], self.ws.tasks()
        existing = {x["id"]: x["status"] for x in ts}
        try:
            plan, _, _ = self.ask("lead", self.team["lead"], self.packet_amend(issues), "plan", tid, "plan", self.main_wt,
                                  check=lambda p: check_plan(p, self.primaries(), existing))
        except Fail as f:
            return self.to_user(tid, f"The lead could not amend the plan ({f.cls}: {f.detail[:300]}). Issues:\n" + "\n".join(issues) +
                                "\nReply 'accept' to finish as is, or give instructions.")
        version = (self.latest_plan() or {"version": 0})["version"] + 1
        rid = f"REVIEW{1 + sum(i.startswith('REVIEW') for i in existing)}"
        try:
            with self.ws.tx():
                if not self.set(tid, "done", f"amended: {len(plan['tasks'])} task(s) added", self.ws.task(tid)["status"], question=None):
                    raise _Abort
                for p in plan["tasks"]:
                    self.ws.add_task(p["id"], "work", p["title"], {k: p[k] for k in ("acceptance", "scope_paths", "verify")}, p["assignee"], p["deps"])
                keep = [x["id"] for x in ts if x["kind"] == "work" and x["status"] not in ("failed", "cancelled")]
                self.ws.add_task(rid, "review", "Final review after amendment", assignee="reviewer", deps=keep + [p["id"] for p in plan["tasks"]])
                self.ws.q("INSERT INTO plans VALUES(?,?,?,?)", self.run, version, json.dumps(plan, ensure_ascii=False), json.dumps({"amend": issues}))
        except _Abort:
            pass

    # --- packets: stable rules first (prompt-cache friendly), then the variable part ---------------------------
    def roster(self):
        return "\n".join(f"- {n}: {w['agent']}/{w['model']}, {w.get('max', 1)} parallel slot(s). {models.card(w['model'])}"
                         for n, w in self.primaries().items())

    def repo_map(self, limit=300):
        return file_map(git(self.main_wt, "ls-files").splitlines(), limit)

    def kg_text(self, query, k=8):
        facts = self.ws.kg_search(query, k)
        return facts and "## Relevant project knowledge\n" + "\n".join(f"- {f['entity']}: {f['fact']} ({f['task']})" for f in facts)

    def join(self, *parts):
        return "\n\n".join(p for p in parts if p)

    def packet_plan(self, prev, feedback):
        return self.join(self.header("lead", "PLAN"), self.rules("common", "lead"), contract("plan"), "---",
                         f"## Goal\n{self.goal}", f"## Workers (assignee must be one of these names)\n{self.roster()}",
                         f"## Repository files\n{self.repo_map()}", self.kg_text(self.goal, 10),
                         prev and f"## Previous plan (v{prev['version']})\n{json.dumps(prev['plan'], ensure_ascii=False)}",
                         feedback and f"## Feedback to address\n{feedback}")

    def packet_plan_review(self, plan):
        return self.join(self.header("reviewer", "PLAN"), self.rules("common", "reviewer"), contract("verdict"), "---",
                         f"## Goal\n{self.goal}", f"## Workers\n{self.roster()}", f"## Repository files\n{self.repo_map(150)}",
                         f"## Plan to review (no work has started)\n{json.dumps(plan, indent=1, ensure_ascii=False)}",
                         "Check coverage of the goal, dependency correctness, overlapping scopes between tasks that can run in parallel, "
                         "verify commands that would really catch broken work, and risky operations.")

    def packet_work(self, t, resume, skills_txt):
        tid, spec, n = t["id"], t["spec"], t["attempts"]
        head = self.header("worker", tid, f" attempt={n}")
        if resume:  # the session already holds the packet: send only the delta
            return (f"{head}\n{t['note'] or 'Continue the task.'}\n\nFix it in this worktree, run the verify commands, "
                    "then reply with ONLY the handoff JSON (same output contract as before).")
        deps = []
        for d in filter(None, map(self.ws.task, t["deps"])):
            h = d["handoff"] or {}
            deps.append(f"- {d['id']} ({d['title']}): {h.get('summary', '')[:600]}\n  files: {', '.join(h.get('files', [])[:20])}"
                        + (f"\n  facts: {'; '.join(h.get('facts', [])[:8])}" if h.get("facts") else ""))
        return self.join(head, self.rules("common", "worker", t["assignee"]), skills_txt, contract("handoff"), "---",
                         f"## Project goal\n{self.goal}",
                         f"## Your task {tid}: {t['title']}\nAcceptance:\n" + "\n".join(f"- {a}" for a in spec.get("acceptance", [])) +
                         f"\nScope (the only paths you may change): {', '.join(spec.get('scope_paths', []))}\n"
                         "Verify (run by the engine from the repo root after your handoff; run them yourself first):\n" +
                         "\n".join(f"- {json.dumps(v)}" for v in spec.get("verify", [])),
                         deps and "## Inputs from finished dependencies\n" + "\n".join(deps),
                         self.kg_text(" ".join([t["title"], *spec.get("acceptance", [])])),
                         t["note"] and f"## Notes for this attempt\n{t['note']}")

    def packet_triage(self, t):
        atts = self.ws.q("SELECT id, kind, agent, model, outcome, failure FROM attempts WHERE run=? AND task=? ORDER BY id", self.run, t["id"])
        spec = t["spec"]
        return self.join(self.header("lead", t["id"], " triage=1"), self.rules("common", "lead"), contract("triage"), "---",
                         f"## Goal\n{self.goal}",
                         f"## Task {t['id']}: {t['title']} (assignee {t['assignee']}, attempt {t['attempts']})\nAcceptance: "
                         f"{'; '.join(spec.get('acceptance', []))}\nScope: {', '.join(spec.get('scope_paths', []))}",
                         f"## Problem\n{t['question'] or '(none recorded)'}",
                         t["handoff"] and f"## Last handoff\n{json.dumps(t['handoff'], ensure_ascii=False)[:2000]}",
                         "## Attempt history\n" + "\n".join(f"- #{a['id']} {a['kind']} {a['agent']}/{a['model']}: {a['outcome']} "
                                                             f"{(a['failure'] or '')[:300]}" for a in atts[-6:]),
                         f"## Workers\n{self.roster()}",
                         "Decide the next step: retry with concrete instructions when the same worker can fix it; reassign when the worker "
                         "is unfit or unavailable; ask_user only for decisions outside your authority.")

    def packet_final(self, tid, work, problems):
        base, tip = self.rmeta("base"), self.tip()
        diff = git(self.main_wt, "diff", base, tip)
        lost = [x for x in self.ws.tasks("failed", "cancelled") if x["kind"] == "work"]
        return self.join(self.header("reviewer", tid), self.rules("common", "reviewer"), contract("verdict"), "---",
                         f"## Goal\n{self.goal}",
                         "## Integrated tasks\n" + "\n".join(f"- {x['id']} {x['title']} [{x['assignee']}]: "
                                                             f"{(x['handoff'] or {}).get('summary', '')[:400]}" for x in work),
                         lost and "## Tasks NOT done\n" + "\n".join(f"- {x['id']} {x['title']}: {x['status']}" for x in lost),
                         "## Verification on the combined tree\n" + ("\n".join(p["message"] for p in problems) or "all verify commands pass"),
                         f"## Diff stat\n{git(self.main_wt, 'diff', '--stat', base, tip)}",
                         f"## Diff{' (truncated)' if len(diff) > 60000 else ''}\n{diff[:60000]}",
                         "Final review: does the integrated result achieve the goal? Blockers only for real defects "
                         "(bugs, missing requirements, security problems, broken tests).")

    def packet_amend(self, issues):
        ts = self.ws.tasks()
        return self.join(self.header("lead", "AMEND"), self.rules("common", "lead"), contract("plan"), "---",
                         f"## Goal\n{self.goal}", f"## Workers\n{self.roster()}",
                         "## Current tasks\n" + "\n".join(f"- {x['id']} [{x['status']}] {x['title']}: {(x['handoff'] or {}).get('summary', '')[:200]}"
                                                          for x in ts if x["kind"] == "work"),
                         "## Issues to fix\n" + "\n".join(f"- {i}" for i in issues),
                         f"Return ONLY NEW tasks that fix these issues. Ids must not reuse: {', '.join(x['id'] for x in ts)}. "
                         "deps may reference done tasks.")

    # --- plan / report files -------------------------------------------------------------------------------------
    def latest_plan(self):
        r = self.ws.q("SELECT version, plan FROM plans WHERE run=? ORDER BY version DESC LIMIT 1", self.run)
        return {"version": r[0]["version"], "plan": json.loads(r[0]["plan"])} if r else None

    def edit_plan(self, version, edits):
        """The user's own edit of the plan waiting for approval (web UI): who does each task and what it waits for. Saved as the
        next version with a fresh approval question. Refused once the plan moved on or an answer is already on its way."""
        cur = self.latest_plan()
        if not cur or cur["version"] != version:
            raise ValueError("the plan changed meanwhile: reload")
        plan, by = cur["plan"], {str(e.get("id")): e for e in edits if isinstance(e, dict) and isinstance(e.get("deps"), list)}
        if len(by) != len(edits) or set(by) != {t["id"] for t in plan["tasks"]}:
            raise ValueError("list every task of the plan once: {id, deps: [ids], assignee}")
        for t in plan["tasks"]:
            t["deps"], t["assignee"] = list(dict.fromkeys(map(str, by[t["id"]]["deps"]))), str(by[t["id"]].get("assignee"))
        if errs := check_plan(plan, self.primaries()):
            raise ValueError("; ".join(errs))
        n, md = version + 1, self.rdir / "plan.md"
        q = f"Plan v{n} ({len(plan['tasks'])} tasks, your edit of v{version}) is ready: {md}\nReply 'yes' to start, or write what to change."
        with self.ws.tx():  # plan.md too: an answer cannot start a re-plan before this version is complete
            if self.latest_plan()["version"] != version or not self.ws.x(
                    "UPDATE tasks SET question=?, updated=? WHERE run=? AND id='PLAN' AND status='pending_user' AND answer IS NULL",
                    q, time.time(), self.run):
                raise ValueError("the plan is not waiting for approval any more, or an answer is already on its way: reload")
            self.ws.q("INSERT INTO plans VALUES(?,?,?,?)", self.run, n, json.dumps(plan, ensure_ascii=False), "[]")
            self.write_plan_md(plan, n, [])
            self.ws.event("plan", f"v{n}: your edit of v{version} -> {md}", "PLAN", "user")
        return n

    def write_plan_md(self, plan, version, verdicts):
        lines = [f"# Plan v{version}", "", f"Goal: {self.goal}", "", "| id | worker | deps | title |", "|---|---|---|---|"]
        lines += [f"| {t['id']} | {t['assignee']} | {', '.join(t['deps']) or '-'} | {t['title']} |" for t in plan["tasks"]]
        for t in plan["tasks"]:
            lines += ["", f"## {t['id']}: {t['title']}", *[f"- [ ] {a}" for a in t["acceptance"]],
                      f"- scope: {', '.join(t['scope_paths'])}", *[f"- verify: `{subprocess.list2cmdline(v)}`" + ("" if allowed(v, self.team["verify_allow"]) else " (not in verify_allow)")
                                                     for v in t["verify"]]]
        lines += ["", "## Resources", "", *pool.describe(self.team, self.ws)]
        for i, v in enumerate(verdicts, 1):
            lines += ["", f"## Review round {i}: {v['verdict']}", *[f"- {x['severity']} [{x['task_id'] or 'plan'}] {x['message']}" for x in v["issues"]]]
        self.rdir.mkdir(parents=True, exist_ok=True)
        (self.rdir / "plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.rdir / "plan.md"

    def report(self, status):
        ts = self.ws.tasks()
        use = self.ws.q("SELECT agent, model, count(*) n, sum(tokens_in) i, sum(tokens_out) o, sum(cost) c FROM attempts "
                        "WHERE run=? GROUP BY agent, model", self.run)
        pend = [t for t in ts if t["status"] == "pending_user"]
        lines = [f"# Orchestra run {self.run}: {status}", "", f"Goal: {self.goal}", "",
                 f"Integration branch `orch/{self.run}/main` ({self.tip()[:10]}, base {self.rmeta('base')[:10]}). "
                 f"Merge when satisfied: `git merge orch/{self.run}/main`", "", "## Tasks", "",
                 "| task | status | worker | attempts | commit | title |", "|---|---|---|---|---|---|",
                 *[f"| {t['id']} | {t['status']} | {t['assignee'] or ''} | {t['attempts']} | {(t['commit_sha'] or '')[:10]} | {t['title'][:70]} |" for t in ts],
                 "", "## Usage", "", "| agent | model | calls | tokens in | tokens out | cost $ |", "|---|---|---|---|---|---|",
                 *[f"| {u['agent']} | {u['model']} | {u['n']} | {u['i'] or 0:,} | {u['o'] or 0:,} | {'' if u['c'] is None else round(u['c'], 4)} |" for u in use]]
        if pend:
            lines += ["", "## Waiting for you", "", *[f"- **{t['id']}**: {t['question']}\n  `python -m orch answer {t['id']} \"...\"`" for t in pend]]
        self.rdir.mkdir(parents=True, exist_ok=True)
        (self.rdir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.rdir / "report.md"

    def pause(self):
        path = self.report("waiting for you")
        self.ws.event("waiting", "; ".join(f"{t['id']}: {(t['question'] or '')[:150]}" for t in self.ws.tasks("pending_user")) + f" (report: {path})")
        return "waiting"

    def finish(self, status, why=""):
        self.rmeta("status", status)
        path = self.report(status)
        self.cleanup()
        self.ws.event("run", f"{status}{': ' + why if why else ''} (report: {path})")
        self.notify(f"[{self.ws.project.name}] run {self.run}: {status}")
        return status

    # --- restart ----------------------------------------------------------------------------------------------
    def reconcile(self):
        """After a crash: the exact recorded commit decides integrating tasks; orphans die; running work is retried."""
        for t in self.ws.tasks("integrating"):
            if t["commit_sha"] and git_ok(self.ws.project, "merge-base", "--is-ancestor", t["commit_sha"], self.tip()):
                self.ws.event("reconcile", f"{t['commit_sha'][:10]} is already in the integration branch: finalizing", t["id"])
                self.finalize(t["id"], t["commit_sha"])
            else:
                self.set(t["id"], "verifying", "reconcile: merge not done, verifying again", "integrating")
        verifying = {t["id"] for t in self.ws.tasks("verifying")}
        for a in self.ws.q("SELECT * FROM attempts WHERE run=? AND ended IS NULL", self.run):
            if a["task"] in verifying and a["kind"] == "work":
                continue  # its agent had finished; post_process closes it with the real outcome
            if a["pid"] and a["pid_ctime"] and agents.proc_ctime(a["pid"]) == a["pid_ctime"]:
                agents.kill_tree(a["pid"])  # PID + creation time: never kill a reused PID
            self.end_attempt(a["id"], "crashed", "the engine stopped during this attempt")
        for t in self.ws.tasks("running"):
            self.set(t["id"], "todo", "reconcile: engine restarted", "running",
                     note="The engine restarted during your previous attempt; check the worktree state and continue.")
