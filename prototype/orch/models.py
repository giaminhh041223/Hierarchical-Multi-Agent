"""Model knowledge base: public benchmarks (Epoch AI, CC-BY) + prices (OpenRouter) + our own run history."""
import bisect, csv, io, json, re, time, urllib.request, zipfile

from . import agents
from .core import HOME, ROOT, history

EPOCH_URL = "https://epoch.ai/data/benchmark_data.zip"
OPENROUTER_URL = "https://openrouter.ai/api/v1/models"
DB_FILE = HOME / "models.json"  # downloaded data: never inside the installed package
LEGACY = ROOT / "catalog" / "models.json"  # where `models refresh` wrote it before 0.1.0

# csv file in Epoch zip -> (model column, score column, our field)
BENCH = {
    "epoch_capabilities_index/eci_scores.csv": ("Model", "eci", "eci"),
    "swe_bench_verified.csv": ("Model version", "mean_score", "swe_bench"),
    "terminalbench_external.csv": ("Model version", "Accuracy mean", "terminal_bench"),
    "webdev_arena_external.csv": ("Model version", "Arena Score", "webdev_elo"),
    "gpqa_diamond.csv": ("Model version", "mean_score", "gpqa"),
    "hle_external.csv": ("Model version", "Accuracy", "hle"),
    "metr_time_horizons_external.csv": ("Model version", "Time horizon", "metr_minutes"),
}
CODING, REASONING = ("swe_bench", "terminal_bench", "metr_minutes"), ("gpqa", "hle", "eci")
NOISE = {"high", "medium", "low", "max", "xhigh", "minimal", "unknown", "thinking", "preview", "latest", "exp", "free"}


def norm(model_id):
    """'anthropic/Claude Opus 5.5:batch', 'claude-opus-5-5_max', 'gemini-3.8-flash-high' -> one key."""
    s = model_id.lower().split("/")[-1].split(":")[0].split("_")[0]
    s = re.sub(r"[.\s]+", "-", s)
    s = re.sub(r"-?(20\d\d-\d\d-\d\d|20\d{6})", "", s)
    parts = s.split("-")
    while len(parts) > 1 and parts[-1] in NOISE:
        parts.pop()
    return "-".join(p for p in parts if p)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "orchestra/0.1"})
    return urllib.request.urlopen(req, timeout=60).read()


def refresh():
    """Rebuild catalog/models.json from live public sources."""
    models = {}
    z = zipfile.ZipFile(io.BytesIO(_get(EPOCH_URL)))
    for fname, (mcol, scol, field) in BENCH.items():
        for row in csv.DictReader(io.StringIO(z.read(fname).decode("utf-8-sig"))):
            try:
                val = float(row[scol])
            except (KeyError, ValueError):
                continue
            m = models.setdefault(norm(row[mcol]), {})
            if val > m.get(field, float("-inf")):
                m[field] = round(val, 3)
            if field == "eci":
                m.update(name=row["Display name"], org=row["Organization"], date=row["date"])
    for o in json.loads(_get(OPENROUTER_URL))["data"]:
        if ":" in o["id"]:  # :free / :batch variants carry misleading prices
            continue
        m = models.setdefault(norm(o["id"]), {})
        m.setdefault("name", o["name"].split(": ")[-1])
        m["context"] = o.get("context_length")
        p = o.get("pricing") or {}
        try:
            m["price_in"], m["price_out"] = round(float(p["prompt"]) * 1e6, 3), round(float(p["completion"]) * 1e6, 3)
        except (KeyError, ValueError, TypeError):
            pass
    db = {
        "as_of": time.strftime("%Y-%m-%d"),
        "sources": {"benchmarks": "Epoch AI, 'Capabilities & benchmarking', epoch.ai/benchmarks (CC-BY 4.0)",
                    "prices_context": "openrouter.ai/api/v1/models (USD per 1M tokens)"},
        "models": dict(sorted(models.items())),
    }
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    DB_FILE.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    return db


def load():
    f = DB_FILE if DB_FILE.exists() else LEGACY
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"models": {}}


