"""`orctram bench`: does the team beat one agent working alone? The same goal, from the same commit, several ways:
- solo: one agent call with the whole goal in a fresh worktree (plus the repair turn every engine call gets), no plan, no
  review, no engine verify;
- team: a normal run of the workspace team, plan auto-approved (like `run --yes`), engine verify and merge;
- optional more team arms: the workspace team in another mode (--mode auto / solo) or other team files (--team-file);
- engine solo (--engine-solo): mode solo with the solo agent/model as the only worker, i.e. the solo agent inside the engine's
  verify-and-retry loop: it tells the engine's share of a win from a model change.
Every result is judged by the same checks the user gives (e.g. the project's test command), never by the agents' own verify
commands, and compared on checks passed, tokens, dollars, wall time, agent calls and questions for the user. --repeat runs
each arm N times, interleaved, and the summary gives medians: agents vary from run to run."""
import contextlib, json, os, shlex, statistics, subprocess, time
from pathlib import Path

from . import agents, models
from .core import HOME, contract, record
from .engine import MODES, RULES, check_handoff, checked_call, ensure_excluded, file_map, git, git_ok, load_team, new_run, validate_team


def run_checks(project, ref, checks, timeout, out_dir, wt):
    """Each check in a clean detached worktree `wt` of `ref`: [(command, passed, tail)]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    git(project, "worktree", "add", "-q", "--detach", str(wt), ref)
    res = []
    try:
        for i, cmd in enumerate(checks):
            o, e = out_dir / f"check{i}.out", out_dir / f"check{i}.err"
            try:
                code = agents.spawn((agents.resolve_bin(cmd[0]) or [cmd[0]]) + cmd[1:], wt, agents.verify_env(), out=o, err=e, timeout=timeout)
            except OSError as ex:
                res.append((cmd, False, f"cannot run: {ex}"))
                continue
            tail = (o.read_text(encoding="utf-8", errors="replace") + e.read_text(encoding="utf-8", errors="replace"))[-300:]
            res.append((cmd, code == 0, "timeout" if code is None else tail))
    finally:
        git(project, "worktree", "remove", "--force", str(wt), codes=None)
    return res


def split_cmd(text):
    """A --check string into argv. Windows: no POSIX escapes, so D:\\proj\\check.py keeps its backslashes; quotes still group."""
    if os.name != "nt":
        return shlex.split(text, posix=True)
    return [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t for t in shlex.split(text, posix=False)]


def dollars(rows):
    """[(cost reported or None, model, tokens in, tokens out)] -> (USD, estimated?) or (None, False): the CLI's own cost where it
    reports one, else the OpenRouter list price (models refresh)."""
    total, est, known = 0.0, False, False
    for cost, model, tin, tout in rows:
        if cost is None:
            cost, est = models.estimate(model, tin, tout), True
        if cost is not None:
            total, known = total + cost, True
    return (total, est) if known else (None, False)


def solo(ws, goal, who, base, bid, n, timeout, out_dir):
    """The baseline: one agent, the whole goal, the whole repository as scope, one call (and its repair turn)."""
    aid, model = who
    branch, wt = f"orch/bench-{bid}/solo-{n}", HOME / "wt" / f"bench-{bid}" / f"solo-{n}"
    git(ws.project, "worktree", "add", "-q", "-b", branch, str(wt), base)
    try:
        note = agents.catalog()[aid].get("note")  # the CLI's quirks, as the engine adds them (agy cannot run commands)
        prompt = "\n\n".join(filter(None, [f"ORCH-CALL role=worker task=SOLO run=bench-{bid}", RULES["common"], RULES["worker"],
                                           contract("handoff"), "---", f"## Goal\n{goal}",
                                           f"## Repository files\n{file_map(git(wt, 'ls-files').splitlines())}",
                                           "You work alone: no plan, no other workers. Scope: the whole repository. Make the goal true, "
                                           + ("" if note else "run the project's tests if it has any, ") + "then reply with the handoff JSON.",
                                           note]))  # no "run the tests" next to a note that forbids them: claude via agy tried to, twice
        t0 = time.time()
        run = lambda p, sub, sess: agents.run_agent(aid, model, p, wt, sub, schema="handoff", session=sess, timeout=timeout, readonly=False)
        r, calls, h, err = checked_call(run, prompt, out_dir / "agent", None, aid, "handoff", check_handoff)  # repaired once, as in a run
        seconds = time.time() - t0
        git(wt, "add", "-A")
        if not git_ok(wt, "diff", "--cached", "--quiet"):
            git(wt, "commit", "-q", "--no-verify", "-m", f"bench {bid}: solo {aid}/{model} #{n}")
        tin, tout = sum(c["tokens_in"] or 0 for c in calls), sum(c["tokens_out"] or 0 for c in calls)
        costs = [c["cost"] for c in calls if c["cost"] is not None]
        usd, est = dollars([(sum(costs) if costs else None, model, tin, tout)])
        record(str(ws.project), "SOLO", aid, model, "bench", (r["failure"] or "error") if not r["ok"] else "invalid" if err else "ok",
               round(seconds, 1), tin, tout, sum(costs) if costs else None)
        why = (r["error"] or "") if not r["ok"] else err if err else h["question"] if h["status"] == "blocked" else \
            h["summary"] if h["status"] == "failed" else ""
        return {"arm": f"solo {aid}/{model}", "ref": branch, "status": f"failed ({r['failure']})" if not r["ok"] else "no valid handoff" if err
                else h["status"], "seconds": seconds, "calls": 1, "tokens_in": tin, "tokens_out": tout, "usd": usd, "est": est, "questions": 0,
                "why": why}
    finally:
        git(ws.project, "worktree", "remove", "--force", str(wt), codes=None)


def team(ws, goal, label, tm):
    """A normal run with team `tm`, auto-approved; it may stop waiting for the user (the report says so; the run stays open)."""
    t0 = time.time()
    e = new_run(ws, goal, auto_approve=True, team=tm)
    e.exit_on_wait = True
    status = e.loop()
    seconds = time.time() - t0
    atts = ws.q("SELECT model, tokens_in, tokens_out, cost FROM attempts WHERE run=?", e.run)
    usd, est = dollars([(a["cost"], a["model"], a["tokens_in"], a["tokens_out"]) for a in atts])
    asked = ws.q("SELECT count(*) n FROM events WHERE run=? AND kind='pending_user'", e.run)[0]["n"]
    return {"arm": label, "ref": f"orch/{e.run}/main", "status": status, "seconds": seconds, "calls": len(atts),
            "tokens_in": sum(a["tokens_in"] or 0 for a in atts), "tokens_out": sum(a["tokens_out"] or 0 for a in atts),
            "usd": usd, "est": est, "questions": asked, "run": e.run, "why": "" if status == "done" else stopped(ws, e.run)}


def stopped(ws, run):
    """Why a run did not finish: the questions it waits on, else the last task that failed, else the run's own last word."""
    waiting = [f"{t['id']}: {t['question'] or ''}" for t in ws.tasks("pending_user", run=run)]
    if waiting:
        return " / ".join(waiting)
    last = ws.q("SELECT task, body FROM events WHERE run=? AND kind IN ('failed', 'run') ORDER BY id DESC LIMIT 1", run)
    return f"{last[0]['task'] or 'run'}: {last[0]['body']}" if last else ""


