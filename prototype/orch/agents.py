"""Agent CLIs: discovery, entitlement probes, headless runs in kill-on-close process trees, output parsing, login, quota."""
import datetime, json, os, re, shutil, signal, subprocess, sys, time, urllib.request
from pathlib import Path

from .core import CATALOG, HOME, ROOT, SCHEMAS, SECRET_NAME, SECRET_VALUE, vault

RESOURCES = HOME / "resources.json"
OVERRIDES = HOME / "agents.json"  # this machine's changes (a router's port, its own profiles); the repo catalog stays untouched


def catalog():
    raw = json.loads((CATALOG / "agents.json").read_text(encoding="utf-8"))
    for k, a in (json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}).items():
        if k != "_doc":
            raw[k] = {**raw.get(k, {}), **a}
    raw.pop("_doc", None)
    for k, a in raw.items():  # profiles inherit from their base adapter
        if "base" in a:
            raw[k] = {**raw[a["base"]], **a}
    return raw


def account(aid, model=None):
    """The quota a call spends. An agent id is one login; a router holds one account per provider prefix of its model ids
    (cx/, ag/ ...), and "shares" maps the prefixes that are also a CLI's subscription: those run out together with the CLI.
    A profile with "quota": "model" runs out per model."""
    a = catalog().get(aid) or {}
    if a.get("quota") == "model" and model:  # agy: claude-opus out for the week while gemini still runs (seen 2026-10-06)
        return f"{aid}/{model}"
    if a.get("remote"):  # model = "<agent>:<model>". ponytail: every runner of one CLI counts as one account; name runners if not
        return f"{aid}/{(model or '').split(':', 1)[0]}"
    if not a.get("router") or "/" not in (model or ""):
        return aid
    pre = model.split("/", 1)[0]
    return a.get("shares", {}).get(pre) or f"{aid}/{pre}"


def resolve_bin(name):
    """Launch npm shims' real target directly: passing prompts through cmd.exe (.cmd) is an injection risk."""
    if name == "python":
        return [sys.executable]
    p = shutil.which(name)
    if not p and os.name == "nt" and name == "agy":
        p = shutil.which("agy", path=str(Path.home() / "AppData/Local/agy/bin"))
    if not p:
        return None
    if p.lower().endswith((".cmd", ".bat")):
        m = re.search(r'"%dp0%\\([^"]+\.(exe|js))"', Path(p).read_text(errors="ignore"))
        target = m and Path(p).parent / m.group(1)
        if target and target.exists():
            return [str(target)] if m.group(2) == "exe" else [shutil.which("node") or "node", str(target)]
    return [p]


def _quick(cmd, timeout=60, env=None):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace", env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"ERR {e}"


def list_models(a, exe):
    if a.get("models_from") == "router":  # the router's own catalog; empty while it is not running
        try:
            req = urllib.request.Request(a["router"].rstrip("/") + "/models",
                                         headers={"Authorization": f"Bearer {worker_env(a).get('ROUTER_API_KEY', '')}"})
            return [m["id"] for m in json.loads(urllib.request.urlopen(req, timeout=5).read())["data"]]
        except (OSError, ValueError, KeyError, TypeError):
            return []
    if a.get("models_from") == "codex_cache":
        f = Path.home() / ".codex" / "models_cache.json"
        if f.exists():
            ms = json.loads(f.read_text(encoding="utf-8")).get("models", [])
            return [m["slug"] for m in ms if m.get("visibility") == "list"]
    if a.get("models_cmd") and exe:
        out = _quick(exe + a["models_cmd"], 90, worker_env(a))  # the adapter's env: profiles may point at their own data dir
        return [ln.split()[0] for ln in out.splitlines()
                if not ln.startswith(("Fetching", "ERR", " ", "\t")) and re.match(r"^[\w./:-]+(\s|$)", ln)]
    return list(a.get("models", []))