def info(model_id, db=None):
    """Benchmarks + prices + our observed stats for a CLI model id."""
    m = dict((db or load())["models"].get(norm(model_id), {}))
    stats = history().execute(
        "SELECT count(*), avg(ok), avg(seconds), avg(tokens_in + tokens_out) FROM runs WHERE model=?", (model_id,)).fetchone()
    if stats[0]:  # ok_rate is Laplace-smoothed: 1 run that succeeded is not "100% reliable"
        m["observed"] = {"runs": stats[0], "ok_rate": round((stats[1] * stats[0] + 1) / (stats[0] + 2), 2), "avg_s": round(stats[2]),
                         "avg_tokens": round(stats[3] or 0)}
    return m


def card(model_id, db=None):
    """One compact line for prompts: the lead reads this instead of browsing the web."""
    m = info(model_id, db)
    bits = [f"{k}={m[k]}" for k in ("eci", "swe_bench", "terminal_bench", "webdev_elo", "gpqa", "context") if m.get(k) is not None]
    if "price_in" in m:  # list API price: a reference point, subscription CLIs do not bill per token
        bits.append(f"api-ref$/Mtok={m['price_in']}/{m['price_out']}")
    if "observed" in m:
        o = m["observed"]
        bits.append(f"ours: {o['runs']} runs ok={o['ok_rate']} avg={o['avg_s']}s")
    return " ".join(bits) or "no data"


def percentiles(db):
    cols = {}
    for m in db["models"].values():
        for k in CODING + REASONING:
            if isinstance(m.get(k), (int, float)):
                cols.setdefault(k, []).append(m[k])
    return {k: sorted(v) for k, v in cols.items()}


def profile(model, db, cols):
    """Benchmark percentiles among all known models: coding, reasoning, overall capability (None = no public result)."""
    m = db["models"].get(norm(model), {})
    p = {k: bisect.bisect_right(cols[k], m[k]) / len(cols[k]) for k in CODING + REASONING if k in cols and isinstance(m.get(k), (int, float))}
    mean = lambda ks: sum(p[k] for k in ks) / len(ks) if ks else None
    return {"c": mean([k for k in CODING if k in p]), "r": mean([k for k in REASONING if k in p]), "cap": mean(list(p))}


def suggest(candidates, db=None, k=5):
    """candidates: [(agent, model)] usable on this machine -> default team, best first by expected quality: the benchmark
    prior (capability percentile among known models, 0.5 without public results) worth k calls, updated by this pair's own
    record: (k * prior + right) / (k + right + wrong). right = calls that ended ok or integrated; wrong = a false "done"
    (verify), a malformed reply (invalid), a timeout. Quota, auth and the like say nothing about the model.
    ponytail: k fixed and time / tokens unweighted; fit k and add a speed term once the history holds a few hundred runs."""
    db = db or load()
    cols = percentiles(db)

    def score(c):
        right, wrong = history().execute("SELECT coalesce(sum(ok), 0), coalesce(sum(outcome IN ('verify', 'invalid', 'timeout')), 0)"
                                         " FROM runs WHERE agent=? AND model=?", c).fetchone()
        cap = profile(c[1], db, cols)["cap"]
        return (k * (0.5 if cap is None else cap) + right) / (k + right + wrong)
    ranked = sorted(candidates, key=score, reverse=True)
    if not ranked:
        return {}
    lead = ranked[0]
    org = lambda c: info(c[1], db).get("org") or c[0]
    reviewer = next((c for c in ranked[1:] if org(c) != org(lead)), ranked[1] if len(ranked) > 1 else lead)
    rest = [c for c in ranked if c not in (lead, reviewer)] or [reviewer]
    seen, workers = set(), []
    for c in rest:  # one worker per account (agents.account): parallelism across subscriptions, not within one
        if agents.account(*c) not in seen:
            seen.add(agents.account(*c))
            workers.append(c)
    return {"lead": lead, "reviewer": reviewer, "skill_architect": rest[-1], "workers": workers[:4]}


def team_of(s):
    """suggest() output -> team.json roles; one parallel task per worker."""
    role = lambda c: {"agent": c[0], "model": c[1]}
    return {"lead": role(s["lead"]), "reviewer": role(s["reviewer"]), "skill_architect": role(s["skill_architect"]),
            "workers": {f"{c[0].split('@')[0]}-{i}": {**role(c), "max": 1} for i, c in enumerate(s["workers"], 1)}}
