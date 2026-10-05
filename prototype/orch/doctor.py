"""`orctram doctor`: is this machine (and this project) ready for a run? Local checks only: no network, no agent calls, no
quota spent, no secret printed. Each check is (level, what, detail) with level ok / warn / fail."""
import json, os, shutil, socket, sqlite3, subprocess, sys, tempfile, types
from pathlib import Path

from . import __version__, agents
from .core import HOME, VAULT, WS_MIGRATIONS, EngineLock, vault


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, (r.stdout or r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)


def machine():
    out = [("ok" if sys.version_info >= (3, 11) else "fail", "python", f"{sys.version.split()[0]} ({sys.executable}); orctram {__version__}")]
    code, text = _run(["git", "--version"])
    out.append(("ok", "git", text) if code == 0 else ("fail", "git", f"not found ({text}): install git"))
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        out.append(("ok", "sqlite", f"{sqlite3.sqlite_version} with FTS5"))
    except sqlite3.Error as e:
        out.append(("fail", "sqlite", f"{sqlite3.sqlite_version} without FTS5 ({e}): the knowledge graph needs it"))
    try:
        HOME.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=HOME):
            pass
        out.append(("ok", "data dir", f"{HOME} (ORCH_HOME) is writable"))
    except OSError as e:
        out.append(("fail", "data dir", f"{HOME} is not writable: {e}"))
    # agents run `python -m orch kg search` with PYTHONPATH set to this package: the python on their PATH must be 3.11+
    py = shutil.which("python") or shutil.which("python3")
    code, text = _run([py, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"]) if py else (None, "")
    try:  # the Windows Store stub answers with a message, not a version
        recent = code == 0 and tuple(map(int, text.split("."))) >= (3, 11)
    except ValueError:
        recent = False
    if recent:
        out.append(("ok", "python on PATH", f"{py} ({text}): agents can query the board and the knowledge graph"))
    else:
        out.append(("warn", "python on PATH", f"{py or 'none'} {text}: agents cannot run `python -m orch kg search` (needs 3.11+)"))
    try:
        keys, unreadable = vault(), None  # key names only are used below; values are never printed
    except Exception as e:  # a corrupt file, or DPAPI refusing (another Windows user, a copied disk)
        keys, unreadable = {}, e
    if unreadable:
        out.append(("fail", "vault", f"{VAULT} cannot be read ({type(unreadable).__name__}): move it away and store the keys again"))
    elif VAULT.exists():
        loose = os.name != "nt" and VAULT.stat().st_mode & 0o077
        mode = "" if os.name == "nt" else f", mode {VAULT.stat().st_mode & 0o777:o}"
        out.append(("warn" if loose else "ok", "vault", f"{len(keys)} key(s) in {VAULT}{mode}" + (": run chmod 600" if loose else "")))
    else:
        out.append(("ok", "vault", "empty (python -m orch vault set NAME stores an API key)"))
    found = []
    for aid, a in agents.catalog().items():
        if a.get("hidden"):
            continue
        if not agents.resolve_bin(a["bin"]):
            continue
        files = [f for f in a.get("auth_files", []) if Path(os.path.expanduser(f)).exists()]
        envs = [k for k in a.get("auth_env", []) if os.environ.get(k) or keys.get(k)]
        missing = [k for k in a.get("needs_vault", []) if k not in keys]
        hint = f"missing vault key {', '.join(missing)}" if missing else "credentials present" if files or envs else "login state unknown"
        found.append(aid)
        out.append(("warn" if missing else "ok", f"agent {aid}", f"installed; {hint}"))
    if not found:
        out.append(("warn", "agents", "no agent CLI found on PATH: install codex, claude, agy, opencode ... (python -m orch discover)"))
    with socket.socket() as s:
        free = s.connect_ex(("127.0.0.1", 8765)) != 0
    out.append(("ok", "ui port", "8765 is free") if free else ("warn", "ui port", "8765 is taken: `ui` picks another port"))
    rt = os.environ.get("ORCH_REMOTE_TOKEN") or keys.get("ORCH_REMOTE_TOKEN")
    if rt:
        out.append(("ok", "remote token", "set, 16+ characters") if len(rt) >= 16 else
                   ("warn", "remote token", "shorter than 16 characters: remote runners are refused"))
    return out


def project(path):
    """The project's git state, team and workspace database; nothing is created when there is none yet."""
    from .engine import git_ok, validate_team  # engine imports this package's heavier modules
    p, out = Path(path).resolve(), []
    if not git_ok(p, "rev-parse", "--verify", "HEAD"):
        return [("fail", "project", f"{p} is not a git repository with a commit (python -m orch init can create one)")]
    code, text = _run(["git", "-C", str(p), "status", "--porcelain"])
    dirty = [ln for ln in text.splitlines() if ".orch" not in ln] if code == 0 else []
    out.append(("warn", "project", f"{p}: {len(dirty)} uncommitted change(s), agents start from HEAD") if dirty else ("ok", "project", f"{p}"))
    team_file = p / ".orch" / "team.json"
    if not team_file.exists():
        return out + [("warn", "team", "no .orch/team.json yet: python -m orch init")]
    try:
        team = validate_team(json.loads(team_file.read_text(encoding="utf-8")))
    except (ValueError, json.JSONDecodeError) as e:
        return out + [("fail", "team", f"{team_file}: {e}")]
    cat, problems = agents.catalog(), []
    for name, r in [*((n, team.get(n)) for n in ("lead", "reviewer", "skill_architect")), *team["workers"].items()]:
        a = cat[r["agent"]]
        if a.get("remote"):
            continue  # runs on another machine
        if not agents.resolve_bin(a["bin"]):
            problems.append(f"{name} uses {r['agent']}, which is not installed here")
    out.append(("fail", "team", "; ".join(problems)) if problems else
               ("ok", "team", f"lead {team['lead']['agent']}, reviewer {team['reviewer']['agent']}, {len(team['workers'])} worker(s)"))
    if any(w.get("agent") == "remote" for w in team["workers"].values()):
        try:
            rt = os.environ.get("ORCH_REMOTE_TOKEN") or vault().get("ORCH_REMOTE_TOKEN") or ""
        except Exception:
            rt = os.environ.get("ORCH_REMOTE_TOKEN") or ""
        out.append(("ok", "remote workers", "ORCH_REMOTE_TOKEN set") if len(rt) >= 16 else
                   ("fail", "remote workers", "the team has remote workers but ORCH_REMOTE_TOKEN is missing or shorter than 16 characters"))
    db = p / ".orch" / "orch.db"
    if db.exists():
        con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
        try:
            v, latest = con.execute("PRAGMA user_version").fetchone()[0], max([1, *(m for m, _ in WS_MIGRATIONS)])
        finally:
            con.close()
        out.append(("fail", "workspace db", f"schema {v} is newer than this orctram ({latest}): upgrade") if v > latest else
                   ("ok", "workspace db", f"schema {v}" + (f", upgraded to {latest} on next use" if v < latest else "")))
        lock = p / ".orch" / "engine.lock"
        out.append(("ok", "engine", "running on this workspace" if lock.exists() and _locked(lock) else "not running"))
    return out


def _locked(path):
    lock = EngineLock(types.SimpleNamespace(dir=path.parent))  # EngineLock only needs the workspace's .orch dir
    if lock.acquire():
        lock.release()
        return False
    return True


def report(project_path=None):
    """-> (text, exit code): 1 when any check fails."""
    checks = machine() + (project(project_path) if project_path else [])
    mark = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}
    lines = [f"[{mark[lvl]}] {what:<16} {detail}" for lvl, what, detail in checks]
    fails, warns = sum(c[0] == "fail" for c in checks), sum(c[0] == "warn" for c in checks)
    lines.append(f"\n{fails} problem(s), {warns} warning(s)." + ("" if fails else " Ready."))
    return "\n".join(lines), 1 if fails else 0