def discover(probe=False, only=None):
    """Inventory of agents. Auth is a *hint* (file/env presence); only a probe proves entitlement.
    Broken or unauthenticated adapters stay listed with their failure reason."""
    res, v = load_resources(), vault()
    for aid, a in catalog().items():
        if a.get("hidden") or (only and aid not in only):
            continue
        exe = resolve_bin(a["bin"])
        info = {"name": a["name"], "installed": bool(exe), "verified": a.get("verified", False),
                "install": a.get("install"), "login": bool(a.get("login")) or "login_hint" in a,
                "login_hint": a.get("login_hint"), "probe": (res.get(aid) or {}).get("probe")}
        if exe:
            lines = _quick(exe + ["--version"], 30).strip().splitlines()
            info["version"] = lines[-1][:80] if lines else "?"
            files = [f for f in a.get("auth_files", []) if Path(os.path.expanduser(f)).exists()]
            envs = [k for k in a.get("auth_env", []) if os.environ.get(k) or v.get(k)]
            missing = [k for k in a.get("needs_vault", []) if k not in v]
            info["auth"] = "missing vault: " + ",".join(missing) if missing else ("ok?" if files or envs else "unknown")
            info["models"] = list_models(a, exe)
            if probe and info["models"] and not missing:
                info["probe"] = probe_agent(aid, a.get("probe_model") or info["models"][-1])
        res[aid] = info
    HOME.mkdir(parents=True, exist_ok=True)
    RESOURCES.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    return res


def load_resources():
    return json.loads(RESOURCES.read_text(encoding="utf-8")) if RESOURCES.exists() else {}


def candidates(found=None):
    """(agent, model) pairs usable here: installed, credentials present, not failing an auth probe.
    found: discovery results to use (the UI passes the saved ones so a page view never launches agent CLIs)."""
    out = []
    for aid, i in (found if found is not None else load_resources() or discover()).items():
        if i.get("installed") and not str(i.get("auth")).startswith("missing") and (i.get("probe") or {}).get("class") != "auth":
            out += [(aid, m) for m in i.get("models", [])]
    return out


def probe_agent(aid, model):
    tmp = HOME / "probe" / aid
    tmp.mkdir(parents=True, exist_ok=True)
    r = run_agent(aid, model, "Reply with exactly the word OK and nothing else.", cwd=tmp, out_dir=tmp, timeout=180, readonly=True)
    ok = r["ok"] and "OK" in r["text"]
    return {"ok": ok, "model": model, "ts": time.strftime("%Y-%m-%d %H:%M"), "class": None if ok else r["failure"] or "error",
            "error": None if ok else (r["error"] or r["text"])[:300], "tokens_in": r["tokens_in"]}


# --- environments ----------------------------------------------------------------------------------
# what verify commands (repo code, written by workers) may see: system, locale, temp dirs and language toolchains; team.json
# "verify_env" adds more names. Secret-looking names and values are dropped even when listed.
VERIFY_ENV = re.compile(r"^(PATH|PATHEXT|SYSTEMROOT|SYSTEMDRIVE|WINDIR|COMSPEC|OS|TEMP|TMP|TMPDIR|HOME|HOMEDRIVE|HOMEPATH|USERPROFILE|"
                        r"APPDATA|LOCALAPPDATA|PROGRAMDATA|PROGRAMFILES.*|COMMONPROGRAMFILES.*|PROCESSOR_\w+|NUMBER_OF_PROCESSORS|"
                        r"USER|USERNAME|LOGNAME|SHELL|TERM|LANG|LANGUAGE|LC_\w+|TZ|XDG_\w+|CI|PYTHON\w*|VIRTUAL_ENV|CONDA_\w+|"
                        r"PYENV\w*|UV_\w+|PIP_\w+|JAVA_HOME|GOPATH|GOROOT|GOBIN|GOCACHE|GOMODCACHE|GOFLAGS|CARGO_HOME|RUSTUP_\w+|"
                        r"NODE_\w+|NVM_\w+|PNPM_HOME|BUN_INSTALL|DENO_\w+|DOTNET_\w+|GIT_EXEC_PATH)$", re.I)


