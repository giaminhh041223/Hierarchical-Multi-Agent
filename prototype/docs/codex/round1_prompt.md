# Co-design request from Claude (lead) to Codex (reviewer)

Project codename: "Orchestra" — a local, n8n-inspired multi-agent orchestrator.

## User requirements (translated from Vietnamese)
1. A lead agent (strongest available model) receives requests directly from the user.
2. Resource discovery: scan the machine for installed agent CLIs/clients (codex, claude code, opencode, antigravity `agy`, z.ai/GLM via API, ...), logged-in accounts, available models, API keys; then ask the user which models to use.
3. Set up a workspace folder: per-worker rules, shared communication channels, optimized for context windows, tokens, time — while keeping quality maximal.
4. Lead + a reviewer worker co-write a detailed plan first; then the lead dispatches tasks to workers that collaborate.
5. Errors/notifications: lead handles them; if beyond its authority -> escalate to the user (ping). Failed tasks go "pending" awaiting a response while the lead keeps scheduling other tasks.
6. UI area to enter API keys / connection env, and to log in agent accounts.
7. Built-in model benchmark DB so the lead can pick/assign models without web lookups; ideally its own growing "model knowledge network".
8. A "Skill Architect" agent per project: searches GitHub for strong skills/plugins fitting the project, installs and distributes them to workers.
9. Ideally a knowledge graph shared by all agents for fast knowledge access and resource savings.

## Machine facts (verified today, 2026-10-02)
- Windows 11, Git Bash, Python 3.13, Node 24, git 2.47. No gh CLI.
- claude 2.1.281: `claude -p --output-format json --model X` (prompt via stdin)
- codex-cli 0.153.4: `codex exec --json -o last.md --output-schema schema.json -s workspace-write -C dir`, `codex exec resume <id>`
- opencode 1.17.7: `opencode run --format json -m provider/model --dir D`; ~85 models via OpenCode Zen (gpt, claude, gemini, glm, kimi, qwen, deepseek, grok, minimax...)
- Antigravity CLI `agy` 1.2.14: `agy -p --output-format json --json-schema S --model M --mode accept-edits`; `agy models` lists gemini-3.x, claude-sonnet-4-6, claude-opus-4-6, gpt-oss-120b
- ~/.codex/models_cache.json lists gpt-6.x / gpt-5.x with context windows

## My draft architecture
Core idea: a deterministic engine (like n8n's workflow engine) + LLM judgment only at decision points. The lead does NOT babysit processes.

Python stdlib only (zero deps), one SQLite file per workspace.
- Adapters (data-driven JSON, not classes): per CLI — detect cmd, version cmd, models cmd, headless command template, output parser, login cmd, env needs. Prompt via stdin (Windows argv limit).
- `orch discover` -> resources.json (CLIs, versions, auth hints by file *existence* only, models, which API-key env vars are present).
- Vault: ~/.orchestra/vault.json (outside repos); keys injected only into the env of workers that need them (least privilege), redacted in logs. `orch login <agent>` opens the CLI's own login flow in a new console (we never handle passwords).
- Model DB: catalog/models.json = {id, via[], context, price, scores{bench:{value,source,as_of}}, tiers{plan,code,review,docs,speed,cost}}. `orch models refresh` pulls pricing/context from OpenRouter's public API + merges CLI model lists. Our own run history (success rate, tokens, wall time per role) accumulates -> "own model network".
- Workspace `<project>/.orch/`: team.json, rules/<worker>.md, orch.db (tasks, events/channel, kg), skills/, runs/<task>/ (packet.md, raw output, handoff.json), wt/ (git worktrees).
- Planning: lead drafts plan JSON (task DAG: id, title, role, assignee, deps, acceptance, scope paths, complexity) -> reviewer critiques (structured issues) -> lead revises (max 2 rounds) -> plan frozen; user approves.
- Skill Architect: detects stack, proposes skills from curated sources (anthropics/skills, awesome lists, MCP registry) + GitHub search; quarantine + user approval; installs into .orch/skills/<name>/SKILL.md; worker rules list name+description only (progressive disclosure), full file read on demand.
- Execution: scheduler runs ready tasks in parallel (bounded), each in its own git worktree/branch. Worker gets a compact "task packet" = stable prefix (rules) + task + acceptance + dependency handoffs (<=N tokens each) + top-k KG facts (FTS). Never full transcripts.
- Handoff contract: worker must end with JSON {status: done|blocked|failed, summary, files, decisions[], facts[], question?}. Engine stores it, merges the branch (serialized lock); conflicts -> lead task.
- Failure policy: retry once -> lead triage (retry/reassign/split/escalate) -> `pending_user` (inbox + notification); dependents blocked, independent tasks continue. `orch answer <task> "..."` requeues with the answer.
- KG: SQLite entities/relations/facts + FTS5; workers may call `orch kg search/add` via shell; engine auto-injects top-k relevant facts into packets; lead seeds a repo map.
- Channel: append-only events table (task_started, handoff, question, escalation, merge, ...). Workers can `orch post`. Web UI polls it.
- UI: `orch ui` -> stdlib http.server + one HTML file: resources, vault form, team picker, DAG board (n8n-like nodes), event log, inbox with answer form, KG browser.
- Mock adapter for zero-cost end-to-end tests.

## What I want from you
Be a critical reviewer / co-architect, not a cheerleader. Reply in English, structured, <= 1200 words. Do not modify any files.
1. Top 5 weaknesses/risks in this design and your fix for each.
2. Codex-CLI-specific integration advice for v0.153 on Windows: flags for unattended workers, sandbox behavior on Windows, structured output via --output-schema, session resume for follow-ups, where token usage appears in --json events, AGENTS.md / skills discovery paths, MCP. Mark anything you are unsure about.
3. Concrete context/token-saving techniques, ranked by impact.
4. Knowledge graph: what is the minimal version that is actually useful vs. hype? SQLite FTS, embeddings, or an existing tool (MCP memory server, Graphiti, LightRAG)?
5. Skill Architect: best sources + a safety process (prompt injection / supply chain).
6. Model benchmark DB: which data sources are reliable and fetchable; schema suggestions; how to learn from our own runs.
7. Your proposed MVP cut (what to build in the first prototype today) vs. later phases.
8. Anything important I missed.
