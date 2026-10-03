"""Scripted stand-in for an agent CLI (zero-cost tests). Speaks agy's JSON; behaviour comes from the ORCH_MOCK scenario file:
{"plan": [tasks], "amend": [tasks], "steps": {"<role>:<task>[@<model>]": [step, ...]}} - call n of a role/task uses step n, the last
repeats; a key with @model wins for that model.
step: {"write": {path: text}, "delete": [path], "sleep": s, "exit": code, "stderr": text, "raw": reply text, "reply": {fields},
"mcp": [tool, arguments] = call a tool on the orch MCP server named in the call's config; its text becomes the reply summary}"""
import json, os, re, subprocess, sys, time
from pathlib import Path


def default(role, task, sc):
    if role == "lead" and task == "PLAN":
        return {"tasks": sc.get("plan", [])}
    if role == "lead" and task == "AMEND":
        return {"tasks": sc.get("amend", [])}
    if role == "lead":
        return {"action": "retry", "note": "Try again, carefully.", "assignee": None, "question": None}
    if role == "reviewer":
        return {"verdict": "approve", "issues": []}
    if role == "skill_architect":
        return {"skills": []}
    return {"status": "done", "summary": f"mock work for {task}", "files": [], "decisions": [], "facts": [], "question": None}


def main():
    prompt = sys.stdin.buffer.read().decode("utf-8")
    m = re.match(r"ORCH-CALL role=(\S+) task=(\S+)", prompt)
    if not m:  # entitlement probe
        return print(json.dumps({"conversation_id": "mock:probe", "status": "SUCCESS", "response": "OK", "usage": {}}))
    role, task = m.groups()
    sc_file = Path(os.environ["ORCH_MOCK"])
    sc = json.loads(sc_file.read_text(encoding="utf-8"))
    state = Path(f"{sc_file}.state")
    state.mkdir(exist_ok=True)
    counter = state / f"{role}-{task}"
    # ponytail: unlocked counter; parallel calls of one role:task (pool pre-tests) may read it mid-write or share a step
    n = int(counter.read_text() or 0) if counter.exists() else 0
    counter.write_text(str(n + 1))
    with open(state / "calls.log", "a", encoding="utf-8") as f:
        f.write(f"{role} {task} {n + 1} {'resume' if len(sys.argv) > 2 else 'new'} {prompt.splitlines()[0]}\n")
    steps = sc.get("steps", {}).get(f"{role}:{task}@{sys.argv[1]}") or sc.get("steps", {}).get(f"{role}:{task}") or [{}]
    step = steps[min(n, len(steps) - 1)]
    for p, text in step.get("write", {}).items():
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        Path(p).write_text(text, encoding="utf-8")
    for p in step.get("delete", []):
        Path(p).unlink(missing_ok=True)
    time.sleep(step.get("sleep", 0))
    if "exit" in step:
        sys.stderr.write(step.get("stderr", "mock failure"))
        sys.exit(step["exit"])
    if "mcp" in step:  # what an agent CLI does: start the server from its per-call config, with a minimal env
        srv = json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])["mcp"]["orch"]
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": step["mcp"][0], "arguments": step["mcp"][1]}}]
        env = {**srv["environment"], **{k: os.environ[k] for k in ("SYSTEMROOT",) if k in os.environ}}
        out = subprocess.run(srv["command"], input="".join(json.dumps(m) + "\n" for m in msgs), capture_output=True,
                             encoding="utf-8", env=env, timeout=60).stdout
        step = {**step, "reply": {"summary": json.loads(out.splitlines()[-1])["result"]["content"][0]["text"], **step.get("reply", {})}}
    reply = {**default(role, task, sc), **step.get("reply", {})}
    if role == "worker" and "files" not in step.get("reply", {}):
        reply["files"] = list(step.get("write", {}))
    print(json.dumps({"conversation_id": f"mock:{role}:{task}", "status": "SUCCESS",
                      "response": step.get("raw", json.dumps(reply)), "usage": {"input_tokens": 1000, "output_tokens": 100}}))


if __name__ == "__main__":
    main()
