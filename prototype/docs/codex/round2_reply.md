**1. Objections to (a)–(c)**

- **(a) Accepted, with limits.** Validate three fixed contracts; don’t implement general JSON Schema in 20 lines. Reject unknown keys, wrong types, oversized payloads, duplicate JSON keys, and nonfinite numbers. DPAPI protects storage, not secrets from code running as the same user. Add request-size limits and socket timeouts to `http.server`.
- **(b) No leases needed yet; PID-only reconciliation is insufficient.** PIDs get reused. Enforce one engine per workspace with an OS lock; identify children by PID plus creation time. Prefer Windows Job Objects for process-tree ownership. Preserve attempt evidence before resetting worktrees.
- **(c) Accepted.** Keep those user-facing features, but implement model selection manually and skill proposals as reviewable records. Broken or unauthenticated adapters should remain visible with their failure reason.

**2. Minimal strict schemas**

These constrain output shape; semantic checks remain engine responsibilities. The engine supplies attempt IDs, plan versions, provenance, and commit IDs.

Worker handoff:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "summary", "files", "decisions", "facts", "question"],
  "properties": {
    "status": {"type": "string", "enum": ["done", "blocked", "failed"]},
    "summary": {"type": "string"},
    "files": {"$ref": "#/$defs/strings"},
    "decisions": {"$ref": "#/$defs/strings"},
    "facts": {"$ref": "#/$defs/strings"},
    "question": {"type": ["string", "null"]}
  },
  "$defs": {
    "strings": {"type": "array", "items": {"type": "string"}}
  }
}
```

Lead plan; each `verify` entry is an argv array, executed from the worktree root:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["tasks"],
  "properties": {
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "title", "assignee", "deps", "acceptance", "scope_paths", "verify"],
        "properties": {
          "id": {"type": "string"},
          "title": {"type": "string"},
          "assignee": {"type": "string"},
          "deps": {"$ref": "#/$defs/strings"},
          "acceptance": {"$ref": "#/$defs/strings"},
          "scope_paths": {"$ref": "#/$defs/strings"},
          "verify": {
            "type": "array",
            "items": {"$ref": "#/$defs/strings"}
          }
        }
      }
    }
  },
  "$defs": {
    "strings": {"type": "array", "items": {"type": "string"}}
  }
}
```

Reviewer verdict:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["verdict", "issues"],
  "properties": {
    "verdict": {"type": "string", "enum": ["approve", "revise"]},
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["task_id", "severity", "message"],
        "properties": {
          "task_id": {"type": ["string", "null"]},
          "severity": {"type": "string", "enum": ["blocker", "advisory"]},
          "message": {"type": "string"}
        }
      }
    }
  }
}
```

Engine checks: nonempty task IDs/titles/acceptance/verification commands, unique IDs, valid references, normalized paths within scope, and verdict consistency. `blocked` requires a nonempty question; other statuses require `question:null`. Treat `done` as “ready for verification.”

Verification commands execute repository code: run them under worker-equivalent restrictions, never with the engine’s credential environment.

**3. State-machine corrections**

The happy path works. Make failure routing explicit:

- From `running`, `verifying`, or `integrating`, record an attempt outcome, then transition to `todo`, `needs_lead`, `pending_user`, or terminal `failed`. Avoid a transient `failed` state that also means terminal failure.
- `needs_lead → todo | pending_user | failed | cancelled`; `pending_user → todo | cancelled`. Rate-limited tasks can remain `todo` with `eligible_at`.
- Dependency waiting is a scheduling condition, distinct from a worker question.
- Recovery during `integrating` must reconcile the **exact recorded commit** before resetting anything. An ancestry check cannot identify an unrecorded commit or validate the current combined tree.
- `done` requires persisted integration and validation evidence. Validate combined changes again at final review.
- Add run `failed` and `cancelled`; define whether pause drains or cancels running attempts. Final-review rejection returns to executing through a recorded amendment.
- Run completion and merging into the user’s branch are separate actions.

**4. First three mock tests**

1. **Crash during integration:** crash after Git merge succeeds but before SQLite commits. Restart must record one integration, preserve evidence, and release dependents exactly once.
2. **Untrustworthy completion:** valid JSON claims `done`, but an out-of-scope diff or failed verification exists. No merge, published facts, or dependent execution.
3. **Blocked branch, live sibling:** one worker hits authentication failure; another completes. Answering the first task requeues it once without rerunning completed work.