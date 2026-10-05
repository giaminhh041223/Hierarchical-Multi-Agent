"""Resource planner, deterministic (zero tokens): each account's quota outlook, and a pre-tested backup pool per primary
worker, ranked by criteria the user ticks or by one of three presets. The engine moves a task to its worker's backup when
that account runs out (Engine.spare) and hands it back after the reset, or after team "cooldown" seconds (Engine.schedule)."""
import copy, math, re, shutil, subprocess, sys, threading, time

from . import agents, models
from .core import HOME, contract, extract_json, history, hm, record, schema, validate

CRITERIA = {  # letter: (name, meaning). Scores are 0..1; None = no evidence yet: counts as 0.5 and lowers the confidence
    "s": ("stable", "calls not cut by quota / rate limit / timeout (your history + pool tests)"),
    "c": ("coding", "coding benchmarks: SWE-bench Verified, Terminal-Bench, METR time horizon (percentile)"),
    "r": ("reasoning", "reasoning benchmarks: GPQA Diamond, HLE, Epoch ECI (percentile)"),
    "h": ("honest", "'done' claims that passed verification = low hallucination (your history + pool tests)"),
    "n": ("near", "capability closest to the primary it replaces (a stronger model loses only half as much)"),
    "q": ("quick", "short calls: 30 s scores 1, 10 min scores 0 (your history)"),
    "f": ("free", "free tier: spends no paid quota"),
    "t": ("trusted", "filter: only models with public benchmark results (needs: python -m orch models refresh)"),
}
PRESETS = {
    "steady": ("Ổn định, không đứt gãy: short outages, keep the work flowing", {"s": 3, "q": 2, "f": 2, "h": 1, "c": 1}),
    "match": ("Năng lực tương đương: long outages, core tasks", {"n": 3, "c": 3, "r": 2, "s": 1, "t": 1}),
    "precise": ("Chính xác, ít ảo giác: sensitive tasks", {"h": 3, "r": 3, "s": 1, "c": 1, "t": 1}),
}
BROKEN = ("auth", "model", "missing", "error", "invalid", "blocked")  # a last pool test like this excludes the model until retested
RISK = 0.75  # ponytail: flat score factor for an at-risk account; scale it by the time left before it runs out if that misranks
FIZZ = ("Create fizz.py in the current directory with a function fizz(n) that returns 'Fizz' for multiples of 3, 'Buzz' for "
        "multiples of 5, 'FizzBuzz' for multiples of both and str(n) otherwise. Change nothing else.")
CHECK = "from fizz import fizz; assert [fizz(i) for i in (1, 3, 5, 15, 7, 30)] == ['1', 'Fizz', 'Buzz', 'FizzBuzz', '7', 'FizzBuzz']"
ROMAN = ("Create roman.py in the current directory with to_roman(n), the Roman numeral of an int from 1 to 3999, and "
         "from_roman(s), its value. from_roman must raise ValueError for every string that is not a numeral in standard form, "
         "for example '', 'IIII', 'VX', 'IM' and 'MMMM'. Change nothing else.")
ROMAN_CHECK = ("from roman import to_roman as t, from_roman as f\n"
               "assert [t(n) for n in (1, 4, 9, 14, 40, 90, 400, 1994, 3999)] == "
               "['I', 'IV', 'IX', 'XIV', 'XL', 'XC', 'CD', 'MCMXCIV', 'MMMCMXCIX']\n"
               "assert all(f(t(n)) == n for n in range(1, 4000))\n"
               "for bad in ('', 'IIII', 'VX', 'IM', 'MMMM', 'IIV', 'XXC', 'VV', 'LC', 'DM', 'IL', 'XIIII', 'ABC'):\n"
               "    try: f(bad)\n"
               "    except ValueError: continue\n"
               "    raise AssertionError(bad)")
TESTS = {False: ("POOL", FIZZ, CHECK), True: ("POOL-HARD", ROMAN, ROMAN_CHECK)}  # hard: the edge cases weak models claim but miss


