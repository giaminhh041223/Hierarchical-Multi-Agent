"""`orctram bench`: does the team beat one agent working alone? The same goal, from the same commit, two ways:
- solo: one agent call with the whole goal in a fresh worktree, no plan, no review, no engine verify;
- team: a normal run of the workspace team, plan auto-approved (like `run --yes`), engine verify and merge.
Both results are judged by the same checks the user gives (e.g. the project's test command), never by the agents' own
verify commands, then compared on checks passed, tokens, cost, wall time, agent calls and questions for the user.
ponytail: one sample per arm; agents are noisy, so repeat it (or add --repeat) before trusting a difference."""
import json, shlex, subprocess, time
from pathlib import Path

from . import agents
from .core import HOME, contract, record
from .engine import RULES, check_handoff, checked_call, ensure_excluded, git, git_ok, load_team, new_run


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


def solo(ws, goal, who, base, bid, timeout, out_dir):
    """The baseline: one agent, the whole goal, the whole repository as scope, one call."""
    aid, model = who
    branch, wt = f"orch/bench-{bid}/solo", HOME / "wt" / f"bench-{bid}" / "solo"
    git(ws.project, "worktree", "add", "-q", "-b", branch, str(wt), base)
    try:
        prompt = "\n\n".join(filter(None, [f"ORCH-CALL role=worker task=SOLO run=bench-{bid}", RULES["common"], RULES["worker"],
                                           contract("handoff"), "---", f"## Goal\n{goal}",
                                           "You work alone: no plan, no other workers. Scope: the whole repository. Make the goal true, "
                                           "run the project's tests if it has any, then reply with the handoff JSON.",
                                           agents.catalog()[aid].get("note")]))  # the CLI's quirks, as the engine adds them (agy cannot run commands)
        t0 = time.time()
        run = lambda p, sub, sess: agents.run_agent(aid, model, p, wt, sub, schema="handoff", session=sess, timeout=timeout, readonly=False)
        r, calls, h, err = checked_call(run, prompt, out_dir / "agent", None, aid, "handoff", check_handoff)  # repaired once, as in a run
        seconds = time.time() - t0
        git(wt, "add", "-A")
        if not git_ok(wt, "diff", "--cached", "--quiet"):
            git(wt, "commit", "-q", "--no-verify", "-m", f"bench {bid}: solo {aid}/{model}")
        tin, tout = sum(c["tokens_in"] or 0 for c in calls), sum(c["tokens_out"] or 0 for c in calls)
        costs = [c["cost"] for c in calls if c["cost"] is not None]
        cost = sum(costs) if costs else None
        record(str(ws.project), "SOLO", aid, model, "bench", (r["failure"] or "error") if not r["ok"] else "invalid" if err else "ok",
               round(seconds, 1), tin, tout, cost)
        return {"arm": f"solo {aid}/{model}", "ref": branch, "status": f"failed ({r['failure']})" if not r["ok"] else "no valid handoff" if err
                else h["status"], "seconds": seconds, "calls": 1, "tokens_in": tin, "tokens_out": tout, "cost": cost, "questions": 0}
    finally:
        git(ws.project, "worktree", "remove", "--force", str(wt), codes=None)


def team(ws, goal):
    """A normal run, auto-approved; it may stop waiting for the user (the report says so, and the run stays open)."""
    t0 = time.time()
    e = new_run(ws, goal, auto_approve=True)
    e.exit_on_wait = True
    status = e.loop()
    seconds = time.time() - t0
    use = ws.q("SELECT count(*) n, coalesce(sum(tokens_in), 0) i, coalesce(sum(tokens_out), 0) o, sum(cost) c FROM attempts WHERE run=?", e.run)[0]
    asked = ws.q("SELECT count(*) n FROM events WHERE run=? AND kind='pending_user'", e.run)[0]["n"]
    return {"arm": f"team (lead {e.team['lead']['agent']}, {len(e.primaries())} worker(s))", "ref": f"orch/{e.run}/main", "status": status,
            "seconds": seconds, "calls": use["n"], "tokens_in": use["i"], "tokens_out": use["o"], "cost": use["c"], "questions": asked,
            "run": e.run}


def bench(ws, goal, checks, solo_who=None, timeout=1800, check_timeout=600):
    tm = load_team(ws)
    if not checks:
        raise ValueError("give at least one --check command: both results are judged by it, not by the agents' own verify")
    who = tuple(solo_who.split("/", 1)) if solo_who else (tm["lead"]["agent"], tm["lead"]["model"])
    if len(who) != 2 or who[0] not in agents.catalog():
        raise ValueError(f"--solo must be agent/model with an agent id from the catalog, not {solo_who!r}")
    if not git_ok(ws.project, "rev-parse", "--verify", "HEAD"):
        raise ValueError("bench needs a git repository with at least one commit")
    ensure_excluded(ws.project)
    base, bid = git(ws.project, "rev-parse", "HEAD"), time.strftime("%Y%m%d-%H%M%S")
    out = ws.dir / "bench" / bid
    out.mkdir(parents=True, exist_ok=True)
    checks = [shlex.split(c, posix=True) if isinstance(c, str) else list(c) for c in checks]
    arms = [solo(ws, goal, who, base, bid, timeout, out / "solo"), team(ws, goal)]
    for a, name in zip(arms, ("solo", "team")):
        a["checks"] = run_checks(ws.project, a["ref"], checks, check_timeout, out / f"checks-{name}", HOME / "wt" / f"bench-{bid}" / f"check-{name}")
    lines = [f"# Bench {bid}", "", f"Goal: {goal}", f"Base: {base[:10]}", "",
             "Both results judged by: " + "; ".join(f"`{subprocess.list2cmdline(c)}`" for c in checks), "",
             "| arm | result | checks passed | tokens in | tokens out | cost $ | agent calls | questions for you | wall time | branch |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for a in arms:
        passed = sum(ok for _, ok, _ in a["checks"])
        lines.append(f"| {a['arm']} | {a['status']} | {passed}/{len(a['checks'])} | {a['tokens_in']:,} | {a['tokens_out']:,} | "
                     f"{'' if a['cost'] is None else round(a['cost'], 4)} | {a['calls']} | {a['questions']} | {a['seconds']:.0f}s | `{a['ref']}` |")
    for a in arms:
        for cmd, ok, tail in a["checks"]:
            if not ok:
                lines += ["", f"**{a['arm']}** failed `{subprocess.list2cmdline(cmd)}`:", "```", tail.strip()[-300:], "```"]
    lines += ["", "One sample per arm: agents vary from run to run, so repeat the bench before trusting a difference."]
    report = out / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (out / "result.json").write_text(json.dumps(arms, default=str, indent=1), encoding="utf-8", newline="\n")
    return report
