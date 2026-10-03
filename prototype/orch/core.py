"""Shared state: paths, workspace DB (tasks / attempts / events / knowledge graph), engine lock, vault, strict JSON."""
import array, base64, collections, contextlib, functools, hashlib, json, math, os, re, sqlite3, sys, threading, time, unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
SCHEMAS = CATALOG / "schemas"
HOME = Path(os.environ.get("ORCH_HOME") or Path.home() / ".orchestra")
SECRET_NAME = re.compile(r"(API_?KEY|ACCESS_KEY|PRIVATE_KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.I)

# Task states. Failure edges always record an attempt outcome first, then go to todo / needs_lead / pending_user / failed.
#   todo -> running -> verifying -> integrating -> done
#   needs_lead -> todo | pending_user | failed | cancelled ;  pending_user -> todo | cancelled
ACTIVE = {"running", "verifying", "integrating"}
TERMINAL = {"done", "failed", "cancelled"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
  run TEXT, id TEXT, kind TEXT, title TEXT, spec TEXT DEFAULT '{}', assignee TEXT, deps TEXT DEFAULT '[]',
  status TEXT DEFAULT 'todo', attempts INT DEFAULT 0, note TEXT DEFAULT '', question TEXT, answer TEXT,
  handoff TEXT, session TEXT, commit_sha TEXT, eligible_at REAL DEFAULT 0, cancel INT DEFAULT 0, updated REAL,
  PRIMARY KEY(run, id));
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY, run TEXT, task TEXT, kind TEXT, agent TEXT, model TEXT, pid INT, pid_ctime TEXT,
  started REAL, ended REAL, outcome TEXT, failure TEXT, tokens_in INT DEFAULT 0, tokens_out INT DEFAULT 0,
  cost REAL, session TEXT, dir TEXT);
CREATE TABLE IF NOT EXISTS plans(run TEXT, version INT, plan TEXT, verdicts TEXT, PRIMARY KEY(run, version));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, ts REAL, run TEXT, task TEXT, actor TEXT, kind TEXT, body TEXT);
CREATE TABLE IF NOT EXISTS skills(
  run TEXT, id TEXT, source TEXT, url TEXT, sha TEXT, status TEXT, curated INT, reason TEXT, tasks TEXT,
  path TEXT, digest TEXT, scan TEXT, updated REAL, PRIMARY KEY(run, id));
CREATE VIRTUAL TABLE IF NOT EXISTS facts USING fts5(entity, fact, task UNINDEXED, actor UNINDEXED, sha UNINDEXED, run UNINDEXED);
CREATE TABLE IF NOT EXISTS links(src TEXT, rel TEXT, dst TEXT, task TEXT, UNIQUE(src, rel, dst));
CREATE TABLE IF NOT EXISTS vectors(digest TEXT PRIMARY KEY, vec BLOB);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


