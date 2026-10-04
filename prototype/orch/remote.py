"""Remote workers: an agent CLI on another machine (its own install and login) takes attempts; the engine keeps scope, verify
and merge. The engine calls the hidden "remote" profile like any CLI: `python -m orch remote proxy <agent>:<model>` snapshots
the worktree into a git bundle, opens a lease in the workspace DB and waits. A runner (`python -m orch remote run --url ...`,
over an `ssh -R` tunnel to the web UI) claims the lease, rebuilds the tree, runs the real CLI with heartbeats and sends back a
binary patch; the proxy applies it to the worktree and prints agy-style JSON. Leases are authorised by ORCH_REMOTE_TOKEN,
a token separate from the UI's."""
import base64, json, os, re, secrets, socket, sqlite3, sys, tempfile, threading, time, urllib.error, urllib.request
from pathlib import Path

from . import agents
from .core import HOME, Workspace, vault
from .engine import _git, ensure_excluded, git_ok


def _env(name, default):
    return float(os.environ.get(name) or default)


def _files(ws, lid):
    return [ws.dir / "leases" / f"{lid}.{x}" for x in ("bundle", "patch", "index")]


def _raw(cwd, *args, env=None):
    r = _git(cwd, *args, env=env, text=False)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])}: {r.stderr.decode('utf-8', 'replace').strip()[-600:]}")
    return r.stdout


def drop(ws, lid):
    ws.x("DELETE FROM leases WHERE id=?", lid)
    for f in _files(ws, lid):
        f.unlink(missing_ok=True)


def alive(lease):
    return bool(lease["pid"]) and agents.proc_ctime(lease["pid"]) == lease["pid_ctime"]


def sweep(ws):
    """Leases whose proxy died (the engine killed it at a timeout or a cancel: its finally never ran)."""
    for lease in ws.q("SELECT id, pid, pid_ctime FROM leases"):
        if not alive(lease):
            drop(ws, lease["id"])


def snapshot(cwd, bundle, lid):
    """The worktree as it is, uncommitted edits included, as a parentless commit in a bundle; the real index is untouched."""
    index = Path(bundle).with_suffix(".index")
    env = {"GIT_INDEX_FILE": str(index)}
    _raw(cwd, "read-tree", "HEAD", env=env)  # keeps tracked-but-ignored files
    _raw(cwd, "add", "-A", env=env)
    if (Path(cwd) / ".agents" / "skills").is_dir():
        _raw(cwd, "add", "-f", "--", ".agents/skills", env=env)  # installed orch-* skills sit in info/exclude
    tree = _raw(cwd, "write-tree", env=env).decode().strip()
    sha = _raw(cwd, "commit-tree", tree, "-m", f"orch lease {lid}").decode().strip()  # no parent: no history leaves
    ref = f"refs/orch/lease-{lid}"
    _raw(cwd, "update-ref", ref, sha)  # `git bundle create f <sha>` refuses: "Refusing to create empty bundle"
    try:
        _raw(cwd, "bundle", "create", str(bundle), ref)
    finally:
        _raw(cwd, "update-ref", "-d", ref)
        index.unlink(missing_ok=True)
    return sha


