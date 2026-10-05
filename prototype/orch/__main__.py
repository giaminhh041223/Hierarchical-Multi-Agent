"""CLI: python -m orch <command>. Workspace = --ws, else $ORCH_WS (set for agents), else the current directory."""
import argparse, getpass, json, os, sqlite3, sys, time
from pathlib import Path

from . import __version__, agents, mcp, models, pool
from .core import TERMINAL, EngineLock, Workspace, mask, vault, vault_set
from .engine import Engine, ensure_excluded, git, git_ok, load_team, new_run, save_team


def ws_of(a, readonly=False):
    return Workspace(a.ws or os.environ.get("ORCH_WS") or os.getcwd(), readonly)


def confirm(q, default=False):
    x = input(q).strip().lower()
    return default if not x else x in ("y", "yes", "c", "có")


def cmd_discover(a):
    for aid, i in agents.discover(a.probe, a.only.split(",") if a.only else None).items():
        if not i["installed"]:
            print(f"- {aid:<12} not installed" + (f" ({i['install']})" if i.get("install") else ""))
            continue
        p = i.get("probe") or {}
        probe = "" if not p else f"  probe {p['model']}: " + ("ok" if p["ok"] else f"FAILED {p['class']}: {(p['error'] or '')[:100]}")
        ms = i.get("models", [])
        print(f"- {aid:<12} {i.get('version', '?')[:32]:<32} auth={i['auth']}{probe}\n    models: {', '.join(ms[:14])}{' ...' if len(ms) > 14 else ''}")


def cmd_models(a):
    if a.action == "refresh":
        db = models.refresh()
        print(f"{len(db['models'])} models from public sources, as of {db['as_of']} -> {models.DB_FILE}")
    elif a.action == "show":
        for m in a.ids or sorted({m for _, m in agents.candidates()}):
            print(f"{m:<30} {models.card(m)}")
    else:
        print(json.dumps(models.suggest(agents.candidates()), indent=1))


def cmd_login(a):
    print(agents.launch_login(a.agent))


def cmd_vault(a):
    if a.action == "set":
        vault_set(a.name, getpass.getpass(f"{a.name} (input hidden): "))
    elif a.action == "rm":
        vault_set(a.name, None)
    for k, v in vault().items():
        print(f"{k} = {mask(v)}")


def pick_team(a):
    cands = agents.candidates()
    if not cands:
        raise SystemExit("no usable agent: install / log in to one (python -m orch discover), or write .orch/team.json by hand")
    s, name = models.suggest(cands), lambda c: f"{c[0]}/{c[1]}"
    for i, (aid, m) in enumerate(cands, 1):
        print(f"{i:>3}. {aid + '/' + m:<36} {models.card(m)}")
    print(f"\nSuggested: lead={name(s['lead'])}  reviewer={name(s['reviewer'])}  skill_architect={name(s['skill_architect'])}\n"
          f"           workers={', '.join(map(name, s['workers']))}")
    if not a.yes and not confirm("Use this team? [Y/n] ", True):
        for r in ("lead", "reviewer", "skill_architect"):
            x = input(f"{r} [number, Enter = {name(s[r])}]: ").strip()
            s[r] = cands[int(x) - 1] if x else s[r]
        x = input("workers [numbers separated by commas, Enter = suggested]: ").strip()
        s["workers"] = [cands[int(i) - 1] for i in x.split(",")] if x else s["workers"]
    if not a.no_probe:  # model lists overstate entitlement (e.g. a ChatGPT plan cannot use every listed codex model)
        bad = []
        for c in dict.fromkeys([s["lead"], s["reviewer"], s["skill_architect"], *s["workers"]]):
            r = agents.probe_agent(*c)
            print(f"probe {name(c)}: " + ("ok" if r["ok"] else f"{r['class']}: {(r['error'] or '')[:120]}"))
            bad += [] if r["ok"] else [c]
        if bad:
            raise SystemExit("replace or fix the failing models, then run init again (or pass --no-probe)")
    return models.team_of(s)