# --- quota outlook ------------------------------------------------------------------------------------------
def outlook(aid, cool_until=0.0, now=None):
    """-> {"text", "used": max % of any window, "out_until": exhausted until (else None), "risk": may run out before its reset}"""
    now = time.time() if now is None else now
    if cool_until > now:
        return {"text": f"out of usage until {hm(cool_until)}", "used": 100.0, "out_until": cool_until, "risk": True}
    wins = agents.usage(aid, now)
    if not wins:
        return {"text": "no quota record (learned from its errors)", "used": 0.0, "out_until": None, "risk": False}
    bits, out, risk = [], None, False
    for w in wins:
        s = (f"{w['minutes'] // 60}h" if w["minutes"] < 1440 else f"{w['minutes'] // 1440}d") + f" {w['used']:.0f}%"
        if w["resets"]:
            eta = now + (100 - w["used"]) / w["burn"] * 3600 if w["burn"] and w["burn"] > 0 and w["used"] < 100 else None
            soon = eta is not None and eta < w["resets"]
            out = max(out or 0, w["resets"]) if w["used"] >= 100 else out
            risk |= w["used"] >= 90 or soon
            s += f" (resets {hm(w['resets'])}" + (f", runs out ~{hm(eta)} at the current pace" if soon else "") + ")"
        bits.append(s)
    return {"text": "; ".join(bits), "used": max(w["used"] for w in wins), "out_until": out, "risk": risk}


def accounts(team):
    """account (one quota: agents.account) -> the roles and workers that use it"""
    use = {}
    for n, r in [*((n, team.get(n)) for n in ("lead", "reviewer", "skill_architect")), *team["workers"].items()]:
        if r:
            use.setdefault(agents.account(r["agent"], r["model"]), []).append(n)
    return use


def outlooks(team, ws):
    return {aid: outlook(aid, float(ws.meta(f"cool:{aid}") or 0)) for aid in accounts(team)}


def backups_of(team, name):
    """Who stands in for primary worker `name`: the pool backups planned for it, then hand-written backups (they cover all)."""
    wk = team["workers"]
    return ([n for n, w in wk.items() if w.get("backup") and name in w.get("for", [])] +
            [n for n, w in wk.items() if w.get("backup") and not w.get("for")])


def fmt(crit):
    return " ".join(k if k == "t" else f"{k}={v}" for k, v in crit.items())


def describe(team, ws):
    """Markdown lines for plan.md and `pool show`."""
    use, wk = accounts(team), team["workers"]
    lines = ["| account | quota | used by |", "|---|---|---|"]
    lines += [f"| {aid} | {o['text']}{' **(at risk)**' if o['risk'] else ''} | {', '.join(use[aid])} |" for aid, o in outlooks(team, ws).items()]
    lines.append("")
    for n, w in wk.items():
        if not w.get("backup"):
            b = backups_of(team, n)
            lines.append(f"- {n} ({w['agent']}/{w['model']}) backups: " +
                         (", ".join(f"{x} ({wk[x]['agent']}/{wk[x]['model']})" for x in b) or "none (python -m orch pool plan)"))
    if team.get("pool"):
        p = team["pool"]
        lines.append(f"- pool: {p['preset']} ({fmt(p['criteria'])}), planned {p['as_of']}. Back to the primary at its reset time, "
                     f"or after cooldown={team.get('cooldown', 3600)}s when the CLI names none")
    return lines


# --- evidence: our own history + public benchmarks ---------------------------------------------------------
def observed(agent, model):
    """Every recorded call of (agent, model), pool tests included."""
    n, cut, good, bad, avg_s = history().execute(
        "SELECT count(*), sum(outcome IN ('quota', 'rate_limit', 'timeout')), sum(outcome = 'integrated' OR (role = 'pool' AND outcome = 'ok')),"
        " sum(outcome = 'verify'), avg(CASE WHEN ok = 1 THEN seconds END) FROM runs WHERE agent=? AND model=? AND outcome IS NOT NULL",
        (agent, model)).fetchone()
    last = history().execute("SELECT outcome, ts FROM runs WHERE agent=? AND model=? AND role='pool' ORDER BY ts DESC LIMIT 1",
                             (agent, model)).fetchone()
    lap = lambda k, m: (k + 1) / (m + 2) if m else None  # Laplace: one lucky call is not "100%"
    return {"stable": lap(n - (cut or 0), n), "honest": lap(good or 0, (good or 0) + (bad or 0)), "avg_s": avg_s, "last": last}


def fresh(pair, hard=False, hours=24):
    """Pool-tested within `hours`; for the hard test only a hard one counts."""
    last = history().execute("SELECT max(ts) FROM runs WHERE agent=? AND model=? AND role='pool' AND (task='POOL-HARD' OR ?=0)",
                             (*pair, int(hard))).fetchone()[0]
    return bool(last and last > time.time() - hours * 3600)


def hard(crit):
    """Rankings led by capability or honesty (match, precise) pre-test with the hard task."""
    return any(crit.get(k, 0) >= 3 for k in "ncrh")