# --- engine side: the proxy process the "remote" profile runs inside the task's worktree -----------------------------------
def proxy(spec, mode="rw", schema=None):
    prompt = sys.stdin.buffer.read().decode("utf-8")
    out = {"status": "ERROR", "response": "", "conversation_id": None, "usage": {}, "error": None}
    ws, lid = None, secrets.token_hex(6)
    try:
        if not os.environ.get("ORCH_WS"):
            raise RuntimeError("remote proxy: ORCH_WS is not set (the engine sets it)")
        ws = Workspace(os.environ["ORCH_WS"])
        ws.quiet = True
        agent, _, model = spec.partition(":")
        cat = agents.catalog()
        if agent not in cat or cat[agent].get("remote") or not model:
            raise RuntimeError(f"remote model {spec!r} must be <agent>:<model>, with an agent id from catalog/agents.json")
        sweep(ws)
        (ws.dir / "leases").mkdir(exist_ok=True)
        cwd, (bundle, patch, _) = Path.cwd(), _files(ws, lid)
        base = snapshot(cwd, bundle, lid) if git_ok(cwd, "rev-parse", "--verify", "HEAD") else None
        task = (re.match(r"ORCH-CALL role=\S+ task=(\S+)", prompt) or [None, None])[1]
        stale, wait = _env("ORCH_REMOTE_STALE", 60), _env("ORCH_REMOTE_WAIT", 600)
        ws.x("INSERT INTO leases(id, task, agent, model, prompt, schema, readonly, base, pid, pid_ctime, stale, created) "
             "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", lid, task, agent, model, prompt, schema and Path(schema).stem, int(mode == "ro"),
             base, os.getpid(), agents.proc_ctime(os.getpid()), stale, time.time())
        t0 = time.time()
        while True:
            time.sleep(0.5)
            rows = ws.q("SELECT * FROM leases WHERE id=?", lid)
            if not rows:
                raise RuntimeError("the lease was removed")
            lease = rows[0]
            if lease["status"] == "done":
                break
            if lease["status"] == "open" and time.time() - t0 > wait:
                raise RuntimeError(f"no remote runner took this attempt within {wait:g}s: start one on the other machine with "
                                   "python -m orch remote run --url <orch ui address>")
            if lease["status"] == "claimed" and time.time() - (lease["beat"] or 0) > stale:
                raise RuntimeError(f"remote runner {lease['runner']} stopped responding (no heartbeat for {stale:g}s)")
        res = json.loads(lease["result"])
        if res["ok"] and mode != "ro" and patch.exists() and patch.stat().st_size:
            r = _git(cwd, "apply", "--whitespace=nowarn", str(patch))  # not --index: autocrlf applies as on a local edit
            if r.returncode:
                raise RuntimeError(f"the remote patch does not apply here: {(r.stderr or r.stdout).strip()[-600:]}")
        out.update(status="SUCCESS" if res["ok"] else "ERROR", response=res["text"], conversation_id=res["session"],
                   usage={"input_tokens": res["tokens_in"], "output_tokens": res["tokens_out"]}, error=res["error"])
    except (RuntimeError, OSError, ValueError, KeyError, sqlite3.Error) as e:
        out["error"] = str(e)
    finally:
        if ws:
            drop(ws, lid)
        print(json.dumps(out, ensure_ascii=False))


# --- web UI routes (remote token only) ----------------------------------------------------------------------------------------
def claim(ws, b, q=None):
    sweep(ws)
    have, runner = [str(x) for x in b.get("agents") or []], str(b.get("runner") or "runner")[:64]
    if not have:
        raise ValueError("agents: the agent ids this runner serves")
    with ws.tx():
        rows = ws.q(f"SELECT * FROM leases WHERE status='open' AND agent IN ({','.join('?' * len(have))}) ORDER BY created LIMIT 1", *have)
        if rows:
            ws.x("UPDATE leases SET status='claimed', runner=?, beat=? WHERE id=?", runner, time.time(), rows[0]["id"])
    if not rows:
        return {"lease": None}
    lease = rows[0]
    ws.event("remote", f"{runner} took the attempt ({lease['agent']}/{lease['model']})", lease["task"], "remote")
    bundle = _files(ws, lease["id"])[0]
    return {"lease": {k: lease[k] for k in ("id", "agent", "model", "prompt", "schema", "readonly", "base", "stale")},
            "bundle": base64.b64encode(bundle.read_bytes()).decode() if lease["base"] and bundle.exists() else None}


def beat(ws, b, q=None):
    lid, rows = str(b.get("id")), ws.q("SELECT * FROM leases WHERE id=?", str(b.get("id")))
    if not rows or rows[0]["status"] != "claimed" or rows[0]["runner"] != str(b.get("runner") or "")[:64]:
        return {"cancel": True}
    if not alive(rows[0]):
        drop(ws, lid)
        return {"cancel": True}
    ws.x("UPDATE leases SET beat=? WHERE id=? AND status='claimed'", time.time(), lid)
    return {"cancel": False}


def done(ws, b, q=None):
    lid, runner = str(b.get("id") or ""), str(b.get("runner") or "")[:64]
    if not re.fullmatch(r"[0-9a-f]{12}", lid):
        raise ValueError("bad lease id")
    data = base64.b64decode(b.get("patch") or "", validate=True)
    gone = ValueError("this lease is gone: the engine gave up on it (or stopped)")
    if not ws.q("SELECT 1 FROM leases WHERE id=? AND status='claimed' AND runner=?", lid, runner):
        raise gone
    patch = _files(ws, lid)[1]
    if data:
        patch.write_bytes(data)  # before the status flips: the proxy applies it as soon as it reads "done"
    num = lambda k: int(b.get(k) or 0)
    res = {"ok": bool(b.get("ok")), "text": str(b.get("text") or ""), "session": b.get("session") and str(b["session"]),
           "tokens_in": num("tokens_in"), "tokens_out": num("tokens_out"), "error": b.get("error") and str(b["error"])[:4000]}
    if not ws.x("UPDATE leases SET status='done', result=? WHERE id=? AND status='claimed' AND runner=?", json.dumps(res), lid, runner):
        patch.unlink(missing_ok=True)
        raise gone
    return {"ok": "result recorded"}


