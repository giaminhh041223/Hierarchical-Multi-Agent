# Kế hoạch nghiên cứu kỹ thuật

## Mục tiêu và cách ra quyết định

Bóc tách source và contracts trước khi chọn nền. Output cần giúp lead giao implementation tasks đủ nhỏ, có quyền/scope/acceptance rõ. Đây là kế hoạch, không phải findings runtime; claims về reference dựa [source registry](SOURCES.md) phải được nâng bằng evidence trong G01–G15.

Không lấy “tối đa hiệu quả” làm lời hứa. RQ07 cần objective đo được: success theo acceptance, effort sửa lại, observed/estimated/unknown usage, elapsed time, traceability, phạm vi quyền. Benchmark/graph chỉ dùng nếu cải thiện workload được đo, không ép thành nền ban đầu.

## 1. Những đường đi phải bóc tách

| Flow | Task | Cần xác định | Failure boundary |
|---|---|---|---|
| User → lead → plan → reviewer | G02/G04/G06/G17 | Proposal vs accepted plan; revisions; state owner | Reviewer rejection, plan scope drift |
| DAG → dispatch → worker → artifact | G02/G04/G06/G16/G17 | Attempt/session identity, dependency guards, event/result contract | Duplicate dispatch, late/out-of-order events |
| Worker lỗi → lead → user → resume | G03/G07/G17 | Error class, authority, human request version | Timeout != approval; stale answer |
| CLI/API resource discovery | G05/G09–G12/G16 | Installed/catalog/auth/inference/quota separate | Missing auth, model alias/entitlement mismatch |
| API profile → key reference → workflow | G12–G14/G18/G22 | Secret owner, env scope, gateway retries/accounting | Unknown billing, key leakage, fallback denied |
| Workspace/process → review/merge | G03/G05/G07/G18 | Resolved path, permission enforcement, child tree, base refs | Junction escape, conflict, orphan process |
| Skills → candidate → review → distribution | G20 | Source pin, license, tools/auth, instruction vs execution | Prompt injection, unpinned dependency |
| Knowledge/context → retrieval → summary | G06/G19 | Project scope, evidence links, conflicts, invalidation | Stale or unsupported summary |
| Budget reserve → run → reconcile | G14/G22 | One owner, cumulative/delta usage, unknown completion | Overshoot, doubled cost, subscription priced as API |

## 2. Bóc tách theo tầng

### Tầng reference evidence — G00–G08
Pin revision trước trace. Với mỗi reference, lưu entrypoint/actor/state writes/transactions/event producer/consumer/permission boundary/recovery/tests defined. Ngưỡng bằng chứng khác nhau: README → DOCUMENTED; actual call chain → CODE_TRACED; đọc test → TEST_DEFINED; runtime Windows cần experiment authorize sau.

Không clone rồi build để “xem nhanh”. Source-only inspection đủ cho giai đoạn này. Không bịa paths/symbols khi code budget chưa mở đủ. Report PARTIAL phải ghi trace đứt ở đâu để lead giao task nhỏ tiếp.

### Tầng client & API — G09–G16
Ba client profiles khác native API profile. Client có thể dùng subscription/login; API có key+endpoint và cách tính usage riêng. Không tái dùng credentials từ login store làm API key.

Adapter chung chỉ normalize contract đã biết; capability có source/version/freshness. Cancel/resume/approvals/events/model catalog không được mặc định hỗ trợ ở mọi provider. Schema mới thuộc app phải PROPOSED; không trình là vendor transcript.

Dify/LiteLLM/framework là candidate components. Cần edition/license/version và trách nhiệm sở hữu. Một task không được có hai scheduler tự chuyển state hoặc hai retry layers không phối hợp.

### Tầng durable orchestration — G17
State machine deterministic cần guard cho từng transition; lead có quyền đề nghị trong scope. Pending request phải persisted và correlated; request stale/expire/reject có semantics rõ.

Attempt/lease/idempotency/cancellation/reconciliation thiết kế theo failure boundaries. SQLite transaction có thể atomic local writes, không kéo external process/API effects vào exactly-once. Completion unknown phải quarantine/reconcile hoặc hỏi user theo quyền.

Task độc lập vẫn runnable khi sibling pending; không gom toàn workflow vào global wait. Reviewer acceptance khác exit0/inference finished.

### Tầng quyền và secrets — G18
Worktree giúp track/isolate changes trong Git, không ngăn tool đọc/ghi ngoài folder. Cần biết từng client enforce gì thực. Nếu quyền user yêu cầu không enforce được bằng documented interface, capability phải ghi limitation thay giả sandbox.

