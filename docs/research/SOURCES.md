# Danh mục nguồn nghiên cứu

Ngày lập: **02/10/2026**. Đây là registry nguồn ban đầu, không phải danh sách tính năng đã chứng minh. `opened` chỉ nghĩa trang đã được truy cập trong khảo sát hiện tại/trước đó; không chứng minh toàn bộ nội dung đúng với version cài local. Hai nguồn `fetch_failed` phải được Gemini lấy lại có giới hạn hoặc để UNKNOWN, không được đọc search snippet rồi tuyên bố đã đọc trang.

## Cách dùng

- Dùng ID Sxx trong claims/result; URL/heading cụ thể phải có ở evidence.
- Repository/đường dẫn `main` là mutable. G01 tạo source-lock bằng commit thật đã resolve; chỉ dùng permalink có commit thật cho CODE_TRACED.
- Tài liệu web: ghi URL sau redirect, heading/section, ngày lấy và snapshot/hash nếu lưu. Không gán một commit giả cho trang web.
- Nhà phát hành mô tả tính năng là DOCUMENTED. CODE_TRACED cần đọc implementation; OBSERVED cần thao tác thực có transcript. Test có trong repo nhưng chưa chạy chỉ là TEST_DEFINED.
- Tài liệu Cloud của Dify không tự chứng minh tính năng self-host. API key, account CLI và quota là các nguồn riêng.
- Nguồn mới chỉ để trả lời câu hỏi task; thêm tối đa hai nguồn primary trực tiếp liên quan mỗi task và ghi lý do. Không làm một danh sách link vô hạn.
- Không sao chép cả README hoặc bảng leaderboard. Tóm tắt ngắn, giữ locator; không quá 25 từ trích trực tiếp từ một nguồn.