def cmd_init(a):
    ws = ws_of(a)
    p = ws.project
    if not git_ok(p, "rev-parse", "--verify", "HEAD"):
        if not (a.yes or confirm(f"{p} has no git commit. Run git init and commit the current files? [y/N] ")):
            raise SystemExit("orctram needs a git repository with at least one commit")
        if not git_ok(p, "rev-parse", "--git-dir"):
            git(p, "init", "-q")
        ensure_excluded(p)
        git(p, "add", "-A")
        git(p, "commit", "-q", "--allow-empty", "-m", "initial commit")
    ensure_excluded(p)
    save_team(ws, json.loads(Path(a.team).read_text(encoding="utf-8")) if a.team else pick_team(a))
    print(f"team -> {ws.dir / 'team.json'}\nrules -> {ws.dir / 'rules'} (one file per role and per worker: edit freely)\n"
          "backup pool (who stands in when an account runs out): python -m orch pool plan")


def done(status, ws):
    print(f"\nrun {ws.run}: {status}" + ("\n  python -m orch inbox, then: python -m orch answer <task> \"...\", then: python -m orch resume"
                                       if status == "waiting" else ""))
    sys.exit({"done": 0, "waiting": 3}.get(status, 1))


def cmd_run(a):
    ws = ws_of(a)
    e = new_run(ws, a.goal, a.yes)
    e.exit_on_wait = a.exit_on_wait
    done(e.loop(), ws)


def cmd_resume(a):
    ws = ws_of(a)
    done(Engine(ws, a.exit_on_wait).loop(), ws)


def cmd_board(a):
    print(ws_of(a, readonly=True).board())


def cmd_status(a):
    cmd_board(a)
    ws = ws_of(a)
    print("engine: " + ("running" if EngineLock(ws).held_elsewhere() else "not running"))
    cmd_inbox(a)


def cmd_inbox(a):
    pend = ws_of(a).tasks("pending_user")
    for t in pend:
        print(f"\n[{t['id']}] {t['question']}\n  -> python -m orch answer {t['id']} \"...\"")
    if not pend:
        print("nothing is waiting for you")


def cmd_answer(a):
    ws = ws_of(a)
    if not ws.update(a.task, _expect="pending_user", answer=a.text):
        raise SystemExit(f"{a.task} is not waiting for an answer (see: python -m orch inbox)")
    print("recorded." + ("" if EngineLock(ws).held_elsewhere() else " Continue with: python -m orch resume"))


def cmd_cancel(a):
    ws = ws_of(a)
    n = ws.cancel(a.task)
    print(f"{n} task(s) flagged; " + ("the engine stops them now" if EngineLock(ws).held_elsewhere() else "applied on: python -m orch resume"))


def cmd_kg(a):
    if a.action == "add":
        ws_of(a).kg_add(a.text[0], " ".join(a.text[1:]), "user", "user")
        return print("added")
    ws, text = ws_of(a, readonly=True), " ".join(a.text)
    print(mcp.kg_links(ws, {"node": text}) if a.action == "links" else mcp.kg_search(ws, {"query": text, "k": a.k}))


def cmd_mcp(a):
    mcp.serve(Path(a.ws or os.environ.get("ORCH_WS") or os.getcwd()).resolve(), control=a.control)


def cmd_log(a):
    ws = ws_of(a, readonly=True)
    for e in reversed(ws.q("SELECT * FROM events WHERE run=? ORDER BY id DESC LIMIT ?", ws.run, a.n)):
        print(f"{time.strftime('%H:%M:%S', time.localtime(e['ts']))} {e['kind']:<10} {e['task'] or '':<8} {e['actor']:<10} {e['body'][:400]}")


def cmd_ui(a):
    from . import server
    server.serve(ws_of(a), a.port, not a.no_browser)


def cmd_skills(a):
    from . import skills
    skills.cli(ws_of(a), a)