def clean_env(extra=None, keep=None):
    """Everything except secret-looking names and values (agents need their own configuration); keep(name) narrows it."""
    env = {k: val for k, val in os.environ.items()
           if (keep is None or keep(k)) and not SECRET_NAME.search(k) and not SECRET_VALUE.search(val)}
    # no bytecode / pytest cache: build junk in a worktree would be committed or flagged as out-of-scope
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTEST_ADDOPTS="-p no:cacheprovider")
    env.update(extra or {})
    return env


def verify_env(more=()):
    """The environment of verify commands and pre-test checks: an allowlist, not "everything but secrets", since they run code
    the workers wrote (SSH_AUTH_SOCK, cloud profiles or a DATABASE_URL must not reach it). more = team.json "verify_env"."""
    more = {str(n).upper() for n in more or ()}
    return clean_env(keep=lambda k: bool(VERIFY_ENV.match(k)) or k.upper() in more)


def worker_env(a, extra=None):
    """Least exposure: clean_env, then add back only the credentials this adapter declares."""
    v = vault()
    env = clean_env()
    for k in a.get("auth_env", []):
        if os.environ.get(k) or v.get(k):
            env[k] = os.environ.get(k) or v[k]
    for k in a.get("unset_env", []):
        env.pop(k, None)
    for k, val in a.get("env", {}).items():
        env[k] = re.sub(r"\{vault:(\w+)\}", lambda m: v.get(m.group(1), ""), val).replace("{home}", str(HOME))
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.update(extra or {})
    return env


# --- processes: one Windows Job Object per attempt (kill-on-close), a process group elsewhere -------
if os.name == "nt":
    import ctypes
    from ctypes import wintypes
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
    _k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]

    class _Limits(ctypes.Structure):  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION, basic part flattened
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
                    ("IoInfo", ctypes.c_uint64 * 6), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    def _job(proc):
        """Children die with the job: on timeout, on cancel, and when the engine itself crashes."""
        job = _k32.CreateJobObjectW(None, None)
        lim = _Limits(LimitFlags=0x2000)  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if job and _k32.SetInformationJobObject(job, 9, ctypes.byref(lim), ctypes.sizeof(lim)) \
                and _k32.AssignProcessToJobObject(job, int(proc._handle)):
            return job
        if job:
            _k32.CloseHandle(job)
        return None

    def proc_ctime(pid):
        """Creation time identifies a process; a PID alone gets reused."""
        h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            t, code = (ctypes.c_uint64 * 4)(), wintypes.DWORD()
            if not _k32.GetProcessTimes(h, *(ctypes.byref(t, 8 * i) for i in range(4))):
                return None
            _k32.GetExitCodeProcess(h, ctypes.byref(code))
            return str(t[0]) if code.value == 259 else None  # STILL_ACTIVE
        finally:
            _k32.CloseHandle(h)
else:
    def _job(proc):
        return None

    def proc_ctime(pid):
        r = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True)
        return r.stdout.strip() or None


def kill_tree(pid, job=None):
    try:
        if job:
            _k32.TerminateJobObject(job, 1)
        elif os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def spawn(cmd, cwd, env, stdin=None, out=None, err=None, timeout=None, on_start=None):
    """Run to completion inside its own job / process group. Returns the exit code, or None on timeout.
    Leftover background processes (dev servers...) are killed when it returns."""
    env = {**env, "PWD": str(Path(cwd).resolve())}  # opencode takes its project dir from PWD: the shell's would aim edits outside the worktree
    with open(out, "wb") as so, open(err, "wb") as se:
        p = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=so, stderr=se,
                             stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                             start_new_session=os.name != "nt", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        job = _job(p)
        try:
            if on_start:
                on_start(p.pid, proc_ctime(p.pid), lambda: kill_tree(p.pid, job))
            p.communicate(stdin, timeout=timeout)
            return p.returncode
        except subprocess.TimeoutExpired:
            kill_tree(p.pid, job)
            p.wait()
            return None
        finally:
            if job:
                _k32.CloseHandle(job)
            elif os.name != "nt":
                kill_tree(p.pid)