Windows path/process behavior cần thử spaces/Unicode/junction/drive/descendants và restart sau này. Vault là host-controlled reference; không đưa key vào lead prompt/log/event/Git. UI entry/login flow là blueprint, không xây hoặc xin key hiện tại.

### Tầng context & skills — G19–G20
Worker nhận brief và artifacts liên quan, source refs và acceptance, không shared transcript vô hạn. Summary giữ decisions/unknowns/authority/provenance và link original; không thu reasoning nội bộ.

Knowledge MVP candidate metadata+FTS, graph extension chỉ nếu query/relations cần và đo có lợi. Edges inferred không chứng minh fact. Skill Architect tư vấn selection; reviewer/tool policy quản lý execution/install rights. Skills/plugins có secrets và executable dependencies khác nhau, không cài từ star ranking.

### Tầng model intelligence & resources — G21–G22
External benchmark có harness/budget/dataset/version/date khác nhau, không rank bằng một score universal. Routing phải trong user allowlist/capability/quality thresholds/resource budgets; thiếu metric thì fallback explicit.

Accounting giữ observed/estimated/unknown. Không coi cancel/timeouts là chưa bị bill hoặc unknown price=0. Quota group/account pooling và concurrency reservation tránh tự vượt app budget; billed provider ceiling vẫn phụ thuộc actual provider behavior.

## 3. Gate chất lượng nghiên cứu

1. **Source gate:** mỗi material claim có nguồn pin/section/observation; failed fetch giữ visible.
2. **Contract gate:** options/events/routes/schema field có official evidence hoặc marked UNKNOWN. Sample app là SYNTHETIC.
3. **Ownership gate:** một source of truth cho task state, approval/review, secret refs và retries.
4. **Boundary gate:** permissions/workspace/client/auth/API semantics đúng; không hứa scope chưa enforce.
5. **Recovery gate:** each crash phase có expected recovery, duplicate/late handling và unknown side effect.
6. **Decision gate:** critical unknown làm recommendation conditional, không tự approve deployment.
7. **Handoff gate:** mỗi implementation item có inputs/scope/outputs/acceptance/deps/stop/rollback.

Gate do independent reviewer áp dụng bằng [checklist](REVIEW_CHECKLIST.md). Gemini self-check không thay review. Có thể accept nghiên cứu mô tả “chưa biết”, nhưng không accept capability tương ứng thành true.

## 4. Mẫu implementation task cần xuất từ G24

Mỗi item Ixx là **future PROPOSED**, không permission chạy:
- Objective và RQ IDs; một behavior có observable output.
- Inputs pinned: contract/schema/design claim IDs, base project state.
- Prerequisites/deps và critical unknowns; thiếu prerequisite thì STOP.
- Allowed paths chính xác; forbidden changes, tool/process/network/credential scope.
- Steps đủ để implement mà không tự thêm product scope.
- Output files và behavior; error/pending/retry semantics.
- Acceptance scenarios: setup → action → expected observable; tests meaningful cho durable state/permissions/credentials.
- Reviewer ownership, rollback/retention và exit conditions.
- Runtime smoke test/inference authorization khi cần; planning acceptance không tự cấp quyền.

Backlog không dùng “hoàn thiện UI/backend” như một task. Chia theo behavior: fixture event normalization; pending sibling dispatch; durable human answer; restart reconciliation; một provider contract; key-reference redaction, v.v. Task count do complexity thực quyết định, không nhồi để đạt số lượng.

## 5. Experiment sau nghiên cứu, chưa được chạy

Ưu tiên so reference/options cùng tiny repo/base ref/task/acceptance:
- Hai task độc lập, một pending human, task còn lại hoàn thành.
- Worker process crash/restart, duplicate terminal event và stale answer.
- Tool denied dù exit0, malformed event, missing auth/model.
- Worktree conflict/path escape/child process cleanup.
- API key redaction, quota group concurrency, unknown usage/billable timeout.
- Scoped retrieval vs full-context baseline, task success/usage/time có observed provenance.

Mỗi experiment cần scope/tool authorization, fixture, actual logs/versions, cleanup và limitation. Không báo pass từ việc viết scenario. Kết quả chưa có sẽ để NOT_RUN/UNKNOWN.

## 6. Chưa chốt tại thời điểm soạn

Final reuse/fork/build, provider/model lựa chọn, budget/quota, framework/dependency exception, auth state, Windows runtime compatibility, isolation implementation, benchmark scores, actual savings. [BRIEF](BRIEF.md) là authoritative scope baseline; các tài liệu kiến trúc trước đó là proposal cần đối chiếu evidence, không axioms.

