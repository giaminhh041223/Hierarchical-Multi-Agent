"""Skills: a curated index (GitHub repos pinned to a commit + skills already installed for local agent CLIs), the skill
architect's per-task picks, and placement into worker worktrees (.agents/skills/orch-<name>/, git-excluded).
Non-curated proposals are only recorded; the user approves a repo, which then joins the sources for the next refresh."""
import hashlib, json, re, shutil, time, urllib.request
from pathlib import Path

from .core import CATALOG, HOME, contract

CACHE = HOME / "skills"
INDEX = CACHE / "index.json"
USER_SOURCES = CACHE / "sources.json"  # repos the user approved
LOCAL_DIRS = [Path.home() / d / "skills" for d in (".claude", ".codex", ".agents")]
MAX_FILE, MAX_SKILL = 1_000_000, 5_000_000
RISKY = re.compile(r"curl |wget |Invoke-WebRequest|iwr |rm -rf|base64 -d|eval\(|exec\(|subprocess|os\.system", re.I)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "orchestra", "Accept": "application/vnd.github+json"})
    data = urllib.request.urlopen(req, timeout=30).read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError(f"{url}: larger than {MAX_FILE} bytes")
    return data


def frontmatter(text):
    """Top-level `key: value` pairs of a SKILL.md YAML header; folded / indented continuation lines are joined."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    pairs = re.findall(r"^([\w-]+):[ \t]*(.*)\n?((?:[ \t]+\S.*\n?)*)", m.group(1) + "\n" if m else "", re.M)
    return {k: " ".join((re.sub(r"^[>|][-+]?$", "", v.strip()) + " " + more).split()).strip("'\"") for k, v, more in pairs}


def sources():
    user = json.loads(USER_SOURCES.read_text(encoding="utf-8")) if USER_SOURCES.exists() else []
    return json.loads((CATALOG / "skills.json").read_text(encoding="utf-8"))["sources"] + user


def refresh():
    """Index every SKILL.md under each source's prefix (1-2 GitHub API calls per repo) and in local skill folders."""
    index = []
    for s in sources():
        sha = s["ref"] if re.fullmatch(r"[0-9a-f]{40}", s["ref"]) else json.loads(_get(f"https://api.github.com/repos/{s['repo']}/commits/{s['ref']}"))["sha"]
        # ponytail: a truncated tree (>100k entries) indexes partially; walk sub-trees if a source ever gets that big
        tree = json.loads(_get(f"https://api.github.com/repos/{s['repo']}/git/trees/{sha}?recursive=1"))["tree"]
        for f in tree:
            if f["path"].split("/")[-1] != "SKILL.md" or not f["path"].startswith(s.get("prefix", "")):
                continue
            d = f["path"].rpartition("/")[0]
            files = [x for x in tree if x["type"] == "blob" and x["path"].startswith(d + "/" if d else "")]
            if sum(x.get("size", 0) for x in files) > MAX_SKILL or len(files) > 60:
                continue
            meta = frontmatter(_get(f"https://raw.githubusercontent.com/{s['repo']}/{sha}/{f['path']}").decode("utf-8", "replace"))
            index.append({"id": f"{s['id']}/{meta.get('name') or d.split('/')[-1]}", "description": meta.get("description", "")[:300],
                          "repo": s["repo"], "sha": sha, "dir": d, "files": [x["path"] for x in files]})
    for root in LOCAL_DIRS:
        for f in sorted(root.glob("*/SKILL.md")) if root.exists() else []:
            meta = frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            index.append({"id": f"local/{meta.get('name') or f.parent.name}", "description": meta.get("description", "")[:300],
                          "local": str(f.parent)})
    CACHE.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return index


def load_index():
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else []


def install(s):
    """-> (folder, sha256 of all files, scan summary). GitHub skills are fetched once per pinned commit."""
    if "local" in s:
        path = Path(s["local"])
    else:
        path = CACHE / s["repo"].replace("/", "_") / s["sha"][:12] / (s["dir"] or "_root")
        if not (path / "SKILL.md").exists():
            tmp = path.with_name(path.name + ".part")
            shutil.rmtree(tmp, ignore_errors=True)
            for f in s["files"]:
                dst = tmp / f[len(s["dir"]) + 1 if s["dir"] else 0:]
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(_get(f"https://raw.githubusercontent.com/{s['repo']}/{s['sha']}/{f}"))
            tmp.rename(path)
    h, scripts, flags = hashlib.sha256(), [], []
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        data = f.read_bytes()
        h.update(f.relative_to(path).as_posix().encode() + b"\0" + data)
        if f.suffix in (".py", ".sh", ".js", ".ts", ".ps1", ".bat", ".cmd"):
            scripts.append(f.relative_to(path).as_posix())
        if RISKY.search(data.decode("utf-8", "ignore")):
            flags.append(f.relative_to(path).as_posix())
    return path, h.hexdigest(), f"scripts: {scripts[:8] or 'none'}; review-worthy patterns in: {flags[:8] or 'none'}"