def cmd_pool(a):
    ws = ws_of(a)
    team = load_team(ws)
    if a.action == "test":
        pairs = [tuple(x.split("/", 1)) for x in a.pairs] or [(w["agent"], w["model"]) for w in team["workers"].values() if w.get("backup")]
        if not pairs or any(len(p) != 2 or p[0] not in agents.catalog() for p in pairs):
            raise SystemExit("name agent/model pairs (python -m orch discover lists them), or plan a pool first")
        for (aid, m), r in pool.pretest(pairs, hard=a.hard).items():
            print(f"{aid}/{m}: {r['outcome']} ({r['seconds']}s) {r['detail'][:150]}")
        return
    if a.action == "plan":
        name, crit = pool.choose(a.preset, a.criteria, None if a.yes else input)
        cands, db = agents.candidates(), models.load()
        if not db["models"]:
            print("no benchmark DB: c / r / n count as 0.5 and the t filter is off "
                  "(python -m orch models refresh downloads the public Epoch AI + OpenRouter data)")
        ranked, hard = pool.rank(team, cands, crit, ws, db), a.hard or pool.hard(crit)
        todo = list(dict.fromkeys(r["pair"] for rows in ranked.values() for r in rows[:3] if not pool.fresh(r["pair"], hard)))
        if todo and not a.no_test and (a.yes or confirm(f"Pre-test {len(todo)} candidate(s) with a {'small' if hard else 'tiny'} coding task, "
                                                        "one agent call each? [Y/n] ", True)):
            for (aid, m), r in pool.pretest(todo, hard=hard).items():
                print(f"  test {aid}/{m}: {r['outcome']} ({r['seconds']}s)")
            ranked = pool.rank(team, cands, crit, ws, db)
        print(pool.table(ranked, team, a.per))
        picks = {n: [r["pair"] for r in rows[:a.per]] for n, rows in ranked.items()}
        if not any(picks.values()):
            raise SystemExit("no usable backup candidate: log in to more agents (python -m orch discover)")
        if a.yes or confirm("Save the backups marked * to team.json? [Y/n] ", True):
            busy = {t["assignee"] for t in ws.tasks() if t["status"] not in TERMINAL}
            team = save_team(ws, pool.apply(team, picks, crit, name, busy))
    print("\n".join(pool.describe(team, ws)))


def cmd_bench(a):
    from . import bench
    report = bench.bench(ws_of(a), a.goal, a.check, a.solo, a.timeout)
    print("\n" + report.read_text(encoding="utf-8") + f"\n-> {report}")


def cmd_doctor(a):
    from . import doctor
    text, code = doctor.report(a.ws or os.environ.get("ORCH_WS") or (os.getcwd() if (Path.cwd() / ".orch").is_dir() else None))
    print(text)
    raise SystemExit(code)


