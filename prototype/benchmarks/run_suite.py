"""Run the benchmark tasks with `orctram bench` and gather one summary.

    python benchmarks/run_suite.py --team my-team.json [--solo agent/model] [--repeat 3] [--mode auto] [--engine-solo] [--tasks 02 03]

For each task in benchmarks/tasks/: copy its seed into a fresh git repository under ORCH_HOME/bench-suite/<time>/<task>, give it
the team file, and run `bench` with the task's goal and its hidden checks (they live outside the repository, so no agent sees
them). Real agents spend quota: run it on your own machine, never in CI. Standard library only."""
import argparse, json, os, shutil, subprocess, sys, time
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--team", required=True, help="team JSON for the team arm (same format as .orch/team.json)")
    ap.add_argument("--solo", help="agent/model working alone (default: the team's lead)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--mode", action="append", default=[], help="also the team in this mode (auto | solo | team)")
    ap.add_argument("--engine-solo", action="store_true", help="also mode solo with the solo agent/model as its only worker")
    ap.add_argument("--tasks", nargs="*", default=[], help="task name prefixes, e.g. 01 03 (default: all)")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args(argv)
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
        cmd += [x for m in a.mode for x in ("--mode", m)] + (["--solo", a.solo] if a.solo else []) + (["--engine-solo"] if a.engine_solo else [])
        print(f"== {task.name}", flush=True)
        r = subprocess.run(cmd, cwd=ROOT, env=env)
        reports = sorted((repo / ".orch" / "bench").glob("*/report.md"))
        if r.returncode or not reports:
            failed.append(task.name)
            parts += [f"## {task.name}", "", f"bench failed (exit {r.returncode}); see {repo}", ""]
            continue
        body = reports[-1].read_text(encoding="utf-8").split("\n", 1)[1]
        parts += [f"## {task.name}", body.strip(), ""]
    summary = out / "summary.md"
    summary.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
    print(f"\n-> {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