# --- the other machine: the runner loop ---------------------------------------------------------------------------------------
def run(url, name=None, have=None, once=False):
    token = os.environ.get("ORCH_REMOTE_TOKEN") or vault().get("ORCH_REMOTE_TOKEN")
    if not token:
        raise SystemExit("set ORCH_REMOTE_TOKEN (environment, or: python -m orch vault set ORCH_REMOTE_TOKEN) to the value the "
                         "engine's machine uses")
    name, cat = (name or socket.gethostname())[:64], agents.catalog()
    if have is None:
        have = [k for k, a in cat.items() if not a.get("hidden") and not a.get("remote") and agents.resolve_bin(a["bin"])]
    if bad := [h for h in have if h not in cat or cat[h].get("remote")]:
        raise SystemExit(f"unknown agent ids {bad}: use ids from catalog/agents.json")
    if not have:
        raise SystemExit("no agent CLI is installed on this machine (python -m orch discover)")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # an http_proxy variable must not see the token

    def post(path, body):
        req = urllib.request.Request(f"{url.rstrip('/')}/api/{path}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "X-Orch-Token": token})
        with opener.open(req, timeout=120) as r:
            return json.loads(r.read())
    print(f"remote runner {name}: serving {', '.join(have)} for {url}", flush=True)
    warned = False
    while True:
        try:
            got = post("lease", {"agents": have, "runner": name})
            warned = False
        except urllib.error.HTTPError as e:
            raise SystemExit(f"the engine's UI refused this runner ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}")
        except OSError as e:
            if not warned:
                print(f"cannot reach {url} ({e}); retrying", flush=True)
                warned = True
            time.sleep(5)
            continue
        if not got.get("lease"):
            time.sleep(2)
            continue
        serve_lease(got, name, post)
        if once:
            return


def serve_lease(got, name, post):
    lease = got["lease"]
    lid, stale = lease["id"], float(lease["stale"] or 60)
    state, finished = {"kill": None, "stop": False}, threading.Event()

    def on_start(pid, ctime, kill):
        state["kill"] = kill
        if state["stop"]:
            kill()

    def stop():
        state["stop"] = True
        if state["kill"]:
            state["kill"]()

    def heartbeat():
        last = time.time()
        while not finished.wait(stale / 6):
            try:
                if post("lease/beat", {"id": lid, "runner": name}).get("cancel"):
                    return stop()  # the engine gave up (timeout, cancel, stop)
                last = time.time()
            except (OSError, ValueError):
                if time.time() - last >= stale:
                    return stop()  # the engine already counts this runner as gone
    threading.Thread(target=heartbeat, daemon=True).start()
    a = agents.catalog()[lease["agent"]]
    prompt = lease["prompt"] + (f"\n\n{a['note']}" if a.get("note") else "")  # the real CLI's quirks, as the engine adds them
    patch, result = b"", {"ok": False, "text": "", "session": None, "tokens_in": 0, "tokens_out": 0, "error": "not run"}
    try:
        with tempfile.TemporaryDirectory(prefix="orch-remote-", ignore_cleanup_errors=True) as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _raw(repo, "init", "-q")
            if got.get("bundle"):
                bundle = Path(tmp) / "base.bundle"
                bundle.write_bytes(base64.b64decode(got["bundle"]))
                _raw(repo, "bundle", "unbundle", str(bundle))
                _raw(repo, "checkout", "-q", "--detach", lease["base"])
            ensure_excluded(repo)
            result = agents.run_agent(lease["agent"], lease["model"], prompt, repo, HOME / "remote" / lid, lease["schema"] or None,
                                      readonly=bool(lease["readonly"]), on_start=on_start, timeout=86400)  # the engine times out
            if result["ok"] and not lease["readonly"] and lease["base"] and not state["stop"]:
                _raw(repo, "add", "-A")
                patch = _raw(repo, "diff", "--cached", "--binary", lease["base"])
    except RuntimeError as e:
        result = {**result, "ok": False, "error": f"remote runner {name}: {e}"}
    finally:
        finished.set()
    if state["stop"]:
        return print(f"lease {lid}: cancelled by the engine", flush=True)
    try:
        post("lease/done", {"id": lid, "runner": name, "patch": base64.b64encode(patch).decode(),
                            **{k: result.get(k) for k in ("ok", "text", "session", "tokens_in", "tokens_out", "error")}})
        print(f"lease {lid} ({lease['agent']}/{lease['model']}): {'ok' if result['ok'] else result['error']}", flush=True)
    except (OSError, ValueError) as e:
        print(f"lease {lid}: the result could not be delivered ({e})", flush=True)
