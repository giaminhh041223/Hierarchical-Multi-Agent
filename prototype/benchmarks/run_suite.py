"""Run the benchmark tasks with `orctram bench` and gather one summary.

    python benchmarks/run_suite.py --team my-team.json [--solo agent/model] [--repeat 3] [--mode auto] [--engine-solo] [--examiner] [--tasks 02 03]
    python benchmarks/run_suite.py --pool <suite dir> [<suite dir> ...]   (no agents: pool earlier rounds into one table)

For each task in benchmarks/tasks/: copy its seed into a fresh git repository under ORCH_HOME/bench-suite/<time>/<task>, give it
the team file, and run `bench` with the task's goal and its hidden checks (they live outside the repository, so no agent sees
them). Real agents spend quota: run it on your own machine, never in CI. Standard library only.

The summary ends with a pooled table: per task and arm, runs passing every check with a 95% Wilson interval, so 2/3 against
3/3 is not read as a difference. --pool builds that table from several suite directories (same team, same arm names)."""
import argparse, json, math, os, shutil, statistics, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # the directory holding the orch package
GIT = ["git", "-c", "user.name=orctram-bench", "-c", "user.email=bench@localhost", "-c", "commit.gpgsign=false"]


def tasks(only):
    found = sorted(p for p in (HERE / "tasks").iterdir() if (p / "goal.md").exists())
    return [p for p in found if not only or any(p.name.startswith(o) for o in only)]


def prepare(task, dest, team_file):
    shutil.copytree(task / "seed", dest)
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", f"seed of {task.name}"]):
        subprocess.run(GIT + args, cwd=dest, check=True, capture_output=True)
    (dest / ".orch").mkdir()
    shutil.copy(team_file, dest / ".orch" / "team.json")


def wilson(k, n, z=1.96):
    """95% interval of a pass rate k/n: honest for small n, where k/n alone overstates what 3 runs show."""
    if not n:
        return 0.0, 1.0
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def gather(suite_dirs):
    """{task: [bench samples]} from the result.json files of suite directories."""
    got = {}
    for d in map(Path, suite_dirs):
        for f in sorted(d.glob("*/.orch/bench/*/result.json")):
            got.setdefault(f.parents[3].name, []).extend(json.loads(f.read_text(encoding="utf-8")))
    return got


def pooled(results):
    lines = ["## Pooled: runs passing every check (95% Wilson interval), median tokens in", "",
             "| task | arm | passing | interval | tokens in |", "|---|---|---|---|---|"]
    for task, samples in sorted(results.items()):
        for arm in dict.fromkeys(s["arm"] for s in samples):
            xs = [s for s in samples if s["arm"] == arm]
            k = sum(all(ok for _, ok, _ in s["checks"]) for s in xs)
            lo, hi = wilson(k, len(xs))
            lines.append(f"| {task} | {arm} | {k}/{len(xs)} | {lo:.0%}-{hi:.0%} | {statistics.median(s['tokens_in'] for s in xs):,.0f} |")
    return lines + ["", "Overlapping intervals: the data cannot tell those arms apart yet; more runs or harder tasks can."]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--team", help="team JSON for the team arm (same format as .orch/team.json)")
    ap.add_argument("--pool", nargs="+", metavar="SUITE_DIR", help="no run: pool these earlier suite directories into one table")
    ap.add_argument("--solo", help="agent/model working alone (default: the team's lead)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--mode", action="append", default=[], help="also the team in this mode (auto | solo | team)")
    ap.add_argument("--engine-solo", action="store_true", help="also mode solo with the solo agent/model as its only worker")
    ap.add_argument("--examiner", action="store_true", help="also engine solo with the reviewer's acceptance tests first")
    ap.add_argument("--tasks", nargs="*", default=[], help="task name prefixes, e.g. 01 03 (default: all)")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args(argv)
    if a.pool:
        print("\n".join(pooled(gather(a.pool))))
        return 0
    if not a.team:
        ap.error("--team is required (or --pool to only pool earlier rounds)")
    home = Path(os.environ.get("ORCH_HOME") or Path.home() / ".orchestra")
    out = home / "bench-suite" / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""), "PYTHONIOENCODING": "utf-8"}
    parts = [f"# Benchmark suite {out.name}", "", f"Team: `{Path(a.team).name}`; solo: `{a.solo or 'the lead'}`; repeat: {a.repeat}", ""]
    failed = []
    for task in tasks(a.tasks):
        repo = out / task.name
        prepare(task, repo, a.team)
        cmd = [sys.executable, "-m", "orch", "--ws", str(repo), "bench", (task / "goal.md").read_text(encoding="utf-8").strip(),
               "--repeat", str(a.repeat), "--timeout", str(a.timeout)]
        for c in sorted((task / "checks").glob("*.py")):
            cmd += ["--check", f'python "{c.as_posix()}"']  # from the result's root; the file stays outside the repository
        cmd += [x for m in a.mode for x in ("--mode", m)] + (["--solo", a.solo] if a.solo else []) + (["--engine-solo"] if a.engine_solo else []) + (["--examiner"] if a.examiner else [])
        print(f"== {task.name}", flush=True)
        r = subprocess.run(cmd, cwd=ROOT, env=env)
        reports = sorted((repo / ".orch" / "bench").glob("*/report.md"))
        if r.returncode or not reports:
            failed.append(task.name)
            parts += [f"## {task.name}", "", f"bench failed (exit {r.returncode}); see {repo}", ""]
            continue
        body = reports[-1].read_text(encoding="utf-8").split("\n", 1)[1]
        parts += [f"## {task.name}", body.strip(), ""]
    parts += pooled(gather([out]))
    summary = out / "summary.md"
    summary.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
    print(f"\n-> {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
