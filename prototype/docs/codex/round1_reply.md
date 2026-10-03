Keep the deterministic engine, but prioritize **recoverable execution and verified integration** over the graph, visual canvas, and automatic skill installation. No files modified.

**1. Top five weaknesses and fixes**

1. **The scheduler lacks crash semantics.** A crash between spawning, committing, merging, and updating SQLite can duplicate work. Separate tasks from attempts; use transactional claims, leases, heartbeats, attempt IDs, deadlines, and restart reconciliation. Record merge intent and resulting commit. Never blindly retry an operation with uncertain external effects.

2. **Credential isolation is overstated.** An out-of-repo plaintext vault and selective environment injection do not isolate secrets from worker subprocesses. Prefer Windows Credential Manager/DPAPI for storage, sanitized environment allowlists, and separate execution identities or credential brokers where needed. Workers must not modify engine state directly. A worktree is not a security boundary.

3. **“Done” conflates generation, validation, and integration.** Introduce `produced → validated → integrated → accepted`. Require engine-observed diffs, tests, scope checks, and commit IDs. Start dependents from the integration commit containing their prerequisites. Serialized merging prevents concurrent Git operations, not semantic conflicts.

4. **JSON-only adapters and zero dependencies are false economies.** Keep declarative manifests, but implement versioned parser/process hooks behind a small interface. Windows launchers, streaming, cancellation, authentication, and resume differ substantially. Permit narrowly justified dependencies for schema validation, credential storage, and serving authenticated UI requests.

5. **Planning and retry rules are too rigid.** Validate DAG cycles, dependencies, permissions, budgets, and acceptance criteria before approval. Two review rounds must not silently accept unresolved blockers. Version amendments to frozen plans. Classify failures: authentication requires intervention; rate limits require backoff; deterministic failures rarely benefit from identical retries.

**2. Codex CLI integration**

**Version caveat:** Your v0.153.4 installation was inaccessible from this session. The following uses current official documentation; exact compatibility requires your local `--help` and adapter smoke tests.

Suggested invocation, with the packet written directly to UTF-8 stdin:

```text
codex -a never exec --json -s workspace-write -C <worktree> -m <model> --output-schema <schema.json> -o <handoff.json> -
```

Use absolute artifact paths, drain stdout/stderr concurrently, and implement process-tree cancellation. Explicit sandbox and approval settings are preferable to `--full-auto`; never use `--yolo` as an unattended-worker shortcut. [CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli)