def cell(text, n=140):
    """One line of free text for a markdown table cell."""
    t = " ".join((text or "").split()).replace("|", "/")
    return t if len(t) <= n else t[:n - 1] + "…"


def money(usd, est):
    return "" if usd is None else f"{'~' if est else ''}{usd:.4f}"


def bench(ws, goal, checks, solo_who=None, timeout=1800, check_timeout=600, repeat=1, modes=(), team_files=(), engine_solo=False):
    if not checks:
        raise ValueError("give at least one --check command: every result is judged by it, not by the agents' own verify")
    if not 1 <= int(repeat) <= 20:
        raise ValueError("--repeat: 1 to 20")
    if bad := [m for m in modes if m not in MODES]:
        raise ValueError(f"--mode: one of {', '.join(MODES)}, not {bad}")
    tm = load_team(ws)
    who = tuple(solo_who.split("/", 1)) if solo_who else (tm["lead"]["agent"], tm["lead"]["model"])
    if len(who) != 2 or who[0] not in agents.catalog():
        raise ValueError(f"--solo must be agent/model with an agent id from the catalog, not {solo_who!r}")
    arms = [(f"team (lead {tm['lead']['agent']}, {sum(not w.get('backup') for w in tm['workers'].values())} worker(s), mode {tm['mode']})", tm)]
    arms += [(f"team mode {m}", {**tm, "mode": m}) for m in modes if m != tm["mode"]]
    for f in team_files:
        arms.append((f"team {Path(f).name}", validate_team(json.loads(Path(f).read_text(encoding="utf-8")))))
    if engine_solo:  # the solo agent's own model as the only worker: the engine's verify loop is then the only difference
        if not tm["verify"]:
            raise ValueError('--engine-solo runs mode solo, which takes its checks from team.json "verify": set it first')
        arms.append((f"engine solo {who[0]}/{who[1]}", validate_team({**tm, "mode": "solo", "solo": "solo",
                                                                      "workers": {"solo": {"agent": who[0], "model": who[1]}}})))
    if not git_ok(ws.project, "rev-parse", "--verify", "HEAD"):
        raise ValueError("bench needs a git repository with at least one commit")
    ensure_excluded(ws.project)
    base, bid = git(ws.project, "rev-parse", "HEAD"), time.strftime("%Y%m%d-%H%M%S")
    out = ws.dir / "bench" / bid
    out.mkdir(parents=True, exist_ok=True)
    checks = [split_cmd(c) if isinstance(c, str) else list(c) for c in checks]
    samples = []
    for n in range(1, int(repeat) + 1):  # interleaved: a slow hour or a cooling account hits every arm alike
        got = [solo(ws, goal, who, base, bid, n, timeout, out / f"solo-{n}")]
        got += [team(ws, goal, label, t) for label, t in arms]
        for i, a in enumerate(got):
            a["n"] = n
            a["checks"] = run_checks(ws.project, a["ref"], checks, check_timeout, out / f"checks-{n}-{i}", HOME / "wt" / f"bench-{bid}" / f"check-{n}-{i}")
        samples += got
    with contextlib.suppress(OSError):
        (HOME / "wt" / f"bench-{bid}").rmdir()  # its worktrees are gone; the empty directory goes too
    report = out / "report.md"
    report.write_text(render(bid, goal, base, checks, samples, int(repeat)), encoding="utf-8", newline="\n")
    (out / "result.json").write_text(json.dumps(samples, default=str, indent=1), encoding="utf-8", newline="\n")
    return report