def cmd_remote(a):
    from . import remote
    if a.action == "proxy":
        return remote.proxy(a.spec or "", a.mode, a.schema)
    remote.run(a.url, a.name, a.agents.split(",") if a.agents else None, a.once)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="orctram", description="Orctram: local multi-agent coding orchestration (same as: python -m orch)")
    ap.add_argument("--version", action="version", version=f"orctram {__version__}")
    ap.add_argument("--ws", help="project folder (default: $ORCH_WS or the current directory)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("discover", help="find agent CLIs, their models and login state")
    s.add_argument("--probe", action="store_true", help="also run one tiny call per agent to prove it works")
    s.add_argument("--only", help="comma-separated agent ids")
    s = sub.add_parser("models", help="model knowledge base")
    s.add_argument("action", choices=["refresh", "show", "suggest"])
    s.add_argument("ids", nargs="*")
    s = sub.add_parser("vault", help="API keys (encrypted with Windows DPAPI)")
    s.add_argument("action", choices=["list", "set", "rm"])
    s.add_argument("name", nargs="?")
    s = sub.add_parser("login", help="open an agent CLI's own login flow")
    s.add_argument("agent", choices=sorted(agents.catalog()))
    s = sub.add_parser("init", help="pick the team for this project")
    s.add_argument("--yes", action="store_true", help="accept the suggested team")
    s.add_argument("--team", help="team JSON file instead of the interactive pick")
    s.add_argument("--no-probe", action="store_true")
    s = sub.add_parser("run", help="start a run for a goal")
    s.add_argument("goal")
    s.add_argument("--yes", action="store_true", help="auto-approve the reviewed plan")
    s.add_argument("--exit-on-wait", action="store_true", help="exit (code 3) when only user answers can make progress")
    s = sub.add_parser("resume", help="continue the current run (after answers, a crash or Ctrl+C)")
    s.add_argument("--exit-on-wait", action="store_true")
    for n in ("status", "board", "inbox"):
        sub.add_parser(n)
    s = sub.add_parser("answer", help="answer a task waiting for you")
    s.add_argument("task")
    s.add_argument("text")
    s = sub.add_parser("cancel", help="cancel a task, or 'all'")
    s.add_argument("task")
    s = sub.add_parser("kg", help="shared knowledge graph")
    s.add_argument("action", choices=["search", "links", "add"])
    s.add_argument("text", nargs="+")
    s.add_argument("-k", type=int, default=8)
    s = sub.add_parser("mcp", help="MCP server on stdio: the board and the knowledge graph as read-only tools for agents")
    s.add_argument("--control", action="store_true", help="also run / status / answer / resume / cancel / doctor: for your own "
                                                          "Claude Code or Codex session (never given to agents in a run)")
    s = sub.add_parser("log", help="recent events")
    s.add_argument("-n", type=int, default=40)
    s = sub.add_parser("ui", help="local web UI")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true", help="only print the link")
    s = sub.add_parser("bench", help="the same goal by one agent alone and by the team, judged by your --check commands: is the team worth it?")
    s.add_argument("goal")
    s.add_argument("--check", action="append", default=[], help='a command that must pass on the result, e.g. "python -m pytest -q" (repeatable)')
    s.add_argument("--solo", help="agent/model working alone (default: the team's lead)")
    s.add_argument("--timeout", type=int, default=1800, help="seconds for the solo agent call")
    sub.add_parser("doctor", help="check this machine (and the project, with --ws) before a run: local checks only, nothing is sent")
    s = sub.add_parser("remote", help="remote worker: run = serve the agent CLIs of this machine to an engine (over ssh -R)")
    s.add_argument("action", choices=["run", "proxy"])
    s.add_argument("spec", nargs="?", help=argparse.SUPPRESS)
    s.add_argument("--url", default="http://127.0.0.1:8765", help="the engine machine's web UI, through the tunnel")
    s.add_argument("--name", help="this runner's name in events (default: the host name)")
    s.add_argument("--agents", help="comma-separated agent ids to serve (default: every installed agent CLI)")
    s.add_argument("--once", action="store_true", help="exit after one attempt")
    s.add_argument("--mode", default="rw", help=argparse.SUPPRESS)
    s.add_argument("--schema", help=argparse.SUPPRESS)
    s = sub.add_parser("skills", help="skill catalog")
    s.add_argument("action", choices=["list", "refresh", "approve", "reject"])
    s.add_argument("id", nargs="?")
    s = sub.add_parser("pool", help="quota outlook and backup pool: show | plan (rank, pre-test, save) | test [agent/model ...]")
    s.add_argument("action", nargs="?", default="show", choices=["show", "plan", "test"])
    s.add_argument("pairs", nargs="*", help="test: agent/model pairs (default: the team's backups)")
    s.add_argument("--preset", choices=list(pool.PRESETS), help="steady (default) | match | precise")
    s.add_argument("--criteria", help='e.g. "s=3,q=2,t": a letter toggles, letter=N sets its weight (0 = off)')
    s.add_argument("--per", type=int, default=1, help="backups per primary worker")
    s.add_argument("--no-test", action="store_true", help="rank without pre-testing")
    s.add_argument("--hard", action="store_true", help="pre-test with the harder task (default for match / precise rankings)")
    s.add_argument("--yes", action="store_true", help="no questions: preset or --criteria, pre-test, save")
    a = ap.parse_args(argv)
    try:
        globals()[f"cmd_{a.cmd}"](a)
    except sqlite3.OperationalError as e:
        raise SystemExit(f"no orchestra workspace here ({e}); use --ws or run: python -m orch init")
    except (ValueError, RuntimeError) as e:  # user-facing errors from shared helpers (vault names, team files, logins)
        raise SystemExit(f"error: {e}")
    except KeyboardInterrupt:
        raise SystemExit("\nstopped. Running agents were killed; continue with: python -m orch resume")


if __name__ == "__main__":
    main()
