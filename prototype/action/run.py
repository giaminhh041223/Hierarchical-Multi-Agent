"""Entry point of the Hoatau GitHub Action (action.yml): set the team, run the goal, publish the verified result.
Inputs arrive as HOATAU_* environment variables; outputs go to $GITHUB_OUTPUT, the report to $GITHUB_STEP_SUMMARY.
Standard library only; runs from the repository to work on (the step's working-directory)."""
import os, sqlite3, subprocess, sys
from pathlib import Path


def gh_write(var, text):
    path = os.environ.get(var)
    if path:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)


def output(key, value):
    gh_write("GITHUB_OUTPUT", f"{key}={value}\n")  # single-line values only


def hoatau(ws, *args):
    return subprocess.run([sys.executable, "-m", "orch", "--ws", str(ws), *args]).returncode


def git(ws, *args):
    r = subprocess.run(["git", *args], cwd=ws, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"git {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()[-500:]}")
    return r.stdout.strip()


def main():
    ws = Path.cwd()
    goal, team = os.environ.get("HOATAU_GOAL", "").strip(), os.environ.get("HOATAU_TEAM", "").strip()
    if not goal or not team:
        raise SystemExit("inputs goal and team are required")
    auto, open_pr = os.environ.get("HOATAU_AUTO_APPROVE", "true") == "true", os.environ.get("HOATAU_OPEN_PR", "true") == "true"
    base = os.environ.get("HOATAU_BASE") or os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") \
        or git(ws, "rev-parse", "--abbrev-ref", "HEAD")
    if hoatau(ws, "init", "--yes", "--team", team):
        raise SystemExit(f"the team file {team} is not usable (see above)")
    hoatau(ws, "doctor")  # a readiness report in the log; a run failure below says what went wrong
    code = hoatau(ws, "run", goal, *(["--yes"] if auto else []), "--exit-on-wait")
    db = sqlite3.connect(ws / ".orch" / "orch.db")
    try:
        run = db.execute("SELECT v FROM meta WHERE k='run'").fetchone()[0]
    finally:
        db.close()
    status = {0: "done", 3: "waiting"}.get(code, "failed")
    output("run", run)
    output("status", status)
    report = ws / ".orch" / "runs" / run / "report.md"
    gh_write("GITHUB_STEP_SUMMARY", (report.read_text(encoding="utf-8") if report.exists() else f"run {run}: {status}") + "\n")
    if status != "done":
        hoatau(ws, "inbox")
        raise SystemExit(f"run {run}: {status}" + (" (it needed a human: answer locally, or set verify_allow / budget in the team)"
                                                    if status == "waiting" else ""))
    if not open_pr:
        return print(f"run {run}: done on branch orch/{run}/main (open-pr is false)")
    branch = f"hoatau/{run}"
    git(ws, "push", "origin", f"orch/{run}/main:refs/heads/{branch}")
    output("branch", branch)
    url = subprocess.run(["gh", "pr", "create", "--base", base, "--head", branch, "--title", f"Hoatau: {goal.splitlines()[0][:72]}",
                          "--body-file", str(report)], cwd=ws, capture_output=True, text=True)
    if url.returncode:
        raise SystemExit(f"pushed {branch}, but the pull request failed: {(url.stderr or url.stdout).strip()[-500:]}")
    output("pr-url", url.stdout.strip().splitlines()[-1])
    print(f"run {run}: done, pull request {url.stdout.strip()}")


if __name__ == "__main__":
    main()