def render(bid, goal, base, checks, samples, repeat):
    med = lambda xs: statistics.median(xs) if xs else None
    lines = [f"# Bench {bid}", "", f"Goal: {goal}", f"Base: {base[:10]}", "",
             "Every result judged by: " + "; ".join(f"`{subprocess.list2cmdline(c)}`" for c in checks), ""]
    order = list(dict.fromkeys(s["arm"] for s in samples))
    if repeat > 1:
        lines += [f"## Summary: medians of {repeat} runs per arm", "",
                  "| arm | runs passing every check | checks passed | tokens in | tokens out | $ | agent calls | questions | wall time |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for arm in order:
            xs = [s for s in samples if s["arm"] == arm]
            passed = [sum(ok for _, ok, _ in s["checks"]) for s in xs]
            usd = [s["usd"] for s in xs if s["usd"] is not None]
            lines.append(f"| {arm} | {sum(p == len(checks) for p in passed)}/{len(xs)} | {med(passed):g}/{len(checks)} | "
                         f"{med([s['tokens_in'] for s in xs]):,.0f} | {med([s['tokens_out'] for s in xs]):,.0f} | "
                         f"{money(med(usd), any(s['est'] for s in xs))} | {med([s['calls'] for s in xs]):g} | {med([s['questions'] for s in xs]):g} | "
                         f"{med([s['seconds'] for s in xs]):.0f}s |")
        lines += ["", "## Every run", ""]
    lines += ["| # | arm | result | checks passed | tokens in | tokens out | $ | agent calls | questions for you | wall time | branch | stopped because |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in samples:
        lines.append(f"| {s['n']} | {s['arm']} | {s['status']} | {sum(ok for _, ok, _ in s['checks'])}/{len(s['checks'])} | {s['tokens_in']:,} | "
                     f"{s['tokens_out']:,} | {money(s['usd'], s['est'])} | {s['calls']} | {s['questions']} | {s['seconds']:.0f}s | `{s['ref']}` | "
                     f"{cell(s.get('why'))} |")
    for s in samples:
        for cmd, ok, tail in s["checks"]:
            if not ok:
                lines += ["", f"**{s['arm']}** (run {s['n']}) failed `{subprocess.list2cmdline(cmd)}`:", "```", tail.strip()[-300:], "```"]
    lines += ["", "`~` = estimated at the OpenRouter list price (`models refresh`): free models cost 0, subscriptions do not bill per token."]
    if repeat == 1:
        lines.append("One sample per arm: agents vary from run to run, so repeat (--repeat 3) before trusting a difference.")
    return "\n".join(lines) + "\n"