# --- headless agent runs -----------------------------------------------------------------------------
ARG_LIMIT = 24000  # escaped length; longer prompts go through a file (Windows command lines top out at 32767 chars)


def supports_readonly(aid):
    return "ro" in catalog()[aid].get("mode", {})


def mcp_server(project):
    """How an agent CLI starts this workspace's MCP server (orch/mcp.py). The env is explicit: CLIs give MCP servers a minimal one
    (no home directory to derive ~/.orchestra from, on Windows)."""
    return {"command": sys.executable, "args": ["-m", "orch", "--ws", str(project), "mcp"],
            "env": {"PYTHONPATH": str(ROOT), "ORCH_HOME": str(HOME)}}


def toml(v):
    """JSON strings and arrays are valid TOML; objects become inline tables (codex -c key=value parses the value as TOML)."""
    if isinstance(v, dict):
        return "{" + ", ".join(f"{json.dumps(k)} = {toml(x)}" for k, x in v.items()) + "}"
    return json.dumps(v, ensure_ascii=False)


def run_agent(aid, model, prompt, cwd, out_dir, schema=None, session=None, timeout=1800, readonly=False, on_start=None, env=None,
              mcp=None):
    """schema = contract name in catalog/schemas. readonly = plan/read-only mode (lead, reviewer, probes).
    mcp = a project: the agent gets that workspace's MCP server through its CLI's per-call config (catalog "mcp": extra args
    with {mcp_json}/{mcp_toml}, or "config" = opencode's OPENCODE_CONFIG_CONTENT). Nothing global is written."""
    a = catalog()[aid]
    srv = mcp_server(mcp) if mcp and a.get("mcp") else None
    exe = resolve_bin(a["bin"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.md").write_text(prompt, encoding="utf-8", newline="\n")
    result = {"ok": False, "text": "", "session": session, "tokens_in": 0, "tokens_out": 0, "cost": None,
              "error": None, "failure": None, "seconds": 0}
    if not exe:
        result.update(error=f"{a['bin']} not installed", failure="missing")
        return result
    if a["prompt"] == "arg" and len(subprocess.list2cmdline([prompt])) > ARG_LIMIT:
        pf = Path(cwd) / ".orch" / f"prompt-{abs(hash(str(out_dir))) % 10 ** 8}.md"  # inside cwd: sandboxes allow reading it
        pf.parent.mkdir(exist_ok=True)
        pf.write_text(prompt, encoding="utf-8", newline="\n")
        prompt = f"Your complete task packet is in the file {pf} . Read all of it first, then do exactly what it says."
    sch = SCHEMAS / f"{schema}.json" if schema else None
    fill = {"model": model, "session": session or "", "out": str(out_dir / "last.txt"), "prompt": prompt,
            "mode": a.get("mode", {}).get("ro" if readonly else "rw", ""),
            "schema": str(sch or ""), "schema_json": json.dumps(json.loads(sch.read_text())) if sch else "",
            "mcp_json": json.dumps({"mcpServers": {"orch": srv}}) if srv else "", "mcp_toml": toml(srv) if srv else "",
            "mcp_tools": ",mcp__orch" if srv else ""}
    args = a["resume"] if session and a.get("resume") else a["run"]
    args = a["mcp"] + args if srv and isinstance(a["mcp"], list) else args
    if not sch:  # drop "--flag {schema}" pairs when the call has no contract
        args = [x for i, x in enumerate(args) if "{schema" not in x and not (i + 1 < len(args) and "{schema" in args[i + 1])]
    cmd = exe + [re.sub(r"\{(\w+)\}", lambda m: fill.get(m.group(1), m.group(0)), x) for x in args]
    (out_dir / "last.txt").unlink(missing_ok=True)
    cfg = router_config(a, model) if a.get("router") else {}
    if srv and a["mcp"] == "config":
        cfg["mcp"] = {"orch": {"type": "local", "command": [srv["command"], *srv["args"]], "environment": srv["env"]}}
    if cfg:
        env = {**(env or {}), "OPENCODE_CONFIG_CONTENT": json.dumps(cfg)}
    t0 = time.time()
    try:
        code = spawn(cmd, cwd, worker_env(a, env), prompt.encode("utf-8") if a["prompt"] == "stdin" else None,
                     out_dir / "stdout.txt", out_dir / "stderr.txt", timeout, on_start)
    except OSError as e:
        result.update(error=str(e), failure="missing")
        return result
    result["seconds"] = round(time.time() - t0, 1)
    if code is None:
        result.update(error=f"timeout after {timeout}s", failure="timeout")
        return result
    stdout = (out_dir / "stdout.txt").read_text(encoding="utf-8", errors="replace")
    stderr = (out_dir / "stderr.txt").read_text(encoding="utf-8", errors="replace")
    unparsed = False
    try:
        result.update({k: v for k, v in PARSERS[a["parse"]](stdout, out_dir / "last.txt").items() if v is not None or k == "error"})
    except (ValueError, KeyError, TypeError) as e:
        result["error"], unparsed = f"unparseable output ({e}): {(stdout or stderr)[-400:]}", True
    result["ok"] = code == 0 and not result["error"]
    if not result["ok"]:
        # classify the CLI's own error and its stderr, never the stdout transcript: it quotes the project ("/login" routes,
        # "line 429", quota.py), which must not cool an account or ask the user to log in
        why = None if unparsed else result["error"]
        result["error"] = result["error"] or (stderr or stdout)[-600:] or f"exit code {code}"
        result["failure"] = classify(why, stderr[-2000:])
    return result


def router_config(a, model):
    """opencode merges OPENCODE_CONFIG_CONTENT into its config: one OpenAI-compatible provider "router" at the local endpoint
    (9router, LiteLLM, one-api ...). The key comes from the vault through the profile's env, never from this JSON."""
    return {"provider": {"router": {
        "npm": "@ai-sdk/openai-compatible", "name": a["name"], "models": {model: {"name": model}},
        "options": {"baseURL": a["router"], "apiKey": "{env:ROUTER_API_KEY}", "headers": a.get("router_headers", {})}}}}


FAILURES = [  # first match wins: a usage-limit message that links a billing or login page is still "quota"
    # status codes only next to an HTTP word: a bare 429 / 401 is as likely a line number or a test name
    ("quota", r"usage limit|hit your (usage )?limit|(5-hour|weekly|daily|monthly) limit|quota.{0,20}(exceeded|exhausted|reached)|"
              r"exceeded.{0,40}quota|insufficient.?quota|resource.?exhausted|out of credits|more credits|credit balance|"
              r"insufficient.?(credit|balance|funds)"),
    ("rate_limit", r"rate.?limit|(status|code|error|http)\W{0,3}429\b|\b429\W{0,3}(too|rate)|too many requests|overloaded"),
    # a passing hiccup of the service, not of the account: the same call again in a moment (agy: "UNAVAILABLE (code 503)",
    # "Malformed function call ... Retries remaining: 3")
    ("transient", r"(status|code|error|http)\W{0,3}(500|502|503|504)\b|service.{0,20}unavailable|temporarily unavailable|"
                  r"malformed function call|retries remaining|bad gateway|gateway time-?out|internal server error|"
                  r"eligibility check failed|dial tcp|no such host|i/o timeout"),  # agy's network precheck: "dial tcp: lookup ..."
    ("auth", r"not logged in|unauthori[sz]ed|(status|code|error|http)\W{0,3}401\b|(run|use|type) /login|login required|"
             r"please log ?in|invalid[ _-]?api[ _-]?key|authentication[ _-](failed|required|error)|failed to authenticate"),
    ("model", r"model.{0,40}not supported|not supported.{0,40}model|unknown model|model .{0,30}not found|invalid model"),
]


def classify(*texts):
    """The first text with a known kind wins: the parsed error before stderr, where codex logs unrelated background 401s."""
    for text in texts:
        t = (text or "").lower()
        for kind, pat in FAILURES:
            if re.search(pat, t):
                return kind
    return "error"


def reset_at(text, now=None):
    """When a usage limit lifts, from the CLI's own message; None when it names no time. Formats seen:
    codex "try again at Oct 4th, 2026 8:58 AM", relative "retry in 51.2s" / "resets in 2h 13m" / agy "Resets in 47m5s", claude "...|1759550400"."""
    t, now = text or "", time.time() if now is None else now
    m = re.search(r"\b([A-Z][a-z]{2})[a-z]*\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4}),? (\d{1,2}:\d{2}) ?([AP]M)", t)
    if m:
        try:
            return time.mktime(time.strptime(" ".join(m.groups()), "%b %d %Y %I:%M %p"))  # local time, as the CLI prints it
        except ValueError:
            pass
    m = re.search(r"\b(?:in|after) ((?:\d+(?:\.\d+)? ?(?:hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)(?:\b|(?=\d)) ?)+)", t, re.I)  # agy: "154h23m44s"
    if m:
        return now + sum(float(n) * {"h": 3600, "m": 60, "s": 1}[u[0].lower()] for n, u in re.findall(r"(\d+(?:\.\d+)?) ?([a-z]+)", m.group(1), re.I))
    m = re.search(r"\|(\d{10})\b", t)
    return float(m.group(1)) if m else None


def usage(aid, now=None):
    """Quota windows of an account, or None when its CLI keeps no record (agy, opencode, routers: learned from errors).
    codex: the rate_limits snapshots in its session rollouts; only that object is read, never conversation content.
    -> [{"minutes": 300, "used": 42.0 (%), "resets": epoch or None (rolled over), "burn": %/hour or None}]"""
    a = catalog().get(aid) or {}  # aid may be a router's provider account (opencode@9router/if): no record
    if a.get("usage") != "codex_rollouts":
        return None
    now = time.time() if now is None else now
    root = Path(worker_env(a).get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
    files = sorted(root.glob("*/*/*/rollout-*.jsonl"), key=lambda p: p.stat().st_mtime)[-6:]  # parallel sessions, one account
    seen = {}  # window minutes -> [(ts, used, resets)]
    for f in files:
        with open(f, "rb") as fh:
            fh.seek(max(0, f.stat().st_size - 262144))
            lines = fh.read().decode("utf-8", "replace").splitlines()
        for ln in lines:
            if '"rate_limits"' not in ln:
                continue
            try:
                d = json.loads(ln)
                ts = datetime.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).timestamp()
                for w in (d["payload"]["rate_limits"].get("primary"), d["payload"]["rate_limits"].get("secondary")):
                    if w and w.get("resets_at"):
                        seen.setdefault(int(w["window_minutes"]), []).append((ts, float(w["used_percent"]), float(w["resets_at"])))
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
    out = []
    for mins, xs in sorted(seen.items()):
        ts, used, resets = max(xs)
        if resets <= now:  # the window rolled over after the last snapshot
            out.append({"minutes": mins, "used": 0.0, "resets": None, "burn": None})
            continue
        first = min(x for x in xs if x[2] == resets and x[0] >= ts - 3600)
        span = (ts - first[0]) / 3600  # ponytail: pace = the last hour of activity; idle gaps make it look slower
        out.append({"minutes": mins, "used": used, "resets": resets, "burn": (used - first[1]) / span if span >= 0.05 else None})
    return out or None


def usage_reset(aid):
    """When an exhausted account comes back, from its quota record; None when unknown or not exhausted."""
    ends = [w["resets"] for w in usage(aid) or [] if w["used"] >= 100 and w["resets"]]
    return max(ends) if ends else None


# --- parsers: stdout -> {text, session, tokens_in, tokens_out, cost, error} ------------------------------
def _claude(out, _):
    d = json.loads(out)
    u = d.get("usage") or {}
    so = d.get("structured_output")  # present when --json-schema is used (unverified on this machine: CLI not logged in)
    return {"text": json.dumps(so) if so is not None else d.get("result") or "", "session": d.get("session_id"),
            "cost": d.get("total_cost_usd"), "tokens_out": u.get("output_tokens") or 0,
            "tokens_in": sum(u.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
            "error": (d.get("result") or "error") if d.get("is_error") else None}


def _codex(out, last):
    ev = [json.loads(ln) for ln in out.splitlines() if ln.startswith("{")]
    text = last.read_text(encoding="utf-8", errors="replace") if last.exists() else ""
    if not text:
        msgs = [e["item"].get("text", "") for e in ev if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"]
        text = msgs[-1] if msgs else ""
    use = [e.get("usage") or {} for e in ev if e.get("type") == "turn.completed"]
    err = next((e.get("message") or (e.get("error") or {}).get("message") for e in ev if e.get("type") in ("error", "turn.failed")), None)
    return {"text": text, "session": next((e["thread_id"] for e in ev if e.get("type") == "thread.started"), None),
            "tokens_in": sum(u.get("input_tokens", 0) for u in use), "tokens_out": sum(u.get("output_tokens", 0) for u in use),
            "error": err if not use else None}


def _agy(out, _):
    d = json.loads(out)
    u = d.get("usage") or {}
    so = d.get("structured_output")  # the schema-clean object; "response" may add toolAction/toolSummary or repeat it
    return {"text": json.dumps(so, ensure_ascii=False) if isinstance(so, dict) else d.get("response") or "",
            "session": d.get("conversation_id"), "tokens_in": u.get("input_tokens", 0),
            "tokens_out": (u.get("output_tokens") or 0) + (u.get("thinking_tokens") or 0),
            "error": None if d.get("status") == "SUCCESS" else f"status {d.get('status')}: {d.get('error') or d.get('response')}"}


def _gemini(out, _):
    d = json.loads(out)
    return {"text": d.get("response") or "", "error": (d.get("error") or {}).get("message") if d.get("error") else None}


def _opencode(out, _):
    """opencode --format json events (verified with 1.18.34): text parts, step_finish tokens/cost, error events."""
    texts, tin, tout, cost, sess, err = [], 0, 0, 0.0, None, None
    for ln in out.splitlines():
        if not ln.startswith("{"):
            continue
        e = json.loads(ln)
        part = e.get("part") or {}
        sess = sess or e.get("sessionID") or part.get("sessionID")
        if e.get("type") == "text" and part.get("text"):
            texts.append((part.get("messageID"), part["text"]))
        if e.get("type") == "error":
            err = ((e.get("error") or {}).get("data") or {}).get("message") or json.dumps(e.get("error"))[:500]
        tok, cache = part.get("tokens") or {}, (part.get("tokens") or {}).get("cache") or {}
        tin += (tok.get("input") or 0) + (cache.get("read") or 0) + (cache.get("write") or 0)
        tout += (tok.get("output") or 0) + (tok.get("reasoning") or 0)
        cost += part.get("cost") or 0
    last = texts[-1][0] if texts else None  # the answer is the last message; earlier ones are narration between tool calls
    text = "\n".join(t for m, t in texts if m == last)
    return {"text": text, "session": sess, "tokens_in": tin, "tokens_out": tout, "cost": cost,
            "error": err or (None if text else "no text events")}


PARSERS = {"claude": _claude, "codex": _codex, "agy": _agy, "gemini": _gemini, "opencode": _opencode}


def launch_login(aid):
    """Open the CLI's own login flow in a new console: Orctram never sees passwords."""
    a = catalog()[aid]
    if a.get("login", []) is None:  # nothing to launch: free tier, or a router whose providers log in on its dashboard
        return a.get("login_hint") or f"{aid} needs no login"
    exe = resolve_bin(a["bin"])
    if not exe:
        raise RuntimeError(f"{a['bin']} is not installed" + (f" ({a['install']})" if a.get("install") else ""))
    cmd = exe + a.get("login", [])
    if os.name == "nt":
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE, env=worker_env(a))
    elif sys.platform == "darwin":
        subprocess.Popen(["osascript", "-e", f'tell app "Terminal" to do script "{" ".join(cmd)}"'])
    else:
        subprocess.Popen(["x-terminal-emulator", "-e"] + cmd)
    return a.get("login_hint") or "complete the login in the new window"