- **Windows:** Current docs distinguish preferred `elevated` and fallback `unelevated` sandboxes. Elevated setup needs administrator approval; the fallback has weaker network isolation. Neither should be inferred from `workspace-write` alone. Verify filesystem/network restrictions and linked-worktree Git metadata access before scheduling. **Exact v0.153 behavior remains unverified.** [Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox)
- **Structured output:** `--json` produces events; `--output-schema` constrains the final response. Use required fields, `additionalProperties:false`, and nullable optional values. Independently validate the handoff and handle missing output, failure, or termination.
- **Usage:** Read `turn.completed.usage.input_tokens`, `cached_input_tokens`, and `output_tokens`. Current examples also contain `reasoning_output_tokens`; treat that field as optional/version-dependent. Preserve unknown fields.
- **Resume:** Save `thread.started.thread_id`; resume that explicit ID, never parallel-unsafe `--last`. Keep the same worktree and policy. Verify resume-specific flag support locally; do not assume every initial-exec flag is accepted. Resume preserves context, not free tokens. [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- **Instructions:** Global `$CODEX_HOME/AGENTS.override.md` takes precedence over `AGENTS.md`; project instructions accumulate from repository root to working directory. `.orch/rules` is not automatically discovered. [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- **Skills:** Current documented locations include ancestor `.agents/skills` directories and `~/.agents/skills`. **Verify legacy `~/.codex/skills` behavior in v0.153.** Explicitly expose approved skills in each worktree. [Skills](https://learn.chatgpt.com/docs/build-skills)
- **MCP:** STDIO and Streamable HTTP are supported; configuration lives in `~/.codex/config.toml` or trusted project `.codex/config.toml`. Allowlist servers/tools per role; complete authentication before unattended execution. [MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

**3. Context/token savings, ranked**

1. **Avoid unnecessary agents and turns:** batch cohesive changes; reserve reviewer calls for meaningful checkpoints.
2. **Send evidence references:** paths, symbols, commit IDs, test results, and focused excerpts; retrieve more on demand.
3. **Use bounded handoffs:** conclusions, unresolved issues, evidence, and artifact pointers. Never recursively summarize summaries.
4. **Control tool output:** search before reading, cap logs, deduplicate errors, retain full artifacts outside prompts.
5. **Keep prefixes stable:** rules and tool definitions first; changing task content last. Measure cache hits.
6. **Reset deliberately:** resume tightly related work; start fresh when stale history exceeds its value. Reserve context for execution and verification.

**4. Minimal useful knowledge layer**

Start with SQLite facts/decisions plus FTS5 and filters for project, task, path, and revision. Store `source`, `commit`, `author`, `verified_at`, `status`, and `supersedes`. Worker assertions enter as candidates, not authoritative facts. Check FTS5 availability at startup.

Add explicit relations only for useful queries such as “what depends on this interface?” Add embeddings only after measuring lexical retrieval misses.

[MCP memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) supplies basic entities/relations; [Graphiti](https://github.com/getzep/graphiti) adds temporal graph machinery; [LightRAG](https://github.com/HKUDS/LightRAG) targets graph-assisted retrieval. My recommendation: none for today’s prototype.

**5. Skill Architect**

Prefer maintained first-party sources such as [Anthropic’s skills](https://github.com/anthropics/skills), vendor repositories, and official catalogs. Use [MCP Registry](https://registry.modelcontextprotocol.io/) for server discovery; awesome lists are leads, not trust endorsements.

Download without execution; pin commits and dependency versions; inspect scripts, hooks, links, licenses, and permissions; test in a disposable environment without credentials. Approve exact hashes/capabilities and review updates separately. Treat instructions, tool descriptions, and retrieved content as potential injection surfaces. Distribution requires adapter-specific packaging, not merely copying `SKILL.md`.

**6. Model database**

Separate **model**, **provider route**, **account entitlement**, and **observations**. A listed model or existing auth file does not prove usable access.

Use provider documentation for authoritative limits/pricing, [OpenRouter’s API](https://openrouter.ai/docs/api/api-reference/models/get-models) for its catalog/routes, and [Artificial Analysis](https://artificialanalysis.ai/data-api/docs) for independently measured benchmarks, subject to access and licensing.

Store source timestamps, units, context/output limits, cache pricing, benchmark/harness versions, reasoning settings, sample counts, and uncertainty. Never apply OpenRouter prices to subscription CLI usage.

Learn from accepted outcomes, rework, regressions, latency, and total attempt cost. Compare similar task classes; retain failures and use shrinkage toward benchmark priors rather than ranking tiny samples.

**7. MVP cut**

Today: mock adapter plus two real CLIs; manual team selection; lead/reviewer planning; approved DAG; SQLite attempts/events; two-worker scheduling; isolated worktrees; validation/integration gate; pending-user inbox; restart recovery.

Test crash-after-commit, malformed handoff, timeout, and merge conflict.

Next: secured UI, account setup, FTS memory, model observations. Later: skill automation, adaptive routing, embeddings, graph traversal, visual workflow editing.

**8. Missing essentials**

Define an authority matrix, global/account concurrency and spending limits, cancellation semantics, artifact retention, dirty-repository handling, and plan amendment rules. Secure localhost UI with authentication, Origin/Host checks, CSRF protection, and escaped event rendering. Make the lead replaceable: durable state must let another model reconstruct outstanding decisions without its transcript.