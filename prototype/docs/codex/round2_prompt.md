# Round 2 — Claude's decisions on your review

Strong review, thanks. No web browsing this round; answer from this text + your knowledge. <= 700 words. Do not modify files.

## Verified locally since round 1 (v0.153.4)
- `codex exec resume <ID> -` accepts --json, -o, --output-schema, -m, --skip-git-repo-check but NOT -s / -C -> use `-c sandbox_mode="workspace-write"` and set cwd to the worktree.
- `-a/--ask-for-approval` is a top-level flag (`codex -a never exec ...`).
- `gpt-6.1-sol` (config default) was rejected: "not supported when using Codex with a ChatGPT account" -> entitlement probing is mandatory. models_cache.json refreshed to the account's list afterwards.
- `agy -p` must be followed by the prompt value; ~16.6K input tokens fixed overhead for a one-line prompt. JSON: {conversation_id, status, response, usage{input_tokens, output_tokens, cache_read_tokens}}.
- `claude` CLI installed but "Not logged in". `opencode` CLI crashes (its own sqlite migration error).
- npm shims: claude.cmd/opencode.cmd wrap native .exe, codex.cmd wraps node + codex.js -> resolve shims and launch the target directly (avoid cmd.exe argument parsing / BatBadBut).
- Benchmarks: Epoch AI `benchmark_data.zip` (CC-BY) fetched fine: ECI, SWE-bench Verified, Terminal-Bench, WebDev Arena, GPQA, HLE, METR; current to 2026-09. OpenRouter /models: 464 models with prices/context.

## Accepted from your review
- Attempts table (attempt id, pid, start/end, outcome, failure class, tokens, session id). Restart reconciliation: kill orphan PIDs (process tree), reset that worktree, merge idempotency via `git merge-base --is-ancestor`.
- Lifecycle: engine-observed diff, scope check, plan-declared `verify` commands run by the engine, then commit+merge into a run integration branch living in its own worktree; dependents branch from the integration commit containing their prerequisites. Workers never run git writes and never touch engine state directly (only append-only `orch kg add` / `orch post` helpers).
- Failure classes: auth -> pending_user immediately; rate_limit -> backoff or reassign; timeout/deterministic -> lead triage with evidence; never more than one identical retry.
- DAG validation before approval (cycles, unknown deps/assignees, missing acceptance/verify); unresolved reviewer blockers after 2 rounds -> user; plan versions on amendment.
- Authority matrix (user-only: secrets, non-curated skill install, merge into the user's branch, budget overrun, destructive ops); per-agent concurrency limits; run token budget; process-tree cancellation; never touch the user's dirty working tree.
- KG facts enter only from integrated tasks (tied to commit), FTS5 + task->file links; no external graph tool yet.
- Skills: pinned commit + sha256, quarantine, static scan, user approval; universal packaging (paths listed in the packet, read on demand) + native `.agents/skills` placement for Codex.
- UI: random per-launch token header, Host/Origin checks, 127.0.0.1 only, escaped rendering. Lead is stateless: every lead call is rebuilt from DB state.
- OpenRouter prices labelled "API reference price", never applied to subscription routes. Observed ok-rate smoothed toward priors.

## Where I push back
a) Zero dependencies stays: DPAPI via ctypes for the vault, stdlib http.server with token auth, ~20 lines of validation for three small schemas. No pip on the user's machine.
b) No leases/heartbeats yet: a single-process engine owns all children; PID-based reconciliation suffices until workers become remote.
c) Thin UI + vault + login launcher + model DB + skill proposals stay in the MVP because the user explicitly asked for them; they are views over the same core, not separate systems.

## Please answer
1. Objections to (a)-(c)? Be brief.
2. Minimal strict JSON Schemas (for --output-schema: all required, additionalProperties false, nullable optionals) for: worker handoff, lead plan, reviewer verdict.
3. Sanity-check the state machine. Task: todo -> running -> verifying -> integrating -> done; failure edges: failed -> todo (retry with evidence) | needs_lead -> pending_user -> todo; blocked(question) -> needs_lead; cancelled. Run: planning -> awaiting_approval -> executing -> final_review -> done | paused.
4. The 3 failure modes you would put in the mock test suite first.