def architect(e, t):
    """The SKILLS task: one cheap call picks 0-3 curated skills for specific tasks; returns a summary line."""
    index, plan = load_index(), e.latest_plan()
    if not index:
        return "no skill index yet (python -m orch skills refresh)"
    tasks = plan["plan"]["tasks"] if plan else []
    prompt = e.join(e.header("skill_architect", "SKILLS"), e.rules("common", "skill_architect"), contract("skills"), "---",
                    f"## Goal\n{e.goal}",
                    "## Tasks\n" + "\n".join(f"- {p['id']} [{p['assignee']}]: {p['title']} (scope: {', '.join(p['scope_paths'])})" for p in tasks),
                    "## Curated skill index (id: description)\n" + "\n".join(f"- {s['id']}: {s['description'][:200]}" for s in index))
    obj, _, _ = e.ask("skill_architect", e.team["skill_architect"], prompt, "skills", "SKILLS", "skills", e.main_wt)
    by_id, done = {s["id"]: s for s in index}, []
    for pick in obj["skills"][:3]:
        s, row = by_id.get(pick["id"]), None
        if s and e.team["skills"] == "propose":  # every pick waits for the user's answer (Engine.job_skills asks)
            row = (s.get("repo") or "local", s.get("repo") and f"https://github.com/{s['repo']}", s.get("sha"), "proposed", 1, None, None, None)
        elif s:
            try:
                path, digest, scan = install(s)
                row = (s.get("repo") or "local", s.get("repo") and f"https://github.com/{s['repo']}", s.get("sha"), "installed", 1, str(path), digest, scan)
            except (OSError, ValueError) as ex:
                e.ws.event("warn", f"skill {pick['id']} not installed: {ex}", "SKILLS")
        elif re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/?", pick["id"]):
            row = ("github", pick["id"], None, "proposed", 0, None, None, None)
            e.ws.event("skill", f"proposed {pick['id']}: {pick['reason'][:200]} (approve: python -m orch skills approve {pick['id']})", "SKILLS")
        if row:
            e.ws.x("INSERT OR REPLACE INTO skills(run, id, source, url, sha, status, curated, path, digest, scan, reason, tasks, updated) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", e.run, pick["id"], *row, pick["reason"][:500], json.dumps(pick["tasks"]), time.time())
            done.append(f"{pick['id']} ({row[3]})")
            if row[3] == "installed":
                e.ws.event("skill", f"installed {pick['id']} for {pick['tasks'] or 'all tasks'}; {row[7]}", "SKILLS")
    return "skills: " + (", ".join(done) or "none needed")


def settle(e, yes):
    """skills=propose: the user's one answer on the curated picks: install them all, or none."""
    by_id, done = {s["id"]: s for s in load_index()}, []
    for r in e.ws.q("SELECT id FROM skills WHERE run=? AND status='proposed' AND curated=1", e.run):
        status, path, digest, scan = "rejected", None, None, None
        if yes and r["id"] in by_id:
            try:
                (path, digest, scan), status = install(by_id[r["id"]]), "installed"
            except (OSError, ValueError) as ex:
                e.ws.event("warn", f"skill {r['id']} not installed: {ex}", "SKILLS")
        e.ws.x("UPDATE skills SET status=?, path=?, digest=?, scan=?, updated=? WHERE run=? AND id=?",
               status, path and str(path), digest, scan, time.time(), e.run, r["id"])
        done.append(f"{r['id']} ({status})")
    return "skills: " + (", ".join(done) or "none")


def place(ws, run, tid, wt):
    """Copy this task's installed skills into its worktree; returns the packet section listing them."""
    lines = []
    for r in ws.q("SELECT id, path, tasks FROM skills WHERE run=? AND status='installed'", run):
        if json.loads(r["tasks"] or "[]") not in ([], None) and tid not in json.loads(r["tasks"]):
            continue
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", r["id"].split("/")[-1])
        dst = Path(wt) / ".agents" / "skills" / f"orch-{name}"
        if not dst.exists():
            shutil.copytree(r["path"], dst)
        lines.append(f"- {r['id']}: .agents/skills/orch-{name}/SKILL.md")
    return "## Skills for this task (read the SKILL.md before relying on one)\n" + "\n".join(lines) if lines else ""


def decide(ws, sid, action):
    """approve | reject a proposed (non-curated) repo; an approved repo joins the sources for the next refresh."""
    if action not in ("approve", "reject") or not ws.q("SELECT id FROM skills WHERE run=? AND id=? AND status='proposed' AND curated=0", ws.run, sid):
        raise ValueError(f"no proposed skill {sid!r} in this run (see: python -m orch skills list)")
    ws.x("UPDATE skills SET status=?, updated=? WHERE run=? AND id=?", action + "d", time.time(), ws.run, sid)
    if action == "reject":
        return f"{sid} rejected"
    owner, repo = sid.rstrip("/").split("/")[-2:]
    user = [s for s in (json.loads(USER_SOURCES.read_text(encoding="utf-8")) if USER_SOURCES.exists() else []) if s["repo"] != f"{owner}/{repo}"]
    CACHE.mkdir(parents=True, exist_ok=True)
    USER_SOURCES.write_text(json.dumps(user + [{"id": owner, "repo": f"{owner}/{repo}", "ref": "HEAD"}], indent=1), encoding="utf-8")
    return f"{owner}/{repo} added to your skill sources; it is indexed (pinned to its current commit) on: python -m orch skills refresh"


def cli(ws, a):
    if a.action == "refresh":
        print(f"{len(refresh())} skills indexed -> {INDEX}")
    elif a.action in ("approve", "reject"):
        print(decide(ws, a.id, a.action))
    else:
        idx = load_index()
        print(f"index: {len(idx)} skills ({INDEX}); sources: {', '.join(s['repo'] for s in sources())} + local skill folders")
        for s in idx:
            print(f"  {s['id']:<40} {s['description'][:90]}")
        for r in ws.q("SELECT id, status, tasks, reason, scan FROM skills WHERE run=?", ws.run) if ws.run else []:
            print(f"* {r['status']:<9} {r['id']} tasks={r['tasks']} {r['reason'][:100]}" + (f"\n    {r['scan']}" if r["scan"] else ""))