def rank(team, cands, crit, ws, db=None):
    """-> {primary worker: [row, best first]}; row = {"pair", "score", "conf", "s": {letter: score}, "last": last pool test, "risk"}.
    Never a backup: the primary's own account (it runs out together), an account cooling or >= 90% used, a model already
    working as a primary, a model whose last pool test failed hard (BROKEN), and with filter t a model without benchmarks.
    An account at risk (may run out before its reset at the current pace) keeps RISK of its score."""
    db = db or models.load()
    cols, cat, looks, base = models.percentiles(db), agents.catalog(), {}, {}
    weights = {k: v for k, v in crit.items() if k != "t" and v}
    total = sum(weights.values()) or 1
    for aid, model in dict.fromkeys(cands):
        if aid not in cat:
            continue
        ac = agents.account(aid, model)
        if ac not in looks:
            looks[ac] = outlook(ac, float(ws.meta(f"cool:{ac}") or 0))
        ob, cp = observed(aid, model), models.profile(model, db, cols)
        if looks[ac]["out_until"] or looks[ac]["used"] >= 90 or (ob["last"] and ob["last"][0] in BROKEN) or (crit.get("t") and cols and cp["cap"] is None):
            continue
        q = None if not ob["avg_s"] else min(1.0, max(0.0, 1 - math.log(max(ob["avg_s"], 1) / 30) / math.log(20)))
        base[(aid, model)] = ({"s": ob["stable"], "c": cp["c"], "r": cp["r"], "h": ob["honest"], "q": q,
                               "f": float(bool(cat[aid].get("free")) or "free" in model.lower())}, cp["cap"], ob["last"], ac)
    prim = {n: w for n, w in team["workers"].items() if not w.get("backup")}
    taken = {(w["agent"], w["model"]) for w in prim.values()}
    out = {}
    for name, p in prim.items():
        pc, rows, mine = models.profile(p["model"], db, cols)["cap"], [], agents.account(p["agent"], p["model"])
        for (aid, model), (s, cap, last, ac) in base.items():
            if ac == mine or (aid, model) in taken:
                continue
            s = {**s, "n": None if cap is None or pc is None else 1 - ((cap - pc) / 2 if cap > pc else pc - cap)}
            score = sum(v * (0.5 if s[k] is None else s[k]) for k, v in weights.items()) / total * (RISK if looks[ac]["risk"] else 1)
            conf = sum(v for k, v in weights.items() if s[k] is not None) / total
            rows.append({"pair": (aid, model), "score": round(score, 3), "conf": round(conf, 2), "s": s, "last": last,
                         "risk": looks[ac]["risk"]})
        out[name] = sorted(rows, key=lambda r: (-r["score"], -r["conf"]))
    return out


def table(ranked, team, per):
    lines = []
    for name, rows in ranked.items():
        w = team["workers"][name]
        lines.append(f"{name} ({w['agent']}/{w['model']}):" + ("" if rows else " no candidate"))
        for i, r in enumerate(rows[:max(per, 4)]):
            s = " ".join(f"{k}={'-' if v is None else round(v, 2)}" for k, v in r["s"].items())
            test = f"tested {r['last'][0]} {hm(r['last'][1])}" if r["last"] else "untested"
            lines.append(f"  {'*' if i < per else ' '} {'/'.join(r['pair']):<42} {r['score']:.2f} conf {r['conf']:.2f}  {s}  {test}"
                         + ("  account at risk" if r["risk"] else ""))
    return "\n".join(lines)