## Dự án tham khảo

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S01 | [Orkestra repository](https://github.com/andyyaro/orkestra) | director, scheduler, adapters; pin source before code claims | opened |
| S02 | [Orkestra architecture](https://github.com/andyyaro/orkestra/blob/main/docs/architecture/ARCHITECTURE.md) | architecture assertions; verify against pinned code | opened |
| S03 | [Orkestra security model](https://github.com/andyyaro/orkestra/blob/main/docs/SECURITY_MODEL.md) | permission boundaries and stated limitations | opened |
| S04 | [Agent Orchestrator repository](https://github.com/Untrivial-ai/agent-orchestrator) | desktop, daemon, sessions; former ComposioHQ redirect | opened |
| S05 | [Stoneforge repository](https://github.com/stoneforge-ai/stoneforge) | roles, tasks, communications, experimental defaults | opened |
| S06 | [Stoneforge multi-provider](https://docs.stoneforge.ai/guides/multi-provider/) | provider/account ownership and adapter claims | opened |
| S07 | [Vibe Kanban repository](https://github.com/BloopAI/vibe-kanban) | UI reference only; maintenance status needs S08 | opened |
| S08 | [Vibe Kanban shutdown announcement](https://www.vibekanban.com/blog/shutdown) | company closure versus continuing local/community project | opened |

## Client và giao thức

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S19 | [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) | exec protocol; actual installed version must be checked | opened |
| S20 | [Codex App Server](https://learn.chatgpt.com/docs/app-server) | session/event/approval protocol | opened |
| S21 | [Codex authentication](https://learn.chatgpt.com/docs/auth) | account-backed versus API billing | opened |
| S22 | [Antigravity headless CLI](https://antigravity.google/docs/cli/headless/) | events, cumulative usage, soft denial, terminal statuses | opened |
| S23 | [Antigravity permissions](https://antigravity.google/docs/permissions/) | tool rights versus terminal containment | opened |
| S24 | [Antigravity installation/auth](https://antigravity.google/docs/cli/install/) | official account login versus Gemini API mode; do not modify settings | opened |
| S25 | [Antigravity model catalog documentation](https://antigravity.google/docs/models/) | catalog does not establish individual entitlement | opened |
| S26 | [Antigravity CLI reference](https://antigravity.google/docs/cli/reference/) | version-specific flags/settings; reconcile docs/help mismatches | opened |
| S27 | [OpenCode CLI](https://opencode.ai/docs/cli/) | run/version/session options | opened |
| S28 | [OpenCode server](https://opencode.ai/docs/server/) | OpenAPI, sessions, events, auth; no server launch in research | opened |
| S29 | [OpenCode permissions](https://opencode.ai/docs/permissions/) | tool policy and external-directory rights | opened |

## API model

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S41 | [OpenAI API reference overview](https://developers.openai.com/api/reference/overview) | canonical API reference navigation | opened |
| S42 | [OpenAI Responses REST create](https://developers.openai.com/api/reference/resources/responses/methods/create) | fetch failed due page size; retrieve bounded official documentation before schema claims | fetch_failed |
| S43 | [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create) | request/response, headers, usage, tools and error envelopes | opened |
| S44 | [Gemini API overview](https://ai.google.dev/api) | compare current primitives; do not assume older recommendation is current | opened |
| S45 | [Z.AI API quick start](https://docs.z.ai/guides/overview/quick-start) | endpoint/key scope and API family | opened |
| S46 | [Z.AI OpenCode integration](https://docs.z.ai/devpack/tool/opencode) | Coding Plan versus general API connection | opened |
| S48 | [Gemini generateContent reference](https://ai.google.dev/api/generate-content) | search result available, full fetch failed; use index to retrieve before quoting schema | fetch_failed |
| S49 | [OpenAI CLI Responses create reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) | CLI wrapper documentation; do not silently treat --flags as REST JSON fields | opened |

## Workflow, key và ngân sách

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S09 | [Dify self-host deployment](https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose) | self-host architecture and dependencies; do not deploy | opened |
| S10 | [Dify model providers (Cloud docs)](https://docs.dify.ai/en/cloud/use-dify/workspace/model-providers) | credentials and model management; cloud/self-host boundary | opened |
| S11 | [Dify Human Input (Cloud docs)](https://docs.dify.ai/en/cloud/use-dify/nodes/human-input) | pause/resume mechanics; verify edition and version | opened |
| S16 | [LiteLLM virtual keys](https://docs.litellm.ai/docs/proxy/virtual_keys) | key scope, model access, edition constraints | opened |
| S17 | [LiteLLM routing](https://docs.litellm.ai/docs/routing) | fallback, retry and routing ownership | opened |
| S18 | [LiteLLM budgets/rate limits](https://docs.litellm.ai/docs/proxy/users) | database requirements, enforcement semantics and license | opened |

## Framework điều phối

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S12 | [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) | framework responsibilities versus application responsibilities | opened |
| S13 | [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | RAM versus durable checkpoints; store scope | opened |
| S14 | [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | resume, replay and side effects | opened |
| S15 | [CrewAI processes](https://docs.crewai.com/en/concepts/processes) | manager/worker hierarchy; not proof of CLI confinement | opened |

## Git, persistence và Windows

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S32 | [Git worktree](https://git-scm.com/docs/git-worktree) | Git isolation, lifecycle; not OS security | opened |
| S33 | [SQLite WAL](https://www.sqlite.org/wal.html) | writer/concurrency and persistence tradeoffs | opened |
| S35 | [Windows Credentials Management](https://learn.microsoft.com/en-us/windows/win32/secauthn/credentials-management) | native credential ownership and lifetime | opened |
| S36 | [Windows CryptProtectData / DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) | user/machine scope and limitations | opened |
| S37 | [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) | process lifecycle; do not call this a filesystem sandbox | opened |
| S47 | [SQLite transactions](https://www.sqlite.org/lang_transaction.html) | atomic state/event updates and crash windows | opened |

## Skill và công cụ

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S30 | [Agent Skills specification](https://agentskills.io/specification) | manifest, resources and compatibility | opened |
| S31 | [MCP specification](https://modelcontextprotocol.io/specification/2026-07-28) | version resolved from /latest; tool/service permission boundary | opened |

## Retrieval

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S34 | [SQLite FTS5](https://www.sqlite.org/fts5.html) | bounded lexical retrieval baseline | opened |

## Benchmark và đánh giá

| ID | Nguồn | Câu hỏi dùng để nghiên cứu | Fetch |
|---|---|---|---|
| S38 | [SWE-bench](https://www.swebench.com/) | harness/model/setup and comparable metrics | opened |
| S39 | [Terminal-Bench](https://www.tbench.ai/) | terminal-agent benchmark; extract methodology, no leaderboard copying | opened |
| S40 | [Artificial Analysis methodology](https://artificialanalysis.ai/methodology) | index definition, latency/cost setup and freshness | opened |

## Điểm cần đối chiếu ngay

1. Orkestra README có một mô tả về JSON flag Antigravity, còn tài liệu headless chính thức hiện mô tả output JSON. G08/G10 phải so revision/ngày/version; không tự chọn một nguồn làm đúng cho tất cả version.
2. Nhà cung cấp CLI có thể trả exit code thành công dù một tool bị từ chối. G10 phải phân biệt thành công inference và đạt acceptance criteria của task.
3. Chỉ có version/catalog trong khảo sát local; auth, quota và inference của tài khoản chưa được kiểm chứng.
4. Source URL tải quá lớn/lỗi fetch là hạn chế truy cập của phiên nghiên cứu, không phải bằng chứng API không tồn tại.