class Workspace:
    """<project>/.orch : one SQLite file is the blackboard. Several processes (engine, CLI, UI) may open it."""
    def __init__(self, project, readonly=False):
        """readonly: agents query the board / knowledge graph from sandboxes that may forbid writes outside their worktree."""
        self.project = Path(project).resolve()
        self.dir = self.project / ".orch"
        self.lock = threading.RLock()
        self.quiet = False
        if readonly:
            self.db = sqlite3.connect(f"{(self.dir / 'orch.db').as_uri()}?mode=ro", uri=True, check_same_thread=False, timeout=30)
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.dir / "orch.db", check_same_thread=False, isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        if not readonly:
            self.db.executescript(SCHEMA)

    def q(self, sql, *args):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def x(self, sql, *args):
        """Execute, return rowcount (used for compare-and-set state transitions)."""
        with self.lock:
            return self.db.execute(sql, args).rowcount

    @contextlib.contextmanager
    def tx(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def read_json(self, name, default=None):
        f = self.dir / name
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default

    def write_json(self, name, data):
        (self.dir / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def meta(self, k, v=None):
        if v is None:
            r = self.q("SELECT v FROM meta WHERE k=?", k)
            return r[0]["v"] if r else None
        self.q("INSERT OR REPLACE INTO meta VALUES(?,?)", k, str(v))

    @property
    def run(self):
        return self.meta("run")

    def event(self, kind, body="", task=None, actor="engine"):
        body = redact(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False))
        self.q("INSERT INTO events(ts, run, task, actor, kind, body) VALUES(?,?,?,?,?,?)", time.time(), self.run, task, actor, kind, body)
        if not self.quiet:
            print(f"[{time.strftime('%H:%M:%S')}] {kind:<10} {task or '':<8} {actor:<10} {body[:220]}", flush=True)

    # --- tasks ---------------------------------------------------------------------------------------
    def add_task(self, id, kind, title, spec=None, assignee=None, deps=(), status="todo"):
        self.q("INSERT INTO tasks(run, id, kind, title, spec, assignee, deps, status, updated) VALUES(?,?,?,?,?,?,?,?,?)",
               self.run, id, kind, title, json.dumps(spec or {}, ensure_ascii=False), assignee, json.dumps(list(deps)), status, time.time())

    def tasks(self, *statuses, run=None):
        rows = self.q("SELECT * FROM tasks WHERE run=? ORDER BY rowid", run or self.run)
        for r in rows:
            r["spec"], r["deps"] = json.loads(r["spec"] or "{}"), json.loads(r["deps"] or "[]")
            r["handoff"] = json.loads(r["handoff"]) if r["handoff"] else None
        return [r for r in rows if not statuses or r["status"] in statuses]

    def task(self, id):
        return next((t for t in self.tasks() if t["id"] == id), None)

    def update(self, id, _expect=None, **fields):
        """Set fields; with _expect=status it is a compare-and-set and returns False if the task moved on."""
        for k in ("handoff", "spec", "deps"):
            if k in fields and fields[k] is not None and not isinstance(fields[k], str):
                fields[k] = json.dumps(fields[k], ensure_ascii=False)
        sets = ", ".join(f"{k}=?" for k in fields)
        sql = f"UPDATE tasks SET {sets}, updated=? WHERE run=? AND id=?" + (" AND status=?" if _expect else "")
        args = [*fields.values(), time.time(), self.run, id] + ([_expect] if _expect else [])
        return self.x(sql, *args) == 1

    def cancel(self, task):
        """Flag one live task, or 'all' (also stops new budget gates); the engine acts on the flag."""
        live = "status NOT IN ('done','failed','cancelled')"
        if task == "all":
            self.meta(f"{self.run}:cancelled", 1)
            return self.x(f"UPDATE tasks SET cancel=1 WHERE run=? AND {live}", self.run)
        return self.x(f"UPDATE tasks SET cancel=1 WHERE run=? AND id=? AND {live}", self.run, task)

    def board(self):
        """The run's status line and one line per task (CLI `board`, MCP tool `board`)."""
        run = self.run
        return "\n".join([f"run {run}: {self.meta(f'{run}:status') or 'open'} | goal: {self.meta(f'{run}:goal')}"] + [
            f"  {t['id']:<8} {t['status']:<12} {t['assignee'] or '':<14} a{t['attempts']} deps={','.join(t['deps']) or '-':<10} {t['title'][:70]}"
            for t in self.tasks()])

    # --- knowledge graph -------------------------------------------------------------------------------
    def kg_add(self, entity, fact, task="", actor="", sha=""):
        self.q("INSERT INTO facts VALUES(?,?,?,?,?,?)", entity, fact, task, actor, sha, self.run or "")

    def link(self, src, rel, dst, task=""):
        self.q("INSERT OR IGNORE INTO links VALUES(?,?,?,?)", src, rel, dst, task)

    def kg_search(self, text, k=8):
        """Top-k facts for free text: two rankings fused by reciprocal rank. FTS5/BM25 keywords, and vectors that also find
        near spellings and words typed without accents (local trigrams) or, with team.json "embeddings", the meaning (any
        OpenAI-compatible /embeddings endpoint; the facts are sent there)."""
        facts = self.q("SELECT rowid, entity, fact, task, actor, sha, run FROM facts")
        if not facts or not text.strip():
            return []
        words = re.findall(r"\w{3,}", text.lower())
        words = ([w for w in words if w not in STOP] or words)[:24]  # a query of only common words still searches them
        lexical = [r["rowid"] for r in self.q("SELECT rowid FROM facts WHERE facts MATCH ? ORDER BY rank LIMIT ?",
                                               " OR ".join(f'"{w}"' for w in words), k * 3)] if words else []
        docs, cfg, ranked = [f["fact"] for f in facts], (self.read_json("team.json") or {}).get("embeddings"), None
        if cfg:
            try:
                ranked = remote_rank(self, cfg, text, docs)
            except Exception as e:  # the optional endpoint must never break search
                print(f"embeddings: {e}; ranking locally", file=sys.stderr)
        vector = [facts[i]["rowid"] for i in (local_rank(text, docs) if ranked is None else ranked)[:k * 3]]
        score = {}
        for ranking in (lexical, vector):
            for n, rowid in enumerate(ranking):
                score[rowid] = score.get(rowid, 0) + 1 / (60 + n)
        by_id = {f.pop("rowid"): f for f in facts}
        return [by_id[i] for i in sorted(score, key=score.get, reverse=True)[:k]]

    def kg_neighbors(self, node):
        return self.q("SELECT * FROM links WHERE src=? OR dst=?", node, node)


STOP = set("the and for with that this from into must should will are was have has not you your task file files use using "
           "add make create implement update when then than all any each".split())


def fold(text):
    """'Đăng nhập' -> 'dang nhap': case and accents do not matter to the local vectors."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold().replace("đ", "d")) if not unicodedata.combining(c))


@functools.lru_cache(4096)
def grams(text):
    return collections.Counter(p[i:i + 3] for w in re.findall(r"\w+", fold(text)) for p in [f" {w} "] for i in range(len(p) - 2))


def local_rank(query, docs, floor=0.1):
    """Indexes of docs by cosine of TF-IDF character-trigram vectors, best first, those under `floor` dropped.
    ponytail: brute force with document frequencies recomputed per query; keep an index past ~10k facts."""
    bags = [grams(d) for d in docs]
    df = collections.Counter(g for b in bags for g in b)

    def unit(bag):
        v = {g: (1 + math.log(c)) * (math.log((len(bags) + 1) / (df[g] + 1)) + 1) for g, c in bag.items()}
        n = math.sqrt(sum(x * x for x in v.values())) or 1
        return {g: x / n for g, x in v.items()}
    q = unit(grams(query))
    sims = [(sum(q.get(g, 0) * x for g, x in unit(b).items()), i) for i, b in enumerate(bags)]
    return [i for s, i in sorted(sims, reverse=True) if s >= floor]


def remote_rank(ws, cfg, query, docs):
    """Indexes of docs by cosine of the endpoint's embeddings, best first, those under cfg "min" (default 0.3) dropped.
    Vectors are cached in the workspace by sha256(model, fact): each fact is sent once per model."""
    if not (isinstance(cfg, dict) and str(cfg.get("url", "")).startswith(("http://", "https://")) and cfg.get("model")):
        raise ValueError('team.json "embeddings" needs {"url": "http(s)://host/v1", "model": "..."}')
    digests = [hashlib.sha256(f"{cfg['model']}\0{d}".encode()).hexdigest() for d in docs]
    have = {r["digest"]: r["vec"] for r in ws.q("SELECT digest, vec FROM vectors")}  # ponytail: all in memory, fine below ~10k facts
    missing = [i for i, g in enumerate(digests) if g not in have]
    for s in range(0, len(missing), 64):
        batch = missing[s:s + 64]
        new = {digests[i]: array.array("f", v).tobytes() for i, v in zip(batch, embed(cfg, [docs[i] for i in batch]), strict=True)}
        have.update(new)
        with contextlib.suppress(sqlite3.OperationalError), ws.tx():  # read-only (the agents' MCP server): sent again next time
            ws.db.executemany("INSERT OR REPLACE INTO vectors VALUES(?,?)", new.items())
    q = embed(cfg, [query])[0]
    sims = [(cosine(q, array.array("f", have[g])), i) for i, g in enumerate(digests)]
    return [i for s, i in sorted(sims, reverse=True) if s >= cfg.get("min", 0.3)]


def embed(cfg, texts):
    """POST {url}/embeddings, OpenAI style. cfg "key" names the env var or vault entry holding the API key (optional).
    ponytail: failures are not remembered, a hung endpoint costs up to 30 s per search; add a cool-down if that bites."""
    key = cfg.get("key") and (os.environ.get(cfg["key"]) or vault().get(cfg["key"]))
    req = urllib.request.Request(cfg["url"].rstrip("/") + "/embeddings", json.dumps({"model": cfg["model"], "input": texts}).encode(),
                                 {"Content-Type": "application/json", "User-Agent": "orchestra", **({"Authorization": f"Bearer {key}"} if key else {})})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())["data"]
    return [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]


def cosine(a, b):  # not math.sumprod: Python 3.11 is supported
    return sum(x * y for x, y in zip(a, b)) / ((math.hypot(*a) * math.hypot(*b)) or 1)


# --- one engine per workspace ------------------------------------------------------------------------
class EngineLock:
    """OS file lock, released by the OS if the engine dies. Two engines on one workspace would double-run tasks."""
    def __init__(self, ws):
        self.path = ws.dir / "engine.lock"
        self.f = None

    def acquire(self):
        f = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        self.f = f
        return True

    def release(self):
        if self.f:
            self.f.close()  # closing the handle releases the lock on both platforms
            self.f = None

    def held_elsewhere(self):
        if self.acquire():
            self.release()
            return False
        return True


@functools.lru_cache(None)
def history():
    """Global run history across projects: the seed of our own model-performance network."""
    HOME.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(HOME / "history.db", check_same_thread=False, isolation_level=None, timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS runs(ts REAL, project TEXT, task TEXT, agent TEXT, model TEXT, role TEXT,"
              " ok INT, seconds REAL, tokens_in INT, tokens_out INT, cost REAL)")
    with contextlib.suppress(sqlite3.OperationalError):  # added later: why a call failed (quota, verify ...), for the resource planner
        c.execute("ALTER TABLE runs ADD COLUMN outcome TEXT")
    return c


def record(project, task, agent, model, role, outcome, seconds, tokens_in=0, tokens_out=0, cost=None):
    with contextlib.suppress(sqlite3.Error):
        history().execute("INSERT INTO runs(ts, project, task, agent, model, role, ok, seconds, tokens_in, tokens_out, cost, outcome)"
                          " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (time.time(), project, task, agent, model, role,
                                                              int(outcome in ("ok", "integrated")), seconds, tokens_in, tokens_out, cost, outcome))


def hm(ts):
    return time.strftime("%m-%d %H:%M", time.localtime(ts))


# --- vault: Windows DPAPI (user scope); chmod-600 JSON elsewhere ---------------------------------------
# DPAPI protects the file at rest (other users, copied disks); it does not hide secrets from code running as you.
VAULT = HOME / ("vault.dpapi" if os.name == "nt" else "vault.json")

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _dpapi(data, protect):
        crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        buf = ctypes.create_string_buffer(data, len(data))
        src, dst = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), _Blob()
        fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        if not fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(dst)):  # 0x1 = UI_FORBIDDEN
            raise ctypes.WinError()
        try:
            return ctypes.string_at(dst.pbData, dst.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(dst.pbData, ctypes.c_void_p))


def vault():
    if not VAULT.exists():
        return {}
    raw = VAULT.read_bytes()
    return json.loads(_dpapi(base64.b64decode(raw), False) if os.name == "nt" else raw)


def vault_set(name, value=None):
    """value=None deletes."""
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", name or ""):
        raise ValueError("vault key must look like ENV_VAR_NAME")
    data = vault()
    if value is None:
        data.pop(name, None)
    else:
        data[name] = value.strip()
    HOME.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data).encode()
    VAULT.write_bytes(base64.b64encode(_dpapi(raw, True)) if os.name == "nt" else raw)
    if os.name != "nt":
        os.chmod(VAULT, 0o600)


def mask(value):
    return value[:4] + "…" + value[-3:] if len(value) > 10 else "***"


def redact(text):
    for v in vault().values():
        if len(v) >= 8:
            text = text.replace(v, "***")
    return text


# --- strict JSON for agent replies: the three(+2) contracts in catalog/schemas -------------------------
MAX_REPLY = 256_000


def _pairs(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate JSON key(s): {sorted({k for k in keys if keys.count(k) > 1})}")
    return dict(pairs)


def _nonfinite(c):
    raise ValueError(f"non-finite number {c}")


def strict_loads(text):
    if len(text) > MAX_REPLY:
        raise ValueError(f"reply too large ({len(text)} chars)")
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_nonfinite)


def extract_json(text):
    """Agents without native structured output may wrap the object in prose or ``` fences, or repeat it
    (agy sometimes appends a second copy with tool fields): the first complete object wins."""
    if len(text) > MAX_REPLY:
        raise ValueError(f"reply too large ({len(text)} chars)")
    a = text.find("{")
    if a < 0:
        raise ValueError("no JSON object in reply")
    return json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_nonfinite).raw_decode(text, a)[0]


@functools.lru_cache(None)
def schema(name):
    return json.loads((SCHEMAS / f"{name}.json").read_text(encoding="utf-8"))


CONTRACT_HINT = {
    "handoff": "status: done = ready for the engine's verification; blocked = you need a decision (ask it in question); "
               "failed = impossible. question is null unless blocked. files = paths you changed. facts = short durable "
               "statements other agents need (e.g. \"api: GET /items returns a JSON list\"). decisions = choices you made.",
    "plan": "ids like T1, T2 (never PLAN, SKILLS, REVIEW, AMEND*, BUDGET*); assignee = a worker name; deps = ids that must be "
            "integrated first (only real dependencies: parallel work is cheaper); acceptance = checkable statements; "
            "scope_paths = files, dirs/ or globs relative to the repo root that the task may change; verify = argv arrays "
            "run from the repo root that must exit 0 (cross-platform, no shell operators, e.g. [\"python\",\"-m\",\"pytest\",\"-q\"]).",
    "verdict": "verdict = approve iff there is no blocker issue, else revise. blocker = must change; advisory = optional. "
               "task_id = the task concerned, or null.",
    "triage": "action: retry (same worker; concrete instructions in note) | reassign (assignee = another worker) | ask_user "
              "(only for decisions you may not take: secrets, goal/scope changes, money; put it in question) | fail | "
              "cancel (the task is unnecessary). assignee and question are null unless needed.",
    "skills": "skills = [{id, tasks, reason}]. id = a curated id from the index, or a GitHub URL for a non-curated proposal "
              "(the user must approve it). tasks = task ids that get the skill ([] = all). Pick 0-3; only clear wins.",
}


def contract(name):
    return (f"## Output contract: {name}\n{CONTRACT_HINT[name]}\nReply with ONLY one JSON object (no prose, no code fences) "
            f"valid against this JSON Schema:\n{json.dumps(schema(name), separators=(',', ':'))}")


def validate(obj, sch, root=None, path="$"):
    """The JSON-Schema subset our contracts use: type (incl. nullable lists), enum, required,
    additionalProperties:false, properties, items, $ref into $defs. Rejects anything else it sees."""
    root = root or sch
    if "$ref" in sch:
        sch = root["$defs"][sch["$ref"].split("/")[-1]]
    types = sch.get("type")
    types = types if isinstance(types, list) else [types]
    py = {"object": dict, "array": list, "string": str, "null": type(None), "integer": int, "number": (int, float), "boolean": bool}
    if not any(isinstance(obj, py[t]) and not (t in ("integer", "number") and isinstance(obj, bool)) for t in types):
        raise ValueError(f"{path}: expected {'/'.join(types)}, got {type(obj).__name__}")
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError(f"{path}: non-finite number")
    if "enum" in sch and obj not in sch["enum"]:
        raise ValueError(f"{path}: {obj!r} not in {sch['enum']}")
    if isinstance(obj, dict):
        props = sch.get("properties", {})
        missing = [k for k in sch.get("required", []) if k not in obj]
        extra = [k for k in obj if k not in props]
        if missing or extra:
            raise ValueError(f"{path}: missing {missing} / unknown {extra}")
        for k, v in obj.items():
            validate(v, props[k], root, f"{path}.{k}")
    if isinstance(obj, list) and "items" in sch:
        for i, v in enumerate(obj):
            validate(v, sch["items"], root, f"{path}[{i}]")
    return obj


if __name__ == "__main__":  # self-check: python -m orch.core
    h = {"status": "done", "summary": "s", "files": [], "decisions": [], "facts": [], "question": None}
    validate(h, schema("handoff"))
    for bad, why in [('{"a":1,"a":2}', "duplicate"), ('{"x": NaN}', "non-finite")]:
        try:
            strict_loads(bad)
            raise AssertionError(why)
        except ValueError as e:
            assert why in str(e), e
    for bad in [{**h, "extra": 1}, {**h, "status": "ok"}, {**h, "files": "a.py"}, {k: v for k, v in h.items() if k != "question"}]:
        try:
            validate(bad, schema("handoff"))
            raise AssertionError(bad)
        except ValueError:
            pass
    assert extract_json('Here:\n```json\n{"verdict":"approve","issues":[]}\n```')["verdict"] == "approve"
    print("core ok")