# --- pre-test: one tiny real task per candidate -------------------------------------------------------------
def pretest(pairs, timeout=300, hard=False):
    """One small coding task per (agent, model), checked by us: is it reachable and entitled, does it follow the worker output
    contract, and is its "done" true? Recorded in history (role "pool"), where the s / h / q criteria read it.
    Accounts run in parallel, one call at a time each: a quota is per account."""
    by, res, (tid, job, check) = {}, {}, TESTS[hard]
    for p in dict.fromkeys(pairs):
        by.setdefault(agents.account(*p), []).append(p)

    def one(aid, model):
        d = HOME / "probe" / "pool" / re.sub(r"[^\w.-]", "_", f"{aid}-{model}")
        shutil.rmtree(d, ignore_errors=True)
        (d / "wt").mkdir(parents=True)
        prompt = "\n\n".join(filter(None, [f"ORCH-CALL role=worker task={tid}", "You are being tried out as a backup worker: one small task.",
                                           contract("handoff"), f"## Task\n{job}", agents.catalog()[aid].get("note")]))
        r = agents.run_agent(aid, model, prompt, d / "wt", d / "out", schema="handoff", timeout=timeout)  # out_dir outside the cwd
        outcome, detail = r["failure"] or "error", r["error"] or ""
        if r["ok"]:
            try:
                h = validate(extract_json(r["text"]), schema("handoff"))
            except ValueError as e:
                h, detail = None, str(e)
            passed = subprocess.run([sys.executable, "-c", check], cwd=d / "wt", env=agents.verify_env(), capture_output=True,
                                    timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
            outcome = "invalid" if h is None else "blocked" if h["status"] != "done" else "ok" if passed else "verify"
            detail = detail if h is None else h["summary"]
        record("pool", tid, aid, model, "pool", outcome, r["seconds"], r["tokens_in"], r["tokens_out"], r["cost"])
        return {"outcome": outcome, "seconds": r["seconds"], "detail": detail[:300]}

    def account(ps):
        for p in ps:
            try:
                res[p] = one(*p)
            except Exception as e:  # one broken adapter must not lose the other results
                res[p] = {"outcome": "error", "seconds": 0, "detail": f"{type(e).__name__}: {e}"}
    ths = [threading.Thread(target=account, args=(ps,)) for ps in by.values()]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    return res


# --- choosing criteria, saving the pool ----------------------------------------------------------------------
def tweak(crit, text):
    """'c' toggles a criterion, 'c=3' sets its weight (0 = off)."""
    crit = dict(crit)
    for tok in filter(None, re.split(r"[\s,]+", text.strip().lower())):
        m = re.fullmatch(r"([a-z])(?:=(\d+))?", tok)
        if not m or m.group(1) not in CRITERIA:
            raise ValueError(f"unknown criterion {tok!r}: use one of {', '.join(CRITERIA)}")
        crit[m.group(1)] = int(m.group(2)) if m.group(2) else 0 if crit.get(m.group(1)) else 1
    return {k: v for k, v in crit.items() if v}


def criteria_text(name, crit):
    lines = [f"Backup ranking: {name}" + (f" ({PRESETS[name][0]})" if name in PRESETS else "")]
    for k, (label, what) in CRITERIA.items():
        w = ("filter" if k == "t" else f"w={crit[k]}") if crit.get(k) else ""
        lines.append(f"  [{'x' if crit.get(k) else ' '}] {k} {label:<9} {w:<6} {what}")
    lines.append("presets: " + " | ".join(f"{i} {n}" for i, n in enumerate(PRESETS, 1)))
    return "\n".join(lines)


def choose(preset=None, spec=None, ask=None):
    """Ranking criteria: a preset (default steady; none when only spec is given), tweaked by spec ("s=3,q=2,t"), then ticked
    interactively while ask (= input) is given. -> (name, {letter: weight})"""
    name = preset or ("custom" if spec else "steady")
    crit = dict(PRESETS[name][1]) if name in PRESETS else {}
    if spec:
        crit, name = tweak(crit, spec), "custom"
    while ask:
        print(criteria_text(name, crit))
        x = ask("digit = preset, letters toggle (e.g. 'c r'), c=3 sets a weight, Enter = rank with these: ").strip()
        if not x:
            break
        if x.isdigit() and 1 <= int(x) <= len(PRESETS):
            name = list(PRESETS)[int(x) - 1]
            crit = dict(PRESETS[name][1])
            continue
        try:
            crit, name = tweak(crit, x), "custom"
        except ValueError as e:
            print(e)
    if not any(v for k, v in crit.items() if k != "t"):
        raise ValueError("pick at least one ranking criterion besides the t filter")
    return name, crit


def apply(team, picks, crit, preset, busy=()):
    """picks {primary: [(agent, model)]} -> new team. Earlier pool backups (they have "for") are replaced, except ones busy in
    the current run; hand-written backups stay and already cover every primary, so a pick equal to one is skipped."""
    team = copy.deepcopy(team)
    wk = {n: w for n, w in team["workers"].items() if not w.get("for") or n in busy}
    for prim, pairs in picks.items():
        for aid, model in pairs:
            same = next((n for n, w in wk.items() if w.get("backup") and (w["agent"], w["model"]) == (aid, model)), None)
            if same:
                if "for" in wk[same] and prim not in wk[same]["for"]:
                    wk[same]["for"].append(prim)
                continue
            stem, i = re.sub(r"[^A-Za-z0-9-]", "-", aid), 1
            while f"{stem}-b{i}" in wk:
                i += 1
            wk[f"{stem}-b{i}"] = {"agent": aid, "model": model, "max": 1, "backup": True, "for": [prim]}
    team["workers"] = wk
    team["pool"] = {"preset": preset, "criteria": crit, "as_of": time.strftime("%Y-%m-%d %H:%M")}
    return team
